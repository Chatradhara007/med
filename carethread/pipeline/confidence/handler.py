"""GateConfidence / PersistEntities / MarkReady states.

One Lambda backs three Step Functions states (selected by ``stage``) so the
execution history stays readable while the entity-building code lives in one
place.

Two invariants are enforced here and nowhere else:

* **Confidence gating.** ``confidence >= 0.85`` becomes ``confirmed``; below it
  the field stays ``needs_review`` and shows as an amber chip until the patient
  accepts or corrects it.
* **Never infer a missing value.** The canonical ``Medication`` contract
  requires a salt, strength, frequency and duration, but a discharge summary
  may not print all four. Rather than let a model complete them from medical
  knowledge, the absent field is recorded as the literal string
  ``"not stated"`` and the entity is forced to ``needs_review`` regardless of
  the model's own confidence. A missing dose stays missing.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple

from carethread.pipeline.common import (
    PipelineError,
    envelope_from_event,
    get_pipeline_repository,
    now_iso,
    update_document_status,
)
from carethread.shared.repository.interfaces import PatientRepositoryInterface
from carethread.shared.schemas.diagnosis import Diagnosis
from carethread.shared.schemas.document import DocumentStatus, DocumentType
from carethread.shared.schemas.lab_result import LabResult
from carethread.shared.schemas.medication import Medication
from carethread.shared.schemas.provenance import (
    CONFIDENCE_THRESHOLD,
    ProvenanceEnvelope,
    ProvenanceSource,
    ProvenanceStatus,
    evaluate_confidence,
)

logger = logging.getLogger(__name__)

NOT_STATED = "not stated"


def _clean(value: Any) -> Optional[str]:
    """Return a trimmed string, or None for absent/blank/null values."""
    if value is None:
        return None
    text = str(value).strip()
    if not text or text.lower() in ("null", "none", "n/a", "na", "-"):
        return None
    return text


def _build_envelope(
    field: str, value: Dict[str, Any], obj: Dict[str, Any], degraded: bool
) -> Tuple[ProvenanceEnvelope, bool]:
    """Build a provenance envelope, applying the 0.85 gate.

    ``degraded`` forces ``needs_review`` when a contract-required field was not
    present in the document.
    """
    source_raw = obj.get("source") or {}
    try:
        confidence = float(obj.get("confidence", 0.0))
    except (TypeError, ValueError):
        confidence = 0.0
    confidence = max(0.0, min(1.0, confidence))

    verbatim = _clean(source_raw.get("verbatim"))
    if not verbatim:
        # The one invariant: no value reaches the UI without a source.
        raise ValueError("entity carries no verbatim source citation")

    source = ProvenanceSource(
        doc_id=str(source_raw.get("doc_id", "")).strip(),
        page=int(source_raw.get("page", 1) or 1),
        bbox=[float(c) for c in (source_raw.get("bbox") or [0.0, 0.0, 1000.0, 1000.0])],
        verbatim=verbatim,
    )

    status = evaluate_confidence(confidence)
    if degraded or not obj.get("_bbox_exact", True):
        # A page-level citation or an unstated field is not confirmable on its
        # own; the patient resolves it in the UI.
        status = ProvenanceStatus.NEEDS_REVIEW

    envelope = ProvenanceEnvelope(
        field=field,
        value=value,
        source=source,
        confidence=confidence,
        status=status,
    )
    return envelope, status == ProvenanceStatus.NEEDS_REVIEW


def build_medications(items: List[Dict[str, Any]]) -> Tuple[List[Medication], List[str]]:
    """Convert extracted medication objects into canonical entities."""
    medications: List[Medication] = []
    problems: List[str] = []

    for obj in items:
        name = _clean(obj.get("name"))
        if not name:
            problems.append("medication without a name was discarded")
            continue

        salt = _clean(obj.get("salt"))
        strength = _clean(obj.get("strength"))
        freq = _clean(obj.get("freq"))
        duration_raw = obj.get("duration_days")

        # Absent contract-required fields are recorded as unstated, never guessed.
        degraded = not all([salt, strength, freq]) or duration_raw in (None, "")
        try:
            duration_days = max(0, int(duration_raw)) if duration_raw not in (None, "") else 0
        except (TypeError, ValueError):
            duration_days = 0
            degraded = True

        value = {
            "name": name,
            "salt": salt or name,
            "strength": strength or NOT_STATED,
            "freq": freq or NOT_STATED,
            "duration_days": duration_days,
        }

        try:
            envelope, _ = _build_envelope("medication", value, obj, degraded)
        except (ValueError, TypeError) as exc:
            problems.append(f"medication '{name}' rejected: {exc}")
            continue

        medications.append(
            Medication(
                name=name,
                # Where no separate salt is printed, the prescribed name is the
                # only active-ingredient text the document actually contains.
                salt=salt or name,
                strength=strength or NOT_STATED,
                form=_clean(obj.get("form")) or "tablet",
                freq=freq or NOT_STATED,
                duration_days=duration_days,
                instructions=_clean(obj.get("instructions")),
                provenance=envelope,
            )
        )
    return medications, problems


def build_diagnoses(items: List[Dict[str, Any]]) -> Tuple[List[Diagnosis], List[str]]:
    """Convert extracted diagnosis objects into canonical entities."""
    diagnoses: List[Diagnosis] = []
    problems: List[str] = []

    for obj in items:
        label = _clean(obj.get("label"))
        if not label:
            problems.append("diagnosis without a label was discarded")
            continue
        try:
            envelope, _ = _build_envelope(
                "diagnosis", {"label": label, "icd_hint": _clean(obj.get("icd_hint"))}, obj, False
            )
        except (ValueError, TypeError) as exc:
            problems.append(f"diagnosis '{label}' rejected: {exc}")
            continue

        diagnoses.append(
            Diagnosis(
                label=label,
                icd_hint=_clean(obj.get("icd_hint")),
                provenance=envelope,
            )
        )
    return diagnoses, problems


def build_lab_results(items: List[Dict[str, Any]]) -> Tuple[List[LabResult], List[str]]:
    """Convert extracted lab rows into canonical entities.

    The reference range printed on the report takes absolute precedence and is
    stored as ``ref_source='printed'``. A report that prints no range leaves
    the bounds null; M3 resolves the fallback later and labels it as such. No
    range is ever invented here.
    """
    results: List[LabResult] = []
    problems: List[str] = []

    for obj in items:
        analyte = _clean(obj.get("analyte"))
        if not analyte:
            problems.append("lab row without an analyte was discarded")
            continue

        raw_value = obj.get("value")
        if raw_value is None or str(raw_value).strip() == "":
            problems.append(f"lab row '{analyte}' has no value and was discarded")
            continue
        try:
            value: Any = float(raw_value)
        except (TypeError, ValueError):
            value = str(raw_value).strip()

        unit = _clean(obj.get("unit"))
        degraded = unit is None

        def _bound(key: str) -> Optional[float]:
            candidate = obj.get(key)
            if candidate is None or str(candidate).strip() == "":
                return None
            try:
                return float(candidate)
            except (TypeError, ValueError):
                return None

        ref_low, ref_high = _bound("ref_low"), _bound("ref_high")
        printed = ref_low is not None or ref_high is not None

        try:
            envelope, _ = _build_envelope(
                "lab_result",
                {"analyte": analyte, "value": value, "unit": unit or NOT_STATED},
                obj,
                degraded,
            )
        except (ValueError, TypeError) as exc:
            problems.append(f"lab row '{analyte}' rejected: {exc}")
            continue

        results.append(
            LabResult(
                analyte=analyte,
                value=value,
                unit=unit or NOT_STATED,
                ref_low=ref_low,
                ref_high=ref_high,
                ref_source="printed" if printed else "none",
                provenance=envelope,
            )
        )
    return results, problems


def gate_confidence(event: Dict[str, Any]) -> Dict[str, Any]:
    """Split extracted fields into confirmed and needs_review."""
    envelope = envelope_from_event(event)
    payload = envelope.get("extraction")
    if not isinstance(payload, dict):
        raise PipelineError("GateConfidence reached with no extraction payload")

    medications, med_problems = build_medications(payload.get("medications") or [])
    diagnoses, diag_problems = build_diagnoses(payload.get("diagnoses") or [])
    labs, lab_problems = build_lab_results(payload.get("lab_results") or [])

    entities = [
        *(("medication", m.provenance) for m in medications),
        *(("diagnosis", d.provenance) for d in diagnoses),
        *(("lab_result", l.provenance) for l in labs),
    ]
    needs_review = [name for name, prov in entities if prov.status == ProvenanceStatus.NEEDS_REVIEW]

    envelope["gated"] = {
        "medications": [m.model_dump(mode="json") for m in medications],
        "diagnoses": [d.model_dump(mode="json") for d in diagnoses],
        "lab_results": [l.model_dump(mode="json") for l in labs],
    }
    envelope["confidence_threshold"] = CONFIDENCE_THRESHOLD
    envelope["needs_review_count"] = len(needs_review)
    envelope["entity_count"] = len(entities)
    envelope["gate_problems"] = med_problems + diag_problems + lab_problems

    logger.info(
        "Gated document %s: %d entities, %d need review",
        envelope["doc_id"],
        len(entities),
        len(needs_review),
    )
    return envelope


def persist_entities(
    event: Dict[str, Any], repository: Optional[PatientRepositoryInterface] = None
) -> Dict[str, Any]:
    """Batch-write MED#/LAB#/DIAG# rows into the canonical partition."""
    envelope = envelope_from_event(event)
    patient_id = envelope["patient_id"]
    gated = envelope.get("gated")
    if not isinstance(gated, dict):
        raise PipelineError("PersistEntities reached before GateConfidence")

    repo = get_pipeline_repository(repository)
    timestamp = now_iso()
    written = 0

    for raw in gated.get("diagnoses") or []:
        repo.create_diagnosis(patient_id, Diagnosis.model_validate(raw))
        written += 1
    for raw in gated.get("medications") or []:
        repo.create_medication(patient_id, Medication.model_validate(raw))
        written += 1
    for raw in gated.get("lab_results") or []:
        repo.create_lab_result(patient_id, LabResult.model_validate(raw), timestamp=timestamp)
        written += 1

    envelope["persisted_count"] = written
    logger.info("Persisted %d entities for patient %s", written, patient_id)
    return envelope


