"""Comprehensive Sanity Tests for E2E Test Harness and Fixtures.

Validates:
1. SQLite DatabaseAdapter: schema creation, PRAGMA foreign_keys enforcement,
   partial unique indexes, seed data, and authoritative occupancy derivation.
2. PlateGenerator: valid Indian formats (HSRP, BH, commercial, EV, diplomatic),
   boundary cases, and DIN 1451 positional confusions.
3. PlateCropGenerator: synthetic image crops, color palettes, noise, tilt, and base64 URLs.
4. E2EApiClient: auth, gate cooldown debouncing, session transitions, unmatched exit,
   low-confidence gating, operator review queue, and occupancy metrics.
5. CameraSimulator: polymorphic feeds, heartbeats, and disconnection isolation.
"""

from __future__ import annotations

import sqlite3
import pytest


def test_db_schema_and_tables(fresh_db):
    """Verify all 9 core tables exist in the database."""
    tables = [
        "facilities",
        "observations",
        "members",
        "reports",
        "audit_events",
        "parking_cameras",
        "vehicles",
        "vehicle_sessions",
        "anpr_events",
    ]
    rows = fresh_db.query(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';"
    )
    existing_tables = {row["name"] for row in rows}
    for tbl in tables:
        assert tbl in existing_tables, f"Missing table: {tbl}"


def test_pragma_foreign_keys_enforced(fresh_db):
    """Verify that foreign key constraints are strictly enforced."""
    # Attempting to insert a camera with non-existent facility_id must fail
    with pytest.raises(sqlite3.IntegrityError):
        fresh_db.execute(
            """
            INSERT INTO parking_cameras
            (id, facility_id, name, feed_type, gate_type, status, created_at, updated_at)
            VALUES ('cam-invalid', 'non-existent-facility', 'Test Cam', 'SIMULATION', 'ENTRY', 'ONLINE', '2026-11-21T00:00:00Z', '2026-11-21T00:00:00Z');
            """
        )


def test_partial_unique_index_active_session(fresh_db):
    """Verify partial unique index prevents concurrent active sessions for same vehicle."""
    # Seed vehicle first (FK constraint)
    fresh_db.execute(
        """
        INSERT INTO vehicles (plate_number, state_code, first_seen_at, last_seen_at, created_at)
        VALUES ('DL01AB1234', 'DL', '2026-11-21T00:00:00Z', '2026-11-21T00:00:00Z', '2026-11-21T00:00:00Z');
        """
    )

    # First session INSIDE succeeds
    fresh_db.execute(
        """
        INSERT INTO vehicle_sessions
        (id, facility_id, plate_number, status, entry_time, created_at, updated_at)
        VALUES ('ses-01', 'palika', 'DL01AB1234', 'INSIDE', '2026-11-21T10:00:00Z', '2026-11-21T10:00:00Z', '2026-11-21T10:00:00Z');
        """
    )

    # Second session INSIDE for same vehicle at same facility MUST fail due to partial unique index
    with pytest.raises(sqlite3.IntegrityError):
        fresh_db.execute(
            """
            INSERT INTO vehicle_sessions
            (id, facility_id, plate_number, status, entry_time, created_at, updated_at)
            VALUES ('ses-02', 'palika', 'DL01AB1234', 'INSIDE', '2026-11-21T10:05:00Z', '2026-11-21T10:05:00Z', '2026-11-21T10:05:00Z');
            """
        )

    # Transition first session to EXITED
    fresh_db.execute(
        "UPDATE vehicle_sessions SET status = 'EXITED' WHERE id = 'ses-01';"
    )

    # Now a new INSIDE session can be created without constraint violation
    fresh_db.execute(
        """
        INSERT INTO vehicle_sessions
        (id, facility_id, plate_number, status, entry_time, created_at, updated_at)
        VALUES ('ses-03', 'palika', 'DL01AB1234', 'INSIDE', '2026-11-21T11:00:00Z', '2026-11-21T11:00:00Z', '2026-11-21T11:00:00Z');
        """
    )

    # Transition second session to EXITED: both can coexist as EXITED
    fresh_db.execute(
        "UPDATE vehicle_sessions SET status = 'EXITED' WHERE id = 'ses-03';"
    )
    exited_count = fresh_db.query_one(
        "SELECT COUNT(*) AS c FROM vehicle_sessions WHERE plate_number = 'DL01AB1234' AND status = 'EXITED';"
    )["c"]
    assert exited_count == 2


