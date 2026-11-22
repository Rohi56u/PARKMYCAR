"""Tier 3: Pairwise Cross-Feature Combination Tests for ParkMyCar ANPR.

Test Cases:
- T3-C01: Entry -> Rapid Duplicate -> Exit
- T3-C02: Low-confidence entry -> NEEDS_REVIEW -> Operator manual edit -> Session created -> Exit
- T3-C03: Camera dropout mid-session -> Reconnect -> Valid exit
- T3-C04: Unmatched exit alert -> Operator links to manual session -> Occupancy reconciled
- T3-C05: Overstay vehicle exit with multi-day tariff calculation
- T3-C06: Concurrent entry and exit of two different vehicles
- T3-C07: Entry -> Camera drop -> Exit -> Camera reconnect -> State integrity
- T3-C08: Cooldown debounce -> Valid exit after cooldown expires
- T3-C09: Needs review rejected by operator -> Duplicate entry attempt -> Valid session
- T3-C10: Bharat Series vehicle entry -> Regular plate vehicle entry -> Interleaved exits
- T3-C11: Commercial plate entry -> Rate tariff calculation on exit
- T3-C12: Out-of-order exit alert -> Subsequent valid entry -> Normal exit
- T3-C13: Full capacity saturation -> Rejection -> One exit -> Immediate re-entry allowed
- T3-C14: Unmatched exit rejected -> Flagged audit log
- T3-C15: Rapid 10-vehicle batch entry and exit pipeline
"""

from __future__ import annotations

import pytest

try:
    from tests.e2e.harness import (
        CameraSimulator,
        DatabaseAdapter,
        E2EApiClient,
        PlateCropGenerator,
        PlateGenerator,
    )
    CameraFeedEmulator = CameraSimulator
except ImportError:
    from harness import (
        CameraSimulator,
        DatabaseAdapter,
        E2EApiClient,
        PlateCropGenerator,
        PlateGenerator,
    )
    CameraFeedEmulator = CameraSimulator


# -----------------------------------------------------------------------------
# T3-C01: Entry -> Rapid Duplicate -> Exit
# -----------------------------------------------------------------------------
def test_t3_c01_entry_rapid_duplicate_exit(
    camera_sim: CameraFeedEmulator,
    exit_camera_sim: CameraFeedEmulator,
    api_client: E2EApiClient,
    fresh_db: DatabaseAdapter,
):
    """T3-C01: Vehicle entry followed by rapid duplicate detection, then clean exit."""
    plate = "DL01AB1234"

    # Step 1: Initial Entry at t = 0s
    res_entry = camera_sim.simulate_detection(
        plate_number=plate,
        confidence=0.95,
        detected_at="2026-11-21T10:00:00Z",
    )
    assert res_entry["status_code"] == 201
    assert res_entry["status"] == "ACCEPTED"
    assert res_entry["liveOccupancy"] == 1
    assert res_entry["availableCapacity"] == 899

    # Authoritative DB assertion: exactly 1 active INSIDE session
    active_session = fresh_db.get_active_session("palika", plate)
    assert active_session is not None
    assert active_session["status"] == "INSIDE"

    # Step 2: Rapid duplicate read at t = 15s on the same camera (within 120s cooldown)
    res_duplicate = camera_sim.simulate_detection(
        plate_number=plate,
        confidence=0.96,
        detected_at="2026-11-21T10:00:15Z",
    )
    assert res_duplicate["status_code"] == 200
    assert res_duplicate["status"] == "COOLDOWN_IGNORED"
    assert res_duplicate["liveOccupancy"] == 1

    # Authoritative DB assertion: still only 1 active session in the database
    all_sessions = fresh_db.query(
        "SELECT * FROM vehicle_sessions WHERE facility_id='palika' AND plate_number=?;",
        (plate,),
    )
    assert len(all_sessions) == 1
    assert fresh_db.get_live_occupancy("palika") == 1

    # Step 3: Exit at t = 1800s (30 minutes stay) via Exit Camera
    res_exit = exit_camera_sim.simulate_detection(
        plate_number=plate,
        confidence=0.95,
        detected_at="2026-11-21T10:30:00Z",
    )
    assert res_exit["status_code"] == 200
    assert res_exit["status"] == "ACCEPTED"
    assert res_exit["durationSeconds"] == 1800
    assert res_exit["liveOccupancy"] == 0
    assert res_exit["availableCapacity"] == 900

    # Final DB assertions: session transitioned to EXITED and occupancy authoritatively 0
    session_row = fresh_db.query_one(
        "SELECT * FROM vehicle_sessions WHERE id=?;",
        (res_exit["sessionId"],),
    )
    assert session_row["status"] == "EXITED"
    assert session_row["duration_seconds"] == 1800
    assert fresh_db.get_live_occupancy("palika") == 0


