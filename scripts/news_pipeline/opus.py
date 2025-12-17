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
핵심포인트는 "정보 전달"이 아니라
"시청자가 스스로 해당 여부를 판단하게 만드는 문장"으로 작성할 것

각 포인트에는 반드시:
- '누가' 체감하는지 (이미 대출 있는 사람? 결정 미루던 사람?)
- '언제' 체감하는지 (이번 달? 다음 달?)
- '어떤 상황에서' 체감하는지 (마트에서? 통장 확인할 때?)
가 드러나야 함

[어미 규칙 - 경제 리포트 언어 금지]
❌ "~할 수 있다", "~가능성이 커진다" → 경제 리포트 언어
⭕ "~하게 된다", "~로 이어진다" → 생활 코치 언어

❌ "주의해야 한다", "살펴봐야 한다" → 해설자 언어
⭕ "이미 시작되고 있다", "나타나고 있다" → 현장 관찰자 언어

[좋은 예시 vs 나쁜 예시]
❌ 나쁨: "대출 이자 부담이 줄어들 수 있다"
⭕ 좋음: "이미 대출을 받은 사람보다, '아직 결정을 미루고 있던 사람'에게 이번 금리 하락 소식이 더 크게 다가올 수 있다"

❌ 나쁨: "투자자들에게 심리적 안정을 제공할 수 있다"
⭕ 좋음: "'시장이 안정되고 있다'는 신호는 '급하게 움직이지 않아도 된다'는 힌트로 볼 수 있다"

❌ 나쁨: "수입 물가가 오를 가능성이 있다"
⭕ 좋음: "환율 부담이 커지면, 뉴스보다 먼저 체감되는 건 마트에서 장바구니 가격이 될 가능성이 크다"

❌ 나쁨: "소비 패턴에 영향을 미칠 수 있다"
⭕ 좋음: "이런 변화가 반복되면, 자연스럽게 '이번 달은 조금 덜 쓰자'는 판단이 늘어날 수밖에 없다"

❌ 나쁨: "재정적 결정이 중요해질 수 있다"
⭕ 좋음: "금리와 환율이 엇갈릴 때는, 지금 당장 움직이기보다 '결정을 미루는 것도 선택'이 될 수 있다"

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
