"""M4 — Medicine Substitution Module.

Provides intelligent pharmacy stockout decision support:
- Salt-level bioequivalence matching from curated formulary (data/drugs.csv)
- Strict Narrow Therapeutic Index (NTI) Hard-Block (data/nti.csv)
- Transparent flagging of formulation strength and dosage form divergences
- Cross-checking against canonical patient active medications for adverse interactions
- Unbroken provenance tracking and confidence gating
"""

from .schemas import (
    CandidateAlternative,
    DetectedMedicine,
    InteractionAdvisory,
    SubstitutionAnalysisResult,
    SubstitutionResultState,
)
from .drug_index import (
    DrugEntry,
    DrugIndexRepository,
    get_default_drug_index,
    parse_numeric_strength,
)
from .nti import (
    NTIEntry,
    NTIRepository,
    get_default_nti_repo,
)
from .interactions import (
    InteractionChecker,
)
from .extraction_adapter import (
    MedicineExtractionAdapterInterface,
    MockMedicineExtractionAdapter,
)
from .service import SubstitutionService

__all__ = [
    "CandidateAlternative",
    "DetectedMedicine",
    "DrugEntry",
    "DrugIndexRepository",
    "InteractionAdvisory",
    "InteractionChecker",
    "MedicineExtractionAdapterInterface",
    "MockMedicineExtractionAdapter",
    "NTIEntry",
    "NTIRepository",
    "SubstitutionAnalysisResult",
    "SubstitutionResultState",
    "SubstitutionService",
    "get_default_drug_index",
    "get_default_nti_repo",
    "parse_numeric_strength",
]
