#!/usr/bin/env python3
"""Run the whole test suite:  python tests/run_tests.py  (thin wrapper around pytest)."""

import sys
from pathlib import Path

import pytest

if __name__ == "__main__":
    root = Path(__file__).resolve().parent.parent
    sys.exit(pytest.main([str(root / "tests"), "-q", *sys.argv[1:]]))