# -----------------------------------------------------------------------------
# T3-C02: Low-confidence entry -> NEEDS_REVIEW -> Operator manual edit -> Exit
# -----------------------------------------------------------------------------
def test_t3_c02_low_confidence_review_operator_edit_exit(
    camera_sim: CameraFeedEmulator,
    exit_camera_sim: CameraFeedEmulator,
    api_client: E2EApiClient,
    fresh_db: DatabaseAdapter,
):
    """T3-C02: Low-confidence entry routed to review queue, resolved by operator, then exited."""
    raw_plate_with_typo = "DL01AB123O"  # 'O' instead of '0' in last numeric slot
    corrected_plate = "DL01AB1230"

    # Step 1: Entry with confidence 0.65 (below 0.80 threshold)
    res_entry = camera_sim.simulate_detection(
        plate_number=raw_plate_with_typo,
        confidence=0.65,
        detected_at="2026-11-21T10:00:00Z",
    )
    assert res_entry["status"] == "NEEDS_REVIEW"
    assert res_entry["liveOccupancy"] == 0
    event_id = res_entry["eventId"]

    # Invariant: No active session created for unverified low-confidence reads
    assert fresh_db.get_active_session("palika", raw_plate_with_typo) is None
    assert fresh_db.get_active_session("palika", corrected_plate) is None
    assert fresh_db.get_live_occupancy("palika") == 0

    # Step 2: Query operator review queue
    queue_res = api_client.get_review_queue("palika")
    assert queue_res["count"] >= 1
    assert any(item["id"] == event_id for item in queue_res["items"])

    # Step 3: Operator resolves event via CONFIRM_ENTRY with corrected plate
    resolve_res = api_client.resolve_review_item(
        event_id=event_id,
        action="CONFIRM_ENTRY",
        corrected_plate=corrected_plate,
        notes="Operator corrected glyph O to 0",
    )
    assert resolve_res["success"] is True
    assert resolve_res["liveOccupancy"] == 1
    assert resolve_res["availableCapacity"] == 899
    session_id = resolve_res["sessionId"]

    # Authoritative DB assertion: Session created as INSIDE with review status MANUALLY_CORRECTED
    session = fresh_db.query_one("SELECT * FROM vehicle_sessions WHERE id=?;", (session_id,))
    assert session["status"] == "INSIDE"
    assert session["plate_number"] == corrected_plate
    assert session["review_status"] == "MANUALLY_CORRECTED"
    assert fresh_db.get_live_occupancy("palika") == 1

    # Step 4: Corrected vehicle exits normally at t = 3600s
    res_exit = exit_camera_sim.simulate_detection(
        plate_number=corrected_plate,
        confidence=0.95,
        detected_at="2026-11-21T11:00:00Z",
    )
    assert res_exit["status"] == "ACCEPTED"
    assert res_exit["sessionId"] == session_id
    assert res_exit["liveOccupancy"] == 0
    assert res_exit["availableCapacity"] == 900

    # Final DB assertion
    updated_session = fresh_db.query_one("SELECT * FROM vehicle_sessions WHERE id=?;", (session_id,))
    assert updated_session["status"] == "EXITED"
    assert updated_session["duration_seconds"] == 3600


# -----------------------------------------------------------------------------
# T3-C03: Camera dropout mid-session -> Reconnect -> Valid exit
# -----------------------------------------------------------------------------
def test_t3_c03_camera_dropout_mid_session_reconnect_exit(
    camera_sim: CameraFeedEmulator,
    exit_camera_sim: CameraFeedEmulator,
    fresh_db: DatabaseAdapter,
):
    """T3-C03: Camera goes offline mid-session; isolation ensures session persistence and clean exit."""
    plate = "DL01CD2345"

    # Step 1: Vehicle enters normally
    res_entry = camera_sim.simulate_detection(
        plate_number=plate,
        confidence=0.95,
        detected_at="2026-11-21T10:00:00Z",
    )
    assert res_entry["status"] == "ACCEPTED"
    assert fresh_db.get_live_occupancy("palika") == 1

    # Step 2: Entry camera drops offline (heartbeat ceases / network disconnect)
    disc = camera_sim.disconnect()
    assert disc["status"] == "OFFLINE"

    cam_db = fresh_db.query_one("SELECT * FROM parking_cameras WHERE id=?;", (camera_sim.camera_id,))
    assert cam_db["status"] == "OFFLINE"

    # Strict Disconnection Isolation Invariant:
    # Camera disconnection MUST NEVER alter active sessions or decrement occupancy!
    assert fresh_db.get_live_occupancy("palika") == 1
    active_session = fresh_db.get_active_session("palika", plate)
    assert active_session is not None
    assert active_session["status"] == "INSIDE"

    # Step 3: Entry camera reconnects
    rec = camera_sim.reconnect(fps=25.0)
    assert rec["status"] == "ONLINE"
    cam_db_after = fresh_db.query_one("SELECT * FROM parking_cameras WHERE id=?;", (camera_sim.camera_id,))
    assert cam_db_after["status"] == "ONLINE"
    assert fresh_db.get_live_occupancy("palika") == 1

    # Step 4: Vehicle exits via exit camera
    res_exit = exit_camera_sim.simulate_detection(
        plate_number=plate,
        confidence=0.95,
        detected_at="2026-11-21T10:45:00Z",
    )
    assert res_exit["status"] == "ACCEPTED"
    assert res_exit["durationSeconds"] == 2700
    assert fresh_db.get_live_occupancy("palika") == 0


