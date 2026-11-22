"""Tier 2 Boundary Tests - Category B2: Malformed Plate Syntax.

Test Cases:
- T2-B2-01: Lowercase registration string auto-uppercased (dl01ab1234 -> DL01AB1234)
- T2-B2-02: Truncated plate missing digits (DL01AB12 -> NEEDS_REVIEW, no session)
- T2-B2-03: Non-existent Indian state code (ZZ99XX9999 -> NEEDS_REVIEW, no session)
- T2-B2-04: Punctuation formatted plate sanitized (DL-01-AB-1234 -> DL01AB1234)
- T2-B2-05: Excessively long garbage text (DL01AB123456789 -> NEEDS_REVIEW, no session)
"""

from __future__ import annotations

import pytest

try:
    from tests.e2e.harness import DatabaseAdapter, E2EApiClient, PlateGenerator
except ImportError:
    from harness import DatabaseAdapter, E2EApiClient, PlateGenerator

from anpr_service.validator.indian_plate import IndianPlateValidator


def test_t2_b2_01_lowercase_registration_uppercased(api_client: E2EApiClient, fresh_db: DatabaseAdapter):
    """T2-B2-01: Lowercase registration string auto-uppercased to standard uppercase.

    Input: 'dl01ab1234'
    Expected: Auto-uppercased to 'DL01AB1234', valid session created.
    """
    raw_plate = "dl01ab1234"

    # Also verify through validator
    val_res = IndianPlateValidator().validate(raw_plate)
    assert val_res.normalized_plate == "DL01AB1234"
    assert val_res.is_valid is True

    payload = {
        "facilityId": "palika",
        "cameraId": "palika-entry-1",
        "gateType": "ENTRY",
        "plateNumber": raw_plate,
        "confidence": 0.95,
    }
    res = api_client.post_anpr_event(payload)
    assert res["status_code"] == 201
    assert res["success"] is True
    assert res["status"] == "ACCEPTED"

    # Authoritative DB Assertions
    evt = fresh_db.query_one("SELECT * FROM anpr_events WHERE id = ?", (res["eventId"],))
    assert evt is not None
    assert evt["plate_number"] == "DL01AB1234"
    assert evt["status"] == "ACCEPTED"

    session = fresh_db.get_active_session("palika", "DL01AB1234")
    assert session is not None
    assert session["status"] == "INSIDE"
    assert fresh_db.get_live_occupancy("palika") == 1


def test_t2_b2_02_truncated_plate_missing_digits(api_client: E2EApiClient, fresh_db: DatabaseAdapter):
    """T2-B2-02: Truncated plate missing digits triggers NEEDS_REVIEW.

    Input: 'DL01AB12' (missing 2 digits in 4-digit number slot)
    Expected: status='NEEDS_REVIEW', no active session created, occupancy unchanged.
    """
    raw_plate = "DL01AB12"

    is_valid, reason = PlateGenerator.is_valid_indian_plate(raw_plate)
    assert is_valid is False

    payload = {
        "facilityId": "palika",
        "cameraId": "palika-entry-1",
        "gateType": "ENTRY",
        "plateNumber": raw_plate,
        "confidence": 0.95,
    }
    res = api_client.post_anpr_event(payload)
    assert res["status_code"] in (200, 202)
    assert res["status"] == "NEEDS_REVIEW"
    assert res["liveOccupancy"] == 0

    # Authoritative DB Assertions
    evt = fresh_db.query_one("SELECT * FROM anpr_events WHERE id = ?", (res["eventId"],))
    assert evt is not None
    assert evt["status"] == "NEEDS_REVIEW"
    assert evt["session_id"] is None

    # Verify NO active session created in database
    session = fresh_db.get_active_session("palika", raw_plate)
    assert session is None
    assert fresh_db.get_live_occupancy("palika") == 0


