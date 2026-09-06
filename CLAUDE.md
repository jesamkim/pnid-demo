# CLAUDE.md — agent guidance for this repo

이 파일은 Claude Code (또는 다른 AI agent)가 이 저장소에서 작업할 때
지켜야 하는 컨텍스트와 룰을 한곳에 모은 문서입니다. **모든 코드 변경
전 이 문서를 먼저 읽으세요.**

## 프로젝트 한 줄 정의

P&ID 도면 → 데이터 변환 데모. **AWS Bedrock AgentCore 위에서
Strands SDK로 짠 4개 Runtime + Sonnet 4.6 sub-agents** 가 협업해
정확도 ~0.88 macro_F1 (실측, 라이브 Bedrock 호출, baseline 대비
+5.7%p). 발표 자료는 [`PRESENTATION.md`](PRESENTATION.md), 사용자
가이드는 [`README.md`](README.md), ralph-loop 자율 개선 spec은
[`RALPH-TASK.md`](RALPH-TASK.md).

## 절대 룰 (위반 = revert)

### 1. Anti-cheating — GT 누설 절대 금지
- `data/ground_truth/*.json`은 **production 코드(`backend/`)에서
  open 금지**. 평가 스크립트(`scripts/eval_*`, `tests/`,
  `benchmark/`)에서만 읽음.
- 도면-id-conditional branch 금지: `if drawing_id == "00":` 류 패턴
  (production 코드에서) 자동 fail.
- GT tag literal (`'V-101'`, `'PSV-101'`, `'8"-CRD-101-CS'` 등) 을
  production 코드의 함수 return / list / dict value 로 hardcode 금지.
  docstring/comment의 example은 OK.
- 모든 코드 변경 후 `python3 scripts/check_no_gt_leak.py` 실행.
  `OK — no GT leak across N files`가 안 나오면 commit 금지.

### 2. 보안 (Job Zero)
- ALB ingress = ONLY `pl-3b927c52` (CloudFront prefix list, dynamic
  lookup). `add_listener(open=False)` 명시. **0.0.0.0/0 절대 금지**
  (보안 스캐너가 자동 감지해 리스너를 회수함).
- ECS Fargate · private subnet · `assign_public_ip=DISABLED`
- Bedrock 호출은 항상 VPC endpoint 경유 (`com.amazonaws.us-east-1.bedrock-runtime`)

### 3. Git 커밋 규칙
- AI attribution 절대 포함 안 함 ("Generated with Claude Code", "Co-Authored-By: Claude")
- 코드/주석/문서에 emoji 사용 금지 (사용자가 명시 요청 시만)
- AWS_PROFILE / account / region은 배포하는 사람의 환경에 맞춰 지정 (기본 리전 us-east-1)

### 4. Customer data 사용 금지
- 외부 고객 PDF/도면을 본 데모에 직접 사용 금지.
- 합성 데이터(`data/samples/`) 또는 public-domain 자료
  (`data/samples_real/` — NREL only, 17 U.S.C. § 105) 만 OK.
- 실 도면 시연이 필요하면 사용자가 자신의 PDF를 UI에서 업로드 (서버
  영구 저장 안 함, TTL 30분).

## 디렉터리별 책임

