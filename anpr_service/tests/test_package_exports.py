"""
Test public package exports of anpr_service.
"""
import anpr_service


def test_public_package_exports():
    """Verify all required top-level components are exported from anpr_service."""
    expected_exports = [
        # Config
        "ANPRSettings",
        "settings",
        # Detector
        "BasePlateDetector",
        "DetectionResult",
        "MorphologicalPlateDetector",
        "YOLOPlateDetector",
        "apply_padding",
        "crop_plate",
        "create_detector",
        # OCR
        "PlateCategory",
        "PreprocessingResult",
        "apply_lab_clahe",
        "detect_plate_category_and_polarity",
        "invert_polarity_if_needed",
        "estimate_skew_angle",
        "deskew_plate",
        "detect_dual_row",
        "split_dual_row",
        "stitch_dual_row_horizontal",
        "preprocess_plate",
        "OcrResult",
        "OcrBackend",
        "CvTemplateMatchingBackend",
        "RapidOCRBackend",
        "EasyOCRBackend",
        "PyTesseractBackend",
        "OnnxCrnnBackend",
        "OcrEngine",
        # Validator
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
        # Synthetic
        "PlateColorTheme",
        "PlateLayout",
        "DistortionType",
        "DistortionConfig",
        "SyntheticPlateResult",
        "SyntheticPlateGenerator",
    ]

    for item in expected_exports:
        assert hasattr(anpr_service, item), f"Missing public export: {item}"
