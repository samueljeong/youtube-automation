"""
OPUS 입력 생성 모듈 (주제 기반 구조)

2024-12 개편:
- 주제별로 수집한 실제 자료 내용을 Opus에 전달
- API에서 추출한 콘텐츠가 대본의 기반이 됨
- Opus는 수집된 자료를 바탕으로 대본 작성

복붙 흐름:
1. OPUS_INPUT 시트에서 opus_prompt_pack 셀 복사
2. Opus에 붙여넣기
3. 대본 생성 완료
"""

import os
from datetime import datetime, timezone
from typing import List, Dict, Any, Tuple, Optional

from .config import (
    ERAS,
    ERA_ORDER,
    SCRIPT_BRIEF_TEMPLATE,
    LLM_ENABLED_DEFAULT,
    LLM_MIN_SCORE_DEFAULT,
    LLM_MODEL_DEFAULT,
    HISTORY_TOPICS,
)
from .utils import (
    get_run_id,
    get_era_display_name,
    get_era_period,
)


def generate_topic_opus_input(
    episode: int,
    era: str,
    era_episode: int,
    topic_info: Dict[str, Any],
    collected_materials: Dict[str, Any],
) -> List[List[Any]]:
    """
    주제 기반 OPUS 입력 생성 (실제 수집 자료 포함)

    Args:
        episode: 전체 에피소드 번호 (1, 2, 3, ...)
        era: 시대 키 (예: "GOJOSEON")
        era_episode: 시대 내 에피소드 번호 (1, 2, 3, ...)
        topic_info: HISTORY_TOPICS에서 가져온 주제 정보
        collected_materials: collector.collect_topic_materials() 결과
            - full_content: 수집된 실제 내용
            - sources: 출처 목록
            - materials: 자료 리스트

    Returns:
        HISTORY_OPUS_INPUT 시트용 행 데이터
    """
    era_name = get_era_display_name(era)
    period = get_era_period(era)

    # 주제 정보 추출
    title = topic_info.get("title", f"{era_name} {era_episode}화")
    topic = topic_info.get("topic", "")
    keywords = topic_info.get("keywords", [])
    description = topic_info.get("description", "")
    reference_links = topic_info.get("reference_links", [])

    # 수집된 자료 추출
    full_content = collected_materials.get("full_content", "")
    sources = collected_materials.get("sources", [])
    materials = collected_materials.get("materials", [])

    # 시대 총 에피소드 수
    total_episodes = len(HISTORY_TOPICS.get(era, []))

    # 다음 에피소드/시대 정보
    next_info = _get_next_info(era, era_episode, total_episodes)

    # 썸네일 문구 생성
    thumbnail_copy = _generate_thumbnail_copy(era_name, era_episode, title, topic)

    # materials_pack 생성 (수집된 자료 요약)
    materials_pack = _build_materials_pack(
        era_name, period, era_episode, total_episodes,
        title, topic, description, sources, full_content
    )

    # opus_prompt_pack 생성 (Opus에 붙여넣을 완제품)
    opus_prompt_pack = _build_opus_prompt_pack(
        era_name, period, era_episode, total_episodes,
        title, topic, keywords, description,
        full_content, sources, next_info
    )

    # 생성 시간
    created_at = datetime.now(timezone.utc).isoformat()

    # 에피소드 제목
    episode_title = f"{era_name} {era_episode}화: {title}"

    # 대표 출처 URL
    source_url = reference_links[0] if reference_links else (sources[0] if sources else "")

    # 시트 행 생성
    opus_row = [[
        episode,          # episode (전체 번호)
        era,              # era
        era_episode,      # era_episode (시대 내 번호)
        total_episodes,   # total_episodes (시대 총 에피소드)
        era_name,         # era_name
        episode_title,    # title
        source_url,       # source_url
        materials_pack,   # materials_pack (참고용)
        opus_prompt_pack, # opus_prompt_pack ★ 이것만 복붙
        thumbnail_copy,   # thumbnail_copy
        "PENDING",        # status
        created_at,       # created_at
    ]]

    print(f"[HISTORY] 에피소드 {episode} 생성: {era_name} {era_episode}/{total_episodes}화 - {title}")
    print(f"[HISTORY] 수집 자료: {len(materials)}개, 내용 {len(full_content)}자")
    return opus_row


