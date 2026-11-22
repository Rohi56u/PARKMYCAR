"""
Abstract base detector interface and data structures for ANPR plate localization.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Optional, Tuple
import numpy as np


@dataclass
class DetectionResult:
    """Represents a localized license plate region."""
    box: Tuple[int, int, int, int]  # (x_min, y_min, x_max, y_max)
    confidence: float
    class_name: str = "license_plate"
    source: str = "yolo"  # "yolo" or "cv_fallback"
    padded_box: Optional[Tuple[int, int, int, int]] = None
    cropped_plate: Optional[np.ndarray] = None


def apply_padding(
    box: Tuple[int, int, int, int],
    image_shape: Tuple[int, ...],
    padding_ratio: float = 0.10,
) -> Tuple[int, int, int, int]:
    """
    Expands a bounding box (x_min, y_min, x_max, y_max) by padding_ratio on all sides,
    clamped to image dimensions.
    """
    h, w = image_shape[:2]
    x_min, y_min, x_max, y_max = box
    x1, x2 = min(x_min, x_max), max(x_min, x_max)
    y1, y2 = min(y_min, y_max), max(y_min, y_max)
    bw = x2 - x1
    bh = y2 - y1

    pad_w = int(round(bw * padding_ratio))
    pad_h = int(round(bh * padding_ratio))

    padded_x_min = max(0, min(w, x1 - pad_w))
    padded_y_min = max(0, min(h, y1 - pad_h))
    padded_x_max = max(0, min(w, x2 + pad_w))
    padded_y_max = max(0, min(h, y2 + pad_h))

    return (padded_x_min, padded_y_min, padded_x_max, padded_y_max)


def crop_plate(
    image: np.ndarray,
    box: Tuple[int, int, int, int],
    padding_ratio: float = 0.10,
) -> Tuple[np.ndarray, Tuple[int, int, int, int]]:
    """
    Crops the padded plate region from the source image.
    Returns (cropped_image, padded_box).
    """
    padded_box = apply_padding(box, image.shape, padding_ratio)
    x_min, y_min, x_max, y_max = padded_box
    crop = image[y_min:y_max, x_min:x_max]
    return crop, padded_box


class BasePlateDetector(ABC):
    """Abstract base class for license plate detectors."""

    @abstractmethod
    def detect(self, image: np.ndarray) -> List[DetectionResult]:
        """
        Detects license plates in the input BGR image.
        Returns a list of DetectionResult objects sorted by confidence descending.
        """
        pass
