"""
GPT-5.2 기반 대본 자동 생성 모듈

2025-01 신규:
- 4개 공신력 있는 소스에서 수집한 자료 기반
- 20,000자 분량의 역사 다큐멘터리 대본 생성
- 학술적 신중함 + 객관적 서술 스타일

2025-01 업데이트:
- GPT-5.1 → GPT-5.2 모델 업그레이드
- 비용: $1.75/1M input, $14/1M output
- Prompt Caching 적용 (System Prompt 90% 할인)
"""

import os
from typing import Dict, Any, Optional

# GPT-5.2 Responses API 사용
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
# ★★★ MASTER SYSTEM PROMPT (Prompt Caching 최적화) ★★★
# ============================================================
# 이 프롬프트는 모든 API 호출에서 System Prompt로 사용됨
# → 90% 캐싱 할인 적용 (동일한 System Prompt 재사용)
# ============================================================
MASTER_SYSTEM_PROMPT = """당신은 한국어 역사 다큐 유튜브 채널의 최상급 대본 작가입니다.
목표는 시청자가 끝까지 듣게 만드는 나레이션 대본을 작성하는 것입니다.

아래 "입력 정보"만을 근거로 하되, 사실/추정/논쟁을 구분해서 신뢰도 높게 쓰세요.
출력은 오직 대본 본문 텍스트만 제공하세요. (설명, 메모, 목록, 제목 라벨, 특수기호, 구분선, "BODY 시작" 같은 메타 문구 절대 금지)

════════════════════════════════════════
★ 절대 금지 사항 (모든 파트 공통)
════════════════════════════════════════
• "한국민족문화대백과사전은 ~라고 설명한다" 같은 출처명 반복 문장 금지
• "정리하면/마무리하면/이제 정리한다" 같은 메타 진행 문장 남발 금지
• "기록되어 있다/언급된다/설명된다" 같은 보고서 종결어 반복 금지
• 불확실한 내용을 확정적으로 단정 금지
  → 불확실하면 "~로 보기도 합니다 / ~라는 견해도 있습니다"로 처리
• 표/목차/번호/불릿 금지 (순수 문장 대본)
• 감정적 과장: "놀랍게도", "충격적이게도", "위대한" 등 금지
• 민족주의: "자랑스러운", "찬란한", "민족의 자존심" 등 금지
• 교훈형: "~해야 합니다", "~를 기억해야 합니다" 금지
• 호칭: "여러분", "우리" 금지

════════════════════════════════════════
★ 방송 원고 스타일 규칙 (모든 파트 공통)
════════════════════════════════════════
• 문장 호흡: 한 문장 15~35자 중심, 긴 문장은 두 문장으로 쪼개기
• 장면 전환: 문단 시작마다 "겨울의 평양성.", "강을 건넙니다." 같은 시각적 전환
• 사건 4박자: "왜→어떻게→결과→다음 사건 연결"
• 출처 반복 금지: "~에 따르면", "~라고 설명한다" ❌
• 보고서 종결어 금지: "기록되어 있다", "언급된다" ❌
• 감정 표현 금지, 객관적 서술
• 서술형 종결: ~합니다, ~입니다
• 사실 기반: 수집된 자료의 내용만 사용 (창작 금지)

════════════════════════════════════════
★ 인트로 기법 (Cold Open + Open Loop)
════════════════════════════════════════
【Cold Open】 가장 극적인 순간부터 시작. 배경 설명 없이 바로 사건 속으로.
❌ "오늘은 광개토대왕에 대해 알아보겠습니다"
✅ "서기 391년, 열여덟 살의 왕이 첫 출정에 나섭니다."

【Open Loop】 첫 30초 안에 해결되지 않은 질문을 던지세요.
✅ "왜 이 어린 왕은 즉위하자마자 전쟁에 나섰을까요?"
✅ "기록에는 이렇게 적혀있습니다. 하지만 무언가 이상합니다."

【Curiosity Gap】 "알려진 사실"과 "숨겨진 진실" 사이의 간극
✅ "삼국사기에는 이렇게 기록되어 있습니다. 그런데 광개토대왕비에는..."

【Stakes Reveal】 이 사건이 왜 중요한지 먼저 알려주기
✅ "이 전투의 결과가 동아시아의 판도를 바꾸게 됩니다."

【Pattern Interrupt】 시청자의 예상을 깨는 문장
✅ "왕이 아니었습니다. 적어도, 아직은."

════════════════════════════════════════
★ 리텐션 훅 (2,000자마다 삽입)
════════════════════════════════════════
✅ "그런데 여기서 한 가지 의문이 생깁니다."
✅ "하지만 여기서 이상한 점이 있습니다."
✅ "이 상황이 어떻게 전개되었을까요?"
✅ "이제 본격적인 이야기가 시작됩니다."
✅ "상황은 점점 복잡해집니다."
✅ "하지만 이것은 시작에 불과했습니다."
✅ "결정적인 순간이 다가옵니다."
✅ "이제 모든 것이 달라지려 합니다."
✅ "그러나 상황은 여기서 반전됩니다."
✅ "이 결정이 어떤 결과를 가져왔을까요?"

════════════════════════════════════════
★ 에피소드 연결 (API 장점 활용)
════════════════════════════════════════
【첫 화】 "한국사의 시작, 고조선 이야기를 시작합니다."
【2화 이후】 "지난 시간, [이전 내용 한 줄 요약]... 오늘은 그 이후 이야기입니다."
【시대 첫 화】 "[이전 시대]가 저물고 새로운 시대가 열립니다."

★ 단, "지난 시간에" 문구는 첫 2-3문장에서만 사용하고 빠르게 본론으로 전환

════════════════════════════════════════
★ 마무리 훅 (Open Loop)
════════════════════════════════════════
✅ "이 선택이 이후 역사를 어떻게 바꿨을까요?"
✅ "다음 시간에는 더 놀라운 이야기가 기다리고 있습니다."
✅ "과연 그들의 결정은 옳았을까요?"

대본만 작성하세요. 다른 설명 없이 나레이션 대본만 출력하세요."""

