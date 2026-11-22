"""Pytest Fixtures for ParkMyCar E2E Test Suite.

Provides isolated test fixtures:
- fresh_db: Fresh in-memory SQLite database adapter with D1 schema & defaults.
- api_client: In-process E2E API client.
- mock_generator: Pair of PlateGenerator & PlateCropGenerator.
- camera_sim: CameraSimulator configured for palika entry gate.
- exit_camera_sim: CameraSimulator configured for palika exit gate.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure project root is on sys.path for robust module discovery across environments
_project_root = Path(__file__).resolve().parent.parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

_e2e_root = Path(__file__).resolve().parent
if str(_e2e_root) not in sys.path:
    sys.path.insert(0, str(_e2e_root))

import pytest

try:
    from tests.e2e.harness.api_client import E2EApiClient
    from tests.e2e.harness.camera_sim import CameraSimulator
    from tests.e2e.harness.db_adapter import DatabaseAdapter
    from tests.e2e.harness.mock_frames import PlateCropGenerator, PlateGenerator
except ImportError:
    from harness.api_client import E2EApiClient
    from harness.camera_sim import CameraSimulator
    from harness.db_adapter import DatabaseAdapter
    from harness.mock_frames import PlateCropGenerator, PlateGenerator


@pytest.fixture
def fresh_db():
    """Yield an isolated, clean in-memory SQLite database instance for each test."""
    adapter = DatabaseAdapter(":memory:")
    yield adapter
    adapter.close()


@pytest.fixture
def api_client(fresh_db):
    """Yield an in-process E2EApiClient attached to the fresh test database."""
    client = E2EApiClient(
        db=fresh_db,
        secret="test-anpr-secret-token-2026",
        cooldown_seconds=120.0,
        min_confidence_threshold=0.80,
    )
    yield client


@pytest.fixture
def mock_generator():
    """Yield plate text and image crop generator classes."""
    class MockGeneratorBundle:
        plate = PlateGenerator
        crop = PlateCropGenerator

    return MockGeneratorBundle()


@pytest.fixture
def camera_sim(api_client, fresh_db):
    """Yield a CameraSimulator for palika-entry-1."""
    sim = CameraSimulator(
        camera_id="palika-entry-1",
        facility_id="palika",
        gate_type="ENTRY",
        feed_type="SIMULATION",
        fps=25.0,
        api_client=api_client,
        db=fresh_db,
    )
    yield sim


@pytest.fixture
def exit_camera_sim(api_client, fresh_db):
    """Yield a CameraSimulator for palika-exit-1."""
    sim = CameraSimulator(
        camera_id="palika-exit-1",
        facility_id="palika",
        gate_type="EXIT",
        feed_type="SIMULATION",
        fps=25.0,
        api_client=api_client,
        db=fresh_db,
    )
    yield sim
