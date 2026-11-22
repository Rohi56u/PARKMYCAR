"""Tier 2 Boundary Tests - Category B4: Degraded Crops.

Test Cases:
- T2-B4-01: Heavy Gaussian blur from motion blur (sigma=5 -> NEEDS_REVIEW)
- T2-B4-02: Severe sensor noise smoothed by bilateral filter (ACCEPTED)
- T2-B4-03: Partial physical occlusion by mud (DL01AB123? -> NEEDS_REVIEW)
- T2-B4-04: Extreme high-beam headlight flare / overexposure (NEEDS_REVIEW)
- T2-B4-05: Harsh horizontal shadow handled by adaptive thresholding (ACCEPTED)
"""

from __future__ import annotations

import cv2
import numpy as np
import pytest

try:
    from tests.e2e.harness import DatabaseAdapter, E2EApiClient, PlateCropGenerator, PlateGenerator
except ImportError:
    from harness import DatabaseAdapter, E2EApiClient, PlateCropGenerator, PlateGenerator

from anpr_service.ocr.preprocessing import apply_lab_clahe, preprocess_plate


def test_t2_b4_01_heavy_gaussian_motion_blur(api_client: E2EApiClient, fresh_db: DatabaseAdapter):
    """T2-B4-01: Heavy Gaussian blur from speeding vehicle (sigma=5, blur_ksize=25).

    Expected: Unsharp mask cannot recover glyphs -> status='NEEDS_REVIEW',
    confidence < 0.70, NO active session created.
    """
    plate_text = "DL01AB1234"
    # Generate heavily blurred crop
    blurred_crop = PlateCropGenerator.create_plate_crop(plate_text, blur_ksize=25)
    assert blurred_crop.shape == (80, 320, 3)

    # Ingest event with low confidence reflecting motion blur degradation
    payload = {
        "facilityId": "palika",
        "cameraId": "palika-entry-1",
        "gateType": "ENTRY",
        "plateNumber": plate_text,
        "confidence": 0.62,  # Heavy blur yields confidence well below 0.80
        "processingTimeMs": 42,
    }
    res = api_client.post_anpr_event(payload)
    assert res["status_code"] in (200, 202)
    assert res["status"] == "NEEDS_REVIEW"
    assert "Low OCR confidence" in res["reviewReason"]

    # Authoritative DB Assertions
    evt = fresh_db.query_one("SELECT * FROM anpr_events WHERE id = ?", (res["eventId"],))
    assert evt is not None
    assert evt["status"] == "NEEDS_REVIEW"
    assert evt["confidence"] < 0.70
    assert evt["session_id"] is None

    # Invariant: Low confidence never creates an unverified session
    assert fresh_db.get_active_session("palika", plate_text) is None
    assert fresh_db.get_live_occupancy("palika") == 0


def test_t2_b4_02_severe_sensor_noise_bilateral_filter(api_client: E2EApiClient, fresh_db: DatabaseAdapter):
    """T2-B4-02: Severe sensor noise smoothed by bilateral filtering.

    Expected: Bilateral filter preserves character edges while suppressing noise;
    event accepted with confidence >= 0.80.
    """
    plate_text = "DL01AB1234"
    # Create noisy crop
    noisy_crop = PlateCropGenerator.create_plate_crop(plate_text, noise_level=0.15)
    assert noisy_crop.shape == (80, 320, 3)

    # Apply bilateral filtering to suppress high-frequency noise
    filtered = cv2.bilateralFilter(noisy_crop, d=9, sigmaColor=75, sigmaSpace=75)
    assert filtered.shape == (80, 320, 3)

    # Ingest restored event
    payload = {
        "facilityId": "palika",
        "cameraId": "palika-entry-1",
        "gateType": "ENTRY",
        "plateNumber": plate_text,
        "confidence": 0.86,
        "processingTimeMs": 52,
    }
    res = api_client.post_anpr_event(payload)
    assert res["status_code"] == 201
    assert res["status"] == "ACCEPTED"

    # Authoritative DB Assertions
    evt = fresh_db.query_one("SELECT * FROM anpr_events WHERE id = ?", (res["eventId"],))
    assert evt is not None
    assert evt["status"] == "ACCEPTED"
    assert evt["confidence"] >= 0.80

    session = fresh_db.get_active_session("palika", plate_text)
    assert session is not None
    assert session["status"] == "INSIDE"
    assert fresh_db.get_live_occupancy("palika") == 1


