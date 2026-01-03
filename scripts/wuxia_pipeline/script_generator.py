"""
무협 소설 대본 자동 생성 모듈 (Claude Opus 4.5 via OpenRouter)

특징:
- 다중 음성 TTS용 태그 기반 대본 형식
- [나레이션], [무영], [설하] 등 캐릭터별 태그
- 오디오북 스타일의 몰입감 있는 스토리텔링
"""

import os
from typing import Dict, Any, Optional, List

from openai import OpenAI

from .config import (
    SERIES_INFO,
    VOICE_MAP,
    MAIN_CHARACTER_TAGS,
    SCRIPT_CONFIG,
    EPISODE_TEMPLATES,
    OPENROUTER_BASE_URL,
    CLAUDE_OPUS_MODEL,
)


# ============================================================
# 대본 설정
# ============================================================
SCRIPT_TARGET_LENGTH = SCRIPT_CONFIG.get("target_chars", 13000)
SCRIPT_MIN_LENGTH = SCRIPT_CONFIG.get("min_chars", 11000)
SCRIPT_MAX_LENGTH = SCRIPT_CONFIG.get("max_chars", 15000)


# ============================================================
# ★★★ MASTER SYSTEM PROMPT - 무협 소설 스타일 ★★★
# ============================================================
MASTER_SYSTEM_PROMPT = f"""당신은 한국 무협 소설의 베테랑 작가입니다.
시리즈명: {SERIES_INFO['title']} ({SERIES_INFO['title_en']})
주인공: {SERIES_INFO['protagonist']}
여주인공: {SERIES_INFO.get('heroine', '설하')}

목표: 시청자가 다음 화가 기다려지는 몰입감 있는 오디오북 대본 작성

════════════════════════════════════════
★★★ 대본 형식 (필수!) ★★★
════════════════════════════════════════
모든 대사와 나레이션은 반드시 [태그] 형식으로 작성:

[나레이션] 어느 깊은 밤, 산중의 오두막에서 한 청년이 잠에서 깨어났다.

[나레이션] 무영이 말했다.
[무영] "또... 그 꿈이었어."

[나레이션] 그때 뒤에서 노인의 목소리가 들려왔다.
[노인] "젊은이, 아직 깨어 있었군."

★ 사용 가능한 태그:
  - [나레이션] : 상황 설명, 장면 전환, 인물 소개
  - [무영] : 주인공 대사
  - [설하] : 여주인공 대사 (4화 이후 등장)
  - [노인] : 스승 대사
  - [각주] : 조연 대사
  - [악역] : 적대 인물 대사
  - [남자] [남자1] [남자2] : 남자 엑스트라
  - [여자] [여자1] [여자2] : 여자 엑스트라

════════════════════════════════════════
★ 핵심 규칙 - 주인공 소개 방식
════════════════════════════════════════
✅ 주요 인물(무영, 설하, 노인, 각주, 악역)은 나레이션이 먼저 소개:
  [나레이션] 무영이 고개를 들며 말했다.
  [무영] "누구냐!"

✅ 엑스트라(남자, 여자)는 나레이션 없이 바로 대사:
  [남자] 이봐! 거기 서!
  [여자] 도망쳐요!

════════════════════════════════════════
★ 무협 소설 문체
════════════════════════════════════════
• 생생한 액션 묘사: 검광, 권경, 보법 등 무공 장면
• 긴장감 있는 전개: 위기, 반전, 각성
• 캐릭터 매력: 무영의 과묵함, 설하의 우아함, 노인의 깊은 지혜
• 무협 용어 적절히 사용: 내공, 경맥, 기혈, 경공, 암기 등

════════════════════════════════════════
★ 캐릭터 설정
════════════════════════════════════════
【무영】
- 노비 출신의 청년 (20대 초반)
- 과묵하고 냉정하지만 속은 따뜻함
- 의문의 노인에게 절세무공 전수받음
- 여자에게 관심 없음 (하지만 설하만은 예외적으로 곁에 둠)

【설하】 (4화부터 등장)
- 명문 세가의 영애, 절세미녀
- 무영에게 목숨을 구해져 은혜를 갚겠다며 따라다님
- 우아하고 총명하지만 때로는 당찬 면도 있음
- 모든 남자가 부러워하지만, 무영만은 무관심

【노인】
- 무영의 스승, 정체불명의 고수
- 깊은 지혜와 절세무공의 소유자
- 무영에게 무공을 전수하고 떠남 (3화 이후)

════════════════════════════════════════
★ 절대 금지
════════════════════════════════════════
❌ 태그 없는 대사/나레이션
❌ 메타 라벨 ("Part 1", "장면 전환" 등)
❌ 격식체 ("~습니다", "~입니다") - 편안한 구어체만
❌ 감정 과장 ("놀랍게도", "충격적으로")
❌ 지나친 설명 (Show, don't tell)

대본만 출력하세요. [태그] 형식의 대본만 제공하세요."""


