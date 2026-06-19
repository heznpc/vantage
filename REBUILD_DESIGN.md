# Rebuild Design — 공간지능 기반 예측형 CCTV 이상탐지 시스템

> 상태: 설계 확정(2026-06-19) · 빌드 착수 전 · 솔로 개발 포트폴리오
> 동반 문서: [ADR-001 라이선스·pose backbone](docs/adr/ADR-001-license-and-pose-backbone.md) · [MODEL_CARD](MODEL_CARD.md) · [eval-harness](docs/eval-harness.md)

## 0. 출처·정직성 (먼저 읽을 것)

- 이 프로젝트는 해체된 팀이 만든 CCTV 절도/이상행동 탐지 제품의 **컨셉을 단독 개발자가 그린필드로 재구축**한 것입니다.
- 원본 레포(github.com/aix-01/aegis-\*)는 다중 저작자 **All-Rights-Reserved**이므로 **코드는 한 줄도 복사하지 않습니다**. 가져오는 것은 *문제 정의*뿐입니다.
- 원본의 중심 메커니즘은 **VLM-as-core**(데이터셋 단계의 VL 모델 파인튜닝 + 에이전트의 VLM 의존, 정확도 낮음)였습니다. 이 재구축의 논지는 그것을 **계승이 아니라 폐기**하고 인식(perception) 코어를 중심에 두는 *반전(inversion)* 입니다.
- 금지 표현(코드·UI·문서·커밋): **"world model"**, **"metric 3D"**(교정 전), **무교정 상태의 초 단위 ETA**. 정직한 명칭은 **"calibrated single-camera BEV risk forecasting with lead-time/FAR ablation"** 입니다.

## 1. 스코프 판정 — 축소 GO

코어 + **단 하나의** 깊은 차별화 + 검증 가능한 ablation = 솔로가 신뢰 가능한 데모로 만들 유일한 정직한 경로. 나머지는 데모 깊이 또는 스텁/설계로 강등.

| 항목 | 처리 | 이유 |
|---|---|---|
| 실시간 엣지(Jetson Orin 등) | **CUT → 설계 문서만** | Orin 동시추론 실시간성 미입증, 데모 가치 0 |
| 멀티캠 융합(BEV-SUSHI/ModTrack) | **DEFER → 스텁/설계** | 카메라별 교정 + association이 필요한 *별개의 더 어려운 시스템* |
| 내구성 에이전트(interrupt/resume, durable checkpointer) | **DEFER → thin slice** | 결정론 정책 + `pending_action` + WS 승인이면 데모 충분 |
| PDF 리포트 / 멀티 트랜스포트 fallback | **DEFER** | 화면 내 타임라인·단일 WS로 데모 충분 |
| 벡터DB(pgvector) | **CUT** | 코어에 임베딩 경로 없음(원본 VLM-RAG 잔재) |
| mTLS 서비스 메시 | **DEFER → JWT scope** | svc-to-svc 신원 발급/회전은 솔로 비용 과다(설계로 명시) |

## 2. 한 줄 설계 + 원칙

> 인식(RTMO/RTMPose + ByteTrack + temporal scorer)은 항상 켜진 워크호스 · 공간지능 예측(2D→**pseudo-metric** BEV + 궤적 rollout)은 단 하나의 깊은 차별화 · 에이전트 SW 액션은 HITL 게이트 · VLM은 꺼도 완주하는 add-on.

1. **차별화는 직교 레이어.** 코어(검출→추적→pose 이상점수)는 depth/BEV/VLM 없이 완결되는 MVP 바닥선이며, 그 위에 BEV 예측을 직교 추가한다.
2. **계약은 단일 진실원천(SSOT).** OpenAPI 3.1 + AsyncAPI 3.0 한 벌에서 codegen, CI diff 게이트. (원본의 `userEmail`/`userMail` 무음 드롭 = 손작성 DTO 표류가 원인.)
3. **배포물은 암호학적으로 확정.** 모든 이미지·모델 가중치는 sha256 digest + 서명으로만 참조.

## 3. 권장 풀스택 스택 (2026-06 검증 버전)

