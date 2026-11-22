# E2E Test Infra: ParkMyCar ANPR & Live Parking Occupancy Tracking

## Test Philosophy
- **Opaque-Box & Requirement-Driven**: Tests strictly exercise public interface contracts (REST HTTP endpoints, Cloudflare D1/SQLite schemas, and simulated camera event streams) derived from `ORIGINAL_REQUEST.md`. No test depends on internal private implementation classes.
- **Authoritative Database Invariants**: Live occupancy is authoritatively verified via `SELECT COUNT(*) FROM vehicle_sessions WHERE facility_id=? AND status='INSIDE'`. Available capacity is strictly `totalCapacity - liveOccupancy`.
- **Methodology**: Systematic 4-tier testing hierarchy combining Category-Partition, Boundary Value Analysis (BVA), Pairwise Combinatorial Testing, and Realistic Multi-Vehicle Workload Simulations.

## Feature Inventory
| # | Feature | Source (Requirement) | Tier 1 (Features) | Tier 2 (Boundaries) | Tier 3 (Combinations) | Tier 4 (Workloads) |
|---|---------|----------------------|:-----------------:|:-------------------:|:---------------------:|:-------------------:|
| F1 | YOLO License Plate Detection | ORIGINAL_REQUEST R2, PROJECT F4 | 5 | 5 | ✓ | ✓ |
| F2 | CLAHE Preprocessing & OCR Engine | ORIGINAL_REQUEST R2, PROJECT F5 | 5 | 5 | ✓ | ✓ |
| F3 | Indian Registration Grammar Validator | ORIGINAL_REQUEST R2, PROJECT F6 | 5 | 5 | ✓ | ✓ |
| F4 | Positional Normalization & Review Gating | ORIGINAL_REQUEST R2, PROJECT F7 | 5 | 5 | ✓ | ✓ |
| F5 | Polymorphic Feeds & Simulation Ingest | ORIGINAL_REQUEST R3, PROJECT F8 | 5 | 5 | ✓ | ✓ |
| F6 | Gate Cooldown Debouncing (120s Cache) | ORIGINAL_REQUEST R3, PROJECT F10 | 5 | 5 | ✓ | ✓ |
| F7 | Camera Disconnection Isolation | ORIGINAL_REQUEST R3, PROJECT F11 | 5 | 5 | ✓ | ✓ |
| F8 | Vehicle Entry Session & Occupancy Increment | ORIGINAL_REQUEST R4, PROJECT F12, F13 | 5 | 5 | ✓ | ✓ |
| F9 | Vehicle Exit Matching, Duration & Decrement | ORIGINAL_REQUEST R4, PROJECT F14, F16 | 5 | 5 | ✓ | ✓ |
| F10 | Unmatched Exit & Operator Review Workflow | ORIGINAL_REQUEST R5, R6, PROJECT F15, F20 | 5 | 5 | ✓ | ✓ |
| **Total** | **10 Core System Features** | | **50** | **50** | **15** | **5** |

## Test Architecture
- **Test Runner**: Python 3.14 + `pytest` (with standalone runner `tests/e2e/run_all.py` for direct execution).
- **Harness & Fixtures**:
  - `tests/e2e/harness/db_adapter.py`: Standalone SQLite database manager executing Drizzle D1 schemas (`0000_smart_prima.sql` + `0002_anpr_tables.sql`) with foreign keys and partial unique indexes (`WHERE status = 'INSIDE'`).
  - `tests/e2e/harness/mock_frames.py`: `PlateGenerator` (synthesizing valid HSRP, Bharat Series, commercial, EV, diplomatic, malformed plates, and DIN 1451 confusion variants) and `PlateCropGenerator` (synthesizing realistic image crops with OpenCV/Pillow).
  - `tests/e2e/harness/api_client.py`: Dual-mode `E2EApiClient` supporting in-process route invocation and live HTTP client calls.
  - `tests/e2e/harness/camera_sim.py`: Polymorphic feed emulator generating synthetic camera heartbeats and frame ingestion events.
