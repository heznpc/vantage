"""Hard gate: same config+seed => identical harness output; different config => differs.

Runnable by both `pytest` and `python -m unittest`.
"""
import importlib.util
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _load(rel: str, name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / rel)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod  # register before exec (dataclass annotation resolution)
    spec.loader.exec_module(mod)
    return mod


harness = _load("eval/harness.py", "vantage_harness")


class TestReproducibility(unittest.TestCase):
    CFG = {"backbone": "rtmo", "bev_enabled": True, "forecast": "kalman", "calibrated": True}

    def test_same_seed_identical(self):
        a = harness.run(self.CFG, seed=7, timestamp="2026-01-01T00:00:00Z")
        b = harness.run(self.CFG, seed=7, timestamp="2026-01-01T00:00:00Z")
        self.assertEqual(a, b)

    def test_config_changes_output(self):
        base = {"backbone": "rtmo", "bev_enabled": False, "forecast": "none", "calibrated": False}
        bev = {"backbone": "rtmo", "bev_enabled": True, "forecast": "none", "calibrated": True}
        self.assertNotEqual(harness.run(base, seed=7), harness.run(bev, seed=7))

    def test_uncalibrated_suppresses_eta(self):
        cfg = {"backbone": "rtmo", "bev_enabled": True, "forecast": "none", "calibrated": False}
        rows = {r["metric"]: r for r in harness.run(cfg, seed=1)}
        self.assertEqual(rows["lead_time_s"]["value"], "NA")
        self.assertIn("suppressed", rows["lead_time_s"]["notes"])


if __name__ == "__main__":
    unittest.main()
