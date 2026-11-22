"""Polymorphic Camera Feed Emulator for ANPR E2E Testing.

Supports:
- Polymorphic feed types: USB, IP_RTSP, VIDEO_FILE, SIMULATION
- Camera connection health management: ONLINE, DEGRADED, OFFLINE, SIMULATING
- Disconnection isolation: Camera going OFFLINE never decrements occupancy or drops sessions
- Multi-frame simulation and burst ingestion
"""

from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any, Optional

from .api_client import E2EApiClient
from .db_adapter import DatabaseAdapter
from .mock_frames import PlateCropGenerator


class CameraSimulator:
    """Polymorphic camera feed and heartbeat simulator."""

    VALID_FEED_TYPES = ["USB", "IP_RTSP", "VIDEO_FILE", "SIMULATION"]
    VALID_STATUSES = ["ONLINE", "DEGRADED", "OFFLINE", "SIMULATING"]

    def __init__(
        self,
        camera_id: str = "palika-entry-1",
        facility_id: str = "palika",
        gate_type: str = "ENTRY",
        feed_type: str = "SIMULATION",
        fps: float = 25.0,
        api_client: Optional[E2EApiClient] = None,
        db: Optional[DatabaseAdapter] = None,
    ):
        """Initialize camera simulator."""
        self.camera_id = camera_id
        self.facility_id = facility_id
        self.gate_type = gate_type.upper()
        self.feed_type = feed_type.upper() if feed_type.upper() in self.VALID_FEED_TYPES else "SIMULATION"
        self.fps = fps
        self.status = "ONLINE"
        self.api_client = api_client
        self.db = db or (api_client.db if api_client else None)
        self.frame_counter = 0

    def _now_iso(self) -> str:
        """UTC ISO-8601 string."""
        return datetime.now(timezone.utc).isoformat()

    def send_heartbeat(
        self,
        status: Optional[str] = None,
        fps: Optional[float] = None,
    ) -> dict[str, Any]:
        """Send camera heartbeat updating health status in database."""
        if status:
            self.status = status.upper()
        if fps is not None:
            self.fps = fps

        payload = {
            "cameraId": self.camera_id,
            "status": self.status,
            "fps": self.fps,
            "lastFrameAt": self._now_iso(),
        }

        if self.api_client:
            return self.api_client.post_camera_heartbeat(payload)

        # Fallback to direct DB update if no API client
        if self.db:
            now_iso = self._now_iso()
            self.db.execute(
                """
                UPDATE parking_cameras
                SET status = ?, fps = ?, last_heartbeat_at = ?, updated_at = ?
                WHERE id = ?;
                """,
                (self.status, self.fps, now_iso, now_iso, self.camera_id),
            )
            return {"status_code": 200, "success": True, "cameraId": self.camera_id, "status": self.status}

        return {"status_code": 500, "success": False, "error": "No api_client or db configured"}

    def disconnect(self) -> dict[str, Any]:
        """Simulate sudden camera ethernet/cable disconnect (marks camera OFFLINE).
        
        Strict Invariant: Camera disconnection NEVER alters active vehicle sessions or live occupancy!
        """
        self.status = "OFFLINE"
        self.fps = 0.0
        return self.send_heartbeat(status="OFFLINE", fps=0.0)

    def reconnect(self, fps: float = 25.0) -> dict[str, Any]:
        """Simulate camera reconnecting and returning ONLINE."""
        self.status = "ONLINE"
        self.fps = fps
        return self.send_heartbeat(status="ONLINE", fps=fps)

    def degrade(self, fps: float = 5.0) -> dict[str, Any]:
        """Simulate degraded connection (dropped frames, reduced FPS)."""
        self.status = "DEGRADED"
        self.fps = fps
        return self.send_heartbeat(status="DEGRADED", fps=fps)

    def simulate_detection(
        self,
        plate_number: str,
        confidence: float = 0.94,
        plate_crop_url: Optional[str] = None,
        processing_time_ms: int = 38,
        detected_at: Optional[str] = None,
        bg_color: str = "white",
    ) -> dict[str, Any]:
        """Simulate vehicle passage detection and forward to API ingest."""
        if not self.api_client:
            raise RuntimeError("E2EApiClient must be provided to simulate detections")

        self.frame_counter += 1
        crop_url = plate_crop_url or PlateCropGenerator.generate_crop_data_url(
            plate_text=plate_number,
            bg_color=bg_color,
        )

        payload = {
            "facilityId": self.facility_id,
            "cameraId": self.camera_id,
            "gateType": self.gate_type,
            "plateNumber": plate_number,
            "confidence": confidence,
            "plateCropBase64": crop_url,
            "detectedAt": detected_at or self._now_iso(),
            "processingTimeMs": processing_time_ms,
        }

        return self.api_client.post_anpr_event(payload)

    def simulate_burst(
        self,
        plates: list[str],
        confidence: float = 0.95,
    ) -> list[dict[str, Any]]:
        """Simulate a burst of vehicles arriving in succession."""
        results = []
        for plate in plates:
            res = self.simulate_detection(plate_number=plate, confidence=confidence)
            results.append(res)
        return results

    def verify_isolation_invariant(self) -> bool:
        """Verify that disconnecting/reconnecting this camera does not alter active sessions."""
        if not self.db:
            return True

        initial_occ = self.db.get_live_occupancy(self.facility_id)
        # Disconnect camera
        self.disconnect()
        occ_after_disconnect = self.db.get_live_occupancy(self.facility_id)
        if occ_after_disconnect != initial_occ:
            return False

        # Reconnect camera
        self.reconnect()
        occ_after_reconnect = self.db.get_live_occupancy(self.facility_id)
        return occ_after_reconnect == initial_occ
