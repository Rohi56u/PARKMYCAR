"""
Tests for ANPR service configuration and settings.
"""
from anpr_service.config import ANPRSettings, settings


def test_config_defaults():
    """Verify statutory defaults and required thresholds."""
    assert settings.SERVICE_NAME == "ParkMyCar ANPR Service"
    assert settings.DETECTION_CONFIDENCE_THRESHOLD == 0.50
    assert settings.BBOX_PADDING_RATIO == 0.10
    assert settings.OCR_MIN_CONFIDENCE == 0.75
    assert settings.ENABLE_CV_FALLBACK is True
    assert settings.GATE_COOLDOWN_SECONDS == 120
    assert settings.VOTING_WINDOW_SECONDS == 2.5
    assert settings.HEARTBEAT_INTERVAL_SECONDS == 15
    assert settings.CV_MIN_ASPECT_RATIO == 1.8
    assert settings.CV_MAX_ASPECT_RATIO == 5.8


def test_config_custom_instantiation():
    """Verify custom settings overrides."""
    custom = ANPRSettings(
        DETECTION_CONFIDENCE_THRESHOLD=0.65,
        BBOX_PADDING_RATIO=0.15,
        OCR_MIN_CONFIDENCE=0.80,
        DEFAULT_FACILITY_ID="connaught-place-1",
    )
    assert custom.DETECTION_CONFIDENCE_THRESHOLD == 0.65
    assert custom.BBOX_PADDING_RATIO == 0.15
    assert custom.OCR_MIN_CONFIDENCE == 0.80
    assert custom.DEFAULT_FACILITY_ID == "connaught-place-1"