# -----------------------------------------------------------------------------
# T3-C04: Unmatched exit alert -> Operator links to manual session -> Occupancy reconciled
# -----------------------------------------------------------------------------
def test_t3_c04_unmatched_exit_alert_operator_link_occupancy_reconciled(
    camera_sim: CameraFeedEmulator,
    exit_camera_sim: CameraFeedEmulator,
    api_client: E2EApiClient,
    fresh_db: DatabaseAdapter,
):
    """T3-C04: Unmatched exit with OCR misread triggers alert, operator links to active session."""
    correct_plate = "DL01EF3456"
    misread_exit_plate = "DL01EF3450"  # OCR misread 6 as 0 (valid syntax, but wrong plate)

    # Step 1: Vehicle enters with correct plate
    res_entry = camera_sim.simulate_detection(
        plate_number=correct_plate,
        confidence=0.95,
        detected_at="2026-11-21T10:00:00Z",
    )
    assert res_entry["status"] == "ACCEPTED"
    assert fresh_db.get_live_occupancy("palika") == 1

    # Step 2: Exit camera captures misread plate
    res_exit = exit_camera_sim.simulate_detection(
        plate_number=misread_exit_plate,
        confidence=0.90,
        detected_at="2026-11-21T11:00:00Z",
    )
    assert res_exit["status"] == "UNMATCHED_EXIT"
    assert res_exit["success"] is False
    # Strict Invariant: Unmatched exit NEVER decrements occupancy!
    assert res_exit["liveOccupancy"] == 1
    assert fresh_db.get_live_occupancy("palika") == 1
    unmatched_event_id = res_exit["eventId"]

    # Step 3: Operator inspects review queue and links misread exit to active session
    q = api_client.get_review_queue("palika")
    assert any(item["id"] == unmatched_event_id for item in q["items"])

    resolve_res = api_client.resolve_review_item(
        event_id=unmatched_event_id,
        action="CONFIRM_EXIT",
        corrected_plate=correct_plate,
        notes="Matched exit crop typo 0 to active inside session 6",
    )
    assert resolve_res["success"] is True
    assert resolve_res["action"] == "CONFIRM_EXIT"
    assert resolve_res["liveOccupancy"] == 0

    # Step 4: Authoritative DB assertions
    active = fresh_db.get_active_session("palika", correct_plate)
    assert active is None  # No longer INSIDE

    closed_session = fresh_db.query_one(
        "SELECT * FROM vehicle_sessions WHERE facility_id='palika' AND plate_number=?;",
        (correct_plate,),
    )
    assert closed_session["status"] == "EXITED"
    assert closed_session["review_status"] == "MANUALLY_CORRECTED"
    assert closed_session["duration_seconds"] == 3600
    assert fresh_db.get_live_occupancy("palika") == 0


# -----------------------------------------------------------------------------
# T3-C05: Overstay vehicle exit with multi-day tariff calculation
# -----------------------------------------------------------------------------
def test_t3_c05_overstay_multi_day_tariff_calculation(
    camera_sim: CameraFeedEmulator,
    exit_camera_sim: CameraFeedEmulator,
    fresh_db: DatabaseAdapter,
):
    """T3-C05: Vehicle parks for 5 days (120 hours); verifies multi-day duration and tariff."""
    plate = "DL01GH4567"
    entry_ts = "2026-11-16T10:00:00Z"
    exit_ts = "2026-11-21T10:00:00Z"  # Exactly 5 days (120 hours = 432,000s)

    # Step 1: Entry 5 days prior
    res_entry = camera_sim.simulate_detection(
        plate_number=plate,
        confidence=0.95,
        detected_at=entry_ts,
    )
    assert res_entry["status"] == "ACCEPTED"
    assert fresh_db.get_live_occupancy("palika") == 1

    # Step 2: Vehicle departs after 5 days
    res_exit = exit_camera_sim.simulate_detection(
        plate_number=plate,
        confidence=0.95,
        detected_at=exit_ts,
    )
    assert res_exit["status"] == "ACCEPTED"
    assert res_exit["durationSeconds"] == 432000
    # Tariff calculation: 20 base + 120 * 10 = 1220.0
    assert res_exit["calculatedTariff"] == 1220.0
    assert res_exit["liveOccupancy"] == 0
    assert res_exit["availableCapacity"] == 900

    # Step 3: DB assertions
    session = fresh_db.query_one(
        "SELECT * FROM vehicle_sessions WHERE id=?;",
        (res_exit["sessionId"],),
    )
    assert session["status"] == "EXITED"
    assert session["duration_seconds"] == 432000
    assert session["calculated_tariff"] == 1220.0
    assert fresh_db.get_live_occupancy("palika") == 0