# 이전 버전 호환성을 위한 별칭
SCRIPT_STYLE_PROMPT = MASTER_SYSTEM_PROMPT


def generate_script_by_parts(
    era_name: str,
    episode: int,
    total_episodes: int,
    title: str,
    topic: str,
    full_content: str,
    sources: list,
    next_episode_info: Dict[str, Any] = None,
    prev_episode_info: Dict[str, Any] = None,  # ★ 이전 에피소드 정보 (API 장점 활용)
    series_context: Dict[str, Any] = None,     # ★ 시리즈 전체 맥락 (API 장점 활용)
) -> Dict[str, Any]:
    """
    GPT-5.2로 파트별 대본 생성 (API 장점 극대화)

    ★★★ API 활용 장점 ★★★
    - prev_episode_info: 이전 에피소드 내용 (자연스러운 연결)
    - next_episode_info: 다음 에피소드 예고 (기대감 조성)
    - series_context: 시리즈 전체 맥락 (위치 인식, 흐름 파악)

    파트 구조:
    1. 인트로 (도입부) - 1,500자 ★ 강조
       - 이전 에피소드 연결 ("지난 시간에...")
    2. 배경 설명 - 3,000자
    3. 본론 - 12,000자
    4. 마무리 - 3,500자
       - 다음 에피소드 예고 (자연스러운 연결)

    총 20,000자
    """
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        return {"error": "OPENAI_API_KEY 환경변수가 설정되지 않았습니다."}

    if not full_content or len(full_content) < 500:
        return {"error": f"수집된 자료가 부족합니다. (현재: {len(full_content)}자)"}

    source_list = "\n".join([f"  - {s}" for s in sources[:10]]) if sources else "(없음)"

    # 다음 에피소드 예고 텍스트
    next_preview = _build_next_preview(next_episode_info, era_name)

    # ★ 이전 에피소드 컨텍스트 (API 장점 활용)
    prev_context = _build_prev_context(prev_episode_info, era_name)

    # ★ 시리즈 전체 컨텍스트 (API 장점 활용)
    series_position = _build_series_position(series_context, era_name, episode, total_episodes)

    total_cost = 0.0
    all_parts = []

    print(f"[SCRIPT] === 파트별 대본 생성 시작 (API 컨텍스트 활용) ===")
    print(f"[SCRIPT] 제목: {title}")
    print(f"[SCRIPT] 시리즈 위치: {era_name} {episode}/{total_episodes}화")
    print(f"[SCRIPT] 입력 자료: {len(full_content):,}자")
    print(f"[SCRIPT] 이전 에피소드 연결: {'있음' if prev_episode_info else '없음(첫 화)'}")
    print(f"[SCRIPT] 다음 에피소드 예고: {'있음' if next_episode_info else '없음(마지막 화)'}")

    try:
        client = OpenAI(api_key=api_key)

        # ========================================
        # Part 1: 인트로 (도입부) - 1,500자 ★★★ 최강 강화
        # ========================================
        # ★ Prompt Caching: 스타일 규칙은 MASTER_SYSTEM_PROMPT에 있음
        print(f"[SCRIPT] Part 1: 인트로 생성 중 (Prompt Caching 적용)...")
        intro_prompt = f"""[파트: 인트로 - 1,500자]

[에피소드 정보]
- 시리즈: 한국사 - {era_name}
- 현재: {episode}/{total_episodes}화
- 제목: {title}
- 주제: {topic}

{series_position}

{prev_context}

[수집된 자료 중 핵심 부분]
{full_content[:3000]}

════════════════════════════════════════
[인트로 구조]
════════════════════════════════════════
1. 오프닝 훅 (0-300자) - Cold Open + Stakes Reveal
2. 미스터리 제시 (300-600자) - Open Loop + Curiosity Gap
3. Stakes 암시 (600-900자) - 역사적 중요성
4. 에피소드 로드맵 (900-1500자) - 이 영상에서 다룰 내용

★ 스타일 규칙은 System Prompt 참조
★ 분량: 약 1,500자"""

        intro_result = _call_gpt52_cached(client, intro_prompt)
        if "error" in intro_result:
            return intro_result
        all_parts.append(intro_result["text"])
        total_cost += intro_result["cost"]
        print(f"[SCRIPT] Part 1 완료: {len(intro_result['text']):,}자")

        # ========================================
        # Part 2: 배경 설명 - 3,000자 + 리텐션 훅
        # ========================================
        # ★ Prompt Caching: 스타일 규칙은 MASTER_SYSTEM_PROMPT에 있음
        print(f"[SCRIPT] Part 2: 배경 설명 생성 중 (Prompt Caching 적용)...")
        background_prompt = f"""[파트: 배경 설명 - 3,000자]

[이전 파트 마지막]
{intro_result['text'][-500:]}

[수집된 자료]
{full_content[:5000]}

════════════════════════════════════════
[배경 설명 구조]
════════════════════════════════════════
1. 시대적 맥락 (1,000자) - 시대 상황을 이야기처럼
2. 인물/세력 소개 (1,000자) - 캐릭터처럼 생생하게
3. 이전 사건과 연결 (1,000자) - 인과관계를 이야기로

★ 리텐션 훅 2개 삽입 (1,000자/2,000자 지점)
★ 스타일 규칙은 System Prompt 참조
★ 분량: 약 3,000자"""

        bg_result = _call_gpt52_cached(client, background_prompt)
        if "error" in bg_result:
            return bg_result
        all_parts.append(bg_result["text"])
        total_cost += bg_result["cost"]
        print(f"[SCRIPT] Part 2 완료: {len(bg_result['text']):,}자")

        # ========================================
        # Part 3-1: 본론 전반부 - 6,000자 + 리텐션 훅
        # ========================================
        # ★ Prompt Caching: 스타일 규칙은 MASTER_SYSTEM_PROMPT에 있음
        print(f"[SCRIPT] Part 3-1: 본론 전반부 생성 중 (Prompt Caching 적용)...")
        body1_prompt = f"""[파트: 본론 전반부 - 6,000자]

[이전 파트 마지막]
{bg_result['text'][-500:]}

[수집된 자료]
{full_content}

[출처 목록]
{source_list}

════════════════════════════════════════
[본론 전반부 구조]
════════════════════════════════════════
- 시간순 전개 (연도/시기는 자연스럽게)
- 인물의 행동과 결정 중심
- 원인 → 전개 → 결과를 드라마틱하게

★ 리텐션 훅 3개 삽입 (2,000자/4,000자/6,000자 지점)
★ 스타일 규칙은 System Prompt 참조
★ 분량: 약 6,000자"""

        body1_result = _call_gpt52_cached(client, body1_prompt)
        if "error" in body1_result:
            return body1_result
        all_parts.append(body1_result["text"])
        total_cost += body1_result["cost"]
        print(f"[SCRIPT] Part 3-1 완료: {len(body1_result['text']):,}자")

        # ★ Prompt Caching: 스타일 규칙은 MASTER_SYSTEM_PROMPT에 있음
        print(f"[SCRIPT] Part 3-2: 본론 후반부 생성 중 (Prompt Caching 적용)...")
        body2_prompt = f"""[파트: 본론 후반부 - 6,000자]

[이전 파트 마지막]
{body1_result['text'][-500:]}

[수집된 자료 후반부]
{full_content[len(full_content)//2:]}

[출처 목록]
{source_list}

════════════════════════════════════════
[본론 후반부 구조]
════════════════════════════════════════
1. 사건 전개 계속 (3,000자) - 긴장감 유지
2. 클라이맥스와 결말 (2,000자) - 가장 극적인 순간
3. 열린 질문 (1,000자) - 시청자가 생각해볼 여지

★ 리텐션 훅 3개 삽입 (2,000자/4,000자/6,000자 지점)
★ 클라이맥스: 리듬 빠르게, 장면 선명하게
★ 스타일 규칙은 System Prompt 참조
★ 분량: 약 6,000자"""

        body2_result = _call_gpt52_cached(client, body2_prompt)
        if "error" in body2_result:
            return body2_result
        all_parts.append(body2_result["text"])
        total_cost += body2_result["cost"]
        print(f"[SCRIPT] Part 3-2 완료: {len(body2_result['text']):,}자")

        # ========================================
        # Part 4: 마무리 - 3,500자 + 다음 예고
        # ========================================
        # ★ Prompt Caching: 스타일 규칙은 MASTER_SYSTEM_PROMPT에 있음
        print(f"[SCRIPT] Part 4: 마무리 생성 중 (Prompt Caching 적용)...")
        ending_prompt = f"""[파트: 마무리 - 3,500자]

[이전 파트 마지막]
{body2_result['text'][-500:]}

{next_preview}

════════════════════════════════════════
[마무리 구조]
════════════════════════════════════════
1. 역사적 영향 (1,500자) - "그로부터 ~년 후..."
2. 열린 질문 (1,000자) - 시청자가 생각해볼 질문
3. 다음 에피소드 예고 (1,000자) - Open Loop로 마무리

★ 여운: "그가 남긴 것"을 한 문장으로 정리
★ 다음 영상 클릭 유도 (Open Loop)
★ 스타일 규칙은 System Prompt 참조
★ 분량: 약 3,500자"""

        ending_result = _call_gpt52_cached(client, ending_prompt)
        if "error" in ending_result:
            return ending_result
        all_parts.append(ending_result["text"])
        total_cost += ending_result["cost"]
        print(f"[SCRIPT] Part 4 완료: {len(ending_result['text']):,}자")

        # 전체 대본 합치기
        full_script = "\n\n".join(all_parts)
        script_length = len(full_script)

        print(f"[SCRIPT] === 파트별 대본 생성 완료 ===")
        print(f"[SCRIPT] 총 분량: {script_length:,}자")
        print(f"[SCRIPT] 총 비용: ${total_cost:.4f}")

        # YouTube 설명란용 출처 텍스트 생성
        youtube_sources = _format_sources_for_youtube(sources)

        # ========================================
        # YouTube SEO 메타데이터 생성 ★ 추가
        # ========================================
        print(f"[SCRIPT] YouTube SEO 메타데이터 생성 중...")
        global_ep = series_context.get("global_episode") if series_context else episode
        seo_result = _generate_youtube_seo(
            client=client,
            era_name=era_name,
            episode=episode,
            total_episodes=total_episodes,
            title=title,
            topic=topic,
            intro_text=all_parts[0] if all_parts else "",
            global_episode=global_ep,  # ★ 전체 시리즈 번호 전달
        )
        total_cost += seo_result.get("cost", 0)

        return {
            "script": full_script,
            "length": script_length,
            "model": "gpt-5.2",
            "cost": total_cost,
            "parts": {
                "intro": len(all_parts[0]) if len(all_parts) > 0 else 0,
                "background": len(all_parts[1]) if len(all_parts) > 1 else 0,
                "body1": len(all_parts[2]) if len(all_parts) > 2 else 0,
                "body2": len(all_parts[3]) if len(all_parts) > 3 else 0,
                "ending": len(all_parts[4]) if len(all_parts) > 4 else 0,
            },
            "youtube_sources": youtube_sources,  # YouTube 설명란용 출처
            # ★ YouTube SEO 메타데이터
            "youtube_title": seo_result.get("title", title),
            "thumbnail_text": seo_result.get("thumbnail_text", ""),
        }

    except Exception as e:
        print(f"[SCRIPT] 파트별 생성 실패: {e}")
        return {"error": str(e)}


