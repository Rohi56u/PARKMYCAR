"""Tier 4: Real-World Workload Scenarios for ParkMyCar ANPR & Live Parking Occupancy.

Simulates 5 complex multi-vehicle daily traffic scenarios:
- S1: Connaught Place Morning Rush (50 vehicles surge, 95% valid entries, 5% review queue, zero duplicate sessions, live occupancy exactly 50)
- S2: Midday Steady-State Turnover (20 entries, 20 exits across multiple gates, zero drift between DB and reported occupancy)
- S3: Evening Rush & Camera Dropout (30 exits, entry camera ethernet disconnect, camera marked OFFLINE, sessions and occupancy fully preserved)
- S4: Full Facility Saturation Limit (Palika capacity reaches 900, available capacity drops to 0, observation syncs to FULL)
- S5: Operator Shift Batch Review (batch resolution of 10 low-confidence reads and unmatched exits, authoritative live occupancy reconciliation)
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
# Scenario S1: Connaught Place Morning Rush
# -----------------------------------------------------------------------------
def test_s1_connaught_place_morning_rush(
    camera_sim: CameraFeedEmulator,
    api_client: E2EApiClient,
    fresh_db: DatabaseAdapter,
):
    """Scenario S1: 50 vehicles surge in morning peak across multiple gates.
    
    Workload:
    - 47 standard HSRP plates with high confidence (>0.90)
    - 1 EV Green plate (DL01EV1111) with polarity inversion
    - 1 Bharat Series plate (22BH9999AA)
    - 1 ambiguous read with low OCR confidence (DL01MR999O at 0.65)
    - Rapid duplicate barrier attempt debounced
    - Zero duplicate active sessions in database
    - Review queue item resolved by operator
    - Live occupancy authoritatively reaches exactly 50
    """
    facility_id = "palika"
    sim_cam = CameraSimulator(
        camera_id="palika-sim-entry",
        facility_id=facility_id,
        gate_type="ENTRY",
        api_client=api_client,
        db=fresh_db,
    )

    # 1. 47 Standard HSRP plates
    hsrp_plates = [f"DL01MR{i:04d}" for i in range(1, 48)]
    # 2. 1 EV plate
    ev_plate = "DL01EV1111"
    # 3. 1 Bharat Series plate
    bh_plate = "22BH9999AA"
    # 4. 1 Low-confidence ambiguous read
    ambiguous_read = "DL01MR999O"
    corrected_plate = "DL01MR9990"

    # Ingest 47 standard HSRP entries alternating between Entry 1 and Simulation Entry
    for idx, plate in enumerate(hsrp_plates, start=1):
        cam = camera_sim if idx % 2 == 1 else sim_cam
        res = cam.simulate_detection(
            plate_number=plate,
            confidence=0.94,
            detected_at=f"2026-11-21T08:{idx % 60:02d}:00Z",
        )
        assert res["status_code"] == 201
        assert res["status"] == "ACCEPTED"
        assert res["liveOccupancy"] == idx

    # Ingest EV entry
    res_ev = camera_sim.simulate_detection(
        plate_number=ev_plate,
        confidence=0.92,
        detected_at="2026-11-21T08:48:00Z",
        bg_color="green",
    )
    assert res_ev["status"] == "ACCEPTED"
    assert res_ev["liveOccupancy"] == 48

    # Ingest Bharat Series entry
    res_bh = sim_cam.simulate_detection(
        plate_number=bh_plate,
        confidence=0.95,
        detected_at="2026-11-21T08:49:00Z",
    )
    assert res_bh["status"] == "ACCEPTED"
    assert res_bh["liveOccupancy"] == 49

    # Ingest Low-confidence ambiguous read (< 0.80 threshold)
    res_amb = camera_sim.simulate_detection(
        plate_number=ambiguous_read,
        confidence=0.65,
        detected_at="2026-11-21T08:50:00Z",
    )
    assert res_amb["status"] == "NEEDS_REVIEW"
    assert res_amb["liveOccupancy"] == 49  # Unchanged
    amb_event_id = res_amb["eventId"]

    # Simulate rapid duplicate read of the first vehicle lingering at barrier (within 120s cooldown)
    res_dup = camera_sim.simulate_detection(
        plate_number=hsrp_plates[0],
        confidence=0.96,
        detected_at="2026-11-21T08:50:30Z",
    )
    assert res_dup["status"] == "COOLDOWN_IGNORED"
    assert res_dup["liveOccupancy"] == 49

    # Verify zero duplicate active sessions in DB
    dup_check = fresh_db.query(
        "SELECT COUNT(*) AS c FROM vehicle_sessions WHERE plate_number=? AND status='INSIDE';",
        (hsrp_plates[0],),
    )
    assert dup_check[0]["c"] == 1

    # Check review queue has exactly 1 pending item
    q = api_client.get_review_queue(facility_id)
    assert q["count"] == 1
    assert q["items"][0]["id"] == amb_event_id

    # Operator resolves the review item with corrected plate
    resolve_res = api_client.resolve_review_item(
        event_id=amb_event_id,
        action="CONFIRM_ENTRY",
        corrected_plate=corrected_plate,
        notes="Morning rush: operator verified blurred last digit O to 0",
    )
    assert resolve_res["success"] is True
    assert resolve_res["liveOccupancy"] == 50
    assert resolve_res["availableCapacity"] == 850

    # Final Authoritative Database Assertions:
    inside_count = fresh_db.query_one(
        "SELECT COUNT(*) AS c FROM vehicle_sessions WHERE facility_id='palika' AND status='INSIDE';"
    )["c"]
    assert inside_count == 50
    assert fresh_db.get_live_occupancy(facility_id) == 50
    assert fresh_db.get_available_capacity(facility_id) == 850

    # Occupancy rate = 50 / 900 = 5.56%
    occ_metrics = api_client.get_facility_occupancy(facility_id)
    assert occ_metrics["vehiclesInside"] == 50
    assert occ_metrics["availableCapacity"] == 850
    assert occ_metrics["occupancyRate"] == 5.56

    # Latest observation indicates facility is AVAILABLE
    obs = fresh_db.query_one(
        "SELECT * FROM observations WHERE facility_id=? ORDER BY observed_at DESC LIMIT 1;",
        (facility_id,),
    )
    assert obs["state"] == "AVAILABLE"


# -----------------------------------------------------------------------------
# Scenario S2: Midday Steady-State Turnover
# -----------------------------------------------------------------------------
def test_s2_midday_steady_state_turnover(
    camera_sim: CameraFeedEmulator,
    exit_camera_sim: CameraFeedEmulator,
    api_client: E2EApiClient,
    fresh_db: DatabaseAdapter,
):
    """Scenario S2: Continuous midday turnover: 20 entries, 20 exits, 5 duplicate reads debounced, zero drift."""
    facility_id = "palika"
    now_seed = "2026-11-21T09:00:00Z"

    # Pre-populate 20 baseline parked vehicles
    baseline_plates = [f"DL01BS{i:04d}" for i in range(1, 21)]
    for i, p in enumerate(baseline_plates, start=1):
        fresh_db.execute(
            "INSERT INTO vehicles (plate_number, state_code, vehicle_class, first_seen_at, last_seen_at, total_sessions, created_at) "
            "VALUES (?, 'DL', 'CAR', ?, ?, 1, ?);",
            (p, now_seed, now_seed, now_seed),
        )
        fresh_db.execute(
            "INSERT INTO vehicle_sessions (id, facility_id, plate_number, status, entry_time, review_status, created_at, updated_at) "
            "VALUES (?, ?, ?, 'INSIDE', ?, 'VERIFIED', ?, ?);",
            (f"ses_bs_{i:04d}", facility_id, p, now_seed, now_seed, now_seed),
        )

    api_client._sync_facility_observation(facility_id)
    assert fresh_db.get_live_occupancy(facility_id) == 20

    # 20 new vehicles entering
    new_plates = [f"DL01NW{i:04d}" for i in range(1, 21)]

    # Multi-gate simulation: alternate entries and exits across 20 turns
    for idx in range(20):
        # 1. New vehicle enters
        new_p = new_plates[idx]
        res_entry = camera_sim.simulate_detection(
            plate_number=new_p,
            confidence=0.95,
            detected_at=f"2026-11-21T12:{idx:02d}:00Z",
        )
        assert res_entry["status"] == "ACCEPTED"

        # Inject 5 duplicate barrier reads during the first 5 entries (within 120s cooldown)
        if idx < 5:
            res_dup = camera_sim.simulate_detection(
                plate_number=new_p,
                confidence=0.96,
                detected_at=f"2026-11-21T12:{idx:02d}:10Z",
            )
            assert res_dup["status"] == "COOLDOWN_IGNORED"

        # 2. Baseline vehicle exits
        bs_p = baseline_plates[idx]
        res_exit = exit_camera_sim.simulate_detection(
            plate_number=bs_p,
            confidence=0.95,
            detected_at=f"2026-11-21T12:{idx:02d}:30Z",
        )
        assert res_exit["status"] == "ACCEPTED"
        assert res_exit["durationSeconds"] > 0

    # Authoritative DB assertions:
    # Exactly 20 vehicles currently INSIDE (the 20 new ones)
    current_inside = fresh_db.query_one(
        "SELECT COUNT(*) AS c FROM vehicle_sessions WHERE facility_id='palika' AND status='INSIDE';"
    )["c"]
    assert current_inside == 20

    # Exactly 20 vehicles EXITED (the 20 baseline ones)
    current_exited = fresh_db.query_one(
        "SELECT COUNT(*) AS c FROM vehicle_sessions WHERE facility_id='palika' AND status='EXITED';"
    )["c"]
    assert current_exited == 20

    # Zero drift between database query and reported occupancy API endpoint
    live_db = fresh_db.get_live_occupancy(facility_id)
    api_occ = api_client.get_facility_occupancy(facility_id)["vehiclesInside"]
    assert live_db == 20
    assert api_occ == 20
    assert fresh_db.get_available_capacity(facility_id) == 880


# -----------------------------------------------------------------------------
# Scenario S3: Evening Rush & Camera Dropout
# -----------------------------------------------------------------------------
def test_s3_evening_rush_and_camera_dropout(
    camera_sim: CameraFeedEmulator,
    exit_camera_sim: CameraFeedEmulator,
    api_client: E2EApiClient,
    fresh_db: DatabaseAdapter,
):
    """Scenario S3: Evening rush: 30 exits, entry camera ethernet disconnect, sessions & occupancy preserved."""
    facility_id = "palika"
    now_seed = "2026-11-21T14:00:00Z"

    # Pre-populate 35 vehicles parked inside
    parked_plates = [f"DL01EV{i:04d}" for i in range(1, 36)]
    for i, p in enumerate(parked_plates, start=1):
        fresh_db.execute(
            "INSERT INTO vehicles (plate_number, state_code, vehicle_class, first_seen_at, last_seen_at, total_sessions, created_at) "
            "VALUES (?, 'DL', 'CAR', ?, ?, 1, ?);",
            (p, now_seed, now_seed, now_seed),
        )
        fresh_db.execute(
            "INSERT INTO vehicle_sessions (id, facility_id, plate_number, status, entry_time, review_status, created_at, updated_at) "
            "VALUES (?, ?, ?, 'INSIDE', ?, 'VERIFIED', ?, ?);",
            (f"ses_ev_{i:04d}", facility_id, p, now_seed, now_seed, now_seed),
        )

    api_client._sync_facility_observation(facility_id)
    assert fresh_db.get_live_occupancy(facility_id) == 35

    # Phase 1: First 10 vehicles exit normally
    for i in range(10):
        res = exit_camera_sim.simulate_detection(
            plate_number=parked_plates[i],
            confidence=0.95,
            detected_at=f"2026-11-21T18:{i:02d}:00Z",
        )
        assert res["status"] == "ACCEPTED"
    assert fresh_db.get_live_occupancy(facility_id) == 25

    # Phase 2: Entry camera suffers network disconnect / ethernet drop
    disc_res = camera_sim.disconnect()
    assert disc_res["status"] == "OFFLINE"
    cam_row = fresh_db.query_one("SELECT status FROM parking_cameras WHERE id=?;", (camera_sim.camera_id,))
    assert cam_row["status"] == "OFFLINE"

    # Strict Invariant: Camera going OFFLINE MUST NOT alter active sessions or decrement occupancy!
    assert fresh_db.get_live_occupancy(facility_id) == 25

    # Phase 3: Next 10 vehicles exit while entry camera is OFFLINE
    for i in range(10, 20):
        res = exit_camera_sim.simulate_detection(
            plate_number=parked_plates[i],
            confidence=0.95,
            detected_at=f"2026-11-21T18:{i:02d}:00Z",
        )
        assert res["status"] == "ACCEPTED"
    assert fresh_db.get_live_occupancy(facility_id) == 15

    # Phase 4: 1 dirty plate read at exit resulting in UNMATCHED_EXIT
    dirty_plate = "DL01ZZ0099"
    res_unmatched = exit_camera_sim.simulate_detection(
        plate_number=dirty_plate,
        confidence=0.91,
        detected_at="2026-11-21T18:25:00Z",
    )
    assert res_unmatched["status"] == "UNMATCHED_EXIT"
    # Occupancy must NOT decrement for unmatched exit
    assert fresh_db.get_live_occupancy(facility_id) == 15

    # Phase 5: Final 10 vehicles exit (total 30 exits out of 35)
    for i in range(20, 30):
        res = exit_camera_sim.simulate_detection(
            plate_number=parked_plates[i],
            confidence=0.95,
            detected_at=f"2026-11-21T18:{i + 10:02d}:00Z",
        )
        assert res["status"] == "ACCEPTED"
    assert fresh_db.get_live_occupancy(facility_id) == 5

    # Phase 6: Entry camera reconnects
    rec_res = camera_sim.reconnect(fps=25.0)
    assert rec_res["status"] == "ONLINE"
    assert fresh_db.query_one("SELECT status FROM parking_cameras WHERE id=?;", (camera_sim.camera_id,))["status"] == "ONLINE"

    # Final Invariants & Assertions:
    # Exactly 30 sessions in EXITED state
    exited_count = fresh_db.query_one(
        "SELECT COUNT(*) AS c FROM vehicle_sessions WHERE facility_id='palika' AND status='EXITED';"
    )["c"]
    assert exited_count == 30

    # Exactly 5 sessions remaining INSIDE
    inside_count = fresh_db.query_one(
        "SELECT COUNT(*) AS c FROM vehicle_sessions WHERE facility_id='palika' AND status='INSIDE';"
    )["c"]
    assert inside_count == 5
    assert fresh_db.get_live_occupancy(facility_id) == 5
    assert fresh_db.get_available_capacity(facility_id) == 895

    # Review queue contains the unmatched exit event
    q = api_client.get_review_queue(facility_id)
    assert any(item["id"] == res_unmatched["eventId"] for item in q["items"])


# -----------------------------------------------------------------------------
# Scenario S4: Full Facility Saturation Limit
# -----------------------------------------------------------------------------
def test_s4_full_facility_saturation_limit(
    camera_sim: CameraFeedEmulator,
    exit_camera_sim: CameraFeedEmulator,
    api_client: E2EApiClient,
    fresh_db: DatabaseAdapter,
):
    """Scenario S4: Palika saturation to 900 capacity, available drops to 0, observation syncs to FULL."""
    facility_id = "palika"
    total_cap = 900
    now_seed = "2026-11-21T07:00:00Z"

    # Step 1: Pre-populate facility with 900 active INSIDE sessions
    for i in range(1, total_cap + 1):
        p = f"DL01ST{i:04d}"
        fresh_db.execute(
            "INSERT INTO vehicles (plate_number, state_code, vehicle_class, first_seen_at, last_seen_at, total_sessions, created_at) "
            "VALUES (?, 'DL', 'CAR', ?, ?, 1, ?);",
            (p, now_seed, now_seed, now_seed),
        )
        fresh_db.execute(
            "INSERT INTO vehicle_sessions (id, facility_id, plate_number, status, entry_time, review_status, created_at, updated_at) "
            "VALUES (?, ?, ?, 'INSIDE', ?, 'VERIFIED', ?, ?);",
            (f"ses_st_{i:04d}", facility_id, p, now_seed, now_seed, now_seed),
        )

    # Synchronize observation
    api_client._sync_facility_observation(facility_id)

    # Verify saturation invariants
    assert fresh_db.get_live_occupancy(facility_id) == 900
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

    # Step 2: 2 vehicles exit
    res_exit1 = exit_camera_sim.simulate_detection(
        plate_number="DL01ST0001",
        confidence=0.95,
        detected_at="2026-11-21T10:00:00Z",
    )
    assert res_exit1["status"] == "ACCEPTED"
    assert res_exit1["liveOccupancy"] == 899
    assert res_exit1["availableCapacity"] == 1

    res_exit2 = exit_camera_sim.simulate_detection(
        plate_number="DL01ST0002",
        confidence=0.95,
        detected_at="2026-11-21T10:01:00Z",
    )
    assert res_exit2["status"] == "ACCEPTED"
    assert res_exit2["liveOccupancy"] == 898
    assert res_exit2["availableCapacity"] == 2

    # At 898/900 (>80%), state transitions from FULL to LIMITED
    latest_obs_2 = fresh_db.query_one(
        "SELECT * FROM observations WHERE facility_id=? ORDER BY observed_at DESC LIMIT 1;",
        (facility_id,),
    )
    assert latest_obs_2["state"] == "LIMITED"

    # Step 3: 2 waiting vehicles enter to return facility to FULL
    res_in1 = camera_sim.simulate_detection(
        plate_number="DL01WT0001",
        confidence=0.95,
        detected_at="2026-11-21T10:05:00Z",
    )
    assert res_in1["status"] == "ACCEPTED"
    assert res_in1["liveOccupancy"] == 899
    assert res_in1["availableCapacity"] == 1

    res_in2 = camera_sim.simulate_detection(
        plate_number="DL01WT0002",
        confidence=0.95,
        detected_at="2026-11-21T10:06:00Z",
    )
    assert res_in2["status"] == "ACCEPTED"
    assert res_in2["liveOccupancy"] == 900
    assert res_in2["availableCapacity"] == 0

    # Observation returns to FULL
    latest_obs_final = fresh_db.query_one(
        "SELECT * FROM observations WHERE facility_id=? ORDER BY observed_at DESC LIMIT 1;",
        (facility_id,),
    )
    assert latest_obs_final["state"] == "FULL"
    assert fresh_db.get_live_occupancy(facility_id) == 900


# -----------------------------------------------------------------------------
# Scenario S5: Operator Shift Batch Review
# -----------------------------------------------------------------------------
def test_s5_operator_shift_batch_review(
    camera_sim: CameraFeedEmulator,
    exit_camera_sim: CameraFeedEmulator,
    api_client: E2EApiClient,
    fresh_db: DatabaseAdapter,
):
    """Scenario S5: Batch resolution of 10 low-confidence reads and unmatched exits; authoritative reconciliation."""
    facility_id = "palika"
    now_seed = "2026-11-21T08:00:00Z"

    # Baseline: 10 parked vehicles inside
    baseline_plates = [f"DL01OP{i:04d}" for i in range(1, 11)]
    for i, p in enumerate(baseline_plates, start=1):
        fresh_db.execute(
            "INSERT INTO vehicles (plate_number, state_code, vehicle_class, first_seen_at, last_seen_at, total_sessions, created_at) "
            "VALUES (?, 'DL', 'CAR', ?, ?, 1, ?);",
            (p, now_seed, now_seed, now_seed),
        )
        fresh_db.execute(
            "INSERT INTO vehicle_sessions (id, facility_id, plate_number, status, entry_time, review_status, created_at, updated_at) "
            "VALUES (?, ?, ?, 'INSIDE', ?, 'VERIFIED', ?, ?);",
            (f"ses_op_{i:04d}", facility_id, p, now_seed, now_seed, now_seed),
        )

    api_client._sync_facility_observation(facility_id)
    initial_occupancy = fresh_db.get_live_occupancy(facility_id)
    assert initial_occupancy == 10

    # 1. Generate 5 NEEDS_REVIEW entry events:
    # 4 valid vehicles with slight OCR blur/typos:
    entry_review_plates = [
        ("DL01AB111O", "DL01AB1110"),
        ("DL01AB222I", "DL01AB2221"),
        ("DL01AB333B", "DL01AB3338"),
        ("DL01AB444S", "DL01AB4445"),
    ]
    entry_event_ids = []
    for raw_p, _ in entry_review_plates:
        res = camera_sim.simulate_detection(
            plate_number=raw_p,
            confidence=0.65,
            detected_at="2026-11-21T13:00:00Z",
        )
        assert res["status"] == "NEEDS_REVIEW"
        entry_event_ids.append(res["eventId"])

    # 1 non-vehicle debris:
    res_debris = camera_sim.simulate_detection(
        plate_number="DL01??9999",
        confidence=0.50,
        detected_at="2026-11-21T13:05:00Z",
    )
    assert res_debris["status"] == "NEEDS_REVIEW"
    debris_event_id = res_debris["eventId"]

    # 2. Generate 5 UNMATCHED_EXIT events:
    # 4 misread exit attempts targeting baseline vehicles DL01OP0001 .. DL01OP0004
    misread_exit_plates = [
        ("DL01OP9901", baseline_plates[0]),
        ("DL01OP9902", baseline_plates[1]),
        ("DL01OP9903", baseline_plates[2]),
        ("DL01OP9904", baseline_plates[3]),
    ]
    exit_event_ids = []
    for raw_exit, _ in misread_exit_plates:
        res = exit_camera_sim.simulate_detection(
            plate_number=raw_exit,
            confidence=0.91,
            detected_at="2026-11-21T13:10:00Z",
        )
        assert res["status"] == "UNMATCHED_EXIT"
        exit_event_ids.append(res["eventId"])

    # 1 phantom exit of non-existent car
    res_phantom = exit_camera_sim.simulate_detection(
        plate_number="DL01ZZ0000",
        confidence=0.92,
        detected_at="2026-11-21T13:15:00Z",
    )
    assert res_phantom["status"] == "UNMATCHED_EXIT"
    phantom_event_id = res_phantom["eventId"]

    # Invariant: None of the 10 unverified events altered live occupancy!
    assert fresh_db.get_live_occupancy(facility_id) == 10

    # Review queue contains exactly 10 pending items (5 NEEDS_REVIEW + 5 UNMATCHED_EXIT)
    q = api_client.get_review_queue(facility_id)
    assert q["count"] == 10

    # Operator Shift Review: Batch resolve all 10 items
    # A. Approve 4 entry events with corrected registration numbers (+4 active sessions)
    for idx, (raw_p, corr_p) in enumerate(entry_review_plates):
        evt_id = entry_event_ids[idx]
        res = api_client.resolve_review_item(
            event_id=evt_id,
            action="CONFIRM_ENTRY",
            corrected_plate=corr_p,
            notes=f"Shift operator verified {raw_p} -> {corr_p}",
        )
        assert res["success"] is True

    # B. Reject 1 entry debris event
    res_rej_entry = api_client.resolve_review_item(
        event_id=debris_event_id,
        action="REJECT",
        notes="Debris / wind-blown newspaper artifact",
    )
    assert res_rej_entry["success"] is True

    # C. Match 4 unmatched exit events to their respective baseline sessions (-4 active sessions)
    for idx, (raw_exit, corr_exit) in enumerate(misread_exit_plates):
        evt_id = exit_event_ids[idx]
        res = api_client.resolve_review_item(
            event_id=evt_id,
            action="CONFIRM_EXIT",
            corrected_plate=corr_exit,
            notes=f"Shift operator matched exit crop {raw_exit} to inside session {corr_exit}",
        )
        assert res["success"] is True

    # D. Reject 1 phantom exit event
    res_rej_exit = api_client.resolve_review_item(
        event_id=phantom_event_id,
        action="REJECT",
        notes="Phantom exit detection rejected",
    )
    assert res_rej_exit["success"] is True

    # Authoritative Reconciliation Assertions:
    # 1. Review queue is now completely cleared (0 items)
    q_final = api_client.get_review_queue(facility_id)
    assert q_final["count"] == 0
    assert len(q_final["items"]) == 0

    # 2. Net live occupancy reconciles authoritatively:
    # Initial 10 + 4 (approved entries) - 4 (confirmed exits) = exactly 10!
    final_occupancy = fresh_db.get_live_occupancy(facility_id)
    assert final_occupancy == 10
    assert api_client.get_facility_occupancy(facility_id)["vehiclesInside"] == 10

    # 3. Database session and event states:
    # 4 newly created sessions have review_status = 'MANUALLY_CORRECTED' and status = 'INSIDE'
    corrected_inside = fresh_db.query_one(
        "SELECT COUNT(*) AS c FROM vehicle_sessions WHERE facility_id='palika' AND review_status='MANUALLY_CORRECTED' AND status='INSIDE';"
    )["c"]
    assert corrected_inside == 4

    # 4 baseline sessions updated to EXITED with review_status = 'MANUALLY_CORRECTED'
    corrected_exited = fresh_db.query_one(
        "SELECT COUNT(*) AS c FROM vehicle_sessions WHERE facility_id='palika' AND review_status='MANUALLY_CORRECTED' AND status='EXITED';"
    )["c"]
    assert corrected_exited == 4

    # Exactly 2 rejected events in anpr_events
    rejected_count = fresh_db.query_one(
        "SELECT COUNT(*) AS c FROM anpr_events WHERE facility_id='palika' AND status='REJECTED';"
    )["c"]
    assert rejected_count == 2