# -----------------------------------------------------------------------------
# T3-C06: Concurrent entry and exit of two different vehicles
# -----------------------------------------------------------------------------
def test_t3_c06_concurrent_entry_exit_two_vehicles(
    camera_sim: CameraFeedEmulator,
    exit_camera_sim: CameraFeedEmulator,
    fresh_db: DatabaseAdapter,
):
    """T3-C06: Simultaneous entry of Vehicle B and exit of Vehicle A at different gates."""
    plate_a = "DL01AA1111"
    plate_b = "DL01BB2222"

    # Seed Vehicle A inside
    res_a_entry = camera_sim.simulate_detection(
        plate_number=plate_a,
        confidence=0.95,
        detected_at="2026-11-21T10:00:00Z",
    )
    assert res_a_entry["status"] == "ACCEPTED"
    assert fresh_db.get_live_occupancy("palika") == 1

    # Concurrently: Vehicle B enters at Entry Gate while Vehicle A exits at Exit Gate at same second
    timestamp = "2026-11-21T10:30:00Z"
    res_b_entry = camera_sim.simulate_detection(
        plate_number=plate_b,
        confidence=0.95,
        detected_at=timestamp,
    )
    res_a_exit = exit_camera_sim.simulate_detection(
        plate_number=plate_a,
        confidence=0.95,
        detected_at=timestamp,
    )

    assert res_b_entry["status"] == "ACCEPTED"
    assert res_a_exit["status"] == "ACCEPTED"

    # Net occupancy: 1 baseline + 1 entry - 1 exit = 1
    assert fresh_db.get_live_occupancy("palika") == 1
    assert fresh_db.get_available_capacity("palika") == 899

    # DB state checks
    session_b = fresh_db.get_active_session("palika", plate_b)
    assert session_b is not None
    assert session_b["status"] == "INSIDE"

    session_a = fresh_db.get_active_session("palika", plate_a)
    assert session_a is None  # Exited


# -----------------------------------------------------------------------------
# T3-C07: Entry -> Camera drop -> Exit -> Camera reconnect -> State integrity
# -----------------------------------------------------------------------------
def test_t3_c07_entry_camera_drop_exit_reconnect_integrity(
    camera_sim: CameraFeedEmulator,
    exit_camera_sim: CameraFeedEmulator,
    fresh_db: DatabaseAdapter,
):
    """T3-C07: Entry occurs, entry camera drops; vehicle exits while camera offline; state preserved on reconnect."""
    plate = "DL01IJ5678"

    # Step 1: Vehicle enters
    res_entry = camera_sim.simulate_detection(
        plate_number=plate,
        confidence=0.95,
        detected_at="2026-11-21T10:00:00Z",
    )
    assert res_entry["status"] == "ACCEPTED"
    assert fresh_db.get_live_occupancy("palika") == 1

    # Step 2: Entry camera disconnects
    camera_sim.disconnect()
    assert fresh_db.query_one("SELECT status FROM parking_cameras WHERE id=?;", (camera_sim.camera_id,))["status"] == "OFFLINE"

    # Step 3: Vehicle exits while entry camera is STILL offline
    res_exit = exit_camera_sim.simulate_detection(
        plate_number=plate,
        confidence=0.95,
        detected_at="2026-11-21T10:30:00Z",
    )
    assert res_exit["status"] == "ACCEPTED"
    assert fresh_db.get_live_occupancy("palika") == 0

    # Step 4: Entry camera comes back online
    camera_sim.reconnect(fps=25.0)
    assert fresh_db.query_one("SELECT status FROM parking_cameras WHERE id=?;", (camera_sim.camera_id,))["status"] == "ONLINE"

    # Step 5: Assert final integrity
    assert fresh_db.get_live_occupancy("palika") == 0
    assert fresh_db.get_available_capacity("palika") == 900
    active = fresh_db.get_active_session("palika", plate)
    assert active is None