def _call_gpt52_cached(client, user_prompt: str) -> Dict[str, Any]:
    """GPT-5.2 API 호출 (Prompt Caching 적용)

    ★★★ Prompt Caching 최적화 ★★★
    - System Prompt (MASTER_SYSTEM_PROMPT): 캐시됨 → 90% 할인
    - User Prompt: 정가

    GPT-5.2 가격:
    - Input (정가): $1.75 / 1M tokens
    - Input (캐시): $0.175 / 1M tokens (90% 할인)
    - Output: $14 / 1M tokens
    """
    try:
        # System/User 메시지 구조로 호출 (캐싱 최적화)
        response = client.responses.create(
            model="gpt-5.2",
            input=[
                {
                    "role": "system",
                    "content": [{"type": "input_text", "text": MASTER_SYSTEM_PROMPT}]
                },
                {
                    "role": "user",
                    "content": [{"type": "input_text", "text": user_prompt}]
                }
            ],
            temperature=0.7,
        )

        # 결과 추출
        text = response.output_text if hasattr(response, 'output_text') else ""

        if not text:
            # 대체 방식
            for item in getattr(response, "output", []) or []:
                for content in getattr(item, "content", []) or []:
                    if getattr(content, "type", "") == "text":
                        text += getattr(content, "text", "")

        # ★★★ 비용 계산 (Prompt Caching 적용) ★★★
        # 한국어 약 2자 = 1토큰
        system_tokens = len(MASTER_SYSTEM_PROMPT) // 2  # 캐시됨 (90% 할인)
        user_tokens = len(user_prompt) // 2              # 정가
        output_tokens = len(text) // 2

        # System Prompt: $0.175/1M (90% 할인), User Prompt: $1.75/1M, Output: $14/1M
        cost = (
            (system_tokens * 0.175 / 1_000_000) +   # 캐시된 System Prompt
            (user_tokens * 1.75 / 1_000_000) +      # User Prompt (정가)
            (output_tokens * 14 / 1_000_000)        # Output
        )

        return {
            "text": text.strip(),
            "cost": cost,
            "tokens": {
                "system_cached": system_tokens,
                "user": user_tokens,
                "output": output_tokens,
            }
        }

    except Exception as e:
        return {"error": str(e)}


