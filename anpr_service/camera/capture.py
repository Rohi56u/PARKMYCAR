"""
Polymorphic Camera Capture Engine for ANPR.
Supports USB webcams, IP RTSP streams, recorded video files, and synthetic simulation feeds.
Features threaded frame grabbing, FPS measurement, reconnection loops, and disconnection isolation.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
import threading
import time
from typing import Generator, Optional, Tuple

import cv2
import numpy as np

from anpr_service.synthetic import (
    DistortionConfig,
    PlateColorTheme,
    PlateLayout,
    SyntheticPlateGenerator,
)


class CameraFeedType(str, Enum):
    USB = "USB"
    IP_RTSP = "IP_RTSP"
    VIDEO_FILE = "VIDEO_FILE"
    SIMULATION = "SIMULATION"


class CameraStatus(str, Enum):
    ONLINE = "ONLINE"
    DEGRADED = "DEGRADED"
    OFFLINE = "OFFLINE"
    SIMULATING = "SIMULATING"


class CameraGateType(str, Enum):
    ENTRY = "ENTRY"
    EXIT = "EXIT"
    BIDIRECTIONAL = "BIDIRECTIONAL"


@dataclass
class CameraTelemetry:
    """Current runtime health telemetry for a camera feed."""
    camera_id: str
    feed_type: CameraFeedType
    gate_type: CameraGateType
    status: CameraStatus
    fps: float
    total_frames_read: int
    last_frame_timestamp: float
    error_count: int


class BaseCameraFeed(ABC):
    """Abstract base class for all camera feeds."""

    def __init__(
        self,
        camera_id: str,
        gate_type: CameraGateType = CameraGateType.ENTRY,
        target_fps: float = 25.0,
    ):
        self.camera_id = camera_id
        self.gate_type = gate_type
        self.target_fps = target_fps
        self.status = CameraStatus.OFFLINE
        self._fps_measured: float = 0.0
        self._frames_count: int = 0
        self._last_frame_time: float = 0.0
        self._error_count: int = 0
        self._running: bool = False

    @abstractmethod
    def start(self) -> bool:
        """Starts feed acquisition."""
        pass

    @abstractmethod
    def read_frame(self) -> Optional[np.ndarray]:
        """Reads the latest BGR frame. Returns None if feed is unavailable."""
        pass

    @abstractmethod
    def stop(self) -> None:
        """Stops the feed and releases resources."""
        pass

    def get_telemetry(self) -> CameraTelemetry:
        """Returns current operational telemetry."""
        return CameraTelemetry(
            camera_id=self.camera_id,
            feed_type=self.feed_type,
            gate_type=self.gate_type,
            status=self.status,
            fps=round(self._fps_measured, 2),
            total_frames_read=self._frames_count,
            last_frame_timestamp=self._last_frame_time,
            error_count=self._error_count,
        )


class OpenCVCameraFeed(BaseCameraFeed):
    """
    OpenCV-backed feed for USB webcams, IP RTSP streams, and video files.
    Uses a background worker thread to constantly pull the latest frame, preventing
    buffer lag and socket bloat.
    """

    def __init__(
        self,
        camera_id: str,
        source: str,  # "0", "rtsp://...", "path/to/video.mp4"
        feed_type: CameraFeedType = CameraFeedType.USB,
        gate_type: CameraGateType = CameraGateType.ENTRY,
        target_fps: float = 25.0,
        loop_video: bool = True,
    ):
        super().__init__(camera_id, gate_type, target_fps)
        self.source = source
        self.feed_type = feed_type
        self.loop_video = loop_video
        self._cap: Optional[cv2.VideoCapture] = None
        self._current_frame: Optional[np.ndarray] = None
        self._lock = threading.Lock()
        self._thread: Optional[threading.Thread] = None

    def start(self) -> bool:
        src = int(self.source) if self.source.isdigit() else self.source
        self._cap = cv2.VideoCapture(src)
        if not self._cap.isOpened():
            self.status = CameraStatus.OFFLINE
            self._error_count += 1
            return False

        self._running = True
        self.status = CameraStatus.ONLINE
        self._thread = threading.Thread(target=self._grab_loop, daemon=True)
        self._thread.start()
        return True

    def _grab_loop(self) -> None:
        fps_start = time.time()
        fps_frame_count = 0

        while self._running and self._cap and self._cap.isOpened():
            ret, frame = self._cap.read()
            if not ret or frame is None:
                if self.feed_type == CameraFeedType.VIDEO_FILE and self.loop_video:
                    self._cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                    continue
                self.status = CameraStatus.DEGRADED
                self._error_count += 1
                time.sleep(0.1)
                continue

            with self._lock:
                self._current_frame = frame
                self._last_frame_time = time.time()
                self._frames_count += 1

            fps_frame_count += 1
            now = time.time()
            elapsed = now - fps_start
            if elapsed >= 1.0:
                self._fps_measured = fps_frame_count / elapsed
                fps_frame_count = 0
                fps_start = now
                self.status = CameraStatus.ONLINE

            # Sleep slightly if needed to match target FPS
            time.sleep(max(0.001, (1.0 / self.target_fps) * 0.5))

    def read_frame(self) -> Optional[np.ndarray]:
        with self._lock:
            if self._current_frame is None:
                return None
            return self._current_frame.copy()

    def stop(self) -> None:
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.0)
        if self._cap:
            self._cap.release()
            self._cap = None
        self.status = CameraStatus.OFFLINE


class SimulationCameraFeed(BaseCameraFeed):
    """
    Synthetic camera feed emulator.
    Generates realistic 720p/1080p frames with synthetic vehicles and Indian license plates
    rendered at barrier focal points. Ideal for E2E testing, CI, and local demos.
    """
    feed_type = CameraFeedType.SIMULATION

    def __init__(
        self,
        camera_id: str,
        gate_type: CameraGateType = CameraGateType.ENTRY,
        target_fps: float = 25.0,
        frame_size: Tuple[int, int] = (1280, 720),
    ):
        super().__init__(camera_id, gate_type, target_fps)
        self.frame_size = frame_size
        self.generator = SyntheticPlateGenerator()
        self._active_plate: Optional[str] = None
        self._plate_image: Optional[np.ndarray] = None
        self._lock = threading.Lock()

    def start(self) -> bool:
        self._running = True
        self.status = CameraStatus.SIMULATING
        self._last_frame_time = time.time()
        self._fps_measured = self.target_fps
        return True

    def set_vehicle(
        self,
        plate_number: str,
        theme: PlateColorTheme = PlateColorTheme.PRIVATE_WHITE,
        layout: PlateLayout = PlateLayout.SINGLE_ROW,
        distortion: Optional[DistortionConfig] = None,
    ) -> None:
        """Injects a specific vehicle plate into the simulation feed."""
        result = self.generator.generate(
            plate_number=plate_number,
            theme=theme,
            layout=layout,
            distortion_cfg=distortion,
        )
        with self._lock:
            self._active_plate = plate_number
            self._plate_image = result.image

    def clear_vehicle(self) -> None:
        """Removes the vehicle from the barrier field of view (empty lane)."""
        with self._lock:
            self._active_plate = None
            self._plate_image = None

    def read_frame(self) -> Optional[np.ndarray]:
        if not self._running:
            return None

        w, h = self.frame_size
        # Render parking gate background (asphalt road, barriers, guard post)
        frame = np.full((h, w, 3), (45, 45, 50), dtype=np.uint8)

        # Draw road lane markings
        cv2.line(frame, (w // 2, 0), (w // 2, h), (255, 255, 255), 4)
        # Draw boom barrier pole and arm
        cv2.rectangle(frame, (100, h - 300), (160, h), (80, 80, 90), -1)
        cv2.line(frame, (160, h - 260), (w - 200, h - 260), (0, 0, 220), 12)

        with self._lock:
            if self._plate_image is not None:
                # Composite vehicle front grille & bumper
                car_w, car_h = 600, 360
                car_x = (w - car_w) // 2
                car_y = h - car_h - 40
                # Vehicle body (metallic grey)
                cv2.rectangle(frame, (car_x, car_y), (car_x + car_w, car_y + car_h), (70, 75, 80), -1)
                # Headlights
                cv2.ellipse(frame, (car_x + 60, car_y + 80), (45, 25), 0, 0, 360, (230, 240, 250), -1)
                cv2.ellipse(frame, (car_x + car_w - 60, car_y + 80), (45, 25), 0, 0, 360, (230, 240, 250), -1)

                # Composite plate onto bumper center
                ph, pw = self._plate_image.shape[:2]
                px = (w - pw) // 2
                py = car_y + car_h - ph - 30
                frame[py : py + ph, px : px + pw] = self._plate_image

        self._frames_count += 1
        self._last_frame_time = time.time()
        return frame

    def stop(self) -> None:
        self._running = False
        self.status = CameraStatus.OFFLINE
