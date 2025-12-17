"""
OPUS 입력 생성 모듈

TOP 1 후보에 대해:
- LLM으로 핵심 사실(core_facts) 생성
- 스토리 아크 제안
- 대본 지시문 생성
"""

import os
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
    run_id = top1[0]
    topic = top1[3]
    score_total = float(top1[4]) if top1[4] else 0
    title = top1[8]
    summary = top1[10]
    url = top1[9]

    era_name = get_era_display_name(era)
    period = get_era_period(era)

    # LLM 호출 조건
    should_call_llm = llm_enabled and (llm_min_score == 0 or score_total >= llm_min_score)

    if should_call_llm:
        print(f"[HISTORY] LLM 호출 (점수 {score_total} >= 최소 {llm_min_score})")
        core_facts, narrative_arc, thumbnail_ideas = _llm_generate_opus_input(
            era, era_name, period, topic, title, summary, url
        )
    else:
        if llm_enabled and score_total < llm_min_score:
            print(f"[HISTORY] LLM 스킵 (점수 {score_total} < 최소 {llm_min_score})")
        # LLM 없이 기본 템플릿
        core_facts, narrative_arc, thumbnail_ideas = _generate_default_template(
            era, era_name, topic, title, summary
        )

    # 대본 지시문 생성
    script_brief = SCRIPT_BRIEF_TEMPLATE.format(
        era_name=era_name,
        period=period
    )

    opus_row = [[
        run_id,          # run_id
        1,               # selected_rank
        era,             # era
        topic,           # topic
        core_facts,      # core_facts
        narrative_arc,   # narrative_arc
        script_brief,    # script_brief
        thumbnail_ideas, # thumbnail_ideas
        "NEW",           # status
        "",              # opus_script (사람이 작성)
    ]]

    print(f"[HISTORY] OPUS_INPUT 생성 완료: {title[:30]}...")
    return opus_row


def _generate_default_template(
    era: str,
    era_name: str,
    topic: str,
    title: str,
    summary: str
) -> Tuple[str, str, str]:
    """LLM 없이 기본 템플릿 생성"""

    core_facts = f"""[핵심 사실 - {era_name}]

주제: {topic}
출처: {title}

핵심 사실 (총 5개):
1. (사실 1 - 출처에서 추출 필요)
2. (사실 2)
3. (사실 3)
4. (사실 4)
5. (사실 5)

참고 요약:
{summary[:300]}
"""

    narrative_arc = f"""[스토리 아크 제안]

시대: {era_name}
주제: {topic}

1. 오프닝 (배경 설정)
   - 이 시대는 어떤 시대였나?
   - 왜 이 주제가 중요한가?

2. 전개 (핵심 사건)
   - 무슨 일이 있었나?
   - 주요 인물은 누구인가?

3. 클라이맥스 (전환점)
   - 결정적 순간은 언제인가?
   - 어떤 선택이 있었나?

4. 결말 (영향과 의의)
   - 이후 역사에 어떤 영향을 미쳤나?
   - 현대와의 연결점은?
"""

    thumbnail_ideas = f"""[썸네일 문구 아이디어]

1. {era_name}의 비밀
2. {title[:15]}...의 진실
3. 역사가 숨긴 {era_name}
"""

    return core_facts, narrative_arc, thumbnail_ideas


def _llm_generate_opus_input(
    era: str,
    era_name: str,
    period: str,
    topic: str,
    title: str,
    summary: str,
    url: str
) -> Tuple[str, str, str]:
    """LLM으로 OPUS 입력 생성"""

    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        print("[HISTORY] OPENAI_API_KEY 환경변수 없음, 기본 템플릿 사용")
        return _generate_default_template(era, era_name, topic, title, summary)

    try:
        from openai import OpenAI
        client = OpenAI(api_key=api_key)

        prompt = f"""당신은 한국사 교육 콘텐츠 기획자입니다.
아래 자료를 바탕으로 YouTube 역사 영상의 대본 작성을 위한 '구조적 핵심 사실'을 생성하세요.

[시대 정보]
- 시대: {era_name}
- 기간: {period}
- 주제 분류: {topic}

[자료 정보]
- 제목: {title}
- 요약: {summary}
- 출처: {url}

[핵심 사실의 정체성]
핵심 사실 = 역사적 사실(What) + 인과관계(Why) + 역사적 흐름(Where)

이 단계는 '대본을 쓰기 위한 재료'를 제공하는 것입니다.
시청자를 설득하거나 감정을 유도하는 문장이 아닙니다.

[절대 금지]
❌ 감정 표현 (흥미롭다, 놀랍다, 안타깝다)
❌ 평가/판단 (위대하다, 중요하다, ~해야 한다)
❌ 추측 (아마도, ~했을 것이다)
❌ 현대적 가치 판단 투영

[허용 요소]
⭕ 시간/장소/인물 정보
⭕ 사건의 원인과 결과
⭕ 역사적 맥락
⭕ 이후 역사에 미친 영향

[출력 형식]

## 핵심 사실 (총 5개)
1. (역사적 사실 - 25~40자)
2. (역사적 사실)
3. (역사적 사실)
4. (역사적 사실)
5. (역사적 사실)

## 스토리 아크 제안
- 오프닝 훅: (시청자의 호기심을 자극할 질문 1개)
- 전개 포인트 3개: (주요 사건/전환점)
- 클로징 연결: (다음 시대로 이어지는 연결고리)

## 썸네일 문구 3안
1.
2.
3.
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

        # 응답 파싱
        core_facts, narrative_arc, thumbnail_ideas = _parse_llm_response(text)

        print(f"[HISTORY] LLM 핵심 사실 생성 완료 (모델: {model})")
        return core_facts, narrative_arc, thumbnail_ideas

    except Exception as e:
        print(f"[HISTORY] LLM 호출 실패: {e}")
        return _generate_default_template(era, era_name, topic, title, summary)


def _parse_llm_response(text: str) -> Tuple[str, str, str]:
    """LLM 응답을 섹션별로 파싱"""
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
