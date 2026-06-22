#!/usr/bin/env python3
"""Data-path: clip manifests -> per-frame risk -> real anticipation metrics (3-arm).

Arms (the ablation that actually matters; see docs/research/anticipation-eval.md):
  - pose_only    : concealment + shelf dwell (no motion)
  - pose_2d_traj : pose_only + image-plane velocity toward the exit (NO depth/BEV)
  - pose_bev     : pose_only + perspective-weighted pseudo-BEV exit progress

PRE-REGISTERED decision rule (committed BEFORE looking at results, so we can't move the
goalposts): BEV is a real differentiator ONLY IF, at FAR <= FAR_MAX, mean lead-time of
pose_bev exceeds pose_2d_traj by >= DELTA_S seconds. Otherwise BEV is REJECTED (2D suffices).

Honesty: on SYNTHETIC (split=staged) data this proves PLUMBING ONLY — never that BEV helps.
A result is only claimable on re-annotated real/staged clips (P1).
"""
from __future__ import annotations

import argparse
import csv
import glob
import json
import math
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
CLIPS = ROOT / "eval" / "clips"

# --- PRE-REGISTERED thresholds (do not tune to results) ---
FAR_MAX = 0.30          # max acceptable false-alarm rate over negative clips
DELTA_S = 0.20          # seconds of lead-time pose_bev must add over pose_2d_traj
TARGET_RECALL = 0.80    # report TTA at this recall (TTA@R80)
ARMS = ["pose_only", "pose_2d_traj", "pose_bev"]
NEG_SCENARIOS = {"S0", "S2"}
POS_SCENARIOS = {"S1"}


def _u(v):
    n = math.hypot(v[0], v[1])
    return (0.0, 0.0) if n < 1e-9 else (v[0] / n, v[1] / n)


def _in_poly(p, poly):
    x, y = p
    inside = False
    n = len(poly)
    for i in range(n):
        x1, y1 = poly[i]
        x2, y2 = poly[(i + 1) % n]
        if (y1 > y) != (y2 > y):
            xin = x1 + (y - y1) * (x2 - x1) / (y2 - y1)
            if x < xin:
                inside = not inside
    return inside


def _center(kp):
    return ((kp["l_ankle"][0] + kp["r_ankle"][0]) / 2, (kp["l_ankle"][1] + kp["r_ankle"][1]) / 2)


def arm_scores(clip: dict, manifest: dict) -> dict:
    """Return {arm: [risk per frame]} for the primary actor."""
    tid = clip["primary_actor_track_id"]
    seq = clip["tracks"][tid]
    shelf = manifest["zones"]["shelf_zone"]
    ev = manifest["zones"]["exit_vector"]
    exit_dir = _u((ev["to"][0] - ev["from"][0], ev["to"][1] - ev["from"][1]))
    H = clip["image_size"][1]

    out = {a: [] for a in ARMS}
    prev = None
    for fr in seq:
        kp = fr["kp"]
        c = _center(kp)
        # concealment: nearest wrist-hip distance (small => hands tucked at hip/torso)
        d = min(math.dist(kp[w], kp[h]) for w in ("l_wrist", "r_wrist") for h in ("l_hip", "r_hip"))
        conceal = max(0.0, 1.0 - d / 40.0)
        dwell = 1.0 if _in_poly(c, shelf) else 0.0
        pose_only = min(1.0, 0.8 * conceal + 0.2 * dwell)
        if prev is None:
            ex2d = exbev = 0.0
        else:
            v = (c[0] - prev[0], c[1] - prev[1])
            ex2d = max(0.0, _u(v)[0] * exit_dir[0] + _u(v)[1] * exit_dir[1])
            # perspective-weighted pseudo-BEV: anisotropic vertical foreshortening correction
            sy = (c[1] / H) + 0.5
            gv = _u((v[0], v[1] / sy))
            exbev = max(0.0, gv[0] * exit_dir[0] + gv[1] * exit_dir[1])
        out["pose_only"].append(pose_only)
        out["pose_2d_traj"].append(min(1.0, pose_only + 0.6 * ex2d))
        out["pose_bev"].append(min(1.0, pose_only + 0.6 * exbev))
        prev = c
    return out


def first_alert(risk: list, w0: int, w1: int, theta: float):
    """Earliest frame in [w0, w1] with risk >= theta, else None."""
    for f in range(max(0, w0), min(len(risk) - 1, w1) + 1):
        if risk[f] >= theta:
            return f
    return None


def _ap(scored: list) -> float:
    """Average precision (area under PR) from [(score, label)]."""
    s = sorted(scored, key=lambda x: -x[0])
    P = sum(y for _, y in s)
    if P == 0:
        return 0.0
    tp = 0
    ap = 0.0
    for i, (_, y) in enumerate(s, start=1):
        if y == 1:
            tp += 1
            ap += (tp / i) / P
    return ap


