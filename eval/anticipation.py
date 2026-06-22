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
    m_tid = manifest["tracks"]["primary_actor_track_id"]
    if m_tid != tid:
        raise ValueError(f"{clip.get('clip_id')}: clip track {tid!r} != manifest track {m_tid!r}")
    if tid not in clip["tracks"]:
        raise ValueError(f"{clip.get('clip_id')}: track {tid!r} missing from clip tracks")
    seq = clip["tracks"][tid]
    shelf = manifest["zones"]["shelf_zone"]
    ev = manifest["zones"]["exit_vector"]
    exit_dir = _u((ev["to"][0] - ev["from"][0], ev["to"][1] - ev["from"][1]))
    H = clip["image_size"][1]

    out = {a: [] for a in ARMS}
    prev = None
    for fr in seq:
        if not fr.get("present", True):
            # occluded/missing frame: emit zero risk, reset velocity (no anticipation through a gap)
            for a in ARMS:
                out[a].append(0.0)
            prev = None
            continue
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


def _point_at(arm: str, th: float, pos: list, neg: list, scores: dict):
    """(recall, far, mean_tta) for one arm at one threshold."""
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
    mean_tta = sum(ttas) / len(ttas) if ttas else 0.0
    return recall, far, mean_tta


def evaluate(clips: list[tuple[dict, dict]], thresholds: "dict | None" = None) -> dict:
    pos = [(c, m) for c, m in clips if m["scenario_id"] in POS_SCENARIOS]
    neg = [(c, m) for c, m in clips if m["scenario_id"] in NEG_SCENARIOS]
    scores = {id(c): arm_scores(c, m) for c, m in clips}

    res = {"n_pos": len(pos), "n_neg": len(neg), "arms": {},
           "threshold_source": "fixed-file" if thresholds else "eval-sweep"}
    thetas = [round(0.05 * i, 2) for i in range(1, 21)]
    for arm in ARMS:
        ap = _ap([(max(scores[id(c)][arm]), 1 if m["scenario_id"] in POS_SCENARIOS else 0)
                  for c, m in clips])
        raw = None
        if thresholds is not None:  # fixed theta chosen on a DEV split (P1 protocol; no eval-set tuning)
            th = float(thresholds[arm])
            recall, far, mean_tta = _point_at(arm, th, pos, neg, scores)
            raw = (th, recall, far, mean_tta)
            # fixed theta still must clear the SAME FAR/recall budget as the sweep, else it is NOT
            # a valid operating point (an arm at FAR=1.0 must not count as feasible).
            op = raw if (recall >= TARGET_RECALL and far <= FAR_MAX) else None
        else:  # dev sweep over the eval set -> plumbing only, never a P1 result
            op = None
            for th in thetas:
                recall, far, mean_tta = _point_at(arm, th, pos, neg, scores)
                if recall >= TARGET_RECALL and far <= FAR_MAX:  # same FAR budget for every arm
                    if op is None or mean_tta > op[3]:
                        op = (th, recall, far, mean_tta)
        res["arms"][arm] = {"auc_pr": ap, "operating_point": op, "raw_point": raw}
    return res


def decide(res: dict) -> dict:
    """Pre-registered: BEV wins iff, at the SAME FAR budget (far<=FAR_MAX, recall>=R) as the 2D
    arm, it adds >= DELTA_S lead-time. Both arms must have a feasible operating point."""
    b = res["arms"]["pose_bev"]["operating_point"]
    t2 = res["arms"]["pose_2d_traj"]["operating_point"]
    if not b or not t2:
        which = "pose_bev" if not b else "pose_2d_traj"
        return {"verdict": "inconclusive",
                "reason": f"no feasible operating point (recall>={TARGET_RECALL} & FAR<={FAR_MAX}) for {which}"}
    gain = b[3] - t2[3]
    return {"verdict": "BEV_accepted" if gain >= DELTA_S else "BEV_rejected",
            "reason": f"both arms @ FAR<={FAR_MAX},recall>={TARGET_RECALL}; "
                      f"lead-time bev-2d = {gain:+.2f}s (>= {DELTA_S}? {gain >= DELTA_S})"}


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
        if a["operating_point"]:
            th, rc, far, tta = a["operating_point"]
            rows.append({"data_kind": data_kind, "arm": arm, "metric": "tta_at_r80",
                         "value": f"{tta:.4f}", "threshold": f"{th:.2f}", "far": f"{far:.2f}",
                         "recall": f"{rc:.2f}", "notes": "seconds @ FAR-constrained op point"})
        else:
            raw = a.get("raw_point")
            if raw:  # fixed theta that failed the budget -> show WHY (far/recall), value stays NA
                th, rc, far, tta = raw
                rows.append({"data_kind": data_kind, "arm": arm, "metric": "tta_at_r80",
                             "value": "NA", "threshold": f"{th:.2f}", "far": f"{far:.2f}",
                             "recall": f"{rc:.2f}",
                             "notes": f"infeasible @ fixed theta: needs recall>={TARGET_RECALL} & FAR<={FAR_MAX}"})
            else:
                rows.append({"data_kind": data_kind, "arm": arm, "metric": "tta_at_r80",
                             "value": "NA", "threshold": "NA", "far": "NA", "recall": "NA",
                             "notes": f"no feasible op point (recall>={TARGET_RECALL} & FAR<={FAR_MAX})"})
    rows.append({"data_kind": data_kind, "arm": "decision", "metric": "bev_decision",
                 "value": dec["verdict"], "threshold": "NA", "far": "NA", "recall": "NA",
                 "notes": dec["reason"]})
    return rows


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="3-arm anticipation eval (data-path)")
    p.add_argument("--clips-dir", default=str(CLIPS))
    p.add_argument("--out", default=str(ROOT / "eval" / "out" / "anticipation_result.csv"))
    p.add_argument("--thresholds", default=None,
                   help="YAML of per-arm fixed theta (P1: dev-selected). Omit -> dev-sweep on the eval set (plumbing only).")
    a = p.parse_args(argv)
    clips = load_clips(Path(a.clips_dir))
    if not clips:
        print(f"no clips in {a.clips_dir}", flush=True)
        return 2
    thresholds = yaml.safe_load(Path(a.thresholds).read_text()) if a.thresholds else None
    data_kind = "/".join(sorted({m["split"] for _, m in clips}))  # provenance from manifest, not filename
    res = evaluate(clips, thresholds)
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
    print(f"[{banner}]  n_pos={res['n_pos']} n_neg={res['n_neg']}  thresholds={res['threshold_source']}")
    for arm in ARMS:
        a_ = res["arms"][arm]
        t = a_["operating_point"]
        ts = f"TTA@R{int(TARGET_RECALL*100)}={t[3]:.2f}s @θ={t[0]:.2f} FAR={t[2]:.2f}" if t else "op-point=NA (FAR/recall infeasible)"
        print(f"  {arm:14} AUC-PR={a_['auc_pr']:.3f}  {ts}")
    print(f"  DECISION: {dec['verdict']}  ({dec['reason']})")
    print(f"  wrote -> {a.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
