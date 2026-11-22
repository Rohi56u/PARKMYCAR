"""Tier 2 Boundary Tests - Category B7: Zero Capacity / Facility Full Limit Boundary.

Test Cases:
- T2-B7-01: Entry event when liveOccupancy reaches total capacity (900/900 saturated -> state 'FULL')
- T2-B7-02: Facility configured with totalCapacity = 0 handled without division-by-zero
- T2-B7-03: Exit event received when liveOccupancy = 0 (underflow protection prevents negative occupancy)
- T2-B7-04: Occupancy rate precision rounding at boundary (899 / 900 -> 99.89%)
- T2-B7-05: Facility observation transition from 'LIMITED' to 'FULL' at threshold crossing
"""

from __future__ import annotations

import json
import pytest

try:
    from tests.e2e.harness import DatabaseAdapter, E2EApiClient, PlateGenerator
except ImportError:
    from harness import DatabaseAdapter, E2EApiClient, PlateGenerator


def _bulk_seed_facility(fresh_db: DatabaseAdapter, facility_id: str, count: int, prefix: str = "DL01"):
    """Helper to bulk-seed vehicle records and active sessions."""
    vehicles = [
        (f"{prefix}X{i:04d}", prefix[:2], "CAR", "2026-11-21T00:00:00Z", "2026-11-21T00:00:00Z", 1, "2026-11-21T00:00:00Z")
        for i in range(1, count + 1)
    ]
    fresh_db.executemany(
        """
        INSERT OR IGNORE INTO vehicles (plate_number, state_code, vehicle_class, first_seen_at, last_seen_at, total_sessions, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?);
        """,
        vehicles,
    )

    sessions = [
        (f"bulk_ses_{i:04d}", facility_id, f"{prefix}X{i:04d}", "INSIDE", f"evt_{i:04d}", "palika-entry-1", "2026-11-21T08:00:00Z", "VERIFIED", "2026-11-21T08:00:00Z", "2026-11-21T08:00:00Z")
        for i in range(1, count + 1)
    ]
    fresh_db.executemany(
        """
        INSERT INTO vehicle_sessions
        (id, facility_id, plate_number, status, entry_event_id, entry_camera_id, entry_time, review_status, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """,
        sessions,
    )


def test_t2_b7_01_full_capacity_900_saturation(api_client: E2EApiClient, fresh_db: DatabaseAdapter):
    """T2-B7-01: Entry event when liveOccupancy reaches 900 (Palika at 100% capacity).

    Expected: liveOccupancy = 900, availableCapacity = 0;
    observation state transitions to 'FULL'.
    """
    # 1. Bulk seed 899 vehicles inside Palika
    _bulk_seed_facility(fresh_db, "palika", 899, prefix="DL01")
    assert fresh_db.get_live_occupancy("palika") == 899
    assert fresh_db.get_available_capacity("palika") == 1

    # 2. 900th vehicle enters
    plate_900 = "DL01ZZ9999"
    res = api_client.post_anpr_event({
        "facilityId": "palika",
        "cameraId": "palika-entry-1",
        "gateType": "ENTRY",
        "plateNumber": plate_900,
        "confidence": 0.95,
    })
    assert res["status_code"] in (200, 201)
    assert res["liveOccupancy"] == 900
    assert res["availableCapacity"] == 0

    # Authoritative DB Assertions
    occ = api_client.get_facility_occupancy("palika")
    assert occ["vehiclesInside"] == 900
    assert occ["availableCapacity"] == 0
    assert occ["occupancyRate"] == 100.0

    # Observations table auto-sync set to FULL
    latest_obs = fresh_db.query_one(
        "SELECT * FROM observations WHERE facility_id = 'palika' ORDER BY observed_at DESC LIMIT 1;"
    )
    assert latest_obs is not None
    assert latest_obs["state"] == "FULL"
    assert latest_obs["evidence_class"] == "OPERATOR_REPORTED"


