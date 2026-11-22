"""
Unit tests for modular OCR Engine and CvTemplateMatchingBackend.
"""
import cv2
import numpy as np
import pytest

from anpr_service.ocr.engine import (
    CvTemplateMatchingBackend,
    OcrEngine,
    OcrResult,
)


def test_cv_template_backend_availability_and_templates():
    """Verify pure-OpenCV template backend is always available and builds all templates."""
    backend = CvTemplateMatchingBackend()
    assert backend.is_available() is True
    # Templates for digits '0'-'9' and letters 'A'-'Z' (total 36 characters)
    assert len(backend.templates) == 36
    for char, tmpls in backend.templates.items():
        assert len(tmpls) >= 1
        # Canonical size is (width, height) = (20, 32), numpy array shape is (height, width) = (32, 20)
        assert tmpls[0].shape == (backend.canonical_size[1], backend.canonical_size[0])


def test_cv_template_backend_character_recognition():
    """Verify template matcher correctly identifies glyphs and confidences."""
    backend = CvTemplateMatchingBackend()

    # Create plate canvas with white background and clearly spaced characters
    plate = np.full((70, 420), 255, dtype=np.uint8)
    # Render with Hershey Simplex font matching template font
    cv2.putText(
        plate,
        "DL 01 AB 1234",
        (25, 50),
        cv2.FONT_HERSHEY_SIMPLEX,
        1.0,
        0,  # dark text
        2,
    )

    result = backend.recognize(plate)
    assert isinstance(result, OcrResult)
    assert result.backend_used == "cv_template"
    assert len(result.char_confidences) == len(result.raw_text)
    assert result.overall_confidence > 0.0

    # Ensure recognized characters are alphanumeric
    assert result.raw_text.isalnum()
    # Should recognize standard characters
    assert "DL" in result.raw_text or "1234" in result.raw_text


def test_ocr_engine_coordinator():
    """Verify OcrEngine coordinates preprocessing, fallback cascade, and metadata."""
    engine = OcrEngine()
    # In offline environment without heavy ML packages, active backend falls back to cv_template
    active_backend = engine.get_active_backend()
    assert active_backend.name == "cv_template"

    plate = np.full((80, 360, 3), 245, dtype=np.uint8)
    cv2.putText(plate, "KA 05 M 5678", (20, 55), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (10, 10, 10), 2)

    ocr_result = engine.extract(plate, preprocess=True)
    assert isinstance(ocr_result, OcrResult)
    assert "preprocessing" in ocr_result.metadata
    assert ocr_result.metadata["preprocessing"]["plate_category"] == "PRIVATE_WHITE"
    assert ocr_result.execution_time_ms > 0


def test_empty_image_handling():
    """Verify empty/None image returns empty OcrResult without crashing."""
    engine = OcrEngine()
    empty = np.zeros((0, 0, 3), dtype=np.uint8)
    result = engine.extract(empty)
    assert result.raw_text == ""
    assert result.overall_confidence == 0.0
    assert result.char_confidences == []


def test_bordered_plate_contour_hierarchy_segmentation():
    """
    Regression test:
    Verify that an outer bounding border on the plate does not hide internal character
    contours, ensuring genuine segmentation and character recognition.
    """
    from anpr_service.synthetic import SyntheticPlateGenerator
    gen = SyntheticPlateGenerator()
    plate = gen.generate("DL01AB1234")

    engine = OcrEngine()
    ocr = engine.extract(plate.image, preprocess=True)
    assert ocr.raw_text == "DL01AB1234"
    assert len(ocr.char_confidences) == 10
    assert ocr.overall_confidence >= 0.75
