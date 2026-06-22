# MVP Scenario — single-shelf theft anticipation

> Status: **locked** (2026-06-20). This is the ONE thing Vantage must prove.
> Related: [scenario-matrix](scenario-matrix.md) · [labeling-protocol](labeling-protocol.md) · [R1 anticipation-eval](../research/anticipation-eval.md)

## The line we will not cross

Aegis classified a broad event set (`assault / burglary / dump / swoon / vandalism`) with a VLM looking at the scene. **Vantage does the opposite: one narrow scenario, proven before completion.** If we widen the event taxonomy we are back to fuzzy VLM scene classification — explicitly out of scope.

## MVP scenario (S1 is the make-or-break)

**Setup:** single CCTV, single shelf, single aisle. One person.

**Sequence:** approach the shelf → pick an item → conceal it (occlusion area / bag / clothing) → move toward the **exit** (not the checkout).

**Required system behavior:** raise `risk` **inside the valid prediction window, BEFORE `event_complete` (τ)** — not after. Reversible actions (notify / voice) may fire autonomously; **irreversible actions (dispatch) go to HITL.**

**Success = prove S1:** `first_valid_alert` (t_θ) occurs before `event_complete` (τ) at an acceptable false-alarm rate, with the lead-time reported FAR/recall-gated (see R1). **If S1 cannot be shown, Vantage is not a predictive system — it is a detector.**

## In scope (MVP)
- S0 normal shopping (false-positive suppression), S1 core theft, S2 ambiguous (no autonomous dispatch), S3 occlusion / ID-switch handling, S4 uncalibrated camera (relative risk only). See [scenario-matrix](scenario-matrix.md).

## Out of scope (MVP)
- S5 multi-person / accomplices → handled as **"unsupported / low confidence"**, never silently mis-handled.
- Broad event taxonomy (assault/vandalism/…), multi-camera fusion, physical actuation, VLM-as-classifier.

## Preconditions (camera / scene) — a clip is *in-spec* only if these hold

These are hard assumptions of the S1 design (currently encoded only in `eval/synth.py`). A clip
that violates them is **out-of-spec** — failure on it is a *data* problem, not a model problem,
and must not be used to judge the system.

- **Single fixed camera; one primary actor** in frame for the event.
- **Exit direction and checkout direction are visually separable in the image plane** — i.e. "moving
  toward the exit" is observable as a distinct direction from "moving toward checkout". If the camera
  cannot see the exit vector (exit behind camera, head-on aisle), the BEV/trajectory signal is
  undefined and the clip is out-of-spec.
- **The shelf, the concealment region, and the exit path are all within view.**
- `zones.exit_vector` in the clip manifest encodes this exit direction; if it can't be drawn
  truthfully for a clip, the clip does not qualify for S1.

## M2 — definition of done (redefined)

M2 is **not** "attach RTMO". M2 is **"a replay pipeline that passes S0/S1/S2/S3"**:
- Ingest a re-annotated clip (per [clip_manifest.schema.json](../../eval/schema/clip_manifest.schema.json)) → run the perception+temporal(+BEV) pipeline → emit `ablation_result` rows.
- S0: no autonomous alert (FP suppressed). S1: `first_valid_alert` before `event_complete`. S2: stays low/medium, **no autonomous dispatch**. S3: occlusion/ID-switch invalidates the trajectory or drops confidence.
- Models (RTMO/ByteTrack/ST-GCN+TCN/BEV) are the **means** to pass the scenarios, not the goal. Swapping a model must not change the scenario contract.

## Why this narrowing is the right call
- **Measurable:** one scenario + re-annotated anchors makes anticipation provable (R1).
- **Honest:** we claim exactly one capability and test it on real data.
- **Differentiated:** "single-shelf theft anticipation, proven before completion" is a sentence no generic CCTV-AI clone can truthfully say.
