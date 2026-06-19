# Eval Harness — 검증 게이트 명세

> 원칙: **성능 우열은 주장이 아니라 측정한다.** 차별화(공간지능 예측)의 정당성은 ablation이 증명한다.
> 1주차(첫) 산출물: `replay harness` + 아래 `ablation CSV schema`. 차별화 코드보다 **먼저** 만든다.
> 관련: [REBUILD_DESIGN](../REBUILD_DESIGN.md) · [ADR-001](adr/ADR-001-license-and-pose-backbone.md) · [MODEL_CARD](../MODEL_CARD.md)

## 1. 목적

- **차별화 ablation(핵심):** `pose-only` 베이스라인 대비 `+BEV(공간예측)`가 **lead-time-vs-FAR 곡선을 측정 가능하게** 개선하는가? 개선 못 하면 BEV 레이어는 장식 → 조기 폐기/단순화.
- **backbone 비교(참고):** 동일 clip set에서 RTMO/RTMPose vs (격리)YOLO26의 keypoint stability·ID-switch·temporal AUC를 측정. **"이긴다"가 아니라 "동일 harness로 측정"**.

## 2. 평가 데이터셋

| 데이터 | 용도 | 한계(정직) |
|---|---|---|
| **PoseLift** | temporal scorer 학습/평가, 절도 구간 라벨 | **2D pose만** — 독립 metric-3D GT 없음 |
| **호모그래피 알려진 clip(소수)** | BEV held-out 검증 | 소수라 평가셋 신뢰 한계 |
| **실제 CCTV 절도 clip(미확보)** | 최종 검증 | **owner 결정 #1** — 없으면 forecast는 "자기일관성 + ablation"까지만 주장 |

> **정직성 경고:** metric-3D GT 부재 → BEV pseudo-label은 self-consistency만 점검 가능. 보고되는 lead-time은 pseudo-label 낙관 편향을 동반함을 결과에 항상 표기.

## 3. 지표

- **keypoint stability** — 프레임 간 keypoint jitter/누락률(backbone 비교).
- **ID-switch rate** — track 당 ID 전환 횟수(no-ReID 대가 측정; 궤적 오염 원인).
- **temporal scorer AUC / EER** — pose 시퀀스 이상탐지 성능.
- **lead-time-vs-FAR 곡선(핵심)** — 일찍 경고할수록 FAR↑. `+BEV`가 곡선을 위로 미는지.
- **(참고) anticipation lead-time** — 사건완료 anchor 대비 평균 선행시간(교정 clip 한정, 신뢰구간 동반).

## 4. 비교 매트릭스

| 비교 | 변인 | 게이트 |
|---|---|---|
| **A. pose-only vs +BEV** | 공간예측 레이어 on/off | **단계적 게이트**: 데이터셋/캘리브레이션 잠금 전엔 **report-only**, baseline 고정 후 **regression gate**(§7). 개선 미달은 CI fail이 아니라 *실험 결과*로 기록 → BEV 단순화/폐기 판단 근거 |
| B. forecast: CV-Kalman vs +GRU 잔차 | forecast head | Kalman 대비 GRU 개선 없으면 GRU 보류 |
| C. backbone: RTMO vs RTMPose vs (격리)YOLO26 | pose 모델 | 참고용. YOLO26은 `optional-agpl-eval` 프로필에서만 |

## 5. `ablation_result` CSV 스키마

```csv
run_id,timestamp,clip_set,backbone,bev_enabled,forecast,calibrated,metric,value,ci_low,ci_high,notes
```
- `backbone`: `rtmo|rtmpose-m|rtmpose-s|yolo26(quarantined)`
- `bev_enabled`: `true|false`  · `forecast`: `none|kalman|kalman+gru`
- `calibrated`: `true|false` (false면 ETA 숫자 metric은 기록 금지 — 정성 등급만)
- `metric`: `keypoint_stability|id_switch_rate|temporal_auc|temporal_eer|far_at_leadtime|lead_time_s`
- `ci_low/ci_high`: 신뢰구간(부트스트랩). `notes`: pseudo-label 편향 등 caveat.

## 6. Replay harness

- 고정 clip set을 결정론적으로 재생(seed 고정) → 파이프라인 통과 → `ablation_result` CSV 누적.
- 동일 입력 = 동일 출력(재현성). CI에서 회귀 감지.
- backbone/bev/forecast/calibrated를 **조합 플래그**로 토글해 위 비교를 한 번에 생성.

## 7. CI 게이트 정의 (단계적 — 실험 설계가 CI 의식이 되지 않도록)

게이트는 **데이터셋·캘리브레이션 잠금 여부**에 따라 단계적으로 강화한다. 데이터가 잠기기 전에 절대 성능 임계로 머지를 막으면 실험 설계가 CI 의식처럼 왜곡되므로 금지한다.

**Phase 1 — report-only (데이터셋/캘리브레이션 잠금 전):**
- 비교 A(pose-only vs +BEV)·temporal_auc·lead-time-vs-FAR를 **측정·게시만** 하고 머지를 막지 않는다. PR에 곡선·표를 코멘트로 첨부.
- 유일한 hard 게이트는 **재현성**(동일 seed=동일 출력)과 **스키마 유효성**(`ablation_result` CSV)뿐.
- BEV 개선 미달은 CI fail이 아니라 *실험 결과*로 기록 → BEV 단순화/폐기 판단 근거.

**Phase 2 — regression gate (baseline 고정 후):**
- 데이터셋·캘리브레이션·평가 프로토콜이 잠기고 baseline이 commit으로 고정되면, 그 baseline 대비 **퇴행**(temporal_auc 임계 하락, far_at_leadtime 곡선 후퇴) 시 fail.
- 절대 성능 목표가 아니라 **회귀 방지**가 목적.

**전 단계 공통:**
- 격리 모델(YOLO26)은 기본 CI에서 import/실행되지 않음(프로필 분리 테스트가 강제).
- 모든 결과 리포트에 **metric-3D GT 부재 caveat**와 calibrated 여부를 자동 첨부.

## 8. 산출 artifact (재현·감사용)

- `ablation_result.csv`(누적) · lead-time-vs-FAR plot · `calibration.json`(homography) + reprojection RMS · camera version · validation frames 목록 · run manifest(모델 SHA, 코드 commit, seed).
