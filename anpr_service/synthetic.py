"""
Synthetic Indian Registration Plate Generator for ANPR Testing.
Generates realistic Indian HSRP and BH registration plates with authentic DIN 1451 typography,
accurate color palettes, single-row and dual-row layouts, and environmental perturbations.
"""
import os
import random
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Tuple

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont


class PlateColorTheme(str, Enum):
    PRIVATE_WHITE = "PRIVATE_WHITE"          # White bg, Black text
    COMMERCIAL_YELLOW = "COMMERCIAL_YELLOW"  # Yellow bg, Black text
    EV_GREEN = "EV_GREEN"                    # Green bg, White text
    COMMERCIAL_EV = "COMMERCIAL_EV"          # Green bg, Yellow text
    RENTAL_BLACK = "RENTAL_BLACK"            # Black bg, Yellow text
    BHARAT_SERIES = "BHARAT_SERIES"          # White bg, Black text
    DIPLOMATIC_BLUE = "DIPLOMATIC_BLUE"      # Blue bg, White text
    TEMPORARY_YELLOW = "TEMPORARY_YELLOW"    # Yellow bg, Red text


class PlateLayout(str, Enum):
    SINGLE_ROW = "SINGLE_ROW"  # 500x120 mm aspect ratio (~4.16:1)
    DUAL_ROW = "DUAL_ROW"      # 200x100 mm aspect ratio (~2.0:1)


class DistortionType(str, Enum):
    GAUSSIAN_BLUR = "GAUSSIAN_BLUR"
    POISSON_NOISE = "POISSON_NOISE"
    PERSPECTIVE_WARP = "PERSPECTIVE_WARP"
    ILLUMINATION_GRADIENT = "ILLUMINATION_GRADIENT"
    ROAD_GRIME = "ROAD_GRIME"


@dataclass
class DistortionConfig:
    enabled: bool = True
    distortions: List[DistortionType] = field(
        default_factory=lambda: [
            DistortionType.GAUSSIAN_BLUR,
            DistortionType.POISSON_NOISE,
            DistortionType.PERSPECTIVE_WARP,
            DistortionType.ILLUMINATION_GRADIENT,
        ]
    )
    blur_kernel_range: Tuple[int, int] = (3, 7)
    noise_sigma_range: Tuple[float, float] = (5.0, 15.0)
    perspective_tilt_deg: float = 12.0
    illumination_range: Tuple[float, float] = (0.7, 1.3)


@dataclass
class SyntheticPlateResult:
    image: np.ndarray  # OpenCV BGR image
    plate_number: str
    theme: PlateColorTheme
    layout: PlateLayout
    state_code: str
    distortions_applied: List[DistortionType]
    metadata: Dict


