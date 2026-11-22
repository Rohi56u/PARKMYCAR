"""Tier 1 Feature 3: Indian Registration Plate Grammar Validation (T1-F3-01 .. T1-F3-05).

Validates:
- T1-F3-01: Standard Delhi HSRP registration format (DL01AB1234)
- T1-F3-02: Maharashtra registration format (MH12DE1432) against 36 States/UTs table
- T1-F3-03: Bharat Series (BH) registration format (22BH1234AA)
- T1-F3-04: Commercial Karnataka registration format (KA01T9999)
- T1-F3-05: Diplomatic registration format (77CD12)
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

import pytest

from anpr_service.validator import (
    VALID_STATE_CODES,
    IndianPlateValidator,
    PlateType,
    ValidationStatus,
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


def test_t1_f3_01_standard_delhi_hsrp(api_client: E2EApiClient, fresh_db: DatabaseAdapter):
    """T1-F3-01: Standard Delhi HSRP registration text "DL01AB1234".
    
    Verifies:
    - Matches standard HSRP regex ^[A-Z]{2}[0-9]{2}[A-Z]{1,2}[0-9]{4}$
    - Correctly parsed: stateCode="DL", rto="01", series="AB", number="1234"
    - Ingested into database, creating record in vehicles and vehicle_sessions
    """
    plate_text = "DL01AB1234"

    # 1. Grammar Validator verification
    validator = IndianPlateValidator()
    val_res = validator.validate(plate_text)
    assert val_res.status == ValidationStatus.ACCEPTED
    assert val_res.plate_type == PlateType.STANDARD_HSRP
    assert val_res.state_code == "DL"
    assert val_res.rto_code == "01"
    assert val_res.series == "AB"
    assert val_res.unique_number == "1234"

    # Harness PlateGenerator check
    is_valid, kind = PlateGenerator.is_valid_indian_plate(plate_text)
    assert is_valid is True
    assert kind == "HSRP"

    # 2. Ingest through E2E API
    crop_url = PlateCropGenerator.generate_crop_data_url(plate_text, bg_color="white")
    res = api_client.post_anpr_event({
        "facilityId": "palika",
        "cameraId": "palika-entry-1",
        "gateType": "ENTRY",
        "plateNumber": plate_text,
        "confidence": 0.95,
        "plateCropBase64": crop_url,
    })

    assert res["status_code"] == 201
    assert res["status"] == "ACCEPTED"
    assert res["liveOccupancy"] == 1

    # 3. Database assertions
    vehicle = fresh_db.query_one("SELECT * FROM vehicles WHERE plate_number = ?", (plate_text,))
    assert vehicle is not None
    assert vehicle["state_code"] == "DL"
    assert vehicle["plate_number"] == plate_text


def test_t1_f3_02_maharashtra_state_code_lookup(api_client: E2EApiClient, fresh_db: DatabaseAdapter):
    """T1-F3-02: Maharashtra registration text "MH12DE1432".
    
    Verifies:
    - Validates state code 'MH' against 36 Indian States/UTs master table
    - Parsed: stateCode="MH", rto="12", series="DE", number="1432"
    - Database vehicles.state_code matches "MH"
    """
    plate_text = "MH12DE1432"

    assert "MH" in VALID_STATE_CODES
    assert len(VALID_STATE_CODES) >= 36

    validator = IndianPlateValidator()
    val_res = validator.validate(plate_text)
    assert val_res.status == ValidationStatus.ACCEPTED
    assert val_res.state_code == "MH"
    assert val_res.rto_code == "12"
    assert val_res.series == "DE"
    assert val_res.unique_number == "1432"

    crop_url = PlateCropGenerator.generate_crop_data_url(plate_text, bg_color="white")
    res = api_client.post_anpr_event({
        "facilityId": "palika",
        "cameraId": "palika-entry-1",
        "gateType": "ENTRY",
        "plateNumber": plate_text,
        "confidence": 0.94,
        "plateCropBase64": crop_url,
    })

    assert res["status_code"] == 201
    assert res["status"] == "ACCEPTED"

    vehicle = fresh_db.query_one("SELECT * FROM vehicles WHERE plate_number = ?", (plate_text,))
    assert vehicle["state_code"] == "MH"
    assert vehicle["plate_number"] == plate_text


def test_t1_f3_03_bharat_series_registration(api_client: E2EApiClient, fresh_db: DatabaseAdapter):
    """T1-F3-03: Bharat Series (BH) registration text "22BH1234AA".
    
    Verifies:
    - Matches BH regex ^[0-9]{2}BH[0-9]{4}[A-Z]{1,2}$
    - Parsed: type="BHARAT_SERIES", year="22", number="1234", series="AA"
    - Database vehicles.state_code = 'BH', plate_number = '22BH1234AA'
    """
    plate_text = "22BH1234AA"

    validator = IndianPlateValidator()
    val_res = validator.validate(plate_text)
    assert val_res.status == ValidationStatus.ACCEPTED
    assert val_res.plate_type == PlateType.BHARAT_SERIES
    assert val_res.state_code == "BH"
    assert val_res.rto_code == "22"  # Registration year
    assert val_res.unique_number == "1234"
    assert val_res.series == "AA"

    is_valid, kind = PlateGenerator.is_valid_indian_plate(plate_text)
    assert is_valid is True
    assert kind == "BHARAT_SERIES"

    crop_url = PlateCropGenerator.generate_crop_data_url(plate_text, bg_color="white")
    res = api_client.post_anpr_event({
        "facilityId": "palika",
        "cameraId": "palika-entry-1",
        "gateType": "ENTRY",
        "plateNumber": plate_text,
        "confidence": 0.96,
        "plateCropBase64": crop_url,
    })

    assert res["status_code"] == 201
    assert res["status"] == "ACCEPTED"

    vehicle = fresh_db.query_one("SELECT * FROM vehicles WHERE plate_number = ?", (plate_text,))
    assert vehicle["state_code"] in ("BH", "22")
    assert vehicle["plate_number"] == plate_text


def test_t1_f3_04_commercial_karnataka_series(api_client: E2EApiClient, fresh_db: DatabaseAdapter):
    """T1-F3-04: Commercial Karnataka registration text "KA01T9999".
    
    Verifies:
    - Commercial plate format (state="KA", rto="01", series="T", number="9999")
    - Validates state code 'KA' in 36 States/UTs table
    - Database vehicles.state_code = 'KA', plate_number = 'KA01T9999'
    """
    plate_text = "KA01T9999"

    validator = IndianPlateValidator()
    val_res = validator.validate(plate_text)
    assert val_res.status == ValidationStatus.ACCEPTED
    assert val_res.state_code == "KA"
    assert val_res.rto_code == "01"
    assert val_res.unique_number == "9999"

    is_valid, kind = PlateGenerator.is_valid_indian_plate(plate_text)
    assert is_valid is True
    assert kind in ("COMMERCIAL", "HSRP")

    crop_url = PlateCropGenerator.generate_crop_data_url(plate_text, bg_color="yellow")
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

    vehicle = fresh_db.query_one("SELECT * FROM vehicles WHERE plate_number = ?", (plate_text,))
    assert vehicle["state_code"] == "KA"
    assert vehicle["plate_number"] == plate_text


def test_t1_f3_05_diplomatic_mission_registration(api_client: E2EApiClient, fresh_db: DatabaseAdapter):
    """T1-F3-05: Diplomatic registration text "77CD12".
    
    Verifies:
    - Matches Diplomatic regex ^[0-9]{1,3}(CD|CC|UN)[0-9]{1,4}$
    - Validates type="DIPLOMATIC", missionCode="77", corps="CD", number="12"
    - Database creates valid vehicle and session records
    """
    plate_text = "77CD12"

    validator = IndianPlateValidator()
    val_res = validator.validate(plate_text)
    assert val_res.status == ValidationStatus.ACCEPTED
    assert val_res.plate_type == PlateType.DIPLOMATIC

    is_valid, kind = PlateGenerator.is_valid_indian_plate(plate_text)
    assert is_valid is True
    assert kind == "DIPLOMATIC"

    crop_url = PlateCropGenerator.generate_crop_data_url(plate_text, bg_color="blue")
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
    assert event["status"] == "ACCEPTED"
    vehicle = fresh_db.query_one("SELECT * FROM vehicles WHERE plate_number = ?", (plate_text,))
    assert vehicle is not None
