"""
OPUS 입력 생성 (LLM 포함)

반자동 운영 최적화:
- opus_prompt_pack: Opus에 한 번에 붙여넣을 완제품 (썸네일 제외)
"""

import os
from datetime import datetime, timezone

from .config import CHANNELS
from .utils import get_weekday_angle


# 통합 시트에 저장할 때 사용할 필드 순서
# ★ opus_rows의 각 열과 정확히 일치해야 함
NEWS_OPUS_FIELDS = [
    "run_id",           # [0] run_id
    "selected_rank",    # [1] rank
    "category",         # [2] category
    "issue_one_line",   # [3] title[:50]
    "core_points",      # [4] core_points
    "brief",            # [5] brief
    "thumbnail_copy",   # [6] thumb
    "opus_prompt_pack", # [7] opus_prompt_pack
    "상태",             # [8] "PENDING" → 상태 열에 저장
    "_skip_created",    # [9] created_at (스킵)
    "_skip_selected",   # [10] selected (스킵)
]


# ============================================================
# 대본 분량 설정 (2024-12 개편: 10-15분)
# ============================================================
SCRIPT_DURATION_MIN = 10  # 분
SCRIPT_DURATION_MAX = 15  # 분
SCRIPT_LEN_MIN = 9300     # 한국어 TTS 기준 약 620자/분
SCRIPT_LEN_MAX = 14000


def generate_opus_input(
    candidate_rows: list,
    channel: str,
    llm_enabled: bool = False,
    llm_min_score: int = 0,
    top_n: int = 3
) -> list:
    """
    OPUS 입력 생성 (TOP N 후보 모두 저장, 사용자 선택 가능)

    Args:
        candidate_rows: CANDIDATES 행 데이터
        channel: 채널 키
        llm_enabled: LLM 사용 여부
        llm_min_score: LLM 호출 최소 점수
        top_n: 저장할 후보 수 (기본 3)

    Returns:
        OPUS_INPUT 시트용 행 데이터 리스트
    """
    if not candidate_rows:
        return []

    # 카테고리 다양성 확보: 같은 카테고리가 연속되지 않도록 재정렬
    diversified = _diversify_by_category(candidate_rows, top_n)

    weekday_angle = get_weekday_angle()
    channel_name = CHANNELS.get(channel, {}).get("name", channel)
    created_at = datetime.now(timezone.utc).isoformat()

    opus_rows = []

    for rank, candidate in enumerate(diversified, start=1):
        run_id = candidate[0]
        category = candidate[2]
        score_total = float(candidate[4]) if candidate[4] else 0
        title = candidate[8]
        link = candidate[9]
        summary = ""

        # score_total을 1~5 중요도로 변환 (0~100점 → 1~5)
        priority = min(5, max(1, int(score_total / 20) + 1))

        # LLM은 TOP N 모두 적용
        should_call_llm = llm_enabled and (llm_min_score == 0 or score_total >= llm_min_score)

        if should_call_llm:
            print(f"[NEWS] LLM 호출 (rank {rank}, 점수 {score_total})")
            core_points, brief, thumb = _llm_make_opus_input(
                category, title, summary, link, channel
            )
        else:
            # LLM 없이 기본 템플릿
            core_points = f"""[핵심포인트]
• 이슈: {title}
• 출처: {link}
• 중요도: {priority}/5
• 채널: {channel}

핵심포인트 (총 5개):
1.
2.
3.
4.
5."""

            brief = f"""[대본 지시문]
- 분량: {SCRIPT_DURATION_MIN}~{SCRIPT_DURATION_MAX}분 ({SCRIPT_LEN_MIN:,}~{SCRIPT_LEN_MAX:,}자)
- 요일: {weekday_angle}
- 관점: "내 돈/내 생활"에 미치는 영향
- 구조: 서론(불안/의문) → 본론(핵심 정리) → 전망 → 마무리
- 금지: 속보 요약, 과장, 공포 조장"""

            thumb = ""

        # opus_prompt_pack 생성 (썸네일 제외, Opus 복붙용)
        opus_prompt_pack = _build_opus_prompt_pack(
            channel_name, category, title, link, weekday_angle, core_points
        )

        opus_rows.append([
            run_id,
            rank,             # selected_rank (1, 2, 3)
            category,
            title[:50],       # issue_one_line
            core_points,
            brief,
            thumb,            # thumbnail_copy
            opus_prompt_pack, # ★ Opus에 붙여넣을 완제품 (썸네일 제외)
            "PENDING",        # status
            created_at,       # created_at
            "",               # selected (사용자가 체크)
        ])

        print(f"[NEWS] OPUS_INPUT #{rank} 생성: [{category}] {title[:30]}...")

    print(f"[NEWS] OPUS_INPUT 총 {len(opus_rows)}개 후보 생성 완료")
    return opus_rows


