"""ParkMyCar E2E Test Harness & Fixtures.

Exports:
    - DatabaseAdapter: Standalone SQLite D1 schema manager.
    - PlateGenerator: Indian registration plate synthesizer (HSRP, BH, etc.).
    - PlateCropGenerator: Synthetic plate crop image synthesizer.
    - E2EApiClient: In-process API simulation client.
    - CameraSimulator: Polymorphic camera feed emulator.
"""

from .db_adapter import DatabaseAdapter
from .mock_frames import PlateGenerator, PlateCropGenerator
from .api_client import E2EApiClient
from .camera_sim import CameraSimulator

__all__ = [
    "DatabaseAdapter",
    "PlateGenerator",
    "PlateCropGenerator",
    "E2EApiClient",
    "CameraSimulator",
]
