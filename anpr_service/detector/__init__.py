"""
License Plate Detection Subpackage.
"""
from typing import Optional

from anpr_service.detector.base import (
    BasePlateDetector,
    DetectionResult,
    apply_padding,
    crop_plate,
)
from anpr_service.detector.cv_fallback import MorphologicalPlateDetector
from anpr_service.detector.yolo import YOLOPlateDetector


def create_detector(
    model_path: Optional[str] = None,
    confidence_threshold: float = 0.50,
    padding_ratio: float = 0.10,
    enable_fallback: bool = True,
) -> BasePlateDetector:
    """Factory helper to instantiate a configured plate detector."""
    return YOLOPlateDetector(
        model_path=model_path,
        confidence_threshold=confidence_threshold,
        padding_ratio=padding_ratio,
        enable_fallback=enable_fallback,
    )


__all__ = [
    "BasePlateDetector",
    "DetectionResult",
    "MorphologicalPlateDetector",
    "YOLOPlateDetector",
    "apply_padding",
    "crop_plate",
    "create_detector",
]
