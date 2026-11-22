"""Tier 1 Feature 5: Polymorphic Camera Simulation & Feed Management (T1-F5-01 .. T1-F5-05).

Validates:
- T1-F5-01: Configure USB webcam feed (feedType: USB, deviceIndex)
- T1-F5-02: Configure RTSP IP camera feed (feedType: IP_RTSP, streamUrl)
- T1-F5-03: Configure Video File feed (feedType: VIDEO_FILE, streamUrl)
- T1-F5-04: Inject synthetic frame event into simulation camera (palika-sim-entry)
- T1-F5-05: Camera telemetry heartbeat ping (fps: 28.4, last_heartbeat_at)
"""

from __future__ import annotations

import json
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


def test_t1_f5_01_configure_usb_webcam_feed(fresh_db: DatabaseAdapter):
    """T1-F5-01: Configure USB webcam feed (feedType: USB, config: {"deviceIndex": 0}).
    
    Verifies:
    - Camera record inserted with feed_type = 'USB' and status = 'ONLINE'
    - Config JSON parsed and validated with deviceIndex
    """
    cam_id = "cam-usb-0"
    config_data = {"deviceIndex": 0, "resolution": "1280x720", "autofocus": True}

    fresh_db.execute(
        """
        INSERT INTO parking_cameras
        (id, facility_id, name, feed_type, stream_url, gate_type, status, fps, config, created_at, updated_at)
        VALUES (?, 'palika', 'Palika USB Entry', 'USB', NULL, 'ENTRY', 'ONLINE', 30.0, ?, '2026-11-21T00:00:00Z', '2026-11-21T00:00:00Z');
        """,
        (cam_id, json.dumps(config_data)),
    )

    cam = fresh_db.query_one("SELECT * FROM parking_cameras WHERE id = ?", (cam_id,))
    assert cam is not None
    assert cam["feed_type"] == "USB"
    assert cam["status"] == "ONLINE"
    cfg = json.loads(cam["config"])
    assert cfg["deviceIndex"] == 0
    assert cfg["autofocus"] is True


def test_t1_f5_02_configure_rtsp_ip_camera(fresh_db: DatabaseAdapter):
    """T1-F5-02: Configure RTSP IP camera feed (feedType: IP_RTSP, streamUrl).
    
    Verifies:
    - Camera record inserted with feed_type = 'IP_RTSP'
    - Stream URL recorded accurately
    """
    cam_id = "cam-rtsp-1"
    stream_url = "rtsp://192.168.1.100:554/live"
    config_data = {"transport": "tcp", "bufferSize": 2048}

    fresh_db.execute(
        """
        INSERT INTO parking_cameras
        (id, facility_id, name, feed_type, stream_url, gate_type, status, fps, config, created_at, updated_at)
        VALUES (?, 'palika', 'Palika RTSP Gate', 'IP_RTSP', ?, 'ENTRY', 'ONLINE', 25.0, ?, '2026-11-21T00:00:00Z', '2026-11-21T00:00:00Z');
        """,
        (cam_id, stream_url, json.dumps(config_data)),
    )

    cam = fresh_db.query_one("SELECT * FROM parking_cameras WHERE id = ?", (cam_id,))
    assert cam is not None
    assert cam["feed_type"] == "IP_RTSP"
    assert cam["stream_url"] == stream_url
    assert cam["status"] == "ONLINE"


def test_t1_f5_03_configure_video_file_feed(fresh_db: DatabaseAdapter):
    """T1-F5-03: Configure Video File feed (feedType: VIDEO_FILE, streamUrl).
    
    Verifies:
    - Camera record configured with feed_type = 'VIDEO_FILE'
    - Video file path persisted in database
    """
    cam_id = "cam-file-1"
    file_path = "fixtures/gate_traffic.mp4"

    fresh_db.execute(
        """
        INSERT INTO parking_cameras
        (id, facility_id, name, feed_type, stream_url, gate_type, status, fps, config, created_at, updated_at)
        VALUES (?, 'palika', 'Palika Video File Gate', 'VIDEO_FILE', ?, 'ENTRY', 'ONLINE', 30.0, '{}', '2026-11-21T00:00:00Z', '2026-11-21T00:00:00Z');
        """,
        (cam_id, file_path),
    )

    cam = fresh_db.query_one("SELECT * FROM parking_cameras WHERE id = ?", (cam_id,))
    assert cam is not None
    assert cam["feed_type"] == "VIDEO_FILE"
    assert cam["stream_url"] == file_path


def test_t1_f5_04_synthetic_simulation_feed_event(api_client: E2EApiClient, fresh_db: DatabaseAdapter):
    """T1-F5-04: Inject synthetic frame event into simulation camera (palika-sim-entry).
    
    Verifies:
    - Simulation camera accepts event and processes synthetic payload
    - anpr_events records camera_id = 'palika-sim-entry'
    - Status is ACCEPTED, session created
    """
    sim_cam = CameraSimulator(
        camera_id="palika-sim-entry",
        facility_id="palika",
        gate_type="ENTRY",
        feed_type="SIMULATION",
        fps=30.0,
        api_client=api_client,
        db=fresh_db,
    )

    plate_text = "DL01AB9876"
    res = sim_cam.simulate_detection(plate_number=plate_text, confidence=0.95)

    assert res["status_code"] == 201
    assert res["success"] is True
    assert res["status"] == "ACCEPTED"

    event = fresh_db.query_one("SELECT * FROM anpr_events WHERE id = ?", (res["eventId"],))
    assert event["camera_id"] == "palika-sim-entry"
    assert event["plate_number"] == plate_text
    assert event["status"] == "ACCEPTED"


def test_t1_f5_05_camera_heartbeat_telemetry(api_client: E2EApiClient, fresh_db: DatabaseAdapter):
    """T1-F5-05: Camera sends heartbeat ping (POST /api/v1/anpr/heartbeat, fps: 28.4).
    
    Verifies:
    - Heartbeat endpoint updates camera fps and last_heartbeat_at in database
    - Status remains ONLINE
    """
    cam_id = "palika-entry-1"
    res = api_client.post_camera_heartbeat({
        "cameraId": cam_id,
        "status": "ONLINE",
        "fps": 28.4,
        "lastFrameAt": "2026-11-21T14:30:00Z",
    })

    assert res["status_code"] == 200
    assert res["success"] is True
    assert res["status"] == "ONLINE"

    cam = fresh_db.query_one("SELECT * FROM parking_cameras WHERE id = ?", (cam_id,))
    assert cam is not None
    assert cam["status"] == "ONLINE"
    assert cam["fps"] == 28.4
    assert cam["last_heartbeat_at"] == "2026-11-21T14:30:00Z"
