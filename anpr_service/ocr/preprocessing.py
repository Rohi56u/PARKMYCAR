"""
anpr_service/ocr/preprocessing.py
Image preprocessing pipeline for Indian license plates:
- LAB CLAHE on L-channel (contrast equalization preserving chromaticity)
- Polarity detection and inversion (white, commercial yellow, EV green, rental black)
- Deskewing (tilt angle detection via minAreaRect and horizontal rectification)
- Dual-row horizontal splitting (aspect ratio + projection histogram analysis)
"""

from dataclasses import dataclass
from enum import Enum
from typing import Optional, Tuple
import cv2
import numpy as np


class PlateCategory(str, Enum):
    PRIVATE_WHITE = "PRIVATE_WHITE"
    COMMERCIAL_YELLOW = "COMMERCIAL_YELLOW"
    EV_GREEN = "EV_GREEN"
    COMMERCIAL_EV = "COMMERCIAL_EV"
    SELF_DRIVE_BLACK = "SELF_DRIVE_BLACK"
    UNKNOWN = "UNKNOWN"


@dataclass
class PreprocessingResult:
    processed_image: np.ndarray
    original_image: np.ndarray
    plate_category: PlateCategory
    was_inverted: bool
    skew_angle: float
    is_dual_row: bool
    split_crops: Optional[Tuple[np.ndarray, np.ndarray]] = None


def apply_lab_clahe(
    image: np.ndarray,
    clip_limit: float = 2.0,
    tile_grid_size: Tuple[int, int] = (8, 8),
) -> np.ndarray:
    """
    Applies CLAHE (Contrast Limited Adaptive Histogram Equalization)
    strictly to the Lightness (L) channel in LAB color space.
    Preserves chromaticity channels (A, B) without color distortion.
    """
    if image is None or image.size == 0:
        return image
    if len(image.shape) == 2:
        clahe = cv2.createCLAHE(clipLimit=clip_limit, tileGridSize=tile_grid_size)
        return clahe.apply(image)

    lab = cv2.cvtColor(image, cv2.COLOR_BGR2LAB)
    l_channel, a_channel, b_channel = cv2.split(lab)
    clahe = cv2.createCLAHE(clipLimit=clip_limit, tileGridSize=tile_grid_size)
    l_enhanced = clahe.apply(l_channel)
    merged_lab = cv2.merge((l_enhanced, a_channel, b_channel))
    return cv2.cvtColor(merged_lab, cv2.COLOR_LAB2BGR)


def detect_plate_category_and_polarity(
    image: np.ndarray,
) -> Tuple[bool, PlateCategory, float]:
    """
    Determines background vs text luminance and categorizes plate type:
    - White Private: White BG, Dark text -> Not Inverted
    - Commercial Yellow: Yellow BG, Dark text -> Not Inverted
    - EV Green: Dark Green BG, White/Yellow text -> Inverted
    - Rental Black: Black BG, Yellow text -> Inverted
    
    Returns:
        (is_inverted, plate_category, background_luminance)
    """
    if image is None or image.size == 0:
        return False, PlateCategory.UNKNOWN, 0.0

    bgr = image if len(image.shape) == 3 else cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)

    # Use 70th percentile of luminance to robustly capture plate background
    # (immune to dark character strokes and dark vehicle bumper padding margins)
    bg_luma = float(np.percentile(gray, 70))
    is_inverted = bool(bg_luma < 120.0)

    if is_inverted:
        mask = gray < 130
        mean_hsv = np.median(hsv[mask], axis=0) if np.any(mask) else np.array([0, 0, 0])
        hue, sat = float(mean_hsv[0]), float(mean_hsv[1])
        if 35 <= hue <= 85 and sat > 35:
            category = PlateCategory.EV_GREEN
        else:
            category = PlateCategory.SELF_DRIVE_BLACK
    else:
        mask = gray > 130
        mean_hsv = np.median(hsv[mask], axis=0) if np.any(mask) else np.array([0, 0, 0])
        hue, sat = float(mean_hsv[0]), float(mean_hsv[1])
        if 15 <= hue <= 40 and sat > 40:
            category = PlateCategory.COMMERCIAL_YELLOW
        else:
            category = PlateCategory.PRIVATE_WHITE

    return is_inverted, category, bg_luma


