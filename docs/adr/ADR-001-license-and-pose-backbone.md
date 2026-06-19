# ADR-001 — Repo 라이선스 및 pose backbone 선택

- **상태:** Accepted
- **일자:** 2026-06-19
- **결정자:** 단독 개발자(owner)
- **관련 문서:** [REBUILD_DESIGN](../../REBUILD_DESIGN.md) · [MODEL_CARD](../../MODEL_CARD.md) · [eval-harness](../eval-harness.md)

## 결정 (한 줄)

> `Default: RTMO/RTMPose + Apache-2.0 repo + Apache-compatible model inventory + optional YOLO26 reference eval only`

## 맥락

- 원본 팀 프로젝트(github.com/aix-01/aegis-\*)는 **LICENSE 파일 부재**(= All-Rights-Reserved, 다중 저작자)였고, 사용 모델은 **abliterated Qwen3-VL 기반 팀 org LoRA**로 권리·평판 모두 모호했음.
- 후보 코어 검출/pose 모델인 **Ultralytics YOLO26**은 공식적으로 **AGPL-3.0 또는 Enterprise** 라이선스. 코드/모델/가중치를 결합·수정하거나 네트워크 서비스로 제공하면 (수정본) 소스 공개 의무가 발생하며, 폐쇄형/상용 배포는 Enterprise 라이선스가 필요.
- 이 프로젝트의 목표 우선순위: (1) 정직함=내 코드, (2) **재사용성/라이선스 의식이라는 성숙도 신호**, (3) 솔로 데모 현실성.

## 결정 내용

1. **Repo 라이선스 = Apache-2.0** (MIT 대신). 특허 grant + NOTICE 체계가 ML/CV 프로젝트에 적합하고 MMPose 계열과 정렬됨.
2. **Default pose backbone = RTMO 또는 RTMPose (Apache-2.0).** RTMO는 one-stage로 box+keypoint를 동시 산출하여 YOLO-pose의 *역할*을 대체.
3. **Apache-compatible model inventory.** 사용하는 모든 모델 가중치는 permissive 라이선스로 한정하고 [MODEL_CARD](../../MODEL_CARD.md)에 weight 라이선스·source·핀을 명시.
4. **YOLO26 = optional reference eval only.** 기본 CI/기본 설치/기본 Docker 이미지에 **포함하지 않음**. `optional-agpl-eval` 같은 명시적 프로필로 격리하고, README에 *"not required for normal operation"* 표기. 비교 결과는 참고용일 뿐 코어 의존 아님.

## 근거 (보수적 문구 — 그대로 사용)

- 포트폴리오 신호로서 **"최신 모델을 썼다"보다 "라이선스/재사용성을 의식해 permissive backbone을 고르고 성능은 동일 harness로 검증한다"가 더 성숙**함.
- 원본에서 라이선스 모호로 이미 데인 만큼, permissive로 **모든 옵션(재사용·상업화)을 열어두는 것이 안전**.

## 정직성 제약 (오버클레임 금지)

- **"RTMO가 드롭인"은 금지 문구.** RTMO는 *역할상* 대체 가능하나 **통합비용은 0이 아님** — API·배포·전/후처리·keypoint schema·export 툴체인이 바뀜.
- **RTMO/RTMPose 성능 수치는 2023/2024 논문 기준**(예: RTMO COCO 74.8 AP·V100 141 FPS; RTMPose-m 75.8 AP; RTMPose-s 모바일 70+ FPS). **"2026 SOTA"로 팔지 않음** — "검증된 permissive 실시간 pose baseline"으로만.
- **AGPL 함의(정밀):** "레포 전체가 무조건 AGPL"이 아니라, **AGPL 코드/모델을 결합·수정하거나 네트워크 서비스로 제공하는 순간 (수정본) 소스 공개 의무와 재사용 마찰이 발생하는 리스크**. (AGPL은 네트워크 서버의 수정 버전 소스 제공을 요구하는 성격.)
- 성능 우열은 **주장이 아니라 [eval-harness](../eval-harness.md)로 실측**.

## 고려한 대안

| 대안 | 판정 |
|---|---|
| YOLO26 유지 + 전체 AGPL-3.0 | 기각(기본). 최신·강력하나 copyleft 영구 고착·재사용 마찰. 참고 eval로만 격리 |
| RF-DETR (Apache-2.0) | 보류. 좋은 permissive **detection** 후보지만 pose backbone 논거의 중심 아님. "필요 시 object detector"로만(2026-06-16 keypoint release 있으나 core 논거로 끌지 않음) |
| ViTPose++ / Sapiens | 보류. 고정밀이나 무겁고 **weight 라이선스 개별 확인 필요**(Sapiens=Meta, 상업 제약 가능) |

## 결과 (Consequences)

- (+) repo가 permissive로 유지 → 재사용/상업화 옵션 전부 열림, 라이선스 마찰 제거.
- (+) 라이선스 의식 자체가 포트폴리오 성숙도 신호.
- (−) MMPose 생태계 통합 비용(API/배포/툴체인) 추가 — 0 아님.
- (−) YOLO26 대비 성능 동등성은 **보장 불가** → 동일 eval harness로 측정·문서화 필요.

## 참고 (2026-06, 날짜 앵커)

- [Ultralytics License (AGPL/Enterprise)](https://www.ultralytics.com/license) · [Ultralytics Pricing](https://www.ultralytics.com/pricing) · [YOLO26 docs](https://docs.ultralytics.com/models/yolo26)
- [RTMPose (Apache-2.0)](https://github.com/open-mmlab/mmpose/blob/main/projects/rtmpose/README.md) · [RTMO (CVPR'24)](https://openaccess.thecvf.com/content/CVPR2024/papers/Lu_RTMO_Towards_High-Performance_One-Stage_Real-Time_Multi-Person_Pose_Estimation_CVPR_2024_paper.pdf) · [RTMPose 논문](https://arxiv.org/abs/2303.07399)
- [RF-DETR (Apache-2.0)](https://github.com/roboflow/rf-detr)
- [AGPL-3.0 (OSI)](https://opensource.org/license/agpl-3-0) · [AGPL 함의(Snyk)](https://snyk.io/articles/agpl-license/)