# -----------------------------------------------------------------------------
# T3-C08: Cooldown debounce -> Valid exit after cooldown expires
# -----------------------------------------------------------------------------
def test_t3_c08_cooldown_debounce_exit_after_cooldown_expires(
    camera_sim: CameraFeedEmulator,
    exit_camera_sim: CameraFeedEmulator,
    api_client: E2EApiClient,
    fresh_db: DatabaseAdapter,
):
    """T3-C08: Vehicle idling debounced, cooldown expires, then vehicle exits normally."""
    plate = "DL01KL6789"

    # Step 1: Vehicle enters at t = 0s
    res1 = camera_sim.simulate_detection(
        plate_number=plate,
        confidence=0.95,
        detected_at="2026-11-21T10:00:00Z",
    )
    assert res1["status"] == "ACCEPTED"

    # Step 2: Second read at t = 20s (idling in front of barrier)
    res2 = camera_sim.simulate_detection(
        plate_number=plate,
        confidence=0.95,
        detected_at="2026-11-21T10:00:20Z",
    )
    assert res2["status"] == "COOLDOWN_IGNORED"
    assert fresh_db.get_live_occupancy("palika") == 1

    # Step 3: Reset/expire cooldown window
    api_client.reset_cooldown()

    # Step 4: Vehicle exits via exit camera at t = 3600s
    res_exit = exit_camera_sim.simulate_detection(
        plate_number=plate,
        confidence=0.95,
        detected_at="2026-11-21T11:00:00Z",
    )
    assert res_exit["status"] == "ACCEPTED"
    assert res_exit["durationSeconds"] == 3600
    assert res_exit["liveOccupancy"] == 0

    # Exactly 1 session recorded in DB
    all_sessions = fresh_db.query(
        "SELECT * FROM vehicle_sessions WHERE plate_number=?;",
        (plate,),
    )
    assert len(all_sessions) == 1
    assert all_sessions[0]["status"] == "EXITED"


# -----------------------------------------------------------------------------
# T3-C09: Needs review rejected by operator -> Duplicate entry attempt -> Valid session
# -----------------------------------------------------------------------------
def test_t3_c09_needs_review_rejected_then_valid_entry(
    camera_sim: CameraFeedEmulator,
    api_client: E2EApiClient,
    fresh_db: DatabaseAdapter,
):
    """T3-C09: Low-confidence noise rejected by operator, followed by clean read establishing valid session."""
    noisy_read = "DL01??9999"
    valid_plate = "DL01MN9999"

    # Step 1: Noisy read triggers NEEDS_REVIEW
    res_noise = camera_sim.simulate_detection(
        plate_number=noisy_read,
        confidence=0.55,
        detected_at="2026-11-21T10:00:00Z",
    )
    assert res_noise["status"] == "NEEDS_REVIEW"
    event_id = res_noise["eventId"]
    assert fresh_db.get_live_occupancy("palika") == 0

    # Step 2: Operator rejects the spurious detection
    reject_res = api_client.resolve_review_item(
        event_id=event_id,
        action="REJECT",
        notes="Spurious reflection / non-plate object",
    )
    assert reject_res["success"] is True
    assert reject_res["action"] == "REJECT"

    rejected_event = fresh_db.query_one("SELECT * FROM anpr_events WHERE id=?;", (event_id,))
    assert rejected_event["status"] == "REJECTED"
    assert fresh_db.get_live_occupancy("palika") == 0

    # Step 3: Vehicle attempts entry with clear plate read
    res_valid = camera_sim.simulate_detection(
        plate_number=valid_plate,
        confidence=0.95,
        detected_at="2026-11-21T10:02:00Z",
    )
    assert res_valid["status"] == "ACCEPTED"
    assert res_valid["liveOccupancy"] == 1
    assert fresh_db.get_live_occupancy("palika") == 1

    # Authoritative DB assertion: 1 active session in the database
    active = fresh_db.get_active_session("palika", valid_plate)
    assert active is not None
    assert active["status"] == "INSIDE"