def invert_polarity_if_needed(image: np.ndarray) -> Tuple[np.ndarray, bool]:
    """
    Inverts the plate image if background is dark, ensuring OCR receives dark text on light background.
    """
    is_inverted, _, _ = detect_plate_category_and_polarity(image)
    if is_inverted:
        return cv2.bitwise_not(image), True
    return image.copy(), False


def estimate_skew_angle(image: np.ndarray, max_angle: float = 30.0) -> float:
    """
    Detects plate skew angle using character contour bounding boxes and cv2.minAreaRect.
    Returns rotation angle in degrees needed to rectify plate to horizontal.
    """
    if image is None or image.size == 0:
        return 0.0

    gray = image if len(image.shape) == 2 else cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    h_img, w_img = gray.shape

    # Adaptive binarization to extract character strokes
    thresh = cv2.adaptiveThreshold(
        gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 25, 10
    )
    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    char_pts = []
    for cnt in contours:
        x, y, w, h = cv2.boundingRect(cnt)
        if 0.20 * h_img <= h <= 0.90 * h_img and w >= 4 and w <= 0.40 * w_img:
            char_pts.append(cnt)

    if not char_pts:
        return 0.0

    all_pts = np.vstack(char_pts)
    rect = cv2.minAreaRect(all_pts)
    (cx, cy), (rw, rh), angle = rect

    # OpenCV 4.5+ angle mapping
    skew = (90.0 + angle) if rw < rh else angle

    # Clamp to reasonable bounds to avoid 90-degree disorientation
    if abs(skew) > max_angle:
        return 0.0
    return float(skew)


def deskew_plate(
    image: np.ndarray,
    skew_angle: Optional[float] = None,
    max_angle: float = 30.0,
) -> Tuple[np.ndarray, float]:
    """
    Rotates plate image around center to align characters horizontally.
    """
    if image is None or image.size == 0:
        return image, 0.0

    angle = skew_angle if skew_angle is not None else estimate_skew_angle(image, max_angle)
    if abs(angle) < 0.5:
        return image.copy(), 0.0

    h, w = image.shape[:2]
    center = (w // 2, h // 2)
    m = cv2.getRotationMatrix2D(center, angle, 1.0)
    rotated = cv2.warpAffine(
        image,
        m,
        (w, h),
        flags=cv2.INTER_CUBIC,
        borderMode=cv2.BORDER_REPLICATE,
    )
    return rotated, angle


def detect_dual_row(
    image: np.ndarray,
    aspect_ratio_threshold: float = 0.40,
) -> Tuple[bool, Optional[int]]:
    """
    Detects if plate is two-row (two-wheelers, trucks, auto-rickshaws)
    via aspect ratio (height / width >= 0.40) and horizontal projection histogram valley.
    
    Returns:
        (is_dual_row, split_row_y_index)
    """
    if image is None or image.size == 0:
        return False, None

    h, w = image.shape[:2]
    aspect_ratio = float(h) / float(w)
    if aspect_ratio < aspect_ratio_threshold:
        return False, None

    gray = image if len(image.shape) == 2 else cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)

    # Horizontal projection histogram (row sum)
    h_proj = np.sum(binary == 255, axis=1)

    # Search for valley in middle row band (35% to 65% of height)
    mid_s = int(h * 0.35)
    mid_e = int(h * 0.65)
    if mid_e <= mid_s:
        return False, None

    valley_offset = int(np.argmin(h_proj[mid_s:mid_e]))
    split_y = mid_s + valley_offset
    valley_val = h_proj[split_y]

    peak_top = np.max(h_proj[:split_y]) if split_y > 0 else 0
    peak_bot = np.max(h_proj[split_y:]) if split_y < h else 0

    # Ensure valley is significantly lower than both peaks
    if peak_top > 0 and peak_bot > 0 and valley_val < 0.40 * min(peak_top, peak_bot):
        return True, split_y

    return False, None