- **Directory Layout**:
  ```
  tests/e2e/
  ├── __init__.py
  ├── conftest.py
  ├── run_all.py                     # Standalone CLI test runner
  ├── harness/
  │   ├── __init__.py
  │   ├── db_adapter.py              # D1 / SQLite test database harness
  │   ├── mock_frames.py             # Synthetic Indian plate & crop generator
  │   ├── api_client.py              # Opaque-box E2E HTTP client
  │   └── camera_sim.py              # Camera feed & heartbeat emulator
  ├── tier1_features/
  │   ├── __init__.py
  │   ├── test_f1_detection.py       # T1-F1-01 .. T1-F1-05
  │   ├── test_f2_ocr.py             # T1-F2-01 .. T1-F2-05
  │   ├── test_f3_grammar.py         # T1-F3-01 .. T1-F3-05
  │   ├── test_f4_normalization.py   # T1-F4-01 .. T1-F4-05
  │   ├── test_f5_camera_mgmt.py     # T1-F5-01 .. T1-F5-05
  │   ├── test_f6_cooldown.py        # T1-F6-01 .. T1-F6-05
  │   ├── test_f7_isolation.py       # T1-F7-01 .. T1-F7-05
  │   ├── test_f8_entry_gate.py      # T1-F8-01 .. T1-F8-05
  │   ├── test_f9_exit_gate.py       # T1-F9-01 .. T1-F9-05
  │   └── test_f10_operator.py       # T1-F10-01 .. T1-F10-05
  ├── tier2_boundaries/
  │   ├── __init__.py
  │   ├── test_b1_ambiguity.py       # T2-B1-01 .. T2-B1-05
  │   ├── test_b2_syntax.py          # T2-B2-01 .. T2-B2-05
  │   ├── test_b3_aspect_ratios.py   # T2-B3-01 .. T2-B3-05
  │   ├── test_b4_degraded_crops.py  # T2-B4-01 .. T2-B4-05
  │   ├── test_b5_out_of_order.py    # T2-B5-01 .. T2-B5-05
  │   ├── test_b6_burst_concurrency.py # T2-B6-01 .. T2-B6-05
  │   ├── test_b7_capacity_limits.py # T2-B7-01 .. T2-B7-05
  │   ├── test_b8_durations.py       # T2-B8-01 .. T2-B8-05
  │   ├── test_b9_camera_flapping.py # T2-B9-01 .. T2-B9-05
  │   └── test_b10_security_auth.py  # T2-B10-01 .. T2-B10-05
  ├── tier3_combinations/
  │   ├── __init__.py
  │   └── test_pairwise_workflows.py # T3-C01 .. T3-C15
  └── tier4_scenarios/
      ├── __init__.py
      └── test_real_world_workloads.py # S1 .. S5
  ```

## Real-World Application Scenarios (Tier 4)
| # | Scenario | Features Exercised | Complexity | Target Invariant |
|---|----------|--------------------|------------|------------------|
| S1 | Connaught Place Morning Rush | F1, F3, F5, F6, F8, F10 | High | 50 vehicles surge; rapid entries; cooldown debouncing; zero duplicate sessions; live occupancy exactly 50 |
| S2 | Midday Steady-State Turnover | F3, F4, F6, F8, F9 | High | 20 entries, 20 exits across multiple gates; concurrent turnover; zero drift between DB and reported occupancy |
| S3 | Evening Rush & Camera Dropout | F1, F5, F7, F8, F9, F10 | Very High | 30 exits, entry camera ethernet disconnect; camera marked OFFLINE; vehicle sessions and occupancy fully preserved |
| S4 | Full Facility Saturation Limit | F8, F9, B7 | High | Palika capacity saturation (occupancy reaches total 900); available capacity drops to 0; observation syncs to FULL |
| S5 | Operator Shift Batch Review | F4, F9, F10 | High | 10 low-confidence reads (`NEEDS_REVIEW`) and unmatched exits resolved in batch; authoritative reconciliation |

## Coverage Thresholds & Pass Criteria
- **Tier 1**: Exactly 50 tests (5 per core feature), 100% pass rate.
- **Tier 2**: Exactly 50 tests (5 per boundary category), 100% pass rate.
- **Tier 3**: Exactly 15 pairwise interaction tests, 100% pass rate.
- **Tier 4**: Exactly 5 multi-vehicle realistic day workloads, 100% pass rate.
- **Total Test Cases**: **120 automated test cases**.
- **Execution Command**: `python -m pytest tests/e2e -v` or `python tests/e2e/run_all.py` (Exit Code 0).
