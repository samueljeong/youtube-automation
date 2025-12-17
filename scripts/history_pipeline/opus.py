"""
OPUS 입력 생성 모듈

반자동 운영 최적화:
- materials_pack: 자료 발췌/요약/핵심포인트
- opus_prompt_pack: Opus에 한 번에 붙여넣을 완제품

복붙 흐름:
1. OPUS_INPUT 시트에서 opus_prompt_pack 셀 복사
2. Opus에 붙여넣기
3. 대본 생성 완료
"""

import os
from datetime import datetime, timezone
from typing import List, Dict, Any, Tuple

from .config import (
    ERAS,
    SCRIPT_BRIEF_TEMPLATE,
    LLM_ENABLED_DEFAULT,
    LLM_MIN_SCORE_DEFAULT,
    LLM_MODEL_DEFAULT,
)
from .utils import (
    get_run_id,
    get_era_display_name,
    get_era_period,
)


def generate_opus_input(
    candidate_rows: List[List[Any]],
    era: str,
    llm_enabled: bool = LLM_ENABLED_DEFAULT,
    llm_min_score: float = LLM_MIN_SCORE_DEFAULT
) -> List[List[Any]]:
    """
    OPUS 입력 생성 (TOP 1만 처리)

    반자동 운영에 최적화:
    - materials_pack: 자료 발췌/요약/핵심포인트
    - opus_prompt_pack: Opus에 한 번에 붙여넣을 완제품

    Args:
        candidate_rows: CANDIDATES 행 데이터
        era: 시대 키
        llm_enabled: LLM 사용 여부
        llm_min_score: LLM 호출 최소 점수

    Returns:
        OPUS_INPUT 시트용 행 데이터 리스트
    """
    if not candidate_rows:
        print("[HISTORY] 후보 없음, OPUS_INPUT 생성 스킵")
        return []

    top1 = candidate_rows[0]
    run_date = top1[0]
    topic = top1[3]
    score_total = float(top1[4]) if top1[4] else 0
    title = top1[8]
    url = top1[9]
    summary = top1[10]

    era_name = get_era_display_name(era)
    period = get_era_period(era)

    # LLM 호출 조건
    should_call_llm = llm_enabled and (llm_min_score == 0 or score_total >= llm_min_score)

    if should_call_llm:
        print(f"[HISTORY] LLM 호출 (점수 {score_total} >= 최소 {llm_min_score})")
        core_facts, thumbnail_copy = _llm_generate_core_facts(
            era, era_name, period, topic, title, summary, url
        )
    else:
        if llm_enabled and score_total < llm_min_score:
            print(f"[HISTORY] LLM 스킵 (점수 {score_total} < 최소 {llm_min_score})")
        core_facts = _generate_default_core_facts(era_name, topic, title, summary)
        thumbnail_copy = _generate_default_thumbnail(era_name, topic, title)

    # ========================================
    # materials_pack: 자료 발췌/요약 묶음
    # ========================================
    materials_pack = _build_materials_pack(
        era_name, period, topic, title, url, summary, core_facts
    )

    # ========================================
    # opus_prompt_pack: Opus에 붙여넣을 완제품 (한 셀)
    # ========================================
    opus_prompt_pack = _build_opus_prompt_pack(
        era_name, period, topic, title, url, core_facts
    )

    # 생성 시간
    created_at = datetime.now(timezone.utc).isoformat()

    # 시트 행 생성 (HISTORY_OPUS_INPUT 컬럼 구조)
    opus_row = [[
        run_date,         # run_date
        era,              # era ★ Idempotency 체크용
        era_name,         # era_name
        title[:100],      # title
        url,              # source_url
        materials_pack,   # materials_pack
        opus_prompt_pack, # opus_prompt_pack ★ 이것만 복붙
        thumbnail_copy,   # thumbnail_copy (썸네일 문구 추천)
        "PENDING",        # status
        created_at,       # created_at
    ]]

    print(f"[HISTORY] OPUS_INPUT 생성 완료: {title[:30]}...")
    return opus_row


def _build_materials_pack(
    era_name: str,
    period: str,
    topic: str,
    title: str,
    url: str,
    summary: str,
    core_facts: str
) -> str:
    """자료 발췌/요약 묶음 생성 (참고용)"""

    return f"""━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📚 자료 정보
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
시대: {era_name} ({period})
주제: {topic}
제목: {title}
출처: {url}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📝 자료 요약
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{summary[:500]}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🎯 핵심포인트 (파이프라인 생성)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{core_facts}
"""