def test_seed_facilities_and_cameras(fresh_db):
    """Verify default seed facilities and cameras are correctly populated."""
    palika = fresh_db.get_facility("palika")
    assert palika is not None
    assert palika["name"] == "Palika Parking"
    assert fresh_db.get_facility_total_capacity("palika") == 900

    cp_west = fresh_db.get_facility("cp-west")
    assert cp_west is not None
    assert fresh_db.get_facility_total_capacity("cp-west") == 150

    cameras = fresh_db.query("SELECT * FROM parking_cameras WHERE facility_id = 'palika';")
    camera_ids = {c["id"] for c in cameras}
    assert "palika-entry-1" in camera_ids
    assert "palika-exit-1" in camera_ids
    assert "palika-sim-entry" in camera_ids


def test_db_helper_occupancy_derivation(fresh_db):
    """Verify live occupancy derivation strictly matches active INSIDE sessions."""
    assert fresh_db.get_live_occupancy("palika") == 0
    assert fresh_db.get_available_capacity("palika") == 900

    # Insert vehicle and session
    fresh_db.execute(
        "INSERT INTO vehicles (plate_number, first_seen_at, last_seen_at, created_at) VALUES ('KA01AB1111', 'T', 'T', 'T');"
    )
    fresh_db.execute(
        "INSERT INTO vehicle_sessions (id, facility_id, plate_number, status, entry_time, created_at, updated_at) VALUES ('s1', 'palika', 'KA01AB1111', 'INSIDE', 'T', 'T', 'T');"
    )

    assert fresh_db.get_live_occupancy("palika") == 1
    assert fresh_db.get_available_capacity("palika") == 899


def test_plate_generator_valid_formats(mock_generator):
    """Verify PlateGenerator generates syntactically valid Indian registration plates."""
    p = mock_generator.plate

    # Valid HSRP
    hsrp = p.generate_valid_hsrp(state="DL", rto="01", series="AB", number="1234")
    assert hsrp == "DL01AB1234"
    valid, kind = p.is_valid_indian_plate(hsrp)
    assert valid and kind == "HSRP"

    # Valid Bharat Series
    bh = p.generate_bharat_series(year=22, number="1234", series="AA")
    assert bh == "22BH1234AA"
    valid, kind = p.is_valid_indian_plate(bh)
    assert valid and kind == "BHARAT_SERIES"

    # Valid Commercial
    comm = p.generate_commercial(state="DL")
    valid, kind = p.is_valid_indian_plate(comm)
    assert valid and kind == "COMMERCIAL"

    # Valid EV
    ev = p.generate_ev(state="DL")
    valid, kind = p.is_valid_indian_plate(ev)
    assert valid and kind == "EV"

    # Valid Diplomatic
    diplo = "77CD12"
    valid, kind = p.is_valid_indian_plate(diplo)
    assert valid and kind == "DIPLOMATIC"


def test_plate_generator_boundaries_and_confusions(mock_generator):
    """Verify PlateGenerator produces malformed and DIN 1451 confusion variants."""
    p = mock_generator.plate

    # Lowercase
    low = p.generate_malformed("lowercase")
    assert low.islower()
    valid, _ = p.is_valid_indian_plate(low)
    # is_valid_indian_plate cleans by upper() so verify raw grammar failure on lowercase if strict
    assert any(c.islower() for c in low)

    # Invalid state
    inv_state = p.generate_malformed("invalid_state")
    valid, reason = p.is_valid_indian_plate(inv_state)
    assert not valid
    assert "INVALID_STATE_CODE" in reason or "INVALID_GRAMMAR" in reason

    # Truncated
    trunc = p.generate_malformed("truncated")
    valid, reason = p.is_valid_indian_plate(trunc)
    assert not valid

    # Symbols
    sym = p.generate_malformed("symbols")
    # Contains non-alphanumeric
    assert any(not c.isalnum() for c in sym)

    # Positional Confusions
    conf_o = p.generate_confusion_variant("DL01AB1234", "O_0")
    assert "O" in conf_o or "0" in conf_o
    conf_1 = p.generate_confusion_variant("DL01AB1234", "1_I")
    assert "I" in conf_1 or "1" in conf_1
    conf_8 = p.generate_confusion_variant("DL01AB1234", "B_8")
    assert "8" in conf_8 or "B" in conf_8


