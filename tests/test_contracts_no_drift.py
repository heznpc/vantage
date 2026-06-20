"""Hard gate (H2): committed contracts/generated/ must equal a fresh regen from the SSOT specs."""
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


gen = _load("scripts/gen_contracts.py", "vantage_gen")


class TestContractsNoDrift(unittest.TestCase):
    def test_generated_matches_committed(self):
        committed = ROOT / "contracts" / "generated"
        with tempfile.TemporaryDirectory() as d:
            fresh = Path(d)
            gen.generate(fresh)
            for fname in ("models.py", "manifest.json"):
                self.assertEqual(
                    (committed / fname).read_text(),
                    (fresh / fname).read_text(),
                    f"{fname} drifted from SSOT — run `python scripts/gen_contracts.py` and commit",
                )


if __name__ == "__main__":
    unittest.main()
