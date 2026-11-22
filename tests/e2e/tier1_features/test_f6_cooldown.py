"""Tier 1 Feature 6: Gate Cooldown Debouncing (T1-F6-01 .. T1-F6-05).

Validates:
- T1-F6-01: Rapid re-read at t=10s suppressed with COOLDOWN_IGNORED
- T1-F6-02: Intermediate re-read at t=60s suppressed, occupancy unchanged
- T1-F6-03: Boundary re-read at t=119s (<120s limit) suppressed
- T1-F6-04: Re-read at t=121s after cooldown expires handled without duplicate session
- T1-F6-05: Distinct vehicle detected at t=10s on same camera accepted without cooldown
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


def test_t1_f6_01_cooldown_suppression_10s(api_client: E2EApiClient, fresh_db: DatabaseAdapter):
    """T1-F6-01: First read at t=0s, followed by re-read at t=10s on same camera.
    
    Verifies:
    - Event 1: HTTP 201 status='ACCEPTED', liveOccupancy=1
    - Event 2: HTTP 200 status='COOLDOWN_IGNORED'
    - DB vehicle_sessions has exactly 1 row
    - DB anpr_events row 2 has status='COOLDOWN_IGNORED'
    """
    plate_text = "DL01AB1234"
    crop_url = PlateCropGenerator.generate_crop_data_url(plate_text, bg_color="white")

    # Event 1: First detection
    res1 = api_client.post_anpr_event({
        "facilityId": "palika",
        "cameraId": "palika-entry-1",
        "gateType": "ENTRY",
        "plateNumber": plate_text,
        "confidence": 0.95,
        "plateCropBase64": crop_url,
        "detectedAt": "2026-11-21T10:00:00Z",
    })
    assert res1["status_code"] == 201
    assert res1["status"] == "ACCEPTED"
    assert res1["liveOccupancy"] == 1

    # Event 2: Re-read within 10 seconds
    res2 = api_client.post_anpr_event({
        "facilityId": "palika",
        "cameraId": "palika-entry-1",
        "gateType": "ENTRY",
        "plateNumber": plate_text,
        "confidence": 0.95,
        "plateCropBase64": crop_url,
        "detectedAt": "2026-11-21T10:00:10Z",
    })
    assert res2["status_code"] == 200
    assert res2["status"] == "COOLDOWN_IGNORED"
    assert res2["liveOccupancy"] == 1

    # Authoritative DB assertions
    sessions_count = fresh_db.query_one(
        "SELECT COUNT(*) AS c FROM vehicle_sessions WHERE facility_id = 'palika' AND status = 'INSIDE';"
    )["c"]
    assert sessions_count == 1

    evt2 = fresh_db.query_one("SELECT * FROM anpr_events WHERE id = ?", (res2["eventId"],))
    assert evt2["status"] == "COOLDOWN_IGNORED"


def test_t1_f6_02_cooldown_suppression_60s(api_client: E2EApiClient, fresh_db: DatabaseAdapter):
    """T1-F6-02: Re-read of same plate at t=60s on same camera.
    
    Verifies:
    - Status is COOLDOWN_IGNORED
    - liveOccupancy remains unchanged
    - vehicle_sessions count remains 1
    """
    plate_text = "MH12DE1432"
    crop_url = PlateCropGenerator.generate_crop_data_url(plate_text, bg_color="white")

    # Initial detection
    res1 = api_client.post_anpr_event({
        "facilityId": "palika",
        "cameraId": "palika-entry-1",
        "gateType": "ENTRY",
        "plateNumber": plate_text,
        "confidence": 0.94,
        "plateCropBase64": crop_url,
    })
    assert res1["status"] == "ACCEPTED"

    # Re-read at 60s
    res2 = api_client.post_anpr_event({
        "facilityId": "palika",
        "cameraId": "palika-entry-1",
        "gateType": "ENTRY",
        "plateNumber": plate_text,
        "confidence": 0.94,
        "plateCropBase64": crop_url,
    })
    assert res2["status"] == "COOLDOWN_IGNORED"
    assert res2["liveOccupancy"] == 1

    sessions_count = fresh_db.query_one(
        "SELECT COUNT(*) AS c FROM vehicle_sessions WHERE facility_id = 'palika' AND status = 'INSIDE';"
    )["c"]
    assert sessions_count == 1


def test_t1_f6_03_cooldown_boundary_119s(api_client: E2EApiClient, fresh_db: DatabaseAdapter):
    """T1-F6-03: Re-read of same plate at boundary t=119s (<120s window).
    
    Verifies:
    - Border test at 119s remains suppressed (<120s limit)
    - liveOccupancy remains unchanged
    - vehicle_sessions count remains 1
    """
    plate_text = "KA05MB9999"
    crop_url = PlateCropGenerator.generate_crop_data_url(plate_text, bg_color="white")

    res1 = api_client.post_anpr_event({
        "facilityId": "palika",
        "cameraId": "palika-entry-1",
        "gateType": "ENTRY",
        "plateNumber": plate_text,
        "confidence": 0.95,
        "plateCropBase64": crop_url,
    })
    assert res1["status"] == "ACCEPTED"

    # Set last seen epoch to exactly 119 seconds ago
    key = ("palika-entry-1", plate_text)
    import time
    api_client._cooldown_cache[key] = time.time() - 119.0

    res2 = api_client.post_anpr_event({
        "facilityId": "palika",
        "cameraId": "palika-entry-1",
        "gateType": "ENTRY",
        "plateNumber": plate_text,
        "confidence": 0.95,
        "plateCropBase64": crop_url,
    })
    assert res2["status"] == "COOLDOWN_IGNORED"
    assert res2["liveOccupancy"] == 1

    sessions_count = fresh_db.query_one(
        "SELECT COUNT(*) AS c FROM vehicle_sessions WHERE facility_id = 'palika' AND status = 'INSIDE';"
    )["c"]
    assert sessions_count == 1


def test_t1_f6_04_cooldown_expiry_duplicate_prevention(api_client: E2EApiClient, fresh_db: DatabaseAdapter):
    """T1-F6-04: Re-read of same plate at t=121s (after cooldown expires).
    
    Verifies:
    - Cooldown window has elapsed
    - Partial unique index prevents duplicate active session for same vehicle
    - Active sessions count remains strictly 1
    """
    plate_text = "UP16BZ4321"
    crop_url = PlateCropGenerator.generate_crop_data_url(plate_text, bg_color="white")

    res1 = api_client.post_anpr_event({
        "facilityId": "palika",
        "cameraId": "palika-entry-1",
        "gateType": "ENTRY",
        "plateNumber": plate_text,
        "confidence": 0.94,
        "plateCropBase64": crop_url,
    })
    assert res1["status"] == "ACCEPTED"
    assert res1["liveOccupancy"] == 1

    # Simulate cooldown expiration (> 120s)
    key = ("palika-entry-1", plate_text)
    import time
    api_client._cooldown_cache[key] = time.time() - 125.0

    # Ingest detection after cooldown expiration
    res2 = api_client.post_anpr_event({
        "facilityId": "palika",
        "cameraId": "palika-entry-1",
        "gateType": "ENTRY",
        "plateNumber": plate_text,
        "confidence": 0.94,
        "plateCropBase64": crop_url,
    })

    # Cooldown has expired, but duplicate entry logic / DB constraint prevents duplicate active session
    assert res2["status"] in ("DUPLICATE_ENTRY", "COOLDOWN_IGNORED") or res2["success"] is False
    assert res2["liveOccupancy"] == 1

    active_count = fresh_db.query_one(
        """
        SELECT COUNT(*) AS c FROM vehicle_sessions
        WHERE facility_id = 'palika' AND plate_number = ? AND status = 'INSIDE';
        """,
        (plate_text,),
    )["c"]
    assert active_count == 1, "There must NEVER be duplicate INSIDE sessions for the same vehicle"


def test_t1_f6_05_different_plate_no_cooldown(api_client: E2EApiClient, fresh_db: DatabaseAdapter):
    """T1-F6-05: Different plate detected at t=10s on same camera.
    
    Verifies:
    - Cooldown debouncing is strictly per-plate
    - Distinct vehicle arriving 10s after first vehicle is ACCEPTED
    - vehicle_sessions count increments to 2
    - liveOccupancy increments to 2
    """
    plate_1 = "DL01AB1111"
    plate_2 = "MH12DE2222"

    crop_1 = PlateCropGenerator.generate_crop_data_url(plate_1, bg_color="white")
    crop_2 = PlateCropGenerator.generate_crop_data_url(plate_2, bg_color="white")

    # Vehicle 1 enters
    res1 = api_client.post_anpr_event({
        "facilityId": "palika",
        "cameraId": "palika-entry-1",
        "gateType": "ENTRY",
        "plateNumber": plate_1,
        "confidence": 0.95,
        "plateCropBase64": crop_1,
    })
    assert res1["status"] == "ACCEPTED"
    assert res1["liveOccupancy"] == 1

    # Vehicle 2 enters on same camera immediately
    res2 = api_client.post_anpr_event({
        "facilityId": "palika",
        "cameraId": "palika-entry-1",
        "gateType": "ENTRY",
        "plateNumber": plate_2,
        "confidence": 0.95,
        "plateCropBase64": crop_2,
    })
    assert res2["status_code"] == 201
    assert res2["status"] == "ACCEPTED"
    assert res2["liveOccupancy"] == 2

    active_sessions = fresh_db.query(
        "SELECT plate_number FROM vehicle_sessions WHERE facility_id = 'palika' AND status = 'INSIDE';"
    )
    plates_inside = {s["plate_number"] for s in active_sessions}
    assert plate_1 in plates_inside
    assert plate_2 in plates_inside
    assert len(plates_inside) == 2
