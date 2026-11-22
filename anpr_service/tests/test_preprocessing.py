"""
Unit tests for ANPR preprocessing pipeline.
"""
import cv2
import numpy as np
import pytest

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


def test_apply_lab_clahe():
    """Verify CLAHE applies on L-channel preserving shape and channel count."""
    image = np.full((100, 300, 3), 128, dtype=np.uint8)
    enhanced = apply_lab_clahe(image, clip_limit=2.0)
    assert enhanced.shape == image.shape
    assert enhanced.dtype == np.uint8


def test_polarity_detection_white_plate():
    """Verify private white plate has standard polarity."""
    plate = np.full((80, 320, 3), 245, dtype=np.uint8)
    cv2.putText(plate, "DL 01 AB 1234", (20, 55), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (15, 15, 15), 2)

    is_inv, cat, luma = detect_plate_category_and_polarity(plate)
    assert is_inv is False
    assert cat == PlateCategory.PRIVATE_WHITE
    assert luma > 180


def test_polarity_detection_commercial_yellow_plate():
    """Verify commercial yellow plate has standard polarity."""
    # BGR for Yellow: B=25, G=200, R=245
    plate = np.full((80, 320, 3), (25, 200, 245), dtype=np.uint8)
    cv2.putText(plate, "HR 26 DQ 5555", (20, 55), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (15, 15, 15), 2)

    is_inv, cat, luma = detect_plate_category_and_polarity(plate)
    assert is_inv is False
    assert cat == PlateCategory.COMMERCIAL_YELLOW


def test_polarity_detection_ev_green_plate():
    """Verify EV green plate triggers inverted polarity and correctly inverts."""
    # BGR for dark emerald green: B=35, G=120, R=25
    plate = np.full((80, 320, 3), (35, 120, 25), dtype=np.uint8)
    cv2.putText(plate, "DL 01 EV 1234", (20, 55), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (245, 245, 245), 2)

    is_inv, cat, luma = detect_plate_category_and_polarity(plate)
    assert is_inv is True
    assert cat == PlateCategory.EV_GREEN

    inverted, was_inv = invert_polarity_if_needed(plate)
    assert was_inv is True
    # Inverted plate should now have light background
    inv_luma = float(np.median(inverted[:5, :5]))
    assert inv_luma > 150


def test_polarity_detection_rental_black_plate():
    """Verify rental black plate triggers inverted polarity."""
    plate = np.full((80, 320, 3), (25, 25, 25), dtype=np.uint8)
    cv2.putText(plate, "KA 05 Z 1234", (20, 55), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (25, 200, 245), 2)

    is_inv, cat, luma = detect_plate_category_and_polarity(plate)
    assert is_inv is True
    assert cat == PlateCategory.SELF_DRIVE_BLACK


def test_deskew_plate():
    """Verify deskewing detects tilt angle and rotates back to near-horizontal."""
    plate = np.full((80, 360, 3), 240, dtype=np.uint8)
    cv2.putText(plate, "DL 01 AB 1234", (20, 55), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (10, 10, 10), 2)

    # Intentionally rotate by -12 degrees
    m = cv2.getRotationMatrix2D((180, 40), -12.0, 1.0)
    tilted = cv2.warpAffine(plate, m, (360, 80), borderMode=cv2.BORDER_REPLICATE)

    rotated, angle = deskew_plate(tilted)
    # The magnitude of detected angle should match the applied tilt
    assert abs(abs(angle) - 12.0) < 3.5
    assert rotated.shape == tilted.shape


def test_dual_row_detection_and_stitching():
    """Verify two-row plate detection, splitting, and horizontal stitching."""
    # Dual-row plate: 160h x 240w -> aspect ratio = 160 / 240 = 0.67 >= 0.40
    dual_plate = np.full((160, 240, 3), 245, dtype=np.uint8)
    # Row 1: State + RTO
    cv2.putText(dual_plate, "DL 01", (40, 55), cv2.FONT_HERSHEY_SIMPLEX, 1.2, (15, 15, 15), 3)
    # Row 2: Series + Number
    cv2.putText(dual_plate, "AB 1234", (20, 130), cv2.FONT_HERSHEY_SIMPLEX, 1.2, (15, 15, 15), 3)

    is_dual, split_y = detect_dual_row(dual_plate)
    assert is_dual is True
    assert split_y is not None
    assert 55 < split_y < 120

    top_crop, bottom_crop = split_dual_row(dual_plate, split_y)
    assert top_crop.shape[0] == split_y
    assert bottom_crop.shape[0] == 160 - split_y

    stitched = stitch_dual_row_horizontal(top_crop, bottom_crop)
    # Stitched width should roughly equal top_w + bot_w + spacer
    assert stitched.shape[1] > dual_plate.shape[1]
    # Stitched aspect ratio (h/w) should now be typical single row (< 0.35)
    stitched_ar = stitched.shape[0] / float(stitched.shape[1])
    assert stitched_ar < 0.35


def test_preprocess_plate_full_pipeline():
    """Verify end-to-end preprocessing on synthetic plate."""
    plate = np.full((80, 320, 3), (35, 120, 25), dtype=np.uint8)  # EV green
    cv2.putText(plate, "DL 01 AB 1234", (20, 55), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (245, 245, 245), 2)

    result = preprocess_plate(plate, deskew=True, normalize_polarity=True, handle_dual_row=True)
    assert isinstance(result, PreprocessingResult)
    assert result.was_inverted is True
    assert result.plate_category == PlateCategory.EV_GREEN
    assert result.processed_image.shape == plate.shape


def test_stitch_dual_row_height_preservation_and_zero_division():
    """
    Regression test:
    1. Verify stitch_dual_row_horizontal pads shorter crop to target_h instead of vertically
       stretching it, maintaining identical character glyph heights.
    2. Verify zero-height or empty crop inputs return safely without ZeroDivisionError.
    """
    # Create top crop (height 60, width 300) and bottom crop (height 100, width 300)
    top = np.full((60, 300, 3), 200, dtype=np.uint8)
    bot = np.full((100, 300, 3), 200, dtype=np.uint8)

    stitched = stitch_dual_row_horizontal(top, bot, spacer_px=20)
    assert stitched.shape[0] == 100
    assert stitched.shape[1] == 300 + 20 + 300

    # Zero height crop resilience
    empty_top = np.zeros((0, 300, 3), dtype=np.uint8)
    res_empty = stitch_dual_row_horizontal(empty_top, bot)
    assert res_empty is not None

    # None resilience
    assert stitch_dual_row_horizontal(None, bot) is not None
