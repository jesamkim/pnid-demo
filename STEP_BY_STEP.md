# Pipeline Step-by-Step (v35)

도면 한 장이 업로드부터 자연어 질의 가능 상태까지 거치는 전체 흐름.
각 단계는 `ProgressEvent` 로 WebSocket 을 통해 프론트엔드에 실시간 스트리밍됩니다.

---

## Step 1 — Image Normalize

| | |
|---|---|
| **모듈** | `backend/tools/image_normalize.py` |
| **기술** | pypdfium2 + PIL Lanczos |
| **입력** | PDF / PNG / JPG / TIFF |
| **출력** | 단일 PNG (≤7800 px, 200 dpi) |

모든 입력을 byte-identical PNG 로 통일. Viewer 와 agent 가 같은 좌표계를 공유.

---

## Step 2 — Hierarchical Vision Extraction

| | |
|---|---|
| **모듈** | `strands_zone_scout.py` → `strands_extractor_hierarchical.py` |
| **AgentCore** | `pnidvision-Bsh2SFGWQl` |
| **모델** | Zone Scout: Sonnet 4.6 / Zone Specialist: **Opus 4.8** |

### 동작 방식

```
[전체 도면] ──(downscale)──► Zone Scout (Sonnet 4.6)
                              │
                              ▼ 3~6 zones (topic + bbox_norm)
                              │
                    ┌─────────┼─────────┐
                    ▼         ▼         ▼
              Zone A crop  Zone B crop  Zone C crop ...
              (Opus 4.8)   (Opus 4.8)   (Opus 4.8)
                    │         │         │
                    └─────────┼─────────┘
                              ▼
                    Deterministic dedup + bbox shift
                              │
                              ▼ merged ExtractionResult
```

사람이 도면을 읽는 순서를 모사: 큰 그림 파악 → 영역별 상세 분석 → 통합.

### Convention Auto-Detect

OCR 직후 `convention_detector.py` 가 텍스트 패턴으로 ISA/DIN 자동 판별.
Zone Specialist 에게 적합한 system prompt 를 주입합니다.

---

## Step 3 — OCR Anchor

| | |
|---|---|
| **모듈** | `strands_ocr.py` |
| **AgentCore** | `pnidocr-iT73xP50Lj` |
| **기술** | AWS Textract `DetectDocumentText` |

Textract 의 LINE block = 여러 단어를 공간적으로 한 줄로 합산. 이 특성이
fusion 의 tag-매칭과 정확히 호환됩니다.

출력: `TextBlock(text, confidence, bbox)` — pixel 좌표.

---

## Step 4 — Fusion

| | |
|---|---|
| **모듈** | `strands_fusion.py` + `line_refinement.py` + `strands_zoom_lines.py` |
| **AgentCore** | `pnidfusion-FuhMBv2aKk` |
| **모델** | Sonnet 4.6 sub-agent |

Vision 의 "무엇이 있는가" + OCR 의 "정확히 어디에" 를 매칭:
- Equipment bbox = OCR label bbox 로 enclose
- Instrument bbox = OCR label ±12px inflate (DIN: loop_id fallback 매칭)
- Line geometry = OCR label 중점들의 polyline

---

## Step 5 — Evaluate

| | |
|---|---|
| **모듈** | `strands_evaluator.py` + `isa_validator.py` |
| **모델** | Sonnet 4.6 critic + 결정론적 룰 엔진 |

ISA 또는 DIN convention 에 맞는 anomaly rules 만 적용:
- ISA: `vessel_without_psv_protection` + `orphan_instrument` + `pipe_spec_inconsistency`
- DIN: `orphan_instrument` + `pipe_spec_inconsistency` (PSV 룰 비활성)

---

## Step 6 — Self-Correction

| | |
|---|---|
| **모듈** | `strands_self_correction.py` + `strands_line_verifier.py` |
| **모델** | Opus 4.8 (재추출) + Sonnet 4.6 (verifier) |

verdict 가 `needs_correction` 이면 Opus 4.8 로 재추출 (max 5 iters).
Sonnet 4.6 line-verifier 가 false positive 제거.

---

## Step 6.5 — Valve Scanner

| | |
|---|---|
| **모듈** | `strands_valve_scanner.py` |
| **AgentCore** | `pnidvalve-ruTR7C6wFF` |
| **모델** | **Opus 4.8** |

각 zone crop 에서 프로세스 라인 위의 **inline valve 심볼**만 집중 탐지:
gate valve, ball valve, control valve, check valve, safety valve.

기존 추출에 없는 새 valve 만 union merge (bbox 포함).

---

## Step 6.7 — Connection Stitcher

| | |
|---|---|
| **모듈** | `strands_connection_stitcher.py` |
| **AgentCore** | `pnidstitch-suWrjC7M7X` |
| **모델** | **Opus 4.8** |

전체 도면 이미지 + 현재까지의 추출 결과를 받아:
- 프로세스 라인을 시각적으로 trace
- from_tag / to_tag / via_line 이 비어있는 connection 을 채움
- 기존에 없는 새 connection 추가

엔지니어가 "장비 사이를 잇는 라인을 따라가며 확인" 하는 동작을 재현.

---

## Step 7 — Index + Summary

| | |
|---|---|
| **모듈** | `api/main.py:/api/index_run` + `tools/search_index.py` + `strands_summary.py` |
| **AgentCore** | `pnidsummary-i79O9rHXOV` + AgentCore Memory |
| **모델** | Cohere Embed v4 (1536-d) + Sonnet 4.6 |

1. **SearchIndex 인덱싱**: equipment/instrument/line 단위 문서 → Cohere 임베딩 → BM25+벡터 하이브리드
2. **AgentCore Memory**: cross-session 저장
3. **한국어 요약**: 4~6 문장 + 추천 자연어 질의 5개
4. **NL Query 활성화**: `/api/query` 로 자연어 질의 가능

---

## 환경 변수

| 변수 | 기본값 | 설명 |
|---|---|---|
| `PNID_CONVENTION` | `auto` | ISA/DIN 자동 판별. `isa` 또는 `din` 강제 가능 |
| `PNID_HIERARCHICAL` | `1` | Zone-scout 기반 hierarchical 추출. `0` 이면 기존 tile fan-out |
| `OCR_BACKEND` | `textract` | `bda` 토글 가능 (실험용) |

---

## 코드 진입점

| 파일 | 역할 |
|---|---|
| `backend/agents/strands_orchestrator.py:run_pipeline` | Step 1~7 순차 실행 |
| `backend/api/main.py:websocket_extract` | WebSocket 핸들러 |
| `backend/api/main.py:/api/index_run` | Step 7 자동 인덱싱 |
| `backend/api/main.py:/api/query` | 자연어 질의 |
| `frontend/src/hooks/useExtractStream.ts` | WebSocket 클라이언트 |
| `frontend/src/components/organisms/PnidStepBanner.tsx` | Step 1~7 UI banner |
