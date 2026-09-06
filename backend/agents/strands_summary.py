"""Strands Agent that writes a Korean natural-language summary of a
finished pipeline run.

Output is meant for an end-user card immediately after extraction so
the audience reads "이 도면은 X로, Y개 설비와 Z 안전 이슈가 있습니다"
instead of squinting at a counts row. Includes a one-liner that the
result has been pushed into the SearchIndex + AgentCore Memory so the
storage path is visible in the demo, not implicit.
"""
from __future__ import annotations

from strands import Agent

from backend.schemas import ExtractionResult
from backend.strands_models import secondary_model


SYSTEM = """당신은 P&ID 분석 결과를 발표 청중에게 한국어로 요약해 주는
어시스턴트입니다.

규칙:
- 입력은 한 도면의 추출/평가 결과 JSON입니다.
- 출력은 **순수 JSON** 한 개. 다음 두 키:
    "summary": 한국어 4~6 문장 단락 (헤더/마크다운 불사용)
    "suggested_queries": 한국어 추천 자연어 질의 5개의 배열.
                        각 항목은 {"label": "짧은 칩 라벨 (12자 이내)",
                                   "text": "실제 질의 문장"}
- summary 흐름:
  1) 한 줄로 도면이 무엇인지
  2) 추출 통계 (장비/계장/라인 수)
  3) 자기수정 루프가 돌았으면 그 횟수와 의미
  4) ISA-5.1 룰 결과 (anomaly 0건이면 안전성 통과, 있으면 가장 중요한 1~2개)
  5) 마지막 한 줄: 추출 데이터가 SearchIndex (BM25 + Cohere Embed v4)에
     인덱싱되었고 AgentCore Memory에 cross-session 저장되어 자연어 질의가
     가능함을 명시
- suggested_queries 작성 규칙 (CRITICAL — 위반 시 답변 무효):
  * **반드시 입력 JSON의 anomalies / equipment / instruments / lines에
    명시된 태그·라인만 인용**한다. 등장하지 않은 태그를 만들지 않는다.
  * **부정 전제 금지 (절대):** "왜 X가 없는지", "왜 연결되어 있지 않은지",
    "X의 PSV 보호 연결 상태", "X의 안전 밸브 보호" 같이 결손/부재를
    가정하는 질문은 금지. 단, 그 결손이 입력 anomalies 배열에
    `rule=vessel_without_psv_protection` 등으로 명시되어 있을 때만,
    그 anomaly의 violated_by 태그를 정확히 인용해 1개 질문 생성 허용.
  * anomalies 배열이 비어 있으면, **결손 가정 질문은 0개**. 대신 다음
    중에서만 5개 선택:
    1. 특정 라인의 사양 (size/service/spec) 조회
    2. 특정 장비의 기능/서비스 요약
    3. 특정 instrument 의 loop_id, located_on, signal target
    4. 두 장비 간 흐름 경로 (어떤 라인을 통해 연결되는가)
    5. 도면 전체의 ISA-5.1 검증 결과 / 자기수정 루프 횟수 / 라인 verifier 가
       바로잡은 항목 같은 메타 질문
  * 질문은 모두 **확정형**으로: "V-101의 서비스는 무엇인가요?",
    "4\\\"-PSV-402-CS 라인은 어디로 흐르나요?" 식. "왜", "보호",
    "안전" 같은 결손 추측 어휘 금지 (단, anomaly에서 직접 인용한
    경우만 예외).
  * 안전 영역 다양화 (장비 타입/계장/라인/흐름 경로) — 같은 카테고리
    5개 금지.
  * 라벨은 12자 이내, text는 한국어 자연어 1문장.
  * 현재 도면(drawing_id)에 한정된 질문만 작성. "다른 도면", "역사적"
    같은 표현 금지.
- 추측 금지. JSON 외 다른 텍스트(설명, 코드 펜스) 금지. 응답은 `{` 로 시작."""


