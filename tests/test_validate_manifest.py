"""Hard gate: clip-manifest semantic validator accepts valid manifests, rejects mislabeled ones."""
import importlib.util
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _load(rel: str, name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / rel)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


vm = _load("eval/validate_manifest.py", "vantage_vm")
synth = _load("eval/synth.py", "vantage_synth2")


def _s1(**over):
    m = {
        "clip_id": "x", "scenario_id": "S1",
        "tracks": {"primary_actor_track_id": "t1"},
        "zones": {"exit_vector": {"from": [0, 0], "to": [10, 1]}},
        "anchors": {"approach_start_frame": 0, "item_interaction_start_frame": 10,
                    "concealment_start_frame": 20, "event_complete_frame": 40},
        "valid_prediction_window": {"start_frame": 0, "end_frame": 39},
    }
    m.update(over)
    return m


class TestValidateManifest(unittest.TestCase):
    def test_valid_s1_passes(self):
        errs, _ = vm.validate_doc(_s1())
        self.assertEqual(errs, [])

    def test_s1_without_tau_fails(self):
        m = _s1(anchors={"approach_start_frame": 0, "item_interaction_start_frame": 10,
                         "concealment_start_frame": 20, "event_complete_frame": None})
        self.assertTrue(vm.validate_doc(m)[0])

    def test_window_end_must_precede_tau(self):
        self.assertTrue(vm.validate_doc(_s1(valid_prediction_window={"start_frame": 0, "end_frame": 40}))[0])

    def test_s0_with_tau_fails(self):
        m = _s1(scenario_id="S0")  # S0 but carries a tau + window -> invalid
        self.assertTrue(vm.validate_doc(m)[0])

    def test_degenerate_exit_vector_fails(self):
        self.assertTrue(vm.validate_doc(_s1(zones={"exit_vector": {"from": [5, 5], "to": [5, 5]}}))[0])

    def test_calibrated_true_requires_calibration_block(self):
        errs = vm.validate_doc(_s1(calibrated=True))[0]
        self.assertTrue(any("calibration" in e for e in errs))

    def test_calibrated_true_with_block_passes(self):
        m = _s1(calibrated=True,
                calibration={"homography": [1, 0, 0, 0, 1, 0, 0, 0, 1], "reprojection_rms": 2.4, "n_points": 4})
        self.assertEqual(vm.validate_doc(m)[0], [])

    def test_generated_clips_all_valid(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            synth.generate(Path(d))
            errs, _ = vm.validate_path(Path(d))
            self.assertEqual(errs, [], f"synthetic manifests should be valid: {errs}")

    def test_schema_fold_catches_bad_homography(self):
        import tempfile
        import yaml as _yaml
        if vm.jsonschema is None:
            self.skipTest("jsonschema not installed; schema fold unavailable")
        with tempfile.TemporaryDirectory() as d:
            synth.generate(Path(d))
            mp = sorted(Path(d).glob("*.manifest.yaml"))[0]
            doc = _yaml.safe_load(mp.read_text())
            doc["calibrated"] = True
            doc["calibration"] = {"homography": [1, 2, 3], "reprojection_rms": 1.0, "n_points": 4}  # len 3 != 9
            mp.write_text(_yaml.safe_dump(doc))
            errs, _ = vm.validate_path(Path(d))
            self.assertTrue(any("schema" in e or "homography" in e for e in errs), errs)

    def test_separation_angle(self):
        m = {"zones": {"exit_vector": {"from": [0, 0], "to": [10, 0]},
                       "checkout_vector": {"from": [0, 0], "to": [-10, 0]}}}
        self.assertAlmostEqual(vm.separation_angle_deg(m), 180.0, places=3)
        self.assertIsNone(vm.separation_angle_deg({"zones": {"exit_vector": {"from": [0, 0], "to": [1, 0]}}}))


if __name__ == "__main__":
    unittest.main()
