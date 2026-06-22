# Scenario Matrix (S0–S5)

> Locked behavior contract for the MVP. Each scenario has an expected behavior, an eval handle, and a pass criterion.
> Related: [mvp-scenario](mvp-scenario.md) · [labeling-protocol](labeling-protocol.md) · [R1 anticipation-eval](../research/anticipation-eval.md)

| ID | scenario | expected behavior | eval handle | pass criterion | MVP |
|---|---|---|---|---|---|
| **S0** | normal shopping: approach → pick → inspect → return / head to checkout | **no alert**; suppress false positives | FP rate on normal tracks; AUC-PR negatives | autonomous alert rate ≈ 0 on S0 set | ✅ |
| **S1** | **core theft**: approach → pick → conceal → exit-direction | `first_valid_alert` (t_θ) **before** `event_complete` (τ) | **TTA@R80**, FAR-gated mTTA, lead-time-vs-FAR | t_θ < τ at acceptable FAR on **real** clips | ✅ (make-or-break) |
| **S2** | ambiguous: long dwell / repeated approach / hand near bag, **but item returned** | **low/medium** risk; **no autonomous dispatch** | risk distribution on S2; dispatch-trigger count | zero autonomous dispatch on S2; risk < dispatch threshold | ✅ |
| **S3** | occlusion / ID-switch: brief block by person / pillar / shelf | detect track contamination → **invalidate trajectory or drop confidence** | ID-switch rate; trajectory-reset events; confidence on S3 | no high-confidence anticipation through a contaminated track | ✅ |
| **S4** | **uncalibrated** camera | **relative risk only**; **no absolute ETA / distance** | calibrated flag = false → spatial metrics suppressed | no absolute seconds/metres emitted when `calibrated=false` | ✅ |
| **S5** | multi-person / accomplices | **"unsupported / low confidence"** (never silent mishandle) | scenario flagged out-of-support | system declares low confidence, does not assert a verdict | ❌ (out) |

## Notes
- **S1 is the only existential one.** S0/S2/S3/S4 protect S1 from reading as luck (false positives, ambiguity, contamination, over-claim). S5 is a guardrail, not a feature.
- **S2 vs S1** is the hardest discrimination (conceal-then-return vs conceal-then-exit) — the exit-direction + non-return is the signal, and it is exactly what BEV trajectory is supposed to add over pose-only.
- **S4** enforces the R1 calibrated/uncalibrated boundary at the scenario level: an uncalibrated clip may still pass S1 in **relative** terms (alert before τ) but must not emit metric ETA/distance.
- Each scenario maps to clips via `scenario_id` in [clip_manifest.schema.json](../../eval/schema/clip_manifest.schema.json); the replay harness selects/filters by `scenario_id`.

## CI staging (per R1 / eval-harness §7)
- **Phase 1 (now):** S0–S4 are **report-only** — measured and published, never block. Hard gates remain reproducibility + schema only.
- **Phase 2 (after real anchors + baseline freeze):** regression-gate S0 (FP rate) and S1 (`tta_at_r80`, `auc_pr_real`) against a frozen **real** baseline.