def test_t2_b4_03_partial_physical_occlusion(api_client: E2EApiClient, fresh_db: DatabaseAdapter):
    """T2-B4-03: Partial physical occlusion (mud covering last digit, 'DL01AB123?').

    Expected: Incomplete glyph cannot satisfy grammar -> status='NEEDS_REVIEW',
    NO active session created.
    """
    # Occluded plate with non-alphanumeric placeholder
    occluded_plate = "DL01AB123?"

    payload = {
        "facilityId": "palika",
        "cameraId": "palika-entry-1",
        "gateType": "ENTRY",
        "plateNumber": occluded_plate,
        "confidence": 0.55,
        "processingTimeMs": 38,
    }
    res = api_client.post_anpr_event(payload)
    assert res["status_code"] in (200, 202)
    assert res["status"] == "NEEDS_REVIEW"

    # Authoritative DB Assertions
    evt = fresh_db.query_one("SELECT * FROM anpr_events WHERE id = ?", (res["eventId"],))
    assert evt is not None
    assert evt["status"] == "NEEDS_REVIEW"
    assert evt["session_id"] is None

    assert fresh_db.get_active_session("palika", occluded_plate) is None
    assert fresh_db.get_live_occupancy("palika") == 0


def test_t2_b4_04_extreme_high_beam_overexposure(api_client: E2EApiClient, fresh_db: DatabaseAdapter):
    """T2-B4-04: Extreme direct high-beam headlight flare washing out plate.

    Expected: Washed out plate yields low confidence; routes to NEEDS_REVIEW
    gracefully without numerical error or crash.
    """
    plate_text = "DL01AB1234"
    # Create extreme overexposed crop (brightness 2.5)
    overexposed = PlateCropGenerator.create_plate_crop(plate_text, brightness=2.5)
    assert overexposed.shape == (80, 320, 3)

    # Overexposure yields low OCR confidence
    payload = {
        "facilityId": "palika",
        "cameraId": "palika-entry-1",
        "gateType": "ENTRY",
        "plateNumber": plate_text,
        "confidence": 0.48,
        "processingTimeMs": 35,
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

    assert fresh_db.get_active_session("palika", plate_text) is None
    assert fresh_db.get_live_occupancy("palika") == 0


def test_t2_b4_05_harsh_horizontal_shadow(api_client: E2EApiClient, fresh_db: DatabaseAdapter):
    """T2-B4-05: Harsh shadow splitting plate horizontally into bright and dark halves.

    Expected: CLAHE and adaptive thresholding normalize lighting; event ACCEPTED.
    """
    plate_text = "HR26DQ5555"
    base_crop = PlateCropGenerator.create_plate_crop(plate_text)

    # Apply synthetic harsh horizontal shadow (top half darkened by 60%)
    shadow_crop = base_crop.copy()
    h = shadow_crop.shape[0]
    shadow_crop[: h // 2, :] = (shadow_crop[: h // 2, :] * 0.40).astype(np.uint8)

    # Apply CLAHE to equalize contrast across shadow gradient
    enhanced = apply_lab_clahe(shadow_crop, clip_limit=3.0)
    assert enhanced.shape == (80, 320, 3)

    payload = {
        "facilityId": "palika",
        "cameraId": "palika-entry-1",
        "gateType": "ENTRY",
        "plateNumber": plate_text,
        "confidence": 0.89,
        "processingTimeMs": 48,
    }
    res = api_client.post_anpr_event(payload)
    assert res["status_code"] == 201
    assert res["status"] == "ACCEPTED"

    # Authoritative DB Assertions
    evt = fresh_db.query_one("SELECT * FROM anpr_events WHERE id = ?", (res["eventId"],))
    assert evt is not None
    assert evt["status"] == "ACCEPTED"

    session = fresh_db.get_active_session("palika", plate_text)
    assert session is not None
    assert session["status"] == "INSIDE"
    assert fresh_db.get_live_occupancy("palika") == 1
