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

[핵심 원칙 - 반드시 지켜라]
❌ 기사 요약 금지 - 뉴스 앵커처럼 사실 나열하지 마라
❌ 과장/공포 조장 금지
⭕ "내 돈/내 생활에 어떤 영향?" 관점으로만 정리
⭕ 시청자가 "그래서 나는 뭘 해야 해?"를 알 수 있게

[출력 형식 - 정확히 이 형태로]
핵심포인트 (총 5개):
1. (내 돈/생활 영향 관점)
2. (내 돈/생활 영향 관점)
3. (내 돈/생활 영향 관점)
4. (내 돈/생활 영향 관점)
5. (내 돈/생활 영향 관점)

오프닝 감정유도 (불안/의문):
-

엔딩 루틴예고:
-

썸네일 문구 3안 (사건명X, 시청자상태O):
1.
2.
3. """

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

        core_points = text
        brief = f"""[대본 지시문]
- 분량: 7~10분 (3,000~3,800자)
- 요일: {weekday_angle}
- 관점: "내 돈/내 생활"에 미치는 영향
- 구조: 서론(불안/의문) → 본론(핵심 정리) → 전망 → 마무리(루틴 예고)
- 금지: 속보 요약, 과장, 공포 조장"""
        shorts = ""
        thumb = ""

        print(f"[NEWS] LLM 핵심포인트 생성 완료 (모델: {model})")
        return core_points, brief, shorts, thumb

    except Exception as e:
        print(f"[NEWS] LLM 호출 실패: {e}")
        return "", "", "", ""
