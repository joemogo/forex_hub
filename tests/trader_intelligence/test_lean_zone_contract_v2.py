"""Registered entry for the synthetic-only, explicitly directional v2 zone contract."""
import os, sys
SYNTHETIC = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "lean_synthetic"))
if SYNTHETIC not in sys.path: sys.path.insert(0, SYNTHETIC)
from zone_contract_v2.test_roundtrip import TestZoneContractV2  # noqa: F401,E402
