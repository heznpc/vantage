"""Hard gates for the 3-arm anticipation data-path: pure-fn correctness, reproducibility, schema."""
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


ant = _load("eval/anticipation.py", "vantage_ant")
synth = _load("eval/synth.py", "vantage_synth")
validator = _load("eval/validate_csv.py", "vantage_validate")


class TestAnticipation(unittest.TestCase):
    def test_first_alert_and_tta_known(self):
        risk = [0.0] * 40 + [0.95] * 40
        t = ant.first_alert(risk, 0, 60, 0.9)
        self.assertEqual(t, 40)
        tau, fps = 70, 15
        self.assertAlmostEqual((tau - t) / fps, 2.0, places=6)

    def test_first_alert_respects_window(self):
        risk = [0.99] * 80
        self.assertEqual(ant.first_alert(risk, 30, 60, 0.5), 30)  # not before window start

    def test_ap_perfect_and_inverted(self):
        self.assertAlmostEqual(ant._ap([(0.9, 1), (0.8, 1), (0.1, 0)]), 1.0, places=6)
        self.assertLess(ant._ap([(0.9, 0), (0.1, 1)]), 1.0)

    def test_decision_rule_rejects_when_no_gain(self):
        res = {"arms": {
            "pose_bev": {"operating_point": (0.5, 1.0, 0.1, 2.0)},
            "pose_2d_traj": {"operating_point": (0.5, 1.0, 0.1, 2.0)},
        }}
        self.assertEqual(ant.decide(res)["verdict"], "BEV_rejected")  # gain 0 < DELTA_S

    def test_decision_rule_accepts_with_gain_under_far(self):
        res = {"arms": {
            "pose_bev": {"operating_point": (0.5, 1.0, 0.10, 3.0)},
            "pose_2d_traj": {"operating_point": (0.5, 1.0, 0.10, 1.0)},
        }}
        self.assertEqual(ant.decide(res)["verdict"], "BEV_accepted")  # +2.0s, FAR 0.10<=0.30

    def test_decision_inconclusive_when_arm_infeasible(self):
        res = {"arms": {
            "pose_bev": {"operating_point": None},  # no feasible FAR-constrained point
            "pose_2d_traj": {"operating_point": (0.5, 1.0, 0.10, 1.0)},
        }}
        self.assertEqual(ant.decide(res)["verdict"], "inconclusive")

    def test_fixed_thresholds_mode(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            synth.generate(Path(d))
            clips = ant.load_clips(Path(d))
            th = {"pose_only": 0.9, "pose_2d_traj": 0.95, "pose_bev": 0.95}
            r1 = ant.evaluate(clips, th)
            self.assertEqual(r1, ant.evaluate(clips, th))           # deterministic
            self.assertEqual(r1["threshold_source"], "fixed-file")
            for arm in ant.ARMS:
                self.assertIsNotNone(r1["arms"][arm]["operating_point"])  # fixed theta always yields a point

    def test_pipeline_reproducible_and_schema_valid(self):
        with tempfile.TemporaryDirectory() as d:
            clips_dir = Path(d) / "clips"
            synth.generate(clips_dir)
            clips = ant.load_clips(clips_dir)
            self.assertEqual(len(clips), 7)
            r1 = ant.evaluate(clips)
            r2 = ant.evaluate(ant.load_clips(clips_dir))
            self.assertEqual(r1, r2)  # deterministic
            rows = ant.to_rows(r1, ant.decide(r1), "synthetic")
            out = Path(d) / "anticipation_result.csv"
            import csv
            with out.open("w", newline="") as f:
                w = csv.DictWriter(f, fieldnames=["data_kind", "arm", "metric", "value",
                                                  "threshold", "far", "recall", "notes"],
                                   lineterminator="\n")
                w.writeheader()
                w.writerows(rows)
            errs = validator.validate(out, ROOT / "eval" / "schema" / "anticipation_result.schema.json")
            self.assertEqual(errs, [], f"schema errors: {errs}")


if __name__ == "__main__":
    unittest.main()