def _get_next_info(era: str, era_episode: int, total_episodes: int) -> Dict[str, Any]:
    """다음 에피소드/시대 정보 계산"""
    is_last_of_era = era_episode >= total_episodes

    if is_last_of_era:
        # 다음 시대로 이동
        try:
            idx = ERA_ORDER.index(era)
            if idx + 1 < len(ERA_ORDER):
                next_era = ERA_ORDER[idx + 1]
                next_era_topics = HISTORY_TOPICS.get(next_era, [])
                next_topic = next_era_topics[0] if next_era_topics else {}
                return {
                    "type": "next_era",
                    "era": next_era,
                    "era_name": get_era_display_name(next_era),
                    "title": next_topic.get("title", ""),
                    "topic": next_topic.get("topic", ""),
                }
        except ValueError:
            pass
        return {"type": "complete", "era": None, "era_name": "시리즈 완결"}
    else:
        # 같은 시대 다음 에피소드
        era_topics = HISTORY_TOPICS.get(era, [])
        next_topic = era_topics[era_episode] if len(era_topics) > era_episode else {}
        return {
            "type": "next_episode",
            "era": era,
            "era_name": get_era_display_name(era),
            "era_episode": era_episode + 1,
            "title": next_topic.get("title", ""),
            "topic": next_topic.get("topic", ""),
        }


def _generate_thumbnail_copy(
    era_name: str,
    era_episode: int,
    title: str,
    topic: str
) -> str:
    """썸네일 문구 생성"""
    return f"""[썸네일 문구 추천]

1. {title}
2. {era_name}의 비밀 #{era_episode}
3. {topic} - 역사가 숨긴 진실"""


def _build_materials_pack(
    era_name: str,
    period: str,
    era_episode: int,
    total_episodes: int,
    title: str,
    topic: str,
    description: str,
    sources: List[str],
    full_content: str
) -> str:
    """
    자료 발췌 묶음 생성 (참고용)

    이 셀은 수집된 자료의 요약본입니다.
    """
    source_list = "\n".join([f"  - {s}" for s in sources[:5]]) if sources else "  (없음)"

    # 내용이 너무 길면 요약
    content_preview = full_content[:2000] + "..." if len(full_content) > 2000 else full_content

    return f"""━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📺 {era_name} 시리즈 {era_episode}/{total_episodes}화
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
■ 제목: {title}
■ 주제: {topic}
■ 시대: {era_name} ({period})
■ 설명: {description}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📚 출처 목록
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{source_list}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📝 수집된 자료 내용 (미리보기)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{content_preview}
"""


