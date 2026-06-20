# Vantage

**Spatial-grounded predictive CCTV anomaly / theft detection — detector-first.**

> Status: **M1 in progress** (2026-06-20). The M0 design baseline is frozen
> ([REBUILD_DESIGN.md](REBUILD_DESIGN.md)); M1 adds the runnable skeleton — a contracts
> single-source-of-truth with a codegen drift-gate, and a deterministic eval harness with
> the pose-only vs +BEV ablation. Perception/spatial models land in M2/M3.

## What this is

Vantage is a from-scratch reimplementation of a CCTV theft/anomaly-detection system I
originally conceived with a (now-disbanded) team. The prior repositories are
All-Rights-Reserved and multi-author, so **no source code is carried over — only the
problem definition.** The prior design used a VLM as the core classifier; Vantage
**deliberately discards that** and puts a lean perception core at the center.

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
- **Differentiator:** *calibrated single-camera BEV risk forecasting* — lift 2D to a
  pseudo-metric bird's-eye view and roll trajectories forward to anticipate an incident
  **before it completes**. Homography-first; monocular depth is an auxiliary signal. This is
  an assembly of off-the-shelf parts, **not a trained world model**.
- **Verification:** parity is **measured, not claimed** — a `pose-only` vs `+BEV`
  lead-time-vs-FAR ablation on a shared clip set. See [docs/eval-harness.md](docs/eval-harness.md).

## Licensing (deliberate)

> Default pose backbone: **RTMO/RTMPose (Apache-2.0)**, chosen to keep this repository
> permissively licensed. **YOLO26 was evaluated but excluded by default** due to
> AGPL-3.0 / Enterprise licensing friction (available only under an `optional-agpl-eval`
> profile, not required for normal operation). Backbone parity is not claimed — it is
> measured on the same evaluation harness (keypoint stability, ID-switch rate,
> temporal-scorer AUC, lead-time-vs-FAR) on real CCTV theft clips.

Repository license: **Apache-2.0** ([LICENSE](LICENSE), [NOTICE](NOTICE)).
Per-model weight licenses and source pins: [MODEL_CARD.md](MODEL_CARD.md).

## Running the M1 skeleton

```bash
make gen-contracts          # regenerate typed models from contracts/*.yaml (single source of truth)
make test                   # hard gates: reproducibility + CSV schema + contract no-drift (stdlib)
make eval && make validate  # report-only ablation: pose-only vs +BEV
```

CI (`.github/workflows/ci.yml`) enforces the same hard gates plus a contracts drift check;
performance numbers are uploaded as artifacts and never block the merge (eval gate Phase 1).

## Documents

- [REBUILD_DESIGN.md](REBUILD_DESIGN.md) — master design, stack, data flow, audit-gap mapping, roadmap.
- [docs/adr/ADR-001-license-and-pose-backbone.md](docs/adr/ADR-001-license-and-pose-backbone.md) — license & backbone decision record.
- [MODEL_CARD.md](MODEL_CARD.md) — model inventory, weight licenses, source pins.
- [docs/eval-harness.md](docs/eval-harness.md) — evaluation gates and ablation methodology.

> Design docs are currently Korean working documents; they will be translated for publication.
