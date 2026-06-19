# MODEL CARD — 모델 인벤토리 및 weight 라이선스 핀

> 원칙: **code 라이선스 ≠ weight 라이선스.** 실제 사용하는 모든 checkpoint의 weight 라이선스·source URL·핀(버전/commit/SHA)을 채택 전 확인해 여기 박는다.
> 상태 범례: ✅확인됨 · ⏳채택 전 확인 필요 · 🚫기본 제외(격리)
> 관련: [ADR-001](docs/adr/ADR-001-license-and-pose-backbone.md) · [REBUILD_DESIGN](REBUILD_DESIGN.md)

## 기본 인벤토리 (Apache-compatible only)

| 모델 | 역할 | code 라이선스 | weight 라이선스 | source URL | 핀(버전/SHA) | 상태 |
|---|---|---|---|---|---|---|
| **RTMO** (MMPose) | 코어 one-stage pose(box+keypoint) | Apache-2.0 | ⏳ checkpoint별 확인 | https://github.com/open-mmlab/mmpose/tree/main/projects/rtmo | _채택 시 기입_ | ⏳ |
| **RTMPose-m/s** (MMPose) | 코어 top-down pose(대안/엣지) | Apache-2.0 | ⏳ checkpoint별 확인 | https://github.com/open-mmlab/mmpose/tree/main/projects/rtmpose | _채택 시 기입_ | ⏳ |
| **ByteTrack** | 다중객체 추적(motion-only, no-ReID) | MIT | n/a(가중치 없음) | https://github.com/FoundationVision/ByteTrack | _채택 시 기입_ | ✅ |
| **ST-GCN+TCN temporal scorer** | pose 시퀀스 이상점수(코어) | **자작(Apache-2.0)** | **자작(PoseLift 학습)** | (this repo) | n/a | ✅ |
| **Depth Anything 3 / DA3Metric** | 단안 metric depth(BEV 보조) | ⏳ 확인 | ⏳ **확인 필수**(ByteDance) | https://github.com/ByteDance-Seed/Depth-Anything-3 | _채택 시 기입_ | ⏳ |
| **UniDepthV2** | intrinsic 미상 depth 폴백 | ⏳ 확인 | ⏳ 확인 | (공식 repo) | _채택 시 기입_ | ⏳ |

## 옵션 레이어 (feature-flag, 기본 OFF)

| 모델 | 역할 | weight 라이선스 | source / LICENSE | 핀(commit/SHA) | 상태 |
|---|---|---|---|---|---|
| **Gemma 4 E4B** | 설명가능 알림(옵션 VLM) | **Apache-2.0 ✅** (공식 model card, 2026-06-10 업데이트) | model card: https://ai.google.dev/gemma/docs/core/model_card_4 · HF: google/gemma-4-e4b | _채택 시 commit 핀_ | ✅ 라이선스 확인 / ⏳ 핀 |
| **Qwen3-VL-4B** | 설명가능 알림(대안 VLM) | ⏳ **미확정** — HF Apache 필터엔 잡히나, **모델 페이지 LICENSE 파일 URL + commit을 핀한 뒤 확정** | HF: Qwen/Qwen3-VL-4B (모델 페이지 LICENSE 확인 필요) | _LICENSE URL + commit 핀_ | ⏳ 확정 전 |

## 격리(기본 제외 — `optional-agpl-eval` 프로필 전용)

| 모델 | 역할 | 라이선스 | 비고 | 상태 |
|---|---|---|---|---|
| **Ultralytics YOLO26-pose** | 참고 비교 eval만 | **AGPL-3.0 / Enterprise** | 기본 CI/설치/Docker **제외**. README "not required for normal operation". 결과는 참고용 | 🚫 |

## 검증 체크리스트 (각 모델 채택 전 필수)

- [ ] weight 라이선스 원문 확인(code와 별개) → 표에 명시
- [ ] source URL + 버전/commit/파일 SHA256 핀
- [ ] permissive 비호환이면 채택 보류 → ADR-001에 배제 기록
- [ ] 가중치 다운로드를 빌드에 고정(digest 검증), 재현 가능하게
- [ ] 옵션/격리 모델은 기본 경로에서 import되지 않음(프로필 분리) 테스트

## 메모

- DA3 weight 라이선스가 permissive 비호환으로 밝혀지면, depth 보조 신호는 **다른 permissive depth 모델로 대체하거나 homography-only로 운용**(차별화는 homography 중심이므로 degrade 허용).
- 모든 "성능" 주장은 [eval-harness](docs/eval-harness.md)의 동일 harness 측정으로만 뒷받침.