def evaluate(clips: list[tuple[dict, dict]]) -> dict:
    pos = [(c, m) for c, m in clips if m["scenario_id"] in POS_SCENARIOS]
    neg = [(c, m) for c, m in clips if m["scenario_id"] in NEG_SCENARIOS]
    scores = {id(c): arm_scores(c, m) for c, m in clips}

    res = {"n_pos": len(pos), "n_neg": len(neg), "arms": {}}
    thetas = [round(0.05 * i, 2) for i in range(1, 21)]
    for arm in ARMS:
        # AUC-PR over all clips (label=1 for S1), score = max risk in clip
        ap = _ap([(max(scores[id(c)][arm]), 1 if m["scenario_id"] in POS_SCENARIOS else 0)
                  for c, m in clips])
        best = None  # (theta, recall, far, mean_tta) at highest theta with recall>=TARGET_RECALL
        for th in thetas:
            ttas = []
            for c, m in pos:
                w = m["valid_prediction_window"]
                tau = m["anchors"]["event_complete_frame"]
                t = first_alert(scores[id(c)][arm], w["start_frame"], w["end_frame"], th)
                if t is not None:
                    ttas.append((tau - t) / m["fps"])
            recall = len(ttas) / len(pos) if pos else 0.0
            fired_neg = sum(1 for c, _ in neg if max(scores[id(c)][arm]) >= th)
            far = fired_neg / len(neg) if neg else 0.0
            if recall >= TARGET_RECALL:
                mean_tta = sum(ttas) / len(ttas) if ttas else 0.0
                best = (th, recall, far, mean_tta)  # keep updating -> ends at highest such theta
        res["arms"][arm] = {"auc_pr": ap, "tta_at_recall": best}
    return res


def decide(res: dict) -> dict:
    """Pre-registered: accept BEV iff at FAR<=FAR_MAX it adds >=DELTA_S lead-time over 2D."""
    b = res["arms"]["pose_bev"]["tta_at_recall"]
    t2 = res["arms"]["pose_2d_traj"]["tta_at_recall"]
    if not b or not t2:
        return {"verdict": "inconclusive", "reason": f"recall<{TARGET_RECALL} for an arm at all thresholds"}
    _, _, far_b, tta_b = b
    _, _, _, tta_2 = t2
    gain = tta_b - tta_2
    ok = (far_b <= FAR_MAX) and (gain >= DELTA_S)
    return {"verdict": "BEV_accepted" if ok else "BEV_rejected",
            "reason": f"FAR(bev)={far_b:.2f} (<= {FAR_MAX}? {far_b <= FAR_MAX}); "
                      f"lead-time gain vs 2D = {gain:+.2f}s (>= {DELTA_S}? {gain >= DELTA_S})"}


def load_clips(clips_dir: Path) -> list[tuple[dict, dict]]:
    out = []
    for cp in sorted(glob.glob(str(clips_dir / "*.clip.json"))):
        clip = json.loads(Path(cp).read_text())
        man = yaml.safe_load(Path(cp.replace(".clip.json", ".manifest.yaml")).read_text())
        out.append((clip, man))
    return out


def to_rows(res: dict, dec: dict, data_kind: str) -> list[dict]:
    rows = []
    for arm in ARMS:
        a = res["arms"][arm]
        rows.append({"data_kind": data_kind, "arm": arm, "metric": "auc_pr",
                     "value": f"{a['auc_pr']:.4f}", "threshold": "NA", "far": "NA",
                     "recall": "NA", "notes": ""})
        if a["tta_at_recall"]:
            th, rc, far, tta = a["tta_at_recall"]
            rows.append({"data_kind": data_kind, "arm": arm, "metric": "tta_at_r80",
                         "value": f"{tta:.4f}", "threshold": f"{th:.2f}", "far": f"{far:.2f}",
                         "recall": f"{rc:.2f}", "notes": "seconds"})
        else:
            rows.append({"data_kind": data_kind, "arm": arm, "metric": "tta_at_r80",
                         "value": "NA", "threshold": "NA", "far": "NA", "recall": "NA",
                         "notes": f"recall<{TARGET_RECALL}"})
    rows.append({"data_kind": data_kind, "arm": "decision", "metric": "bev_decision",
                 "value": dec["verdict"], "threshold": "NA", "far": "NA", "recall": "NA",
                 "notes": dec["reason"]})
    return rows


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="3-arm anticipation eval (data-path)")
    p.add_argument("--clips-dir", default=str(CLIPS))
    p.add_argument("--out", default=str(ROOT / "eval" / "out" / "anticipation_result.csv"))
    a = p.parse_args(argv)
    clips = load_clips(Path(a.clips_dir))
    if not clips:
        print(f"no clips in {a.clips_dir}", flush=True)
        return 2
    kinds = {m["split"] for _, m in clips}
    data_kind = "synthetic" if all(c["clip_id"].startswith("syn_") for c, _ in clips) else "/".join(sorted(kinds))
    res = evaluate(clips)
    dec = decide(res)
    rows = to_rows(res, dec, data_kind)
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    cols = ["data_kind", "arm", "metric", "value", "threshold", "far", "recall", "notes"]
    with out.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols, lineterminator="\n")
        w.writeheader()
        w.writerows(rows)

    banner = "PLUMBING ONLY (synthetic) — NOT a result about +BEV" if data_kind == "synthetic" \
        else f"data_kind={data_kind}"
    print(f"[{banner}]  n_pos={res['n_pos']} n_neg={res['n_neg']}")
    for arm in ARMS:
        a_ = res["arms"][arm]
        t = a_["tta_at_recall"]
        ts = f"TTA@R{int(TARGET_RECALL*100)}={t[3]:.2f}s @θ={t[0]:.2f} FAR={t[2]:.2f}" if t else "TTA@R80=NA"
        print(f"  {arm:14} AUC-PR={a_['auc_pr']:.3f}  {ts}")
    print(f"  DECISION: {dec['verdict']}  ({dec['reason']})")
    print(f"  wrote -> {a.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
