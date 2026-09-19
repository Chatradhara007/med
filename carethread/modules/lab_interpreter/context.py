"""Cross-module clinical context evaluation for laboratory findings.

CRITICAL SAFETY CONSTRAINTS:
1. This module MUST NOT create a new Diagnosis entity.
2. This module MUST NOT prescribe, alter, or discontinue any medication.
3. Consumes ONLY confirmed active Diagnoses and Medications from the canonical record.
4. Identifies documented contextual interactions without autonomous medical reasoning.
"""

from dataclasses import dataclass
import re
from typing import List, Optional, Set, Tuple, Union

from carethread.shared.schemas.diagnosis import Diagnosis
from carethread.shared.schemas.medication import Medication
from carethread.modules.lab_interpreter.schemas import FindingStatus


@dataclass
class ClinicalContextResult:
    """Contextual associations detected for an analyte finding."""
    diagnoses: List[str]
    medications: List[str]
    notes: List[str]
    cross_module_alert: Optional[str] = None


# Drug keywords associated with specific analyte monitoring
RAAS_INHIBITORS: Set[str] = {
    "ramipril", "enalapril", "lisinopril", "perindopril",
    "telmisartan", "losartan", "valsartan", "olmesartan", "candesartan",
    "spironolactone", "eplerenone"
}

STATINS: Set[str] = {
    "atorvastatin", "rosuvastatin", "simvastatin", "pravastatin"
}

ANTIDIABETICS: Set[str] = {
    "metformin", "glimepiride", "gliclazide", "glipizide",
    "sitagliptin", "vildagliptin", "linagliptin", "dapagliflozin",
    "empagliflozin", "canagliflozin", "insulin"
}


def _matches_med(med: Medication, keywords: Set[str]) -> bool:
    """Check if a medication's brand name or active salt contains any keyword."""
    name_clean = (med.name or "").lower()
    salt_clean = (med.salt or "").lower()
    for kw in keywords:
        if kw in name_clean or kw in salt_clean:
            return True
    return False


def evaluate_lab_context(
    analyte: str,
    status: FindingStatus,
    value: Union[float, str],
    unit: str,
    active_diagnoses: List[Diagnosis],
    active_medications: List[Medication],
) -> ClinicalContextResult:
    """Cross-read an analyte result against active diagnoses and medications."""
    analyte_clean = analyte.strip().lower()
    context_diagnoses: List[str] = []
    context_medications: List[str] = []
    context_notes: List[str] = []
    cross_module_alert: Optional[str] = None

    # 1. Renal Function (Creatinine / BUN) + Metformin
    if any(k in analyte_clean for k in ["creatinine", "blood urea nitrogen", "bun"]):
        if status == FindingStatus.ABOVE:
            for med in active_medications:
                if "metformin" in (med.name or "").lower() or "metformin" in (med.salt or "").lower():
                    context_medications.append(med.name)
                    context_notes.append(
                        f"Patient is prescribed {med.name} ({med.strength}). "
                        f"Elevated {analyte} indicates reduced renal filtration; "
                        "continuing Metformin during renal elevation carries advisory risk of lactic acidosis. "
                        "Requires clinical review."
                    )
                    cross_module_alert = (
                        f"Outpatient {analyte} is {value} {unit} (elevated). "
                        f"Because your discharge summary prescribed {med.name} {med.strength}, "
                        "continuing Metformin during acute renal elevation can induce lactic acidosis. "
                        "Contact treating physician immediately."
                    )
        # Check for chronic kidney disease / renal impairment diagnoses
        for diag in active_diagnoses:
            d_lower = diag.label.lower()
            if any(k in d_lower for k in ["kidney", "renal", "ckd", "nephro"]):
                context_diagnoses.append(diag.label)
                context_notes.append(
                    f"Patient has documented diagnosis of {diag.label}. "
                    f"Renal parameter {analyte} monitored in this context."
                )

    # 2. Serum Potassium + RAAS Inhibitors / Potassium-sparing Diuretics
    if "potassium" in analyte_clean:
        if status in (FindingStatus.ABOVE, FindingStatus.BELOW):
            for med in active_medications:
                if _matches_med(med, RAAS_INHIBITORS):
                    context_medications.append(med.name)
                    context_notes.append(
                        f"Patient is prescribed {med.name}. "
                        "Abnormal potassium levels require close monitoring with renin-angiotensin-aldosterone inhibitors."
                    )

    # 3. Glycemic Markers (Blood Sugar / HbA1c) + Diabetes
    if any(k in analyte_clean for k in ["blood sugar", "glucose", "hba1c"]):
        for diag in active_diagnoses:
            d_lower = diag.label.lower()
            if any(k in d_lower for k in ["diabet", "t2dm", "t1dm", "dm"]):
                context_diagnoses.append(diag.label)
                context_notes.append(
                    f"Patient has documented diagnosis of {diag.label}. "
                    "Glycemic reading evaluated in context of established condition."
                )
        for med in active_medications:
            if _matches_med(med, ANTIDIABETICS):
                context_medications.append(med.name)

    # 4. Cardiac Biomarkers (Troponin, CPK-MB) + Coronary Artery Disease / MI
    if any(k in analyte_clean for k in ["troponin", "cpk"]):
        for diag in active_diagnoses:
            d_lower = diag.label.lower()
            if any(k in d_lower for k in ["cad", "coronary", "infarction", "angina", "cardiac"]):
                context_diagnoses.append(diag.label)
                context_notes.append(
                    f"Patient has documented diagnosis of {diag.label}. "
                    "Cardiac biomarker evaluated in context of coronary history."
                )

    # 5. Lipid Panel + Statins / Dyslipidemia
    if any(k in analyte_clean for k in ["cholesterol", "triglyceride", "ldl", "hdl"]):
        for med in active_medications:
            if _matches_med(med, STATINS):
                context_medications.append(med.name)
        for diag in active_diagnoses:
            d_lower = diag.label.lower()
            if any(k in d_lower for k in ["lipid", "cholesterol", "cad", "coronary"]):
                context_diagnoses.append(diag.label)

    return ClinicalContextResult(
        diagnoses=list(dict.fromkeys(context_diagnoses)),
        medications=list(dict.fromkeys(context_medications)),
        notes=list(dict.fromkeys(context_notes)),
        cross_module_alert=cross_module_alert,
    )
