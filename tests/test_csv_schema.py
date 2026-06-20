"""Hard gate: harness output conforms to ablation_result schema; bad rows are rejected."""
import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _load(rel: str, name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / rel)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


harness = _load("eval/harness.py", "vantage_harness")
validator = _load("eval/validate_csv.py", "vantage_validate")


class TestCsvSchema(unittest.TestCase):
    def test_harness_output_valid(self):
        cfg = {"backbone": "rtmpose-m", "bev_enabled": True, "forecast": "kalman+gru", "calibrated": True}
        rows = harness.run(cfg, seed=3)
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / "r.csv"
            harness.write_csv(rows, out)
            errs = validator.validate(out)
            self.assertEqual(errs, [], f"unexpected schema errors: {errs}")

    def test_bad_enum_rejected(self):
        cfg = {"backbone": "rtmo", "bev_enabled": False, "forecast": "none", "calibrated": False}
        rows = harness.run(cfg, seed=3)
        rows[0]["backbone"] = "not-a-backbone"  # corrupt one enum value
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / "bad.csv"
            harness.write_csv(rows, out)
            errs = validator.validate(out)
            self.assertTrue(errs, "validator should reject an invalid enum value")


if __name__ == "__main__":
    unittest.main()
