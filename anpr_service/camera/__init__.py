"""
Camera management subsystem for ANPR:
- capture.py: Polymorphic feeds (USB, IP_RTSP, VIDEO_FILE, SIMULATION)
- tracker.py: Multi-frame temporal voting
- cooldown.py: 120s gate debouncing
- manager.py: Fleet orchestration
"""
from anpr_service.camera.capture import (
    BaseCameraFeed,
    CameraFeedType,
    CameraGateType,
    CameraStatus,
    CameraTelemetry,
    OpenCVCameraFeed,
    SimulationCameraFeed,
)
from anpr_service.camera.cooldown import GateCooldownManager
from anpr_service.camera.tracker import (
    FrameDetection,
    MultiFrameVehicleTracker,
    VotingQuorumResult,
)
from anpr_service.camera.manager import (
    CameraFleetManager,
    ProcessedPlateEvent,
)

__all__ = [
    "BaseCameraFeed",
    "CameraFeedType",
    "CameraGateType",
    "CameraStatus",
    "CameraTelemetry",
    "OpenCVCameraFeed",
    "SimulationCameraFeed",
    "GateCooldownManager",
    "FrameDetection",
    "MultiFrameVehicleTracker",
    "VotingQuorumResult",
    "CameraFleetManager",
    "ProcessedPlateEvent",
]
