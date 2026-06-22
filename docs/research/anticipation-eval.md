# R1 — Anticipation Evaluation Protocol (claim-lock)

> Status: **locked from deep-research R1** (2026-06-20). Scope = how to *honestly prove* "pre-completion
> theft anticipation". Feeds [../eval-harness.md](../eval-harness.md) and the M2/M3 harness.
> Evidence: 25/25 verified claims (3-vote adversarial, 0 killed). NOT market analysis.

## TL;DR (the locks)

1. **PoseLift & RetailS are DETECTION-only** (per-frame binary labels, no event timestamps). They are **post-hoc baselines, NOT anticipation prior art.** → Vantage **must re-annotate** theft clips with temporal anchors to make any anticipation claim.
2. **Lead-time is gameable** (alert early always → huge lead time, huge false-alarm rate). Anticipation must be reported **false-alarm-/recall-gated** (TTA@R80, FAR-gated mTTA) and as a **lead-time-vs-FAR frontier**, never as a single scalar.
3. **The anchor τ is a labeling convention, not a measured physical onset.** Without metric-3D ground truth a pseudo-metric BEV may claim only **relative/ordinal** anticipation. **Absolute "seconds-to-event" derived from an uncalibrated BEV is forbidden.** (Measured lead-time in seconds from frame timestamps vs. the labeled anchor is fine — it is temporal, not spatial.)
4. **Staged→real gap is large** (RetailS: AUC-ROC 87.24→63.22, AUC-PR 86.60→38.44). **Headline numbers must be on REAL held-out data; prefer AUC-PR** for the rare-event imbalance. Staged data is supplementary only.

## 1. Taxonomy & labeling