def _call_gpt52(client, prompt: str) -> Dict[str, Any]:
    """GPT-5.2 API 호출 (이전 버전 호환용 - 캐싱 미적용)

    ※ 새 코드는 _call_gpt52_cached() 사용 권장
    """
    try:
        response = client.responses.create(
            model="gpt-5.2",
            input=prompt,
        )

        text = response.output_text if hasattr(response, 'output_text') else ""

        if not text:
            for item in getattr(response, "output", []) or []:
                for content in getattr(item, "content", []) or []:
                    if getattr(content, "type", "") == "text":
                        text += getattr(content, "text", "")

        input_tokens = len(prompt) // 2
        output_tokens = len(text) // 2
        cost = (input_tokens * 1.75 / 1_000_000) + (output_tokens * 14 / 1_000_000)

        return {"text": text.strip(), "cost": cost}

    except Exception as e:
        return {"error": str(e)}


# 이전 버전 호환성을 위한 별칭
_call_gpt51 = _call_gpt52


def _build_next_preview(next_info: Dict[str, Any], era_name: str) -> str:
    """다음 에피소드 예고 텍스트"""
    if not next_info:
        return ""

    if next_info.get("type") == "next_era":
        return f"""[다음 에피소드 정보]
- 다음 시대: {next_info.get('era_name', '')}
- 다음 주제: {next_info.get('title', '')}
- 예고: "다음 시간에는 {next_info.get('era_name', '')}의 이야기를 시작합니다. {next_info.get('title', '')}에 대해 알아보겠습니다."
"""
    elif next_info.get("type") == "next_episode":
        return f"""[다음 에피소드 정보]
- 다음 화: {era_name} {next_info.get('era_episode', '')}화
- 다음 주제: {next_info.get('title', '')}
- 예고: "다음 시간에는 {next_info.get('title', '')}에 대해 살펴보겠습니다."
"""
    else:
        return """[시리즈 마지막]
- 시리즈 완결
- 전체 시리즈를 정리하며 마무리
"""