# -----------------------------------------------------------------------------
# T3-C10: Bharat Series vehicle entry -> Regular plate vehicle entry -> Interleaved exits
# -----------------------------------------------------------------------------
def test_t3_c10_bharat_series_and_regular_plate_interleaved_exits(
    camera_sim: CameraFeedEmulator,
    exit_camera_sim: CameraFeedEmulator,
    fresh_db: DatabaseAdapter,
):
    """T3-C10: Bharat Series (BH) plate and standard HSRP plate enter and exit in interleaved order."""
    bh_plate = "22BH1234AA"
    regular_plate = "DL01OP1234"

    # Step 1: Bharat Series enters at 10:00:00
    res_bh = camera_sim.simulate_detection(
        plate_number=bh_plate,
        confidence=0.95,
        detected_at="2026-11-21T10:00:00Z",
    )
    assert res_bh["status"] == "ACCEPTED"
    assert fresh_db.get_live_occupancy("palika") == 1

    # Step 2: Regular HSRP enters at 10:10:00
    res_reg = camera_sim.simulate_detection(
        plate_number=regular_plate,
        confidence=0.95,
        detected_at="2026-11-21T10:10:00Z",
    )
    assert res_reg["status"] == "ACCEPTED"
    assert fresh_db.get_live_occupancy("palika") == 2

    # Step 3: Bharat Series exits first at 10:30:00 (30 min stay)
    res_bh_exit = exit_camera_sim.simulate_detection(
        plate_number=bh_plate,
        confidence=0.95,
        detected_at="2026-11-21T10:30:00Z",
    )
    assert res_bh_exit["status"] == "ACCEPTED"
    assert res_bh_exit["durationSeconds"] == 1800
    assert fresh_db.get_live_occupancy("palika") == 1

    # Step 4: Regular plate exits second at 11:10:00 (60 min stay)
    res_reg_exit = exit_camera_sim.simulate_detection(
        plate_number=regular_plate,
        confidence=0.95,
        detected_at="2026-11-21T11:10:00Z",
    )
    assert res_reg_exit["status"] == "ACCEPTED"
    assert res_reg_exit["durationSeconds"] == 3600
    assert fresh_db.get_live_occupancy("palika") == 0

    # DB state: Both sessions marked EXITED
    s_bh = fresh_db.query_one("SELECT * FROM vehicle_sessions WHERE plate_number=?;", (bh_plate,))
    s_reg = fresh_db.query_one("SELECT * FROM vehicle_sessions WHERE plate_number=?;", (regular_plate,))
    assert s_bh["status"] == "EXITED"
    assert s_reg["status"] == "EXITED"
    assert fresh_db.get_live_occupancy("palika") == 0


# -----------------------------------------------------------------------------
# T3-C11: Commercial plate entry -> Rate tariff calculation on exit
# -----------------------------------------------------------------------------
def test_t3_c11_commercial_plate_entry_tariff_on_exit(
    camera_sim: CameraFeedEmulator,
    exit_camera_sim: CameraFeedEmulator,
    fresh_db: DatabaseAdapter,
):
    """T3-C11: Commercial yellow plate entry, parking for 3 hours, tariff calculated on departure."""
    comm_plate = "DL1T1234"

    # Step 1: Entry at 10:00:00
    res_entry = camera_sim.simulate_detection(
        plate_number=comm_plate,
        confidence=0.95,
        detected_at="2026-11-21T10:00:00Z",
        bg_color="yellow",
    )
    assert res_entry["status"] == "ACCEPTED"
    assert fresh_db.get_live_occupancy("palika") == 1

    # Step 2: Exit 3 hours later at 13:00:00 (10,800 seconds)
    res_exit = exit_camera_sim.simulate_detection(
        plate_number=comm_plate,
        confidence=0.95,
        detected_at="2026-11-21T13:00:00Z",
        bg_color="yellow",
    )
    assert res_exit["status"] == "ACCEPTED"
    assert res_exit["durationSeconds"] == 10800
    # Tariff calculation: 20 base + 3 * 10 = 50.0
    assert res_exit["calculatedTariff"] == 50.0
    assert res_exit["liveOccupancy"] == 0

    # Authoritative DB assertion
    session = fresh_db.query_one("SELECT * FROM vehicle_sessions WHERE id=?;", (res_exit["sessionId"],))
    assert session["status"] == "EXITED"
    assert session["duration_seconds"] == 10800
    assert session["calculated_tariff"] == 50.0