**Detection vs anticipation** — the field separates *detection* (per-frame binary, scores the event while/after it happens) from *anticipation* (predicts before the event finishes, characterized by a lead time τ−t_θ) [survey [2308.15985](https://arxiv.org/pdf/2308.15985); [2410.14045](https://arxiv.org/html/2410.14045)]. The anticipation lineage is **traffic-accident** (DAD [2106.10197](https://arxiv.org/pdf/2106.10197), CCD/UString, LATTE) — out-of-domain for retail, so it lends the *protocol*, not the data.

**Anchors (must be re-annotated on real theft clips):**
- `event_complete` = **τ** — the last frame the theft is still in progress (the labeled positive boundary). A *convention*, not a measured onset.
- `first_valid_alert` = **t_θ** — first frame the system score ≥ θ **within the valid window**.
- `TTA` (time-to-event) = **(τ − t_θ) / fps** seconds (fps is known from the video → temporal lead-time is measurable without any spatial calibration).
- **valid prediction window** = `[w_start, τ)` where `w_start` ≥ estimated event onset (or track start). An alert at/after τ is **detection, not anticipation** (lead-time 0).

**Labeling pitfalls / failure modes** [[2510.22260](https://arxiv.org/abs/2510.22260)]: "all-frames-positive" labeling (no temporal structure → anticipation unmeasurable); using `event_complete` as if it were the onset; threshold θ tuned on the test split; label leakage across the window.

## 2. EVAL PROTOCOL table

| metric | definition | data req | label/anchor | known failure mode | calibrated-only? | CI gate |
|---|---|---|---|---|---|---|
| **AUC-PR (real)** | area under precision–recall | real held-out | per-frame binary | — (intended for rare events) | N | **regression (Phase 2)** |
| **AUC-ROC (real, +staged ctx)** | rank probability P(score⁺>score⁻) | real (+staged as context) | per-frame binary | optimistic under imbalance | N | report-only |
| **TTA@R80** | (τ−t_θ)/fps at **fixed recall 0.80** | real | τ + t_θ | constrains *miss* rate, not FAR | N | **regression (Phase 2)** |
| **FAR-gated mTTA / TTA@FPPH** | mean TTA at a fixed false-positives-per-hour | real + normal-only clips | τ + normal track durations | needs enough normal data | N | report-only → regression |
| **lead-time-vs-FAR frontier** | TTA across a θ/FAR sweep | real | τ + θ sweep | it's a curve, not a scalar (that's the point) | N | report-only (artifact) |
| **relative anticipation Δ** | frames earlier than the pose-only baseline at matched FAR | real | same anchors | only meaningful vs a fixed baseline | N | report-only |
| **spatial (distance/velocity, m, m/s)** | homography-projected world quantity | **calibrated** camera | floor plan + intrinsics + **reprojection RMS** | uncalibrated ⇒ invalid | **Y** | report-only (calibrated cams only) |

*(reproducibility + CSV-schema remain the only Phase-1 hard gates — see [eval-harness.md §7](../eval-harness.md).)*

## 3. Baseline / prior-art (anticipation-relevant only)

| method | anticipate / ongoing / post-hoc | metric | data | limitation | relevance |
|---|---|---|---|---|---|
| PoseLift (STG-NF/TSGAD/GEPC) | **post-hoc detection** | AUC-ROC/PR, EER | real US store | no event timestamps | **not anticipation prior art**; supplies clips for re-annotation only |
| RetailS ([2603.04723](https://arxiv.org/html/2603.04723v1)) | **ongoing/concurrent detection** | AUC-ROC/PR (staged+real) | staged+real | no BEV/depth/anticipation | strongest in-domain **detection** baseline; not anticipation |
| Shopformer | post-hoc detection | AUC-ROC | PoseLift | no forecasting | not anticipation |
| Traffic anticipation (DAD/CCD/UString/LATTE) | **true anticipation** | AP, mTTA, TTA@R | driving | out-of-domain | **source of the metric protocol**, not the data |

## 4. Calibrated vs uncalibrated — claim boundary

**Provable WITHOUT metric-3D GT** (uncalibrated / pseudo-metric):
- Measured anticipation **lead-time TTA in seconds** = (τ−t_θ)/fps (temporal; from frame timestamps + labeled anchor).
- **Relative/ordinal** anticipation ("fires N frames earlier than pose-only at matched FAR").
- Image-plane / homography-*relative* trajectory tendencies (only if **reprojection error is reported**).
- AUC-PR / AUC-ROC / FAR-gated TTA on the re-annotated anchors.

**Requires metric calibration** (homography to a *measured* floor plan + intrinsics, **reprojection RMS reported**):
- Absolute world distance (m), velocity (m/s), distance-to-zone.
- Any "seconds-to-event" **derived from metric spatial extrapolation** (velocity × distance).

**FORBIDDEN (over-claiming):**
- `mTTA` reported **alone** (ungated) — gameable.
- Citing **PoseLift / RetailS / Shopformer as anticipation prior art** (detection-only).
- **Headlining staged-data** numbers; reporting staged without the real number beside it.
- **Absolute seconds-to-event from an uncalibrated/pseudo-metric BEV.**
- **top-1 accuracy** for anticipation [[2410.14045](https://arxiv.org/html/2410.14045)].
- "all-frames-positive" labeling.

## 5. Staged→real protocol

- Report **real and staged side-by-side with the gap explicit**; **headline = real**. RetailS gap (Table 2, [2603.04723](https://arxiv.org/html/2603.04723v1)): AUC-ROC 87.24→63.22, **AUC-PR 86.60→38.44** (PR collapses harder under real imbalance).
- **Prefer AUC-PR** as the primary detection metric for rare theft; AUC-ROC is context only.

## 6. Maps into the harness (M2/M3)

- The synthetic fixture already carries `event_complete_frame` → wire the real τ/t_θ anchors through the same field on re-annotated clips.
- Extend the `ablation_result` metric enum (in M2, with the real pipeline) to: `auc_pr_real`, `tta_at_r80`, `mtta_far_gated`, `lead_time_vs_far` (artifact), `rel_anticipation_delta`; keep current `temporal_auc`/`far_at_leadtime`/`lead_time_s` deprecated/aliased.
- Gate staging unchanged: **Phase 1 report-only** until real anchors + (for any spatial metric) calibration are locked; **Phase 2 regression** on `auc_pr_real` + `tta_at_r80` against a frozen real baseline.

## 7. Open questions (carry to R2 / M2)

- Ground [arXiv:2601.01457](https://arxiv.org/abs/2601.01457) + a BEV-scale source to fully pin the metric-3D boundary (not grounded this run).
- Is there any retail-theft dataset with explicit **sub-event landmarks** usable as `event_complete` **without** re-annotation? (Assume re-annotation is required.)
- Defensible **FP/hour** threshold (traffic uses ~1 false alarm/min as a reference).
- **Context-length** bound: RetailS events are only ~25–35 frames.

## Sources

Definitions/metrics: [2308.15985](https://arxiv.org/pdf/2308.15985), [2410.14045](https://arxiv.org/html/2410.14045), [2106.10197 (DAD)](https://arxiv.org/pdf/2106.10197), [2409.01256](https://arxiv.org/pdf/2409.01256), [2510.22260 (FAR-gated mTTA)](https://arxiv.org/abs/2510.22260), [2504.04103](https://arxiv.org/pdf/2504.04103), [2511.08640](https://arxiv.org/html/2511.08640). Datasets / domain gap: [PoseLift 2501.06591](https://arxiv.org/abs/2501.06591), [RetailS 2603.04723](https://arxiv.org/html/2603.04723v1). Calibration/BEV: [2601.01457](https://arxiv.org/abs/2601.01457) (ungrounded this run), [2103.15293](https://arxiv.org/pdf/2306.17253).