def _build_prev_context(prev_info: Dict[str, Any], era_name: str) -> str:
    """
    이전 에피소드 컨텍스트 생성 (API 장점 활용)

    이전 에피소드 정보를 받아서 자연스러운 연결을 위한 컨텍스트 생성
    """
    if not prev_info:
        return """[이전 에피소드]
- 첫 에피소드입니다.
- 시리즈 시작 인사로 시작하세요.
- 예: "한국사의 시작, 고조선 이야기를 시작합니다."
"""

    if prev_info.get("type") == "same_era":
        return f"""[이전 에피소드 - {era_name} 연속]
- 이전 화: {prev_info.get('title', '')}
- 이전 내용 요약: {prev_info.get('summary', '')}
- 연결 방식: "지난 시간, {prev_info.get('summary', '')}... 오늘은 그 이후 이야기입니다."
"""
    elif prev_info.get("type") == "new_era":
        return f"""[새로운 시대 시작]
- 이전 시대: {prev_info.get('prev_era_name', '')}
- 이전 시대 마지막 사건: {prev_info.get('summary', '')}
- 연결 방식: "{prev_info.get('prev_era_name', '')}가 저물고, 새로운 시대가 열립니다..."
"""
    else:
        return ""


def _build_series_position(series_ctx: Dict[str, Any], era_name: str, episode: int, total: int) -> str:
    """
    시리즈 전체에서의 현재 위치 컨텍스트 생성 (API 장점 활용)

    전체 시리즈에서 현재 에피소드가 어디에 위치하는지 알려줌
    """
    if not series_ctx:
        return f"""[시리즈 위치]
- 현재: {era_name} 시대 {episode}/{total}화
- 위치 활용: 시대의 시작/중반/끝에 따라 톤 조절
  - 시대 시작 (1-2화): 새로운 시대의 시작을 알림
  - 시대 중반: 핵심 사건 전개
  - 시대 끝 (마지막 1-2화): 시대의 마무리와 다음 시대 예고
"""

    global_episode = series_ctx.get("global_episode", 0)
    total_global = series_ctx.get("total_global_episodes", 60)
    era_index = series_ctx.get("era_index", 0)
    total_eras = series_ctx.get("total_eras", 8)

    # 시리즈 내 위치 파악
    if episode == 1:
        position_hint = "시대 시작 - 새로운 시대의 서막을 알리세요"
    elif episode == total:
        position_hint = "시대 마지막 - 시대를 정리하고 다음 시대를 예고하세요"
    elif episode <= 2:
        position_hint = "시대 초반 - 배경과 주요 인물 소개에 집중"
    elif episode >= total - 1:
        position_hint = "시대 후반 - 클라이맥스를 향해 전개"
    else:
        position_hint = "시대 중반 - 핵심 사건 전개"

    return f"""[시리즈 전체 위치 - API 장점]
- 전체: {global_episode}/{total_global}화 (한국사 통사 시리즈)
- 현재 시대: {era_name} ({era_index+1}/{total_eras}번째 시대)
- 시대 내: {episode}/{total}화
- 위치 가이드: {position_hint}

★ 이 위치 정보를 활용하세요:
- 시리즈 전반부: 기초 맥락 충분히 설명
- 시리즈 중반: 역사의 흐름과 연결점 강조
- 시리즈 후반: 앞서 다룬 내용 레퍼런스 가능
"""