class SyntheticPlateGenerator:
    """Generates realistic Indian HSRP and BH plates with authentic DIN 1451 typography."""

    THEME_COLORS = {
        PlateColorTheme.PRIVATE_WHITE: {
            "bg": (245, 245, 245), "text": (20, 20, 20), "border": (20, 20, 20)
        },
        PlateColorTheme.COMMERCIAL_YELLOW: {
            "bg": (245, 200, 25), "text": (20, 20, 20), "border": (20, 20, 20)
        },
        PlateColorTheme.EV_GREEN: {
            "bg": (20, 110, 50), "text": (245, 245, 245), "border": (245, 245, 245)
        },
        PlateColorTheme.COMMERCIAL_EV: {
            "bg": (20, 110, 50), "text": (245, 200, 25), "border": (245, 200, 25)
        },
        PlateColorTheme.RENTAL_BLACK: {
            "bg": (25, 25, 25), "text": (245, 200, 25), "border": (245, 200, 25)
        },
        PlateColorTheme.BHARAT_SERIES: {
            "bg": (245, 245, 245), "text": (20, 20, 20), "border": (20, 20, 20)
        },
        PlateColorTheme.DIPLOMATIC_BLUE: {
            "bg": (40, 100, 180), "text": (245, 245, 245), "border": (245, 245, 245)
        },
        PlateColorTheme.TEMPORARY_YELLOW: {
            "bg": (245, 200, 25), "text": (200, 30, 30), "border": (200, 30, 30)
        },
    }

    def __init__(self, font_path: Optional[str] = None):
        # Prefer statutory DIN 1451 font (Bahnschrift on Windows)
        candidate_fonts = [
            font_path,
            "C:/Windows/Fonts/bahnschrift.ttf",
            "C:/Windows/Fonts/arial.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        ]
        self.resolved_font_path = None
        for p in candidate_fonts:
            if p and os.path.exists(p):
                self.resolved_font_path = p
                break

    def _get_font(self, size: int) -> ImageFont.FreeTypeFont:
        if self.resolved_font_path:
            return ImageFont.truetype(self.resolved_font_path, size)
        return ImageFont.load_default()

    def generate(
        self,
        plate_number: str,
        theme: PlateColorTheme = PlateColorTheme.PRIVATE_WHITE,
        layout: PlateLayout = PlateLayout.SINGLE_ROW,
        distortion_cfg: Optional[DistortionConfig] = None,
    ) -> SyntheticPlateResult:
        palette = self.THEME_COLORS[theme]

        if layout == PlateLayout.SINGLE_ROW:
            width, height = 440, 105
            img = Image.new("RGB", (width, height), palette["bg"])
            draw = ImageDraw.Draw(img)

            # HSRP blue strip
            strip_w = 42
            draw.rectangle([0, 0, strip_w, height], fill=(20, 60, 160))
            ind_font = self._get_font(15)
            draw.text((10, height - 32), "IND", fill=(255, 255, 255), font=ind_font)
            # Ashok Chakra gold circle
            draw.ellipse([14, 20, 28, 34], outline=(240, 200, 40), width=2)

            # Text rendering with DIN 1451
            main_font = self._get_font(52)
            formatted = self._format_plate_spacing(plate_number)
            draw.text((strip_w + 18, 22), formatted, fill=palette["text"], font=main_font)
            # Outer border
            draw.rounded_rectangle([2, 2, width - 3, height - 3], radius=6, outline=palette["border"], width=2)

        else:  # DUAL_ROW
            width, height = 300, 180
            img = Image.new("RGB", (width, height), palette["bg"])
            draw = ImageDraw.Draw(img)

            # HSRP blue strip on left
            strip_w = 34
            draw.rectangle([0, 0, strip_w, height], fill=(20, 60, 160))
            ind_font = self._get_font(13)
            draw.text((6, height - 30), "IND", fill=(255, 255, 255), font=ind_font)

            main_font = self._get_font(46)
            row1, row2 = self._split_dual_row(plate_number)
            draw.text((strip_w + 16, 20), row1, fill=palette["text"], font=main_font)
            draw.text((strip_w + 16, 95), row2, fill=palette["text"], font=main_font)
            draw.rounded_rectangle([2, 2, width - 3, height - 3], radius=6, outline=palette["border"], width=2)

        # Convert to OpenCV BGR
        cv_img = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)

        applied: List[DistortionType] = []
        if distortion_cfg and distortion_cfg.enabled:
            cv_img, applied = self._apply_distortions(cv_img, distortion_cfg)

        state = plate_number[:2] if len(plate_number) >= 2 else "UNKNOWN"
        return SyntheticPlateResult(
            image=cv_img,
            plate_number=plate_number,
            theme=theme,
            layout=layout,
            state_code=state,
            distortions_applied=applied,
            metadata={"width": width, "height": height, "font": self.resolved_font_path}
        )

    def _format_plate_spacing(self, plate: str) -> str:
        # DL01AB1234 -> DL 01 AB 1234
        if len(plate) == 10 and plate[:2].isalpha() and plate[2:4].isdigit() and plate[4:6].isalpha():
            return f"{plate[:2]} {plate[2:4]} {plate[4:6]} {plate[6:]}"
        elif len(plate) == 10 and plate[:2].isdigit() and plate[2:4] == "BH":
            return f"{plate[:2]} BH {plate[4:8]} {plate[8:]}"
        elif len(plate) == 9 and plate[:2].isalpha() and plate[2:4].isdigit() and plate[4:5].isalpha():
            return f"{plate[:2]} {plate[2:4]} {plate[4:5]} {plate[5:]}"
        return plate

    def _split_dual_row(self, plate: str) -> Tuple[str, str]:
        # Split into Row 1 (State + RTO) and Row 2 (Series + Number)
        if len(plate) >= 8:
            # If standard plate (e.g. DL01AB1234), row1=DL01, row2=AB1234
            if plate[:2].isalpha() and plate[2:4].isdigit():
                return f"{plate[:2]} {plate[2:4]}", plate[4:]
            return plate[:4], plate[4:]
        mid = len(plate) // 2
        return plate[:mid], plate[mid:]

    def _apply_distortions(
        self, img: np.ndarray, cfg: DistortionConfig
    ) -> Tuple[np.ndarray, List[DistortionType]]:
        h, w = img.shape[:2]
        out = img.copy()
        applied = []

        for d in cfg.distortions:
            if d == DistortionType.ILLUMINATION_GRADIENT:
                grad = np.linspace(cfg.illumination_range[0], cfg.illumination_range[1], w).reshape(1, w, 1)
                out = np.clip(out.astype(np.float32) * grad, 0, 255).astype(np.uint8)
                applied.append(d)

            elif d == DistortionType.GAUSSIAN_BLUR:
                k = random.choice([3, 5])
                out = cv2.GaussianBlur(out, (k, k), random.uniform(0.8, 1.8))
                applied.append(d)

            elif d == DistortionType.POISSON_NOISE:
                noise = np.random.normal(0, random.uniform(cfg.noise_sigma_range[0], cfg.noise_sigma_range[1]), out.shape)
                out = np.clip(out.astype(np.float32) + noise, 0, 255).astype(np.uint8)
                applied.append(d)

            elif d == DistortionType.PERSPECTIVE_WARP:
                tilt = cfg.perspective_tilt_deg
                dx = int(w * (tilt / 100.0) * random.choice([-1, 1]))
                dy = int(h * (tilt / 100.0) * random.choice([-1, 1]))
                pts1 = np.float32([[0, 0], [w, 0], [0, h], [w, h]])
                pts2 = np.float32([
                    [max(0, dx), max(0, dy)],
                    [w - abs(dx) // 2, max(0, -dy)],
                    [max(0, -dx), h - abs(dy) // 2],
                    [w - abs(dx), h - abs(dy)]
                ])
                m = cv2.getPerspectiveTransform(pts1, pts2)
                out = cv2.warpPerspective(out, m, (w, h), borderValue=(120, 120, 120))
                applied.append(d)

            elif d == DistortionType.ROAD_GRIME:
                # Add random subtle smudge spots
                num_spots = random.randint(2, 5)
                for _ in range(num_spots):
                    cx = random.randint(int(w * 0.1), int(w * 0.9))
                    cy = random.randint(int(h * 0.1), int(h * 0.9))
                    axes = (random.randint(5, 15), random.randint(3, 10))
                    cv2.ellipse(out, (cx, cy), axes, random.randint(0, 180), 0, 360, (50, 45, 40), -1)
                applied.append(d)

        return out, applied
