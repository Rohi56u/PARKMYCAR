"""Tier 2 Boundary Tests - Category B9: Sudden Camera Dropout While Vehicle in Gate Zone.

Test Cases:
- T2-B9-01: Entry camera drops offline immediately after detection (atomic session preserved)
- T2-B9-02: Exit camera drops offline mid-frame (no corrupt exit, session remains INSIDE)
- T2-B9-03: Rapid camera flapping ONLINE/OFFLINE handled without pipeline instability
- T2-B9-04: Camera offline for extended period flushes 15 buffered events in sequence
- T2-B9-05: Facility-wide power outage / all cameras drop offline simultaneously
"""

from __future__ import annotations

import pytest

try:
    from tests.e2e.harness import DatabaseAdapter, E2EApiClient, PlateGenerator
except ImportError:
    from harness import DatabaseAdapter, E2EApiClient, PlateGenerator


def test_t2_b9_01_entry_camera_drop_after_detection(api_client: E2EApiClient, fresh_db: DatabaseAdapter):
    """T2-B9-01: Entry camera drops offline immediately after plate detection.

    Expected: Database commit ensures session is recorded; subsequent camera dropout
    does not revert or corrupt the active INSIDE session.
    """
    plate = "DL01AB1234"

    # Ingest detection
    res = api_client.post_anpr_event({
        "facilityId": "palika",
        "cameraId": "palika-entry-1",
        "gateType": "ENTRY",
        "plateNumber": plate,
        "confidence": 0.95,
    })
    assert res["status"] == "ACCEPTED"
    assert fresh_db.get_live_occupancy("palika") == 1

    # Camera immediately drops offline
    hb_res = api_client.post_camera_heartbeat({
        "cameraId": "palika-entry-1",
        "status": "OFFLINE",
        "fps": 0.0,
    })
    assert hb_res["status"] == "OFFLINE"

    # Authoritative DB Assertions: camera is OFFLINE, session remains INSIDE
    cam = fresh_db.query_one("SELECT * FROM parking_cameras WHERE id = 'palika-entry-1';")
    assert cam["status"] == "OFFLINE"

    session = fresh_db.get_active_session("palika", plate)
    assert session is not None
    assert session["status"] == "INSIDE"
    assert fresh_db.get_live_occupancy("palika") == 1


def test_t2_b9_02_exit_camera_drop_mid_frame(api_client: E2EApiClient, fresh_db: DatabaseAdapter):
    """T2-B9-02: Exit camera drops offline mid-frame while vehicle is passing barrier.

    Expected: No exit event is emitted; active session remains INSIDE;
    occupancy is NOT decremented.
    """
    plate = "MH12DE1432"

    # Vehicle entered and parked
    api_client.post_anpr_event({
        "facilityId": "palika",
        "cameraId": "palika-entry-1",
        "gateType": "ENTRY",
        "plateNumber": plate,
        "confidence": 0.95,
    })
    assert fresh_db.get_live_occupancy("palika") == 1

    # Exit camera connection fails mid-transit (heartbeat stops, camera marked OFFLINE)
    api_client.post_camera_heartbeat({
        "cameraId": "palika-exit-1",
        "status": "OFFLINE",
        "fps": 0.0,
    })

    # Invariant: Disconnected exit camera must NEVER alter active session or decrement occupancy!
    session = fresh_db.get_active_session("palika", plate)
    assert session is not None
    assert session["status"] == "INSIDE"
    assert fresh_db.get_live_occupancy("palika") == 1