def _build_opus_prompt_pack(
    era_name: str,
    period: str,
    topic: str,
    title: str,
    url: str,
    core_facts: str
) -> str:
    """
    Opus에 붙여넣을 완제품 프롬프트 생성

    이 셀 하나만 복사해서 Opus에 붙여넣으면 됨
    마커 구조: [CONTEXT] / [STRUCTURE POINTS] / [OPUS SCRIPT BRIEF] / [ENDING PROMISE]
    """

    return f"""당신은 한국사 전문 유튜브 채널의 대본 작가입니다.
아래 정보를 바탕으로 **15~20분 분량(6,000~8,000자)**의 나레이션 대본을 작성하세요.

════════════════════════════════════════
[CONTEXT]
════════════════════════════════════════
- 채널/시대: 한국사 / {era_name} ({period})
- 자료 출처: {title}
- URL: {url}
- 오늘의 핵심 질문: 왜 {era_name}이 한국 역사의 시작점으로 중요한가?

════════════════════════════════════════
[STRUCTURE POINTS] (5~7개, 구조 중심)
════════════════════════════════════════
{core_facts}

════════════════════════════════════════
{SCRIPT_BRIEF_TEMPLATE}

════════════════════════════════════════
[ENDING PROMISE]
════════════════════════════════════════
- 다음 시대 연결: {era_name} 이후의 역사로 자연스럽게 연결
- 다음 영상 예고 한 줄: "다음 시간에는 ___에 대해 알아보겠습니다"

════════════════════════════════════════
⚠️ 최종 체크리스트 (작성 후 반드시 확인)
════════════════════════════════════════
□ 총 글자수 6,000~8,000자 사이인가?
□ 전반부(0~60%)에 감정/행동/공감 표현이 없는가?
□ "정리하면/핵심은/결론적으로" 등 중간요약 표현이 없는가?
□ 마지막 문장이 다음 시대로 연결되는 질문인가?
□ "~해야 합니다/~를 기억합시다" 같은 훈계형 표현이 없는가?
□ 갑자기 훈훈해지거나 착해지는 결론이 아닌가?
"""


def _generate_default_core_facts(
    era_name: str,
    topic: str,
    title: str,
    summary: str
) -> str:
    """LLM 없이 기본 핵심포인트 템플릿 생성"""

    return f"""[핵심포인트 - {era_name}]

▶ 주제: {topic}
▶ 출처: {title}

[#OPEN] 오프닝 질문
- 이 시대는 어떤 시대였나?
- 왜 이 주제가 오늘날에도 중요한가?

[#BODY1_FACTS_ONLY] 핵심 사실 (5개)
1. (사실 1 - 시간/장소/인물 중심)
2. (사실 2)
3. (사실 3)
4. (사실 4)
5. (사실 5)

[#TURN] 전환점
- 결정적 순간은 언제였나?
- 어떤 선택의 갈림길이 있었나?

[#BODY2_HUMAN_ALLOWED] 스토리 전개
- 주요 인물의 행동과 심리
- 사건의 드라마틱한 전개

[#IMPACT] 역사적 의의
- 이후 역사에 미친 영향

[#NEXT] 다음 시대 연결
- 다음 시대로 이어지는 질문

▶ 참고 요약:
{summary[:400]}
"""


def _generate_default_thumbnail(
    era_name: str,
    topic: str,
    title: str
) -> str:
    """기본 썸네일 문구 템플릿"""
    return f"""[썸네일 문구 추천]

1. {era_name}의 비밀
2. {topic} - 역사가 숨긴 진실
3. {title[:20]}...의 충격적 결말"""


