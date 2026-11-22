"""
Data schemas for plate validation and status decisions.
"""
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


class ValidationStatus(str, Enum):
    ACCEPTED = "ACCEPTED"
    NEEDS_REVIEW = "NEEDS_REVIEW"
    REJECTED = "REJECTED"


class ReviewReason(str, Enum):
    NONE = "NONE"
    LOW_OCR_CONFIDENCE = "LOW_OCR_CONFIDENCE"
    MIN_CHAR_CONFIDENCE_FAILED = "MIN_CHAR_CONFIDENCE_FAILED"
    SYNTAX_GRAMMAR_MISMATCH = "SYNTAX_GRAMMAR_MISMATCH"
    INVALID_STATE_CODE = "INVALID_STATE_CODE"
    AMBIGUOUS_READ = "AMBIGUOUS_READ"


class PlateType(str, Enum):
    STANDARD_HSRP = "STANDARD_HSRP"
    BHARAT_SERIES = "BHARAT_SERIES"
    DIPLOMATIC = "DIPLOMATIC"
    TEMPORARY = "TEMPORARY"
    MILITARY = "MILITARY"
    UNKNOWN = "UNKNOWN"


class PlateValidationResult(BaseModel):
    raw_text: str
    normalized_plate: str
    is_valid: bool
    status: ValidationStatus
    plate_type: PlateType
    confidence: float = Field(ge=0.0, le=1.0)
    raw_ocr_confidence: float = Field(ge=0.0, le=1.0)
    state_code: Optional[str] = None
    rto_code: Optional[str] = None
    series: Optional[str] = None
    unique_number: Optional[str] = None
    review_reason: ReviewReason = ReviewReason.NONE
    substitutions_applied: int = 0