def test_t2_b7_02_zero_capacity_facility_handling(api_client: E2EApiClient, fresh_db: DatabaseAdapter):
    """T2-B7-02: Facility configured with totalCapacity = 0 handled without division-by-zero.

    Expected: No crash or zero division; availableCapacity = 0; observation state is handled cleanly.
    """
    # Create or update facility with capacity 0
    payload = json.dumps({"name": "Zero Cap Facility", "totalCapacity": 0, "capacity": 0})
    fresh_db.execute(
        """
        INSERT INTO facilities (id, name, lat, lng, active, version, payload)
        VALUES ('zero-cap-fac', 'Zero Cap Facility', 28.63, 77.21, 1, 1, ?);
        """,
        (payload,),
    )

    occ = api_client.get_facility_occupancy("zero-cap-fac")
    assert occ["totalCapacity"] == 0
    assert occ["vehiclesInside"] == 0
    assert occ["availableCapacity"] == 0
    assert occ["occupancyRate"] == 0.0


def test_t2_b7_03_exit_at_zero_occupancy_underflow_protection(api_client: E2EApiClient, fresh_db: DatabaseAdapter):
    """T2-B7-03: Exit event received when liveOccupancy == 0.

    Expected: Returns UNMATCHED_EXIT; liveOccupancy remains 0 (underflow protection prevents negative occupancy).
    """
    assert fresh_db.get_live_occupancy("palika") == 0

    res = api_client.post_anpr_event({
        "facilityId": "palika",
        "cameraId": "palika-exit-1",
        "gateType": "EXIT",
        "plateNumber": "DL01AB9999",
        "confidence": 0.95,
    })
    assert res["status"] == "UNMATCHED_EXIT"
    assert res["liveOccupancy"] == 0
    assert res["availableCapacity"] == 900

    # Authoritative DB Assertions: occupancy never negative
    db_occ = fresh_db.get_live_occupancy("palika")
    assert db_occ == 0
    assert fresh_db.get_available_capacity("palika") == 900


def test_t2_b7_04_occupancy_percentage_precision_rounding(api_client: E2EApiClient, fresh_db: DatabaseAdapter):
    """T2-B7-04: Occupancy percentage calculation at boundary (899 / 900 vehicles).

    Expected: 899 / 900 * 100 = 99.8888... -> round to 2 decimals = 99.89%.
    """
    _bulk_seed_facility(fresh_db, "palika", 899, prefix="MH12")

    occ = api_client.get_facility_occupancy("palika")
    assert occ["totalCapacity"] == 900
    assert occ["vehiclesInside"] == 899
    assert occ["availableCapacity"] == 1
    assert occ["occupancyRate"] == 99.89


def test_t2_b7_05_observation_transition_limited_to_full(api_client: E2EApiClient, fresh_db: DatabaseAdapter):
    """T2-B7-05: Observation transition from 'LIMITED' to 'FULL' when saturation threshold is crossed.

    Expected: At 899 vehicles (>=80%), observation state is 'LIMITED'.
    900th vehicle entry transitions state synchronously to 'FULL'.
    """
    # Seed 898 vehicles
    _bulk_seed_facility(fresh_db, "palika", 898, prefix="KA05")

    # Ingest 899th vehicle -> triggers LIMITED observation sync (899/900 = 99.8% >= 80%)
    res_899 = api_client.post_anpr_event({
        "facilityId": "palika",
        "cameraId": "palika-entry-1",
        "gateType": "ENTRY",
        "plateNumber": "KA05MB8888",
        "confidence": 0.95,
    })
    assert res_899["status"] == "ACCEPTED"
    assert res_899["liveOccupancy"] == 899

    obs_899 = fresh_db.query_one(
        "SELECT * FROM observations WHERE facility_id = 'palika' ORDER BY observed_at DESC LIMIT 1;"
    )
    assert obs_899 is not None
    assert obs_899["state"] == "LIMITED"

    # Ingest 900th vehicle -> reaches 100% saturation, triggers FULL
    res_900 = api_client.post_anpr_event({
        "facilityId": "palika",
        "cameraId": "palika-entry-1",
        "gateType": "ENTRY",
        "plateNumber": "KA05MB9999",
        "confidence": 0.95,
    })
    assert res_900["status"] == "ACCEPTED"
    assert res_900["liveOccupancy"] == 900
    assert res_900["availableCapacity"] == 0

    obs_900 = fresh_db.query_one(
        "SELECT * FROM observations WHERE facility_id = 'palika' ORDER BY observed_at DESC LIMIT 1;"
    )
    assert obs_900 is not None
    assert obs_900["state"] == "FULL"
