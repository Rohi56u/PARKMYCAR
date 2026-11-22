"""Tier 1 Feature 4: Positional Character Normalization & NEEDS_REVIEW Gating (T1-F4-01 .. T1-F4-05).

Validates:
- T1-F4-01: Raw OCR string "DLO1AB1234" (letter 'O' at index 2 converted to digit '0')
- T1-F4-02: Raw OCR string "DL01ABI234" (letter 'I' at index 6 converted to digit '1')
- T1-F4-03: Raw OCR string "DL01AB12B4" (letter 'B' at index 8 converted to digit '8')
- T1-F4-04: Low OCR confidence read (<0.80) gated to status='NEEDS_REVIEW' without session
- T1-F4-05: Unparseable symbols ("DL01@#1234") gated to status='NEEDS_REVIEW' without session
"""

from __future__ import annotations

import sys
from pathlib import Path

_repo_root = Path(__file__).resolve().parent.parent.parent
if str(_repo_root) not in sys.path:
    sys.path.insert(0, str(_repo_root))

_e2e_root = Path(__file__).resolve().parent.parent
if str(_e2e_root) not in sys.path:
    sys.path.insert(0, str(_e2e_root))

import pytest

from anpr_service.validator import (
    IndianPlateValidator,
    PlateValidationResult,
    ValidationStatus,
    disambiguate_standard_hsrp,
)

try:
    from tests.e2e.harness import (
        DatabaseAdapter,
        E2EApiClient,
        PlateCropGenerator,
        PlateGenerator,
    )
except ImportError:
    from harness import (
        DatabaseAdapter,
        E2EApiClient,
        PlateCropGenerator,
        PlateGenerator,
    )


def test_t1_f4_01_normalize_letter_o_in_rto_slot(api_client: E2EApiClient, fresh_db: DatabaseAdapter):
    """T1-F4-01: Raw OCR string "DLO1AB1234" (letter 'O' at index 2 in RTO slot).
    
    Verifies:
    - Positional disambiguation converts 'O' -> '0' at index 2
    - Output normalized plate is "DL01AB1234"
    - Database anpr_events records plate_number = "DL01AB1234", status = "ACCEPTED"
    """
    raw_ocr = "DLO1AB1234"

    # 1. Positional disambiguation logic
    validator = IndianPlateValidator()
    val_res = validator.validate(raw_ocr)
    assert val_res.status == ValidationStatus.ACCEPTED
    assert val_res.normalized_plate == "DL01AB1234"

    norm_res = disambiguate_standard_hsrp(raw_ocr)
    assert norm_res is not None
    normalized_plate, subs = norm_res
    assert normalized_plate == "DL01AB1234"
    assert subs >= 1

    # 2. Ingest normalized plate through E2E API
    crop_url = PlateCropGenerator.generate_crop_data_url(normalized_plate, bg_color="white")
    res = api_client.post_anpr_event({
        "facilityId": "palika",
        "cameraId": "palika-entry-1",
        "gateType": "ENTRY",
        "plateNumber": normalized_plate,
        "confidence": 0.94,
        "plateCropBase64": crop_url,
    })

    assert res["status_code"] == 201
    assert res["status"] == "ACCEPTED"
    assert res["liveOccupancy"] == 1

    # 3. Database assertions
    event = fresh_db.query_one("SELECT * FROM anpr_events WHERE id = ?", (res["eventId"],))
    assert event["plate_number"] == "DL01AB1234"
    assert event["status"] == "ACCEPTED"


def test_t1_f4_02_normalize_letter_i_in_number_slot(api_client: E2EApiClient, fresh_db: DatabaseAdapter):
    """T1-F4-02: Raw OCR string "DL01ABI234" (letter 'I' at index 6 in numeric number slot).
    
    Verifies:
    - Positional disambiguation converts 'I' -> '1' at index 6
    - Output normalized plate is "DL01AB1234"
    - Database anpr_events records plate_number = "DL01AB1234", status = "ACCEPTED"
    """
    raw_ocr = "DL01ABI234"

    validator = IndianPlateValidator()
    val_res = validator.validate(raw_ocr)
    assert val_res.status == ValidationStatus.ACCEPTED
    assert val_res.normalized_plate == "DL01AB1234"

    norm_res = disambiguate_standard_hsrp(raw_ocr)
    assert norm_res is not None
    normalized_plate, subs = norm_res
    assert normalized_plate == "DL01AB1234"
    assert subs >= 1

    crop_url = PlateCropGenerator.generate_crop_data_url(normalized_plate, bg_color="white")
    res = api_client.post_anpr_event({
        "facilityId": "palika",
        "cameraId": "palika-entry-1",
        "gateType": "ENTRY",
        "plateNumber": normalized_plate,
        "confidence": 0.92,
        "plateCropBase64": crop_url,
    })

    assert res["status_code"] == 201
    assert res["status"] == "ACCEPTED"

    event = fresh_db.query_one("SELECT * FROM anpr_events WHERE id = ?", (res["eventId"],))
    assert event["plate_number"] == "DL01AB1234"
    assert event["status"] == "ACCEPTED"