| 레이어 | 선택 | 비고 |
|---|---|---|
| **Repo License** | **Apache-2.0** | 특허 grant + NOTICE, MMPose 계열과 정렬 |
| **Perception (코어)** | **RTMO 또는 RTMPose (Apache-2.0)** + ByteTrack(motion-only, no-ReID) + ST-GCN+TCN temporal scorer | RTMO = one-stage box+keypoint(YOLO-pose 역할). export: ONNX/TensorRT/ncnn/RKNN |
| **Spatial (차별화)** | **homography 1순위** + Depth Anything 3(보조) + BEV 리프팅(0.1m 그리드) + forecast(CV-Kalman 먼저, GRU 잔차 나중) | DA3 weight 라이선스는 채택 전 확인(MODEL_CARD) |
| **Frontend** | Next.js 16 + React 19 + TS strict + **ESLint CLI(Flat config)** + PixiJS v8(BEV 렌더) | `next lint`은 Next 16에서 제거됨 |
| **Backend** | Spring Boot **4.1.0** / Java 21(virtual threads) | 3.5.x는 2026-06-30 EOL → 4.1.0 채택 |
| **Agent** | Python 3.12 / **정책테이블 + `pending_action` + audit log 먼저**; LangGraph는 설명/리포트 orchestration wrapper로만 | |
| **Optional VLM** | OpenAI 호환(vLLM) 뒤 소형 VL(Gemma 4 E4B / Qwen3-VL-4B, Apache-2.0), feature-flag + cost-gate | OFF면 결정론 템플릿 문자열(빈 값 아님) |
| **Datastores** | PostgreSQL **18**(관계형 전용) + Redis Streams(consumer group + XACK + DLQ) | 19는 beta(2026-06-04)라 운영 제외 |
| **Infra/CI** | 단일 canonical Terraform + branch-scoped OIDC(plan/apply 분리) + cosign digest verify + OPA conftest + gitleaks/trufflehog | |

> 라이선스·모델 결정의 전체 근거는 [ADR-001](docs/adr/ADR-001-license-and-pose-backbone.md), 모델 weight 핀은 [MODEL_CARD](MODEL_CARD.md).

## 4. 컴포넌트 + End-to-End 데이터 흐름

```
[녹화 클립 / (스트레치) RTSP]
   │ video-ingest
   ▼
[RTMO (또는 RTMPose+검출)] ── frame → [(person_box, keypoints, conf)]
   ▼
[ByteTrack] ── {track_id: (box, keypoints, ts)}   ※ ID-switch 시 궤적 버퍼 무효화
   ├──▶ [ST-GCN+TCN temporal scorer] → anomaly_score
   │        (★ 여기까지가 depth/VLM 없이 완결되는 코어 = MVP 바닥선 = ablation 베이스라인)
   ▼ (cheap-gate)
[homography BEV-lift (1순위) + DA3 depth(보조)] ── ankle keypoints → BEV (x_m, z_m) + zone_id
   ▼
[trajectory-store] ── per-track BEV ring buffer + 속도/가속도  ※ ID-switch 가드
   ▼
[forecast: CV-Kalman(항상) + GRU 잔차(나중)] ── 미래 K스텝 + zone-arrival ETA
   ▼
[anticipation-fuser] ── anomaly × (zone-ETA + 은닉/배회) → pre-theft risk + lead_time_s
   ▼
[AgentLoop] 가역·저비용(spotlight/voice/notify)=즉시 자율 / 비가역(dispatch)=HITL 승인(pending_action+WS)
   ▼ [옵션 VLM 설명; OFF면 템플릿]
[인시던트 뷰] 타임라인 + BEV 궤적 + (DEFER:PDF)
   ▼
[Frontend] BevCanvas + TrajectoryLayer + AlertConsole + HitlApprovalPanel
```

## 5. 차별화 — 공간지능 기반 예측형 (정직한 한계 포함)

- 2D CCTV를 **pseudo-metric BEV로 리프팅** 후 **궤적을 rollout**해 절도 완료 전 경고. **학습된 world model이 아니라 off-the-shelf 조립.**
- **homography 중심, DA3는 보조.** artifact 필수: `calibration.json`, floor polygon, reprojection RMS, camera version, validation frames.
- **CV-Kalman 먼저.** pose-only 대비 `+BEV`의 lead-time-vs-FAR 곡선이 측정 가능하게 개선되지 않으면 GRU는 장식 → 나중.
- **무교정 시 초 단위 ETA 비노출**(정성 등급 + confidence band만). 교정된 카메라에서만 ETA 숫자를 신뢰구간과 함께.
- **데이터 한계(최상위 리스크):** 독립 metric-3D GT 부재(PoseLift는 2D pose only). 교정된 실제 절도 영상이 없으면 forecast는 **자기일관성 + ablation**까지만 정직하게 주장. 상세는 [eval-harness](docs/eval-harness.md).

## 6. 감사 결함 → 구조적 예방

