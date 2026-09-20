"""Deterministic clinical escalation rule engine.

THE RULES DECIDE. LLMS FORMAT AND TRANSLATE.
All clinical escalation triggers are loaded from static rules.yaml.
No rule can be invented or hallucinated at runtime.
"""

import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import yaml

from carethread.shared.schemas.alert_rule import AlertRule, AlertSeverity, FiredAlert
from carethread.shared.schemas.diagnosis import Diagnosis

DEFAULT_RULES_PATH = os.path.join(os.path.dirname(__file__), "rules.yaml")


def load_rules(yaml_path: Optional[str] = None) -> List[AlertRule]:
    """Load and validate static rules from rules.yaml."""
    path = yaml_path or DEFAULT_RULES_PATH
    if not os.path.exists(path):
        raise FileNotFoundError(f"Static rules file not found: {path}")

    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}

    raw_rules = data.get("rules", [])
    parsed_rules: List[AlertRule] = []
    for r in raw_rules:
        parsed_rules.append(AlertRule(
            id=r["id"],
            when=r.get("when"),
            severity=AlertSeverity(r["severity"].lower()),
            message=r["message"],
            applies_if_diagnosis=r.get("applies_if_diagnosis")
        ))
    return parsed_rules


def _matches_diagnosis(rule_diagnoses: Optional[List[str]], patient_diagnoses: List[Diagnosis]) -> bool:
    """Check if any of the rule's qualifying diagnosis terms match active patient diagnoses."""
    if not rule_diagnoses:
        return True  # Rule applies generally

    import re

    patient_diag_terms = []
    for d in patient_diagnoses:
        if d.label and d.label.strip():
            patient_diag_terms.append(d.label.strip().lower())
        if d.code_or_slug and d.code_or_slug.strip():
            patient_diag_terms.append(d.code_or_slug.strip().lower())
        if d.icd_hint and d.icd_hint.strip():
            patient_diag_terms.append(d.icd_hint.strip().lower())

    for req in rule_diagnoses:
        req_norm = req.strip().lower()
        if not req_norm:
            continue
        pattern = r"\b" + re.escape(req_norm) + r"\b"
        for p_term in patient_diag_terms:
            if req_norm == p_term or re.search(pattern, p_term):
                return True
    return False


def evaluate_escalation_rules(
    patient_diagnoses: List[Diagnosis],
    symptoms: Dict[str, Any],
    rules: Optional[List[AlertRule]] = None
) -> List[FiredAlert]:
    """Deterministically evaluate patient symptoms against static clinical rules."""
    active_rules = rules if rules is not None else load_rules()
    fired_alerts: List[FiredAlert] = []
    now_iso = datetime.now(timezone.utc).isoformat()

    for rule in active_rules:
        # Check diagnosis qualification
        if not _matches_diagnosis(rule.applies_if_diagnosis, patient_diagnoses):
            continue

        triggered = False
        context_evidence: Dict[str, Any] = {}

        # 1. fever_persistent: symptom.fever_f > 101 for 48h
        if rule.id == "fever_persistent":
            fever = float(symptoms.get("fever_f") or 0.0)
            hours = float(symptoms.get("fever_hours") or 0.0)
            if fever > 101.0 and hours >= 48.0:
                triggered = True
                context_evidence = {"fever_f": fever, "fever_hours": hours}

        # 2. post_cardiac_chest_pain: symptom.chest_pain == true
        elif rule.id == "post_cardiac_chest_pain":
            chest_pain = bool(symptoms.get("chest_pain"))
            if chest_pain:
                triggered = True
                context_evidence = {
                    "chest_pain": True,
                    "qualifying_diagnoses": [d.label for d in patient_diagnoses]
                }

        # 3. hypoglycemia_acute: symptom.blood_glucose < 70
        elif rule.id == "hypoglycemia_acute":
            bg = symptoms.get("blood_glucose")
            if bg is not None and float(bg) < 70.0:
                triggered = True
                context_evidence = {"blood_glucose": float(bg)}

        # 4. severe_shortness_of_breath: symptom.shortness_of_breath == true
        elif rule.id == "severe_shortness_of_breath":
            sob = bool(symptoms.get("shortness_of_breath"))
            if sob:
                triggered = True
                context_evidence = {"shortness_of_breath": True}

        # 5. hypertensive_crisis: vitals.systolic_bp > 180
        elif rule.id == "hypertensive_crisis":
            sbp = symptoms.get("systolic_bp")
            if sbp is not None and float(sbp) > 180.0:
                triggered = True
                context_evidence = {"systolic_bp": float(sbp)}

        if triggered:
            fired_alerts.append(FiredAlert(
                alert_id=f"alt_{rule.id}_{int(datetime.now(timezone.utc).timestamp())}",
                rule_id=rule.id,
                severity=rule.severity,
                message=rule.message,
                fired_at=now_iso,
                acknowledged=False,
                cross_module_context=context_evidence
            ))

    return fired_alerts
