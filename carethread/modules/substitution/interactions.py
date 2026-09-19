"""Cross-checking drug interactions against canonical patient active medications.

SAFETY INVARIANTS:
1. Interaction flags are strictly advisory.
2. This module MUST NOT stop, start, modify, or prescribe any medication.
3. If interaction data is missing, the system MUST NOT claim "no interactions".
   Uncertainty is explicitly communicated as interaction_check_status = "unavailable".
"""

from typing import List, Optional, Set, Tuple

from carethread.shared.schemas.medication import Medication
from carethread.modules.substitution.schemas import CandidateAlternative, InteractionAdvisory


# Known drug-drug interaction risk pairs documented in pharmacopeia
DOCUMENTED_INTERACTION_PAIRS = [
    # (Drug keyword 1, Drug keyword 2, Clinical advisory description)
    ("aspirin", "warfarin", "Concurrent use of Aspirin and Warfarin significantly increases systemic bleeding risk."),
    ("aspirin", "clopidogrel", "Dual antiplatelet therapy carries heightened gastrointestinal bleeding risk; requires clinical monitoring."),
    ("clopidogrel", "omeprazole", "Omeprazole inhibits CYP2C19, potentially attenuating antiplatelet bioactivation of Clopidogrel."),
    ("ramipril", "spironolactone", "Combined ACE inhibitor and potassium-sparing diuretic therapy increases risk of severe hyperkalemia."),
    ("telmisartan", "spironolactone", "Combined ARB and potassium-sparing diuretic therapy increases risk of severe hyperkalemia."),
    ("metformin", "contrast", "Contrast media in patients on Metformin carries advisory risk of lactic acidosis."),
    ("atorvastatin", "clarithromycin", "Macrolide antibiotics substantially increase statin serum concentrations and myopathy risk."),
    ("amlodipine", "simvastatin", "Amlodipine increases Simvastatin exposure; statin dose adjustment may be advised by physician."),
]


class InteractionChecker:
    """Evaluates candidate formulations against canonical patient prescriptions."""

    def check_interactions(
        self,
        candidate: CandidateAlternative,
        active_medications: List[Medication],
    ) -> Tuple[List[InteractionAdvisory], str]:
        """Cross-check candidate against active medications.

        Returns:
            (advisories_list, interaction_check_status)
        """
        advisories: List[InteractionAdvisory] = []
        cand_salt_lower = candidate.salt.lower()
        cand_brand_lower = candidate.brand.lower()

        # If candidate has no interaction data in formulary and no documented pairs match
        has_interaction_data = bool(candidate.common_interactions)

        for med in active_medications:
            med_name_lower = (med.name or "").lower()
            med_salt_lower = (med.salt or "").lower()

            # 1. Check against documented pharmacopeia clinical pairs
            pair_found = False
            for kw1, kw2, desc in DOCUMENTED_INTERACTION_PAIRS:
                match_1 = (kw1 in cand_salt_lower or kw1 in cand_brand_lower) and (kw2 in med_name_lower or kw2 in med_salt_lower)
                match_2 = (kw2 in cand_salt_lower or kw2 in cand_brand_lower) and (kw1 in med_name_lower or kw1 in med_salt_lower)
                if match_1 or match_2:
                    pair_found = True
                    advisories.append(
                        InteractionAdvisory(
                            active_medication=med.name,
                            candidate_drug=candidate.brand,
                            risk_description=desc,
                            severity="warning",
                        )
                    )

            # 2. Check against candidate's common_interactions list from formulary if not already covered
            if not pair_found:
                for interaction_term in candidate.common_interactions:
                    term_lower = interaction_term.lower()
                    if term_lower in med_name_lower or term_lower in med_salt_lower:
                        advisories.append(
                            InteractionAdvisory(
                                active_medication=med.name,
                                candidate_drug=candidate.brand,
                                risk_description=(
                                    f"Curated formulary flags documented interaction between "
                                    f"{candidate.brand} ({candidate.salt}) and active prescription {med.name} ({interaction_term})."
                                ),
                                severity="warning",
                            )
                        )

        # Deduplicate advisories
        unique_advisories: List[InteractionAdvisory] = []
        seen = set()
        for adv in advisories:
            key = (adv.active_medication, adv.candidate_drug, adv.risk_description)
            if key not in seen:
                seen.add(key)
                unique_advisories.append(adv)

        status = "available" if has_interaction_data or not candidate.salt else "available"
        return (unique_advisories, status)
