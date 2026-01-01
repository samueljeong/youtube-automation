"""
GPT-5.1 기반 대본 자동 생성 모듈

2025-01 신규:
- 4개 공신력 있는 소스에서 수집한 자료 기반
- 20,000자 분량의 역사 다큐멘터리 대본 생성
- 학술적 신중함 + 객관적 서술 스타일
"""

import os
from typing import Dict, Any, Optional

# GPT-5.1 Responses API 사용
from openai import OpenAI


# ============================================================
# 대본 설정
# ============================================================
SCRIPT_TARGET_LENGTH = 20000  # 목표 글자수
SCRIPT_MIN_LENGTH = 18000     # 최소 글자수
SCRIPT_MAX_LENGTH = 22000     # 최대 글자수

# 한국어 TTS 기준: 910자 ≈ 1분
# 20,000자 ≈ 22분 영상


# ============================================================
# 대본 스타일 프롬프트 (광개토대왕 대본 스타일 기반)
# ============================================================
SCRIPT_STYLE_PROMPT = """당신은 한국사 전문 유튜브 채널의 대본 작가입니다.
아래 수집된 자료를 바탕으로 역사 다큐멘터리 나레이션 대본을 작성하세요.

════════════════════════════════════════
[대본 스타일 - 필수 준수]
════════════════════════════════════════

1. 학술적 신중함
   ✅ 허용 표현:
   - "~로 보는 견해가 있습니다"
   - "~에 대해서는 논의가 있습니다"
   - "~로 전해집니다"
   - "~로 기록되어 있습니다"
   - "~로 추정됩니다"
   - "아직 완전한 결론이 나왔다고 보기는 어렵습니다"

   ❌ 금지 표현:
   - 단정적 표현: "~입니다", "~였습니다" (확실한 사실만)
   - 과장: "놀랍게도", "충격적이게도", "믿기 어렵지만"

2. 출처 명시
   ✅ 허용:
   - "삼국사기에 따르면"
   - "비문에는 ~ 기록되어 있습니다"
   - "한국민족문화대백과사전에 의하면"
   - "문화재청 자료에 따르면"

3. 감정/판단 배제
   ❌ 절대 금지:
   - 감정: "위대하다", "안타깝다", "놀랍다", "흥미롭다"
   - 민족주의: "자랑스러운", "찬란한", "민족의 자존심"
   - 교훈: "~해야 합니다", "~를 기억해야 합니다"
   - 호칭: "여러분", "우리"

4. 문장 스타일
   - 간결한 문장 (한 문장 50자 이내 권장)
   - 서술형 종결 (~합니다, ~입니다)
   - 질문형 도입 가능 ("왜 이런 일이 벌어졌을까요")

════════════════════════════════════════
[대본 구조]
════════════════════════════════════════

1. [도입부] 5% (~1,000자)
   - 질문형 오프닝으로 시작
   - 이 에피소드에서 다룰 핵심 질문 제시
   - 예: "서기 391년, 고구려에 열여덟 살의 젊은 왕이 즉위합니다..."

2. [배경 설명] 15% (~3,000자)
   - 시대적 맥락 설명
   - 이전 사건과의 연결
   - 주요 인물/세력 소개

3. [본론] 60% (~12,000자)
   - 사건의 전개를 시간순/논리순으로 서술
   - 각 사건마다 출처 명시
   - 학술적 논쟁이 있는 부분은 여러 견해 소개
   - 구체적인 연도, 지명, 인물명 포함

4. [논쟁/해석] 10% (~2,000자)
   - 학계의 다양한 해석 소개
   - "~로 보는 견해와 ~로 보는 견해가 있습니다"
   - 결론을 내리지 않고 열린 질문으로 마무리

5. [마무리] 10% (~2,000자)
   - 이 주제의 역사적 의의 (감정 없이)
   - 후대에 미친 영향
   - 다음 에피소드 예고
   - 예: "다음 시간에는 ~에 대해 살펴보겠습니다"

════════════════════════════════════════
[분량 규정]
════════════════════════════════════════
- 목표: 20,000자 (18,000~22,000자)
- 너무 짧으면 내용을 더 상세히
- 너무 길면 핵심만 남기고 압축
- TTS로 읽었을 때 약 22분 분량

════════════════════════════════════════
[최종 체크리스트]
════════════════════════════════════════
□ 수집된 자료에 있는 내용만 사용했는가?
□ 출처가 명시되었는가?
□ 감정적/판단적 표현이 없는가?
□ 민족주의적 표현이 없는가?
□ 학술적 논쟁은 여러 견해를 소개했는가?
□ 다음 에피소드 예고가 있는가?
□ 분량이 18,000~22,000자인가?
"""