def test_t2_b9_03_rapid_camera_flapping_stability(api_client: E2EApiClient, fresh_db: DatabaseAdapter):
    """T2-B9-03: Camera connection flaps rapidly between ONLINE and OFFLINE.

    Expected: Telemetry updates camera record; ANPR state and active sessions remain stable.
    """
    plate = "KA05MB9999"
    api_client.post_anpr_event({
        "facilityId": "palika",
        "cameraId": "palika-entry-1",
        "gateType": "ENTRY",
        "plateNumber": plate,
        "confidence": 0.95,
    })

    # Rapid flapping 5 cycles (ONLINE -> OFFLINE -> ONLINE)
    for i in range(5):
        api_client.post_camera_heartbeat({"cameraId": "palika-entry-1", "status": "OFFLINE", "fps": 0.0})
        api_client.post_camera_heartbeat({"cameraId": "palika-entry-1", "status": "ONLINE", "fps": 25.0})

    # Assert active session is intact
    assert fresh_db.get_live_occupancy("palika") == 1
    session = fresh_db.get_active_session("palika", plate)
    assert session is not None
    assert session["status"] == "INSIDE"


def test_t2_b9_04_camera_buffered_events_burst_flush(api_client: E2EApiClient, fresh_db: DatabaseAdapter):
    """T2-B9-04: Camera offline for 2 hours flushes 15 buffered offline events upon reconnection.

    Expected: All 15 events ingested in sequence; 15 active INSIDE sessions recorded.
    """
    # Camera offline
    api_client.post_camera_heartbeat({"cameraId": "palika-entry-1", "status": "OFFLINE", "fps": 0.0})

    # Camera reconnects and flushes 15 buffered events
    api_client.post_camera_heartbeat({"cameraId": "palika-entry-1", "status": "ONLINE", "fps": 25.0})

    plates = [f"DL01FL{i:04d}" for i in range(1, 16)]
    for idx, plate in enumerate(plates, 1):
        res = api_client.post_anpr_event({
            "facilityId": "palika",
            "cameraId": "palika-entry-1",
            "gateType": "ENTRY",
            "plateNumber": plate,
            "confidence": 0.95,
            "detectedAt": f"2026-11-21T10:{idx:02d}:00Z",
        })
        assert res["status"] == "ACCEPTED"
        assert res["liveOccupancy"] == idx

    # Authoritative DB Assertions
    count = fresh_db.query_one(
        "SELECT COUNT(*) AS c FROM vehicle_sessions WHERE facility_id = 'palika' AND status = 'INSIDE';"
    )["c"]
    assert count == 15
    assert fresh_db.get_live_occupancy("palika") == 15


def test_t2_b9_05_facility_wide_camera_blackout(api_client: E2EApiClient, fresh_db: DatabaseAdapter):
    """T2-B9-05: Facility-wide power outage drops all cameras offline simultaneously.

    Expected: All cameras marked OFFLINE; all active sessions and live occupancy preserved.
    """
    # Seed 5 parked vehicles
    plates = ["DL01AB0001", "DL01AB0002", "DL01AB0003", "DL01AB0004", "DL01AB0005"]
    for p in plates:
        api_client.post_anpr_event({
            "facilityId": "palika",
            "cameraId": "palika-entry-1",
            "gateType": "ENTRY",
            "plateNumber": p,
            "confidence": 0.95,
        })
    assert fresh_db.get_live_occupancy("palika") == 5

    # Power outage: all cameras drop offline
    cameras = ["palika-entry-1", "palika-entry-2", "palika-exit-1", "palika-exit-2", "palika-sim-entry"]
    for cam in cameras:
        api_client.post_camera_heartbeat({"cameraId": cam, "status": "OFFLINE", "fps": 0.0})

    # Verify all cameras are OFFLINE
    for cam in cameras:
        rec = fresh_db.query_one("SELECT status FROM parking_cameras WHERE id = ?;", (cam,))
        if rec:
            assert rec["status"] == "OFFLINE"

    # Core Invariant: Total blackout never modifies vehicle sessions or occupancy!
    assert fresh_db.get_live_occupancy("palika") == 5
    inside_count = fresh_db.query_one(
        "SELECT COUNT(*) AS c FROM vehicle_sessions WHERE facility_id = 'palika' AND status = 'INSIDE';"
    )["c"]
    assert inside_count == 5
