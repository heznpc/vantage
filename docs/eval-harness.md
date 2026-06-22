# Eval Harness — 검증 게이트 명세

> 원칙: **성능 우열은 주장이 아니라 측정한다.** 차별화(공간지능 예측)의 정당성은 ablation이 증명한다.
> 1주차(첫) 산출물: `replay harness` + 아래 `ablation CSV schema`. 차별화 코드보다 **먼저** 만든다.
> **Anticipation 라벨링·지표·calibrated 경계·금지관행은 [R1 anticipation-eval (locked)](research/anticipation-eval.md)에서 잠금** — 이 문서는 그 요약/배선이다.
> 관련: [REBUILD_DESIGN](../REBUILD_DESIGN.md) · [ADR-001](adr/ADR-001-license-and-pose-backbone.md) · [MODEL_CARD](../MODEL_CARD.md)

## 1. 목적

- **차별화 ablation(핵심):** `pose-only` 베이스라인 대비 `+BEV(공간예측)`가 **lead-time-vs-FAR 프런티어**를 측정 가능하게 개선하는가? 개선 못 하면 BEV 레이어는 장식 → 조기 폐기/단순화.
- **anticipation은 detection과 다르다(R1):** "완료 전 예측" 주장은 **재라벨된 시간 앵커**(`event_complete`=τ, `first_valid_alert`=t_θ)가 있어야 성립. lead-time은 gameable → **FAR/recall-gated로만** 보고.
- **backbone 비교(참고):** 동일 clip set에서 RTMO/RTMPose vs (격리)YOLO26의 keypoint stability·ID-switch·temporal 성능 측정. **"이긴다"가 아니라 "동일 harness로 측정"**.

## 2. 평가 데이터셋

| 데이터 | 용도 | 한계(정직) |
|---|---|---|
| **PoseLift / RetailS** | temporal scorer 학습/평가(detection) | **detection-only — 이벤트 타임스탬프 없음.** anticipation prior art 아님 → 앵커 **재라벨 필요**(R1) |
| **호모그래피 알려진 clip(소수)** | BEV held-out 검증 + 공간 metric | 소수라 평가셋 신뢰 한계 |
| **실제 CCTV 절도 clip(미확보)** | 최종 검증 + 재라벨 앵커 | **owner 결정 #1** — 없으면 anticipation은 relative + self-consistency까지만 |

> **정직성 경고(R1):** ① PoseLift/RetailS는 detection-only이므로 **anticipation을 주장하려면 τ/t_θ 재라벨이 선행**. ② staged→real 갭 큼(RetailS AUC-PR 86.60→38.44) → **headline은 real, AUC-PR 우선**. ③ metric-3D GT 없는 pseudo-BEV는 **relative anticipation만**, 절대 초(seconds) 금지.

## 3. 지표 (R1 잠금)

상세 정의·실패모드·calibrated 여부는 [anticipation-eval.md §2](research/anticipation-eval.md). 요약:

- **AUC-PR (real, 1순위)** — 희소 이벤트 주 지표. AUC-ROC은 context용(불균형에 낙관적).
- **TTA@R80** — `(τ−t_θ)/fps`를 **고정 recall 0.80**에서. (miss율 제약; FAR는 아래로 별도 제약)
- **FAR-gated mTTA / TTA@FPPH** — 고정 false-positive-per-hour에서의 평균 lead-time.
- **lead-time-vs-FAR 프런티어** — θ/FAR sweep 곡선(스칼라 아님; 핵심 artifact).
- **relative anticipation Δ** — 동일 FAR에서 pose-only 대비 몇 프레임 빠른가.
- **keypoint stability / ID-switch rate** — backbone 비교(no-ReID 대가 측정).
- **spatial(거리 m·속도 m/s) — calibrated 카메라 한정**: homography(측정된 floor plan)+intrinsics, **reprojection RMS 동반**. 무교정이면 무효.

**금지(over-claim):** `mTTA` 단독(ungated) · PoseLift/RetailS/Shopformer를 anticipation prior art로 인용 · staged headline · **무교정 BEV에서 절대 초** · top-1 accuracy · all-frames-positive 라벨.

## 4. 비교 매트릭스

