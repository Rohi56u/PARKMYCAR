"""
Unit tests for Indian license plate validator, regex grammars, DIN 1451 disambiguation,
and confidence gating.
"""
import pytest

from anpr_service.validator import (
    VALID_STATE_CODES,
    GRAMMARS,
    ValidationStatus,
    ReviewReason,
    PlateType,
    PlateValidationResult,
    clean_ocr_text,
    IndianPlateValidator,
)


def test_all_41_state_and_ut_codes_present():
    """Verify all 36 active States/UTs + 5 historical/alternative aliases are present."""
    assert len(VALID_STATE_CODES) == 41

    # Check key states & UTs
    core_codes = [
        "AN", "AP", "AR", "AS", "BR", "CH", "CG", "CT", "DD", "DN",
        "DL", "GA", "GJ", "HR", "HP", "JH", "JK", "KA", "KL", "LA",
        "LD", "MP", "MH", "MN", "ML", "MZ", "NL", "OD", "OR", "PB",
        "PY", "RJ", "SK", "TN", "TS", "TG", "TR", "UP", "UK", "UA",
        "WB"
    ]
    for code in core_codes:
        assert code in VALID_STATE_CODES, f"Code {code} missing from VALID_STATE_CODES"


def test_standard_hsrp_valid_formats():
    """Verify standard HSRP formats across states and series lengths."""
    validator = IndianPlateValidator()

    test_cases = [
        ("DL01AB1234", "DL", "01", "AB", "1234"),
        ("MH12DE1433", "MH", "12", "DE", "1433"),
        ("HR26DQ5555", "HR", "26", "DQ", "5555"),
        ("KA05M5678", "KA", "05", "M", "5678"),
        ("DL1C1234", "DL", "1", "C", "1234"),
        ("TN09ABC1234", "TN", "09", "ABC", "1234"),
        ("UP321234", "UP", "32", None, "1234"),
        ("TS08EA1234", "TS", "08", "EA", "1234"),
        ("TG09FA5678", "TG", "09", "FA", "5678"),  # New Telangana code
        ("OR02B1234", "OR", "02", "B", "1234"),    # Legacy Odisha code
    ]

    for plate, state, rto, ser, num in test_cases:
        res = validator.validate(plate, [0.95] * len(plate))
        assert res.status == ValidationStatus.ACCEPTED, f"Failed for {plate}"
        assert res.is_valid is True
        assert res.plate_type == PlateType.STANDARD_HSRP
        assert res.normalized_plate == plate
        assert res.state_code == state
        assert res.unique_number == num
        if rto:
            assert res.rto_code == rto
        if ser:
            assert res.series == ser


def test_bharat_series_validation():
    """Verify Bharat Series (BH) plates."""
    validator = IndianPlateValidator()

    bh_cases = [
        ("22BH1234AA", "22", "1234", "AA"),
        ("21BH5678B", "21", "5678", "B"),
        ("24BH9999ZZ", "24", "9999", "ZZ"),
    ]

    for plate, year, num, ser in bh_cases:
        res = validator.validate(plate, [0.92] * len(plate))
        assert res.status == ValidationStatus.ACCEPTED
        assert res.is_valid is True
        assert res.plate_type == PlateType.BHARAT_SERIES
        assert res.state_code == "BH"
        assert res.rto_code == year
        assert res.unique_number == num
        assert res.series == ser


def test_diplomatic_and_temporary_validation():
    """Verify diplomatic and temporary registration validation."""
    validator = IndianPlateValidator()

    # Diplomatic
    res_cd = validator.validate("77CD12", [0.95] * 6)
    assert res_cd.status == ValidationStatus.ACCEPTED
    assert res_cd.plate_type == PlateType.DIPLOMATIC

    # Temporary
    res_temp = validator.validate("MH02TEMP1234", [0.95] * 12)
    assert res_temp.status == ValidationStatus.ACCEPTED
    assert res_temp.plate_type == PlateType.TEMPORARY


def test_din_1451_character_disambiguation():
    """Verify slot-dependent confusion disambiguation."""
    validator = IndianPlateValidator()

    # O to 0 in number, 8 to B in series, I to 1 in number
    res1 = validator.validate("DLO1A8I234", [0.90] * 10)
    assert res1.normalized_plate == "DL01AB1234"
    assert res1.status == ValidationStatus.ACCEPTED
    assert res1.substitutions_applied == 3

    # Z to 2 in RTO digits
    res2 = validator.validate("MH1ZDE1433", [0.92] * 10)
    assert res2.normalized_plate == "MH12DE1433"
    assert res2.status == ValidationStatus.ACCEPTED
    assert res2.substitutions_applied == 1

    # 0 to D in State code prefix
    res3 = validator.validate("0LO1AB1234", [0.90] * 10)
    assert res3.normalized_plate == "DL01AB1234"
    assert res3.status == ValidationStatus.ACCEPTED

    # O to 0 in RTO digits
    res4 = validator.validate("KAO5M5678", [0.91] * 9)
    assert res4.normalized_plate == "KA05M5678"
    assert res4.status == ValidationStatus.ACCEPTED

    # Z to 2 and S to 5 in number
    res5 = validator.validate("HRZ6DQSSSS", [0.95] * 10)
    assert res5.normalized_plate == "HR26DQ5555"
    assert res5.status == ValidationStatus.ACCEPTED

    # Bharat Series disambiguation: Z28HI2348A -> 22BH1234BA
    res6 = validator.validate("Z28HI2348A", [0.90] * 10)
    assert res6.normalized_plate == "22BH1234BA"
    assert res6.status == ValidationStatus.ACCEPTED
    assert res6.plate_type == PlateType.BHARAT_SERIES