def _agent_text(result) -> str:
    msg = result.message
    if isinstance(msg, dict):
        for part in msg.get("content", []):
            if "text" in part:
                return part["text"]
    return str(msg)


def summarize(
    *,
    drawing_id: str,
    title: str | None,
    extraction: ExtractionResult,
    verdict: str,
    iterations_used: int,
    anomalies: list[dict],
    memory_backend: str,
) -> dict:
    eq_n = len(extraction.equipment)
    inst_n = len(extraction.instruments)
    line_n = len(extraction.lines)
    conn_n = len(extraction.connections)

    eq_tags = ", ".join(e.tag for e in extraction.equipment[:20])
    inst_tags = ", ".join(i.tag for i in extraction.instruments[:20])
    line_tags = ", ".join(l.line_no for l in extraction.lines[:15])
    anomaly_lines = "\n".join(
        f"- rule={a.get('rule')} severity={a.get('severity')} "
        f"violated_by={a.get('violated_by')} desc={a.get('description')}"
        for a in anomalies[:5]
    ) or "- (none — no ISA-5.1 violations were detected)"

    user = (
        f"drawing_id: {drawing_id}\n"
        f"title: {title or '(unknown)'}\n"
        f"verdict: {verdict}\n"
        f"iterations_used: {iterations_used}\n"
        f"counts: equipment={eq_n} instruments={inst_n} "
        f"lines={line_n} connections={conn_n}\n"
        f"equipment_tags: {eq_tags}\n"
        f"instrument_tags: {inst_tags}\n"
        f"line_tags: {line_tags}\n"
        f"anomalies:\n{anomaly_lines}\n"
        f"memory_backend: {memory_backend}\n"
        "\nWrite the Korean summary now. Remember: only use tags that "
        "appear above; do not invent shortcomings that the anomalies "
        "list does not mention."
    )
    agent = Agent(
        model=secondary_model(),
        system_prompt=SYSTEM,
        callback_handler=None,
    )
    result = agent(user)
    raw = _agent_text(result).strip()
    return _parse_summary_json(raw)


def _parse_summary_json(raw: str) -> dict:
    """Best-effort decode of the agent's JSON envelope.

    The agent is instructed to return pure JSON, but Strands sometimes
    wraps it in a ```json``` fence, prefixes it with prose, or appends a
    trailing summary line. We extract the first balanced {...} block,
    then fall back to a plain-text summary with no suggestions if
    nothing parses.
    """
    import json
    text = raw.strip()

    candidates: list[str] = []

    # 1) ```json ... ``` fenced block.
    if "```" in text:
        try:
            inner = text.split("```", 2)[1]
            if inner.startswith("json"):
                inner = inner[4:]
            inner = inner.strip().rstrip("`").strip()
            if inner:
                candidates.append(inner)
        except IndexError:
            pass

    # 2) First balanced {...} substring.
    start = text.find("{")
    if start >= 0:
        depth = 0
        for i in range(start, len(text)):
            ch = text[i]
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    candidates.append(text[start : i + 1])
                    break

    # 3) Whole string (covers the rare case of pure JSON without prose).
    candidates.append(text)

    for cand in candidates:
        try:
            data = json.loads(cand)
        except json.JSONDecodeError:
            continue
        if not isinstance(data, dict):
            continue
        summary_text = str(data.get("summary", ""))
        raw_q = data.get("suggested_queries") or []
        cleaned: list[dict] = []
        for item in raw_q[:6]:
            if isinstance(item, dict) and "label" in item and "text" in item:
                cleaned.append({
                    "label": str(item["label"])[:24],
                    "text": str(item["text"])[:200],
                })
        if not cleaned:
            print(f"[summary] parsed JSON but no suggested_queries; "
                  f"raw_q={raw_q!r:.300}")
        return {"summary": summary_text, "suggested_queries": cleaned}

    print(f"[summary] JSON parse failed; raw={raw[:300]!r}")
    return {"summary": raw, "suggested_queries": []}
