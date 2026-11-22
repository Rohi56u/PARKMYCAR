"""Tier 1 Feature 9: Vehicle Exit Matching & Occupancy Decrement (T1-F9-01 .. T1-F9-05).

Validates:
- T1-F9-01: Vehicle exit transitions session to EXITED, records duration, and decrements occupancy
- T1-F9-02: Audit timestamps and exit camera recorded accurately on departure
- T1-F9-03: Re-entry of vehicle after prior session EXITED succeeds under partial unique index
- T1-F9-04: Exit calculates parking tariff based on length of stay
- T1-F9-05: Live occupancy endpoint immediately updates following exit event
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


def test_t1_f9_01_exit_matching_and_duration_30m(api_client: E2EApiClient, fresh_db: DatabaseAdapter):
    """T1-F9-01: Exit event for active vehicle (30 minutes stay).
    
    Verifies:
    - HTTP 200 status="ACCEPTED"
    - duration_seconds = 1800 (30 minutes)
    - liveOccupancy decrements from 1 to 0
    - availableCapacity returns to 900
    - vehicle_sessions.status updated to 'EXITED'
    """
    plate_text = "DL01AB1234"
    crop_url = PlateCropGenerator.generate_crop_data_url(plate_text, bg_color="white")

    # 1. Entry at 10:00:00Z
    entry_res = api_client.post_anpr_event({
        "facilityId": "palika",
        "cameraId": "palika-entry-1",
        "gateType": "ENTRY",
        "plateNumber": plate_text,
        "confidence": 0.95,
        "plateCropBase64": crop_url,
        "detectedAt": "2026-11-21T10:00:00Z",
    })
    assert entry_res["status"] == "ACCEPTED"
    assert fresh_db.get_live_occupancy("palika") == 1

    # 2. Exit at 10:30:00Z (1800 seconds later)
    exit_res = api_client.post_anpr_event({
        "facilityId": "palika",
        "cameraId": "palika-exit-1",
        "gateType": "EXIT",
        "plateNumber": plate_text,
        "confidence": 0.95,
        "plateCropBase64": crop_url,
        "detectedAt": "2026-11-21T10:30:00Z",
    })

    assert exit_res["status_code"] == 200
    assert exit_res["success"] is True
    assert exit_res["status"] == "ACCEPTED"
    assert exit_res["durationSeconds"] == 1800
    assert exit_res["liveOccupancy"] == 0
    assert exit_res["availableCapacity"] == 900

    # 3. Database assertions
    session = fresh_db.query_one("SELECT * FROM vehicle_sessions WHERE id = ?", (exit_res["sessionId"],))
    assert session["status"] == "EXITED"
    assert session["duration_seconds"] == 1800
    assert session["exit_time"] == "2026-11-21T10:30:00Z"
    assert session["exit_camera_id"] == "palika-exit-1"


def test_t1_f9_02_exit_audit_timestamps(api_client: E2EApiClient, fresh_db: DatabaseAdapter):
    """T1-F9-02: Verification of audit timestamps upon exit completion.
    
    Verifies:
    - exit_time > entry_time
    - exit_camera_id and exit_event_id are populated
    - audit integrity maintained
    """
    plate_text = "MH12DE9876"
    crop_url = PlateCropGenerator.generate_crop_data_url(plate_text, bg_color="white")

    entry_res = api_client.post_anpr_event({
        "facilityId": "palika",
        "cameraId": "palika-entry-1",
        "gateType": "ENTRY",
        "plateNumber": plate_text,
        "confidence": 0.94,
        "plateCropBase64": crop_url,
        "detectedAt": "2026-11-21T09:00:00Z",
    })

    exit_res = api_client.post_anpr_event({
        "facilityId": "palika",
        "cameraId": "palika-exit-1",
        "gateType": "EXIT",
        "plateNumber": plate_text,
        "confidence": 0.94,
        "plateCropBase64": crop_url,
        "detectedAt": "2026-11-21T10:15:00Z",
    })

    assert exit_res["status"] == "ACCEPTED"
    session = fresh_db.query_one("SELECT * FROM vehicle_sessions WHERE id = ?", (exit_res["sessionId"],))
    assert session["entry_time"] == "2026-11-21T09:00:00Z"
    assert session["exit_time"] == "2026-11-21T10:15:00Z"
    assert session["exit_camera_id"] == "palika-exit-1"
    assert session["exit_event_id"] == exit_res["eventId"]
    assert session["duration_seconds"] == 4500  # 1 hr 15 mins


def test_t1_f9_03_reentry_after_prior_session_exited(api_client: E2EApiClient, fresh_db: DatabaseAdapter):
    """T1-F9-03: Re-entry of vehicle after previous session was marked EXITED.
    
    Verifies:
    - Vehicle completes first session (marked EXITED)
    - Vehicle enters again: creates a NEW active session (status INSIDE)
    - Total vehicle_sessions in DB = 2 (1 EXITED, 1 INSIDE)
    - Partial unique index allows new session once prior session is EXITED
    """
    plate_text = "KA01T1111"
    crop_url = PlateCropGenerator.generate_crop_data_url(plate_text, bg_color="white")

    # Session 1: Entry -> Exit
    s1_entry = api_client.post_anpr_event({
        "facilityId": "palika",
        "cameraId": "palika-entry-1",
        "gateType": "ENTRY",
        "plateNumber": plate_text,
        "confidence": 0.95,
        "detectedAt": "2026-11-21T08:00:00Z",
    })
    s1_exit = api_client.post_anpr_event({
        "facilityId": "palika",
        "cameraId": "palika-exit-1",
        "gateType": "EXIT",
        "plateNumber": plate_text,
        "confidence": 0.95,
        "detectedAt": "2026-11-21T09:00:00Z",
    })
    assert s1_exit["status"] == "ACCEPTED"
    assert fresh_db.get_live_occupancy("palika") == 0

    # Clear camera cooldown to allow clean re-entry detection
    api_client.reset_cooldown()

    # Session 2: Re-entry at 14:00:00Z
    s2_entry = api_client.post_anpr_event({
        "facilityId": "palika",
        "cameraId": "palika-entry-1",
        "gateType": "ENTRY",
        "plateNumber": plate_text,
        "confidence": 0.95,
        "detectedAt": "2026-11-21T14:00:00Z",
    })
    assert s2_entry["status_code"] == 201
    assert s2_entry["status"] == "ACCEPTED"
    assert fresh_db.get_live_occupancy("palika") == 1

    # Database assertions
    all_sessions = fresh_db.query(
        "SELECT * FROM vehicle_sessions WHERE facility_id = 'palika' AND plate_number = ? ORDER BY entry_time ASC;",
        (plate_text,),
    )
    assert len(all_sessions) == 2
    assert all_sessions[0]["status"] == "EXITED"
    assert all_sessions[1]["status"] == "INSIDE"


def test_t1_f9_04_parking_tariff_calculation(api_client: E2EApiClient, fresh_db: DatabaseAdapter):
    """T1-F9-04: Exit event calculates parking tariff (2 hours stay).
    
    Verifies:
    - 2 hours stay (7200 seconds) calculates tariff = 40.0 INR
    - vehicle_sessions.calculated_tariff recorded accurately
    """
    plate_text = "UP16BZ8888"
    crop_url = PlateCropGenerator.generate_crop_data_url(plate_text, bg_color="white")

    # Entry at 10:00:00Z
    api_client.post_anpr_event({
        "facilityId": "palika",
        "cameraId": "palika-entry-1",
        "gateType": "ENTRY",
        "plateNumber": plate_text,
        "confidence": 0.95,
        "detectedAt": "2026-11-21T10:00:00Z",
    })

    # Exit at 12:00:00Z (exactly 2 hours)
    res_exit = api_client.post_anpr_event({
        "facilityId": "palika",
        "cameraId": "palika-exit-1",
        "gateType": "EXIT",
        "plateNumber": plate_text,
        "confidence": 0.95,
        "detectedAt": "2026-11-21T12:00:00Z",
    })

    assert res_exit["status"] == "ACCEPTED"
    assert res_exit["durationSeconds"] == 7200
    assert res_exit["calculatedTariff"] == 40.0

    session = fresh_db.query_one("SELECT * FROM vehicle_sessions WHERE id = ?", (res_exit["sessionId"],))
    assert session["calculated_tariff"] == 40.0


def test_t1_f9_05_live_occupancy_endpoint_synchronization(api_client: E2EApiClient, fresh_db: DatabaseAdapter):
    """T1-F9-05: Live occupancy endpoint updates immediately following exit.
    
    Verifies:
    - GET /api/v1/facilities/palika/occupancy returns vehiclesInside: 0, availableCapacity: 900
    - Math matches database SELECT COUNT(*) WHERE status='INSIDE'
    """
    plate_text = "HR26DQ1234"

    # Enter
    api_client.post_anpr_event({
        "facilityId": "palika",
        "cameraId": "palika-entry-1",
        "gateType": "ENTRY",
        "plateNumber": plate_text,
        "confidence": 0.95,
        "detectedAt": "2026-11-21T10:00:00Z",
    })
    occ1 = api_client.get_facility_occupancy("palika")
    assert occ1["vehiclesInside"] == 1
    assert occ1["availableCapacity"] == 899

    # Exit
    api_client.post_anpr_event({
        "facilityId": "palika",
        "cameraId": "palika-exit-1",
        "gateType": "EXIT",
        "plateNumber": plate_text,
        "confidence": 0.95,
        "detectedAt": "2026-11-21T11:00:00Z",
    })

    # Occupancy endpoint check
    occ2 = api_client.get_facility_occupancy("palika")
    assert occ2["vehiclesInside"] == 0
    assert occ2["availableCapacity"] == 900
    assert occ2["occupancyRate"] == 0.0

    db_count = fresh_db.query_one(
        "SELECT COUNT(*) AS c FROM vehicle_sessions WHERE facility_id = 'palika' AND status = 'INSIDE';"
    )["c"]
    assert db_count == 0
