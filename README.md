# Vantage

**Detector-first retail theft-*anticipation* system. MVP proof gate: single-shelf *pre-completion* theft warning (S1).**

> **Status (2026-06-20): this repo has not proven anything yet.** Done: M0 design ·
> M1 skeleton (contracts SSOT + codegen drift-gate, deterministic eval harness) · R1
> anticipation-eval protocol · scenario lock (S0–S5 + clip manifest).
>
> Vantage is a *predictive* system **only if** it passes its one gate — **S1: raise risk
> before `event_complete` on real, re-annotated clips, FAR/recall-gated.** Until then it is
> honestly a **detector with an anticipation hypothesis**, not a proven predictive system.
>
> **Next — M2** = a replay pipeline that passes S0/S1/S2/S3 (*not* "attach RTMO"); **M3** =
> show `+BEV` beats **`+2D-trajectory`** on S1 (3-arm: pose-only / +2D-traj / +BEV — earlier alert, fewer false alarms). If 2D suffices, BEV is rejected.

## What this is

Vantage is a from-scratch reimplementation of a CCTV theft/anomaly-detection system I
originally conceived with a (now-disbanded) team. The prior repositories are
All-Rights-Reserved and multi-author, so **no source code is carried over — only the
problem definition.** The prior design used a VLM as the core classifier; Vantage
**deliberately discards that** and puts a lean perception core at the center.

**Vantage (the system) vs the MVP (the proof gate).** The *system* goal is a detector-first
stack — pose perception core + tracking/temporal scorer + BEV trajectory layer +
pre-completion risk + HITL action loop + a verifiable eval harness. The *MVP* is **not** all
of that; it is the single slice that proves the system is genuinely predictive — **S1,
single-shelf pre-completion theft warning.** S1 is the first gate, not the whole identity.

**What deep-research locked (so we don't over-claim):** the detector-first + privacy-by-pose
core is **established prior art, not a USP**; the real differentiator is *proving
pre-completion anticipation on real data* (lead-time vs FAR), which **cannot even be measured
without re-annotated clips** (`event_complete` τ, `first_valid_alert` t_θ). See
[docs/scenarios/mvp-scenario.md](docs/scenarios/mvp-scenario.md) and
[docs/research/anticipation-eval.md](docs/research/anticipation-eval.md).

## Approach

```
camera → RTMO/RTMPose (pose) → ByteTrack → ST-GCN+TCN temporal scorer   ← always-on core
                                              │ (cheap-gate)
            homography BEV-lift (+ depth, aux) → trajectory rollout → pre-theft risk + lead-time
                                              │
                 agentic software actions (spotlight / voice / notify) → HITL for irreversible
                                              │ (optional, flag-gated)
                                      VLM explanation
```

- **Core (workhorse):** pose detection + tracking + a temporal anomaly scorer. Runs fully
  without depth, BEV, or any VLM.
- **Differentiator (the bet being proven, not yet demonstrated):** *calibrated single-camera
  BEV risk forecasting* — lift 2D to a pseudo-metric bird's-eye view and roll trajectories
  forward to anticipate an incident **before it completes**. Homography-first; monocular depth
  is auxiliary. An assembly of off-the-shelf parts, **not a trained world model**. Uncalibrated
  ⇒ **relative anticipation only** (no absolute ETA/distance).
- **Verification:** parity is **measured, not claimed** — **3-arm** `pose-only` / `+2D-trajectory` /
  `+BEV` (BEV must beat **2D-trajectory**, not just pose-only), reported FAR/recall-gated on **real**
  clips. See [docs/eval-harness.md](docs/eval-harness.md), [docs/research/anticipation-eval.md](docs/research/anticipation-eval.md).

## Licensing (deliberate)

> Default pose backbone: **RTMO/RTMPose (Apache-2.0)**, chosen to keep this repository
> permissively licensed. **YOLO26 was evaluated but excluded by default** due to
> AGPL-3.0 / Enterprise licensing friction (available only under an `optional-agpl-eval`
> profile, not required for normal operation). Backbone parity is not claimed — it is
> measured on the same evaluation harness on real CCTV theft clips.

Repository license: **Apache-2.0** ([LICENSE](LICENSE), [NOTICE](NOTICE)).
Per-model weight licenses and source pins: [MODEL_CARD.md](MODEL_CARD.md).

## Running

```bash
make gen-contracts   # regenerate typed models from contracts/*.yaml (single source of truth)
make test            # hard gates: reproducibility + CSV schema + contract no-drift + anticipation
make anticipation    # 3-arm data-path: pose-only / +2D-traj / +BEV + pre-registered BEV decision
make eval            # (M1 harness) report-only pose-only vs +BEV stub ablation
```

All targets run through `uv` (`PYTHON ?= uv run python`) so deps resolve — `make` no longer needs an ambient Python with pyyaml.

CI (`.github/workflows/ci.yml`) enforces the same hard gates plus a contracts drift check;
performance numbers are uploaded as artifacts and never block the merge (eval gate Phase 1).

## Documents

- [REBUILD_DESIGN.md](REBUILD_DESIGN.md) — master design, stack, data flow, audit-gap mapping, roadmap.
- [docs/scenarios/mvp-scenario.md](docs/scenarios/mvp-scenario.md) · [scenario-matrix.md](docs/scenarios/scenario-matrix.md) · [labeling-protocol.md](docs/scenarios/labeling-protocol.md) — the S1 MVP, the S0–S5 behavior contract, and the clip-labeling SOP.
- [docs/research/anticipation-eval.md](docs/research/anticipation-eval.md) — R1: locked anticipation eval protocol (metrics, labeling, forbidden practices).
- [docs/eval-harness.md](docs/eval-harness.md) — evaluation gates and ablation methodology.
- [docs/adr/ADR-001-license-and-pose-backbone.md](docs/adr/ADR-001-license-and-pose-backbone.md) — license & backbone decision record.
- [MODEL_CARD.md](MODEL_CARD.md) — model inventory, weight licenses, source pins.

> Design docs are currently Korean working documents; they will be translated for publication.
