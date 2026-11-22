"""
Morphological Edge & Contour Computer Vision Plate Detector.
Acts as a zero-dependency fallback when deep learning models are missing or yield low confidence.
"""
from typing import List, Tuple
import cv2
import numpy as np

from anpr_service.detector.base import (
    BasePlateDetector,
    DetectionResult,
    apply_padding,
    crop_plate,
)


class MorphologicalPlateDetector(BasePlateDetector):
    """
    Morphological edge and contour license plate detector.
    Identifies rectangular license plate regions using horizontal gradient (Sobel-X)
    and rectangular kernel closing to fuse vertical character strokes.
    """

    def __init__(
        self,
        min_aspect_ratio: float = 1.8,
        max_aspect_ratio: float = 5.8,
        min_area: int = 1200,
        max_area_ratio: float = 0.25,
        padding_ratio: float = 0.10,
        max_candidates: int = 5,
    ):
        self.min_aspect_ratio = min_aspect_ratio
        self.max_aspect_ratio = max_aspect_ratio
        self.min_area = min_area
        self.max_area_ratio = max_area_ratio
        self.padding_ratio = padding_ratio
        self.max_candidates = max_candidates

    def detect(self, image: np.ndarray) -> List[DetectionResult]:
        if image is None or image.size == 0:
            return []

        h, w = image.shape[:2]
        max_area = int(h * w * self.max_area_ratio)

        # 1. Grayscale & Noise reduction
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image.copy()

        blurred = cv2.GaussianBlur(gray, (5, 5), 0)

        # 2. Horizontal gradient (Sobel-X) detects vertical strokes
        sobel_x = cv2.Sobel(blurred, cv2.CV_16S, 1, 0, ksize=3)
        abs_sobel_x = cv2.convertScaleAbs(sobel_x)

        # 3. Morphological closing with horizontal rectangular kernel
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (33, 5))
        closed = cv2.morphologyEx(abs_sobel_x, cv2.MORPH_CLOSE, kernel)

        # 4. Otsu's thresholding
        _, thresh = cv2.threshold(closed, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

        # 5. Dilation to connect broken horizontal regions
        thresh = cv2.dilate(thresh, cv2.getStructuringElement(cv2.MORPH_RECT, (11, 3)), iterations=1)

        # 6. Find external contours
        contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        candidates = []
        for c in contours:
            x, y, bw, bh = cv2.boundingRect(c)
            if bh == 0:
                continue

            aspect_ratio = bw / float(bh)
            area = bw * bh

            if not (self.min_aspect_ratio <= aspect_ratio <= self.max_aspect_ratio):
                continue
            if not (self.min_area <= area <= max_area):
                continue

            # Rectangular solidity check
            c_area = cv2.contourArea(c)
            solidity = c_area / float(area) if area > 0 else 0
            if solidity < 0.25:
                continue

            # Heuristic score based on closeness to ideal single-row (4.0) or dual-row (2.0) aspect ratio
            ar_diff_single = abs(aspect_ratio - 4.0)
            ar_diff_dual = abs(aspect_ratio - 2.0)
            ar_score = max(0.5, 1.0 - min(ar_diff_single, ar_diff_dual) * 0.15)
            confidence = round(float(np.clip(0.60 + 0.30 * ar_score * solidity, 0.50, 0.90)), 3)

            box = (x, y, x + bw, y + bh)
            cropped, padded_box = crop_plate(image, box, self.padding_ratio)

            candidates.append(
                DetectionResult(
                    box=box,
                    confidence=confidence,
                    class_name="license_plate",
                    source="cv_fallback",
                    padded_box=padded_box,
                    cropped_plate=cropped,
                )
            )

        # Sort by confidence descending, take top candidates
        candidates.sort(key=lambda d: d.confidence, reverse=True)
        return candidates[: self.max_candidates]