def test_t2_b2_03_non_existent_state_code(api_client: E2EApiClient, fresh_db: DatabaseAdapter):
    """T2-B2-03: Non-existent Indian state code rejected.

    Input: 'ZZ99XX9999' ('ZZ' is not a valid Indian state/UT)
    Expected: status='NEEDS_REVIEW', no active session created.
    """
    raw_plate = "ZZ99XX9999"

    val_res = IndianPlateValidator().validate(raw_plate)
    assert val_res.is_valid is False
    assert val_res.state_code == "ZZ"

    payload = {
        "facilityId": "palika",
        "cameraId": "palika-entry-1",
        "gateType": "ENTRY",
        "plateNumber": raw_plate,
        "confidence": 0.95,
    }
    res = api_client.post_anpr_event(payload)
    assert res["status_code"] in (200, 202)
    assert res["status"] == "NEEDS_REVIEW"
    assert "Invalid grammar" in res.get("reviewReason", "") or "INVALID_STATE_CODE" in res.get("reviewReason", "")

    # Authoritative DB Assertions
    evt = fresh_db.query_one("SELECT * FROM anpr_events WHERE id = ?", (res["eventId"],))
    assert evt is not None
    assert evt["status"] == "NEEDS_REVIEW"
    assert evt["session_id"] is None

    assert fresh_db.get_active_session("palika", raw_plate) is None
    assert fresh_db.get_live_occupancy("palika") == 0


def test_t2_b2_04_punctuation_formatted_plate(api_client: E2EApiClient, fresh_db: DatabaseAdapter):
    """T2-B2-04: Punctuation formatted plate sanitized and accepted.

    Input: 'DL-01-AB-1234'
    Expected: Hyphens stripped to 'DL01AB1234', valid session created.
    """
    raw_plate = "DL-01-AB-1234"

    val_res = IndianPlateValidator().validate(raw_plate)
    assert val_res.is_valid is True
    assert val_res.normalized_plate == "DL01AB1234"

    payload = {
        "facilityId": "palika",
        "cameraId": "palika-entry-1",
        "gateType": "ENTRY",
        "plateNumber": raw_plate,
        "confidence": 0.95,
    }
    res = api_client.post_anpr_event(payload)
    assert res["status_code"] == 201
    assert res["success"] is True
    assert res["status"] == "ACCEPTED"

    # Authoritative DB Assertions
    evt = fresh_db.query_one("SELECT * FROM anpr_events WHERE id = ?", (res["eventId"],))
    assert evt is not None
    assert evt["plate_number"] == "DL01AB1234"

    session = fresh_db.get_active_session("palika", "DL01AB1234")
    assert session is not None
    assert session["status"] == "INSIDE"
    assert fresh_db.get_live_occupancy("palika") == 1


def test_t2_b2_05_excessively_long_garbage_text(api_client: E2EApiClient, fresh_db: DatabaseAdapter):
    """T2-B2-05: Excessively long garbage text routed to review queue.

    Input: 'DL01AB123456789' (15 chars)
    Expected: status='NEEDS_REVIEW', no active session created.
    """
    raw_plate = "DL01AB123456789"

    val_res = IndianPlateValidator().validate(raw_plate)
    assert val_res.is_valid is False

    payload = {
        "facilityId": "palika",
        "cameraId": "palika-entry-1",
        "gateType": "ENTRY",
        "plateNumber": raw_plate,
        "confidence": 0.95,
    }
    res = api_client.post_anpr_event(payload)
    assert res["status_code"] in (200, 202)
    assert res["status"] == "NEEDS_REVIEW"

    # Authoritative DB Assertions
    evt = fresh_db.query_one("SELECT * FROM anpr_events WHERE id = ?", (res["eventId"],))
    assert evt is not None
    assert evt["status"] == "NEEDS_REVIEW"
    assert evt["session_id"] is None

    assert fresh_db.get_active_session("palika", raw_plate) is None
    assert fresh_db.get_live_occupancy("palika") == 0
