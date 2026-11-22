"""
End-to-End Pipeline Integration Tests.
Verifies complete flow: Synthetic Plate -> Detection -> Preprocessing -> OCR Engine -> Validation -> Gating.
"""
import cv2
import numpy as np
import pytest

from anpr_service.detector import YOLOPlateDetector, MorphologicalPlateDetector, crop_plate
from anpr_service.ocr import OcrEngine, preprocess_plate, PlateCategory
from anpr_service.validator import (
    IndianPlateValidator,
    ValidationStatus,
    ReviewReason,
    PlateType,
)
from anpr_service.synthetic import (
    SyntheticPlateGenerator,
    PlateColorTheme,
    PlateLayout,
    DistortionConfig,
    DistortionType,
)


def test_end_to_end_single_row_hsrp_pipeline():
    """
    End-to-end test on clean standard HSRP plate:
    1. Generate synthetic plate 'DL01AB1234'
    2. Place plate on simulated vehicle bumper frame
    3. Detect plate region using detector with 10% padding
    4. Preprocess crop (LAB CLAHE, deskew, polarity)
    5. OCR extract characters and confidences
    6. Validate with IndianPlateValidator and verify ACCEPTED status
    """
    generator = SyntheticPlateGenerator()
    synth_res = generator.generate("DL01AB1234", theme=PlateColorTheme.PRIVATE_WHITE)
    plate_img = synth_res.image  # 105x440

    # Place plate on vehicle background (500x800)
    frame = np.full((500, 800, 3), 45, dtype=np.uint8)
    # Plate coordinates: y=200..305, x=180..620
    frame[200:305, 180:620] = plate_img

    # 1. Detection
    detector = YOLOPlateDetector(model_path="nonexistent.pt", enable_fallback=True)
    detections = detector.detect(frame)
    assert len(detections) >= 1
    best_det = detections[0]
    assert best_det.cropped_plate is not None

    # 2. Preprocessing
    pre_result = preprocess_plate(best_det.cropped_plate)
    assert pre_result.processed_image is not None
    assert pre_result.plate_category == PlateCategory.PRIVATE_WHITE

    # 3. OCR Engine
    ocr_engine = OcrEngine()
    ocr_result = ocr_engine.extract(pre_result.processed_image, preprocess=False)
    assert ocr_result.backend_used is not None

    # 4. Indian Plate Validation
    validator = IndianPlateValidator()
    assert ocr_result.raw_text == "DL01AB1234"
    val_res = validator.validate(ocr_result.raw_text, ocr_result.char_confidences)
    assert val_res.status == ValidationStatus.ACCEPTED
    assert val_res.is_valid is True
    assert val_res.normalized_plate == "DL01AB1234"
    assert val_res.plate_type == PlateType.STANDARD_HSRP
    assert val_res.confidence >= 0.75


def test_end_to_end_ev_green_plate_polarity_inversion():
    """
    End-to-end test on EV green plate:
    Verifies polarity detection correctly identifies EV_GREEN and inverts text for OCR.
    """
    generator = SyntheticPlateGenerator()
    synth_res = generator.generate("DL01EV1234", theme=PlateColorTheme.EV_GREEN)
    plate_img = synth_res.image

    pre_result = preprocess_plate(plate_img, normalize_polarity=True)
    assert pre_result.was_inverted is True
    assert pre_result.plate_category == PlateCategory.EV_GREEN

    ocr_engine = OcrEngine()
    ocr_result = ocr_engine.extract(pre_result.processed_image, preprocess=False)
    assert ocr_result.raw_text == "DL01EV1234"

    validator = IndianPlateValidator()
    val_res = validator.validate(ocr_result.raw_text, ocr_result.char_confidences)
    assert val_res.status == ValidationStatus.ACCEPTED
    assert val_res.state_code == "DL"
    assert val_res.normalized_plate == "DL01EV1234"


def test_end_to_end_dual_row_hsrp_pipeline():
    """
    End-to-end test on dual-row plate:
    Verifies dual-row detection, height-preserving horizontal stitching,
    genuine OCR character extraction of both rows, and statutory plate validation.
    """
    generator = SyntheticPlateGenerator()
    synth_res = generator.generate("DL01AB1234", layout=PlateLayout.DUAL_ROW)

    pre_result = preprocess_plate(synth_res.image, handle_dual_row=True)
    assert pre_result.is_dual_row is True

    ocr_engine = OcrEngine()
    ocr_result = ocr_engine.extract(pre_result.processed_image, preprocess=False)
    assert ocr_result.raw_text == "DL01AB1234"

    validator = IndianPlateValidator()
    val_res = validator.validate(ocr_result.raw_text, ocr_result.char_confidences)
    assert val_res.status == ValidationStatus.ACCEPTED
    assert val_res.normalized_plate == "DL01AB1234"


def test_end_to_end_low_confidence_gating_invariant():
    """
    Verify core invariant: when detection/OCR confidence drops below 0.75,
    status MUST be NEEDS_REVIEW to prevent unverified vehicle sessions.
    """
    validator = IndianPlateValidator()
    # Simulating low OCR confidence read (e.g. blurry frame at night)
    low_conf_read = "DL01AB1234"
    low_confs = [0.52] * len(low_conf_read)

    val_res = validator.validate(low_conf_read, low_confs)
    assert val_res.status == ValidationStatus.NEEDS_REVIEW
    assert val_res.is_valid is False
    assert val_res.review_reason == ReviewReason.LOW_OCR_CONFIDENCE
    assert val_res.confidence < 0.75
