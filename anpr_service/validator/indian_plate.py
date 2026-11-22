"""
Indian License Plate Validator with strict gating and invariant protection.
"""
from typing import List, Optional
from anpr_service.validator.constants import (
    GRAMMARS,
    VALID_STATE_CODES,
    CONFIDENCE_THRESHOLD,
    MIN_CHAR_CONFIDENCE_THRESHOLD,
    DISAMBIGUATION_PENALTY_PER_CHAR,
)
from anpr_service.validator.schemas import (
    PlateValidationResult,
    ValidationStatus,
    ReviewReason,
    PlateType,
)
from anpr_service.validator.disambiguation import (
    clean_ocr_text,
    disambiguate_standard_hsrp,
    disambiguate_bharat_series,
)


class IndianPlateValidator:
    """
    Validates Indian license plates against statutory grammars and DIN 1451 confusions.
    Enforces the core invariant: any read with confidence < 0.75 or failing syntax grammar
    MUST be tagged status='NEEDS_REVIEW' and must never alter active vehicle sessions.
    """

    def validate(
        self,
        raw_text: Optional[str],
        char_confidences: Optional[List[float]] = None
    ) -> PlateValidationResult:
        if raw_text is None or not isinstance(raw_text, str) or not raw_text.strip():
            return PlateValidationResult(
                raw_text="" if raw_text is None else str(raw_text),
                normalized_plate="",
                is_valid=False,
                status=ValidationStatus.NEEDS_REVIEW,
                plate_type=PlateType.UNKNOWN,
                confidence=0.0,
                raw_ocr_confidence=0.0,
                state_code=None,
                rto_code=None,
                series=None,
                unique_number=None,
                review_reason=ReviewReason.SYNTAX_GRAMMAR_MISMATCH,
                substitutions_applied=0,
            )

        cleaned = clean_ocr_text(raw_text)

        # Calculate raw OCR metrics and clamp to [0.0, 1.0]
        if char_confidences and len(char_confidences) > 0:
            avg_ocr_conf = float(sum(char_confidences) / len(char_confidences))
            min_ocr_conf = float(min(char_confidences))
        else:
            avg_ocr_conf = 0.90
            min_ocr_conf = 0.85

        avg_ocr_conf = max(0.0, min(1.0, avg_ocr_conf))
        min_ocr_conf = max(0.0, min(1.0, min_ocr_conf))

        rto_code = None
        series = None
        unique_number = None

        # Check Bharat Series first
        bh_result = disambiguate_bharat_series(cleaned)
        if bh_result:
            normalized_plate, subs = bh_result
            plate_type = PlateType.BHARAT_SERIES
            state_code = "BH"
            rto_code = normalized_plate[:2]  # Year of registration
            unique_number = normalized_plate[4:8]
            series = normalized_plate[8:]
        else:
            # Check Standard HSRP
            hsrp_result = disambiguate_standard_hsrp(cleaned)
            if hsrp_result:
                normalized_plate, subs = hsrp_result
                plate_type = PlateType.STANDARD_HSRP
                state_code = normalized_plate[:2]
                unique_number = normalized_plate[-4:]
                middle = normalized_plate[2:-4]
                # Parse middle into RTO digits and Series letters
                rto_digits = "".join([c for c in middle if c.isdigit()])
                series_letters = "".join([c for c in middle if c.isalpha()])
                rto_code = rto_digits if rto_digits else None
                series = series_letters if series_letters else None
            else:
                normalized_plate = cleaned
                plate_type = PlateType.UNKNOWN
                subs = 0
                state_code = cleaned[:2] if len(cleaned) >= 2 else None

        # Verify against statutory regex grammars
        is_grammar_valid = False
        if plate_type == PlateType.BHARAT_SERIES:
            is_grammar_valid = bool(GRAMMARS["BHARAT_SERIES"].match(normalized_plate))
        elif plate_type == PlateType.STANDARD_HSRP:
            is_grammar_valid = bool(GRAMMARS["HSRP_STANDARD"].match(normalized_plate))

        # Check diplomatic or temporary if still unverified
        if not is_grammar_valid:
            if GRAMMARS["DIPLOMATIC"].match(normalized_plate):
                is_grammar_valid = True
                plate_type = PlateType.DIPLOMATIC
            elif GRAMMARS["TEMPORARY"].match(normalized_plate):
                is_grammar_valid = True
                plate_type = PlateType.TEMPORARY
            elif GRAMMARS["MILITARY"].match(normalized_plate):
                is_grammar_valid = True
                plate_type = PlateType.MILITARY

        # State validity check
        is_state_valid = (
            (state_code in VALID_STATE_CODES)
            or (plate_type == PlateType.BHARAT_SERIES)
            or (plate_type == PlateType.DIPLOMATIC)
            or (plate_type == PlateType.MILITARY)
        )

        # Compound Confidence calculation
        s_grammar = 1.0 if (is_grammar_valid and is_state_valid) else 0.0
        calculated_conf = (
            0.60 * avg_ocr_conf
            + 0.20 * min_ocr_conf
            + 0.20 * s_grammar
            - (subs * DISAMBIGUATION_PENALTY_PER_CHAR)
        )
        calculated_conf = max(0.0, min(1.0, calculated_conf))

        if not (is_grammar_valid and is_state_valid):
            calculated_conf = min(calculated_conf, 0.50)

        # Gating Decision
        status = ValidationStatus.ACCEPTED
        review_reason = ReviewReason.NONE

        if not is_state_valid and plate_type != PlateType.DIPLOMATIC:
            status = ValidationStatus.NEEDS_REVIEW
            review_reason = ReviewReason.INVALID_STATE_CODE
        elif not is_grammar_valid:
            status = ValidationStatus.NEEDS_REVIEW
            review_reason = ReviewReason.SYNTAX_GRAMMAR_MISMATCH
        elif min_ocr_conf < MIN_CHAR_CONFIDENCE_THRESHOLD:
            status = ValidationStatus.NEEDS_REVIEW
            review_reason = ReviewReason.MIN_CHAR_CONFIDENCE_FAILED
        elif avg_ocr_conf < CONFIDENCE_THRESHOLD:
            status = ValidationStatus.NEEDS_REVIEW
            review_reason = ReviewReason.LOW_OCR_CONFIDENCE
        elif calculated_conf < CONFIDENCE_THRESHOLD:
            status = ValidationStatus.NEEDS_REVIEW
            review_reason = ReviewReason.LOW_OCR_CONFIDENCE

        return PlateValidationResult(
            raw_text=raw_text,
            normalized_plate=normalized_plate,
            is_valid=(status == ValidationStatus.ACCEPTED),
            status=status,
            plate_type=plate_type,
            confidence=round(calculated_conf, 4),
            raw_ocr_confidence=round(avg_ocr_conf, 4),
            state_code=state_code,
            rto_code=rto_code,
            series=series,
            unique_number=unique_number,
            review_reason=review_reason,
            substitutions_applied=subs,
        )
