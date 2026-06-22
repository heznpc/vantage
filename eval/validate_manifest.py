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
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
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


def validate_path(path: Path) -> tuple[list[str], list[str]]:
    files = ([str(path)] if path.is_file()
             else sorted(glob.glob(str(path / "*.manifest.yaml"))))
    errs: list[str] = []
    warns: list[str] = []
    for f in files:
        e, w = validate_doc(yaml.safe_load(Path(f).read_text()))
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
