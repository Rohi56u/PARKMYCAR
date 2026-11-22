"""Tier 2 Boundary Tests - Category B8: Extreme Duration Calculations.

Test Cases:
- T2-B8-01: Vehicle exits 1 second after entry (sub-minute duration = 1s)
- T2-B8-02: Vehicle exits at identical second as entry (zero duration = 0s)
- T2-B8-03: Vehicle stays 30 days inside facility (2,592,000s, multi-day tariff)
- T2-B8-04: Vehicle stay crosses midnight UTC boundary (4 hours = 14,400s)
- T2-B8-05: Vehicle abandoned for 365 days identified as OVERSTAY
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import pytest

try:
    from tests.e2e.harness import DatabaseAdapter, E2EApiClient, PlateGenerator
except ImportError:
    from harness import DatabaseAdapter, E2EApiClient, PlateGenerator


def test_t2_b8_01_sub_minute_one_second_stay(api_client: E2EApiClient, fresh_db: DatabaseAdapter):
    """T2-B8-01: Vehicle exits 1 second after entry.

    Expected: durationSeconds = 1, session marked EXITED; occupancy decrements by 1.
    """
    plate = "DL01AB1111"
    t_entry = "2026-11-21T10:00:00Z"
    t_exit = "2026-11-21T10:00:01Z"

    # 1. Entry
    res_entry = api_client.post_anpr_event({
        "facilityId": "palika",
        "cameraId": "palika-entry-1",
        "gateType": "ENTRY",
        "plateNumber": plate,
        "confidence": 0.95,
        "detectedAt": t_entry,
    })
    assert res_entry["status"] == "ACCEPTED"
    assert fresh_db.get_live_occupancy("palika") == 1

    # 2. Exit 1s later
    res_exit = api_client.post_anpr_event({
        "facilityId": "palika",
        "cameraId": "palika-exit-1",
        "gateType": "EXIT",
        "plateNumber": plate,
        "confidence": 0.95,
        "detectedAt": t_exit,
    })
    assert res_exit["status_code"] == 200
    assert res_exit["status"] == "ACCEPTED"
    assert res_exit["durationSeconds"] == 1
    assert res_exit["liveOccupancy"] == 0

    # Authoritative DB Assertions
    session = fresh_db.query_one(
        "SELECT * FROM vehicle_sessions WHERE id = ?;",
        (res_exit["sessionId"],),
    )
    assert session is not None
    assert session["status"] == "EXITED"
    assert session["duration_seconds"] == 1
    assert fresh_db.get_live_occupancy("palika") == 0


def test_t2_b8_02_identical_second_zero_duration(api_client: E2EApiClient, fresh_db: DatabaseAdapter):
    """T2-B8-02: Vehicle exits at identical second as entry (duration = 0s).

    Expected: durationSeconds = 0, no arithmetic underflow; session marked EXITED.
    """
    plate = "DL01AB2222"
    t_same = "2026-11-21T10:00:00Z"

    res_entry = api_client.post_anpr_event({
        "facilityId": "palika",
        "cameraId": "palika-entry-1",
        "gateType": "ENTRY",
        "plateNumber": plate,
        "confidence": 0.95,
        "detectedAt": t_same,
    })
    assert res_entry["status"] == "ACCEPTED"

    res_exit = api_client.post_anpr_event({
        "facilityId": "palika",
        "cameraId": "palika-exit-1",
        "gateType": "EXIT",
        "plateNumber": plate,
        "confidence": 0.95,
        "detectedAt": t_same,
    })
    assert res_exit["status"] == "ACCEPTED"
    assert res_exit["durationSeconds"] == 0

    session = fresh_db.query_one(
        "SELECT * FROM vehicle_sessions WHERE id = ?;",
        (res_exit["sessionId"],),
    )
    assert session["duration_seconds"] == 0
    assert session["status"] == "EXITED"
    assert fresh_db.get_live_occupancy("palika") == 0


def test_t2_b8_03_extended_30_days_overstay(api_client: E2EApiClient, fresh_db: DatabaseAdapter):
    """T2-B8-03: Vehicle stays 30 days inside facility (2,592,000 seconds).

    Expected: durationSeconds = 2592000, multi-day tariff tier applied;
    session transitioned to EXITED.
    """
    plate = "DL01AB3333"
    t_entry = "2026-10-22T10:00:00Z"
    t_exit = "2026-11-21T10:00:00Z"  # 30 days = 30 * 86400 = 2,592,000s

    res_entry = api_client.post_anpr_event({
        "facilityId": "palika",
        "cameraId": "palika-entry-1",
        "gateType": "ENTRY",
        "plateNumber": plate,
        "confidence": 0.95,
        "detectedAt": t_entry,
    })
    assert res_entry["status"] == "ACCEPTED"

    res_exit = api_client.post_anpr_event({
        "facilityId": "palika",
        "cameraId": "palika-exit-1",
        "gateType": "EXIT",
        "plateNumber": plate,
        "confidence": 0.95,
        "detectedAt": t_exit,
    })
    assert res_exit["status"] == "ACCEPTED"
    assert res_exit["durationSeconds"] == 2592000
    assert res_exit["calculatedTariff"] > 50.0

    session = fresh_db.query_one(
        "SELECT * FROM vehicle_sessions WHERE id = ?;",
        (res_exit["sessionId"],),
    )
    assert session["duration_seconds"] == 2592000
    assert session["status"] == "EXITED"
    assert fresh_db.get_live_occupancy("palika") == 0


def test_t2_b8_04_cross_midnight_utc_boundary(api_client: E2EApiClient, fresh_db: DatabaseAdapter):
    """T2-B8-04: Vehicle stay crosses midnight UTC boundary.

    Expected: UTC epoch calculation computes exactly 4 hours (14,400s).
    """
    plate = "DL01AB4444"
    t_entry = "2026-11-21T22:00:00Z"
    t_exit = "2026-11-22T02:00:00Z"  # 4 hours across midnight

    res_entry = api_client.post_anpr_event({
        "facilityId": "palika",
        "cameraId": "palika-entry-1",
        "gateType": "ENTRY",
        "plateNumber": plate,
        "confidence": 0.95,
        "detectedAt": t_entry,
    })
    assert res_entry["status"] == "ACCEPTED"

    res_exit = api_client.post_anpr_event({
        "facilityId": "palika",
        "cameraId": "palika-exit-1",
        "gateType": "EXIT",
        "plateNumber": plate,
        "confidence": 0.95,
        "detectedAt": t_exit,
    })
    assert res_exit["status"] == "ACCEPTED"
    assert res_exit["durationSeconds"] == 14400  # 4 * 3600

    session = fresh_db.query_one(
        "SELECT * FROM vehicle_sessions WHERE id = ?;",
        (res_exit["sessionId"],),
    )
    assert session["duration_seconds"] == 14400
    assert session["status"] == "EXITED"


def test_t2_b8_05_vehicle_abandoned_365_days_overstay(api_client: E2EApiClient, fresh_db: DatabaseAdapter):
    """T2-B8-05: Vehicle abandoned for 365 days (audit query flags OVERSTAY).

    Expected: Background audit query identifies overstay vehicles (entry_time < now - 30 days);
    status can be tagged 'OVERSTAY' while maintaining live occupancy.
    """
    plate = "DL01AB5555"
    one_year_ago = (datetime.now(timezone.utc) - timedelta(days=365)).isoformat()

    # Create vehicle & session directly or via ingest
    fresh_db.execute(
        """
        INSERT INTO vehicles (plate_number, state_code, vehicle_class, first_seen_at, last_seen_at, total_sessions, created_at)
        VALUES (?, 'DL', 'CAR', ?, ?, 1, ?);
        """,
        (plate, one_year_ago, one_year_ago, one_year_ago),
    )
    fresh_db.execute(
        """
        INSERT INTO vehicle_sessions (id, facility_id, plate_number, status, entry_time, created_at, updated_at)
        VALUES ('ses_abandoned', 'palika', ?, 'INSIDE', ?, ?, ?);
        """,
        (plate, one_year_ago, one_year_ago, one_year_ago),
    )
    assert fresh_db.get_live_occupancy("palika") == 1

    # Overstay audit query: identify sessions inside for > 30 days
    cutoff_iso = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
    overstay_candidates = fresh_db.query(
        "SELECT * FROM vehicle_sessions WHERE status = 'INSIDE' AND entry_time < ?;",
        (cutoff_iso,),
    )
    assert len(overstay_candidates) == 1
    assert overstay_candidates[0]["plate_number"] == plate

    # Flag as OVERSTAY
    fresh_db.execute(
        "UPDATE vehicle_sessions SET status = 'OVERSTAY' WHERE id = 'ses_abandoned';"
    )
    session = fresh_db.query_one("SELECT * FROM vehicle_sessions WHERE id = 'ses_abandoned';")
    assert session["status"] == "OVERSTAY"
