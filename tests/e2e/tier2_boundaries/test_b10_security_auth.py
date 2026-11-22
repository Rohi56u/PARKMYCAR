"""Tier 2 Boundary Tests - Category B10: Security & Bad Authentication.

Test Cases:
- T2-B10-01: Missing X-ANPR-Secret header rejects with HTTP 401 Unauthorized
- T2-B10-02: Invalid X-ANPR-Secret header rejects with HTTP 401 Unauthorized
- T2-B10-03: Missing or bad Content-Type / header format handling
- T2-B10-04: Malformed payload / missing required fields handled safely
- T2-B10-05: SQL injection attempt in plateNumber safely escaped via parameterized queries
"""

from __future__ import annotations

import pytest

try:
    from tests.e2e.harness import DatabaseAdapter, E2EApiClient, PlateGenerator
except ImportError:
    from harness import DatabaseAdapter, E2EApiClient, PlateGenerator


def test_t2_b10_01_missing_x_anpr_secret_unauthorized(api_client: E2EApiClient, fresh_db: DatabaseAdapter):
    """T2-B10-01: POST /api/v1/anpr/events missing X-ANPR-Secret header.

    Expected: HTTP 401 Unauthorized; NO rows written to anpr_events or vehicle_sessions.
    """
    payload = {
        "facilityId": "palika",
        "cameraId": "palika-entry-1",
        "gateType": "ENTRY",
        "plateNumber": "DL01AB1234",
        "confidence": 0.95,
    }

    # Request with empty headers (missing X-ANPR-Secret)
    res = api_client.post_anpr_event(payload, headers={})
    assert res["status_code"] == 401
    assert res["success"] is False
    assert "Unauthorized" in res["error"]

    # Authoritative DB Assertions: zero database mutation
    events = fresh_db.query("SELECT * FROM anpr_events;")
    sessions = fresh_db.query("SELECT * FROM vehicle_sessions;")
    assert len(events) == 0
    assert len(sessions) == 0
    assert fresh_db.get_live_occupancy("palika") == 0


def test_t2_b10_02_invalid_x_anpr_secret_rejected(api_client: E2EApiClient, fresh_db: DatabaseAdapter):
    """T2-B10-02: POST /api/v1/anpr/events with invalid X-ANPR-Secret token.

    Expected: HTTP 401 Unauthorized; constant-time comparison rejects client;
    NO rows written to database.
    """
    payload = {
        "facilityId": "palika",
        "cameraId": "palika-entry-1",
        "gateType": "ENTRY",
        "plateNumber": "DL01AB1234",
        "confidence": 0.95,
    }

    res = api_client.post_anpr_event(payload, headers={"X-ANPR-Secret": "tampered-secret-xyz"})
    assert res["status_code"] == 401
    assert res["success"] is False

    # Authoritative DB Assertions: zero database mutation
    events = fresh_db.query("SELECT * FROM anpr_events;")
    sessions = fresh_db.query("SELECT * FROM vehicle_sessions;")
    assert len(events) == 0
    assert len(sessions) == 0
    assert fresh_db.get_live_occupancy("palika") == 0


def test_t2_b10_03_wrong_content_type_header_validation(api_client: E2EApiClient, fresh_db: DatabaseAdapter):
    """T2-B10-03: Header validation and case-insensitivity verification.

    Expected: Validates header casing (e.g. lowercase 'x-anpr-secret') and enforces
    authentication integrity across varied client headers.
    """
    payload = {
        "facilityId": "palika",
        "cameraId": "palika-entry-1",
        "gateType": "ENTRY",
        "plateNumber": "DL01AB1234",
        "confidence": 0.95,
    }

    # Case-insensitive header lookup: lowercase 'x-anpr-secret' accepted
    headers_lower = {"x-anpr-secret": api_client.secret, "Content-Type": "application/json"}
    res_ok = api_client.post_anpr_event(payload, headers=headers_lower)
    assert res_ok["status_code"] == 201
    assert res_ok["success"] is True

    # Bad header key without secret
    headers_bad = {"Content-Type": "text/plain"}
    res_bad = api_client.post_anpr_event(payload, headers=headers_bad)
    assert res_bad["status_code"] == 401
    assert res_bad["success"] is False


def test_t2_b10_04_missing_required_fields_handled_safely(api_client: E2EApiClient, fresh_db: DatabaseAdapter):
    """T2-B10-04: Missing required fields or empty payload handled safely.

    Expected: Gating or fallback catches empty plateNumber; no unverified session created.
    """
    empty_payload = {
        "facilityId": "palika",
        "cameraId": "palika-entry-1",
        "gateType": "ENTRY",
        "plateNumber": "",
        "confidence": 0.0,
    }

    res = api_client.post_anpr_event(empty_payload)
    # Empty plate fails validation, marked NEEDS_REVIEW without session creation
    assert res["status"] == "NEEDS_REVIEW"
    assert fresh_db.get_live_occupancy("palika") == 0

    sessions = fresh_db.query("SELECT * FROM vehicle_sessions;")
    assert len(sessions) == 0


def test_t2_b10_05_sql_injection_attempt_in_plate_number(api_client: E2EApiClient, fresh_db: DatabaseAdapter):
    """T2-B10-05: SQL injection attempt in plateNumber is safely handled.

    Input: \"DL01AB1234'; DROP TABLE vehicles; --\"
    Expected: Parameterized SQLite queries safely escape injection;
    database schema remains intact; grammar validation flags syntax;
    vehicles table is NOT dropped.
    """
    malicious_plate = "DL01AB1234'; DROP TABLE vehicles; --"

    payload = {
        "facilityId": "palika",
        "cameraId": "palika-entry-1",
        "gateType": "ENTRY",
        "plateNumber": malicious_plate,
        "confidence": 0.95,
    }

    res = api_client.post_anpr_event(payload)
    # Grammar validator rejects special SQL characters, routes to NEEDS_REVIEW
    assert res["status"] == "NEEDS_REVIEW"

    # CRUCIAL INVARIANT: Table vehicles still exists and is completely unharmed!
    vehicles_check = fresh_db.query("SELECT COUNT(*) AS c FROM vehicles;")
    assert vehicles_check is not None
    assert isinstance(vehicles_check[0]["c"], int)

    sessions_check = fresh_db.query("SELECT COUNT(*) AS c FROM vehicle_sessions;")
    assert sessions_check is not None
    assert isinstance(sessions_check[0]["c"], int)

    # Injected string safely recorded as parameterized parameter in anpr_events
    evt = fresh_db.query_one("SELECT * FROM anpr_events WHERE id = ?;", (res["eventId"],))
    assert evt is not None
    assert evt["status"] == "NEEDS_REVIEW"