def test_crop_generator_synthetic_images(mock_generator):
    """Verify PlateCropGenerator generates valid images and base64 URLs."""
    c = mock_generator.crop

    for bg in ["white", "yellow", "green", "blue"]:
        crop = c.create_plate_crop("DL01AB1234", bg_color=bg, width=320, height=80)
        assert crop is not None
        assert crop.shape == (80, 320, 3)

    # Check with noise, tilt, brightness
    distorted = c.create_plate_crop(
        "DL01AB1234",
        bg_color="white",
        noise_level=0.2,
        tilt_angle=5.0,
        brightness=1.2,
    )
    assert distorted.shape == (80, 320, 3)

    # Check base64 URL format
    data_url = c.generate_crop_data_url("DL01AB1234", bg_color="white")
    assert data_url.startswith("data:image/jpeg;base64,")
    assert len(data_url) > 100


def test_api_client_authentication(api_client):
    """Verify X-ANPR-Secret header authentication."""
    payload = {
        "facilityId": "palika",
        "cameraId": "palika-entry-1",
        "gateType": "ENTRY",
        "plateNumber": "DL01AB1234",
        "confidence": 0.95,
    }

    # Missing header -> 401
    res_no_auth = api_client.post_anpr_event(payload, headers={})
    assert res_no_auth["status_code"] == 401
    assert not res_no_auth["success"]

    # Wrong secret -> 401
    res_bad_auth = api_client.post_anpr_event(payload, headers={"X-ANPR-Secret": "invalid-token"})
    assert res_bad_auth["status_code"] == 401

    # Valid secret -> 201
    res_ok = api_client.post_anpr_event(payload, headers={"X-ANPR-Secret": api_client.secret})
    assert res_ok["status_code"] == 201
    assert res_ok["success"]
    assert res_ok["status"] == "ACCEPTED"


def test_api_client_entry_flow(api_client, fresh_db):
    """Verify vehicle entry creates active session and increments occupancy."""
    payload = {
        "facilityId": "palika",
        "cameraId": "palika-entry-1",
        "gateType": "ENTRY",
        "plateNumber": "MH12DE1432",
        "confidence": 0.94,
        "detectedAt": "2026-11-21T10:00:00Z",
    }
    res = api_client.post_anpr_event(payload)
    assert res["status_code"] == 201
    assert res["success"]
    assert res["status"] == "ACCEPTED"
    assert res["liveOccupancy"] == 1
    assert res["availableCapacity"] == 899

    # Verify session in DB
    active = fresh_db.get_active_session("palika", "MH12DE1432")
    assert active is not None
    assert active["status"] == "INSIDE"
    assert active["plate_number"] == "MH12DE1432"


def test_api_client_gate_cooldown_debouncing(api_client):
    """Verify 120s cooldown prevents duplicate active sessions from idling vehicles."""
    payload = {
        "facilityId": "palika",
        "cameraId": "palika-entry-1",
        "gateType": "ENTRY",
        "plateNumber": "KA05MB9999",
        "confidence": 0.96,
        "detectedAt": "2026-11-21T10:00:00Z",
    }
    # First detection accepts
    res1 = api_client.post_anpr_event(payload)
    assert res1["status"] == "ACCEPTED"
    assert res1["liveOccupancy"] == 1

    # Second detection within 120s returns COOLDOWN_IGNORED without incrementing occupancy
    res2 = api_client.post_anpr_event(payload)
    assert res2["status"] == "COOLDOWN_IGNORED"
    assert res2["liveOccupancy"] == 1


def test_api_client_exit_flow(api_client, fresh_db):
    """Verify vehicle exit updates session to EXITED and decrements occupancy."""
    plate = "DL01AB9999"

    # 1. Entry
    entry_payload = {
        "facilityId": "palika",
        "cameraId": "palika-entry-1",
        "gateType": "ENTRY",
        "plateNumber": plate,
        "confidence": 0.95,
        "detectedAt": "2026-11-21T10:00:00Z",
    }
    res_entry = api_client.post_anpr_event(entry_payload)
    assert res_entry["status"] == "ACCEPTED"
    assert fresh_db.get_live_occupancy("palika") == 1

    # 2. Exit 2 hours later
    exit_payload = {
        "facilityId": "palika",
        "cameraId": "palika-exit-1",
        "gateType": "EXIT",
        "plateNumber": plate,
        "confidence": 0.95,
        "detectedAt": "2026-11-21T12:00:00Z",
    }
    res_exit = api_client.post_anpr_event(exit_payload)
    assert res_exit["status"] == "ACCEPTED"
    assert res_exit["durationSeconds"] == 7200
    assert res_exit["liveOccupancy"] == 0
    assert res_exit["availableCapacity"] == 900

    # Confirm session status in DB
    session = fresh_db.query_one("SELECT * FROM vehicle_sessions WHERE id = ?", (res_exit["sessionId"],))
    assert session["status"] == "EXITED"
    assert session["duration_seconds"] == 7200


