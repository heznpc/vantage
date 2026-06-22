# eval/ — replay harness & ablation gate

Implements the M1 verification skeleton from [../docs/eval-harness.md](../docs/eval-harness.md).
**Parity is measured, not claimed.**

## Layout
- `harness.py` — deterministic replay → `ablation_result` rows. STUB scoring now; the
  real RTMO/ByteTrack/ST-GCN+TCN + BEV forecast pipeline replaces `_score_tracks` in M2.
- `schema/ablation_result.schema.json` — JSON Schema (2020-12) for one result row.
- `validate_csv.py` — stdlib validator (required keys, no extras, enums).
- `fixtures/synthetic_tracks.json` — deterministic synthetic fixture (NOT real data).
- `synth.py` — generates synthetic pose-sequence clips + manifests into `clips/`. **PLUMBING ONLY.**
- `anticipation.py` — **3-arm data-path** (`pose_only` / `pose_2d_traj` / `pose_bev`): manifest+clip →
  per-frame risk → τ/t_θ → FAR-gated **TTA@R80**, **AUC-PR** + a **pre-registered BEV decision rule**.
- `schema/clip_manifest.schema.json`, `schema/anticipation_result.schema.json`.
- `clips/` — synthetic instrumented-pilot clips (`*.clip.json` + `*.manifest.yaml`, `split: synthetic`).

## Run
```bash
# pose-only baseline
uv run python eval/harness.py --backbone rtmo --no-bev --no-calibrated --out eval/out/pose_only.csv
# +BEV (the ablation treatment)
uv run python eval/harness.py --backbone rtmo --bev --calibrated --out eval/out/bev.csv
uv run python eval/validate_csv.py eval/out/bev.csv
```

## Data-path & 3-arm anticipation (P0)

```bash
uv run python eval/synth.py            # (re)generate synthetic clips into eval/clips/
uv run python eval/validate_manifest.py eval/clips   # JSON-schema (shape) + semantic gate, one command
uv run python eval/anticipation.py     # 3-arm: τ/t_θ → TTA@R80, AUC-PR + pre-registered BEV decision (dev-sweep)
uv run python eval/anticipation.py --thresholds eval/thresholds.synthetic.yaml  # fixed dev θ (P1 protocol)
```

`validate_manifest.py` folds **JSON-schema shape** + **semantic** checks (S1 anchor chain, S0/S2 null τ,
window<τ, `calibrated:true` ⇒ `calibration` block). Threshold selection: P0 dev-sweeps the eval set
(**plumbing only**); **P1 must pass a fixed `--thresholds` file** chosen on a dev split — never sweep the eval set.

The ablation that actually matters is **3-arm** — `pose_only` vs `pose_2d_traj` (image-plane
exit motion, **no depth/BEV**) vs `pose_bev` (perspective-weighted pseudo-BEV). **BEV is a real
differentiator only if it beats 2D-trajectory**, not pose-only. The **pre-registered rule** (in
`anticipation.py`: `FAR_MAX`, `DELTA_S`, `TARGET_RECALL`) is committed before looking at numbers so
results can't move the goalposts; it can return `BEV_rejected`.

**Honesty (P0 vs P1):**
- **P0 = synthetic** (`split: synthetic`, `clips/syn_*`) proves **plumbing only** — never that BEV helps.
  The CLI prints a `PLUMBING ONLY` banner and `data_kind=synthetic`.
- **P1 = real / re-annotated staged clips** with a labeled `event_complete` τ — only from here is a
  number a *result*. RTMO/ByteTrack (video→pose) and monocular depth are **deferred** until P1 shows
  BEV is worth it (see [../docs/scenarios/mvp-scenario.md](../docs/scenarios/mvp-scenario.md)).

## Gate staging (matches docs/eval-harness.md §7)
- **Phase 1 — report-only (now):** only **reproducibility** (same seed+config ⇒ identical
  CSV) and **schema validity** are hard gates. Performance numbers are published, never block.
- **Phase 2 — regression gate (after data + calibration lock):** block on regression vs a
  frozen baseline. Not enabled until real data lands (owner decision #1).

## Determinism contract
No wall-clock, no unseeded RNG, no builtin `hash()`. `--timestamp` defaults to the epoch so
output is byte-identical across runs; real runs pass a real timestamp (stamped outside).
