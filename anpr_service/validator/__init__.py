"""
Public exports for ANPR plate validator.
"""
from anpr_service.validator.constants import (
    VALID_STATE_CODES,
    GRAMMARS,
    CONFIDENCE_THRESHOLD,
    MIN_CHAR_CONFIDENCE_THRESHOLD,
    DISAMBIGUATION_PENALTY_PER_CHAR,
    DIGIT_TO_ALPHA_MAP,
    ALPHA_TO_DIGIT_MAP,
)
from anpr_service.validator.schemas import (
    ValidationStatus,
    ReviewReason,
    PlateType,
    PlateValidationResult,
)
from anpr_service.validator.disambiguation import (
    clean_ocr_text,
    map_char_to_alpha,
    map_char_to_digit,
    disambiguate_standard_hsrp,
    disambiguate_bharat_series,
)
from anpr_service.validator.indian_plate import IndianPlateValidator

__all__ = [
    "VALID_STATE_CODES",
    "GRAMMARS",
    "CONFIDENCE_THRESHOLD",
    "MIN_CHAR_CONFIDENCE_THRESHOLD",
    "DISAMBIGUATION_PENALTY_PER_CHAR",
    "DIGIT_TO_ALPHA_MAP",
    "ALPHA_TO_DIGIT_MAP",
    "ValidationStatus",
    "ReviewReason",
    "PlateType",
    "PlateValidationResult",
    "clean_ocr_text",
    "map_char_to_alpha",
    "map_char_to_digit",
    "disambiguate_standard_hsrp",
    "disambiguate_bharat_series",
    "IndianPlateValidator",
]
