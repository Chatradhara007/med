"""Care Plan domain service.

Converts canonical patient record into a day-by-day care plan (Day 0 to Day 6)
across four daily slots (morning, afternoon, evening, night).
Evaluates deterministic escalation rules from static rules.yaml.
"""

from typing import Any, Dict, List, Optional, Tuple
from carethread.shared.schemas.plan_entry import PlanEntry, SlotName
from carethread.shared.schemas.medication import Medication
from carethread.shared.schemas.diagnosis import Diagnosis
from carethread.shared.schemas.alert_rule import AlertRule, FiredAlert
from carethread.shared.schemas.provenance import (
    ProvenanceEnvelope,
    ProvenanceStatus,
)
from carethread.shared.schemas.extraction import DischargeFollowup, DischargeRestriction
from carethread.shared.repository.interfaces import PatientRepositoryInterface
from carethread.shared.repository.exceptions import MissingProvenanceError, PatientNotFoundError

from .rules import load_rules, evaluate_escalation_rules as eval_rules
from .bedrock_formatter import get_care_plan_formatter
from .formatter import LLMFormatterInterface, MockLLMFormatter
from .schemas import CarePlanResult, SymptomReport

DEFAULT_SLOT_HOURS = {
    SlotName.MORNING: "08:00",
    SlotName.AFTERNOON: "13:00",
    SlotName.EVENING: "19:00",
    SlotName.NIGHT: "21:00",
}


def map_frequency_to_slots(freq: str, instructions: Optional[str] = None, drug_name: str = "") -> List[SlotName]:
    """Deterministically map clinical frequency string into standard timetable slots."""
    f = freq.strip().upper()
    instr = (instructions or "").lower()
    name = drug_name.lower()

    if "statin" in name or "atorvastatin" in name or "rosuvastatin" in name or "hs" in f.lower() or "bedtime" in instr:
        return [SlotName.NIGHT]

    if f in ("OD", "ONCE DAILY", "DAILY", "1 TIME A DAY"):
        if "night" in instr or "evening" in instr:
            return [SlotName.NIGHT]
        return [SlotName.MORNING]

    if f in ("BD", "BID", "TWICE DAILY", "2 TIMES A DAY"):
        return [SlotName.MORNING, SlotName.NIGHT]

    if f in ("TDS", "TID", "THREE TIMES DAILY", "3 TIMES A DAY"):
        return [SlotName.MORNING, SlotName.AFTERNOON, SlotName.NIGHT]

    if f in ("QID", "QDS", "FOUR TIMES DAILY", "4 TIMES A DAY"):
        return [SlotName.MORNING, SlotName.AFTERNOON, SlotName.EVENING, SlotName.NIGHT]

    if f in ("PRN", "AS NEEDED", "SOS"):
        return [SlotName.AFTERNOON]

    # Default fallback to morning
    return [SlotName.MORNING]


