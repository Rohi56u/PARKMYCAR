"""ParkMyCar Tier 1 E2E Feature Coverage Test Suite.

Contains 50 test cases covering features F1 through F10:
- test_f1_detection.py: T1-F1-01 .. T1-F1-05 (Plate Bounding Box Detection)
- test_f2_ocr.py: T1-F2-01 .. T1-F2-05 (CLAHE Preprocessing & OCR Extraction)
- test_f3_grammar.py: T1-F3-01 .. T1-F3-05 (Indian Registration Grammar Validation)
- test_f4_normalization.py: T1-F4-01 .. T1-F4-05 (Positional Normalization & Gating)
- test_f5_camera_mgmt.py: T1-F5-01 .. T1-F5-05 (Polymorphic Camera Feeds & Heartbeat)
- test_f6_cooldown.py: T1-F6-01 .. T1-F6-05 (Gate Cooldown Debouncing)
- test_f7_isolation.py: T1-F7-01 .. T1-F7-05 (Camera Disconnection Isolation)
- test_f8_entry_gate.py: T1-F8-01 .. T1-F8-05 (Vehicle Entry Session & Occupancy Inc)
- test_f9_exit_gate.py: T1-F9-01 .. T1-F9-05 (Vehicle Exit Matching & Occupancy Dec)
- test_f10_operator.py: T1-F10-01 .. T1-F10-05 (Review Queue & Operator Resolution)
"""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure repo root and tests/e2e root are in sys.path
_repo_root = Path(__file__).resolve().parent.parent.parent
if str(_repo_root) not in sys.path:
    sys.path.insert(0, str(_repo_root))

_e2e_root = Path(__file__).resolve().parent.parent
if str(_e2e_root) not in sys.path:
    sys.path.insert(0, str(_e2e_root))
