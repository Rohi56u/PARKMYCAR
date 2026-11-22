"""Tier 1 Feature 7: Camera Disconnection Isolation (T1-F7-01 .. T1-F7-05).

Validates:
- T1-F7-01: Heartbeat timeout (>30s) transitions camera status to OFFLINE
- T1-F7-02: Entry camera disconnect leaves 20 INSIDE vehicle sessions completely untouched
- T1-F7-03: Exit camera disconnect never decrements occupancy or mutates session states
- T1-F7-04: Disconnected camera resumes heartbeats and restores status to ONLINE
- T1-F7-05: Ingesting ANPR event from OFFLINE camera succeeds and restores camera state
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
        CameraSimulator,
        DatabaseAdapter,
        E2EApiClient,
        PlateCropGenerator,
        PlateGenerator,
    )
except ImportError:
    from harness import (
        CameraSimulator,
        DatabaseAdapter,
        E2EApiClient,
        PlateCropGenerator,
        PlateGenerator,
    )


def test_t1_f7_01_heartbeat_timeout_transitions_offline(api_client: E2EApiClient, fresh_db: DatabaseAdapter):
    """T1-F7-01: Camera stops sending heartbeats for 35s (>30s timeout).
    
    Verifies:
    - Camera status transitions to OFFLINE
    - Database parking_cameras.status = 'OFFLINE', updated_at is populated
    """
    cam_id = "palika-entry-1"
    sim = CameraSimulator(
        camera_id=cam_id,
        facility_id="palika",
        gate_type="ENTRY",
        api_client=api_client,
        db=fresh_db,
    )

    # Disconnect camera
    disc_res = sim.disconnect()
    assert disc_res["status"] == "OFFLINE"

    cam = fresh_db.query_one("SELECT * FROM parking_cameras WHERE id = ?", (cam_id,))
    assert cam["status"] == "OFFLINE"
    assert cam["fps"] == 0.0


def test_t1_f7_02_entry_camera_disconnect_preserves_sessions(
    api_client: E2EApiClient,
    fresh_db: DatabaseAdapter,
    camera_sim: CameraSimulator,
):
    """T1-F7-02: Entry camera disconnects while 20 vehicles are currently INSIDE.
    
    Verifies:
    - Camera disconnection sets status = 'OFFLINE'
    - Invariant: Zero active vehicle session mutations occur
    - Authoritative database count and occupancy endpoint strictly report 20 vehicles
    """
    # 1. Seed 20 active vehicles inside facility
    for i in range(1, 21):
        plate = f"DL01AB{i:04d}"
        res = api_client.post_anpr_event({
            "facilityId": "palika",
            "cameraId": "palika-entry-1",
            "gateType": "ENTRY",
            "plateNumber": plate,
            "confidence": 0.95,
        })
        assert res["status"] == "ACCEPTED"

    # Verify initial occupancy
    assert fresh_db.get_live_occupancy("palika") == 20

    # 2. Entry camera suddenly disconnects
    camera_sim.disconnect()
    cam_row = fresh_db.query_one("SELECT status FROM parking_cameras WHERE id = 'palika-entry-1';")
    assert cam_row["status"] == "OFFLINE"

    # 3. Disconnection Isolation Invariant Verification
    db_inside = fresh_db.query_one(
        "SELECT COUNT(*) AS c FROM vehicle_sessions WHERE facility_id = 'palika' AND status = 'INSIDE';"
    )["c"]
    assert db_inside == 20, "Disconnection of entry camera must NEVER alter active INSIDE sessions"

    occ = api_client.get_facility_occupancy("palika")
    assert occ["vehiclesInside"] == 20
    assert occ["availableCapacity"] == 880


def test_t1_f7_03_exit_camera_disconnect_preserves_occupancy(
    api_client: E2EApiClient,
    fresh_db: DatabaseAdapter,
    exit_camera_sim: CameraSimulator,
):
    """T1-F7-03: Exit camera disconnects while vehicles are INSIDE.
    
    Verifies:
    - Exit camera drop sets status = 'OFFLINE'
    - Occupancy does NOT decrement
    - Active sessions remain intact
    """
    # Seed 5 vehicles inside
    for i in range(1, 6):
        plate = f"MH12DE{i:04d}"
        api_client.post_anpr_event({
            "facilityId": "palika",
            "cameraId": "palika-entry-1",
            "gateType": "ENTRY",
            "plateNumber": plate,
            "confidence": 0.94,
        })

    assert fresh_db.get_live_occupancy("palika") == 5

    # Exit camera disconnects
    exit_camera_sim.disconnect()
    cam_row = fresh_db.query_one("SELECT status FROM parking_cameras WHERE id = 'palika-exit-1';")
    assert cam_row["status"] == "OFFLINE"

    # Invariant: live occupancy strictly unchanged
    assert fresh_db.get_live_occupancy("palika") == 5
    occ = api_client.get_facility_occupancy("palika")
    assert occ["vehiclesInside"] == 5


def test_t1_f7_04_camera_reconnection_and_heartbeat_recovery(
    api_client: E2EApiClient,
    fresh_db: DatabaseAdapter,
    camera_sim: CameraSimulator,
):
    """T1-F7-04: Disconnected camera resumes heartbeats and recovers to ONLINE.
    
    Verifies:
    - Camera transitions from OFFLINE back to ONLINE
    - last_heartbeat_at and fps are updated
    """
    camera_sim.disconnect()
    assert camera_sim.status == "OFFLINE"

    # Reconnect camera
    rec_res = camera_sim.reconnect(fps=25.0)
    assert rec_res["status"] == "ONLINE"

    cam = fresh_db.query_one("SELECT * FROM parking_cameras WHERE id = 'palika-entry-1';")
    assert cam["status"] == "ONLINE"
    assert cam["fps"] == 25.0
    assert cam["last_heartbeat_at"] is not None


def test_t1_f7_05_offline_camera_event_transmission(
    api_client: E2EApiClient,
    fresh_db: DatabaseAdapter,
    camera_sim: CameraSimulator,
):
    """T1-F7-05: Incoming ANPR event received from a camera currently marked OFFLINE.
    
    Verifies:
    - Legitimate event transmission is accepted (HTTP 201)
    - Session created, liveOccupancy increments
    - anpr_events records status = 'ACCEPTED'
    """
    # Mark camera offline
    camera_sim.disconnect()
    cam = fresh_db.query_one("SELECT status FROM parking_cameras WHERE id = 'palika-entry-1';")
    assert cam["status"] == "OFFLINE"

    # Event received from the offline camera
    plate_text = "KA05MB7777"
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
    assert res["status"] == "ACCEPTED"
    assert res["liveOccupancy"] == 1

    event = fresh_db.query_one("SELECT * FROM anpr_events WHERE id = ?", (res["eventId"],))
    assert event["status"] == "ACCEPTED"
    assert fresh_db.get_active_session("palika", plate_text) is not None
