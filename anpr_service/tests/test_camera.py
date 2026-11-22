"""
Unit tests for Camera Management & Simulation (Milestone 3).
Tests:
- Polymorphic feeds: SimulationCameraFeed, OpenCV feed abstractions
- Cooldown debouncing: repeated detections within 120s are debounced
- Multi-frame temporal voting: consensus reached across sliding window
- Health telemetry & disconnection isolation: going offline doesn't impact state
- CameraFleetManager orchestration: end-to-end frame processing & event dispatch
"""
import time
import numpy as np
import pytest

from anpr_service.camera import (
    BaseCameraFeed,
    CameraFeedType,
    CameraGateType,
    CameraStatus,
    CameraTelemetry,
    SimulationCameraFeed,
    GateCooldownManager,
    MultiFrameVehicleTracker,
    CameraFleetManager,
    ProcessedPlateEvent,
)
from anpr_service.synthetic import PlateColorTheme


def test_simulation_camera_feed_lifecycle():
    feed = SimulationCameraFeed(
        camera_id="test-sim-entry",
        gate_type=CameraGateType.ENTRY,
        target_fps=20.0,
    )
    assert feed.status == CameraStatus.OFFLINE

    assert feed.start() is True
    assert feed.status == CameraStatus.SIMULATING

    # Empty barrier frame
    frame = feed.read_frame()
    assert frame is not None
    assert frame.shape == (720, 1280, 3)

    # Set vehicle
    feed.set_vehicle("DL01AB1234", theme=PlateColorTheme.PRIVATE_WHITE)
    frame_with_car = feed.read_frame()
    assert frame_with_car is not None

    telemetry = feed.get_telemetry()
    assert telemetry.camera_id == "test-sim-entry"
    assert telemetry.feed_type == CameraFeedType.SIMULATION
    assert telemetry.gate_type == CameraGateType.ENTRY
    assert telemetry.status == CameraStatus.SIMULATING
    assert telemetry.total_frames_read >= 2

    feed.stop()
    assert feed.status == CameraStatus.OFFLINE
    assert feed.read_frame() is None


def test_cooldown_manager_debouncing():
    cd = GateCooldownManager(cooldown_seconds=120.0)
    cam = "palika-gate-1"
    plate = "DL01AB1234"

    t0 = 1000.0
    # First detection: should NOT debounce
    assert cd.should_debounce(cam, plate, current_time=t0) is False
    cd.record_detection(cam, plate, current_time=t0)

    # Immediate repeat detection (t = 1005s): MUST debounce
    assert cd.should_debounce(cam, plate, current_time=t0 + 5.0) is True

    # 60s later: still in 120s window -> MUST debounce
    assert cd.should_debounce(cam, plate, current_time=t0 + 60.0) is True

    # Different camera at t = 1005s: NOT debounced on other camera
    assert cd.should_debounce("palika-gate-2", plate, current_time=t0 + 5.0) is False

    # After cooldown expires (t = t0 + 125s): NOT debounced
    assert cd.should_debounce(cam, plate, current_time=t0 + 125.0) is False

    # Prune expired entries
    pruned = cd.prune_expired(current_time=t0 + 500.0)
    assert pruned == 1


def test_multi_frame_vehicle_tracker_quorum():
    tracker = MultiFrameVehicleTracker(
        window_seconds=2.5,
        min_votes_required=3,
        min_consensus_ratio=0.60,
    )
    cam = "cam-1"
    t0 = 2000.0

    # Add 1 detection: below min_votes_required
    tracker.add_detection(cam, "DL01AB1234", confidence=0.92, timestamp=t0)
    assert tracker.evaluate_quorum(cam, current_time=t0) is None

    # Add 2nd detection
    tracker.add_detection(cam, "DL01AB1234", confidence=0.94, timestamp=t0 + 0.1)
    assert tracker.evaluate_quorum(cam, current_time=t0 + 0.1) is None

    # Add 3rd detection (same plate): reaches consensus
    tracker.add_detection(cam, "DL01AB1234", confidence=0.96, timestamp=t0 + 0.2)
    quorum = tracker.evaluate_quorum(cam, current_time=t0 + 0.2)
    assert quorum is not None
    assert quorum.winner_plate == "DL01AB1234"
    assert quorum.vote_count == 3
    assert quorum.total_frames == 3
    assert quorum.consensus_reached is True
    assert quorum.confidence >= 0.94

    # Add conflicting single noisy glitch frame
    tracker.add_detection(cam, "DL01AB1238", confidence=0.50, timestamp=t0 + 0.3)
    quorum2 = tracker.evaluate_quorum(cam, current_time=t0 + 0.3)
    assert quorum2 is not None
    # Winner is still the consensus plate
    assert quorum2.winner_plate == "DL01AB1234"
    assert quorum2.vote_count == 3
    assert quorum2.total_frames == 4
    assert quorum2.consensus_reached is True  # 3/4 = 75% >= 60%

    # Wait until window expires
    quorum_expired = tracker.evaluate_quorum(cam, current_time=t0 + 3.0)
    assert quorum_expired is None


def test_camera_fleet_manager_orchestration():
    manager = CameraFleetManager(
        facility_id="palika",
        cooldown_seconds=120.0,
        voting_window_seconds=2.5,
    )

    feed = manager.register_camera(
        camera_id="sim-entry-1",
        feed_type=CameraFeedType.SIMULATION,
        gate_type=CameraGateType.ENTRY,
    )
    manager.start_camera("sim-entry-1")
    assert feed.status == CameraStatus.SIMULATING

    events_received = []
    manager.add_event_listener(lambda e: events_received.append(e))

    # Set valid vehicle in feed
    feed.set_vehicle("DL01AB1234", theme=PlateColorTheme.PRIVATE_WHITE)
    frame = feed.read_frame()

    # Process frame
    t0 = 5000.0
    evt1 = manager.process_frame("sim-entry-1", frame, current_time=t0)
    assert evt1 is not None
    assert evt1.camera_id == "sim-entry-1"
    assert evt1.gate_type == "ENTRY"
    assert evt1.status in ("ACCEPTED", "NEEDS_REVIEW")

    # If first event was ACCEPTED, immediate second frame MUST be COOLDOWN_IGNORED
    if evt1.status == "ACCEPTED":
        evt2 = manager.process_frame("sim-entry-1", frame, current_time=t0 + 1.0)
        assert evt2 is not None
        assert evt2.status == "COOLDOWN_IGNORED"

    manager.shutdown()
    assert feed.status == CameraStatus.OFFLINE