# -----------------------------------------------------------------------------
# T3-C12: Out-of-order exit alert -> Subsequent valid entry -> Normal exit
# -----------------------------------------------------------------------------
def test_t3_c12_out_of_order_exit_subsequent_entry_normal_exit(
    camera_sim: CameraFeedEmulator,
    exit_camera_sim: CameraFeedEmulator,
    api_client: E2EApiClient,
    fresh_db: DatabaseAdapter,
):
    """T3-C12: Exit detected prior to any entry triggers alert; subsequent valid entry and exit complete lifecycle."""
    plate = "DL01QR4321"

    # Step 1: Spurious/out-of-order exit event arrives first
    res_bad_exit = exit_camera_sim.simulate_detection(
        plate_number=plate,
        confidence=0.95,
        detected_at="2026-11-21T10:00:00Z",
    )
    assert res_bad_exit["status"] == "UNMATCHED_EXIT"
    assert res_bad_exit["success"] is False
    assert fresh_db.get_live_occupancy("palika") == 0

    # Step 2: Vehicle arrives and enters through Entry Gate
    res_entry = camera_sim.simulate_detection(
        plate_number=plate,
        confidence=0.95,
        detected_at="2026-11-21T10:05:00Z",
    )
    assert res_entry["status"] == "ACCEPTED"
    assert fresh_db.get_live_occupancy("palika") == 1

    # Reset cooldown so legitimate exit after parking is processed
    api_client.reset_cooldown()

    # Step 3: Vehicle departs through Exit Gate
    res_good_exit = exit_camera_sim.simulate_detection(
        plate_number=plate,
        confidence=0.95,
        detected_at="2026-11-21T10:35:00Z",
    )
    assert res_good_exit["status"] == "ACCEPTED"
    assert res_good_exit["durationSeconds"] == 1800
    assert fresh_db.get_live_occupancy("palika") == 0

    # Authoritative DB verification:
    # 1 UNMATCHED_EXIT event + 1 ACCEPTED entry event + 1 ACCEPTED exit event
    events = fresh_db.query("SELECT * FROM anpr_events WHERE plate_number=? ORDER BY detected_at ASC;", (plate,))
    assert len(events) == 3
    assert events[0]["status"] == "UNMATCHED_EXIT"
    assert events[1]["status"] == "ACCEPTED"
    assert events[2]["status"] == "ACCEPTED"


# -----------------------------------------------------------------------------
# T3-C13: Full capacity saturation -> Rejection -> One exit -> Immediate re-entry allowed
# -----------------------------------------------------------------------------
def test_t3_c13_full_capacity_saturation_rejection_exit_reentry(
    camera_sim: CameraFeedEmulator,
    exit_camera_sim: CameraFeedEmulator,
    api_client: E2EApiClient,
    fresh_db: DatabaseAdapter,
):
    """T3-C13: Facility saturation at capacity 900, available drops to 0, exit opens space, immediate re-entry."""
    facility_id = "palika"
    total_cap = 900
    now = "2026-11-21T08:00:00Z"

    # Step 1: Pre-populate facility to 100% saturation (900 active INSIDE sessions)
    for i in range(1, total_cap + 1):
        p = f"DL01CA{i:04d}"
        fresh_db.execute(
            "INSERT INTO vehicles (plate_number, state_code, vehicle_class, first_seen_at, last_seen_at, total_sessions, created_at) "
            "VALUES (?, 'DL', 'CAR', ?, ?, 1, ?);",
            (p, now, now, now),
        )
        fresh_db.execute(
            "INSERT INTO vehicle_sessions (id, facility_id, plate_number, status, entry_time, review_status, created_at, updated_at) "
            "VALUES (?, ?, ?, 'INSIDE', ?, 'VERIFIED', ?, ?);",
            (f"ses_cap_{i:04d}", facility_id, p, now, now, now),
        )

    # Sync and verify capacity metrics at saturation
    api_client._sync_facility_observation(facility_id)
    assert fresh_db.get_live_occupancy(facility_id) == total_cap
    assert fresh_db.get_available_capacity(facility_id) == 0

    occ_metrics = api_client.get_facility_occupancy(facility_id)
    assert occ_metrics["vehiclesInside"] == 900
    assert occ_metrics["availableCapacity"] == 0
    assert occ_metrics["occupancyRate"] == 100.0

    latest_obs = fresh_db.query_one(
        "SELECT * FROM observations WHERE facility_id=? ORDER BY observed_at DESC LIMIT 1;",
        (facility_id,),
    )
    assert latest_obs["state"] == "FULL"

    # Step 2: One parked vehicle exits
    exiting_plate = "DL01CA0001"
    res_exit = exit_camera_sim.simulate_detection(
        plate_number=exiting_plate,
        confidence=0.95,
        detected_at="2026-11-21T10:00:00Z",
    )
    assert res_exit["status"] == "ACCEPTED"
    assert res_exit["liveOccupancy"] == 899
    assert res_exit["availableCapacity"] == 1
    assert fresh_db.get_live_occupancy(facility_id) == 899

    latest_obs_after_exit = fresh_db.query_one(
        "SELECT * FROM observations WHERE facility_id=? ORDER BY observed_at DESC LIMIT 1;",
        (facility_id,),
    )
    # At 899/900 (>80% capacity), observation transitions from FULL to LIMITED
    assert latest_obs_after_exit["state"] == "LIMITED"

    # Step 3: Immediate re-entry of new vehicle fills the open spot
    new_plate = "DL01FR9999"
    res_reentry = camera_sim.simulate_detection(
        plate_number=new_plate,
        confidence=0.95,
        detected_at="2026-11-21T10:02:00Z",
    )
    assert res_reentry["status"] == "ACCEPTED"
    assert res_reentry["liveOccupancy"] == 900
    assert res_reentry["availableCapacity"] == 0
    assert fresh_db.get_live_occupancy(facility_id) == 900

    latest_obs_after_reentry = fresh_db.query_one(
        "SELECT * FROM observations WHERE facility_id=? ORDER BY observed_at DESC LIMIT 1;",
        (facility_id,),
    )
    assert latest_obs_after_reentry["state"] == "FULL"