def split_dual_row(
    image: np.ndarray,
    split_y: Optional[int] = None,
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Splits a dual-row plate into (top_crop, bottom_crop).
    """
    h = image.shape[0]
    if split_y is None:
        _, detected_y = detect_dual_row(image)
        split_y = detected_y if detected_y is not None else h // 2

    top_crop = image[0:split_y, :]
    bottom_crop = image[split_y:h, :]
    return top_crop, bottom_crop


def stitch_dual_row_horizontal(
    top_crop: np.ndarray,
    bottom_crop: np.ndarray,
    spacer_px: int = 15,
) -> np.ndarray:
    """
    Stitches top and bottom rows horizontally into a synthetic single-line plate crop.
    Pads the shorter crop to target_h using border padding (cv2.copyMakeBorder),
    preserving exact character glyph heights across rows.
    """
    if top_crop is None:
        return bottom_crop
    if bottom_crop is None:
        return top_crop

    if top_crop.size == 0 or top_crop.shape[0] == 0:
        return bottom_crop
    if bottom_crop.size == 0 or bottom_crop.shape[0] == 0:
        return top_crop

    target_h = max(top_crop.shape[0], bottom_crop.shape[0])

    def pad_to_height(crop: np.ndarray, th: int) -> np.ndarray:
        ch = crop.shape[0]
        if ch >= th:
            return crop
        pad_total = th - ch
        pad_top = pad_total // 2
        pad_bot = pad_total - pad_top
        color = (255, 255, 255) if len(crop.shape) == 3 else 255
        return cv2.copyMakeBorder(crop, pad_top, pad_bot, 0, 0, cv2.BORDER_CONSTANT, value=color)

    top_padded = pad_to_height(top_crop, target_h)
    bot_padded = pad_to_height(bottom_crop, target_h)

    # Whitespace spacer
    channels = 3 if len(top_crop.shape) == 3 else 1
    if channels == 3:
        spacer = np.full((target_h, spacer_px, 3), 255, dtype=np.uint8)
    else:
        spacer = np.full((target_h, spacer_px), 255, dtype=np.uint8)

    return np.hstack([top_padded, spacer, bot_padded])


def preprocess_plate(
    image: np.ndarray,
    deskew: bool = True,
    normalize_polarity: bool = True,
    handle_dual_row: bool = True,
) -> PreprocessingResult:
    """
    Full end-to-end preprocessing pipeline for Indian license plates.
    1. LAB CLAHE enhancement on L-channel.
    2. Polarity detection and inversion for EV/Commercial/Rental plates.
    3. Deskewing via character contour alignment.
    4. Dual-row detection and splitting.
    """
    if image is None or image.size == 0:
        return PreprocessingResult(
            processed_image=image,
            original_image=image,
            plate_category=PlateCategory.UNKNOWN,
            was_inverted=False,
            skew_angle=0.0,
            is_dual_row=False,
        )

    orig = image.copy()
    # Step 1: LAB CLAHE
    enhanced = apply_lab_clahe(image)

    # Step 2: Polarity detection & normalization
    was_inverted = False
    category = PlateCategory.UNKNOWN
    if normalize_polarity:
        is_inv, category, _ = detect_plate_category_and_polarity(enhanced)
        if is_inv:
            enhanced = cv2.bitwise_not(enhanced)
            was_inverted = True

    # Step 3: Deskewing
    skew_angle = 0.0
    if deskew:
        enhanced, skew_angle = deskew_plate(enhanced)

    # Step 4: Dual-row handling
    is_dual = False
    split_crops = None
    if handle_dual_row:
        is_dual, split_y = detect_dual_row(enhanced)
        if is_dual and split_y is not None:
            top_half, bot_half = split_dual_row(enhanced, split_y)
            split_crops = (top_half, bot_half)
            # Horizontally stitched single-line representation
            enhanced = stitch_dual_row_horizontal(top_half, bot_half)

    return PreprocessingResult(
        processed_image=enhanced,
        original_image=orig,
        plate_category=category,
        was_inverted=was_inverted,
        skew_angle=skew_angle,
        is_dual_row=is_dual,
        split_crops=split_crops,
    )
