"""Tier 1 Feature 2: CLAHE Preprocessing & OCR Extraction (T1-F2-01 .. T1-F2-05).

Validates:
- T1-F2-01: High contrast standard private plate crop (black on white)
- T1-F2-02: Green Electric Vehicle (EV) plate crop polarity inversion
- T1-F2-03: Commercial vehicle yellow plate crop L-channel normalization
- T1-F2-04: Dual-line plate crop row splitting and horizontal concatenation
- T1-F2-05: Low-light underexposed night-time frame CLAHE enhancement
"""

from __future__ import annotations

import sys
from pathlib import Path

_repo_root = Path(__file__).resolve().parent.parent.parent
if str(_repo_root) not in sys.path:
    sys.path.insert(0, str(_repo_root))

_e2e_root = Path(__file__).resolve().parent.parent
if str(_e2e_root) not in sys.path:
    sys.path.insert(0, str(_e2e_root))

import cv2
import numpy as np
import pytest

from anpr_service.ocr import (
    PlateCategory,
    apply_lab_clahe,
    detect_plate_category_and_polarity,
    invert_polarity_if_needed,
    detect_dual_row,
    split_dual_row,
    stitch_dual_row_horizontal,
    preprocess_plate,
)

try:
    from tests.e2e.harness import (
        DatabaseAdapter,
        E2EApiClient,
        PlateCropGenerator,
        PlateGenerator,
    )
except ImportError:
    from harness import (
        DatabaseAdapter,
        E2EApiClient,
        PlateCropGenerator,
        PlateGenerator,
    )


def test_t1_f2_01_standard_private_plate_ocr(api_client: E2EApiClient, fresh_db: DatabaseAdapter):
    """T1-F2-01: High contrast standard private plate crop (white reflective background).
    
    Verifies:
    - Plate categorized as PRIVATE_WHITE without polarity inversion
    - Ingested plateNumber matches verbatim "DL01AB1234"
    - Confidence >= 0.95 and status ACCEPTED in DB
    """
    plate_text = "DL01AB1234"
    crop = PlateCropGenerator.create_plate_crop(plate_text, bg_color="white", width=340, height=85)

    is_inverted, category, bg_luma = detect_plate_category_and_polarity(crop)
    assert not is_inverted, "Standard private white plate should not be inverted"
    assert category == PlateCategory.PRIVATE_WHITE
    assert bg_luma > 120.0

    crop_url = PlateCropGenerator.to_base64_data_url(crop)
    res = api_client.post_anpr_event({
        "facilityId": "palika",
        "cameraId": "palika-entry-1",
        "gateType": "ENTRY",
        "plateNumber": plate_text,
        "confidence": 0.97,
        "plateCropBase64": crop_url,
    })

    assert res["status_code"] == 201
    assert res["status"] == "ACCEPTED"
    assert res["liveOccupancy"] == 1

    event = fresh_db.query_one("SELECT * FROM anpr_events WHERE id = ?", (res["eventId"],))
    assert event["plate_number"] == plate_text
    assert event["confidence"] >= 0.95
    assert event["status"] == "ACCEPTED"


def test_t1_f2_02_green_ev_plate_polarity_inversion(api_client: E2EApiClient, fresh_db: DatabaseAdapter):
    """T1-F2-02: Green Electric Vehicle (EV) plate crop polarity inversion.
    
    Verifies:
    - Dark green background with white text identified as EV_GREEN and inverted
    - Polarity inversion transforms dark background to light
    - Ingested plateNumber "DL01EV5678", confidence >= 0.90, status ACCEPTED
    """
    plate_text = "DL01EV5678"
    crop = PlateCropGenerator.create_plate_crop(plate_text, bg_color="green", width=340, height=85)

    is_inverted, category, bg_luma = detect_plate_category_and_polarity(crop)
    assert is_inverted is True, "Green EV plate must be flagged for polarity inversion"
    assert category == PlateCategory.EV_GREEN

    inverted_crop, was_inverted = invert_polarity_if_needed(crop)
    assert was_inverted is True
    assert inverted_crop is not None
    # Verify inverted background is now bright
    gray_inverted = cv2.cvtColor(inverted_crop, cv2.COLOR_BGR2GRAY)
    assert np.mean(gray_inverted) > np.mean(cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY))

    crop_url = PlateCropGenerator.to_base64_data_url(inverted_crop)
    res = api_client.post_anpr_event({
        "facilityId": "palika",
        "cameraId": "palika-entry-1",
        "gateType": "ENTRY",
        "plateNumber": plate_text,
        "confidence": 0.92,
        "plateCropBase64": crop_url,
    })

    assert res["status_code"] == 201
    assert res["status"] == "ACCEPTED"

    event = fresh_db.query_one("SELECT * FROM anpr_events WHERE id = ?", (res["eventId"],))
    assert event["plate_number"] == plate_text
    assert event["confidence"] >= 0.90
    assert event["status"] == "ACCEPTED"


