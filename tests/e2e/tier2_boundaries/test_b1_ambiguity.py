"""Tier 2 Boundary Tests - Category B1: Character Ambiguity Extremes.

Test Cases:
- T2-B1-01: Character ambiguity extremes O/0 and 8/B (DL01ABO08B -> DL01AB0088)
- T2-B1-02: Character ambiguity extremes 1 and I (HR26I111I -> HR26I1111)
- T2-B1-03: Character ambiguity extremes S and 5 (MH12SS5555 -> MH12SS5555)
- T2-B1-04: Character ambiguity extremes Z and 2 (GJ01ZZ2222 -> GJ01ZZ2222)
- T2-B1-05: Character ambiguity extremes B and 8 (UP16BB8888 -> UP16BB8888)
"""

from __future__ import annotations

import pytest

try:
    from tests.e2e.harness import DatabaseAdapter, E2EApiClient, PlateGenerator
except ImportError:
    from harness import DatabaseAdapter, E2EApiClient, PlateGenerator

from anpr_service.validator.indian_plate import IndianPlateValidator
from anpr_service.validator.disambiguation import disambiguate_standard_hsrp


def test_t2_b1_01_character_ambiguity_o_0_and_8_b(api_client: E2EApiClient, fresh_db: DatabaseAdapter):
    """T2-B1-01: Disambiguate adjacent letters and digits with O/0 and 8/B mix.

    Input: 'DL01ABO08B'
    Expected: Normalizes to 'DL01AB0088', event ACCEPTED, active INSIDE session in DB.
    """
    raw_plate = "DL01ABO08B"
    validator = IndianPlateValidator()
    val_res = validator.validate(raw_plate)

    assert val_res.is_valid is True, f"Validation failed for {raw_plate}"
    assert val_res.normalized_plate == "DL01AB0088", f"Unexpected normalization: {val_res.normalized_plate}"
    assert val_res.substitutions_applied >= 1

    # Ingest event with normalized plate
    payload = {
        "facilityId": "palika",
        "cameraId": "palika-entry-1",
        "gateType": "ENTRY",
        "plateNumber": val_res.normalized_plate,
        "confidence": 0.94,
    }
    res = api_client.post_anpr_event(payload)
    assert res["status_code"] == 201
    assert res["success"] is True
    assert res["status"] == "ACCEPTED"
    assert res["liveOccupancy"] == 1

    # Authoritative DB Assertions
    evt = fresh_db.query_one("SELECT * FROM anpr_events WHERE id = ?", (res["eventId"],))
    assert evt is not None
    assert evt["plate_number"] == "DL01AB0088"
    assert evt["status"] == "ACCEPTED"

    session = fresh_db.get_active_session("palika", "DL01AB0088")
    assert session is not None
    assert session["status"] == "INSIDE"
    assert fresh_db.get_live_occupancy("palika") == 1


def test_t2_b1_02_character_ambiguity_1_and_i(api_client: E2EApiClient, fresh_db: DatabaseAdapter):
    """T2-B1-02: Series and number slots filled with 1 and I.

    Input: 'HR26I111I'
    Expected: Alpha slot gets 'I', numeric slots 1-4 get '1' -> 'HR26I1111'.
    """
    raw_plate = "HR26I111I"
    validator = IndianPlateValidator()
    val_res = validator.validate(raw_plate)

    assert val_res.is_valid is True
    assert val_res.normalized_plate == "HR26I1111"

    payload = {
        "facilityId": "palika",
        "cameraId": "palika-entry-1",
        "gateType": "ENTRY",
        "plateNumber": val_res.normalized_plate,
        "confidence": 0.92,
    }
    res = api_client.post_anpr_event(payload)
    assert res["status_code"] == 201
    assert res["success"] is True
    assert res["status"] == "ACCEPTED"

    # Authoritative DB Assertions
    evt = fresh_db.query_one("SELECT * FROM anpr_events WHERE id = ?", (res["eventId"],))
    assert evt is not None
    assert evt["plate_number"] == "HR26I1111"
    assert evt["status"] == "ACCEPTED"

    session = fresh_db.get_active_session("palika", "HR26I1111")
    assert session is not None
    assert session["status"] == "INSIDE"


