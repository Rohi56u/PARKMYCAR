"""In-Process E2E API Client Simulating ParkMyCar ANPR & Occupancy Endpoints.

Implements service contracts per PROJECT.md § Interface Contracts:
- Authentication via X-ANPR-Secret header
- Gate cooldown debouncing (120s per camera)
- Authoritative vehicle session transitions (INSIDE -> EXITED)
- Unmatched exit detection & isolation
- Low-confidence gating (<0.80) to NEEDS_REVIEW
- Operator manual review queue inspection and resolution
- Live occupancy derivation strictly from SELECT COUNT(*) WHERE status='INSIDE'
"""

from __future__ import annotations

import hmac
import json
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from .db_adapter import DatabaseAdapter
from .mock_frames import PlateGenerator


class E2EApiClient:
    """In-process mock client simulating ParkMyCar FastAPI and Next.js/Cloudflare API routes."""

    DEFAULT_SECRET = "test-anpr-secret-token-2026"

    def __init__(
        self,
        db: DatabaseAdapter,
        secret: str = DEFAULT_SECRET,
        cooldown_seconds: float = 120.0,
        min_confidence_threshold: float = 0.80,
    ):
        """Initialize API client with database adapter and debouncing configuration."""
        self.db = db
        self.secret = secret
        self.cooldown_seconds = cooldown_seconds
        self.min_confidence_threshold = min_confidence_threshold
        # In-memory cooldown cache: (camera_id, plate_number) -> last_detection_epoch
        self._cooldown_cache: dict[tuple[str, str], float] = {}

    def reset_cooldown(self) -> None:
        """Clear camera debouncing cache."""
        self._cooldown_cache.clear()

    def _authenticate(self, headers: Optional[dict[str, str]]) -> bool:
        """Verify constant-time X-ANPR-Secret token authentication."""
        if not headers:
            return False
        # Normalize header keys (case-insensitive lookup)
        header_val = None
        for k, v in headers.items():
            if k.lower() == "x-anpr-secret":
                header_val = v
                break

        if not header_val:
            return False
        return hmac.compare_digest(header_val, self.secret)

    def _now_iso(self) -> str:
        """Generate current UTC ISO-8601 timestamp string."""
        return datetime.now(timezone.utc).isoformat()

    def _parse_iso(self, ts_str: str) -> datetime:
        """Parse ISO-8601 string to aware datetime."""
        # Replace trailing 'Z' with '+00:00' for Python fromisoformat
        clean = ts_str.replace("Z", "+00:00")
        return datetime.fromisoformat(clean)

    def _sync_facility_observation(self, facility_id: str) -> None:
        """Sync live occupancy state to facilities observations table for driver discovery."""
        total = self.db.get_facility_total_capacity(facility_id)
        live = self.db.get_live_occupancy(facility_id)

        if total <= 0:
            state = "UNKNOWN"
        elif live >= total:
            state = "FULL"
        elif live >= total * 0.8:
            state = "LIMITED"
        else:
            state = "AVAILABLE"

        now = self._now_iso()
        expires = datetime.now(timezone.utc).timestamp() + 3600  # 1 hour lease
        expires_iso = datetime.fromtimestamp(expires, timezone.utc).isoformat()
        obs_id = f"obs_{uuid.uuid4().hex[:12]}"

        self.db.execute(
            """
            INSERT INTO observations (id, facility_id, state, evidence_class, source, observed_at, expires_at)
            VALUES (?, ?, ?, 'OPERATOR_REPORTED', 'ANPR_AUTO_SYNC', ?, ?);
            """,
            (obs_id, facility_id, state, now, expires_iso),
        )

    # -------------------------------------------------------------------------
    # 1. ANPR Ingestion: POST /api/v1/anpr/events
    # -------------------------------------------------------------------------
    def post_anpr_event(
        self,
        payload: dict[str, Any],
        headers: Optional[dict[str, str]] = None,
    ) -> dict[str, Any]:
        """Simulate POST /api/v1/anpr/events endpoint.
        
        Payload:
        {
            "facilityId": "palika",
            "cameraId": "palika-entry-1",
            "gateType": "ENTRY" | "EXIT",
            "plateNumber": "DL01AB1234",
            "confidence": 0.94,
            "plateCropBase64": "data:image/jpeg;base64,...",
            "detectedAt": "2026-11-21T14:30:00.000Z",
            "processingTimeMs": 48
        }
        """
        # 1. Authenticate request
        if headers is None:
            headers = {"X-ANPR-Secret": self.secret}

        if not self._authenticate(headers):
            return {
                "status_code": 401,
                "success": False,
                "error": "Unauthorized: Invalid or missing X-ANPR-Secret",
            }

        facility_id = payload.get("facilityId", "palika")
        camera_id = payload.get("cameraId", "palika-entry-1")
        gate_type = payload.get("gateType", "ENTRY").upper()
        raw_plate = payload.get("plateNumber", "")
        confidence = float(payload.get("confidence", 0.0))
        plate_crop = payload.get("plateCropBase64")
        detected_at = payload.get("detectedAt") or self._now_iso()
        processing_time_ms = int(payload.get("processingTimeMs", 35))
        now_epoch = datetime.now(timezone.utc).timestamp()
        event_id = f"evt_{uuid.uuid4().hex[:12]}"

        # Normalize plate
        normalized_plate = raw_plate.strip().upper().replace(" ", "").replace("-", "")

        # Verify camera exists in database
        camera = self.db.query_one("SELECT * FROM parking_cameras WHERE id = ?", (camera_id,))
        if not camera:
            # Auto-register test camera if facility exists
            self.db.execute(
                """
                INSERT OR IGNORE INTO parking_cameras
                (id, facility_id, name, feed_type, gate_type, status, created_at, updated_at)
                VALUES (?, ?, ?, 'SIMULATION', ?, 'ONLINE', ?, ?);
                """,
                (camera_id, facility_id, f"Auto-Camera {camera_id}", gate_type, detected_at, detected_at),
            )

        # 2. Check low confidence (< 0.80) or unparseable grammar
        is_valid_grammar, grammar_kind = PlateGenerator.is_valid_indian_plate(normalized_plate)
        if confidence < self.min_confidence_threshold or not is_valid_grammar:
            review_reason = (
                f"Low OCR confidence ({confidence:.2f})"
                if confidence < self.min_confidence_threshold
                else f"Invalid grammar: {grammar_kind}"
            )
            # Record event as NEEDS_REVIEW without creating an active session
            self.db.execute(
                """
                INSERT INTO anpr_events
                (id, facility_id, camera_id, gate_type, plate_number, confidence, plate_crop_url,
                 processing_time_ms, status, review_reason, session_id, detected_at, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'NEEDS_REVIEW', ?, NULL, ?, ?);
                """,
                (
                    event_id,
                    facility_id,
                    camera_id,
                    gate_type,
                    normalized_plate or raw_plate,
                    confidence,
                    plate_crop,
                    processing_time_ms,
                    review_reason,
                    detected_at,
                    self._now_iso(),
                ),
            )
            return {
                "status_code": 200,
                "success": True,
                "eventId": event_id,
                "status": "NEEDS_REVIEW",
                "reviewReason": review_reason,
                "liveOccupancy": self.db.get_live_occupancy(facility_id),
                "availableCapacity": self.db.get_available_capacity(facility_id),
            }

        # 3. Check gate cooldown debouncing (120s cache per camera)
        cooldown_key = (camera_id, normalized_plate)
        last_seen = self._cooldown_cache.get(cooldown_key)
        if last_seen is not None and (now_epoch - last_seen) < self.cooldown_seconds:
            # Debounce duplicate read: record event as COOLDOWN_IGNORED without state mutation
            self.db.execute(
                """
                INSERT INTO anpr_events
                (id, facility_id, camera_id, gate_type, plate_number, confidence, plate_crop_url,
                 processing_time_ms, status, review_reason, session_id, detected_at, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'COOLDOWN_IGNORED', 'Gate debouncing window active', NULL, ?, ?);
                """,
                (
                    event_id,
                    facility_id,
                    camera_id,
                    gate_type,
                    normalized_plate,
                    confidence,
                    plate_crop,
                    processing_time_ms,
                    detected_at,
                    self._now_iso(),
                ),
            )
            return {
                "status_code": 200,
                "success": True,
                "eventId": event_id,
                "status": "COOLDOWN_IGNORED",
                "message": f"Plate {normalized_plate} ignored due to gate cooldown (120s)",
                "liveOccupancy": self.db.get_live_occupancy(facility_id),
                "availableCapacity": self.db.get_available_capacity(facility_id),
            }

        # Update cooldown cache timestamp
        self._cooldown_cache[cooldown_key] = now_epoch

        # 4. State Transitions: ENTRY or EXIT
        if gate_type == "ENTRY":
            # Check for existing active session (prevent duplicate entry)
            active_session = self.db.get_active_session(facility_id, normalized_plate)
            if active_session:
                # Vehicle already inside: cannot create duplicate active session due to partial unique index
                self.db.execute(
                    """
                    INSERT INTO anpr_events
                    (id, facility_id, camera_id, gate_type, plate_number, confidence, plate_crop_url,
                     processing_time_ms, status, review_reason, session_id, detected_at, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'COOLDOWN_IGNORED', 'Active session already exists', ?, ?, ?);
                    """,
                    (
                        event_id,
                        facility_id,
                        camera_id,
                        gate_type,
                        normalized_plate,
                        confidence,
                        plate_crop,
                        processing_time_ms,
                        active_session["id"],
                        detected_at,
                        self._now_iso(),
                    ),
                )
                return {
                    "status_code": 200,
                    "success": False,
                    "eventId": event_id,
                    "status": "DUPLICATE_ENTRY",
                    "sessionId": active_session["id"],
                    "message": f"Active session already exists for plate {normalized_plate}",
                    "liveOccupancy": self.db.get_live_occupancy(facility_id),
                    "availableCapacity": self.db.get_available_capacity(facility_id),
                }

            # Upsert vehicle record
            state_code = normalized_plate[:2] if len(normalized_plate) >= 2 else "XX"
            self.db.execute(
                """
                INSERT INTO vehicles (plate_number, state_code, vehicle_class, first_seen_at, last_seen_at, total_sessions, created_at)
                VALUES (?, ?, 'CAR', ?, ?, 1, ?)
                ON CONFLICT(plate_number) DO UPDATE SET
                    last_seen_at = excluded.last_seen_at,
                    total_sessions = total_sessions + 1;
                """,
                (normalized_plate, state_code, detected_at, detected_at, self._now_iso()),
            )

            # Create new INSIDE session
            session_id = f"ses_{uuid.uuid4().hex[:12]}"
            self.db.execute(
                """
                INSERT INTO vehicle_sessions
                (id, facility_id, plate_number, status, entry_event_id, entry_camera_id, entry_time,
                 review_status, created_at, updated_at)
                VALUES (?, ?, ?, 'INSIDE', ?, ?, ?, 'VERIFIED', ?, ?);
                """,
                (
                    session_id,
                    facility_id,
                    normalized_plate,
                    event_id,
                    camera_id,
                    detected_at,
                    self._now_iso(),
                    self._now_iso(),
                ),
            )

            # Record accepted ANPR event linked to session
            self.db.execute(
                """
                INSERT INTO anpr_events
                (id, facility_id, camera_id, gate_type, plate_number, confidence, plate_crop_url,
                 processing_time_ms, status, review_reason, session_id, detected_at, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'ACCEPTED', NULL, ?, ?, ?);
                """,
                (
                    event_id,
                    facility_id,
                    camera_id,
                    gate_type,
                    normalized_plate,
                    confidence,
                    plate_crop,
                    processing_time_ms,
                    session_id,
                    detected_at,
                    self._now_iso(),
                ),
            )

            # Synchronize authoritative observation
            self._sync_facility_observation(facility_id)

            live_occ = self.db.get_live_occupancy(facility_id)
            avail_cap = self.db.get_available_capacity(facility_id)

            return {
                "status_code": 201,
                "success": True,
                "eventId": event_id,
                "status": "ACCEPTED",
                "sessionId": session_id,
                "liveOccupancy": live_occ,
                "availableCapacity": avail_cap,
            }

        elif gate_type == "EXIT":
            # Find active INSIDE session for this vehicle
            active_session = self.db.get_active_session(facility_id, normalized_plate)
            if not active_session:
                # UNMATCHED EXIT: Do NOT decrement occupancy! Log event for operator review
                self.db.execute(
                    """
                    INSERT INTO anpr_events
                    (id, facility_id, camera_id, gate_type, plate_number, confidence, plate_crop_url,
                     processing_time_ms, status, review_reason, session_id, detected_at, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'UNMATCHED_EXIT', 'No active INSIDE session found for plate', NULL, ?, ?);
                    """,
                    (
                        event_id,
                        facility_id,
                        camera_id,
                        gate_type,
                        normalized_plate,
                        confidence,
                        plate_crop,
                        processing_time_ms,
                        detected_at,
                        self._now_iso(),
                    ),
                )
                return {
                    "status_code": 200,
                    "success": False,
                    "eventId": event_id,
                    "status": "UNMATCHED_EXIT",
                    "message": f"Unmatched exit attempt for plate {normalized_plate} logged for review",
                    "liveOccupancy": self.db.get_live_occupancy(facility_id),
                    "availableCapacity": self.db.get_available_capacity(facility_id),
                }

            # Calculate parking duration
            try:
                entry_dt = self._parse_iso(active_session["entry_time"])
                exit_dt = self._parse_iso(detected_at)
                duration_seconds = max(0, int((exit_dt - entry_dt).total_seconds()))
            except Exception:
                duration_seconds = 0

            # Calculate tariff (sample: 20 INR base + 10 INR per hour)
            hours = max(1, duration_seconds // 3600)
            tariff = float(20 + hours * 10)

            # Update session to EXITED
            self.db.execute(
                """
                UPDATE vehicle_sessions
                SET status = 'EXITED',
                    exit_event_id = ?,
                    exit_camera_id = ?,
                    exit_time = ?,
                    duration_seconds = ?,
                    calculated_tariff = ?,
                    updated_at = ?
                WHERE id = ?;
                """,
                (
                    event_id,
                    camera_id,
                    detected_at,
                    duration_seconds,
                    tariff,
                    self._now_iso(),
                    active_session["id"],
                ),
            )

            # Record accepted exit ANPR event
            self.db.execute(
                """
                INSERT INTO anpr_events
                (id, facility_id, camera_id, gate_type, plate_number, confidence, plate_crop_url,
                 processing_time_ms, status, review_reason, session_id, detected_at, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'ACCEPTED', NULL, ?, ?, ?);
                """,
                (
                    event_id,
                    facility_id,
                    camera_id,
                    gate_type,
                    normalized_plate,
                    confidence,
                    plate_crop,
                    processing_time_ms,
                    active_session["id"],
                    detected_at,
                    self._now_iso(),
                ),
            )

            # Synchronize authoritative observation
            self._sync_facility_observation(facility_id)

            live_occ = self.db.get_live_occupancy(facility_id)
            avail_cap = self.db.get_available_capacity(facility_id)

            return {
                "status_code": 200,
                "success": True,
                "eventId": event_id,
                "status": "ACCEPTED",
                "sessionId": active_session["id"],
                "durationSeconds": duration_seconds,
                "calculatedTariff": tariff,
                "liveOccupancy": live_occ,
                "availableCapacity": avail_cap,
            }

        return {
            "status_code": 400,
            "success": False,
            "error": f"Invalid gate type: {gate_type}",
        }

    # -------------------------------------------------------------------------
    # 2. Camera Heartbeat: POST /api/v1/anpr/heartbeat
    # -------------------------------------------------------------------------
    def post_camera_heartbeat(
        self,
        payload: dict[str, Any],
        headers: Optional[dict[str, str]] = None,
    ) -> dict[str, Any]:
        """Simulate POST /api/v1/anpr/heartbeat endpoint.
        
        Payload:
        {
            "cameraId": "palika-entry-1",
            "status": "ONLINE" | "OFFLINE" | "DEGRADED" | "SIMULATING",
            "fps": 24.5,
            "lastFrameAt": "2026-11-21T14:30:00.000Z"
        }
        """
        if headers is None:
            headers = {"X-ANPR-Secret": self.secret}

        if not self._authenticate(headers):
            return {
                "status_code": 401,
                "success": False,
                "error": "Unauthorized: Invalid or missing X-ANPR-Secret",
            }

        camera_id = payload.get("cameraId")
        status = payload.get("status", "ONLINE").upper()
        fps = float(payload.get("fps", 0.0))
        last_frame_at = payload.get("lastFrameAt") or self._now_iso()
        now_iso = self._now_iso()

        self.db.execute(
            """
            UPDATE parking_cameras
            SET status = ?,
                fps = ?,
                last_heartbeat_at = ?,
                updated_at = ?
            WHERE id = ?;
            """,
            (status, fps, last_frame_at, now_iso, camera_id),
        )

        return {
            "status_code": 200,
            "success": True,
            "cameraId": camera_id,
            "status": status,
            "lastHeartbeatAt": last_frame_at,
        }

    # -------------------------------------------------------------------------
    # 3. Operator Review Queue: GET /api/v1/anpr/review-queue
    # -------------------------------------------------------------------------
    def get_review_queue(
        self,
        facility_id: str,
        headers: Optional[dict[str, str]] = None,
    ) -> dict[str, Any]:
        """Retrieve items in operator verification queue (NEEDS_REVIEW & UNMATCHED_EXIT)."""
        events = self.db.query(
            """
            SELECT * FROM anpr_events
            WHERE facility_id = ? AND status IN ('NEEDS_REVIEW', 'UNMATCHED_EXIT')
            ORDER BY detected_at DESC;
            """,
            (facility_id,),
        )
        return {
            "status_code": 200,
            "success": True,
            "facilityId": facility_id,
            "items": events,
            "count": len(events),
        }

    # -------------------------------------------------------------------------
    # 4. Review Queue Resolution: POST /api/v1/anpr/review-queue/:id/resolve
    # -------------------------------------------------------------------------
    def resolve_review_item(
        self,
        event_id: str,
        action: str,
        corrected_plate: Optional[str] = None,
        notes: str = "",
        headers: Optional[dict[str, str]] = None,
    ) -> dict[str, Any]:
        """Resolve a review queue item with operator action.
        
        Actions:
        - CONFIRM_ENTRY: Corrects/confirms entry, creates active INSIDE session, increments occupancy.
        - CONFIRM_EXIT: Corrects/confirms exit, updates matching session to EXITED, decrements occupancy.
        - REJECT: Rejects the capture, updates status to REJECTED.
        """
        event = self.db.query_one("SELECT * FROM anpr_events WHERE id = ?", (event_id,))
        if not event:
            return {"status_code": 404, "success": False, "error": f"Event {event_id} not found"}

        facility_id = event["facility_id"]
        camera_id = event["camera_id"]
        plate = (corrected_plate or event["plate_number"] or "").strip().upper()
        now_iso = self._now_iso()
        action = action.upper()

        if action == "CONFIRM_ENTRY":
            # Upsert vehicle
            state_code = plate[:2] if len(plate) >= 2 else "XX"
            self.db.execute(
                """
                INSERT INTO vehicles (plate_number, state_code, vehicle_class, first_seen_at, last_seen_at, total_sessions, created_at)
                VALUES (?, ?, 'CAR', ?, ?, 1, ?)
                ON CONFLICT(plate_number) DO UPDATE SET last_seen_at = excluded.last_seen_at;
                """,
                (plate, state_code, event["detected_at"], event["detected_at"], now_iso),
            )

            # Create session
            session_id = f"ses_{uuid.uuid4().hex[:12]}"
            self.db.execute(
                """
                INSERT INTO vehicle_sessions
                (id, facility_id, plate_number, status, entry_event_id, entry_camera_id, entry_time,
                 review_status, operator_notes, created_at, updated_at)
                VALUES (?, ?, ?, 'INSIDE', ?, ?, ?, 'MANUALLY_CORRECTED', ?, ?, ?);
                """,
                (
                    session_id,
                    facility_id,
                    plate,
                    event_id,
                    camera_id,
                    event["detected_at"],
                    notes or "Resolved by operator",
                    now_iso,
                    now_iso,
                ),
            )

            # Update event
            self.db.execute(
                """
                UPDATE anpr_events
                SET status = 'MANUALLY_RESOLVED',
                    plate_number = ?,
                    session_id = ?,
                    review_reason = ?
                WHERE id = ?;
                """,
                (plate, session_id, f"CONFIRMED_ENTRY: {notes}", event_id),
            )

            self._sync_facility_observation(facility_id)
            return {
                "status_code": 200,
                "success": True,
                "action": "CONFIRM_ENTRY",
                "sessionId": session_id,
                "liveOccupancy": self.db.get_live_occupancy(facility_id),
                "availableCapacity": self.db.get_available_capacity(facility_id),
            }

        elif action == "CONFIRM_EXIT":
            # Match active session for plate
            active = self.db.get_active_session(facility_id, plate)
            session_id = active["id"] if active else None

            if active:
                entry_dt = self._parse_iso(active["entry_time"])
                exit_dt = self._parse_iso(event["detected_at"])
                duration = max(0, int((exit_dt - entry_dt).total_seconds()))
                tariff = float(20 + max(1, duration // 3600) * 10)

                self.db.execute(
                    """
                    UPDATE vehicle_sessions
                    SET status = 'EXITED',
                        exit_event_id = ?,
                        exit_camera_id = ?,
                        exit_time = ?,
                        duration_seconds = ?,
                        calculated_tariff = ?,
                        review_status = 'MANUALLY_CORRECTED',
                        operator_notes = ?,
                        updated_at = ?
                    WHERE id = ?;
                    """,
                    (
                        event_id,
                        camera_id,
                        event["detected_at"],
                        duration,
                        tariff,
                        notes or "Resolved exit by operator",
                        now_iso,
                        active["id"],
                    ),
                )

            self.db.execute(
                """
                UPDATE anpr_events
                SET status = 'MANUALLY_RESOLVED',
                    plate_number = ?,
                    session_id = ?,
                    review_reason = ?
                WHERE id = ?;
                """,
                (plate, session_id, f"CONFIRMED_EXIT: {notes}", event_id),
            )

            self._sync_facility_observation(facility_id)
            return {
                "status_code": 200,
                "success": True,
                "action": "CONFIRM_EXIT",
                "sessionId": session_id,
                "liveOccupancy": self.db.get_live_occupancy(facility_id),
                "availableCapacity": self.db.get_available_capacity(facility_id),
            }

        elif action == "REJECT":
            self.db.execute(
                """
                UPDATE anpr_events
                SET status = 'REJECTED',
                    review_reason = ?
                WHERE id = ?;
                """,
                (f"REJECTED: {notes}", event_id),
            )
            return {
                "status_code": 200,
                "success": True,
                "action": "REJECT",
                "eventId": event_id,
                "liveOccupancy": self.db.get_live_occupancy(facility_id),
            }

        return {"status_code": 400, "success": False, "error": f"Unknown action: {action}"}

    # -------------------------------------------------------------------------
    # 5. Live Occupancy Metrics: GET /api/v1/facilities/:id/occupancy
    # -------------------------------------------------------------------------
    def get_facility_occupancy(self, facility_id: str) -> dict[str, Any]:
        """Simulate GET /api/v1/facilities/:id/occupancy endpoint.
        
        Derives metrics authoritatively from database records.
        """
        facility = self.db.get_facility(facility_id)
        if not facility:
            return {"status_code": 404, "success": False, "error": f"Facility {facility_id} not found"}

        total_cap = self.db.get_facility_total_capacity(facility_id)
        live_occ = self.db.get_live_occupancy(facility_id)
        avail_cap = self.db.get_available_capacity(facility_id)
        occ_rate = round((live_occ / total_cap * 100), 2) if total_cap > 0 else 0.0

        return {
            "status_code": 200,
            "success": True,
            "facilityId": facility_id,
            "facilityName": facility["name"],
            "totalCapacity": total_cap,
            "vehiclesInside": live_occ,
            "availableCapacity": avail_cap,
            "occupancyRate": occ_rate,
            "lastUpdated": self._now_iso(),
        }
