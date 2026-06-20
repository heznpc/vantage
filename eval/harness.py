#!/usr/bin/env python3
"""Deterministic replay harness — the M1 ablation skeleton.

Replays a fixed clip set through a STUB pipeline under a flag config
(backbone / bev_enabled / forecast / calibrated) and emits `ablation_result`
rows (see eval/schema/ablation_result.schema.json).

WHAT IS REAL HERE: the harness contract — determinism (same seed+config =>
identical output), the metric set, the CSV schema, and the calibration rule
(no numeric ETA when calibrated=false). temporal_auc is computed for real from
the synthetic per-track scores.

WHAT IS STUB: the per-track scores come from a seeded synthetic generator, not
from RTMO/ByteTrack/ST-GCN+TCN or a BEV forecast. M2 replaces `_score_tracks`
with the real perception+spatial pipeline; the harness/CSV/gates stay put.

No wall-clock, no unseeded RNG, no builtin hash() -> reproducible by construction.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import random
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_FIXTURE = ROOT / "eval" / "fixtures" / "synthetic_tracks.json"
EPOCH = "1970-01-01T00:00:00Z"  # deterministic default; real runs pass --timestamp
COLUMNS = ["run_id", "timestamp", "clip_set", "backbone", "bev_enabled", "forecast",
           "calibrated", "metric", "value", "ci_low", "ci_high", "notes"]

# Stable per-backbone perception characteristics (stub priors; replaced by real measurement in M2).
_BACKBONE = {
    "rtmo":      {"kp_stability": 0.91, "id_switch": 0.06},
    "rtmpose-m": {"kp_stability": 0.93, "id_switch": 0.05},
    "rtmpose-s": {"kp_stability": 0.88, "id_switch": 0.08},
    "yolo26":    {"kp_stability": 0.92, "id_switch": 0.06},  # quarantined reference only
}


def _seed_int(config: dict, seed: int) -> int:
    blob = json.dumps(config, sort_keys=True, separators=(",", ":")) + f"|{seed}"
    return int(hashlib.sha256(blob.encode()).hexdigest()[:16], 16)


def _run_id(config: dict, seed: int) -> str:
    blob = json.dumps(config, sort_keys=True, separators=(",", ":")) + f"|{seed}"
    return hashlib.sha256(blob.encode()).hexdigest()[:12]


def _score_tracks(tracks: list[dict], config: dict, seed: int) -> list[tuple[float, int]]:
    """STUB: deterministic per-track (anomaly_score, label). Replace with real pipeline in M2."""
    rng = random.Random(_seed_int(config, seed))
    base = _BACKBONE[config["backbone"]]["kp_stability"]
    out = []
    for tr in tracks:
        r = random.Random(_seed_int(config, seed) ^ tr["feature_seed"])
        is_theft = 1 if tr["label"] == "theft" else 0
        # base separability scaled by backbone keypoint quality
        # overlapping distributions on purpose: pose-only is imperfect, so +BEV can show a gap
        score = r.uniform(0.0, 0.55) + (0.22 * is_theft) * base
        if config["bev_enabled"]:
            # BEV/forecast nudges theft tracks up, normals slightly down (synthetic separability gain)
            score += 0.15 * is_theft - 0.04 * (1 - is_theft)
        score += rng.uniform(-0.03, 0.03)
        out.append((max(0.0, min(1.0, score)), is_theft))
    return out


def _auc(scored: list[tuple[float, int]]) -> float:
    pos = [s for s, y in scored if y == 1]
    neg = [s for s, y in scored if y == 0]
    if not pos or not neg:
        return 0.5
    wins = sum((p > n) + 0.5 * (p == n) for p in pos for n in neg)
    return wins / (len(pos) * len(neg))


def _fmt(v: float) -> str:
    return f"{v:.6f}"


def run(config: dict, fixture_path: Path = DEFAULT_FIXTURE, seed: int = 0,
        timestamp: str = EPOCH) -> list[dict]:
    fx = json.loads(Path(fixture_path).read_text())
    tracks = fx["tracks"]
    scored = _score_tracks(tracks, config, seed)
    prior = _BACKBONE[config["backbone"]]
    rid, clip = _run_id(config, seed), fx["clip_set"]

    auc = _auc(scored)
    eer = max(0.0, min(1.0, 1.0 - auc))  # crude stub relation
    far = (0.18 if not config["bev_enabled"] else 0.11)  # lower FAR with BEV (synthetic)

    def row(metric, value, ci_low="NA", ci_high="NA", notes=""):
        return {
            "run_id": rid, "timestamp": timestamp, "clip_set": clip,
            "backbone": config["backbone"], "bev_enabled": str(config["bev_enabled"]).lower(),
            "forecast": config["forecast"], "calibrated": str(config["calibrated"]).lower(),
            "metric": metric, "value": value, "ci_low": ci_low, "ci_high": ci_high, "notes": notes,
        }

    rows = [
        row("keypoint_stability", _fmt(prior["kp_stability"]), _fmt(prior["kp_stability"] - 0.02), _fmt(prior["kp_stability"] + 0.02)),
        row("id_switch_rate", _fmt(prior["id_switch"]), _fmt(prior["id_switch"] - 0.01), _fmt(prior["id_switch"] + 0.01)),
        row("temporal_auc", _fmt(auc), _fmt(max(0.0, auc - 0.05)), _fmt(min(1.0, auc + 0.05)),
            "STUB scores; real pipeline in M2"),
        row("temporal_eer", _fmt(eer), _fmt(max(0.0, eer - 0.05)), _fmt(min(1.0, eer + 0.05))),
    ]
    # Calibration rule: no numeric ETA/FAR-at-lead-time unless calibrated (design invariant).
    if config["calibrated"]:
        rows.append(row("far_at_leadtime", _fmt(far), _fmt(max(0.0, far - 0.04)), _fmt(far + 0.04),
                        "lead-time anchor=event_complete_frame"))
        rows.append(row("lead_time_s", _fmt(3.2 if config["bev_enabled"] else 1.1),
                        _fmt(2.0), _fmt(4.5), "calibrated"))
    else:
        rows.append(row("far_at_leadtime", "NA", "NA", "NA", "uncalibrated: numeric ETA suppressed"))
        rows.append(row("lead_time_s", "NA", "NA", "NA", "uncalibrated: numeric ETA suppressed"))
    return rows


def write_csv(rows: list[dict], out_path: Path) -> None:
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS, lineterminator="\n")
        w.writeheader()
        w.writerows(rows)


def _parse_args(argv=None):
    p = argparse.ArgumentParser(description="Vantage deterministic replay harness")
    p.add_argument("--backbone", default="rtmo", choices=list(_BACKBONE))
    p.add_argument("--bev", dest="bev", action="store_true", default=False)
    p.add_argument("--no-bev", dest="bev", action="store_false")
    p.add_argument("--forecast", default="none", choices=["none", "kalman", "kalman+gru"])
    p.add_argument("--calibrated", dest="calibrated", action="store_true", default=False)
    p.add_argument("--no-calibrated", dest="calibrated", action="store_false")
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--timestamp", default=EPOCH)
    p.add_argument("--fixture", default=str(DEFAULT_FIXTURE))
    p.add_argument("--out", default=str(ROOT / "eval" / "out" / "ablation_result.csv"))
    return p.parse_args(argv)


def main(argv=None) -> int:
    a = _parse_args(argv)
    config = {"backbone": a.backbone, "bev_enabled": a.bev, "forecast": a.forecast, "calibrated": a.calibrated}
    rows = run(config, Path(a.fixture), a.seed, a.timestamp)
    write_csv(rows, Path(a.out))
    print(f"wrote {len(rows)} rows -> {a.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