# -----------------------------------------------------------------------------
# T3-C14: Unmatched exit rejected -> Flagged audit log
# -----------------------------------------------------------------------------
def test_t3_c14_unmatched_exit_rejected_audit_log(
    exit_camera_sim: CameraFeedEmulator,
    api_client: E2EApiClient,
    fresh_db: DatabaseAdapter,
):
    """T3-C14: Unmatched exit arrives, operator rejects as phantom noise, logged in audit trail."""
    unknown_plate = "DL01ZZ9999"

    # Step 1: Unmatched exit arrives
    res = exit_camera_sim.simulate_detection(
        plate_number=unknown_plate,
        confidence=0.92,
        detected_at="2026-11-21T10:00:00Z",
    )
    assert res["status"] == "UNMATCHED_EXIT"
    assert res["liveOccupancy"] == 0
    event_id = res["eventId"]

    # Step 2: Event in review queue
    q = api_client.get_review_queue("palika")
    assert any(item["id"] == event_id for item in q["items"])

    # Step 3: Operator rejects the unmatched exit event
    reject_res = api_client.resolve_review_item(
        event_id=event_id,
        action="REJECT",
        notes="Phantom exit detection; no vehicle present",
    )
    assert reject_res["success"] is True
    assert reject_res["action"] == "REJECT"

    # Step 4: Verify audit log and cleared queue
    evt = fresh_db.query_one("SELECT * FROM anpr_events WHERE id=?;", (event_id,))
    assert evt["status"] == "REJECTED"
    assert "REJECTED" in evt["review_reason"]

    # Review queue cleared
    q_after = api_client.get_review_queue("palika")
    assert not any(item["id"] == event_id for item in q_after["items"])
    assert fresh_db.get_live_occupancy("palika") == 0


# -----------------------------------------------------------------------------
# T3-C15: Rapid 10-vehicle batch entry and exit pipeline
# -----------------------------------------------------------------------------
def test_t3_c15_rapid_10_vehicle_batch_entry_exit_pipeline(
    camera_sim: CameraFeedEmulator,
    exit_camera_sim: CameraFeedEmulator,
    fresh_db: DatabaseAdapter,
):
    """T3-C15: Batch of 10 distinct vehicles sequentially enters, occupancy tracks to 10, then all exit to 0."""
    plates = [f"DL01BT{i:04d}" for i in range(1, 11)]

    # Step 1: Sequentially enter all 10 vehicles
    for idx, plate in enumerate(plates, start=1):
        res = camera_sim.simulate_detection(
            plate_number=plate,
            confidence=0.95,
            detected_at=f"2026-11-21T10:{idx:02d}:00Z",
        )
        assert res["status"] == "ACCEPTED"
        assert res["liveOccupancy"] == idx
        assert fresh_db.get_live_occupancy("palika") == idx

    # Verify all 10 active INSIDE sessions exist in DB
    active_count = fresh_db.query_one(
        "SELECT COUNT(*) AS c FROM vehicle_sessions WHERE facility_id='palika' AND status='INSIDE';"
    )["c"]
    assert active_count == 10
    assert fresh_db.get_available_capacity("palika") == 890

    # Step 2: Sequentially exit all 10 vehicles
    for idx, plate in enumerate(plates, start=1):
        res = exit_camera_sim.simulate_detection(
            plate_number=plate,
            confidence=0.95,
            detected_at=f"2026-11-21T11:{idx:02d}:00Z",
        )
        assert res["status"] == "ACCEPTED"
        assert res["durationSeconds"] == 3600
        expected_remaining = 10 - idx
        assert res["liveOccupancy"] == expected_remaining
        assert fresh_db.get_live_occupancy("palika") == expected_remaining

    # Final DB assertions: 0 inside, 10 exited, available capacity = 900
    final_inside = fresh_db.query_one(
        "SELECT COUNT(*) AS c FROM vehicle_sessions WHERE facility_id='palika' AND status='INSIDE';"
    )["c"]
    final_exited = fresh_db.query_one(
        "SELECT COUNT(*) AS c FROM vehicle_sessions WHERE facility_id='palika' AND status='EXITED';"
    )["c"]
    assert final_inside == 0
    assert final_exited == 10
    assert fresh_db.get_available_capacity("palika") == 900
