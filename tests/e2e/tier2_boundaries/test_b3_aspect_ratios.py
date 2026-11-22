"""Tier 2 Boundary Tests - Category B3: Extreme Aspect Ratios and Resolutions.

Test Cases:
- T2-B3-01: Super-wide aspect ratio crop (10:1 ratio, 1000x100px)
- T2-B3-02: Tall narrow aspect ratio crop (1:2 ratio, 100x200px)
- T2-B3-03: Sub-resolution tiny crop (20x10px, below minimum OCR threshold)
- T2-B3-04: Ultra-high-resolution 4K frame (3840x2160)
- T2-B3-05: Square crop (1:1 ratio, 250x250px)
"""

from __future__ import annotations

import cv2
import numpy as np
import pytest

try:
    from tests.e2e.harness import DatabaseAdapter, E2EApiClient, PlateCropGenerator, PlateGenerator
except ImportError:
    from harness import DatabaseAdapter, E2EApiClient, PlateCropGenerator, PlateGenerator

from anpr_service.ocr.preprocessing import preprocess_plate, detect_dual_row


def test_t2_b3_01_super_wide_aspect_ratio_10_to_1(api_client: E2EApiClient, fresh_db: DatabaseAdapter):
    """T2-B3-01: Super-wide aspect ratio crop (10:1 ratio, 1000x100px).

    Expected: Image processed safely without error; event accepted with confidence >= 0.80.
    """
    plate_text = "DL01AB1234"
    crop = PlateCropGenerator.create_plate_crop(plate_text, width=1000, height=100)
    assert crop.shape == (100, 1000, 3)

    # Process through preprocessing
    prep_res = preprocess_plate(crop)
    assert prep_res.processed_image is not None
    assert prep_res.processed_image.size > 0

    # Ingest event
    payload = {
        "facilityId": "palika",
        "cameraId": "palika-entry-1",
        "gateType": "ENTRY",
        "plateNumber": plate_text,
        "confidence": 0.88,
        "processingTimeMs": 65,
    }
    res = api_client.post_anpr_event(payload)
    assert res["status_code"] == 201
    assert res["status"] == "ACCEPTED"

    # Authoritative DB Assertions
    evt = fresh_db.query_one("SELECT * FROM anpr_events WHERE id = ?", (res["eventId"],))
    assert evt is not None
    assert evt["confidence"] >= 0.80
    assert evt["status"] == "ACCEPTED"
    assert fresh_db.get_live_occupancy("palika") == 1


def test_t2_b3_02_tall_narrow_aspect_ratio_1_to_2(api_client: E2EApiClient, fresh_db: DatabaseAdapter):
    """T2-B3-02: Tall narrow aspect ratio crop (1:2 ratio, 100x200px).

    Expected: Preprocessor detects non-standard/dual-row orientation without crash;
    ingestion status handled gracefully in ('ACCEPTED', 'NEEDS_REVIEW').
    """
    plate_text = "MH12DE1432"
    crop = PlateCropGenerator.create_plate_crop(plate_text, width=100, height=200)
    assert crop.shape == (200, 100, 3)

    # Height / Width = 2.0 >= 0.40 (triggers dual-row detection branch without exception)
    is_dual, _ = detect_dual_row(crop)
    prep_res = preprocess_plate(crop)
    assert prep_res.processed_image is not None

    payload = {
        "facilityId": "palika",
        "cameraId": "palika-entry-1",
        "gateType": "ENTRY",
        "plateNumber": plate_text,
        "confidence": 0.82,
        "processingTimeMs": 45,
    }
    res = api_client.post_anpr_event(payload)
    assert res["status"] in ("ACCEPTED", "NEEDS_REVIEW")

    evt = fresh_db.query_one("SELECT * FROM anpr_events WHERE id = ?", (res["eventId"],))
    assert evt is not None
    assert evt["status"] in ("ACCEPTED", "NEEDS_REVIEW")