def _build_opus_prompt_pack(
    era_name: str,
    period: str,
    era_episode: int,
    total_episodes: int,
    title: str,
    topic: str,
    keywords: List[str],
    description: str,
    full_content: str,
    sources: List[str],
    next_info: Dict[str, Any]
) -> str:
    """
    Opus에 붙여넣을 완제품 프롬프트 생성

    ★ 핵심 변경: 실제 수집된 자료 내용이 포함됨
    """
    is_last_of_era = era_episode >= total_episodes

    # 키워드 문자열
    keyword_str = ", ".join(keywords[:10]) if keywords else topic

    # 출처 목록 문자열
    source_list = "\n".join([f"  {i+1}. {s}" for i, s in enumerate(sources[:5])]) if sources else "  (출처 없음)"

    # 다음 에피소드/시대 안내
    if next_info["type"] == "next_era":
        ending_section = f"""════════════════════════════════════════
[ENDING - 시대 마무리]
════════════════════════════════════════
▶ 이 화는 {era_name}의 마지막 에피소드입니다.
▶ 시대를 정리하고 다음 시대로 자연스럽게 연결하세요.

[마무리 방향]
- {era_name} 시대가 남긴 것 (감정적 판단 없이)
- 이 시대의 방식/제도가 이후에 어떻게 이어졌는가

[다음 시대 예고]
- 다음 시대: {next_info['era_name']}
- 다음 주제: {next_info.get('title', '')}
- 예고 문구 예시: "다음 시간에는 {next_info['era_name']}의 이야기를 시작합니다. {next_info.get('title', '')}에 대해 알아보겠습니다."
"""
    elif next_info["type"] == "next_episode":
        ending_section = f"""════════════════════════════════════════
[ENDING - 다음 에피소드 예고]
════════════════════════════════════════
▶ {era_name} 시리즈는 계속됩니다. ({era_episode}/{total_episodes}화)

[다음 에피소드 예고]
- 다음 화: {era_name} {next_info['era_episode']}화
- 다음 주제: {next_info.get('title', '')}
- 예고 문구 예시: "다음 시간에는 {next_info.get('title', '')}에 대해 알아보겠습니다."
"""
    else:
        ending_section = """════════════════════════════════════════
[ENDING - 시리즈 완결]
════════════════════════════════════════
▶ 한국사 시리즈의 마지막 에피소드입니다.
▶ 전체 시리즈를 돌아보며 마무리하세요.
"""

    # 수집된 자료가 있으면 포함, 없으면 기본 안내
    if full_content and len(full_content) > 100:
        content_section = f"""════════════════════════════════════════
[수집된 자료 - 대본 작성의 기반]
════════════════════════════════════════
⚠️ 아래 자료는 실제 백과사전/박물관에서 추출한 내용입니다.
⚠️ 이 자료를 기반으로 대본을 작성하세요. 자료에 없는 내용은 추가하지 마세요.

{full_content[:8000]}
"""
    else:
        content_section = f"""════════════════════════════════════════
[자료 안내]
════════════════════════════════════════
⚠️ 수집된 자료가 부족합니다.
⚠️ 아래 주제와 키워드를 기반으로 대본을 작성하되,
   확인되지 않은 사실은 "~로 전해진다", "~로 알려져 있다" 등으로 표현하세요.

▶ 주제: {topic}
▶ 키워드: {keyword_str}
▶ 설명: {description}
"""

    return f"""당신은 한국사 전문 유튜브 채널의 대본 작가입니다.
아래 수집된 자료를 바탕으로 **15~20분 분량(13,650~18,200자)**의 나레이션 대본을 작성하세요.

════════════════════════════════════════
[SERIES INFO]
════════════════════════════════════════
📺 시리즈: 한국사 - {era_name}
📍 현재 에피소드: {era_episode}/{total_episodes}화
📌 에피소드 제목: {title}
⏱️ 분량: 15~20분 (13,650~18,200자)

════════════════════════════════════════
[CONTEXT]
════════════════════════════════════════
■ 시대: {era_name} ({period})
■ 주제: {topic}
■ 키워드: {keyword_str}
■ 설명: {description}

■ 출처:
{source_list}

{content_section}

════════════════════════════════════════
[SCRIPT STRUCTURE - 대본 구조]
════════════════════════════════════════
1. [OPEN] 오프닝 (500~800자)
   - 시청자의 호기심을 자극하는 질문으로 시작
   - 이 에피소드에서 다룰 내용 예고
   - 감정적 표현 없이 사실 중심

2. [BODY] 본문 (11,000~15,000자)
   - 수집된 자료의 내용을 스토리로 풀어서 설명
   - 시간순 또는 논리적 순서로 전개
   - 중간중간 시청자의 이해를 돕는 설명 추가
   - ⚠️ 자료에 없는 내용 추가 금지

3. [IMPACT] 역사적 의의 (1,000~1,500자)
   - 이 주제가 이후 역사에 미친 영향
   - 감정적 판단 없이 사실 중심으로 서술
   - ❌ 금지: "위대하다", "자랑스럽다", "안타깝다"

4. [ENDING] 마무리 (500~800자)
   - 핵심 내용 간단 정리 (3줄 이내)
   - 다음 에피소드 예고

════════════════════════════════════════
[RULES - 작성 규칙]
════════════════════════════════════════
✅ 허용:
- 수집된 자료에 있는 사실
- "~로 전해진다", "~로 기록되어 있다" 등 출처 명시 표현
- 시청자 이해를 돕는 배경 설명

❌ 금지:
- 자료에 없는 내용 추가 (창작 금지)
- 감정적 표현: "흥미롭다", "놀랍다", "위대하다", "안타깝다"
- 민족주의 표현: "민족의 자존심", "외세 침략", "찬란한 문화"
- 교훈적 결론: "~해야 한다", "~를 기억해야 한다"
- 시청자 직접 호칭: "여러분", "우리"

{ending_section}

════════════════════════════════════════
⚠️ 최종 체크리스트
════════════════════════════════════════
□ 총 글자수 13,650~18,200자 사이인가?
□ 수집된 자료의 내용만 사용했는가? (창작 내용 없음)
□ 감정적/판단적 표현이 없는가?
□ 민족주의적 표현이 없는가?
□ 다음 에피소드 예고가 있는가?
□ 출처가 명시되었는가?
"""


