"""
Gate Cooldown and Debouncing Manager.
Prevents repeated vehicle reads within the statutory cooldown window (120s by default).
"""
import time
from typing import Dict, Optional, Tuple


class GateCooldownManager:
    """
    In-memory gate cooldown debouncer.
    Tracks (camera_id, plate_number) -> last_seen_timestamp.
    """

    def __init__(self, cooldown_seconds: float = 120.0):
        self.cooldown_seconds = cooldown_seconds
        self._cache: Dict[Tuple[str, str], float] = {}

    def should_debounce(
        self,
        camera_id: str,
        plate_number: str,
        current_time: Optional[float] = None,
    ) -> bool:
        """
        Returns True if the vehicle was detected at this camera within cooldown_seconds.
        """
        now = current_time if current_time is not None else time.time()
        key = (camera_id, plate_number.upper().strip())
        last_seen = self._cache.get(key)

        if last_seen is not None and (now - last_seen) < self.cooldown_seconds:
            return True
        return False

    def record_detection(
        self,
        camera_id: str,
        plate_number: str,
        current_time: Optional[float] = None,
    ) -> None:
        """
        Updates the cooldown cache with the current timestamp.
        """
        now = current_time if current_time is not None else time.time()
        key = (camera_id, plate_number.upper().strip())
        self._cache[key] = now

    def reset(self) -> None:
        """Clears the debouncing cache."""
        self._cache.clear()

    def prune_expired(self, current_time: Optional[float] = None) -> int:
        """Removes entries older than 2x cooldown_seconds to prevent memory leaks."""
        now = current_time if current_time is not None else time.time()
        expiry_limit = now - (self.cooldown_seconds * 2)
        expired_keys = [k for k, v in self._cache.items() if v < expiry_limit]
        for k in expired_keys:
            del self._cache[k]
        return len(expired_keys)