def generate_episode_script(
    episode: int,
    title: str = None,
    summary: str = None,
    key_events: List[str] = None,
    characters: List[str] = None,
    prev_episode_summary: str = None,
    next_episode_preview: str = None,
) -> Dict[str, Any]:
    """
    에피소드 대본 생성

    Args:
        episode: 에피소드 번호
        title: 에피소드 제목 (없으면 템플릿에서 가져옴)
        summary: 에피소드 요약 (없으면 템플릿에서 가져옴)
        key_events: 주요 사건 목록
        characters: 등장 캐릭터 목록
        prev_episode_summary: 이전 에피소드 요약
        next_episode_preview: 다음 에피소드 예고

    Returns:
        {
            "ok": True,
            "script": "...",  # 태그 형식 대본
            "char_count": 13500,
            "cost": 0.15
        }
    """
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        return {"ok": False, "error": "OPENROUTER_API_KEY 환경변수가 설정되지 않았습니다."}

    # 에피소드 템플릿에서 기본값 가져오기
    template = EPISODE_TEMPLATES.get(episode, {})

    title = title or template.get("title", f"제{episode}화")
    summary = summary or template.get("summary", "")
    key_events = key_events or template.get("key_events", [])
    characters = characters or template.get("characters", ["무영"])

    # 캐릭터별 음성 정보
    char_voices = []
    for char in characters:
        voice = VOICE_MAP.get(char, VOICE_MAP.get("나레이션"))
        char_voices.append(f"  - [{char}]: {voice}")

    char_info = "\n".join(char_voices)
    events_info = "\n".join([f"  {i+1}. {e}" for i, e in enumerate(key_events)])

    # 이전/다음 에피소드 연결
    prev_context = ""
    if prev_episode_summary:
        prev_context = f"""
[이전 화 요약]
{prev_episode_summary}

★ 이전 화와 자연스럽게 연결해서 시작하세요.
"""

    next_context = ""
    if next_episode_preview:
        next_context = f"""
[다음 화 예고]
{next_episode_preview}

★ 마지막에 다음 화에 대한 기대감을 심어주세요.
"""

    # 메인 프롬프트
    user_prompt = f"""[{SERIES_INFO['title']} 제{episode}화: {title}]

[에피소드 정보]
- 제목: {title}
- 요약: {summary}

[등장 캐릭터 & TTS 음성]
{char_info}

[주요 사건]
{events_info}

{prev_context}
{next_context}

════════════════════════════════════════
[대본 구조]
════════════════════════════════════════
1. 오프닝 (1,500자)
   - 이전 화 연결 (있으면)
   - 몰입감 있는 도입
   - 첫 장면 설정

2. 전개 (4,000자)
   - 주요 사건 1, 2 전개
   - 캐릭터 대화와 액션
   - 긴장감 조성

3. 클라이맥스 (4,500자)
   - 주요 사건 3, 4 전개
   - 액션 장면 또는 감정적 절정
   - 반전 또는 위기

4. 마무리 (3,000자)
   - 사건 마무리
   - 다음 화 예고 (여운 남기기)
   - 기대감 조성

════════════════════════════════════════
★★★ 분량: 최소 {SCRIPT_MIN_LENGTH:,}자, 권장 {SCRIPT_TARGET_LENGTH:,}자 ★★★
★★★ 반드시 [태그] 형식으로 모든 대사/나레이션 작성 ★★★

대본만 출력하세요:"""

    print(f"[WUXIA-SCRIPT] === 제{episode}화 대본 생성 시작 ===")
    print(f"[WUXIA-SCRIPT] 제목: {title}")
    print(f"[WUXIA-SCRIPT] 캐릭터: {', '.join(characters)}")

    try:
        client = OpenAI(
            api_key=api_key,
            base_url=OPENROUTER_BASE_URL,
        )

        response = client.chat.completions.create(
            model=CLAUDE_OPUS_MODEL,
            max_tokens=16384,  # 긴 대본을 위해 충분한 토큰
            messages=[
                {"role": "system", "content": MASTER_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.8,  # 창의성을 위해 약간 높게
        )

        script = response.choices[0].message.content or ""
        script = script.strip()

        # 비용 계산 (Claude Opus 4.5)
        input_tokens = response.usage.prompt_tokens if response.usage else 0
        output_tokens = response.usage.completion_tokens if response.usage else 0

        # Prompt Caching 가정 (System Prompt 90% 할인)
        input_cost = input_tokens * 1.5 / 1_000_000  # 캐싱 적용 시
        output_cost = output_tokens * 75 / 1_000_000
        total_cost = input_cost + output_cost

        char_count = len(script.replace(" ", "").replace("\n", ""))

        print(f"[WUXIA-SCRIPT] 생성 완료: {char_count:,}자")
        print(f"[WUXIA-SCRIPT] 비용: ${total_cost:.4f}")

        # 분량 부족 시 이어쓰기
        if char_count < SCRIPT_MIN_LENGTH:
            print(f"[WUXIA-SCRIPT] 분량 부족 ({char_count:,}자 < {SCRIPT_MIN_LENGTH:,}자), 이어쓰기...")

            continue_result = _continue_script(client, script, char_count)
            if continue_result.get("ok"):
                script = continue_result["script"]
                total_cost += continue_result.get("cost", 0)
                char_count = len(script.replace(" ", "").replace("\n", ""))
                print(f"[WUXIA-SCRIPT] 이어쓰기 후: {char_count:,}자")

        return {
            "ok": True,
            "script": script,
            "char_count": char_count,
            "cost": round(total_cost, 4),
            "episode": episode,
            "title": title,
        }

    except Exception as e:
        print(f"[WUXIA-SCRIPT] 오류: {e}")
        return {"ok": False, "error": str(e)}


def _continue_script(client: OpenAI, current_script: str, current_length: int) -> Dict[str, Any]:
    """대본 이어쓰기"""
    target_additional = SCRIPT_TARGET_LENGTH - current_length

    continue_prompt = f"""[이어쓰기 요청]

현재까지 작성된 대본:
---
{current_script[-3000:]}
---

현재 분량: {current_length:,}자
추가 필요: {target_additional:,}자 이상

★ 위 대본에 이어서 자연스럽게 작성하세요.
★ 동일한 [태그] 형식 유지
★ 스토리가 자연스럽게 이어지도록

이어서 작성:"""

    try:
        response = client.chat.completions.create(
            model=CLAUDE_OPUS_MODEL,
            max_tokens=8192,
            messages=[
                {"role": "system", "content": MASTER_SYSTEM_PROMPT},
                {"role": "user", "content": continue_prompt}
            ],
            temperature=0.8,
        )

        continuation = response.choices[0].message.content or ""
        continuation = continuation.strip()

        # 비용 계산
        input_tokens = response.usage.prompt_tokens if response.usage else 0
        output_tokens = response.usage.completion_tokens if response.usage else 0
        input_cost = input_tokens * 1.5 / 1_000_000
        output_cost = output_tokens * 75 / 1_000_000

        # 합치기
        full_script = current_script + "\n\n" + continuation

        return {
            "ok": True,
            "script": full_script,
            "cost": input_cost + output_cost,
        }

    except Exception as e:
        print(f"[WUXIA-SCRIPT] 이어쓰기 오류: {e}")
        return {"ok": False, "error": str(e)}


def generate_youtube_metadata(script: str, episode: int, title: str) -> Dict[str, Any]:
    """
    YouTube 메타데이터 생성 (제목, 설명, 썸네일 문구)
    """
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        return {"ok": False, "error": "OPENROUTER_API_KEY 없음"}

    # 대본에서 핵심 장면 추출 (앞부분)
    script_preview = script[:2000] if len(script) > 2000 else script

    prompt = f"""[{SERIES_INFO['title']} 제{episode}화: {title}]

대본 미리보기:
{script_preview}

아래 형식으로 YouTube 메타데이터를 생성하세요:

1. 영상 제목 (50자 이내)
   - 궁금증 유발, 클릭 욕구
   - 예: "[혈영] 노비 청년이 강호 최강이 되기까지 | 1화"

2. 영상 설명 (300자)
   - 줄거리 힌트
   - 시청 유도 문구

3. 썸네일 문구 (2줄, 각 10자 이내)
   - Line1: 강렬한 키워드
   - Line2: 호기심 자극

JSON 형식으로만 출력:
{{"title": "...", "description": "...", "thumbnail_line1": "...", "thumbnail_line2": "..."}}"""

    try:
        client = OpenAI(
            api_key=api_key,
            base_url=OPENROUTER_BASE_URL,
        )

        response = client.chat.completions.create(
            model=CLAUDE_OPUS_MODEL,
            max_tokens=1024,
            messages=[
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
        )

        result_text = response.choices[0].message.content or ""

        # JSON 파싱
        import json
        import re

        json_match = re.search(r'\{[^}]+\}', result_text, re.DOTALL)
        if json_match:
            metadata = json.loads(json_match.group())
            return {"ok": True, **metadata}

        return {"ok": False, "error": "JSON 파싱 실패"}

    except Exception as e:
        return {"ok": False, "error": str(e)}


# =====================================================
# 테스트
# =====================================================

if __name__ == "__main__":
    import json

    print("=== 무협 대본 생성 테스트 ===\n")

    # 1화 테스트
    result = generate_episode_script(
        episode=1,
        prev_episode_summary=None,
        next_episode_preview="노인의 가르침 아래 무영이 첫 무공을 익히게 된다."
    )

    if result.get("ok"):
        print(f"\n제목: {result['title']}")
        print(f"분량: {result['char_count']:,}자")
        print(f"비용: ${result['cost']:.4f}")
        print("\n=== 대본 미리보기 (첫 1000자) ===")
        print(result['script'][:1000])
    else:
        print(f"오류: {result.get('error')}")