def _generate_youtube_seo(
    client,
    era_name: str,
    episode: int,
    total_episodes: int,
    title: str,
    topic: str,
    intro_text: str,
    global_episode: int = None,  # ★ 전체 시리즈 번호
) -> Dict[str, Any]:
    """
    YouTube SEO 최적화 메타데이터 생성

    Returns:
        {
            "title": YouTube 제목 (클릭 유도),
            "thumbnail_text": 썸네일 문구 (2줄),
            "cost": API 비용
        }
    """
    # 전체 시리즈 번호가 없으면 에피소드 번호 사용
    series_num = global_episode if global_episode else episode

    prompt = f"""당신은 YouTube SEO 전문가입니다.

[영상 정보]
- 시리즈: 한국사 - {era_name}
- 전체 시리즈 번호: {series_num}화
- 시대 내 에피소드: {episode}/{total_episodes}화
- 원본 제목: {title}
- 주제: {topic}

[대본 인트로]
{intro_text[:1000]}

════════════════════════════════════════
[작업 1: YouTube 제목 작성]
════════════════════════════════════════

★ 필수 형식: "한국사 시리즈 {series_num}화 | [내용]"

이 형식을 반드시 지키면서 클릭을 유도하는 제목을 작성하세요.

규칙:
- 형식: "한국사 시리즈 N화 | [내용]" 필수
- [내용] 부분은 30자 이내
- 클릭 유도 요소:
  ✅ 핵심 키워드 포함
  ✅ 짧고 임팩트 있게
  ✅ 질문형 또는 결과형
- 감정적 과장 금지 (충격적, 놀라운 등 ❌)

좋은 예:
- "한국사 시리즈 2화 | 비파형동검과 고인돌, 고조선의 흔적"
- "한국사 시리즈 5화 | 왕검성 함락, 고조선의 최후"
- "한국사 시리즈 13화 | 광개토대왕, 동북아를 호령하다"

════════════════════════════════════════
[작업 2: 썸네일 문구 작성]
════════════════════════════════════════

썸네일에 들어갈 텍스트를 작성하세요.

규칙:
- 2줄로 작성 (줄바꿈으로 구분)
- 1줄당 7자 이내 권장 (10자 초과 금지)
- 짧고 임팩트 있게
- 질문형 또는 감탄형

좋은 예:
```
18세 왕의
첫 출정
```

```
숨겨진 진실
밝혀지다
```

════════════════════════════════════════
[출력 형식]
════════════════════════════════════════

아래 형식으로만 출력하세요:

TITLE: [YouTube 제목]
THUMBNAIL:
[1줄]
[2줄]
"""

    try:
        result = _call_gpt51(client, prompt)
        if "error" in result:
            return {"title": title, "thumbnail_text": "", "cost": 0}

        text = result.get("text", "")
        cost = result.get("cost", 0)

        # 파싱
        youtube_title = title  # 기본값
        thumbnail_text = ""

        lines = text.strip().split("\n")
        for i, line in enumerate(lines):
            if line.startswith("TITLE:"):
                youtube_title = line.replace("TITLE:", "").strip()
            elif line.startswith("THUMBNAIL:"):
                # 다음 2줄이 썸네일 텍스트
                thumb_lines = []
                for j in range(i + 1, min(i + 3, len(lines))):
                    if lines[j].strip() and not lines[j].startswith("TITLE"):
                        thumb_lines.append(lines[j].strip())
                thumbnail_text = "\n".join(thumb_lines)

        print(f"[SCRIPT] YouTube 제목: {youtube_title}")
        print(f"[SCRIPT] 썸네일 문구: {thumbnail_text.replace(chr(10), ' / ')}")

        return {
            "title": youtube_title,
            "thumbnail_text": thumbnail_text,
            "cost": cost,
        }

    except Exception as e:
        print(f"[SCRIPT] SEO 생성 실패: {e}")
        return {"title": title, "thumbnail_text": "", "cost": 0}


