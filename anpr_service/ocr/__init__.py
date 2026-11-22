"""
OCR Subpackage for License Plate Recognition.
"""
from anpr_service.ocr.preprocessing import (
    PlateCategory,
    PreprocessingResult,
    apply_lab_clahe,
    detect_plate_category_and_polarity,
    invert_polarity_if_needed,
    estimate_skew_angle,
    deskew_plate,
    detect_dual_row,
    split_dual_row,
    stitch_dual_row_horizontal,
    preprocess_plate,
)
from anpr_service.ocr.engine import (
    OcrResult,
    OcrBackend,
    CvTemplateMatchingBackend,
    RapidOCRBackend,
    EasyOCRBackend,
    PyTesseractBackend,
    OnnxCrnnBackend,
    OcrEngine,
)

__all__ = [
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
]