def mark_ready(
    event: Dict[str, Any], repository: Optional[PatientRepositoryInterface] = None
) -> Dict[str, Any]:
    """Close out the document: ready, or review_required when chips remain."""
    envelope = envelope_from_event(event)
    repo = get_pipeline_repository(repository)

    needs_review = int(envelope.get("needs_review_count") or 0)
    status = DocumentStatus.REVIEW_REQUIRED if needs_review else DocumentStatus.READY

    try:
        document_type = DocumentType(envelope.get("document_type", DocumentType.UNKNOWN.value))
    except ValueError:
        document_type = DocumentType.UNKNOWN

    update_document_status(
        repo,
        envelope["patient_id"],
        envelope["doc_id"],
        status,
        document_type=document_type if document_type != DocumentType.UNKNOWN else None,
    )
    envelope["final_status"] = status.value
    return envelope


def handle_failure(
    event: Dict[str, Any], repository: Optional[PatientRepositoryInterface] = None
) -> Dict[str, Any]:
    """Mark the document failed with a reason the UI can surface."""
    payload = dict(event or {})

    # The state machine hands the whole failed state under "input", because a
    # Rasterise failure happens before patient_id/doc_id exist and a JSONPath
    # for them would fail the HandleFailure state itself.
    if isinstance(payload.get("input"), dict):
        nested = dict(payload["input"])
        nested.setdefault("error", payload.get("error"))
        payload = nested

    error = payload.get("error") or {}
    reason = (
        error.get("Cause")
        or error.get("Error")
        or payload.get("unsupported_reason")
        or "We could not read this document. Please try uploading it again."
    )
    # Step Functions Causes carry a full stack trace; never show that to a patient.
    reason = str(reason).splitlines()[0][:500]

    try:
        envelope = envelope_from_event(payload)
    except PipelineError:
        logger.error("HandleFailure could not identify the document: %s", reason)
        return {"final_status": DocumentStatus.FAILED.value, "error_reason": reason}

    repo = get_pipeline_repository(repository)
    update_document_status(
        repo,
        envelope["patient_id"],
        envelope["doc_id"],
        DocumentStatus.FAILED,
        error_reason=reason,
    )
    envelope["final_status"] = DocumentStatus.FAILED.value
    envelope["error_reason"] = reason
    return envelope


_STAGES = {
    "gate": gate_confidence,
    "persist": persist_entities,
    "mark_ready": mark_ready,
    "fail": handle_failure,
}


def handler(event: Dict[str, Any], context: Any = None) -> Dict[str, Any]:
    """Lambda entrypoint. ``stage`` selects which Step Functions state this is."""
    payload = dict(event or {})
    stage = payload.pop("stage", "gate")
    try:
        stage_fn = _STAGES[stage]
    except KeyError:
        raise PipelineError(
            f"Unknown pipeline stage '{stage}'; expected one of {sorted(_STAGES)}"
        ) from None
    return stage_fn(payload)