| 비교 | 변인 | 게이트 |
|---|---|---|
| **A. pose-only vs +BEV** | 공간예측 레이어 on/off | **단계적**: 데이터/캘리브 잠금 전 **report-only**, baseline 고정 후 **regression**(§7). 개선 미달은 CI fail 아니라 *실험 결과* |
| B. forecast: CV-Kalman vs +GRU 잔차 | forecast head | Kalman 대비 GRU 개선 없으면 GRU 보류 |
| C. backbone: RTMO vs RTMPose vs (격리)YOLO26 | pose 모델 | 참고용. YOLO26은 `optional-agpl-eval` 프로필에서만 |

## 5. `ablation_result` CSV 스키마

```csv
run_id,timestamp,clip_set,backbone,bev_enabled,forecast,calibrated,metric,value,ci_low,ci_high,notes
```
- `backbone`: `rtmo|rtmpose-m|rtmpose-s|yolo26(quarantined)`
- `bev_enabled`: `true|false`  · `forecast`: `none|kalman|kalman+gru`
- `calibrated`: `true|false` (false면 **공간 metric·절대 초 기록 금지** — relative/temporal만)
- `metric` (현재 M1): `keypoint_stability|id_switch_rate|temporal_auc|temporal_eer|far_at_leadtime|lead_time_s`
- **M2 확장(R1):** `auc_pr_real|tta_at_r80|mtta_far_gated|lead_time_vs_far|rel_anticipation_delta` 추가, 현행 `temporal_auc/far_at_leadtime/lead_time_s`는 deprecated/alias.
- `ci_low/ci_high`: 신뢰구간(부트스트랩). `notes`: pseudo-label 편향·calibrated 등 caveat.

## 6. Replay harness

- 고정 clip set을 결정론적으로 재생(seed 고정) → 파이프라인 통과 → `ablation_result` CSV 누적.
- 동일 입력 = 동일 출력(재현성). CI에서 회귀 감지.
- backbone/bev/forecast/calibrated를 **조합 플래그**로 토글해 위 비교를 한 번에 생성.

## 7. CI 게이트 정의 (단계적 — 실험 설계가 CI 의식이 되지 않도록)

게이트는 **데이터셋·캘리브레이션 잠금 여부**에 따라 단계적으로 강화한다. 데이터가 잠기기 전에 절대 성능 임계로 머지를 막으면 실험 설계가 CI 의식처럼 왜곡되므로 금지한다.

**Phase 1 — report-only (데이터셋/캘리브레이션 잠금 전):**
- 비교 A·AUC-PR·TTA·lead-time-vs-FAR를 **측정·게시만** 하고 머지를 막지 않는다. PR에 곡선·표를 코멘트로 첨부.
- 유일한 hard 게이트는 **재현성**(동일 seed=동일 출력)과 **스키마 유효성**(`ablation_result` CSV)뿐.
- BEV 개선 미달은 CI fail이 아니라 *실험 결과*로 기록.

**Phase 2 — regression gate (real baseline 고정 후):**
- 재라벨된 **real** 데이터 + 평가 프로토콜이 잠기고 baseline이 commit으로 고정되면, 그 baseline 대비 **퇴행**(`auc_pr_real` 임계 하락, `tta_at_r80`(real) 후퇴) 시 fail.
- **real에 gate**(staged 아님). 절대 성능 목표가 아니라 **회귀 방지**가 목적.

**전 단계 공통:**
- 격리 모델(YOLO26)은 기본 CI에서 import/실행되지 않음(프로필 분리 테스트가 강제).
- 모든 결과 리포트에 **metric-3D GT 부재 caveat**·calibrated 여부·**synthetic/staged/real 구분**을 자동 첨부.
- **Threshold 선택(P1 필수):** op θ는 **dev/calibration split**(또는 고정 threshold 파일)에서 고른다. **eval set에서 θ를 sweep 금지**(평가셋 튜닝). P0의 합성 sweep은 자기 set 한정 → plumbing only. `calibrated=true` clip은 `calibration`(homography+reprojection_rms) 블록 필수(validate_manifest 강제), 없으면 공간 metric 금지.

## 8. 산출 artifact (재현·감사용)

- `ablation_result.csv`(누적) · lead-time-vs-FAR plot · `calibration.json`(homography) + reprojection RMS · camera version · validation frames 목록 · **재라벨 앵커(τ/t_θ) 파일** · run manifest(모델 SHA, 코드 commit, seed).
