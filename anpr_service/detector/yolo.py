"""
YOLO License Plate Detector with graceful offline fallback to Morphological CV.
"""
import os
import logging
from typing import List, Optional
import numpy as np

from anpr_service.detector.base import BasePlateDetector, DetectionResult, crop_plate
from anpr_service.detector.cv_fallback import MorphologicalPlateDetector

logger = logging.getLogger(__name__)


class YOLOPlateDetector(BasePlateDetector):
    """
    YOLOv8-based license plate detector.
    Guards model loading with local file existence checks.
    Gracefully falls back to MorphologicalPlateDetector when weights are missing
    or unreadable, preventing unhandled network/403 errors in offline environments.
    """

    def __init__(
        self,
        model_path: Optional[str] = None,
        confidence_threshold: float = 0.50,
        padding_ratio: float = 0.10,
        enable_fallback: bool = True,
        fallback_detector: Optional[BasePlateDetector] = None,
    ):
        self.model_path = model_path
        self.confidence_threshold = confidence_threshold
        self.padding_ratio = padding_ratio
        self.enable_fallback = enable_fallback
        self.fallback = fallback_detector or MorphologicalPlateDetector(padding_ratio=padding_ratio)
        self.model = None
        self.is_loaded = False

        self._init_model()

    def _init_model(self) -> None:
        """Safely initialize YOLO model only if weights exist locally."""
        if not self.model_path:
            logger.info("No YOLO model_path specified; using morphological CV detector.")
            return

        if not os.path.exists(self.model_path):
            logger.warning(
                f"YOLO weights not found at '{self.model_path}'. "
                "Running in fallback mode (MorphologicalPlateDetector)."
            )
            return

        try:
            from ultralytics import YOLO
            self.model = YOLO(self.model_path)
            self.is_loaded = True
            logger.info(f"Loaded YOLO license plate detector from '{self.model_path}'.")
        except Exception as e:
            logger.warning(f"Failed to load YOLO model from '{self.model_path}': {e}. Using fallback.")
            self.is_loaded = False

    def detect(self, image: np.ndarray) -> List[DetectionResult]:
        """
        Detects license plates in the input BGR image.
        Uses YOLO model if loaded; otherwise delegates to morphological CV fallback.
        """
        if image is None or image.size == 0:
            return []

        if not self.is_loaded or self.model is None:
            if self.enable_fallback and self.fallback:
                return self.fallback.detect(image)
            return []

        try:
            results = self.model(image, conf=self.confidence_threshold, verbose=False)
            detections = []
            for r in results:
                boxes = r.boxes
                for box in boxes:
                    xyxy = box.xyxy[0].cpu().numpy().astype(int)
                    conf = float(box.conf[0].cpu().numpy())
                    raw_box = (int(xyxy[0]), int(xyxy[1]), int(xyxy[2]), int(xyxy[3]))
                    cropped, padded_box = crop_plate(image, raw_box, self.padding_ratio)

                    detections.append(
                        DetectionResult(
                            box=raw_box,
                            confidence=conf,
                            class_name="license_plate",
                            source="yolo",
                            padded_box=padded_box,
                            cropped_plate=cropped,
                        )
                    )

            if not detections and self.enable_fallback and self.fallback:
                return self.fallback.detect(image)

            detections.sort(key=lambda d: d.confidence, reverse=True)
            return detections
        except Exception as e:
            logger.warning(f"Error during YOLO inference: {e}. Attempting CV fallback.")
            if self.enable_fallback and self.fallback:
                return self.fallback.detect(image)
            return []