def _format_sources_for_youtube(sources: list) -> str:
    """
    YouTube 설명란용 출처 텍스트 생성

    Returns:
        출처 목록 (YouTube 설명란에 복사-붙여넣기 가능한 형식)
    """
    if not sources:
        return ""

    lines = ["📚 참고 자료 및 출처", ""]

    # 출처별 분류
    encykorea = []
    history_db = []
    cultural = []
    museum = []
    others = []

    for url in sources:
        if not url:
            continue
        url_lower = url.lower()
        if "encykorea" in url_lower:
            encykorea.append(url)
        elif "db.history.go.kr" in url_lower or "history.go.kr" in url_lower:
            history_db.append(url)
        elif "heritage.go.kr" in url_lower:
            cultural.append(url)
        elif "museum.go.kr" in url_lower:
            museum.append(url)
        else:
            others.append(url)

    # 카테고리별 출력
    if encykorea:
        lines.append("▸ 한국민족문화대백과사전")
        for url in encykorea[:3]:  # 최대 3개
            lines.append(f"  {url}")
        lines.append("")

    if history_db:
        lines.append("▸ 국사편찬위원회 한국사DB")
        for url in history_db[:3]:
            lines.append(f"  {url}")
        lines.append("")

    if cultural:
        lines.append("▸ 문화재청 국가문화유산포털")
        for url in cultural[:3]:
            lines.append(f"  {url}")
        lines.append("")

    if museum:
        lines.append("▸ 국립중앙박물관")
        for url in museum[:3]:
            lines.append(f"  {url}")
        lines.append("")

    if others:
        lines.append("▸ 기타 자료")
        for url in others[:3]:
            lines.append(f"  {url}")
        lines.append("")

    return "\n".join(lines)


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
    GPT-5.2로 20,000자 대본 생성 (이전 버전 호환용 함수명 유지)

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

        print(f"[SCRIPT] GPT-5.2 대본 생성 시작...")
        print(f"[SCRIPT] 입력 자료: {len(full_content):,}자")

        # GPT-5.2 Responses API 호출
        response = client.responses.create(
            model="gpt-5.2",
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
        # GPT-5.2 가격: $1.75/1M input, $14/1M output
        input_tokens = (len(SCRIPT_STYLE_PROMPT) + len(user_prompt)) // 2
        output_tokens = script_length // 2
        cost = (input_tokens * 1.75 / 1_000_000) + (output_tokens * 14 / 1_000_000)

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
            "model": "gpt-5.2",
            "cost": cost,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
        }

    except Exception as e:
        print(f"[SCRIPT] GPT-5.2 호출 실패: {e}")
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
    대본 생성 (분량 부족 시 이어쓰기)

    분량이 SCRIPT_MIN_LENGTH 미만이면 이어쓰기 요청
    """
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

    script = result.get("script", "")
    total_cost = result.get("cost", 0)

    # 분량 부족 시 이어쓰기
    for attempt in range(max_retries):
        if len(script) >= SCRIPT_MIN_LENGTH:
            break

        print(f"[SCRIPT] 분량 부족 ({len(script):,}자), 이어쓰기 시도 ({attempt + 1}/{max_retries})...")

        continuation = _continue_script(
            era_name=era_name,
            episode=episode,
            title=title,
            current_script=script,
            target_length=SCRIPT_TARGET_LENGTH,
        )

        if "error" in continuation:
            print(f"[SCRIPT] 이어쓰기 실패: {continuation['error']}")
            break

        script += "\n\n" + continuation.get("script", "")
        total_cost += continuation.get("cost", 0)

    result["script"] = script
    result["length"] = len(script)
    result["cost"] = total_cost

    return result


def _continue_script(
    era_name: str,
    episode: int,
    title: str,
    current_script: str,
    target_length: int,
) -> Dict[str, Any]:
    """
    대본 이어쓰기 (분량 부족 시)
    """
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        return {"error": "OPENAI_API_KEY 없음"}

    remaining = target_length - len(current_script)

    prompt = f"""아래 대본의 이어쓰기를 작성하세요.