def _diversify_by_category(candidate_rows: list, top_n: int) -> list:
    """
    카테고리 다양성 확보: 서로 다른 카테고리 우선 선정

    예: [경제, 경제, 정책, 사회, 경제] → [경제, 정책, 사회]
    """
    if len(candidate_rows) <= top_n:
        return candidate_rows

    selected = []
    used_categories = set()
    remaining = list(candidate_rows)

    # 1차: 서로 다른 카테고리 우선 선정
    for candidate in candidate_rows:
        category = candidate[2]
        if category not in used_categories:
            selected.append(candidate)
            used_categories.add(category)
            remaining.remove(candidate)
            if len(selected) >= top_n:
                break

    # 2차: 부족하면 점수순으로 채우기
    while len(selected) < top_n and remaining:
        selected.append(remaining.pop(0))

    return selected[:top_n]


def _build_opus_prompt_pack(
    channel_name: str,
    category: str,
    title: str,
    link: str,
    weekday_angle: str,
    core_points: str
) -> str:
    """
    Opus에 붙여넣을 완제품 프롬프트 생성 (썸네일 제외)
    """
    return f"""당신은 뉴스 전문 유튜브 채널의 대본 작가입니다.
아래 정보를 바탕으로 **{SCRIPT_DURATION_MIN}~{SCRIPT_DURATION_MAX}분 분량({SCRIPT_LEN_MIN:,}~{SCRIPT_LEN_MAX:,}자)**의 나레이션 대본을 작성하세요.

════════════════════════════════════════
[CONTEXT]
════════════════════════════════════════
- 채널: {channel_name}
- 카테고리: {category}
- 이슈: {title}
- 출처: {link}
- 오늘 톤: {weekday_angle}

════════════════════════════════════════
[STRUCTURE POINTS]
════════════════════════════════════════
{core_points}

════════════════════════════════════════
[SCRIPT BRIEF]
════════════════════════════════════════
📌 분량 (필수)
- 시간: {SCRIPT_DURATION_MIN}~{SCRIPT_DURATION_MAX}분
- 문자수: {SCRIPT_LEN_MIN:,}~{SCRIPT_LEN_MAX:,}자 (한국어 기준) ← 반드시 준수
- TTS 속도: 약 620~930자/분

📌 관점
- "내 돈/내 생활"에 미치는 영향 중심
- 시청자가 오늘 뉴스를 왜 봐야 하는지

📌 구조
- 서론: 불안/의문 유발 (15%)
- 본론: 핵심 정리 + 인과 설명 (60%)
- 전망: 앞으로 주목할 포인트 (20%)
- 마무리: 한 줄 요약 (5%)

🚫 금지
- 속보 요약 스타일
- 과장, 공포 조장
- "~해야 합니다", "~를 기억합시다" 같은 훈계

════════════════════════════════════════
⚠️ 최종 체크리스트 (작성 후 반드시 확인)
════════════════════════════════════════
□ 총 글자수 {SCRIPT_LEN_MIN:,}~{SCRIPT_LEN_MAX:,}자 사이인가?
□ "내 돈/내 생활"에 미치는 영향이 명확한가?
□ 과장/공포 조장 표현이 없는가?
□ 훈계형 표현이 없는가?
"""


def _parse_llm_response(text: str) -> tuple:
    """
    LLM 응답을 섹션별로 파싱

    Returns:
        (core_points, thumbnail_copy)
    """
    import re

    # 기본값
    core_points = ""
    thumb_copy = ""

    # 핵심포인트 추출 (썸네일 전까지)
    core_match = re.search(
        r'핵심포인트.*?(?=썸네일|$)',
        text,
        re.DOTALL | re.IGNORECASE
    )
    if core_match:
        core_points = core_match.group(0).strip()

    # 썸네일 문구 추출
    thumb_match = re.search(
        r'썸네일.*',
        text,
        re.DOTALL | re.IGNORECASE
    )
    if thumb_match:
        thumb_copy = thumb_match.group(0).strip()

    # 핵심포인트가 비어있으면 전체 텍스트 사용
    if not core_points:
        core_points = text

    return core_points, thumb_copy


