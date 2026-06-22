#!/usr/bin/env python3
"""Generate synthetic 'instrumented-pilot' pose-sequence clips + manifests.

NOT real data. honestly labeled split=staged, calibrated=false (image px, uncalibrated).
Purpose: make the data-path (manifest -> clip -> harness -> real TTA/FAR/AUC-PR) run
end-to-end BEFORE real clips are sourced. A synthetic clip proves PLUMBING ONLY — never
a result about whether +BEV helps. Real / staged clips (P1) drop into the same path.
Deterministic: seeded, no wall-clock.
"""
from __future__ import annotations

import json
import random
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "eval" / "clips"

# Scene (image px). Approach is vertical; exit is RIGHT, checkout is LEFT -> a leave
# toward checkout produces ~zero exit-direction signal (clean separation).
ENTRY = (640, 690)
SHELF = (640, 300)
EXIT = (1180, 360)
CHECKOUT = (100, 360)
SHELF_ZONE = [[500, 210], [780, 210], [800, 330], [480, 330]]
OCCL_ZONE = [[900, 320], [980, 320], [980, 520], [900, 520]]
SHELF_REACH = (660, 225)
FPS = 15


def _lerp(a, b, t):
    t = max(0.0, min(1.0, t))
    return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)


def _body(center, rwrist):
    cx, cy = center
    hip_r = (cx + 18, cy - 85)
    return {
        "nose": [round(cx, 1), round(cy - 175, 1)],
        "l_wrist": [round(cx - 55, 1), round(cy - 60, 1)],  # left hand parked at side
        "r_wrist": [round(rwrist[0], 1), round(rwrist[1], 1)],
        "l_hip": [round(cx - 18, 1), round(cy - 85, 1)],
        "r_hip": [round(hip_r[0], 1), round(hip_r[1], 1)],
        "l_ankle": [round(cx - 15, 1), round(cy, 1)],
        "r_ankle": [round(cx + 15, 1), round(cy, 1)],
    }


def _side(center):
    cx, cy = center
    return (cx + 55, cy - 60)


def _hip_r(center):
    cx, cy = center
    return (cx + 22, cy - 81)  # right hand pressed to right hip (concealment)


def _s1(f):
    if f < 28:
        c = _lerp(ENTRY, SHELF, f / 28)
        w = _side(c)
    elif f < 44:
        c = SHELF
        w = SHELF_REACH
    else:
        c = _lerp(SHELF, EXIT, (f - 44) / 26)  # exit drift starts at 44
        w = _lerp(SHELF_REACH, _hip_r(c), (f - 44) / 8)  # conceal ramps 44..52
    return c, w


def _s0(f):
    if f < 28:
        c = _lerp(ENTRY, SHELF, f / 28)
        w = _side(c)
    elif f < 48:
        c = SHELF
        w = SHELF_REACH if (f < 36 or f >= 42) else _side(c)  # inspect (up, dip, up)
    else:
        c = _lerp(SHELF, CHECKOUT, (f - 48) / 32)  # leave toward checkout (not exit)
        w = _side(c)
    return c, w


def _s2(f):
    if f < 28:
        c = _lerp(ENTRY, SHELF, f / 28)
        w = _side(c)
    elif f < 44:
        c, w = SHELF, SHELF_REACH
    elif f < 54:
        c, w = SHELF, _lerp(SHELF_REACH, _hip_r(SHELF), (f - 44) / 8)  # conceal-like blip
    elif f < 64:
        c, w = SHELF, _lerp(_hip_r(SHELF), SHELF_REACH, (f - 54) / 8)  # return item
    else:
        c = _lerp(SHELF, CHECKOUT, (f - 64) / 24)  # leave toward checkout
        w = _side(c)
    return c, w


# clip_id, scenario, frames, fn, anchors(dict or None), seed
SPECS = [
    ("syn_S1_01", "S1", 84, _s1, {"approach_start_frame": 0, "item_interaction_start_frame": 28, "concealment_start_frame": 44, "event_complete_frame": 70}, 11),
    ("syn_S1_02", "S1", 88, _s1, {"approach_start_frame": 0, "item_interaction_start_frame": 28, "concealment_start_frame": 44, "event_complete_frame": 70}, 12),
    ("syn_S1_03", "S1", 84, _s1, {"approach_start_frame": 0, "item_interaction_start_frame": 28, "concealment_start_frame": 44, "event_complete_frame": 70}, 13),
    ("syn_S0_01", "S0", 80, _s0, None, 21),
    ("syn_S0_02", "S0", 80, _s0, None, 22),
    ("syn_S2_01", "S2", 88, _s2, None, 31),
    ("syn_S2_02", "S2", 88, _s2, None, 32),
]


def _manifest(clip_id, scenario, anchors):
    tau = anchors["event_complete_frame"] if anchors else None
    return {
        "clip_id": clip_id,
        "camera_id": "syn-cam",
        "scenario_id": scenario,
        "fps": FPS,
        "calibrated": False,  # synthetic image space; uncalibrated -> relative anticipation only
        "split": "staged",    # synthetic instrumented-pilot, NOT real-world proof
        "zones": {"shelf_zone": SHELF_ZONE, "occlusion_zone": OCCL_ZONE,
                  "exit_vector": {"from": list(SHELF), "to": list(EXIT)}},
        "tracks": {"primary_actor_track_id": "t-actor-1"},
        "anchors": anchors or {"event_complete_frame": None},
        "valid_prediction_window": {"start_frame": 0, "end_frame": (tau - 1) if tau else None},
        "notes": "SYNTHETIC instrumented-pilot. Plumbing only; not evidence about +BEV.",
    }


def generate(out_dir: Path = OUT) -> list[str]:
    out_dir.mkdir(parents=True, exist_ok=True)
    written = []
    for clip_id, scenario, frames, fn, anchors, seed in SPECS:
        rng = random.Random(seed)
        seq = []
        for f in range(frames):
            c, w = fn(f)
            c = (c[0] + rng.uniform(-2, 2), c[1] + rng.uniform(-2, 2))
            seq.append({"f": f, "kp": _body(c, w), "present": True})
        clip = {"clip_id": clip_id, "fps": FPS, "frames": frames, "image_size": [1280, 720],
                "primary_actor_track_id": "t-actor-1", "tracks": {"t-actor-1": seq}}
        (out_dir / f"{clip_id}.clip.json").write_text(json.dumps(clip, indent=2, sort_keys=True) + "\n")
        (out_dir / f"{clip_id}.manifest.yaml").write_text(
            yaml.safe_dump(_manifest(clip_id, scenario, anchors), sort_keys=True, allow_unicode=True))
        written.append(clip_id)
    return written


if __name__ == "__main__":
    ids = generate()
    print(f"generated {len(ids)} synthetic clips -> {OUT.relative_to(ROOT)}/ : {', '.join(ids)}")
