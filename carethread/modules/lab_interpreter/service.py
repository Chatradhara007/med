"""Orchestration service for M3 Lab Interpreter module.

Executes the complete deterministic clinical analysis pipeline:
1. Fetch canonical episodic record via single-table repository (PK = PATIENT#<id>)
2. Enforce verified provenance invariants on all input LabResult entities
3. Resolve reference ranges (Printed report range takes precedence over fallback)
4. Compute deterministic deviation and boundary status (below, within, above, unknown)
5. Cross-read against active Diagnoses and Medications (e.g. Creatinine + Metformin)
6. Rank findings deterministically (abnormal findings by descending deviation score)
7. Generate safety-verified patient-readable explanations via formatter
8. Return structured, machine-readable LabInterpretationReport
"""

from datetime import datetime, timezone
from typing import List, Optional

from carethread.shared.repository.interfaces import PatientRepositoryInterface
from carethread.shared.repository.exceptions import MissingProvenanceError
from carethread.shared.schemas.lab_result import LabResult
from carethread.shared.schemas.diagnosis import Diagnosis
from carethread.shared.schemas.medication import Medication
from carethread.shared.schemas.provenance import ProvenanceStatus
from carethread.modules.lab_interpreter.schemas import (
    FindingStatus,
    InterpretedLabFinding,
    LabInterpretationReport,
    ReferenceRangeSource,
)
from carethread.modules.lab_interpreter.reference_ranges import (
    ReferenceRangeRepository,
    get_default_fallback_repo,
    resolve_reference_range,
)
from carethread.modules.lab_interpreter.ranking import (
    calculate_deviation,
    rank_findings,
)
from carethread.modules.lab_interpreter.context import (
    evaluate_lab_context,
)
from carethread.modules.lab_interpreter.llm_adapter import (
    LabExplanationFormatterInterface,
    MockLabExplanationFormatter,
)


class LabInterpreterService:
    """Core domain service for analyzing and interpreting outpatient laboratory panels."""

    def __init__(
        self,
        repository: Optional[PatientRepositoryInterface] = None,
        fallback_repo: Optional[ReferenceRangeRepository] = None,
        formatter: Optional[LabExplanationFormatterInterface] = None,
    ) -> None:
        self.repository = repository
        self.fallback_repo = fallback_repo or get_default_fallback_repo()
        self.formatter = formatter or MockLabExplanationFormatter()

    def interpret_labs(
        self,
        patient_id: str,
        lab_results: List[LabResult],
        diagnoses: Optional[List[Diagnosis]] = None,
        medications: Optional[List[Medication]] = None,
    ) -> LabInterpretationReport:
        """Interpret a collection of LabResult entities against clinical context."""
        active_diagnoses = [d for d in (diagnoses or []) if getattr(d, "status", "active") == "active"]
        active_medications = medications or []

        raw_findings: List[InterpretedLabFinding] = []
        cross_module_alerts: List[str] = []

        for lab in lab_results:
            # 1. Enforce strict provenance invariant
            if lab.provenance is None or lab.provenance.source is None:
                raise MissingProvenanceError(
                    f"Provenance Invariant Violation: LabResult for analyte '{lab.analyte}' "
                    "lacks mandatory source citation."
                )

            # 2. Reference range precedence resolution
            # Printed report range takes absolute precedence over fallback
            ref_low, ref_high, ref_source = resolve_reference_range(
                analyte=lab.analyte,
                report_low=lab.ref_low,
                report_high=lab.ref_high,
                fallback_repo=self.fallback_repo,
            )

            # 3. Deterministic deviation analysis
            status, deviation_score = calculate_deviation(
                value=lab.value,
                ref_low=ref_low,
                ref_high=ref_high,
            )

            # 4. Context cross-reading against active Diagnoses and Medications
            context_res = evaluate_lab_context(
                analyte=lab.analyte,
                status=status,
                value=lab.value,
                unit=lab.unit,
                active_diagnoses=active_diagnoses,
                active_medications=active_medications,
            )
            if context_res.cross_module_alert:
                cross_module_alerts.append(context_res.cross_module_alert)

            # 5. Preserve low-confidence uncertainty
            # If M1 flagged item as needs_review or confidence < 0.85, do NOT promote to confirmed
            source_conf = lab.provenance.confidence
            is_low_confidence = (
                lab.provenance.status == ProvenanceStatus.NEEDS_REVIEW
                or (source_conf is not None and source_conf < 0.85)
            )
            review_status = "needs_review" if is_low_confidence else "confirmed"

            finding = InterpretedLabFinding(
                analyte=lab.analyte,
                value=lab.value,
                unit=lab.unit,
                ref_low=ref_low,
                ref_high=ref_high,
                ref_source=ref_source,
                status=status,
                deviation_score=deviation_score,
                rank=1,  # Placeholder, assigned by rank_findings
                context_diagnoses=context_res.diagnoses,
                context_medications=context_res.medications,
                context_notes=context_res.notes,
                explanation="",  # Formatted after ranking
                provenance=lab.provenance,
                confidence=source_conf,
                review_status=review_status,
            )
            raw_findings.append(finding)

        # 6. Deterministic finding ranking
        ranked_findings = rank_findings(raw_findings)

        # 7. Generate patient-readable explanations via formatter
        final_findings: List[InterpretedLabFinding] = []
        for f in ranked_findings:
            explanation = self.formatter.format_explanation(f)
            updated = f.model_copy(update={"explanation": explanation})
            final_findings.append(updated)

        # 8. Compile report
        abnormal_count = sum(
            1 for f in final_findings if f.status in (FindingStatus.ABOVE, FindingStatus.BELOW)
        )
        top_findings = [
            f for f in final_findings if f.status in (FindingStatus.ABOVE, FindingStatus.BELOW)
        ][:3]

        return LabInterpretationReport(
            patient_id=patient_id,
            total_findings=len(final_findings),
            abnormal_count=abnormal_count,
            top_findings=top_findings,
            all_findings=final_findings,
            cross_module_alerts=list(dict.fromkeys(cross_module_alerts)),
            generated_at=datetime.now(timezone.utc).isoformat(),
        )

    def interpret_patient_labs(self, patient_id: str) -> LabInterpretationReport:
        """Query canonical patient context from DynamoDB/repository and interpret all lab findings."""
        if not self.repository:
            raise ValueError("Repository is required to interpret patient labs by patient_id.")

        context = self.repository.get_patient_context(patient_id)
        return self.interpret_labs(
            patient_id=patient_id,
            lab_results=context.lab_results,
            diagnoses=context.diagnoses,
            medications=context.medications,
        )
