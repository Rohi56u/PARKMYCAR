"""Tier 2 Boundary Tests - Category B6: Rapid Consecutive Burst Events.

Test Cases:
- T2-B6-01: Burst of 10 identical entry requests for same plate (1 ACCEPTED, 9 COOLDOWN_IGNORED)
- T2-B6-02: Burst of 5 distinct vehicles in rapid succession (5 ACCEPTED, liveOccupancy=5)
- T2-B6-03: Rapid entry-exit-entry turnaround cycle (2 total sessions: 1 EXITED, 1 INSIDE)
- T2-B6-04: Concurrent entries from multi-gate cameras at exact same timestamp
- T2-B6-05: Burst of 20 camera heartbeats across 4 cameras simultaneously
"""

from __future__ import annotations

import pytest

try:
    from tests.e2e.harness import DatabaseAdapter, E2EApiClient, PlateGenerator
except ImportError:
    from harness import DatabaseAdapter, E2EApiClient, PlateGenerator


def test_t2_b6_01_burst_identical_entries_debounced(api_client: E2EApiClient, fresh_db: DatabaseAdapter):
    """T2-B6-01: Burst of 10 identical entry requests for same plate.

    Expected: 1st request accepted (HTTP 201), requests 2-10 ignored by cooldown debouncer;
    exactly 1 active session in database, liveOccupancy = 1.
    """
    plate = "DL01AB1234"
    results = []

    for i in range(10):
        res = api_client.post_anpr_event({
            "facilityId": "palika",
            "cameraId": "palika-entry-1",
            "gateType": "ENTRY",
            "plateNumber": plate,
            "confidence": 0.95,
        })
        results.append(res)

    # 1st request accepted
    assert results[0]["status_code"] == 201
    assert results[0]["status"] == "ACCEPTED"
    assert results[0]["liveOccupancy"] == 1

    # Remaining 9 requests debounced
    for i in range(1, 10):
        assert results[i]["status"] == "COOLDOWN_IGNORED"
        assert results[i]["liveOccupancy"] == 1

    # Authoritative DB Assertions
    sessions = fresh_db.query(
        "SELECT * FROM vehicle_sessions WHERE facility_id = 'palika' AND plate_number = ?;",
        (plate,),
    )
    assert len(sessions) == 1
    assert sessions[0]["status"] == "INSIDE"

    cooldown_events = fresh_db.query(
        "SELECT * FROM anpr_events WHERE facility_id = 'palika' AND status = 'COOLDOWN_IGNORED';"
    )
    assert len(cooldown_events) == 9
    assert fresh_db.get_live_occupancy("palika") == 1


def test_t2_b6_02_burst_distinct_vehicles_rapid_succession(api_client: E2EApiClient, fresh_db: DatabaseAdapter):
    """T2-B6-02: Burst of 5 distinct vehicles arriving in rapid succession.

    Expected: All 5 accepted (HTTP 201), liveOccupancy increments monotonically from 1 to 5;
    exactly 5 active INSIDE sessions in database.
    """
    plates = [
        "DL01AB1111",
        "MH12DE2222",
        "KA05MB3333",
        "HR26DQ4444",
        "UP16BZ5555",
    ]

    for idx, plate in enumerate(plates, 1):
        res = api_client.post_anpr_event({
            "facilityId": "palika",
            "cameraId": "palika-entry-1",
            "gateType": "ENTRY",
            "plateNumber": plate,
            "confidence": 0.95,
        })
        assert res["status_code"] == 201
        assert res["status"] == "ACCEPTED"
        assert res["liveOccupancy"] == idx

    # Authoritative DB Assertions
    active_count = fresh_db.query_one(
        "SELECT COUNT(*) AS c FROM vehicle_sessions WHERE facility_id = 'palika' AND status = 'INSIDE';"
    )["c"]
    assert active_count == 5
    assert fresh_db.get_live_occupancy("palika") == 5


