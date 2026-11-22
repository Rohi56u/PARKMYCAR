"""Synthetic Indian License Plate & Crop Generator for ANPR E2E Testing.

Provides:
- PlateGenerator: Synthesizes valid Indian registration plates (HSRP, Bharat Series,
  commercial, EV, diplomatic), boundary/malformed plates, and DIN 1451 positional confusion variants.
- PlateCropGenerator: Synthesizes realistic plate crop images with OpenCV/Pillow,
  applying background colors, border, IND strips, noise, tilt, and lighting adjustments,
  and encodes them as base64 JPEG data URLs.
"""

from __future__ import annotations

import base64
import io
import math
import random
import re
from typing import Optional

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont


class PlateGenerator:
    """Generates synthetic Indian vehicle registration numbers across all formats."""

    # 36 States and Union Territories of India
    VALID_STATE_CODES = [
        "AN", "AP", "AR", "AS", "BR", "CH", "CG", "DD", "DL", "DN",
        "GA", "GJ", "HR", "HP", "JK", "JH", "KA", "KL", "LA", "LD",
        "MP", "MH", "MN", "ML", "MZ", "NL", "OD", "PY", "PB", "RJ",
        "SK", "TN", "TS", "TR", "UP", "UK", "WB"
    ]

    # Regular expressions for validation
    REGEX_HSRP = re.compile(r"^[A-Z]{2}[0-9]{2}[A-Z]{1,2}[0-9]{4}$")
    REGEX_BH = re.compile(r"^[0-9]{2}BH[0-9]{4}[A-Z]{1,2}$")
    REGEX_COMMERCIAL = re.compile(r"^[A-Z]{2}[0-9]{1,2}T[0-9]{4}$")
    REGEX_EV = re.compile(r"^[A-Z]{2}[0-9]{2}EV[0-9]{4}$")
    REGEX_DIPLOMATIC = re.compile(r"^[0-9]{2,3}(CD|CC|UN)[0-9]{1,4}$")

    # DIN 1451 Positional Character Confusions
    CONFUSION_MAP = {
        "O": "0",
        "0": "O",
        "I": "1",
        "1": "I",
        "B": "8",
        "8": "B",
        "S": "5",
        "5": "S",
        "Z": "2",
        "2": "Z",
    }

    @classmethod
    def generate_valid_hsrp(
        cls,
        state: Optional[str] = None,
        rto: Optional[str] = None,
        series: Optional[str] = None,
        number: Optional[str] = None,
    ) -> str:
        """Generate a valid standard HSRP Indian registration plate (e.g. DL01AB1234)."""
        state_code = state.upper() if state else random.choice(cls.VALID_STATE_CODES)
        rto_code = rto if rto is not None else f"{random.randint(1, 99):02d}"
        if series is None:
            series_len = random.choice([1, 2])
            series = "".join(random.choices("ABCDEFGHJKLMNPQRSTUVWXYZ", k=series_len))
        else:
            series = series.upper()
        num_str = number if number is not None else f"{random.randint(1, 9999):04d}"
        return f"{state_code}{rto_code}{series}{num_str}"

    @classmethod
    def generate_bharat_series(
        cls,
        year: Optional[int] = None,
        number: Optional[str] = None,
        series: Optional[str] = None,
    ) -> str:
        """Generate a valid Bharat Series (BH) plate (e.g. 22BH1234AA)."""
        yr = year if year is not None else random.randint(21, 26)
        num_str = number if number is not None else f"{random.randint(1, 9999):04d}"
        if series is None:
            series = "".join(random.choices("ABCDEFGHJKLMNPQRSTUVWXYZ", k=2))
        else:
            series = series.upper()
        return f"{yr:02d}BH{num_str}{series}"

    @classmethod
    def generate_commercial(cls, state: Optional[str] = None) -> str:
        """Generate a commercial vehicle plate (yellow background, e.g. DL1T1234 or DL01T5678)."""
        state_code = state.upper() if state else random.choice(["DL", "MH", "KA", "HR", "UP"])
        rto_code = random.choice(["1", "01", "12", "04"])
        num_str = f"{random.randint(1000, 9999):04d}"
        return f"{state_code}{rto_code}T{num_str}"

    @classmethod
    def generate_ev(cls, state: Optional[str] = None) -> str:
        """Generate an Electric Vehicle (EV) plate (green background, e.g. DL01EV5678)."""
        state_code = state.upper() if state else random.choice(["DL", "MH", "KA", "TN"])
        rto_code = f"{random.randint(1, 15):02d}"
        num_str = f"{random.randint(1000, 9999):04d}"
        return f"{state_code}{rto_code}EV{num_str}"

    @classmethod
    def generate_diplomatic(cls) -> str:
        """Generate a diplomatic mission vehicle plate (blue background, e.g. 77CD12)."""
        country_code = random.randint(10, 99)
        mission_type = random.choice(["CD", "CC", "UN"])
        num_str = random.randint(1, 99)
        return f"{country_code}{mission_type}{num_str}"

    @classmethod
    def generate_malformed(cls, kind: str = "lowercase") -> str:
        """Generate boundary and malformed plates for edge case testing."""
        if kind == "lowercase":
            valid = cls.generate_valid_hsrp()
            return valid.lower()
        elif kind == "invalid_state":
            invalid_states = ["ZZ", "XX", "QQ", "YY", "WW", "00"]
            prefix = random.choice(invalid_states)
            return f"{prefix}01AB1234"
        elif kind == "truncated":
            return random.choice(["DL01", "DL01A", "DL", "22BH", "MH12D"])
        elif kind == "overlength":
            return f"{cls.generate_valid_hsrp()}99999"
        elif kind == "symbols":
            return random.choice([
                "DL-01-AB-1234",
                "DL.01.AB.1234",
                "DL#01*AB",
                "MH/12/DE/1432",
                "KA 05 MB 9999",
            ])
        elif kind == "spaces":
            return "DL 01 AB 1234"
        elif kind == "zero_padded":
            return "DL000AB1234"
        else:
            return "INVALID_PLATE_XYZ"

    @classmethod
    def generate_confusion_variant(
        cls,
        plate: str,
        confusion_type: str = "O_0",
    ) -> str:
        """Generate a DIN 1451 positional confusion variant of an existing plate."""
        chars = list(plate.upper())

        if confusion_type in ("O_0", "0_O"):
            # Replace 0 with O or O with 0
            for i, c in reversed(list(enumerate(chars))):
                if c == "0":
                    chars[i] = "O"
                    return "".join(chars)
                elif c == "O":
                    chars[i] = "0"
                    return "".join(chars)
            # If no 0 or O, force in a digit position
            chars[-1] = "O"
        elif confusion_type in ("I_1", "1_I"):
            for i, c in reversed(list(enumerate(chars))):
                if c == "1":
                    chars[i] = "I"
                    return "".join(chars)
                elif c == "I":
                    chars[i] = "1"
                    return "".join(chars)
            chars[-1] = "I"
        elif confusion_type in ("B_8", "8_B"):
            for i, c in enumerate(chars):
                if c == "B":
                    chars[i] = "8"
                    return "".join(chars)
                elif c == "8":
                    chars[i] = "B"
                    return "".join(chars)
            chars[4] = "8" if len(chars) > 4 else "8"
        elif confusion_type in ("S_5", "5_S"):
            for i, c in enumerate(chars):
                if c == "S":
                    chars[i] = "5"
                    return "".join(chars)
                elif c == "5":
                    chars[i] = "S"
                    return "".join(chars)
            chars[4] = "5" if len(chars) > 4 else "5"
        elif confusion_type in ("Z_2", "2_Z"):
            for i, c in enumerate(chars):
                if c == "Z":
                    chars[i] = "2"
                    return "".join(chars)
                elif c == "2":
                    chars[i] = "Z"
                    return "".join(chars)
            chars[4] = "2" if len(chars) > 4 else "2"

        return "".join(chars)

    @classmethod
    def is_valid_indian_plate(cls, plate: str) -> tuple[bool, str]:
        """Validate plate string against Indian registration grammars."""
        clean = plate.strip().upper()
        if not clean:
            return False, "EMPTY_PLATE"

        # Check Diplomatic
        if cls.REGEX_DIPLOMATIC.match(clean):
            return True, "DIPLOMATIC"

        # Check BH Series
        if cls.REGEX_BH.match(clean):
            return True, "BHARAT_SERIES"

        # Check EV
        if cls.REGEX_EV.match(clean):
            state = clean[:2]
            if state in cls.VALID_STATE_CODES:
                return True, "EV"
            return False, f"INVALID_STATE_CODE:{state}"

        # Check Commercial (e.g. DL1T1234 or DL01T1234)
        if cls.REGEX_COMMERCIAL.match(clean):
            state = clean[:2]
            if state in cls.VALID_STATE_CODES:
                return True, "COMMERCIAL"
            return False, f"INVALID_STATE_CODE:{state}"

        # Check HSRP
        if cls.REGEX_HSRP.match(clean):
            state = clean[:2]
            if state in cls.VALID_STATE_CODES:
                return True, "HSRP"
            return False, f"INVALID_STATE_CODE:{state}"

        return False, "INVALID_GRAMMAR"

    @classmethod
    def get_sample_corpus(cls) -> dict[str, list[str]]:
        """Return a curated corpus of valid and boundary Indian registration plates."""
        return {
            "valid_hsrp": [
                "DL01AB1234",
                "MH12DE1432",
                "KA05MB9999",
                "HR26DQ5555",
                "UP16BZ4321",
                "TN09AK7777",
                "GJ01RA2020",
                "RJ14CX9000",
                "WB02AD3333",
                "KL07BN1111",
            ],
            "valid_bh": [
                "22BH1234AA",
                "23BH5678AB",
                "21BH9999ZZ",
                "24BH0001A",
                "22BH7777CD",
            ],
            "valid_commercial": [
                "DL1T1234",
                "MH12T5678",
                "KA01T9999",
                "UP16T4444",
            ],
            "valid_ev": [
                "DL01EV5678",
                "MH02EV1234",
                "KA05EV9999",
                "TN01EV3333",
            ],
            "valid_diplomatic": [
                "77CD12",
                "11UN34",
                "45CC78",
            ],
            "malformed": [
                "dl01ab1234",
                "ZZ99AB1234",
                "DL01A1",
                "DL01AB123456",
                "DL-01-AB-1234",
                "DL 01 AB 1234",
                "XX01AA1111",
            ],
            "positional_confusion": [
                "DL01AB123O",
                "DLO1AB1234",
                "DL01AB123I",
                "DLI1AB1234",
                "DL01A81234",
                "DL01AB123B",
                "DL01A51234",
                "DL01A21234",
            ],
        }