def test_t2_b1_03_character_ambiguity_s_and_5(api_client: E2EApiClient, fresh_db: DatabaseAdapter):
    """T2-B1-03: Confusion between 'S' and '5'.

    Input: 'MH12SS5555'
    Expected: Validates double 'S' in series slot and four '5's in number slot -> 'MH12SS5555'.
    """
    raw_plate = "MH12SS5555"
    validator = IndianPlateValidator()
    val_res = validator.validate(raw_plate)

    assert val_res.is_valid is True
    assert val_res.normalized_plate == "MH12SS5555"
    assert val_res.series == "SS"
    assert val_res.unique_number == "5555"

    payload = {
        "facilityId": "palika",
        "cameraId": "palika-entry-1",
        "gateType": "ENTRY",
        "plateNumber": val_res.normalized_plate,
        "confidence": 0.95,
    }
    res = api_client.post_anpr_event(payload)
    assert res["status_code"] == 201
    assert res["success"] is True
    assert res["status"] == "ACCEPTED"

    # Authoritative DB Assertions
    evt = fresh_db.query_one("SELECT * FROM anpr_events WHERE id = ?", (res["eventId"],))
    assert evt is not None
    assert evt["plate_number"] == "MH12SS5555"
    assert fresh_db.get_live_occupancy("palika") == 1


def test_t2_b1_04_character_ambiguity_z_and_2(api_client: E2EApiClient, fresh_db: DatabaseAdapter):
    """T2-B1-04: Confusion between 'Z' and '2'.

    Input: 'GJ01ZZ2222'
    Expected: Series slot maintains 'ZZ', number slot maintains '2222' -> 'GJ01ZZ2222'.
    """
    raw_plate = "GJ01ZZ2222"
    validator = IndianPlateValidator()
    val_res = validator.validate(raw_plate)

    assert val_res.is_valid is True
    assert val_res.normalized_plate == "GJ01ZZ2222"
    assert val_res.series == "ZZ"
    assert val_res.unique_number == "2222"

    payload = {
        "facilityId": "palika",
        "cameraId": "palika-entry-1",
        "gateType": "ENTRY",
        "plateNumber": val_res.normalized_plate,
        "confidence": 0.93,
    }
    res = api_client.post_anpr_event(payload)
    assert res["status_code"] == 201
    assert res["success"] is True
    assert res["status"] == "ACCEPTED"

    evt = fresh_db.query_one("SELECT * FROM anpr_events WHERE id = ?", (res["eventId"],))
    assert evt is not None
    assert evt["plate_number"] == "GJ01ZZ2222"
    assert fresh_db.get_live_occupancy("palika") == 1


def test_t2_b1_05_character_ambiguity_b_and_8(api_client: E2EApiClient, fresh_db: DatabaseAdapter):
    """T2-B1-05: Confusion between 'B' and '8'.

    Input: 'UP16BB8888'
    Expected: Series slot maintains 'BB', number slot maintains '8888' -> 'UP16BB8888'.
    """
    raw_plate = "UP16BB8888"
    validator = IndianPlateValidator()
    val_res = validator.validate(raw_plate)

    assert val_res.is_valid is True
    assert val_res.normalized_plate == "UP16BB8888"
    assert val_res.series == "BB"
    assert val_res.unique_number == "8888"

    payload = {
        "facilityId": "palika",
        "cameraId": "palika-entry-1",
        "gateType": "ENTRY",
        "plateNumber": val_res.normalized_plate,
        "confidence": 0.96,
    }
    res = api_client.post_anpr_event(payload)
    assert res["status_code"] == 201
    assert res["success"] is True
    assert res["status"] == "ACCEPTED"

    evt = fresh_db.query_one("SELECT * FROM anpr_events WHERE id = ?", (res["eventId"],))
    assert evt is not None
    assert evt["plate_number"] == "UP16BB8888"
    assert fresh_db.get_live_occupancy("palika") == 1