| 결함 | 구조적 예방 |
|---|---|
| H1 테스트 ~0 | bev-lift/forecast/fuser를 **순수 함수** → pytest 골든 픽스처. 전 레포 commit #1부터 required check. **eval-harness 재현성·스키마가 머지 게이트**(성능은 단계적: report-only→regression, [eval-harness](docs/eval-harness.md) §7) |
| H2 계약 표류 | OpenAPI/AsyncAPI **SSOT codegen + CI diff 게이트** + schemathesis. WS 채널 codegen은 M0에서 실증 |
| H3 /internal 무인증 | permitAll 삭제 + JWT scope(데모) / mTLS는 설계 명시 |
| H4 OIDC Admin | AdministratorAccess 폐기 + ARN 한정 + branch-scoped sub + plan/apply 분리 |
| H5 :latest·락파일 | immutable digest + cosign verify + 전 언어 hash-pinned lockfile + 모델 sha256 |
| H6 datastore 노출 | private subnet + TLS + AUTH 토큰, SG 0.0.0.0/0 conftest 금지, 원본 프레임 비저장 |
| H7 토폴로지·docs 표류 | 단일 canonical Terraform root, README는 생성·CI 대조, trunk-based |
| 시크릿 위생 | Secrets Manager만, 평문 git 0건, gitleaks/trufflehog(pre-commit+CI+주기) |
| 솔로 bus-factor | CODEOWNERS + conventional commits + ADR. ("CI green+cool-off"는 2-eyes 아님을 ADR 명시) |

## 7. 빌드 로드맵 (솔로, 리뷰 반영 재컷 — eval/contracts 우선)

| 주차 | 산출물 |
|---|---|
| **1주차** | `contracts(OpenAPI/AsyncAPI SSOT + codegen + CI diff)` · `replay harness` · `ablation CSV schema` · 정직한 README/negative-result caveat |
| **2–4주** | RTMO/RTMPose + ByteTrack + ST-GCN+TCN baseline → **pose-only 첫 곡선(ablation, report-only)** |
| **5–7주** | homography BEV-lift + CV-Kalman forecast → `+BEV` 곡선 비교 |
| **8–9주** | BEV incident UI(BevCanvas + TrajectoryLayer + WS) |
| **10–11주** | HITL action thin slice(pending_action + 승인/거부 + audit log) |
| **12–14주** | hardening · docs · demo script · negative-result caveat 잠금 |
| **스트레치** | 옵션 VLM 설명 · 멀티캠 · GRU 잔차 · 클라우드 프로덕션 토폴로지 · 엣지 |

## 8. 리스크 / 미해결 결정

1. **(최상위) 데이터 획득** — 교정된 실제 절도 영상(또는 합의된 metric GT 대체)이 없으면 forecast는 "자기일관성 + ablation"까지만. 차별화 신뢰도를 결정.
2. **DA3 등 모델 weight 라이선스 개별 확인** — MODEL_CARD에 핀.
3. **캘리브레이션 일반화 투자** — 데모 1대 hand-tune 유지 권장, 다수 카메라 일반화는 비범위.
4. **실시간 worst-case 예산** — M3(5–7주)에서 단계별 지연·동시 VRAM 실측해 갱신.
5. **repo 이름/공개 시점** — 미정(이 문서는 `rebuild/`에 임시 저장).
6. **클립/증거 보존 정책** — 원본 프레임 비저장 원칙 vs 인시던트 증거 보존.

## 9. 검증된 기술 근거 (2026-06, 날짜 앵커)

- RTMPose/RTMO: Apache-2.0, 실시간 multi-person pose (논문 2023/2024 기준 — "검증된 permissive baseline"이지 "2026 SOTA" 아님). [RTMPose](https://github.com/open-mmlab/mmpose/blob/main/projects/rtmpose/README.md) · [RTMO CVPR'24](https://openaccess.thecvf.com/content/CVPR2024/papers/Lu_RTMO_Towards_High-Performance_One-Stage_Real-Time_Multi-Person_Pose_Estimation_CVPR_2024_paper.pdf)
- Depth Anything 3 / DA3-Streaming (2025-12): 단안 metric depth 보조. [repo](https://github.com/ByteDance-Seed/Depth-Anything-3)
- Spring Boot 4.1.0 GA (2026-06-10), 3.5.x EOL 2026-06-30. [spring.io](https://spring.io/blog/2026/06/10/spring-boot-4/)
- PostgreSQL 18.4/17.10/16.14 (2026-06), 19 beta(2026-06-04). [release](https://www.postgresql.org/about/news/postgresql-184-1710-1614-1518-and-1423-released-3297/)
- Next.js 16: `next lint` 제거 → ESLint CLI. [upgrade](https://nextjs.org/docs/app/guides/upgrading/version-16)
- Ultralytics YOLO26 = AGPL-3.0/Enterprise(기본 제외). [license](https://www.ultralytics.com/license)