| 디렉터리 | 무엇이 들어있나 | 변경 시 주의 |
|---------|----------------|-------------|
| `backend/agents/` | Strands agents (extractor, ocr, fusion, evaluator, self-correction, summary, line-verifier) | GT 누설 체크. anti-cheat 가드 통과 의무 |
| `backend/api/` | FastAPI + WebSocket. /api/extract, /api/query, /api/summary, /api/uploads, /api/index_run | image_normalize를 통해 PNG 단일화. dpi 변경 시 viewer-agent 좌표 정합 영향. uvicorn `--workers 1` 의무 (in-process SearchIndex 공유) |
| `backend/agents/strands_ocr.py` + `bda_ocr.py` | OCR 라우터. `OCR_BACKEND` env 로 textract↔bda 토글 | TextBlock dataclass `{text, confidence, bbox}` 동일 contract. fusion/refinement 코드는 수정 안 함 |
| `backend/tools/image_normalize.py` | 모든 입력 → 단일 PNG (≤7800px cap, mtime cache) | 7800 cap은 Bedrock Vision max=8000 대응. 변경 금지 |
| `backend/agents/runtime_*.py` | AgentCore Runtime entrypoint (vision/ocr/fusion/summary) | 변경 시 `scripts/runtime_deploy.py` 재실행 필요 (4 Runtime 모두 redeploy) |
| `backend/agents/strands_orchestrator.py` | 7-stage pipeline (render → OCR → Vision → refine → zoom → fusion → evaluate → self-correct → verifier → memory) | 단계 추가 시 step banner 라벨도 업데이트 (`PnidStepBanner.tsx`) |
| `frontend/src/components/organisms/PnidViewer.tsx` | 도면 viewer — zoom/pan, banner, overlay | `key={selectedKey}` 강제 재마운트 패턴 유지 (도면 전환 시 stale state 방지) |
| `frontend/src/components/organisms/PnidStepBanner.tsx` | Step 1~7 banner. 사용자 클릭 dismiss + `done` 후 자동 hide | `view!` non-null assertion 금지 (예전 React unmount 사고 원인) |
| `frontend/src/styles/tokens.css` | Cinematic Tech 디자인 토큰 (cyan + bloom + AWS orange 1회) | `--accent` (#00d4ff) 변경 시 모든 viewer/banner/halo 영향 |
| `infra/cdk/app/app_stack.py` | ECS + ALB + CloudFront. AgentCore Runtime ARN env wiring | ALB add_listener `open=False` 절대 변경 금지 |
| `data/synthesis/` | 합성 P&ID topology specs + auto_layout (grid + A* networkx) | 변경 후 `scripts/build_drawings.py` 재실행. ground-truth JSON도 같이 갱신 |
| `scripts/eval_live_extraction.py` | ⭐ 라이브 정확도 측정 (P/R/F1) | 도면별 결과 + `OVERALL macro_f1=X.YYYY` 출력 |
| `scripts/check_no_gt_leak.py` | ⭐ anti-cheat 가드 | 모든 ralph-loop iter 전후 의무 |
| `tests/backend/` | pytest 106 (api, image_normalize, harness_adapter 등) | unit + integration |
| `.claude/artifacts/eval/ralph-history.jsonl` | ralph-loop 자율 진화 이력 (23 iter) | 발표 자료 출처 |

## OCR 백엔드 swap + rollback

| 동작 | 명령 |
|------|------|
| Textract (default) | `aws ecs update-service ... --task-definition PnidDemoAppTaskDefA9614226:23` |
| BDA 토글 | `aws ecs update-service ... --task-definition PnidDemoAppTaskDefA9614226:24` |
| Convention auto-detect (v30, current) | `aws ecs update-service ... --task-definition PnidDemoAppTaskDefA9614226:26` |
| 즉시 rollback (v27/textract) | `bash scripts/rollback_to_textract.sh` (3분 내 복구) |

## P&ID Convention (v30+)

| 환경변수 | 동작 |
|----------|------|
| `PNID_CONVENTION=auto` (default) | OCR 결과로 ISA/DIN 자동 판별 |
| `PNID_CONVENTION=isa` | ISA-5.1 강제 (v27 이전 동작과 동일) |
| `PNID_CONVENTION=din` | DIN EN 10628 강제 |

지원 도면:
- 합성 (00/01/01b): ISA-5.1 (영어, V-/P-/PSV- prefix, `<size>"-<SVC>-<NUM>-<SPEC>`)
- 사전 탑재 실 도면 (uer-1234567): DIN EN 10628 + DIN 19227 (독일어, KA/BA/WA/PA prefix, `LR<...>.<...>-<...>-<...>` 라인)
- 사용자 업로드: convention auto-detect

stable checkpoint: `.claude/artifacts/rollback/STABLE_v27.md`. BDA 자원
정보 (project ARN, S3 버킷, IAM 변경사항): `.claude/artifacts/rollback/BDA_RESOURCES.md`.

## 자주 쓰는 명령

```bash
# 백엔드 + 프론트 로컬 개발
uvicorn backend.api.main:app --host 127.0.0.1 --port 8000
cd frontend && VITE_PROXY_TARGET=http://127.0.0.1:8000 npm run dev

# pytest 회귀 (단위 + 통합, Bedrock 호출 없음)
python3 -m pytest tests/backend/

# anti-cheat 가드
python3 scripts/check_no_gt_leak.py

# 라이브 정확도 측정 (Bedrock 호출 발생)
AWS_PROFILE=profile2 python3 scripts/eval_live_extraction.py

# 합성 도면 재생성
AWS_PROFILE=profile2 python3 scripts/build_drawings.py

# AgentCore Runtimes 4개 재배포
AWS_PROFILE=profile2 python3 scripts/runtime_deploy.py

# Docker build + push (linux/amd64)
docker buildx build --platform linux/amd64 \
  -f infra/docker/Dockerfile \
  -t <ACCOUNT_ID>.dkr.ecr.us-east-1.amazonaws.com/pnid-demo:vN \
  --push .

# CDK deploy (ARN 환경변수 전달)
cd infra/cdk && AWS_PROFILE=profile2 IMAGE_TAG=vN PNID_DEMO_VPC_ID=vpc-... \
  AGENTCORE_VISION_ARN=... AGENTCORE_OCR_ARN=... \
  AGENTCORE_FUSION_ARN=... AGENTCORE_SUMMARY_ARN=... \
  BEDROCK_AGENTCORE_MEMORY_ID=pnid_demo_memory-X3yThLB8sc \
  npx cdk deploy PnidDemoApp

# CloudFront invalidate
AWS_PROFILE=profile2 aws cloudfront create-invalidation \
  --distribution-id E1SRSKOUV081XL --paths '/*'
```

## 모델 ID (절대 변경 금지 — 메모리 룰 참조)

| 용도 | Model ID | 비고 |
|------|---------|------|
| Vision (Opus 4.8, 1M context) | `global.anthropic.claude-opus-4-8` | -v1 없음! |
| Critic / NL Query / Summary / Verifier | `global.anthropic.claude-sonnet-4-6` | -v1 없음, max_tokens 65536 지원 |
| Embedding | `us.cohere.embed-v4:0` | inference profile 필수 |

`config/settings.yaml` 의 `max_tokens_default: 32768` 도 변경 금지
(00 도면 같은 큰 도면이 8k에서 truncate되어 Strands MaxTokensReachedException
일으킴).

## ralph-loop 사용 시

`RALPH-TASK.md` 참조 — 종료 조건, 허용 lever, 금지 패턴 모두 명시.
핵심:

- 각 iter 시작 시 `python3 scripts/check_no_gt_leak.py` 의무
- 변경 가능 영역: extractor system prompt / tile params /
  self-correction trigger / OCR threshold / verifier sub-agent /
  config max_tokens
- 금지: 도면-id-conditional branch / GT tag literal / GT 파일 read
- 종료: macro_F1 ≥ 0.98 OR iter ≥ 30
- 0.98은 01b occluded line label 때문에 본 데이터셋에선 unreachable.
  실 도면(가림 없음)에선 도달 가능.

이력: `.claude/artifacts/eval/ralph-history.jsonl` (23 iter,
plateau ~0.88, +5.7%p 자율 향상).

## 알려진 함정 / 회귀 사고

1. **PnidStepBanner의 `view!` non-null assertion** — 도면 전환 시 한 프레임 동안
   `view`가 null인데 `done=true && showFinal=true` 조합에서 우변 unwrap 시도 →
   React 전체 unmount → 검은 화면. **반드시 `view ?? null` + `if (!banner) return null`**.
2. **ECR `:v6` 태그 retag race** — 같은 태그를 여러 build에 reuse하면 ECS task
   pull 시점 cache 불일치. **명시적 `v17`/`v18` 태그 + `IMAGE_TAG=vN` env**.
3. **`runtimeSessionId` 길이 33+ 의무** (AgentCore Runtime). UUID 사용.
4. **Connection schema는 `type` + `via_line`**, NOT `kind`. tile fan-in dedup 시.
5. **Cognito callback URL placeholder** (example.invalid) — CDK 첫 deploy 후
   실제 CloudFront URL로 update 필요 (cognito-idp update-user-pool-client).
6. **Image > 8000px** Bedrock Vision 거부 — `image_normalize` cap 7800.

## 변경하면 안 되는 부분 (테스트 / 검증 자동화)

- `scripts/check_no_gt_leak.py` 룰 약화 금지. ralph-loop 가드.
- `scripts/eval_live_extraction.py` 의 `_score()` Tag-level 비교 — F1 정의 변경 금지.
- `tests/backend/test_image_normalize.py` 의 7800 cap test.
- `tests/backend/test_harness_adapter.py` 의 feature-detect 검증.

## 글로벌 룰과 우선순위

순위 (높음 → 낮음):
1. 위 「절대 룰」 2번 보안 항목 — ALB SG, ECS private subnet, VPC endpoint
2. 위 「절대 룰」 3번 커밋 규칙 — AI attribution 금지, emoji 금지
3. **이 파일 (CLAUDE.md)** — 본 데모 specific
4. 기타 cursor-specific / agent-specific 가이드

충돌 시 위 우선순위로 해결.
