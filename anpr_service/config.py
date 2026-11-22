"""
Central ANPR Service Configuration using pydantic_settings.
"""
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field


class ANPRSettings(BaseSettings):
    """Configuration settings for ParkMyCar ANPR Service."""
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    # Service identity
    SERVICE_NAME: str = "ParkMyCar ANPR Service"
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    DEBUG: bool = False

    # Security & API Integration
    ANPR_SHARED_SECRET: str = Field(default="test-anpr-secret", alias="ANPR_SHARED_SECRET")
    PARKMYCAR_API_URL: str = Field(default="http://localhost:3000/api/v1", alias="PARKMYCAR_API_URL")
    DEFAULT_FACILITY_ID: str = Field(default="palika", alias="DEFAULT_FACILITY_ID")

    # Detection Pipeline Thresholds
    DETECTOR_MODEL_PATH: str = Field(default="models/plate_detector.pt", alias="ANPR_MODEL_PATH")
    DETECTION_CONFIDENCE_THRESHOLD: float = 0.50
    BBOX_PADDING_RATIO: float = 0.10  # 10% bounding box padding
    ENABLE_CV_FALLBACK: bool = True

    # Morphological CV Parameters
    CV_MIN_ASPECT_RATIO: float = 1.8
    CV_MAX_ASPECT_RATIO: float = 5.8
    CV_MIN_AREA: int = 1200
    CV_MAX_AREA_RATIO: float = 0.25

    # OCR & Validation Thresholds
    OCR_MIN_CONFIDENCE: float = 0.75  # Reads < 0.75 flagged as NEEDS_REVIEW
    OCR_MAX_CANDIDATES: int = 3

    # Gate & Temporal Tracking Parameters
    GATE_COOLDOWN_SECONDS: int = 120  # 120s debouncing
    VOTING_WINDOW_SECONDS: float = 2.5  # 2.5s multi-frame voting
    HEARTBEAT_INTERVAL_SECONDS: int = 15


settings = ANPRSettings()