def _llm_generate_core_facts(
    era: str,
    era_name: str,
    period: str,
    topic: str,
    title: str,
    summary: str,
    url: str
) -> Tuple[str, str]:
    """
    LLM으로 핵심포인트 생성 (구조 마커 포함)

    Returns:
        (core_facts, thumbnail_copy)
    """

    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        print("[HISTORY] OPENAI_API_KEY 환경변수 없음, 기본 템플릿 사용")
        return (
            _generate_default_core_facts(era_name, topic, title, summary),
            _generate_default_thumbnail(era_name, topic, title)
        )

    try:
        from openai import OpenAI
        client = OpenAI(api_key=api_key)

        prompt = f"""당신은 한국사 교육 콘텐츠 기획자입니다.
아래 자료를 바탕으로 YouTube 역사 영상의 대본 작성을 위한 '구조적 핵심포인트'를 생성하세요.

[시대 정보]
- 시대: {era_name}
- 기간: {period}
- 주제 분류: {topic}

[자료 정보]
- 제목: {title}
- 요약: {summary}
- 출처: {url}

[핵심포인트의 정체성]
이 단계는 '대본을 쓰기 위한 재료'를 제공하는 것입니다.
시청자를 설득하거나 감정을 유도하는 문장이 아닙니다.

[절대 금지]
❌ 감정 표현 (흥미롭다, 놀랍다, 안타깝다)
❌ 평가/판단 (위대하다, 중요하다, ~해야 한다)
❌ 추측 (아마도, ~했을 것이다)

[허용 요소]
⭕ 시간/장소/인물 정보
⭕ 사건의 원인과 결과
⭕ 역사적 맥락

[출력 형식 - 반드시 아래 구조 마커를 포함할 것]

[#OPEN] 오프닝 질문
- (시청자의 호기심을 자극할 질문 1~2개)

[#BODY1_FACTS_ONLY] 핵심 사실 (5개)
1. (역사적 사실 - 시간/장소/인물 중심, 25~40자)
2. (역사적 사실)
3. (역사적 사실)
4. (역사적 사실)
5. (역사적 사실)

[#TURN] 전환점
- (결정적 순간/선택의 갈림길)

[#BODY2_HUMAN_ALLOWED] 스토리 전개 힌트
- (여기서부터 인물 심리/행동 묘사 가능)
- (드라마틱한 전개 포인트)

[#IMPACT] 역사적 의의
- (이후 역사에 미친 영향)

[#NEXT] 다음 시대 연결
- (다음 시대로 이어지는 질문 1개)

[썸네일 문구 3안]
1. (클릭 유도 문구 - 짧고 임팩트 있게)
2. (호기심 자극 문구)
3. (반전/놀라움 문구)
"""

        model = os.environ.get("OPENAI_MODEL", LLM_MODEL_DEFAULT)

        if "gpt-5" in model:
            response = client.responses.create(
                model=model,
                input=[
                    {"role": "system", "content": [{"type": "input_text", "text": "한국사 교육 콘텐츠 기획자"}]},
                    {"role": "user", "content": [{"type": "input_text", "text": prompt}]}
                ],
                temperature=0.7
            )
            if getattr(response, "output_text", None):
                text = response.output_text.strip()
            else:
                text_chunks = []
                for item in getattr(response, "output", []) or []:
                    for content in getattr(item, "content", []) or []:
                        if getattr(content, "type", "") == "text":
                            text_chunks.append(getattr(content, "text", ""))
                text = "\n".join(text_chunks).strip()
        else:
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": "한국사 교육 콘텐츠 기획자"},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7
            )
            text = response.choices[0].message.content.strip()

        # 썸네일 문구 추출
        core_facts, thumbnail_copy = _parse_llm_response_with_thumbnail(text)

        print(f"[HISTORY] LLM 핵심포인트 생성 완료 (모델: {model})")
        return core_facts, thumbnail_copy

    except Exception as e:
        print(f"[HISTORY] LLM 호출 실패: {e}")
        return (
            _generate_default_core_facts(era_name, topic, title, summary),
            _generate_default_thumbnail(era_name, topic, title)
        )


def _parse_llm_response_with_thumbnail(text: str) -> Tuple[str, str]:
    """
    LLM 응답을 파싱하여 핵심포인트와 썸네일 문구 추출

    Returns:
        (core_facts, thumbnail_copy)
    """
    import re

    # 썸네일 문구 추출 (썸네일 이후 부분)
    thumb_match = re.search(
        r'썸네일.*',
        text,
        re.DOTALL | re.IGNORECASE
    )
    thumbnail_copy = thumb_match.group(0).strip() if thumb_match else ""

    # 핵심포인트 = 썸네일 전까지 전체
    if thumb_match:
        core_facts = text[:thumb_match.start()].strip()
    else:
        core_facts = text.strip()

    return core_facts, thumbnail_copy


def _parse_llm_response(text: str) -> Tuple[str, str, str]:
    """LLM 응답을 섹션별로 파싱 (레거시, 미사용)"""
    import re

    core_facts = ""
    narrative_arc = ""
    thumbnail_ideas = ""

    # 핵심 사실 추출
    core_match = re.search(
        r'핵심\s*사실.*?(?=스토리|$)',
        text,
        re.DOTALL | re.IGNORECASE
    )
    if core_match:
        core_facts = core_match.group(0).strip()

    # 스토리 아크 추출
    arc_match = re.search(
        r'스토리\s*아크.*?(?=썸네일|$)',
        text,
        re.DOTALL | re.IGNORECASE
    )
    if arc_match:
        narrative_arc = arc_match.group(0).strip()

    # 썸네일 문구 추출
    thumb_match = re.search(
        r'썸네일.*',
        text,
        re.DOTALL | re.IGNORECASE
    )
    if thumb_match:
        thumbnail_ideas = thumb_match.group(0).strip()

    # 핵심 사실이 비어있으면 전체 텍스트 사용
    if not core_facts:
        core_facts = text

    return core_facts, narrative_arc, thumbnail_ideas