[현재 대본 마지막 부분]
{current_script[-2000:]}

[지시사항]
- 위 대본에 자연스럽게 이어지는 내용 작성
- 약 {remaining:,}자 분량 추가
- 기존 스타일(학술적, 객관적) 유지
- 마무리 + 다음 에피소드 예고 포함
"""

    try:
        client = OpenAI(api_key=api_key)

        response = client.responses.create(
            model="gpt-5.2",
            input=[
                {
                    "role": "system",
                    "content": [{"type": "input_text", "text": "한국사 대본 작가입니다. 기존 대본에 이어서 작성합니다."}]
                },
                {
                    "role": "user",
                    "content": [{"type": "input_text", "text": prompt}]
                }
            ],
            temperature=0.7,
        )

        if getattr(response, "output_text", None):
            continuation = response.output_text.strip()
        else:
            text_chunks = []
            for item in getattr(response, "output", []) or []:
                for content in getattr(item, "content", []) or []:
                    if getattr(content, "type", "") == "text":
                        text_chunks.append(getattr(content, "text", ""))
            continuation = "\n".join(text_chunks).strip()

        # 비용 계산 (GPT-5.2 가격: $1.75/1M input, $14/1M output)
        input_tokens = len(prompt) // 2
        output_tokens = len(continuation) // 2
        cost = (input_tokens * 1.75 / 1_000_000) + (output_tokens * 14 / 1_000_000)

        print(f"[SCRIPT] 이어쓰기 완료: +{len(continuation):,}자")

        return {
            "script": continuation,
            "length": len(continuation),
            "cost": cost,
        }

    except Exception as e:
        return {"error": str(e)}
