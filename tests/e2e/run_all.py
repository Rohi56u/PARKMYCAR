"""Standalone E2E Test Suite Runner for ParkMyCar.

Executes all test cases under tests/e2e/ using pytest, formats the execution output,
and returns exit code 0 on complete pass or 1 on failure.

Usage:
    python tests/e2e/run_all.py
    python tests/e2e/run_all.py -v
"""

from __future__ import annotations

import sys
import time
from pathlib import Path
import pytest


def main() -> int:
    """Execute pytest test runner against tests/e2e."""
    project_root = Path(__file__).resolve().parent.parent.parent
    e2e_dir = Path(__file__).resolve().parent

    print("=" * 80)
    print("PARKMYCAR ANPR & LIVE OCCUPANCY - E2E TEST SUITE RUNNER")
    print("=" * 80)
    print(f"Project Root: {project_root}")
    print(f"E2E Test Dir: {e2e_dir}")
    print(f"Python Ver:   {sys.version.split()[0]}")
    print("=" * 80)

    # Prepare pytest args: forward extra CLI arguments if provided, else run harness sanity
    extra_args = sys.argv[1:]
    pytest_args = [
        str(e2e_dir),
        "-v",
        "-s",
        "--tb=short",
    ]
    if extra_args:
        pytest_args.extend(extra_args)

    start_time = time.perf_counter()
    exit_code = pytest.main(pytest_args)
    duration = time.perf_counter() - start_time

    print("=" * 80)
    if exit_code == 0:
        print(f"STATUS: SUCCESS (100% Passed) in {duration:.2f}s")
    else:
        print(f"STATUS: FAILURE (Exit Code: {exit_code}) in {duration:.2f}s")
    print("=" * 80)

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
