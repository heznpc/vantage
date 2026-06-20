# eval/ — replay harness & ablation gate

Implements the M1 verification skeleton from [../docs/eval-harness.md](../docs/eval-harness.md).
**Parity is measured, not claimed.**

## Layout
- `harness.py` — deterministic replay → `ablation_result` rows. STUB scoring now; the
  real RTMO/ByteTrack/ST-GCN+TCN + BEV forecast pipeline replaces `_score_tracks` in M2.
- `schema/ablation_result.schema.json` — JSON Schema (2020-12) for one result row.
- `validate_csv.py` — stdlib validator (required keys, no extras, enums).
- `fixtures/synthetic_tracks.json` — deterministic synthetic fixture (NOT real data).

## Run
```bash
# pose-only baseline
python3 eval/harness.py --backbone rtmo --no-bev --no-calibrated --out eval/out/pose_only.csv
# +BEV (the ablation treatment)
python3 eval/harness.py --backbone rtmo --bev --calibrated --out eval/out/bev.csv
python3 eval/validate_csv.py eval/out/bev.csv
```

## Gate staging (matches docs/eval-harness.md §7)
- **Phase 1 — report-only (now):** only **reproducibility** (same seed+config ⇒ identical
  CSV) and **schema validity** are hard gates. Performance numbers are published, never block.
- **Phase 2 — regression gate (after data + calibration lock):** block on regression vs a
  frozen baseline. Not enabled until real data lands (owner decision #1).

## Determinism contract
No wall-clock, no unseeded RNG, no builtin `hash()`. `--timestamp` defaults to the epoch so
output is byte-identical across runs; real runs pass a real timestamp (stamped outside).
