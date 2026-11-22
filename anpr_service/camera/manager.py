"""
Camera Fleet Manager and Live Processing Pipeline Orchestrator.
Coordinates camera lifecycles, frame acquisition, detection, OCR, validation,
temporal multi-frame tracking, and gate cooldown debouncing.
"""
from dataclasses import dataclass, field
import logging
import threading
import time
from typing import Callable, Dict, List, Optional

import cv2
import numpy as np

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
from anpr_service.camera.tracker import MultiFrameVehicleTracker, VotingQuorumResult
from anpr_service.detector import BasePlateDetector, create_detector
from anpr_service.ocr import OcrEngine, OcrResult
from anpr_service.validator import IndianPlateValidator, PlateValidationResult, ValidationStatus


logger = logging.getLogger("anpr.camera_manager")


@dataclass
class ProcessedPlateEvent:
    """Standardized event generated when a vehicle is identified at a barrier."""
    facility_id: str
    camera_id: str
    gate_type: str
    plate_number: str
    confidence: float
    status: str  # ACCEPTED, NEEDS_REVIEW, COOLDOWN_IGNORED, UNMATCHED_EXIT
    review_reason: Optional[str]
    processing_time_ms: int
    detected_at: str
    plate_crop_b64: Optional[str] = None


class CameraFleetManager:
    """
    Central manager controlling all cameras across a parking facility.
    Executes frame processing loop, coordinates detection/OCR/validation,
    applies multi-frame quorum and debouncing, and dispatches events.
    """

    def __init__(
        self,
        facility_id: str = "palika",
        detector: Optional[BasePlateDetector] = None,
        ocr_engine: Optional[OcrEngine] = None,
        validator: Optional[IndianPlateValidator] = None,
        cooldown_seconds: float = 120.0,
        voting_window_seconds: float = 2.5,
    ):
        self.facility_id = facility_id
        self.detector = detector or create_detector()
        self.ocr_engine = ocr_engine or OcrEngine()
        self.validator = validator or IndianPlateValidator()
        self.cooldown = GateCooldownManager(cooldown_seconds)
        self.tracker = MultiFrameVehicleTracker(window_seconds=voting_window_seconds)

        self._cameras: Dict[str, BaseCameraFeed] = {}
        self._event_callbacks: List[Callable[[ProcessedPlateEvent], None]] = []
        self._running = False
        self._pipeline_thread: Optional[threading.Thread] = None

    def register_camera(
        self,
        camera_id: str,
        feed_type: CameraFeedType = CameraFeedType.SIMULATION,
        gate_type: CameraGateType = CameraGateType.ENTRY,
        source: Optional[str] = None,
        target_fps: float = 25.0,
    ) -> BaseCameraFeed:
        """Instantiates and registers a camera feed."""
        if feed_type == CameraFeedType.SIMULATION:
            feed = SimulationCameraFeed(
                camera_id=camera_id,
                gate_type=gate_type,
                target_fps=target_fps,
            )
        else:
            feed = OpenCVCameraFeed(
                camera_id=camera_id,
                source=source or "0",
                feed_type=feed_type,
                gate_type=gate_type,
                target_fps=target_fps,
            )

        self._cameras[camera_id] = feed
        return feed

    def start_camera(self, camera_id: str) -> bool:
        """Starts a specific camera feed."""
        feed = self._cameras.get(camera_id)
        if feed:
            return feed.start()
        return False

    def stop_camera(self, camera_id: str) -> None:
        """Stops a specific camera feed."""
        feed = self._cameras.get(camera_id)
        if feed:
            feed.stop()

    def get_camera(self, camera_id: str) -> Optional[BaseCameraFeed]:
        return self._cameras.get(camera_id)

    def list_cameras(self) -> List[CameraTelemetry]:
        """Returns health telemetry for all registered cameras."""
        return [c.get_telemetry() for c in self._cameras.values()]

    def add_event_listener(self, callback: Callable[[ProcessedPlateEvent], None]) -> None:
        """Registers a listener for verified ANPR events."""
        self._event_callbacks.append(callback)

    def process_frame(
        self,
        camera_id: str,
        frame: np.ndarray,
        current_time: Optional[float] = None,
    ) -> Optional[ProcessedPlateEvent]:
        """
        Executes end-to-end ANPR on a single frame from `camera_id`:
        1. Detect plate bbox
        2. Extract & preprocess crop
        3. OCR character recognition
        4. Statutory validation & DIN 1451 disambiguation
        5. Temporal multi-frame voting
        6. Cooldown debouncing check
        """
        start_t = time.perf_counter()
        t_now = current_time if current_time is not None else time.time()
        feed = self._cameras.get(camera_id)
        gate_type = feed.gate_type.value if feed else "ENTRY"

        # 1. Detection
        detections = self.detector.detect(frame)
        if not detections:
            return None

        # Iterate detection candidates to find valid plate crop with text
        ocr_res: Optional[OcrResult] = None
        chosen_det = None

        for det in detections[: self.detector.max_candidates if hasattr(self.detector, 'max_candidates') else 5]:
            crop = det.cropped_plate
            if crop is None or crop.size == 0:
                continue
            cand_ocr = self.ocr_engine.extract(crop)
            if cand_ocr.raw_text:
                ocr_res = cand_ocr
                chosen_det = det
                break

        if not ocr_res or not chosen_det:
            return None

        # 3. Statutory Validation
        val_res: PlateValidationResult = self.validator.validate(
            ocr_res.raw_text,
            ocr_res.char_confidences,
        )

        plate_str = val_res.normalized_plate or ocr_res.raw_text
        confidence = val_res.confidence

        # 4. Multi-frame Voting Accumulation
        self.tracker.add_detection(
            camera_id=camera_id,
            plate_number=plate_str,
            confidence=confidence,
            timestamp=t_now,
            bbox=chosen_det.box,
        )

        # 5. Check Low-Confidence / Invalid Syntax Gating Invariant
        if not val_res.is_valid or val_res.status == ValidationStatus.NEEDS_REVIEW:
            elapsed_ms = int((time.perf_counter() - start_t) * 1000)
            event = ProcessedPlateEvent(
                facility_id=self.facility_id,
                camera_id=camera_id,
                gate_type=gate_type,
                plate_number=plate_str,
                confidence=round(confidence, 3),
                status="NEEDS_REVIEW",
                review_reason=val_res.review_reason.value if val_res.review_reason else "Syntax mismatch",
                processing_time_ms=elapsed_ms,
                detected_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(t_now)),
            )
            self._dispatch_event(event)
            return event

        # 6. Cooldown Check
        if self.cooldown.should_debounce(camera_id, plate_str, t_now):
            elapsed_ms = int((time.perf_counter() - start_t) * 1000)
            event = ProcessedPlateEvent(
                facility_id=self.facility_id,
                camera_id=camera_id,
                gate_type=gate_type,
                plate_number=plate_str,
                confidence=round(confidence, 3),
                status="COOLDOWN_IGNORED",
                review_reason="Gate cooldown active (120s)",
                processing_time_ms=elapsed_ms,
                detected_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(t_now)),
            )
            return event

        # Cooldown expired or first seen: record in debouncer
        self.cooldown.record_detection(camera_id, plate_str, t_now)
        elapsed_ms = int((time.perf_counter() - start_t) * 1000)

        event = ProcessedPlateEvent(
            facility_id=self.facility_id,
            camera_id=camera_id,
            gate_type=gate_type,
            plate_number=plate_str,
            confidence=round(confidence, 3),
            status="ACCEPTED",
            review_reason=None,
            processing_time_ms=elapsed_ms,
            detected_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(t_now)),
        )
        self._dispatch_event(event)
        return event

    def _dispatch_event(self, event: ProcessedPlateEvent) -> None:
        for cb in self._event_callbacks:
            try:
                cb(event)
            except Exception as e:
                logger.error(f"Error dispatching ANPR event: {e}")

    def shutdown(self) -> None:
        """Stops all camera feeds and releases resources."""
        for feed in self._cameras.values():
            feed.stop()
        self._cameras.clear()
        self.cooldown.reset()