# ============================================================
# 레거시 호환 함수들 (기존 run.py에서 사용)
# ============================================================

def generate_opus_input(
    candidate_rows: List[List[Any]],
    era: str,
    llm_enabled: bool = LLM_ENABLED_DEFAULT,
    llm_min_score: float = LLM_MIN_SCORE_DEFAULT
) -> List[List[Any]]:
    """
    레거시 호환용 - 기존 OPUS 입력 생성

    새 코드는 generate_topic_opus_input() 사용 권장
    """
    print("[HISTORY] 레거시 함수 호출됨 - generate_topic_opus_input() 사용 권장")

    if not candidate_rows:
        return []

    top1 = candidate_rows[0]
    era_name = get_era_display_name(era)
    period = get_era_period(era)

    run_date = top1[0] if len(top1) > 0 else ""
    title = top1[8] if len(top1) > 8 else ""
    url = top1[9] if len(top1) > 9 else ""

    created_at = datetime.now(timezone.utc).isoformat()

    return [[
        run_date,
        era,
        era_name,
        title[:100],
        url,
        "(레거시 - 자료 없음)",
        "(레거시 - 프롬프트 없음)",
        "",
        "PENDING",
        created_at,
    ]]


def generate_episode_opus_input(
    episode: int,
    era: str,
    era_episode: int,
    total_episodes: int,
    candidate_row: List[Any],
    is_new_era: bool = False
) -> List[List[Any]]:
    """
    레거시 호환용 - 에피소드 기반 OPUS 입력 생성

    새 코드는 generate_topic_opus_input() 사용 권장
    """
    print("[HISTORY] 레거시 함수 호출됨 - generate_topic_opus_input() 사용 권장")

    era_name = get_era_display_name(era)
    period = get_era_period(era)
    created_at = datetime.now(timezone.utc).isoformat()

    title = candidate_row[8] if len(candidate_row) > 8 else f"{era_name} {era_episode}화"
    url = candidate_row[9] if len(candidate_row) > 9 else ""

    return [[
        episode,
        era,
        era_episode,
        total_episodes,
        era_name,
        f"{era_name} {era_episode}화: {title[:50]}",
        url,
        "(레거시 - 자료 없음)",
        "(레거시 - 프롬프트 없음)",
        "",
        "PENDING",
        created_at,
    ]]


def determine_era_episodes(era: str, materials: List[Dict[str, Any]]) -> int:
    """
    레거시 호환용 - AI가 시대별 에피소드 수 결정

    새 구조에서는 HISTORY_TOPICS에 미리 정의됨
    """
    # 새 구조에서는 HISTORY_TOPICS에서 가져옴
    topics = HISTORY_TOPICS.get(era, [])
    if topics:
        return len(topics)

    # 폴백: 기본값
    era_defaults = {
        "GOJOSEON": 5,
        "BUYEO": 4,
        "SAMGUK": 8,
        "NAMBUK": 6,
        "GORYEO": 7,
        "JOSEON_EARLY": 7,
        "JOSEON_LATE": 8,
        "DAEHAN": 5,
        "JAPANESE_RULE": 5,
        "DIVISION": 3,
        "MODERN": 2,
    }
    return era_defaults.get(era, 5)
