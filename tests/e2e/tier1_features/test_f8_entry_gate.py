"""Tier 1 Feature 8: Vehicle Entry Session Creation & Authoritative Occupancy Increment (T1-F8-01 .. T1-F8-05).

Validates:
- T1-F8-01: Valid vehicle entry records INSIDE session and increments liveOccupancy
- T1-F8-02: Sequential valid entries of 3 distinct vehicles reflect exact mathematical count
- T1-F8-03: First-time vehicle entry creates historical registry row in vehicles table
- T1-F8-04: Duplicate entry attempt for vehicle already INSIDE blocked by partial unique constraint
- T1-F8-05: Live occupancy synchronizes synchronously to observations table for public discovery
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


def test_t1_f8_01_valid_entry_creates_inside_session(api_client: E2EApiClient, fresh_db: DatabaseAdapter):
    """T1-F8-01: Valid entry event creates active session and increments occupancy.
    
    Verifies:
    - HTTP 201 with status="ACCEPTED"
    - liveOccupancy=1, availableCapacity=899
    - vehicle_sessions has 1 row with status='INSIDE', entry_time populated
    - liveOccupancy strictly equals SELECT COUNT(*) WHERE status='INSIDE'
    """
    plate_text = "DL01AB1234"
    crop_url = PlateCropGenerator.generate_crop_data_url(plate_text, bg_color="white")

    res = api_client.post_anpr_event({
        "facilityId": "palika",
        "cameraId": "palika-entry-1",
        "gateType": "ENTRY",
        "plateNumber": plate_text,
        "confidence": 0.95,
        "plateCropBase64": crop_url,
        "detectedAt": "2026-11-21T10:00:00Z",
    })

    assert res["status_code"] == 201
    assert res["success"] is True
    assert res["status"] == "ACCEPTED"
    assert res["liveOccupancy"] == 1
    assert res["availableCapacity"] == 899
    assert "sessionId" in res

    session = fresh_db.query_one("SELECT * FROM vehicle_sessions WHERE id = ?", (res["sessionId"],))
    assert session is not None
    assert session["facility_id"] == "palika"
    assert session["plate_number"] == plate_text
    assert session["status"] == "INSIDE"
    assert session["entry_time"] == "2026-11-21T10:00:00Z"

    # Invariant: liveOccupancy derived strictly from database
    assert fresh_db.get_live_occupancy("palika") == 1
    assert fresh_db.get_available_capacity("palika") == 899


def test_t1_f8_02_sequential_entries_exact_occupancy(api_client: E2EApiClient, fresh_db: DatabaseAdapter):
    """T1-F8-02: Sequential valid entries of 3 distinct vehicles.
    
    Verifies:
    - Entries return liveOccupancy 1, 2, then 3
    - Database query SELECT COUNT(*) WHERE status='INSIDE' equals exactly 3
    """
    plates = ["DL01AB1111", "MH12DE2222", "KA01T3333"]

    for idx, plate in enumerate(plates, start=1):
        crop_url = PlateCropGenerator.generate_crop_data_url(plate, bg_color="white")
        res = api_client.post_anpr_event({
            "facilityId": "palika",
            "cameraId": "palika-entry-1",
            "gateType": "ENTRY",
            "plateNumber": plate,
            "confidence": 0.94,
            "plateCropBase64": crop_url,
        })
        assert res["status_code"] == 201
        assert res["liveOccupancy"] == idx
        assert res["availableCapacity"] == 900 - idx

    # Invariant assertion
    db_count = fresh_db.query_one(
        "SELECT COUNT(*) AS c FROM vehicle_sessions WHERE facility_id = 'palika' AND status = 'INSIDE';"
    )["c"]
    assert db_count == 3


def test_t1_f8_03_first_time_entry_populates_vehicles_table(api_client: E2EApiClient, fresh_db: DatabaseAdapter):
    """T1-F8-03: First-time vehicle entry creates record in vehicles table.
    
    Verifies:
    - vehicles record created with total_sessions = 1
    - first_seen_at and last_seen_at populated
    """
    plate_text = "HR26DQ9999"
    crop_url = PlateCropGenerator.generate_crop_data_url(plate_text, bg_color="white")

    res = api_client.post_anpr_event({
        "facilityId": "palika",
        "cameraId": "palika-entry-1",
        "gateType": "ENTRY",
        "plateNumber": plate_text,
        "confidence": 0.96,
        "plateCropBase64": crop_url,
        "detectedAt": "2026-11-21T10:15:00Z",
    })
    assert res["status_code"] == 201

    vehicle = fresh_db.query_one("SELECT * FROM vehicles WHERE plate_number = ?", (plate_text,))
    assert vehicle is not None
    assert vehicle["plate_number"] == plate_text
    assert vehicle["total_sessions"] == 1
    assert vehicle["first_seen_at"] == "2026-11-21T10:15:00Z"
    assert vehicle["last_seen_at"] == "2026-11-21T10:15:00Z"


def test_t1_f8_04_duplicate_entry_prevention(api_client: E2EApiClient, fresh_db: DatabaseAdapter):
    """T1-F8-04: Duplicate entry attempt for vehicle already INSIDE.
    
    Verifies:
    - Attempting second entry for currently parked vehicle is blocked
    - liveOccupancy does not double count
    - Active sessions count for plate remains strictly 1
    """
    plate_text = "DL01AB5555"
    crop_url = PlateCropGenerator.generate_crop_data_url(plate_text, bg_color="white")

    # Initial entry
    res1 = api_client.post_anpr_event({
        "facilityId": "palika",
        "cameraId": "palika-entry-1",
        "gateType": "ENTRY",
        "plateNumber": plate_text,
        "confidence": 0.95,
        "plateCropBase64": crop_url,
    })
    assert res1["status"] == "ACCEPTED"
    assert res1["liveOccupancy"] == 1

    # Clear camera debouncing cache to simulate arrival at a different gate or post-cooldown
    api_client.reset_cooldown()

    # Second entry attempt while still INSIDE
    res2 = api_client.post_anpr_event({
        "facilityId": "palika",
        "cameraId": "palika-entry-2",
        "gateType": "ENTRY",
        "plateNumber": plate_text,
        "confidence": 0.95,
        "plateCropBase64": crop_url,
    })

    assert res2["success"] is False
    assert res2["status"] == "DUPLICATE_ENTRY"
    assert res2["liveOccupancy"] == 1

    # Invariant: partial unique constraint allows only 1 INSIDE session per vehicle per facility
    active_count = fresh_db.query_one(
        """
        SELECT COUNT(*) AS c FROM vehicle_sessions
        WHERE facility_id = 'palika' AND plate_number = ? AND status = 'INSIDE';
        """,
        (plate_text,),
    )["c"]
    assert active_count == 1


def test_t1_f8_05_facility_occupancy_syncs_to_observations(api_client: E2EApiClient, fresh_db: DatabaseAdapter):
    """T1-F8-05: Facility occupancy syncs to observations table for live driver discovery.
    
    Verifies:
    - New row inserted into observations table
    - state = 'AVAILABLE' (occupancy 1/900 < 80%)
    - evidence_class = 'OPERATOR_REPORTED'
    """
    plate_text = "UP16BZ1234"
    crop_url = PlateCropGenerator.generate_crop_data_url(plate_text, bg_color="white")

    res = api_client.post_anpr_event({
        "facilityId": "palika",
        "cameraId": "palika-entry-1",
        "gateType": "ENTRY",
        "plateNumber": plate_text,
        "confidence": 0.95,
        "plateCropBase64": crop_url,
    })
    assert res["status_code"] == 201

    # Check observations table
    obs = fresh_db.query_one(
        "SELECT * FROM observations WHERE facility_id = 'palika' ORDER BY observed_at DESC LIMIT 1;"
    )
    assert obs is not None
    assert obs["state"] == "AVAILABLE"
    assert obs["evidence_class"] == "OPERATOR_REPORTED"
    assert obs["source"] == "ANPR_AUTO_SYNC"
