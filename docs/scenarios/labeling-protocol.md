# Labeling Protocol — clip manifests for theft anticipation

> Status: **locked** (2026-06-20). The human SOP for annotating clips so anticipation is *measurable*.
> Schema: [eval/schema/clip_manifest.schema.json](../../eval/schema/clip_manifest.schema.json) · Example: [eval/fixtures/scenario_manifest.example.yaml](../../eval/fixtures/scenario_manifest.example.yaml)
> Why this exists: per [R1](../research/anticipation-eval.md), PoseLift/RetailS have **no event timestamps**, so anticipation cannot be measured on them as-is. We re-annotate.

## Who labels what

| field | source | note |
|---|---|---|
| `scenario_id`, `zones`, `tracks.primary_actor_track_id` | **human** | scene setup |
| `anchors.*` incl. **`event_complete_frame` (τ)** | **human** | the anchor that makes anticipation measurable |
| `valid_prediction_window` | **human** (derived from anchors) | `end_frame` < τ |
| **`first_valid_alert` (t_θ)** | **model, at eval time** | NOT stored in the manifest |
| `TTA = (τ − t_θ)/fps` | **computed** | lead-time in seconds |

**If `event_complete_frame` is missing, the clip is unusable for anticipation** — it becomes a detection-only clip.

## Anchor definitions (annotate in order)

- `approach_start_frame` — actor enters the aisle / starts moving toward `shelf_zone`.
- `item_interaction_start_frame` — hand reaches the shelf / contacts an item.
- `concealment_start_frame` — item moves toward body / bag / clothing / `occlusion_zone`.
- **`event_complete_frame` (τ)** — the **last frame the theft is still in progress** (e.g. the moment the item is fully concealed AND the actor has committed to leaving without payment). This is a **labeling convention, not a physical onset** — keep it consistent across annotators.

## valid_prediction_window
- `start_frame` ≥ event onset estimate (usually `approach_start_frame`).
- `end_frame` = **τ − 1** (the last frame an alert still counts as *anticipation*).
- An alert at or after τ is **detection, lead-time 0** — never count it as anticipation.

## Scenario specifics
- **S0 / S2-returned** (no theft): `event_complete_frame = null`, `valid_prediction_window.{start,end} = null`. These are negative controls — any autonomous alert is a false positive.
- **S1**: full anchor chain + integer τ.
- **S3** (occlusion/ID-switch): annotate `occlusion_zone`; the eval checks the trajectory is invalidated / confidence drops through contamination — do **not** silently keep the track.
- **S4** (uncalibrated): `calibrated: false`; coordinates are **image pixels**; spatial/metric outputs (absolute ETA, distance) are forbidden downstream — relative anticipation only.
- **S5** (multi-person): mark `scenario_id: S5`; out of MVP support → system must declare low confidence.

## Calibrated vs uncalibrated (R1 boundary)
- `calibrated: true` requires a floor homography; coordinates are floor-plan metres and **reprojection RMS must be tracked** (run manifest, not here). Only then may absolute distance/seconds be reported.
- `calibrated: false` → pixels; report **relative/ordinal anticipation only**.

## Staged vs real
- `split: synthetic | staged | real`. **Headline metrics must be `real`.** `synthetic` = plumbing only (no claims); `staged` = acted/instrumented (dev/ablation); report staged and real side-by-side with the gap explicit (RetailS staged→real: AUC-PR 86.60→38.44).

## Forbidden / pitfalls (from R1)
- **All-frames-positive** labeling (no temporal structure) → anticipation unmeasurable.
- Using `event_complete_frame` as if it were the *onset*.
- Tuning the alert threshold θ on the test split.
- Citing manifests built on PoseLift/RetailS as "anticipation prior art" — they are re-annotations of detection datasets.
- Reporting `mTTA` ungated, or absolute seconds from an uncalibrated clip.

## Quality
- Two annotators on a sample; report frame-level agreement on τ (±k frames). Large disagreement on τ ⇒ the scenario boundary is ill-defined and must be tightened before use.

## Relationship to the M1 fixture
[eval/fixtures/synthetic_tracks.json](../../eval/fixtures/synthetic_tracks.json) is a synthetic harness self-test (carries a per-track `event_complete_frame`). Real clips use this richer manifest; the harness reads τ / valid-window from the manifest for anticipation metrics in M2.
