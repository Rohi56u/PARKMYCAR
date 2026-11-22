"""
Unit tests for license plate detector modules.
"""
import cv2
import numpy as np
import pytest

from anpr_service.detector import (
    BasePlateDetector,
    DetectionResult,
    MorphologicalPlateDetector,
    YOLOPlateDetector,
    apply_padding,
    crop_plate,
    create_detector,
)


def test_apply_padding_expansion():
    """Verify 10% bounding box expansion on standard coordinates."""
    image_shape = (480, 640, 3)
    # Box width = 100, height = 50
    box = (100, 100, 200, 150)
    padded = apply_padding(box, image_shape, padding_ratio=0.10)

    # pad_w = 10 (10% of 100), pad_h = 5 (10% of 50)
    assert padded == (90, 95, 210, 155)


def test_apply_padding_boundary_clamping():
    """Verify coordinate clamping at image boundaries [0, 0, w, h]."""
    image_shape = (400, 600, 3)
    # Box near top-left origin
    box_origin = (5, 5, 50, 40)
    padded_origin = apply_padding(box_origin, image_shape, padding_ratio=0.20)
    assert padded_origin[0] == 0  # Clamped to 0
    assert padded_origin[1] == 0  # Clamped to 0

    # Box near bottom-right boundary
    box_far = (550, 370, 595, 395)
    padded_far = apply_padding(box_far, image_shape, padding_ratio=0.20)
    assert padded_far[2] == 600  # Clamped to width
    assert padded_far[3] == 400  # Clamped to height


def test_crop_plate():
    """Verify crop_plate returns cropped image matching padded coordinates."""
    image = np.zeros((300, 400, 3), dtype=np.uint8)
    image[50:150, 50:250] = 200  # draw rectangular patch

    box = (60, 60, 240, 140)  # bw=180, bh=80 -> pad_w=18, pad_h=8
    crop, padded_box = crop_plate(image, box, padding_ratio=0.10)

    expected_box = (42, 52, 258, 148)
    assert padded_box == expected_box
    assert crop.shape == (expected_box[3] - expected_box[1], expected_box[2] - expected_box[0], 3)


def test_morphological_detection_on_synthetic_frame():
    """Verify MorphologicalPlateDetector detects rectangular license plate."""
    # Create background frame simulating a vehicle bumper
    frame = np.full((600, 800, 3), 40, dtype=np.uint8)

    # License plate at (250, 350) to (550, 430) -> width=300, height=80, aspect_ratio=3.75
    px1, py1, px2, py2 = 250, 350, 550, 430
    frame[py1:py2, px1:px2] = 240  # white plate

    # Render simulated registration characters to create horizontal gradient edges
    cv2.putText(
        frame,
        "DL 01 AB 1234",
        (px1 + 25, py1 + 55),
        cv2.FONT_HERSHEY_SIMPLEX,
        1.0,
        (10, 10, 10),
        3,
    )

    detector = MorphologicalPlateDetector(
        min_aspect_ratio=1.8,
        max_aspect_ratio=5.8,
        min_area=1200,
        padding_ratio=0.10,
    )
    detections = detector.detect(frame)

    assert len(detections) >= 1
    best = detections[0]
    assert best.confidence >= 0.50
    assert best.source == "cv_fallback"
    assert best.cropped_plate is not None
    assert best.padded_box is not None

    # Verify detected coordinates overlap significantly with ground truth
    dx1, dy1, dx2, dy2 = best.box
    assert abs(dx1 - px1) < 25
    assert abs(dy1 - py1) < 25
    assert abs(dx2 - px2) < 25
    assert abs(dy2 - py2) < 25


def test_yolo_graceful_fallback():
    """Verify YOLOPlateDetector safely falls back to MorphologicalPlateDetector when weights are missing."""
    detector = YOLOPlateDetector(
        model_path="nonexistent_weights_12345.pt",
        confidence_threshold=0.50,
        enable_fallback=True,
    )
    assert detector.is_loaded is False
    assert detector.model is None

    # Build synthetic frame
    frame = np.full((500, 700, 3), 30, dtype=np.uint8)
    frame[200:270, 200:480] = 245
    cv2.putText(frame, "MH 12 DE 1433", (210, 250), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 0, 0), 2)

    detections = detector.detect(frame)
    assert len(detections) >= 1
    assert detections[0].source == "cv_fallback"


def test_create_detector_factory():
    """Verify create_detector factory helper."""
    detector = create_detector(model_path=None, confidence_threshold=0.60)
    assert isinstance(detector, BasePlateDetector)
    assert detector.is_loaded is False


def test_apply_padding_negative_and_oob_clamping_regression():
    """
    Regression test for bounding box padding:
    Verifies that negative coordinates, inverted coordinates, and out-of-bounds boxes
    are strictly clamped to [0, w] and [0, h] without causing backward slice indexing.
    """
    shape = (100, 100, 3)

    # 1. Entirely negative box
    padded_neg = apply_padding((-50, -50, -10, -10), shape, padding_ratio=0.10)
    assert padded_neg == (0, 0, 0, 0)
    assert all(0 <= c <= 100 for c in padded_neg)

    # Slicing test
    img = np.zeros(shape, dtype=np.uint8)
    crop, box = crop_plate(img, (-50, -50, -10, -10))
    assert crop.shape == (0, 0, 3)

    # 2. Inverted coordinates (x_min > x_max)
    padded_inv = apply_padding((80, 70, 30, 20), shape, padding_ratio=0.10)
    assert padded_inv[0] <= padded_inv[2]
    assert padded_inv[1] <= padded_inv[3]
    assert all(0 <= c <= 100 for c in padded_inv)

    # 3. Way beyond bounds
    padded_oob = apply_padding((150, 150, 200, 200), shape, padding_ratio=0.10)
    assert padded_oob == (100, 100, 100, 100)
    crop_oob, _ = crop_plate(img, (150, 150, 200, 200))
    assert crop_oob.shape == (0, 0, 3)
