"""Tier 2 Boundary Tests - Category B5: Out-of-Order Vehicle Events.

Test Cases:
- T2-B5-01: Exit event for vehicle with NO active entry session (UNMATCHED_EXIT)
- T2-B5-02: Simultaneous duplicate exits prevent double-decrement (underflow protection)
- T2-B5-03: Entry event with stale timestamp older than 48 hours
- T2-B5-04: Exit timestamp earlier than entry timestamp (clock skew negative duration prevention)
- T2-B5-05: Multi-facility independent session scoping (per-facility partial unique index)
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import pytest

try:
    from tests.e2e.harness import DatabaseAdapter, E2EApiClient, PlateGenerator
except ImportError:
    from harness import DatabaseAdapter, E2EApiClient, PlateGenerator


def test_t2_b5_01_exit_without_active_entry_unmatched_exit(api_client: E2EApiClient, fresh_db: DatabaseAdapter):
    """T2-B5-01: Exit event arrives for vehicle with NO active entry session.

    Expected: status='UNMATCHED_EXIT', live occupancy UNCHANGED (remains 0);
    alert recorded in anpr_events.
    """
    plate = "HR26XY9999"
    payload = {
        "facilityId": "palika",
        "cameraId": "palika-exit-1",
        "gateType": "EXIT",
        "plateNumber": plate,
        "confidence": 0.95,
        "detectedAt": "2026-11-21T10:00:00Z",
    }
    res = api_client.post_anpr_event(payload)
    assert res["status"] == "UNMATCHED_EXIT"
    assert res["liveOccupancy"] == 0
    assert not res["success"]

    # Authoritative DB Assertions
    evt = fresh_db.query_one("SELECT * FROM anpr_events WHERE id = ?", (res["eventId"],))
    assert evt is not None
    assert evt["status"] == "UNMATCHED_EXIT"
    assert evt["session_id"] is None

    # Invariant: Unmatched exit never decrements occupancy
    assert fresh_db.get_live_occupancy("palika") == 0


def test_t2_b5_02_simultaneous_duplicate_exits_prevent_double_decrement(api_client: E2EApiClient, fresh_db: DatabaseAdapter):
    """T2-B5-02: Simultaneous exit events for same vehicle from two gates at same millisecond.

    Expected: Event 1 closes active session (occupancy 1 -> 0);
    Event 2 returns UNMATCHED_EXIT (occupancy stays 0, never drops to -1).
    """
    plate = "DL01AB1234"

    # 1. Vehicle enters
    entry_res = api_client.post_anpr_event({
        "facilityId": "palika",
        "cameraId": "palika-entry-1",
        "gateType": "ENTRY",
        "plateNumber": plate,
        "confidence": 0.95,
        "detectedAt": "2026-11-21T10:00:00Z",
    })
    assert entry_res["status"] == "ACCEPTED"
    assert fresh_db.get_live_occupancy("palika") == 1

    # 2. First exit request arrives
    exit1 = api_client.post_anpr_event({
        "facilityId": "palika",
        "cameraId": "palika-exit-1",
        "gateType": "EXIT",
        "plateNumber": plate,
        "confidence": 0.95,
        "detectedAt": "2026-11-21T11:00:00Z",
    })
    assert exit1["status"] == "ACCEPTED"
    assert exit1["liveOccupancy"] == 0
    assert fresh_db.get_live_occupancy("palika") == 0

    # 3. Second simultaneous exit request arrives for already exited vehicle
    exit2 = api_client.post_anpr_event({
        "facilityId": "palika",
        "cameraId": "palika-exit-2",
        "gateType": "EXIT",
        "plateNumber": plate,
        "confidence": 0.95,
        "detectedAt": "2026-11-21T11:00:00Z",
    })
    assert exit2["status"] == "UNMATCHED_EXIT"
    assert exit2["liveOccupancy"] == 0

    # Authoritative DB Assertions: occupancy must be strictly 0, never negative
    inside_count = fresh_db.query_one(
        "SELECT COUNT(*) AS c FROM vehicle_sessions WHERE facility_id = 'palika' AND status = 'INSIDE';"
    )["c"]
    assert inside_count == 0
    assert fresh_db.get_live_occupancy("palika") == 0


def test_t2_b5_03_entry_event_with_stale_timestamp(api_client: E2EApiClient, fresh_db: DatabaseAdapter):
    """T2-B5-03: Entry event with stale timestamp older than 48 hours.

    Expected: Audit timestamps reflect capture time accurately; database integrity preserved.
    """
    plate = "DL01AB5555"
    stale_dt = (datetime.now(timezone.utc) - timedelta(hours=50)).isoformat()

    payload = {
        "facilityId": "palika",
        "cameraId": "palika-entry-1",
        "gateType": "ENTRY",
        "plateNumber": plate,
        "confidence": 0.95,
        "detectedAt": stale_dt,
    }
    res = api_client.post_anpr_event(payload)

    # Ingests with full audit trail
    assert res["status"] in ("ACCEPTED", "STALE_TIMESTAMP")

    evt = fresh_db.query_one("SELECT * FROM anpr_events WHERE id = ?", (res["eventId"],))
    assert evt is not None
    assert evt["detected_at"] == stale_dt

    # If accepted, session entry_time matches detected_at
    if res["status"] == "ACCEPTED":
        session = fresh_db.get_active_session("palika", plate)
        assert session is not None
        assert session["entry_time"] == stale_dt


def test_t2_b5_04_exit_time_earlier_than_entry_negative_duration_prevention(api_client: E2EApiClient, fresh_db: DatabaseAdapter):
    """T2-B5-04: Exit timestamp earlier than entry timestamp (clock skew).

    Expected: Duration is clamped to 0 (never negative); session duration >= 0.
    """
    plate = "MH12DE1432"

    # 1. Entry at 10:00:00
    entry_res = api_client.post_anpr_event({
        "facilityId": "palika",
        "cameraId": "palika-entry-1",
        "gateType": "ENTRY",
        "plateNumber": plate,
        "confidence": 0.95,
        "detectedAt": "2026-11-21T10:00:00Z",
    })
    assert entry_res["status"] == "ACCEPTED"

    # 2. Exit with clock-skewed timestamp at 09:00:00 (1 hour earlier!)
    exit_res = api_client.post_anpr_event({
        "facilityId": "palika",
        "cameraId": "palika-exit-1",
        "gateType": "EXIT",
        "plateNumber": plate,
        "confidence": 0.95,
        "detectedAt": "2026-11-21T09:00:00Z",
    })
    assert exit_res["status"] == "ACCEPTED"

    # Crucial Invariant: duration cannot be negative!
    assert exit_res["durationSeconds"] >= 0
    assert exit_res["durationSeconds"] == 0

    session = fresh_db.query_one("SELECT * FROM vehicle_sessions WHERE id = ?", (exit_res["sessionId"],))
    assert session is not None
    assert session["status"] == "EXITED"
    assert session["duration_seconds"] >= 0
    assert session["duration_seconds"] == 0


def test_t2_b5_05_cross_facility_independent_session_scoping(api_client: E2EApiClient, fresh_db: DatabaseAdapter):
    """T2-B5-05: Vehicle recorded INSIDE in Facility A enters Facility B without exiting A.

    Expected: Independent facility scoping: both sessions active;
    Partial unique index UNIQUE(facility_id, plate_number) WHERE status='INSIDE'
    allows simultaneous entries in different facilities.
    """
    plate = "KA05MB9999"

    # 1. Entry at palika
    res1 = api_client.post_anpr_event({
        "facilityId": "palika",
        "cameraId": "palika-entry-1",
        "gateType": "ENTRY",
        "plateNumber": plate,
        "confidence": 0.95,
        "detectedAt": "2026-11-21T10:00:00Z",
    })
    assert res1["status_code"] == 201
    assert res1["status"] == "ACCEPTED"
    assert fresh_db.get_live_occupancy("palika") == 1

    # 2. Entry at cp-west (different facility) for same vehicle
    res2 = api_client.post_anpr_event({
        "facilityId": "cp-west",
        "cameraId": "cp-west-entry-1",
        "gateType": "ENTRY",
        "plateNumber": plate,
        "confidence": 0.95,
        "detectedAt": "2026-11-21T10:15:00Z",
    })
    assert res2["status_code"] == 201
    assert res2["status"] == "ACCEPTED"
    assert fresh_db.get_live_occupancy("cp-west") == 1

    # Authoritative DB Assertions: both sessions exist with status='INSIDE'
    ses_palika = fresh_db.get_active_session("palika", plate)
    ses_cp_west = fresh_db.get_active_session("cp-west", plate)

    assert ses_palika is not None and ses_palika["facility_id"] == "palika"
    assert ses_cp_west is not None and ses_cp_west["facility_id"] == "cp-west"
    assert ses_palika["status"] == "INSIDE"
    assert ses_cp_west["status"] == "INSIDE"
    assert ses_palika["id"] != ses_cp_west["id"]

    assert fresh_db.get_live_occupancy("palika") == 1
    assert fresh_db.get_live_occupancy("cp-west") == 1
