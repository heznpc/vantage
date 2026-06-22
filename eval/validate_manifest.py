#!/usr/bin/env python3
"""Semantic validator for clip manifests (beyond JSON-schema shape).

JSON schema (clip_manifest.schema.json) checks types; this checks MEANING that a
mislabeled manifest would otherwise sneak past and silently corrupt anticipation
metrics in P1:
  - S1 (theft) must have the full anchor chain, ordered, with a non-null tau.
  - S0/S2 (no completed theft) must have tau null AND a null valid window.
  - when tau is present: approach <= interaction <= concealment < tau, and
    valid_prediction_window.start <= end < tau.
  - exit_vector must be non-degenerate; primary_actor_track_id non-empty.
  - S3/S4/S5 are not handled by the P0 pipeline -> WARN (non-fatal).
stdlib + PyYAML only.
"""
from __future__ import annotations

import glob
import json
import math
import sys
from pathlib import Path

import yaml

try:
    import jsonschema  # optional: folds JSON-schema (shape) validation into this one command
except ModuleNotFoundError:
    jsonschema = None

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "eval" / "schema" / "clip_manifest.schema.json"
NEG = {"S0", "S2"}
NOT_IN_P0 = {"S3", "S4", "S5"}
CHAIN = ["approach_start_frame", "item_interaction_start_frame", "concealment_start_frame", "event_complete_frame"]


def validate_doc(m: dict) -> tuple[list[str], list[str]]:
    errs: list[str] = []
    warns: list[str] = []
    cid = m.get("clip_id", "?")
    sid = m.get("scenario_id")
    anchors = m.get("anchors", {})
    tau = anchors.get("event_complete_frame")
    w = m.get("valid_prediction_window", {})

    if not (m.get("tracks", {}).get("primary_actor_track_id") or "").strip():
        errs.append(f"{cid}: tracks.primary_actor_track_id is empty")
    ev = m.get("zones", {}).get("exit_vector", {})
    if ev.get("from") == ev.get("to"):
        errs.append(f"{cid}: zones.exit_vector is degenerate (from == to)")

    cal = m.get("calibration")
    if m.get("calibrated") is True:
        if not cal:
            errs.append(f"{cid}: calibrated=true requires a 'calibration' block (homography + reprojection_rms + n_points)")
        elif not isinstance(cal.get("reprojection_rms"), (int, float)):
            errs.append(f"{cid}: calibration.reprojection_rms must be a number")
    elif m.get("calibrated") is False and cal:
        warns.append(f"{cid}: calibrated=false but a 'calibration' block is present (it will be ignored)")

    if sid in NOT_IN_P0:
        warns.append(f"{cid}: scenario {sid} is not handled by the P0 pipeline")

    if sid == "S1":
        if tau is None:
            errs.append(f"{cid}: S1 must have a non-null event_complete_frame (tau)")
        chain = [anchors.get(k) for k in CHAIN]
        if any(v is None for v in chain):
            errs.append(f"{cid}: S1 requires full anchor chain {CHAIN}")
        elif not (chain[0] <= chain[1] <= chain[2] < chain[3]):
            errs.append(f"{cid}: S1 anchors must satisfy approach<=interaction<=concealment<tau, got {chain}")
    elif sid in NEG:
        if tau is not None:
            errs.append(f"{cid}: {sid} (no completed theft) must have event_complete_frame = null")
        if w.get("start_frame") is not None or w.get("end_frame") is not None:
            errs.append(f"{cid}: {sid} must have a null valid_prediction_window")

    if tau is not None:
        s, e = w.get("start_frame"), w.get("end_frame")
        if s is None or e is None:
            errs.append(f"{cid}: tau present but valid_prediction_window has null start/end")
        else:
            if not (s <= e):
                errs.append(f"{cid}: valid_prediction_window start({s}) > end({e})")
            if not (e < tau):
                errs.append(f"{cid}: valid_prediction_window.end({e}) must be < tau({tau})")
    return errs, warns


HARD_ANGLE_DEG = 60.0  # angle(exit, checkout) <= this => 'hard' (weakly separated) case


def separation_angle_deg(m: dict):
    """Angle (deg) between exit_vector and checkout_vector, or None if checkout_vector absent.
    <= HARD_ANGLE_DEG marks a 'hard' clip; a P1 dataset must contain >=1 such clip so results
    aren't read as 'cherry-picked cameras where trajectory trivially works'."""
    z = m.get("zones", {})
    ev, cv = z.get("exit_vector"), z.get("checkout_vector")
    if not ev or not cv:
        return None
    ax, ay = ev["to"][0] - ev["from"][0], ev["to"][1] - ev["from"][1]
    bx, by = cv["to"][0] - cv["from"][0], cv["to"][1] - cv["from"][1]
    na, nb = math.hypot(ax, ay), math.hypot(bx, by)
    if na < 1e-9 or nb < 1e-9:
        return None
    cos = max(-1.0, min(1.0, (ax * bx + ay * by) / (na * nb)))
    return math.degrees(math.acos(cos))


def _schema_errors(doc: dict, schema: "dict | None") -> list[str]:
    if jsonschema is None or schema is None:
        return []
    cid = doc.get("clip_id", "?")
    v = jsonschema.Draft202012Validator(schema)
    return [f"{cid}: schema: {e.message} @ {'/'.join(map(str, e.path)) or '<root>'}"
            for e in v.iter_errors(doc)]


def validate_path(path: Path) -> tuple[list[str], list[str]]:
    schema = json.loads(SCHEMA_PATH.read_text()) if SCHEMA_PATH.exists() else None
    files = ([str(path)] if path.is_file()
             else sorted(glob.glob(str(path / "*.manifest.yaml"))))
    errs: list[str] = []
    warns: list[str] = []
    if jsonschema is None:
        warns.append("jsonschema not installed -> shape validation skipped (semantic only)")
    for f in files:
        doc = yaml.safe_load(Path(f).read_text())
        errs += _schema_errors(doc, schema)
        e, w = validate_doc(doc)
        errs += e
        warns += w
    return errs, warns


def main(argv=None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    target = Path(args[0]) if args else (ROOT / "eval" / "clips")
    errs, warns = validate_path(target)
    for w in warns:
        print(f"WARN  {w}", file=sys.stderr)
    if errs:
        print(f"INVALID manifests ({len(errs)} error(s)) under {target}", file=sys.stderr)
        for e in errs:
            print(f"  - {e}", file=sys.stderr)
        return 1
    print(f"OK: manifests under {target} are semantically valid ({len(warns)} warning(s))")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