def test_t1_f2_03_commercial_yellow_plate(api_client: E2EApiClient, fresh_db: DatabaseAdapter):
    """T1-F2-03: Commercial vehicle yellow plate crop L-channel normalization.
    
    Verifies:
    - Yellow commercial plate classified as COMMERCIAL_YELLOW
    - LAB CLAHE enhances luminance contrast without altering color balance
    - Ingested plateNumber "DL1T1234", confidence >= 0.92, status ACCEPTED
    """
    plate_text = "DL1T1234"
    crop = PlateCropGenerator.create_plate_crop(plate_text, bg_color="yellow", width=340, height=85)

    is_inverted, category, bg_luma = detect_plate_category_and_polarity(crop)
    assert not is_inverted, "Commercial yellow plate does not require polarity inversion"
    assert category == PlateCategory.COMMERCIAL_YELLOW

    # Apply CLAHE on L-channel
    clahe_img = apply_lab_clahe(crop)
    assert clahe_img.shape == crop.shape

    crop_url = PlateCropGenerator.to_base64_data_url(clahe_img)
    res = api_client.post_anpr_event({
        "facilityId": "palika",
        "cameraId": "palika-entry-1",
        "gateType": "ENTRY",
        "plateNumber": plate_text,
        "confidence": 0.93,
        "plateCropBase64": crop_url,
    })

    assert res["status_code"] == 201
    assert res["status"] == "ACCEPTED"

    event = fresh_db.query_one("SELECT * FROM anpr_events WHERE id = ?", (res["eventId"],))
    assert event["plate_number"] == plate_text
    assert event["confidence"] >= 0.92
    assert event["status"] == "ACCEPTED"

    vehicle = fresh_db.query_one("SELECT * FROM vehicles WHERE plate_number = ?", (plate_text,))
    assert vehicle is not None


def test_t1_f2_04_dual_line_plate_splitting(api_client: E2EApiClient, fresh_db: DatabaseAdapter):
    """T1-F2-04: Dual-line plate crop row splitting and horizontal stitching.
    
    Verifies:
    - Dual row plate correctly split and concatenated horizontally
    - Ingested event plateNumber "MH12DE1432", confidence >= 0.88
    - anpr_events row status is ACCEPTED
    """
    plate_text = "MH12DE1432"

    # Synthesize two single rows: Top "MH12" and Bottom "DE1432"
    top_crop = PlateCropGenerator.create_plate_crop("MH12", bg_color="white", width=220, height=60)
    bot_crop = PlateCropGenerator.create_plate_crop("DE1432", bg_color="white", width=220, height=60)
    # Stack vertically to create a dual-line plate
    dual_row_img = np.vstack([top_crop, bot_crop])

    # Test splitting and horizontal stitching
    top_split, bot_split = split_dual_row(dual_row_img, split_y=60)
    assert top_split.shape[0] == 60
    assert bot_split.shape[0] == 60

    stitched = stitch_dual_row_horizontal(top_split, bot_split, spacer_px=15)
    assert stitched is not None
    # Horizontal stitch should be wider than individual crops
    assert stitched.shape[1] > 220

    crop_url = PlateCropGenerator.to_base64_data_url(stitched)
    res = api_client.post_anpr_event({
        "facilityId": "palika",
        "cameraId": "palika-entry-1",
        "gateType": "ENTRY",
        "plateNumber": plate_text,
        "confidence": 0.91,
        "plateCropBase64": crop_url,
    })

    assert res["status_code"] == 201
    assert res["status"] == "ACCEPTED"

    event = fresh_db.query_one("SELECT * FROM anpr_events WHERE id = ?", (res["eventId"],))
    assert event["plate_number"] == plate_text
    assert event["confidence"] >= 0.88
    assert event["status"] == "ACCEPTED"


def test_t1_f2_05_low_light_clahe_enhancement(api_client: E2EApiClient, fresh_db: DatabaseAdapter):
    """T1-F2-05: Low-light underexposed night-time frame CLAHE enhancement.
    
    Verifies:
    - CLAHE significantly enhances local contrast of underexposed frame
    - Ingested event plateNumber "DL08CD9999", confidence >= 0.84
    - anpr_events row status is ACCEPTED
    """
    plate_text = "DL08CD9999"
    # Create dark / underexposed crop
    dark_crop = PlateCropGenerator.create_plate_crop(
        plate_text, bg_color="white", brightness=0.40, width=340, height=85
    )

    # Apply CLAHE
    enhanced = apply_lab_clahe(dark_crop, clip_limit=3.0)
    assert enhanced is not None

    # Verify luminance contrast was boosted
    gray_dark = cv2.cvtColor(dark_crop, cv2.COLOR_BGR2GRAY)
    gray_enh = cv2.cvtColor(enhanced, cv2.COLOR_BGR2GRAY)
    assert np.std(gray_enh) > np.std(gray_dark), "CLAHE must increase image contrast std deviation"

    crop_url = PlateCropGenerator.to_base64_data_url(enhanced)
    res = api_client.post_anpr_event({
        "facilityId": "palika",
        "cameraId": "palika-entry-1",
        "gateType": "ENTRY",
        "plateNumber": plate_text,
        "confidence": 0.87,
        "plateCropBase64": crop_url,
    })

    assert res["status_code"] == 201
    assert res["status"] == "ACCEPTED"

    event = fresh_db.query_one("SELECT * FROM anpr_events WHERE id = ?", (res["eventId"],))
    assert event["plate_number"] == plate_text
    assert event["confidence"] >= 0.84
    assert event["status"] == "ACCEPTED"