class PlateCropGenerator:
    """Generates synthetic license plate crop images using OpenCV and Pillow."""

    PALETTES = {
        "white": {  # Standard Private HSRP
            "bg": (245, 245, 245),
            "text": (20, 20, 20),
            "border": (30, 30, 30),
            "has_ind_strip": True,
        },
        "yellow": {  # Commercial
            "bg": (240, 210, 20),
            "text": (15, 15, 15),
            "border": (25, 25, 25),
            "has_ind_strip": True,
        },
        "green": {  # Electric Vehicle (EV)
            "bg": (35, 130, 50),
            "text": (250, 250, 250),
            "border": (20, 80, 30),
            "has_ind_strip": True,
        },
        "blue": {  # Diplomatic
            "bg": (30, 110, 220),
            "text": (255, 255, 255),
            "border": (20, 80, 160),
            "has_ind_strip": False,
        },
    }

    @classmethod
    def create_plate_crop(
        cls,
        plate_text: str,
        bg_color: str = "white",
        noise_level: float = 0.0,
        tilt_angle: float = 0.0,
        brightness: float = 1.0,
        blur_ksize: int = 0,
        width: int = 320,
        height: int = 80,
    ) -> np.ndarray:
        """Generate a realistic synthetic BGR image crop of a license plate."""
        palette = cls.PALETTES.get(bg_color.lower(), cls.PALETTES["white"])
        bg_rgb = palette["bg"]
        text_rgb = palette["text"]
        border_rgb = palette["border"]

        # 1. Create base RGB image
        img = Image.new("RGB", (width, height), color=bg_rgb)
        draw = ImageDraw.Draw(img)

        # 2. Draw outer plate border
        border_thickness = 3
        draw.rectangle(
            [0, 0, width - 1, height - 1],
            outline=border_rgb,
            width=border_thickness,
        )

        # 3. Draw blue IND strip on the left if applicable
        text_start_x = 10
        if palette["has_ind_strip"]:
            strip_width = int(width * 0.09)
            draw.rectangle(
                [border_thickness, border_thickness, strip_width, height - border_thickness - 1],
                fill=(0, 51, 153),  # Deep blue
            )
            # Mini IND text or chakra representation
            draw.text(
                (strip_width // 4, height // 2 - 6),
                "IND",
                fill=(255, 255, 255),
            )
            text_start_x = strip_width + 12

        # 4. Render plate registration text
        # Format text with spacing for realistic plate appearance
        formatted_text = plate_text.upper()
        if len(formatted_text) == 10 and PlateGenerator.REGEX_HSRP.match(formatted_text):
            # e.g., "DL 01 AB 1234"
            formatted_text = f"{formatted_text[:2]} {formatted_text[2:4]} {formatted_text[4:6]} {formatted_text[6:]}"
        elif len(formatted_text) == 10 and PlateGenerator.REGEX_BH.match(formatted_text):
            # e.g., "22 BH 1234 AA"
            formatted_text = f"{formatted_text[:2]} BH {formatted_text[4:8]} {formatted_text[8:]}"

        # Convert to OpenCV image (BGR) for font rendering & transformations
        cv_img = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
        text_bgr = (text_rgb[2], text_rgb[1], text_rgb[0])

        # Calculate font scale to fit plate dimensions
        font = cv2.FONT_HERSHEY_DUPLEX
        font_scale = 0.95
        thickness = 2
        text_size, baseline = cv2.getTextSize(formatted_text, font, font_scale, thickness)

        # Re-scale if text overflows
        avail_width = width - text_start_x - 10
        if text_size[0] > avail_width and text_size[0] > 0:
            font_scale = font_scale * (avail_width / text_size[0]) * 0.95
            text_size, baseline = cv2.getTextSize(formatted_text, font, font_scale, thickness)

        # Center vertically and align horizontally after IND strip
        text_y = int((height + text_size[1]) / 2) - 2
        text_x = int(text_start_x + (avail_width - text_size[0]) / 2)
        if text_x < text_start_x:
            text_x = text_start_x

        cv2.putText(
            cv_img,
            formatted_text,
            (text_x, text_y),
            font,
            font_scale,
            text_bgr,
            thickness,
            cv2.LINE_AA,
        )

        # 5. Apply tilt (perspective/rotation) if requested
        if abs(tilt_angle) > 0.01:
            center = (width / 2.0, height / 2.0)
            rot_mat = cv2.getRotationMatrix2D(center, tilt_angle, 1.0)
            cv_img = cv2.warpAffine(
                cv_img,
                rot_mat,
                (width, height),
                flags=cv2.INTER_LINEAR,
                borderMode=cv2.BORDER_CONSTANT,
                borderValue=(text_bgr if bg_color == "green" else (200, 200, 200)),
            )

        # 6. Apply Gaussian noise if requested
        if noise_level > 0.0:
            noise = np.random.normal(0, noise_level * 25, cv_img.shape).astype(np.float32)
            noisy_img = cv_img.astype(np.float32) + noise
            cv_img = np.clip(noisy_img, 0, 255).astype(np.uint8)

        # 7. Apply lighting / brightness scaling if requested
        if abs(brightness - 1.0) > 0.01:
            bright_img = cv_img.astype(np.float32) * brightness
            cv_img = np.clip(bright_img, 0, 255).astype(np.uint8)

        # 8. Apply blur if requested
        if blur_ksize > 0:
            k = blur_ksize if blur_ksize % 2 == 1 else blur_ksize + 1
            cv_img = cv2.GaussianBlur(cv_img, (k, k), 0)

        return cv_img

    @classmethod
    def to_base64_data_url(cls, image: np.ndarray | Image.Image) -> str:
        """Encode an OpenCV BGR array or PIL Image into a JPEG data URL."""
        if isinstance(image, Image.Image):
            buffered = io.BytesIO()
            image.save(buffered, format="JPEG", quality=85)
            b64_str = base64.b64encode(buffered.getvalue()).decode("utf-8")
        else:
            # OpenCV BGR image
            success, encoded_buf = cv2.imencode(".jpg", image, [int(cv2.IMWRITE_JPEG_QUALITY), 85])
            if not success:
                raise ValueError("Failed to encode image to JPEG")
            b64_str = base64.b64encode(encoded_buf).decode("utf-8")

        return f"data:image/jpeg;base64,{b64_str}"

    @classmethod
    def generate_crop_data_url(
        cls,
        plate_text: str,
        bg_color: str = "white",
        noise_level: float = 0.0,
        tilt_angle: float = 0.0,
        brightness: float = 1.0,
        blur_ksize: int = 0,
        width: int = 320,
        height: int = 80,
    ) -> str:
        """Convenience method to generate synthetic crop and return base64 data URL."""
        crop = cls.create_plate_crop(
            plate_text=plate_text,
            bg_color=bg_color,
            noise_level=noise_level,
            tilt_angle=tilt_angle,
            brightness=brightness,
            blur_ksize=blur_ksize,
            width=width,
            height=height,
        )
        return cls.to_base64_data_url(crop)
