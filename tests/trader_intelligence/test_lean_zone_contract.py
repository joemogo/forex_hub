"""Registered runner entry for the isolated synthetic MOGO-to-LEAN zone contract."""
import os
import sys

LEAN_SYNTHETIC = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "lean_synthetic"))
if LEAN_SYNTHETIC not in sys.path:
    sys.path.insert(0, LEAN_SYNTHETIC)

# The implementation remains beside the isolated contract; this import deliberately exposes its
# TestCase to the repository's trader-intelligence discovery and count guards.
from zone_contract.test_roundtrip import TestSyntheticEmitterAndBoundary  # noqa: F401,E402
