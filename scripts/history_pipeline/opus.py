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
    ERA_ORDER,
    SCRIPT_BRIEF_TEMPLATE,
    LLM_ENABLED_DEFAULT,
    LLM_MIN_SCORE_DEFAULT,
    LLM_MODEL_DEFAULT,
    PENDING_TARGET_COUNT,
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
아래 정보를 바탕으로 **15~20분 분량(13,650~18,200자)**의 나레이션 대본을 작성하세요.

════════════════════════════════════════
[CONTEXT]
════════════════════════════════════════
- 채널/시대: 한국사 / {era_name} ({period})
- 자료 출처: {title}
- URL: {url}
- 오늘의 핵심 질문: {era_name} 시대는 어떻게 형성되고 변화했는가?

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
□ 총 글자수 13,650~18,200자 사이인가?
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
- 주요 인물이 한 행동과 결정 (구체적 행위)
- 사건의 전개 과정 (원인→결과)

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
❌ 민족주의 표현 (민족 저항, 외세 침략, 자주 정신, 찬란한)
❌ 시청자 직접 호칭 (궁금하지 않은가?, 여러분, 우리)

[BODY1_FACTS_ONLY 특별 규칙]
⚠️ 사실만! 해석/의미/평가 금지
❌ 나쁜 예: "멸망은 역사적 종말을 의미하며, 저항이 계속되었다"
⭕ 좋은 예: "멸망 이후 한나라의 직접 지배 체제가 들어왔다"
→ "의미", "저항", "정체성" 같은 단어는 [#IMPACT]에서만 사용

[OPEN 질문 규칙]
⚠️ 관찰자 시점만! 감정 유도 금지
❌ 나쁜 예: "궁금하지 않은가?"
⭕ 좋은 예: "한나라의 침략은 고조선의 구조를 어떻게 바꾸었을까?"

[허용 요소]
⭕ 시간/장소/인물 정보
⭕ 사건의 원인과 결과
⭕ 역사적 맥락
⭕ "대응", "전개", "변화" (가치중립 표현)

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
- (인물이 한 구체적 행동과 결정)
- (사건 전개 과정: 원인→결과)

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


# ============================================================
# 에피소드 기반 OPUS 입력 생성 (새 구조)
# ============================================================

def determine_era_episodes(era: str, materials: List[Dict[str, Any]]) -> int:
    """
    AI가 시대별 에피소드 수 결정

    Args:
        era: 시대 키
        materials: 수집된 자료 목록

    Returns:
        해당 시대의 총 에피소드 수 (3~10)
    """
    era_name = get_era_display_name(era)
    period = get_era_period(era)

    # 기본 에피소드 수 (자료 수 기반)
    material_count = len(materials)

    # 시대별 중요도 가중치
    era_weights = {
        "GOJOSEON": 1.0,      # 고조선 (기본)
        "BUYEO": 0.8,         # 부여/옥저/동예
        "SAMGUK": 1.5,        # 삼국시대 (많은 이야기)
        "NAMBUK": 1.0,        # 남북국시대
        "GORYEO": 1.3,        # 고려 (다양한 사건)
        "JOSEON_EARLY": 1.4,  # 조선 전기 (세종 등)
        "JOSEON_LATE": 1.5,   # 조선 후기 (격변기)
        "DAEHAN": 1.0,        # 대한제국
    }

    weight = era_weights.get(era, 1.0)

    # LLM으로 에피소드 수 결정
    api_key = os.environ.get("OPENAI_API_KEY")
    if api_key and os.environ.get("LLM_ENABLED", "0") == "1":
        episodes = _llm_determine_episodes(era, era_name, period, materials)
        if episodes:
            return episodes

    # 기본 계산: 자료 수 * 가중치, 최소 3, 최대 10
    base_episodes = max(3, min(10, int(material_count * 0.5 * weight)))

    print(f"[HISTORY] {era_name} 에피소드 수 결정: {base_episodes}편 (자료 {material_count}개, 가중치 {weight})")
    return base_episodes


def _llm_determine_episodes(
    era: str,
    era_name: str,
    period: str,
    materials: List[Dict[str, Any]]
) -> int:
    """LLM으로 에피소드 수 결정"""

    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        return 0

    try:
        from openai import OpenAI
        client = OpenAI(api_key=api_key)

        # 자료 요약
        material_summaries = []
        for m in materials[:10]:
            material_summaries.append(f"- {m.get('title', '')[:50]}")

        prompt = f"""당신은 한국사 YouTube 시리즈 기획자입니다.

[시대 정보]
- 시대: {era_name}
- 기간: {period}

[수집된 자료 (총 {len(materials)}개)]
{chr(10).join(material_summaries)}

이 시대를 몇 편의 에피소드로 구성할지 결정하세요.

[고려 사항]
1. 각 에피소드는 15~20분 분량 (하나의 주제에 집중)
2. 시대의 중요도와 복잡성
3. 시청자 관심도 유지를 위한 적정 분량
4. 자료의 다양성과 깊이

[답변 형식]
숫자만 답하세요 (예: 5)
최소 3편, 최대 10편 사이로 답하세요.
"""

        model = os.environ.get("OPENAI_MODEL", LLM_MODEL_DEFAULT)

        if "gpt-5" in model:
            response = client.responses.create(
                model=model,
                input=[
                    {"role": "user", "content": [{"type": "input_text", "text": prompt}]}
                ],
                temperature=0.3
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
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3
            )
            text = response.choices[0].message.content.strip()

        # 숫자 추출
        import re
        numbers = re.findall(r'\d+', text)
        if numbers:
            episodes = int(numbers[0])
            episodes = max(3, min(10, episodes))
            print(f"[HISTORY] LLM이 결정한 에피소드 수: {episodes}편")
            return episodes

    except Exception as e:
        print(f"[HISTORY] LLM 에피소드 수 결정 실패: {e}")

    return 0


def generate_episode_opus_input(
    episode: int,
    era: str,
    era_episode: int,
    total_episodes: int,
    candidate_row: List[Any],
    is_new_era: bool = False
) -> List[List[Any]]:
    """
    에피소드 기반 OPUS 입력 생성

    Args:
        episode: 전체 에피소드 번호 (1, 2, 3, ...)
        era: 시대 키
        era_episode: 시대 내 에피소드 번호 (1, 2, 3, ...)
        total_episodes: 해당 시대 총 에피소드 수
        candidate_row: CANDIDATES 행 데이터
        is_new_era: 새 시대 시작 여부

    Returns:
        OPUS_INPUT 시트용 행 데이터
    """
    if not candidate_row:
        print("[HISTORY] 후보 없음, OPUS_INPUT 생성 스킵")
        return []

    # CANDIDATES 행 파싱
    topic = candidate_row[3] if len(candidate_row) > 3 else ""
    score_total = float(candidate_row[4]) if len(candidate_row) > 4 and candidate_row[4] else 0
    title = candidate_row[8] if len(candidate_row) > 8 else ""
    url = candidate_row[9] if len(candidate_row) > 9 else ""
    summary = candidate_row[10] if len(candidate_row) > 10 else ""

    era_name = get_era_display_name(era)
    period = get_era_period(era)

    # 다음 시대 정보 (엔딩용)
    next_era_info = _get_next_era_info(era)

    # LLM 호출 조건
    llm_enabled = os.environ.get("LLM_ENABLED", "0") == "1"
    llm_min_score = float(os.environ.get("LLM_MIN_SCORE", LLM_MIN_SCORE_DEFAULT))
    should_call_llm = llm_enabled and (llm_min_score == 0 or score_total >= llm_min_score)

    if should_call_llm:
        print(f"[HISTORY] LLM 호출 (에피소드 {episode}, 점수 {score_total})")
        core_facts, thumbnail_copy = _llm_generate_episode_content(
            era, era_name, period, era_episode, total_episodes,
            topic, title, summary, url, next_era_info
        )
    else:
        core_facts = _generate_episode_core_facts(
            era_name, period, era_episode, total_episodes,
            topic, title, summary, next_era_info
        )
        thumbnail_copy = _generate_episode_thumbnail(
            era_name, era_episode, total_episodes, topic, title
        )

    # materials_pack 생성
    materials_pack = _build_episode_materials_pack(
        era_name, period, era_episode, total_episodes,
        topic, title, url, summary, core_facts
    )

    # opus_prompt_pack 생성
    opus_prompt_pack = _build_episode_opus_prompt_pack(
        era_name, period, era_episode, total_episodes,
        topic, title, url, core_facts, next_era_info
    )

    # 생성 시간
    created_at = datetime.now(timezone.utc).isoformat()

    # 에피소드 제목 생성
    episode_title = f"{era_name} {era_episode}화: {title[:50]}" if title else f"{era_name} {era_episode}화"

    # 시트 행 생성 (새 컬럼 구조)
    opus_row = [[
        episode,          # episode (전체 번호)
        era,              # era
        era_episode,      # era_episode (시대 내 번호)
        total_episodes,   # total_episodes (시대 총 에피소드)
        era_name,         # era_name
        episode_title,    # title
        url,              # source_url
        materials_pack,   # materials_pack
        opus_prompt_pack, # opus_prompt_pack
        thumbnail_copy,   # thumbnail_copy
        "PENDING",        # status
        created_at,       # created_at
    ]]

    print(f"[HISTORY] 에피소드 {episode} 생성: {era_name} {era_episode}/{total_episodes}화")
    return opus_row


def _get_next_era_info(era: str) -> Dict[str, str]:
    """다음 시대 정보 반환"""
    try:
        idx = ERA_ORDER.index(era)
        if idx + 1 < len(ERA_ORDER):
            next_era = ERA_ORDER[idx + 1]
            return {
                "era": next_era,
                "name": get_era_display_name(next_era),
                "period": get_era_period(next_era),
            }
    except ValueError:
        pass

    return {"era": "", "name": "다음 시대", "period": ""}


def _generate_episode_core_facts(
    era_name: str,
    period: str,
    era_episode: int,
    total_episodes: int,
    topic: str,
    title: str,
    summary: str,
    next_era_info: Dict[str, str]
) -> str:
    """에피소드용 핵심포인트 템플릿 생성"""

    is_last = era_episode >= total_episodes

    ending_hint = f"""[#NEXT] 다음 시대 연결
- {next_era_info['name']}으로 이어지는 질문
- "이 시대가 끝나고, {next_era_info['name']}이 시작됩니다. 다음 시간에 만나요."
""" if is_last else f"""[#NEXT] 다음 에피소드 예고
- {era_name} {era_episode + 1}화에서 다룰 내용 예고
- "다음 시간에는 {era_name}의 또 다른 이야기를 들려드리겠습니다."
"""

    return f"""[핵심포인트 - {era_name} {era_episode}/{total_episodes}화]

▶ 주제: {topic}
▶ 출처: {title}
▶ 진행상황: {era_name} 시리즈 {era_episode}/{total_episodes}화

[#OPEN] 오프닝 질문
- 이 에피소드의 핵심 질문
- 시청자가 알고 싶어할 포인트

[#BODY1_FACTS_ONLY] 핵심 사실 (5개)
1. (사실 1 - 시간/장소/인물 중심)
2. (사실 2)
3. (사실 3)
4. (사실 4)
5. (사실 5)

[#TURN] 전환점
- 결정적 순간은 언제였나?

[#BODY2_HUMAN_ALLOWED] 스토리 전개
- 주요 인물이 한 행동과 결정 (구체적 행위)
- 사건의 전개 과정 (원인→결과)

[#IMPACT] 역사적 의의
- 이후 역사에 미친 영향

{ending_hint}

▶ 참고 요약:
{summary[:400]}
"""


def _generate_episode_thumbnail(
    era_name: str,
    era_episode: int,
    total_episodes: int,
    topic: str,
    title: str
) -> str:
    """에피소드용 썸네일 문구 생성"""
    return f"""[썸네일 문구 추천 - {era_name} {era_episode}화]

1. {era_name} {era_episode}화 | {topic}
2. {title[:20]}...의 진실
3. 역사가 숨긴 {era_name}의 비밀 #{era_episode}"""


def _build_episode_materials_pack(
    era_name: str,
    period: str,
    era_episode: int,
    total_episodes: int,
    topic: str,
    title: str,
    url: str,
    summary: str,
    core_facts: str
) -> str:
    """에피소드용 자료 발췌 묶음"""

    return f"""━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📺 {era_name} 시리즈 {era_episode}/{total_episodes}화
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
🎯 핵심포인트
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{core_facts}
"""


def _build_episode_opus_prompt_pack(
    era_name: str,
    period: str,
    era_episode: int,
    total_episodes: int,
    topic: str,
    title: str,
    url: str,
    core_facts: str,
    next_era_info: Dict[str, str]
) -> str:
    """에피소드용 Opus 프롬프트 생성"""

    is_last = era_episode >= total_episodes

    next_hint = f"""- 시대 마무리: {era_name} 시대의 역사적 의의로 마무리
- 다음 시대 예고: "{next_era_info['name']}이 시작됩니다. 다음 시간에..."
""" if is_last else f"""- 다음 에피소드 예고: "{era_name} {era_episode + 1}화에서 계속됩니다"
- 시청자 유지: 다음 화에서 다룰 흥미로운 주제 언급
"""

    return f"""당신은 한국사 전문 유튜브 채널의 대본 작가입니다.
아래 정보를 바탕으로 **15~20분 분량(13,650~18,200자)**의 나레이션 대본을 작성하세요.

════════════════════════════════════════
[SERIES INFO]
════════════════════════════════════════
📺 시리즈: 한국사 - {era_name}
📍 현재 에피소드: {era_episode}/{total_episodes}화
⏱️ 분량: 15~20분 (13,650~18,200자)

════════════════════════════════════════
[CONTEXT]
════════════════════════════════════════
- 시대: {era_name} ({period})
- 자료 출처: {title}
- URL: {url}
- 오늘의 핵심 질문: {topic}의 구조와 변화 - 누가, 어떻게, 왜?

════════════════════════════════════════
[STRUCTURE POINTS]
════════════════════════════════════════
{core_facts}

════════════════════════════════════════
{SCRIPT_BRIEF_TEMPLATE}

════════════════════════════════════════
[ENDING PROMISE] - {era_episode}/{total_episodes}화
════════════════════════════════════════
{next_hint}

════════════════════════════════════════
⚠️ 최종 체크리스트
════════════════════════════════════════
□ 총 글자수 13,650~18,200자 사이인가?
□ 전반부(0~60%)에 감정/행동/공감 표현이 없는가?
□ 시리즈 {era_episode}/{total_episodes}화임을 명시했는가?
□ 다음 에피소드/시대 예고가 있는가?
"""


def _llm_generate_episode_content(
    era: str,
    era_name: str,
    period: str,
    era_episode: int,
    total_episodes: int,
    topic: str,
    title: str,
    summary: str,
    url: str,
    next_era_info: Dict[str, str]
) -> Tuple[str, str]:
    """LLM으로 에피소드 콘텐츠 생성"""

    # 기존 LLM 함수 활용
    core_facts, thumbnail_copy = _llm_generate_core_facts(
        era, era_name, period, topic, title, summary, url
    )

    # 에피소드 정보 추가
    episode_info = f"\n\n[에피소드 정보: {era_name} {era_episode}/{total_episodes}화]"
    core_facts = core_facts + episode_info

    return core_facts, thumbnail_copy