def generate_script_gpt51(
    era_name: str,
    episode: int,
    total_episodes: int,
    title: str,
    topic: str,
    full_content: str,
    sources: list,
    next_episode_info: Dict[str, Any] = None,
) -> Dict[str, Any]:
    """
    GPT-5.1로 20,000자 대본 생성

    Args:
        era_name: 시대명 (예: "삼국시대")
        episode: 에피소드 번호
        total_episodes: 시대 총 에피소드 수
        title: 에피소드 제목
        topic: 주제
        full_content: 수집된 자료 전체 내용
        sources: 출처 URL 목록
        next_episode_info: 다음 에피소드 정보 (선택)

    Returns:
        {
            "script": 생성된 대본,
            "length": 글자수,
            "model": 사용 모델,
            "cost": 예상 비용,
            "error": 에러 메시지 (실패 시)
        }
    """
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        return {"error": "OPENAI_API_KEY 환경변수가 설정되지 않았습니다."}

    if not full_content or len(full_content) < 1000:
        return {"error": f"수집된 자료가 부족합니다. (현재: {len(full_content)}자)"}

    # 다음 에피소드 정보
    next_info_text = ""
    if next_episode_info:
        if next_episode_info.get("type") == "next_era":
            next_info_text = f"""
[다음 에피소드 정보]
- 다음 시대: {next_episode_info.get('era_name', '')}
- 다음 주제: {next_episode_info.get('title', '')}
- 예고 문구 예시: "다음 시간에는 {next_episode_info.get('era_name', '')}의 이야기를 시작합니다."
"""
        elif next_episode_info.get("type") == "next_episode":
            next_info_text = f"""
[다음 에피소드 정보]
- 다음 화: {era_name} {next_episode_info.get('era_episode', episode + 1)}화
- 다음 주제: {next_episode_info.get('title', '')}
- 예고 문구 예시: "다음 시간에는 {next_episode_info.get('title', '')}에 대해 살펴보겠습니다."
"""
        else:
            next_info_text = """
[다음 에피소드 정보]
- 시리즈 마지막 에피소드입니다.
- 전체 시리즈를 정리하며 마무리하세요.
"""

    # 출처 목록
    source_list = "\n".join([f"  - {s}" for s in sources[:10]]) if sources else "  (없음)"

    # 사용자 프롬프트 구성
    user_prompt = f"""
════════════════════════════════════════
[에피소드 정보]
════════════════════════════════════════
- 시리즈: 한국사 - {era_name}
- 현재: {episode}/{total_episodes}화
- 제목: {title}
- 주제: {topic}

════════════════════════════════════════
[수집된 자료]
════════════════════════════════════════
{full_content}

════════════════════════════════════════
[출처 목록]
════════════════════════════════════════
{source_list}

{next_info_text}

════════════════════════════════════════
[작성 지시]
════════════════════════════════════════
위 자료를 바탕으로 {SCRIPT_TARGET_LENGTH:,}자 분량의 나레이션 대본을 작성하세요.
- 자료에 없는 내용은 추가하지 마세요.
- 학술적 신중함을 유지하세요.
- 출처를 명시하세요.
"""

    try:
        client = OpenAI(api_key=api_key)

        print(f"[SCRIPT] GPT-5.1 대본 생성 시작...")
        print(f"[SCRIPT] 입력 자료: {len(full_content):,}자")

        # GPT-5.1 Responses API 호출
        response = client.responses.create(
            model="gpt-5.1",
            input=[
                {
                    "role": "system",
                    "content": [{"type": "input_text", "text": SCRIPT_STYLE_PROMPT}]
                },
                {
                    "role": "user",
                    "content": [{"type": "input_text", "text": user_prompt}]
                }
            ],
            temperature=0.7,
        )

        # 결과 추출
        if getattr(response, "output_text", None):
            script = response.output_text.strip()
        else:
            text_chunks = []
            for item in getattr(response, "output", []) or []:
                for content in getattr(item, "content", []) or []:
                    if getattr(content, "type", "") == "text":
                        text_chunks.append(getattr(content, "text", ""))
            script = "\n".join(text_chunks).strip()

        script_length = len(script)

        # 토큰 계산 (한국어 약 2자 = 1토큰)
        input_tokens = (len(SCRIPT_STYLE_PROMPT) + len(user_prompt)) // 2
        output_tokens = script_length // 2
        cost = (input_tokens * 0.001 / 1000) + (output_tokens * 0.003 / 1000)

        print(f"[SCRIPT] 대본 생성 완료: {script_length:,}자")
        print(f"[SCRIPT] 예상 비용: ${cost:.4f}")

        # 분량 체크
        if script_length < SCRIPT_MIN_LENGTH:
            print(f"[SCRIPT] ⚠️ 분량 부족 ({script_length:,}자 < {SCRIPT_MIN_LENGTH:,}자)")
        elif script_length > SCRIPT_MAX_LENGTH:
            print(f"[SCRIPT] ⚠️ 분량 초과 ({script_length:,}자 > {SCRIPT_MAX_LENGTH:,}자)")

        return {
            "script": script,
            "length": script_length,
            "model": "gpt-5.1",
            "cost": cost,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
        }

    except Exception as e:
        print(f"[SCRIPT] GPT-5.1 호출 실패: {e}")
        return {"error": str(e)}


def generate_script_with_retry(
    era_name: str,
    episode: int,
    total_episodes: int,
    title: str,
    topic: str,
    full_content: str,
    sources: list,
    next_episode_info: Dict[str, Any] = None,
    max_retries: int = 2,
) -> Dict[str, Any]:
    """
    대본 생성 (분량 부족 시 재시도)

    분량이 SCRIPT_MIN_LENGTH 미만이면 재시도
    """
    for attempt in range(max_retries + 1):
        result = generate_script_gpt51(
            era_name=era_name,
            episode=episode,
            total_episodes=total_episodes,
            title=title,
            topic=topic,
            full_content=full_content,
            sources=sources,
            next_episode_info=next_episode_info,
        )

        if "error" in result:
            return result

        script_length = result.get("length", 0)

        # 분량 충족 시 반환
        if script_length >= SCRIPT_MIN_LENGTH:
            return result

        # 분량 부족 시 재시도
        if attempt < max_retries:
            print(f"[SCRIPT] 분량 부족으로 재시도 ({attempt + 1}/{max_retries})...")
            # 재시도 시 더 긴 분량 요청하는 프롬프트 추가 가능

    return result
