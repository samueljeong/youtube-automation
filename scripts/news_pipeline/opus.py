"""
OPUS 입력 생성 (LLM 포함)
"""

import os

from .config import CHANNELS
from .utils import get_weekday_angle


def generate_opus_input(
    candidate_rows: list,
    channel: str,
    llm_enabled: bool = False,
    llm_min_score: int = 0
) -> list:
    """
    OPUS 입력 생성 (TOP 1만 처리)

    Args:
        candidate_rows: CANDIDATES 행 데이터
        channel: 채널 키
        llm_enabled: LLM 사용 여부
        llm_min_score: LLM 호출 최소 점수

    Returns:
        OPUS_INPUT 시트용 행 데이터 리스트
    """
    if not candidate_rows:
        return []

    top1 = candidate_rows[0]
    run_id = top1[0]
    category = top1[2]
    score_total = float(top1[4]) if top1[4] else 0
    title = top1[8]
    link = top1[9]
    summary = ""

    # score_total을 1~5 중요도로 변환 (0~100점 → 1~5)
    priority = min(5, max(1, int(score_total / 20) + 1))

    weekday_angle = get_weekday_angle()

    # LLM 호출 조건
    should_call_llm = llm_enabled and (llm_min_score == 0 or score_total >= llm_min_score)

    if should_call_llm:
        print(f"[NEWS] LLM 호출 (점수 {score_total} >= 최소 {llm_min_score})")
        core_points, brief, shorts, thumb = _llm_make_opus_input(
            category, title, summary, link, channel
        )
    elif llm_enabled and score_total < llm_min_score:
        print(f"[NEWS] LLM 스킵 (점수 {score_total} < 최소 {llm_min_score})")
        core_points, brief, shorts, thumb = "", "", "", ""
    else:
        # LLM 없이 기본 템플릿
        channel_name = CHANNELS.get(channel, {}).get("name", channel)
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
- 분량: 7~10분 (3,000~3,800자)
- 요일: {weekday_angle}
- 관점: "내 돈/내 생활"에 미치는 영향
- 구조: 서론(불안/의문) → 본론(핵심 정리) → 전망 → 마무리(루틴 예고)
- 금지: 속보 요약, 과장, 공포 조장"""

        shorts = ""
        thumb = ""

    opus_row = [[
        run_id,
        1,  # selected_rank
        category,
        title[:50],  # issue_one_line
        core_points,
        brief,
        shorts,
        thumb,
        "PENDING",  # status
        "",  # opus_script
    ]]

    print(f"[NEWS] OPUS_INPUT 생성 완료: {title[:30]}...")
    return opus_row


def _parse_llm_response(text: str) -> tuple:
    """
    LLM 응답을 섹션별로 파싱

    Returns:
        (core_points, shorts_hook, thumbnail_copy)
    """
    import re

    # 기본값
    core_points = ""
    shorts_hook = ""
    thumb_copy = ""

    # 핵심포인트 + 오프닝 감정유도 추출 (엔딩 전까지)
    core_match = re.search(
        r'핵심포인트.*?(?=엔딩|$)',
        text,
        re.DOTALL | re.IGNORECASE
    )
    if core_match:
        core_points = core_match.group(0).strip()

    # 엔딩 루틴예고 추출 (썸네일 전까지)
    shorts_match = re.search(
        r'엔딩\s*루틴.*?(?=썸네일|$)',
        text,
        re.DOTALL | re.IGNORECASE
    )
    if shorts_match:
        shorts_hook = shorts_match.group(0).strip()

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

    return core_points, shorts_hook, thumb_copy


def _llm_make_opus_input(
    category: str,
    title: str,
    summary: str,
    link: str,
    channel: str
) -> tuple:
    """LLM으로 핵심포인트 생성"""
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        print("[NEWS] OPENAI_API_KEY 환경변수 없음, LLM 스킵")
        return "", "", "", ""

    try:
        from openai import OpenAI
        client = OpenAI(api_key=api_key)

        channel_name = CHANNELS.get(channel, {}).get("name", channel)
        weekday_angle = get_weekday_angle()

        prompt = f"""너는 '속보가 아니라 정리' 뉴스 채널의 기획자다.
Opus가 대본을 쓸 때 참고할 '핵심포인트'를 설계하는 역할이다.

[채널 정보]
- 채널: {channel_name} ({channel})
- 오늘 톤: {weekday_angle}
- 타겟: 50대 이상 시청자

[이슈 정보]
- 카테고리: {category}
- 제목: {title}
- 요약: {summary}
- 출처: {link}

[중요 규칙 - 이것만큼은 반드시 지켜라]
❌ 숫자/지표/수치는 '이유 설명' 용도로만! 핵심포인트의 중심으로 삼지 마라
❌ 기사에 나온 사실을 요약하거나 나열하지 마라
❌ "~으로 전망된다", "~라고 분석된다" 같은 기사 문체 절대 금지
❌ "~이 중요하다", "~을 살펴볼 필요가 있다" 같은 해설 리포트 문체 금지
❌ 과장/공포 조장 금지

[문체 규칙 - 가장 중요]
핵심포인트는 "경제를 설명하는 문장"이 아니라
"시청자가 겪게 될 상황을 먼저 떠올리게 하는 문장"으로 작성할 것

각 포인트는:
1. "이 뉴스가 내 일상에서 언제, 어디서, 어떻게 느껴질지"를 먼저 말하고
2. 그 다음에 이유를 덧붙일 것

[좋은 예시 vs 나쁜 예시]
❌ 나쁨: "환율이 1,470원 안팎으로 예상된다"
❌ 나쁨: "일본 금리 인상은 환율에 영향을 미칠 수 있다"
❌ 나쁨: "일본 경제 변화는 수출입 시장에 영향을 미치므로 관련 기업 동향을 확인해보는 것이 중요하다"

⭕ 좋음: "환율 숫자보다 중요한 건, 이 수준이 '일상화'되고 있다는 점이다"
⭕ 좋음: "일본 금리 인상 소식은 당장 환율 숫자보다, 다음 달 생활비 변동으로 체감될 가능성이 크다"
⭕ 좋음: "수입물가가 오르면 가장 먼저 체감되는 지출 항목은 따로 있다"

[출력 형식 - 정확히 이 형태로]
핵심포인트 (총 5개):
1. (판단 유도 문장)
2. (판단 유도 문장)
3. (판단 유도 문장)
4. (판단 유도 문장)
5. (판단 유도 문장)

오프닝 감정유도 (불안/의문):
-

엔딩 루틴예고:
-

썸네일 문구 3안 (사건명X, 시청자상태O):
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
        core_points, shorts, thumb = _parse_llm_response(text)

        brief = f"""[대본 지시문]
- 분량: 7~10분 (3,000~3,800자)
- 요일: {weekday_angle}
- 관점: "내 돈/내 생활"에 미치는 영향
- 구조: 서론(불안/의문) → 본론(핵심 정리) → 전망 → 마무리(루틴 예고)
- 금지: 속보 요약, 과장, 공포 조장"""

        print(f"[NEWS] LLM 핵심포인트 생성 완료 (모델: {model})")
        return core_points, brief, shorts, thumb

    except Exception as e:
        print(f"[NEWS] LLM 호출 실패: {e}")
        return "", "", "", ""