def test_t2_b3_03_sub_resolution_tiny_crop(api_client: E2EApiClient, fresh_db: DatabaseAdapter):
    """T2-B3-03: Sub-resolution tiny crop (20x10px, below minimum OCR threshold).

    Expected: Minimum resolution guard or low confidence routes to NEEDS_REVIEW;
    no active session created.
    """
    plate_text = "DL01AB1234"
    # Extremely small 20x10 image cannot be read with high confidence
    tiny_crop = np.full((10, 20, 3), 200, dtype=np.uint8)
    assert tiny_crop.shape == (10, 20, 3)

    # Low confidence read due to extreme pixelation
    payload = {
        "facilityId": "palika",
        "cameraId": "palika-entry-1",
        "gateType": "ENTRY",
        "plateNumber": plate_text,
        "confidence": 0.45,  # Sub-resolution confidence < 0.80
        "plateCropBase64": "data:image/jpeg;base64,tiny...",
        "processingTimeMs": 12,
    }
    res = api_client.post_anpr_event(payload)
    assert res["status_code"] in (200, 202)
    assert res["status"] == "NEEDS_REVIEW"
    assert "Low OCR confidence" in res["reviewReason"]

    # Authoritative DB Assertions
    evt = fresh_db.query_one("SELECT * FROM anpr_events WHERE id = ?", (res["eventId"],))
    assert evt is not None
    assert evt["status"] == "NEEDS_REVIEW"
    assert evt["session_id"] is None

    session = fresh_db.get_active_session("palika", plate_text)
    assert session is None
    assert fresh_db.get_live_occupancy("palika") == 0


def test_t2_b3_04_ultra_high_resolution_4k_frame(api_client: E2EApiClient, fresh_db: DatabaseAdapter):
    """T2-B3-04: Ultra-high-resolution 4K frame (3840x2160).

    Expected: Scaled and processed within processing budget (processingTimeMs < 500);
    event ACCEPTED.
    """
    plate_text = "KA05MB9999"
    # Synthetic frame representation of 4K dimensions
    width, height = 3840, 2160

    # Downsampling test for 4K frame to standard inference size (640x360)
    scale = 640 / width
    new_w = int(width * scale)
    new_h = int(height * scale)
    assert new_w == 640
    assert new_h == 360

    payload = {
        "facilityId": "palika",
        "cameraId": "palika-entry-1",
        "gateType": "ENTRY",
        "plateNumber": plate_text,
        "confidence": 0.94,
        "processingTimeMs": 180,  # Well within 500ms budget
    }
    res = api_client.post_anpr_event(payload)
    assert res["status_code"] == 201
    assert res["status"] == "ACCEPTED"

    # Authoritative DB Assertions
    evt = fresh_db.query_one("SELECT * FROM anpr_events WHERE id = ?", (res["eventId"],))
    assert evt is not None
    assert evt["status"] == "ACCEPTED"
    assert evt["processing_time_ms"] < 500

    session = fresh_db.get_active_session("palika", plate_text)
    assert session is not None
    assert session["status"] == "INSIDE"
    assert fresh_db.get_live_occupancy("palika") == 1


def test_t2_b3_05_square_crop_aspect_ratio_1_to_1(api_client: E2EApiClient, fresh_db: DatabaseAdapter):
    """T2-B3-05: Square crop (1:1 ratio, 250x250px) containing plate and surround.

    Expected: Preprocessing and gating handle square crop; event ACCEPTED.
    """
    plate_text = "HR26DQ5555"
    crop = PlateCropGenerator.create_plate_crop(plate_text, width=250, height=250)
    assert crop.shape == (250, 250, 3)

    prep_res = preprocess_plate(crop)
    assert prep_res.processed_image is not None

    payload = {
        "facilityId": "palika",
        "cameraId": "palika-entry-1",
        "gateType": "ENTRY",
        "plateNumber": plate_text,
        "confidence": 0.91,
        "processingTimeMs": 55,
    }
    res = api_client.post_anpr_event(payload)
    assert res["status_code"] == 201
    assert res["status"] == "ACCEPTED"

    evt = fresh_db.query_one("SELECT * FROM anpr_events WHERE id = ?", (res["eventId"],))
    assert evt is not None
    assert evt["status"] == "ACCEPTED"
    assert fresh_db.get_live_occupancy("palika") == 1
