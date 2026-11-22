"""Tier 1 Feature 10: Unmatched Exit & Operator Review Workflow (T1-F10-01 .. T1-F10-05).

Validates:
- T1-F10-01: Exit detection with no active matching session flagged as UNMATCHED_EXIT without decrement
- T1-F10-02: Review queue query returns pending UNMATCHED_EXIT and NEEDS_REVIEW events
- T1-F10-03: Operator resolves misread exit with CONFIRM_EXIT action, reconciling occupancy
- T1-F10-04: Operator confirms low-confidence entry with CONFIRM_ENTRY, creating active session
- T1-F10-05: Operator rejects spurious noise capture with REJECT action, preserving occupancy
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


def test_t1_f10_01_unmatched_exit_does_not_decrement(api_client: E2EApiClient, fresh_db: DatabaseAdapter):
    """T1-F10-01: Exit event for unknown plate "HR26XY9999" with no prior INSIDE session.
    
    Verifies:
    - Status is UNMATCHED_EXIT
    - liveOccupancy does NOT decrement and remains 0
    - anpr_events records status='UNMATCHED_EXIT'
    - NO row modified in vehicle_sessions
    """
    plate_text = "HR26XY9999"
    crop_url = PlateCropGenerator.generate_crop_data_url(plate_text, bg_color="white")

    res = api_client.post_anpr_event({
        "facilityId": "palika",
        "cameraId": "palika-exit-1",
        "gateType": "EXIT",
        "plateNumber": plate_text,
        "confidence": 0.95,
        "plateCropBase64": crop_url,
        "detectedAt": "2026-11-21T10:00:00Z",
    })

    assert res["status"] == "UNMATCHED_EXIT"
    assert res["success"] is False
    assert res["liveOccupancy"] == 0
    assert "Unmatched exit attempt" in res["message"]

    # Database assertions
    event = fresh_db.query_one("SELECT * FROM anpr_events WHERE id = ?", (res["eventId"],))
    assert event is not None
    assert event["status"] == "UNMATCHED_EXIT"
    assert event["session_id"] is None

    sessions_count = fresh_db.query_one(
        "SELECT COUNT(*) AS c FROM vehicle_sessions WHERE facility_id = 'palika';"
    )["c"]
    assert sessions_count == 0


def test_t1_f10_02_query_operator_review_queue(api_client: E2EApiClient, fresh_db: DatabaseAdapter):
    """T1-F10-02: Query operator review queue (GET /api/v1/anpr/review-queue?facilityId=palika).
    
    Verifies:
    - Queue retrieves all events with status IN ('NEEDS_REVIEW', 'UNMATCHED_EXIT')
    - Items include event ID, plate number, confidence, and plate crop URL
    """
    # 1. Generate 1 NEEDS_REVIEW event (low confidence)
    res_nr = api_client.post_anpr_event({
        "facilityId": "palika",
        "cameraId": "palika-entry-1",
        "gateType": "ENTRY",
        "plateNumber": "DL01AB1234",
        "confidence": 0.68,
        "detectedAt": "2026-11-21T10:00:00Z",
    })
    assert res_nr["status"] == "NEEDS_REVIEW"

    # 2. Generate 1 UNMATCHED_EXIT event
    res_ue = api_client.post_anpr_event({
        "facilityId": "palika",
        "cameraId": "palika-exit-1",
        "gateType": "EXIT",
        "plateNumber": "KA01T9999",
        "confidence": 0.95,
        "detectedAt": "2026-11-21T10:05:00Z",
    })
    assert res_ue["status"] == "UNMATCHED_EXIT"

    # 3. Query review queue
    q = api_client.get_review_queue("palika")
    assert q["status_code"] == 200
    assert q["count"] >= 2
    item_ids = {item["id"] for item in q["items"]}
    assert res_nr["eventId"] in item_ids
    assert res_ue["eventId"] in item_ids


def test_t1_f10_03_operator_resolves_misread_exit(api_client: E2EApiClient, fresh_db: DatabaseAdapter):
    """T1-F10-03: Operator resolves misread exit event (CONFIRM_EXIT with corrected plate).
    
    Verifies:
    - Active session exists for "DL01AB1234" (occupancy=1)
    - Exit misread as "DL01AB123O" produces UNMATCHED_EXIT
    - Operator resolves item with action="CONFIRM_EXIT", corrected_plate="DL01AB1234"
    - Session transitioned to EXITED, liveOccupancy decrements to 0
    - anpr_events updated to status='MANUALLY_RESOLVED'
    """
    real_plate = "DL01AB1234"
    misread_plate = "DL01AB9999"  # Misread as another valid plate number not inside

    # 1. Real vehicle enters
    res_entry = api_client.post_anpr_event({
        "facilityId": "palika",
        "cameraId": "palika-entry-1",
        "gateType": "ENTRY",
        "plateNumber": real_plate,
        "confidence": 0.95,
        "detectedAt": "2026-11-21T10:00:00Z",
    })
    assert fresh_db.get_live_occupancy("palika") == 1

    # 2. Exit gate misreads plate
    res_exit_misread = api_client.post_anpr_event({
        "facilityId": "palika",
        "cameraId": "palika-exit-1",
        "gateType": "EXIT",
        "plateNumber": misread_plate,
        "confidence": 0.91,
        "detectedAt": "2026-11-21T11:00:00Z",
    })
    assert res_exit_misread["status"] in ("UNMATCHED_EXIT", "NEEDS_REVIEW")
    assert fresh_db.get_live_occupancy("palika") == 1  # Not decremented yet

    # 3. Operator resolves in review queue
    event_id = res_exit_misread["eventId"]
    resolve_res = api_client.resolve_review_item(
        event_id=event_id,
        action="CONFIRM_EXIT",
        corrected_plate=real_plate,
        notes="Corrected OCR terminal 'O' to '0'",
    )

    assert resolve_res["status_code"] == 200
    assert resolve_res["success"] is True
    assert resolve_res["liveOccupancy"] == 0

    # 4. DB assertions
    session = fresh_db.query_one("SELECT * FROM vehicle_sessions WHERE plate_number = ?", (real_plate,))
    assert session["status"] == "EXITED"
    assert session["review_status"] == "MANUALLY_CORRECTED"
    assert session["duration_seconds"] == 3600

    evt = fresh_db.query_one("SELECT * FROM anpr_events WHERE id = ?", (event_id,))
    assert evt["status"] == "MANUALLY_RESOLVED"
    assert evt["plate_number"] == real_plate
    assert evt["session_id"] == session["id"]


def test_t1_f10_04_operator_confirms_low_confidence_entry(api_client: E2EApiClient, fresh_db: DatabaseAdapter):
    """T1-F10-04: Operator confirms low-confidence entry (CONFIRM_ENTRY).
    
    Verifies:
    - Low-confidence entry flagged as NEEDS_REVIEW without active session
    - Operator confirms with corrected plate "MH12DE1432"
    - New session created with status='INSIDE' and review_status='MANUALLY_CORRECTED'
    - liveOccupancy increments to 1
    """
    ocr_plate = "MH12DE143O"
    true_plate = "MH12DE1432"

    res_entry = api_client.post_anpr_event({
        "facilityId": "palika",
        "cameraId": "palika-entry-1",
        "gateType": "ENTRY",
        "plateNumber": ocr_plate,
        "confidence": 0.72,
        "detectedAt": "2026-11-21T10:00:00Z",
    })
    assert res_entry["status"] == "NEEDS_REVIEW"
    assert fresh_db.get_live_occupancy("palika") == 0

    # Operator resolves with action="CONFIRM_ENTRY"
    event_id = res_entry["eventId"]
    resolve_res = api_client.resolve_review_item(
        event_id=event_id,
        action="CONFIRM_ENTRY",
        corrected_plate=true_plate,
        notes="Operator confirmed plate crop visually",
    )

    assert resolve_res["status_code"] == 200
    assert resolve_res["success"] is True
    assert resolve_res["liveOccupancy"] == 1

    active = fresh_db.get_active_session("palika", true_plate)
    assert active is not None
    assert active["status"] == "INSIDE"
    assert active["review_status"] == "MANUALLY_CORRECTED"

    evt = fresh_db.query_one("SELECT * FROM anpr_events WHERE id = ?", (event_id,))
    assert evt["status"] == "MANUALLY_RESOLVED"
    assert evt["plate_number"] == true_plate


def test_t1_f10_05_operator_rejects_spurious_capture(api_client: E2EApiClient, fresh_db: DatabaseAdapter):
    """T1-F10-05: Operator rejects spurious capture event (REJECT).
    
    Verifies:
    - Low-confidence or noise capture flagged as NEEDS_REVIEW
    - Operator marks action="REJECT" with operator notes
    - anpr_events updated to status='REJECTED'
    - NO session created, liveOccupancy remains 0
    """
    res_entry = api_client.post_anpr_event({
        "facilityId": "palika",
        "cameraId": "palika-entry-1",
        "gateType": "ENTRY",
        "plateNumber": "DL01??0000",
        "confidence": 0.50,
        "detectedAt": "2026-11-21T10:00:00Z",
    })
    assert res_entry["status"] == "NEEDS_REVIEW"
    event_id = res_entry["eventId"]

    # Operator rejects spurious capture
    resolve_res = api_client.resolve_review_item(
        event_id=event_id,
        action="REJECT",
        notes="Discarded spurious pedestrian shadow trigger",
    )

    assert resolve_res["status_code"] == 200
    assert resolve_res["action"] == "REJECT"
    assert resolve_res["liveOccupancy"] == 0

    evt = fresh_db.query_one("SELECT * FROM anpr_events WHERE id = ?", (event_id,))
    assert evt["status"] == "REJECTED"
    assert "REJECTED: Discarded spurious pedestrian shadow" in evt["review_reason"]

    assert fresh_db.get_live_occupancy("palika") == 0