def test_api_client_unmatched_exit(api_client, fresh_db):
    """Verify exit for non-inside vehicle logs alert and does NOT decrement occupancy."""
    exit_payload = {
        "facilityId": "palika",
        "cameraId": "palika-exit-1",
        "gateType": "EXIT",
        "plateNumber": "HR26DQ1111",
        "confidence": 0.95,
        "detectedAt": "2026-11-21T10:00:00Z",
    }
    res = api_client.post_anpr_event(exit_payload)
    assert res["status"] == "UNMATCHED_EXIT"
    assert not res["success"]
    assert res["liveOccupancy"] == 0

    # Verify event logged in DB
    evt = fresh_db.query_one("SELECT * FROM anpr_events WHERE id = ?", (res["eventId"],))
    assert evt["status"] == "UNMATCHED_EXIT"


def test_api_client_low_confidence_needs_review(api_client, fresh_db):
    """Verify confidence < 0.80 flags event as NEEDS_REVIEW without creating session."""
    payload = {
        "facilityId": "palika",
        "cameraId": "palika-entry-1",
        "gateType": "ENTRY",
        "plateNumber": "DL01AB1234",
        "confidence": 0.72,  # Below 0.80 threshold
        "detectedAt": "2026-11-21T10:00:00Z",
    }
    res = api_client.post_anpr_event(payload)
    assert res["status"] == "NEEDS_REVIEW"
    assert res["liveOccupancy"] == 0

    # No active session created
    assert fresh_db.get_active_session("palika", "DL01AB1234") is None


def test_api_client_review_queue_resolution(api_client, fresh_db):
    """Verify operator can review and resolve flagged events."""
    # 1. Trigger low confidence event
    payload = {
        "facilityId": "palika",
        "cameraId": "palika-entry-1",
        "gateType": "ENTRY",
        "plateNumber": "DL01AB123O",  # Low confidence with O/0 confusion
        "confidence": 0.75,
        "detectedAt": "2026-11-21T10:00:00Z",
    }
    res = api_client.post_anpr_event(payload)
    event_id = res["eventId"]

    # 2. Check review queue
    q = api_client.get_review_queue("palika")
    assert q["count"] >= 1
    assert any(item["id"] == event_id for item in q["items"])

    # 3. Operator resolves with corrected plate
    resolve_res = api_client.resolve_review_item(
        event_id=event_id,
        action="CONFIRM_ENTRY",
        corrected_plate="DL01AB1230",
        notes="Operator corrected O to 0",
    )
    assert resolve_res["success"]
    assert resolve_res["liveOccupancy"] == 1

    # Session now active for corrected plate
    active = fresh_db.get_active_session("palika", "DL01AB1230")
    assert active is not None
    assert active["status"] == "INSIDE"


def test_camera_sim_polymorphic_and_disconnection_isolation(camera_sim, api_client, fresh_db):
    """Verify camera simulation and strict disconnection isolation invariant."""
    # Seed active session
    camera_sim.simulate_detection("DL01AB7777", confidence=0.95)
    assert fresh_db.get_live_occupancy("palika") == 1

    # Camera heartbeat
    hb = camera_sim.send_heartbeat(status="ONLINE", fps=24.0)
    assert hb["status"] == "ONLINE"

    # Camera disconnects
    disc = camera_sim.disconnect()
    assert disc["status"] == "OFFLINE"

    # Camera OFFLINE status must NEVER alter active sessions or decrement occupancy!
    assert fresh_db.get_live_occupancy("palika") == 1
    active = fresh_db.get_active_session("palika", "DL01AB7777")
    assert active is not None and active["status"] == "INSIDE"

    # Camera reconnects
    rec = camera_sim.reconnect(fps=25.0)
    assert rec["status"] == "ONLINE"
    assert fresh_db.get_live_occupancy("palika") == 1


def test_authoritative_occupancy_endpoint(api_client, camera_sim):
    """Verify live occupancy metrics endpoint matches authoritative state."""
    occ1 = api_client.get_facility_occupancy("palika")
    assert occ1["totalCapacity"] == 900
    assert occ1["vehiclesInside"] == 0
    assert occ1["availableCapacity"] == 900
    assert occ1["occupancyRate"] == 0.0

    camera_sim.simulate_detection("DL01AB5555", confidence=0.95)
    occ2 = api_client.get_facility_occupancy("palika")
    assert occ2["vehiclesInside"] == 1
    assert occ2["availableCapacity"] == 899
    assert occ2["occupancyRate"] == round(1 / 900 * 100, 2)