class CarePlanService:
    """Service that reads the canonical patient record and compiles a structured 7-day care plan."""

    def __init__(
        self,
        repository: PatientRepositoryInterface,
        formatter: Optional[LLMFormatterInterface] = None,
        rules_path: Optional[str] = None
    ):
        self.repo = repository
        self.formatter = formatter or get_care_plan_formatter()
        self.rules_path = rules_path
        self._static_rules = load_rules(rules_path)

    def generate_care_plan(
        self,
        patient_id: str,
        days: int = 7,
        persist: bool = True,
        restrictions: Optional[List[DischargeRestriction]] = None,
        followups: Optional[List[DischargeFollowup]] = None
    ) -> CarePlanResult:
        """Convert canonical medications, restrictions, and follow-ups into structured PlanEntry items."""
        if not patient_id or not patient_id.strip():
            raise ValueError("patient_id must be provided")

        context = self.repo.get_patient_context(patient_id)
        if not context.patient:
            raise PatientNotFoundError(f"Patient {patient_id} does not exist")

        existing_entries_map: Dict[Tuple[int, str], PlanEntry] = {
            (e.day_index, e.slot.value if hasattr(e.slot, "value") else str(e.slot)): e
            for e in context.plan_entries
        }

        generated_entries: List[PlanEntry] = []

        # 1. Map Prescriptions to Slots
        for med in context.medications:
            if not med.provenance or not getattr(med.provenance, "source", None):
                raise MissingProvenanceError(f"Medication {med.name} lacks verified provenance citation")

            slots = map_frequency_to_slots(med.freq, med.instructions, med.name)
            med_duration = med.duration_days if med.duration_days and med.duration_days > 0 else days
            active_days = min(med_duration, days)

            for day_idx in range(active_days):
                for slot in slots:
                    action_text = self.formatter.format_medication_action(med, slot)
                    slot_str = slot.value

                    # Preserve adherence status if dose was already confirmed taken
                    existing = existing_entries_map.get((day_idx, slot_str))
                    done_flag = existing.done if existing else False
                    completed_ts = existing.completed_at if existing else None

                    # Construct PlanEntry with inherited provenance
                    entry = PlanEntry(
                        day_index=day_idx,
                        slot=slot,
                        action=action_text,
                        med_ref=med.sk,
                        time_target=DEFAULT_SLOT_HOURS.get(slot, "08:00"),
                        done=done_flag,
                        completed_at=completed_ts,
                        provenance=med.provenance
                    )
                    generated_entries.append(entry)

        # 2. Map Documented Restrictions
        if restrictions:
            for r in restrictions:
                if not r.provenance or not getattr(r.provenance, "source", None):
                    raise MissingProvenanceError(f"Restriction '{r.text}' lacks verified provenance citation")

                action_text = self.formatter.format_instruction(f"Restriction: {r.text}")
                # Place restriction in Morning slot for Day 0 to Day 6
                for day_idx in range(days):
                    entry = PlanEntry(
                        day_index=day_idx,
                        slot=SlotName.MORNING,
                        action=action_text,
                        med_ref=f"RESTRICTION#{day_idx}",
                        time_target=DEFAULT_SLOT_HOURS[SlotName.MORNING],
                        done=False,
                        provenance=r.provenance
                    )
                    generated_entries.append(entry)

        # 3. Map Documented Follow-ups
        if followups:
            for f in followups:
                if not f.provenance or not getattr(f.provenance, "source", None):
                    raise MissingProvenanceError(f"Follow-up '{f.what}' lacks verified provenance citation")

                action_text = self.formatter.format_instruction(f"Follow-up Appointment: {f.what} ({f.when})")
                # Default follow-up slot on Day 6 (end of post-discharge week)
                entry = PlanEntry(
                    day_index=min(6, days - 1),
                    slot=SlotName.AFTERNOON,
                    action=action_text,
                    med_ref="FOLLOWUP#opd",
                    time_target=DEFAULT_SLOT_HOURS[SlotName.AFTERNOON],
                    done=False,
                    provenance=f.provenance
                )
                generated_entries.append(entry)

        # 4. Idempotent Persistence
        if persist:
            for entry in generated_entries:
                self.repo.create_plan_entry(patient_id, entry)

        return CarePlanResult(
            patient_id=patient_id,
            days_covered=days,
            entries=generated_entries,
            alerts=context.alerts
        )

    def evaluate_escalation_rules(
        self,
        patient_id: str,
        symptoms: SymptomReport,
        persist: bool = True
    ) -> List[FiredAlert]:
        """Evaluate static escalation rules against active patient record and symptoms."""
        context = self.repo.get_patient_context(patient_id)
        symptoms_dict = symptoms.model_dump()

        fired_alerts = eval_rules(
            patient_diagnoses=context.diagnoses,
            symptoms=symptoms_dict,
            rules=self._static_rules
        )

        if persist:
            for alert in fired_alerts:
                self.repo.create_alert(patient_id, alert)

        return fired_alerts