def test_t1_f4_03_normalize_letter_b_in_number_slot(api_client: E2EApiClient, fresh_db: DatabaseAdapter):
    """T1-F4-03: Raw OCR string "DL01AB12B4" (letter 'B' at index 8 in numeric number slot).
    
    Verifies:
    - Positional disambiguation converts 'B' -> '8' at index 8
    - Output normalized plate is "DL01AB1284"
    - Database anpr_events records plate_number = "DL01AB1284", status = "ACCEPTED"
    """
    raw_ocr = "DL01AB12B4"

    validator = IndianPlateValidator()
    val_res = validator.validate(raw_ocr)
    assert val_res.status == ValidationStatus.ACCEPTED
    assert val_res.normalized_plate == "DL01AB1284"

    norm_res = disambiguate_standard_hsrp(raw_ocr)
    assert norm_res is not None
    normalized_plate, subs = norm_res
    assert normalized_plate == "DL01AB1284"
    assert subs >= 1

    crop_url = PlateCropGenerator.generate_crop_data_url(normalized_plate, bg_color="white")
    res = api_client.post_anpr_event({
        "facilityId": "palika",
        "cameraId": "palika-entry-1",
        "gateType": "ENTRY",
        "plateNumber": normalized_plate,
        "confidence": 0.93,
        "plateCropBase64": crop_url,
    })

    assert res["status_code"] == 201
    assert res["status"] == "ACCEPTED"

    event = fresh_db.query_one("SELECT * FROM anpr_events WHERE id = ?", (res["eventId"],))
    assert event["plate_number"] == "DL01AB1284"
    assert event["status"] == "ACCEPTED"


def test_t1_f4_04_low_confidence_needs_review_gating(api_client: E2EApiClient, fresh_db: DatabaseAdapter):
    """T1-F4-04: Plate with low recognition confidence (confidence = 0.65 < 0.80).
    
    Verifies:
    - HTTP 200/202 with status="NEEDS_REVIEW"
    - Database anpr_events records status = 'NEEDS_REVIEW'
    - NO active row created in vehicle_sessions (get_active_session returns None)
    - liveOccupancy remains unchanged (0)
    """
    plate_text = "DL01AB1234"
    crop_url = PlateCropGenerator.generate_crop_data_url(plate_text, bg_color="white")

    res = api_client.post_anpr_event({
        "facilityId": "palika",
        "cameraId": "palika-entry-1",
        "gateType": "ENTRY",
        "plateNumber": plate_text,
        "confidence": 0.65,  # Below min threshold 0.80
        "plateCropBase64": crop_url,
        "detectedAt": "2026-11-21T10:00:00Z",
    })

    assert res["status"] == "NEEDS_REVIEW"
    assert res["liveOccupancy"] == 0
    assert "Low OCR confidence" in res["reviewReason"]

    # Invariant: NO unverified vehicle session created
    active_session = fresh_db.get_active_session("palika", plate_text)
    assert active_session is None, "NEEDS_REVIEW event must NEVER create an active session"

    event = fresh_db.query_one("SELECT * FROM anpr_events WHERE id = ?", (res["eventId"],))
    assert event is not None
    assert event["status"] == "NEEDS_REVIEW"
    assert event["session_id"] is None
    assert fresh_db.get_live_occupancy("palika") == 0


def test_t1_f4_05_invalid_symbols_needs_review_gating(api_client: E2EApiClient, fresh_db: DatabaseAdapter):
    """T1-F4-05: Plate containing invalid symbols ("DL01@#1234") that cannot be normalized.
    
    Verifies:
    - Unparseable glyphs route event to status="NEEDS_REVIEW"
    - session_id IS NULL in anpr_events
    - NO active row created in vehicle_sessions, liveOccupancy remains 0
    """
    malformed_plate = "DL01@#1234"
    crop_url = PlateCropGenerator.generate_crop_data_url("DL01AB1234", bg_color="white")

    res = api_client.post_anpr_event({
        "facilityId": "palika",
        "cameraId": "palika-entry-1",
        "gateType": "ENTRY",
        "plateNumber": malformed_plate,
        "confidence": 0.95,
        "plateCropBase64": crop_url,
    })

    assert res["status"] == "NEEDS_REVIEW"
    assert res["liveOccupancy"] == 0

    event = fresh_db.query_one("SELECT * FROM anpr_events WHERE id = ?", (res["eventId"],))
    assert event is not None
    assert event["status"] == "NEEDS_REVIEW"
    assert event["session_id"] is None

    # Zero sessions created
    sessions_count = fresh_db.query_one(
        "SELECT COUNT(*) AS c FROM vehicle_sessions WHERE facility_id = 'palika';"
    )["c"]
    assert sessions_count == 0
    assert fresh_db.get_live_occupancy("palika") == 0