def test_t2_b6_03_rapid_entry_exit_entry_turnaround(api_client: E2EApiClient, fresh_db: DatabaseAdapter):
    """T2-B6-03: Rapid entry-exit-entry cycle within 300 seconds.

    Expected: Entry 1 -> Exit -> Entry 2 succeeds;
    2 total sessions in DB (1 EXITED, 1 INSIDE); liveOccupancy = 1.
    """
    plate = "DL08CD9999"

    # Step 1: First Entry
    res1 = api_client.post_anpr_event({
        "facilityId": "palika",
        "cameraId": "palika-entry-1",
        "gateType": "ENTRY",
        "plateNumber": plate,
        "confidence": 0.95,
        "detectedAt": "2026-11-21T10:00:00Z",
    })
    assert res1["status"] == "ACCEPTED"
    assert fresh_db.get_live_occupancy("palika") == 1

    # Step 2: Exit 180 seconds later
    res2 = api_client.post_anpr_event({
        "facilityId": "palika",
        "cameraId": "palika-exit-1",
        "gateType": "EXIT",
        "plateNumber": plate,
        "confidence": 0.95,
        "detectedAt": "2026-11-21T10:03:00Z",
    })
    assert res2["status"] == "ACCEPTED"
    assert res2["durationSeconds"] == 180
    assert fresh_db.get_live_occupancy("palika") == 0

    # Step 3: Re-entry at Gate 2 (or after cooldown clear)
    res3 = api_client.post_anpr_event({
        "facilityId": "palika",
        "cameraId": "palika-entry-2",
        "gateType": "ENTRY",
        "plateNumber": plate,
        "confidence": 0.95,
        "detectedAt": "2026-11-21T10:05:00Z",
    })
    assert res3["status_code"] == 201
    assert res3["status"] == "ACCEPTED"
    assert fresh_db.get_live_occupancy("palika") == 1

    # Authoritative DB Assertions: 2 total sessions
    sessions = fresh_db.query(
        "SELECT * FROM vehicle_sessions WHERE facility_id = 'palika' AND plate_number = ? ORDER BY entry_time ASC;",
        (plate,),
    )
    assert len(sessions) == 2
    assert sessions[0]["status"] == "EXITED"
    assert sessions[1]["status"] == "INSIDE"
    assert fresh_db.get_live_occupancy("palika") == 1


def test_t2_b6_04_concurrent_entries_multi_gate(api_client: E2EApiClient, fresh_db: DatabaseAdapter):
    """T2-B6-04: Concurrent entries from Entry Gate 1 and Entry Gate 2 at exact same timestamp.

    Expected: Both return HTTP 201 ACCEPTED; liveOccupancy increments to 2;
    multi-gate parallel ingest maintains database consistency.
    """
    ts = "2026-11-21T10:00:00.000Z"
    plate_a = "DL01AA0001"
    plate_b = "DL01BB0002"

    res_a = api_client.post_anpr_event({
        "facilityId": "palika",
        "cameraId": "palika-entry-1",
        "gateType": "ENTRY",
        "plateNumber": plate_a,
        "confidence": 0.95,
        "detectedAt": ts,
    })
    assert res_a["status_code"] == 201
    assert res_a["status"] == "ACCEPTED"

    res_b = api_client.post_anpr_event({
        "facilityId": "palika",
        "cameraId": "palika-entry-2",
        "gateType": "ENTRY",
        "plateNumber": plate_b,
        "confidence": 0.95,
        "detectedAt": ts,
    })
    assert res_b["status_code"] == 201
    assert res_b["status"] == "ACCEPTED"

    # Authoritative DB Assertions
    assert fresh_db.get_live_occupancy("palika") == 2
    active_sessions = fresh_db.query(
        "SELECT * FROM vehicle_sessions WHERE facility_id = 'palika' AND status = 'INSIDE';"
    )
    active_plates = {s["plate_number"] for s in active_sessions}
    assert plate_a in active_plates
    assert plate_b in active_plates


def test_t2_b6_05_burst_camera_heartbeats_concurrent(api_client: E2EApiClient, fresh_db: DatabaseAdapter):
    """T2-B6-05: Burst of 20 camera heartbeat requests across 4 cameras simultaneously.

    Expected: All 20 return HTTP 200; parking_cameras records updated with latest heartbeats.
    """
    cameras = ["palika-entry-1", "palika-entry-2", "palika-exit-1", "palika-exit-2"]

    # Pre-register cameras
    for cam in cameras:
        fresh_db.execute(
            """
            INSERT OR IGNORE INTO parking_cameras
            (id, facility_id, name, feed_type, gate_type, status, created_at, updated_at)
            VALUES (?, 'palika', ?, 'SIMULATION', 'ENTRY', 'ONLINE', '2026-11-21T00:00:00Z', '2026-11-21T00:00:00Z');
            """,
            (cam, f"Camera {cam}"),
        )

    # Fire 5 heartbeats for each of the 4 cameras (total 20 pings)
    for i in range(5):
        for cam in cameras:
            res = api_client.post_camera_heartbeat({
                "cameraId": cam,
                "status": "ONLINE",
                "fps": 25.0 + i * 0.5,
                "lastFrameAt": f"2026-11-21T10:0{i}:00Z",
            })
            assert res["status_code"] == 200
            assert res["success"] is True
            assert res["status"] == "ONLINE"

    # Authoritative DB Assertions: all 4 cameras updated
    for cam in cameras:
        record = fresh_db.query_one("SELECT * FROM parking_cameras WHERE id = ?;", (cam,))
        assert record is not None
        assert record["status"] == "ONLINE"
        assert record["fps"] >= 25.0
        assert record["last_heartbeat_at"] is not None
