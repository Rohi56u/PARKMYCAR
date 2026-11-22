"""
Multi-frame Vehicle Tracking and Voting Quorum Accumulator.
Aggregates detections across a temporal sliding window (default 2.5s) to eliminate
transient glints, shadows, and low-confidence single-frame anomalies.
"""
from collections import Counter
from dataclasses import dataclass, field
import time
from typing import Dict, List, Optional, Tuple


@dataclass
class FrameDetection:
    """Represents a single-frame plate detection."""
    plate_number: str
    confidence: float
    timestamp: float
    bbox: Optional[Tuple[int, int, int, int]] = None
    metadata: Dict = field(default_factory=dict)


@dataclass
class VotingQuorumResult:
    """Consensus output after multi-frame sliding window voting."""
    winner_plate: str
    vote_count: int
    total_frames: int
    confidence: float
    consensus_reached: bool
    detections: List[FrameDetection]


class MultiFrameVehicleTracker:
    """
    Temporal sliding window aggregator for camera streams.
    Vehicles approaching a barrier spend 1-4 seconds in view.
    This accumulator groups frames within `window_seconds` and picks the consensus winner.
    """

    def __init__(
        self,
        window_seconds: float = 2.5,
        min_votes_required: int = 2,
        min_consensus_ratio: float = 0.50,
    ):
        self.window_seconds = window_seconds
        self.min_votes_required = min_votes_required
        self.min_consensus_ratio = min_consensus_ratio
        # camera_id -> list of FrameDetection
        self._windows: Dict[str, List[FrameDetection]] = {}

    def add_detection(
        self,
        camera_id: str,
        plate_number: str,
        confidence: float,
        timestamp: Optional[float] = None,
        bbox: Optional[Tuple[int, int, int, int]] = None,
        metadata: Optional[Dict] = None,
    ) -> None:
        """Adds a detection to the camera's temporal window."""
        t = timestamp if timestamp is not None else time.time()
        if camera_id not in self._windows:
            self._windows[camera_id] = []

        self._windows[camera_id].append(
            FrameDetection(
                plate_number=plate_number.upper().strip(),
                confidence=confidence,
                timestamp=t,
                bbox=bbox,
                metadata=metadata or {},
            )
        )
        self._prune_window(camera_id, t)

    def _prune_window(self, camera_id: str, current_time: float) -> None:
        """Removes detections older than window_seconds."""
        cutoff = current_time - self.window_seconds
        self._windows[camera_id] = [
            d for d in self._windows[camera_id] if d.timestamp >= cutoff
        ]

    def evaluate_quorum(
        self,
        camera_id: str,
        current_time: Optional[float] = None,
    ) -> Optional[VotingQuorumResult]:
        """
        Evaluates the current window for a consensus winner.
        Returns VotingQuorumResult if a winner reaches the quorum threshold, else None.
        """
        now = current_time if current_time is not None else time.time()
        self._prune_window(camera_id, now)

        frames = self._windows.get(camera_id, [])
        if not frames:
            return None

        total_frames = len(frames)
        if total_frames < self.min_votes_required:
            return None

        # Count votes per normalized plate string
        counts = Counter(d.plate_number for d in frames)
        winner_plate, winner_votes = counts.most_common(1)[0]

        # Calculate average confidence of the winner's detections
        winner_confs = [d.confidence for d in frames if d.plate_number == winner_plate]
        avg_confidence = sum(winner_confs) / len(winner_confs) if winner_confs else 0.0

        consensus_ratio = winner_votes / total_frames
        consensus_reached = (
            winner_votes >= self.min_votes_required
            and consensus_ratio >= self.min_consensus_ratio
        )

        return VotingQuorumResult(
            winner_plate=winner_plate,
            vote_count=winner_votes,
            total_frames=total_frames,
            confidence=round(avg_confidence, 4),
            consensus_reached=consensus_reached,
            detections=frames,
        )

    def clear_camera(self, camera_id: str) -> None:
        """Flushes the detection window for a camera (e.g. after gate opening)."""
        if camera_id in self._windows:
            self._windows[camera_id].clear()