def test_clean_ocr_text_strips_ind_badge():
    """Verify HSRP IND badge artifacts are stripped."""
    assert clean_ocr_text("IND DL-01 AB 1234") == "DL01AB1234"
    assert clean_ocr_text("1ND MH 12 DE 1433") == "MH12DE1433"
    assert clean_ocr_text("IND22BH1234AA") == "22BH1234AA"


def test_strict_gating_invalid_state_triggers_needs_review():
    """Verify invalid state code triggers NEEDS_REVIEW with INVALID_STATE_CODE."""
    validator = IndianPlateValidator()
    res = validator.validate("XX01AB1234", [0.98] * 10)
    assert res.status == ValidationStatus.NEEDS_REVIEW
    assert res.is_valid is False
    assert res.review_reason == ReviewReason.INVALID_STATE_CODE
    assert res.confidence <= 0.50


def test_strict_gating_syntax_mismatch_triggers_needs_review():
    """Verify malformed plate syntax triggers NEEDS_REVIEW with SYNTAX_GRAMMAR_MISMATCH."""
    validator = IndianPlateValidator()
    # 6 digits at the end exceeds maximum allowed
    res = validator.validate("DL01AB123456", [0.95] * 12)
    assert res.status == ValidationStatus.NEEDS_REVIEW
    assert res.is_valid is False
    assert res.review_reason == ReviewReason.SYNTAX_GRAMMAR_MISMATCH


def test_strict_gating_low_confidence_triggers_needs_review():
    """Verify low average OCR confidence (<0.75) triggers NEEDS_REVIEW."""
    validator = IndianPlateValidator()
    # High quality syntax but blurry camera capture
    res = validator.validate("DL01AB1234", [0.55] * 10)
    assert res.status == ValidationStatus.NEEDS_REVIEW
    assert res.is_valid is False
    assert res.review_reason == ReviewReason.LOW_OCR_CONFIDENCE
    assert res.confidence < 0.75


def test_strict_gating_min_char_confidence_failure():
    """Verify single very low confidence character triggers NEEDS_REVIEW."""
    validator = IndianPlateValidator()
    # One character has confidence 0.20 (below MIN_CHAR_CONFIDENCE_THRESHOLD 0.40)
    confs = [0.95, 0.95, 0.95, 0.95, 0.20, 0.95, 0.95, 0.95, 0.95, 0.95]
    res = validator.validate("DL01AB1234", confs)
    assert res.status == ValidationStatus.NEEDS_REVIEW
    assert res.is_valid is False
    assert res.review_reason == ReviewReason.MIN_CHAR_CONFIDENCE_FAILED


def test_military_plate_validation():
    """Verify Indian armed forces / military registration pattern."""
    validator = IndianPlateValidator()
    res = validator.validate("21D123456A", [0.95] * 10)
    assert res.status == ValidationStatus.ACCEPTED
    assert res.plate_type == PlateType.MILITARY


def test_lowercase_and_spaced_input():
    """Verify lowercase and irregularly spaced strings are normalized properly."""
    validator = IndianPlateValidator()
    res = validator.validate("  dl - 01 . ab / 1234  ", [0.95] * 10)
    assert res.status == ValidationStatus.ACCEPTED
    assert res.normalized_plate == "DL01AB1234"
    assert res.state_code == "DL"


def test_validator_remediations_regression():
    """
    Regression suite covering all Challenger & Reviewer wave findings:
    1. Direct OCR confidence gating: avg conf 0.749 must be NEEDS_REVIEW vs 0.751 ACCEPTED.
    2. Broken Bharat Series: 22BH12345 must be NEEDS_REVIEW.
    3. Invalid RTO 00 and vehicle number 0000: 0000000000 & DDDDDDDDDD must be NEEDS_REVIEW.
    4. 1-digit RTO: DL1AB1234 must remain DL1AB1234 and not mutate to DL14B1234.
    5. Crash resilience on None and confidence > 1.0.
    """
    validator = IndianPlateValidator()

    # 1. Direct OCR confidence gating
    r_749 = validator.validate("DL01AB1234", [0.749] * 10)
    assert r_749.status == ValidationStatus.NEEDS_REVIEW
    assert r_749.is_valid is False
    assert r_749.review_reason == ReviewReason.LOW_OCR_CONFIDENCE

    r_751 = validator.validate("DL01AB1234", [0.751] * 10)
    assert r_751.status == ValidationStatus.ACCEPTED
    assert r_751.is_valid is True

    # 2. Broken Bharat Series
    r_bh5 = validator.validate("22BH12345", [0.95] * 9)
    assert r_bh5.status == ValidationStatus.NEEDS_REVIEW
    assert r_bh5.is_valid is False

    # 3. All zeros & all Ds
    r_zeros = validator.validate("0000000000", [0.99] * 10)
    assert r_zeros.status == ValidationStatus.NEEDS_REVIEW
    assert r_zeros.is_valid is False

    r_ds = validator.validate("DDDDDDDDDD", [0.99] * 10)
    assert r_ds.status == ValidationStatus.NEEDS_REVIEW
    assert r_ds.is_valid is False

    # 4. 1-digit RTO disambiguation
    r_1rto = validator.validate("DL1AB1234", [0.95] * 9)
    assert r_1rto.status == ValidationStatus.ACCEPTED
    assert r_1rto.normalized_plate == "DL1AB1234"

    # 5. None resilience
    r_none = validator.validate(None)
    assert r_none.status == ValidationStatus.NEEDS_REVIEW
    assert r_none.is_valid is False

    # 6. Confidence > 1.0 clamping resilience
    r_high_conf = validator.validate("DL01AB1234", [1.05] * 10)
    assert r_high_conf.status == ValidationStatus.ACCEPTED
    assert r_high_conf.confidence <= 1.0
    assert r_high_conf.raw_ocr_confidence <= 1.0