def _llm_make_opus_input(
    category: str,
    title: str,
    summary: str,
    link: str,
    channel: str
) -> tuple:
    """
    LLM으로 핵심포인트 생성

    Returns:
        (core_points, brief, thumbnail_copy)
    """
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        print("[NEWS] OPENAI_API_KEY 환경변수 없음, LLM 스킵")
        return "", "", ""

    try:
        from openai import OpenAI
        client = OpenAI(api_key=api_key)

        channel_name = CHANNELS.get(channel, {}).get("name", channel)
        weekday_angle = get_weekday_angle()

        prompt = f"""당신은 뉴스 대본 작성을 위한 '구조적 핵심포인트'를 생성하는 역할이다.

[채널 정보]
- 채널: {channel_name} ({channel})
- 오늘 톤: {weekday_angle}

[이슈 정보]
- 카테고리: {category}
- 제목: {title}
- 요약: {summary}
- 출처: {link}

[핵심포인트의 정체성]
핵심포인트 = 사실(What) + 구조적 관계(Why) + 흐름/방향(Where)

이 단계의 핵심포인트는 '대본을 쓰기 위한 재료'이지,
시청자를 설득하거나 감정을 유도하는 문장이 아니다.

[절대 금지 - 이건 Opus가 할 일]
❌ 감정 표현 (불안, 부담, 걱정, 체감, 느낄 것이다)
❌ 시청자 관점 문장 (누가 체감한다, 어디서 느낀다)
❌ 조언, 판단, 결론 (해야 한다, 중요하다)
❌ "~할 것이다", "~해야 한다", "~수 있다"
❌ 생활 예시 (마트에서, 통장에서)
❌ 해석/설명 문장

[허용 요소 - 이것만 쓸 것]
⭕ 지표 변화
⭕ 정책/시장/환율/금리 간 관계
⭕ 인과 구조 (A → B → C)
⭕ 흐름의 방향성
⭕ 다음 단계에서 관찰할 포인트

[출력 조건]
- 총 5개
- 각 문장은 1문장, 25~40자
- 구조 설명 중심
- 문장 끝에 판단/조언 금지

[좋은 예시]
1. 환율 1,470원 수준이 소비자물가 전망에 반영되는 구조
2. 원화 약세가 수입물가를 통해 물가 상승 압력으로 전이되는 경로
3. 물가 전망 변화가 통화정책 판단에 미치는 영향
4. 환율 수준에 따른 소비자물가 상승률 변동 가능성
5. 향후 환율 흐름이 물가 안정성에 작용하는 변수

[나쁜 예시 - 절대 이렇게 쓰지 마라]
❌ "대출이 있는 사람은 부담이 커질 것이다" → 감정+시청자관점
❌ "장바구니 가격이 오르면 절약을 생각하게 된다" → 생활예시+감정
❌ "투자자들에게 심리적 안정을 제공할 수 있다" → 감정+판단

[출력 형식]
핵심포인트 (총 5개):
1. (구조/인과/방향 문장)
2. (구조/인과/방향 문장)
3. (구조/인과/방향 문장)
4. (구조/인과/방향 문장)
5. (구조/인과/방향 문장)

썸네일 문구 3안:
1.
2.
3."""

        model = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")

        if "gpt-5" in model:
            response = client.responses.create(
                model=model,
                input=[
                    {"role": "system", "content": [{"type": "input_text", "text": "뉴스 채널 기획자 역할"}]},
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
                    {"role": "system", "content": "뉴스 채널 기획자 역할"},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7
            )
            text = response.choices[0].message.content.strip()

        # LLM 응답 파싱 (섹션별 분리)
        core_points, thumb = _parse_llm_response(text)

        brief = f"""[대본 지시문]
- 분량: {SCRIPT_DURATION_MIN}~{SCRIPT_DURATION_MAX}분 ({SCRIPT_LEN_MIN:,}~{SCRIPT_LEN_MAX:,}자)
- 요일: {weekday_angle}
- 관점: "내 돈/내 생활"에 미치는 영향
- 구조: 서론(불안/의문) → 본론(핵심 정리) → 전망 → 마무리
- 금지: 속보 요약, 과장, 공포 조장"""

        print(f"[NEWS] LLM 핵심포인트 생성 완료 (모델: {model})")
        return core_points, brief, thumb

    except Exception as e:
        print(f"[NEWS] LLM 호출 실패: {e}")
        return "", "", ""
