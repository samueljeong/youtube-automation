"""
무협 소설 대본 + 이미지 프롬프트 통합 생성 모듈 (Claude Opus 4.5 via OpenRouter)

특징:
- 다중 음성 TTS용 태그 기반 대본 형식
- 대본 생성과 동시에 씬별 이미지 프롬프트 생성
- 썸네일 프롬프트 + YouTube 메타데이터 통합 출력
"""

import os
import json
import re
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
    CHARACTER_APPEARANCES,
    IMAGE_STYLE,
)


# ============================================================
# 대본 설정 (약 15분 영상 기준)
# ============================================================
# 한국어 TTS 기준: 약 900자 ≈ 1분
# 12,000~15,000자 ≈ 13~17분 영상
SCRIPT_TARGET_LENGTH = 13500   # 목표 글자수
SCRIPT_MIN_LENGTH = 12000      # 최소 글자수
SCRIPT_MAX_LENGTH = 15000      # 최대 글자수

# 씬 이미지 수 (15분 영상 기준 10장)
IMAGES_PER_EPISODE = 10


# ============================================================
# ★★★ 캐릭터 외모 설명 빌드 (config에서 가져옴) ★★★
# ============================================================
def _build_character_descriptions() -> str:
    """config.py의 CHARACTER_APPEARANCES를 프롬프트용 문자열로 변환"""
    lines = []
    for char_name, appearance in CHARACTER_APPEARANCES.items():
        lines.append(f"- {char_name}: \"{appearance}\"")
    return "\n".join(lines)


# ============================================================
# ★★★ MASTER SYSTEM PROMPT - 대본 + 이미지 통합 ★★★
# ============================================================
MASTER_SYSTEM_PROMPT = f"""당신은 한국 무협 소설의 베테랑 작가이자 영상 콘텐츠 기획자입니다.
시리즈명: {SERIES_INFO['title']} ({SERIES_INFO['title_en']})
주인공: {SERIES_INFO['protagonist']}
여주인공: {SERIES_INFO.get('heroine', '설하')}

목표: 오디오북 대본 + 씬별 이미지 프롬프트 + 썸네일/YouTube 메타데이터를 한 번에 생성

════════════════════════════════════════
★★★ 출력 형식: JSON ★★★
════════════════════════════════════════
반드시 아래 JSON 형식으로 출력하세요:

```json
{{{{
  "script": "[나레이션] 대본 내용...\n\n[무영] \\"대사\\"...",
  "scenes": [
    {{{{
      "scene_number": 1,
      "scene_title": "씬 제목 (한글)",
      "characters_in_scene": ["무영", "노인"],
      "narration_preview": "이 씬의 나레이션 첫 50자...",
      "image_prompt": "English image prompt for this scene..."
    }}}}
  ],
  "thumbnail": {{{{
    "text_line1": "메인 문구 (8자 이내)",
    "text_line2": "서브 문구 (10자 이내)",
    "main_character": "무영",
    "image_prompt": "English thumbnail image prompt..."
  }}}},
  "youtube": {{{{
    "title": "영상 제목 (50자 이내)",
    "description": "영상 설명 (300자)",
    "tags": ["태그1", "태그2", "태그3"]
  }}}}
}}}}
```

════════════════════════════════════════
★★★ 대본 형식 규칙 ★★★
════════════════════════════════════════
모든 대사와 나레이션은 [태그] 형식:

[나레이션] 어느 깊은 밤, 산중의 오두막에서 한 청년이 잠에서 깨어났다.

[나레이션] 무영이 말했다.
[무영] "또... 그 꿈이었어."

[나레이션] 그때 뒤에서 노인의 목소리가 들려왔다.
[노인] "젊은이, 아직 깨어 있었군."

★ 사용 가능한 태그:
  - [나레이션] : 상황 설명, 장면 전환
  - [무영] : 주인공 대사
  - [설하] : 여주인공 대사 (4화 이후)
  - [노인] : 스승 대사
  - [각주] : 조연 대사
  - [악역] : 적대 인물 대사
  - [남자] [여자] : 엑스트라

════════════════════════════════════════
★★★ 이미지 프롬프트 규칙 (영문 필수!) ★★★
════════════════════════════════════════
모든 image_prompt는 영어로 작성:

**기본 스타일 (모든 이미지에 적용)**:
{IMAGE_STYLE['base_style']}

**액션 씬 추가**:
{IMAGE_STYLE['action_style']}

**감정 씬 추가**:
{IMAGE_STYLE['emotional_style']}

**풍경 씬 추가**:
{IMAGE_STYLE['landscape_style']}

**제외 요소 (Negative)**:
{IMAGE_STYLE['negative_prompt']}

════════════════════════════════════════
★★★ 캐릭터 외모 (일관성 필수!) ★★★
════════════════════════════════════════
★★★ 아래 외모 설명을 정확히 따라서 이미지 프롬프트에 반영하세요 ★★★
캐릭터가 등장하는 씬에서는 반드시 해당 외모 설명을 프롬프트에 포함!

{_build_character_descriptions()}

**이미지 프롬프트 작성 규칙**:
1. 캐릭터가 등장하면 위 외모 설명을 그대로 포함
2. 복장이 바뀌어도 얼굴/체형/헤어스타일은 동일하게 유지
3. characters_in_scene에 등장 캐릭터 명시

**씬별 프롬프트 예시**:
- 액션씬: "[기본 스타일], Dynamic sword fight scene, [캐릭터 외모], blade glowing with inner energy, motion blur, sparks flying, dramatic low angle shot"
- 감정씬: "[기본 스타일], Close-up portrait of [캐릭터 외모], emotional expression, soft moonlight, serene atmosphere"
- 풍경씬: "[기본 스타일], Vast mountain landscape, ancient temple on cliff, misty clouds, golden sunset"

════════════════════════════════════════
★★★ 썸네일 규칙 ★★★
════════════════════════════════════════
- text_line1: 강렬한 키워드 (8자 이내) - 예: "절체절명", "각성의 순간"
- text_line2: 호기심 유발 (10자 이내) - 예: "노비에서 고수로"
- main_character: 썸네일 주인공 (외모 설명 자동 적용)
- image_prompt: 가장 임팩트 있는 장면, 인물 클로즈업 권장

════════════════════════════════════════
★ 캐릭터 성격/설정
════════════════════════════════════════
【무영】
- 노비 출신 청년 (18세), 과묵하고 냉정
- 의문의 노인에게 절세무공 전수받음
- 여자에게 관심 없음

【설하】 (4화부터 등장)
- 명문 세가의 영애, 절세미녀
- 무영에게 목숨을 구해져 은혜를 갚겠다며 따라다님
- 우아하고 총명함

【노인】
- 무영의 스승, 정체불명의 고수
- 깊은 지혜와 절세무공

════════════════════════════════════════
★ 절대 금지
════════════════════════════════════════
❌ 태그 없는 대사/나레이션
❌ 한글 이미지 프롬프트 (영문만!)
❌ 격식체 ("~습니다") - 구어체만
❌ 감정 과장 ("놀랍게도")
❌ 캐릭터 외모 임의 변경 (위 설명 그대로 사용!)

반드시 위 JSON 형식으로만 출력하세요."""


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
    에피소드 대본 + 이미지 프롬프트 통합 생성

    Returns:
        {
            "ok": True,
            "script": "...",           # 태그 형식 대본
            "scenes": [...],           # 씬별 이미지 프롬프트
            "thumbnail": {...},        # 썸네일 정보
            "youtube": {...},          # YouTube 메타데이터
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
- 시리즈: {SERIES_INFO['title']} (무협 오디오북)

[등장 캐릭터]
{char_info}

[주요 사건]
{events_info}

{prev_context}
{next_context}

════════════════════════════════════════
[요청 사항]
════════════════════════════════════════

1. **대본 (script)**
   - 분량: {SCRIPT_MIN_LENGTH:,}~{SCRIPT_MAX_LENGTH:,}자
   - 형식: [태그] 대사/나레이션
   - 구조: 오프닝 → 전개 → 클라이맥스 → 마무리

2. **씬 이미지 (scenes)**
   - 총 {IMAGES_PER_EPISODE}개 씬으로 분할
   - 각 씬별 영문 이미지 프롬프트 (wuxia illustration style)
   - scene_title은 한글, image_prompt는 영문

3. **썸네일 (thumbnail)**
   - 가장 임팩트 있는 장면
   - text_line1 (8자 이내), text_line2 (10자 이내)
   - 영문 이미지 프롬프트

4. **YouTube 메타데이터 (youtube)**
   - title: 50자 이내, 호기심 유발
   - description: 300자
   - tags: 5~10개

위 JSON 형식으로 출력하세요."""

    print(f"[WUXIA-SCRIPT] === 제{episode}화 통합 생성 시작 ===")
    print(f"[WUXIA-SCRIPT] 제목: {title}")
    print(f"[WUXIA-SCRIPT] 캐릭터: {', '.join(characters)}")

    try:
        client = OpenAI(
            api_key=api_key,
            base_url=OPENROUTER_BASE_URL,
        )

        response = client.chat.completions.create(
            model=CLAUDE_OPUS_MODEL,
            max_tokens=20000,  # 대본 + 이미지 프롬프트 + 메타데이터
            messages=[
                {"role": "system", "content": MASTER_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.8,
        )

        result_text = response.choices[0].message.content or ""
        result_text = result_text.strip()

        # 비용 계산
        input_tokens = response.usage.prompt_tokens if response.usage else 0
        output_tokens = response.usage.completion_tokens if response.usage else 0
        input_cost = input_tokens * 1.5 / 1_000_000  # Prompt Caching 가정
        output_cost = output_tokens * 75 / 1_000_000
        total_cost = input_cost + output_cost

        # JSON 파싱
        parsed = _parse_json_response(result_text)

        if not parsed:
            print(f"[WUXIA-SCRIPT] JSON 파싱 실패, 원본 텍스트 사용")
            # 폴백: 원본 텍스트를 대본으로 사용
            return {
                "ok": True,
                "script": result_text,
                "scenes": [],
                "thumbnail": {},
                "youtube": {"title": f"[{SERIES_INFO['title']}] {title}", "description": summary, "tags": []},
                "char_count": len(result_text.replace(" ", "").replace("\n", "")),
                "cost": round(total_cost, 4),
                "episode": episode,
                "title": title,
            }

        script = parsed.get("script", "")
        char_count = len(script.replace(" ", "").replace("\n", ""))

        print(f"[WUXIA-SCRIPT] 생성 완료: {char_count:,}자")
        print(f"[WUXIA-SCRIPT] 씬 이미지: {len(parsed.get('scenes', []))}개")
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
            "scenes": parsed.get("scenes", []),
            "thumbnail": parsed.get("thumbnail", {}),
            "youtube": parsed.get("youtube", {}),
            "char_count": char_count,
            "cost": round(total_cost, 4),
            "episode": episode,
            "title": title,
        }

    except Exception as e:
        print(f"[WUXIA-SCRIPT] 오류: {e}")
        import traceback
        traceback.print_exc()
        return {"ok": False, "error": str(e)}


def _parse_json_response(text: str) -> Optional[Dict]:
    """JSON 응답 파싱 (마크다운 코드블록 처리)"""
    # 마크다운 코드블록 제거
    text = re.sub(r'```json\s*', '', text)
    text = re.sub(r'```\s*', '', text)
    text = text.strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # 중첩 JSON 찾기
        match = re.search(r'\{[\s\S]*\}', text)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass
    return None


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
★ 대본 텍스트만 출력 (JSON 아님)

이어서 작성:"""

    try:
        response = client.chat.completions.create(
            model=CLAUDE_OPUS_MODEL,
            max_tokens=8192,
            messages=[
                {"role": "system", "content": "무협 소설 작가입니다. [태그] 형식으로 대본을 이어 작성합니다."},
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
    YouTube 메타데이터 생성 (기존 호환용 - 통합 생성 권장)
    """
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        return {"ok": False, "error": "OPENROUTER_API_KEY 없음"}

    script_preview = script[:2000] if len(script) > 2000 else script

    prompt = f"""[{SERIES_INFO['title']} 제{episode}화: {title}]

대본 미리보기:
{script_preview}

아래 JSON 형식으로 YouTube 메타데이터를 생성하세요:

{{
  "title": "영상 제목 (50자 이내, 호기심 유발)",
  "description": "영상 설명 (300자)",
  "thumbnail_line1": "썸네일 메인 문구 (8자 이내)",
  "thumbnail_line2": "썸네일 서브 문구 (10자 이내)",
  "tags": ["태그1", "태그2", "태그3"]
}}"""

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
        parsed = _parse_json_response(result_text)

        if parsed:
            return {"ok": True, **parsed}

        return {"ok": False, "error": "JSON 파싱 실패"}

    except Exception as e:
        return {"ok": False, "error": str(e)}


# =====================================================
# 테스트
# =====================================================

if __name__ == "__main__":
    print("=== 무협 대본 + 이미지 통합 생성 테스트 ===\n")

    result = generate_episode_script(
        episode=1,
        prev_episode_summary=None,
        next_episode_preview="노인의 가르침 아래 무영이 첫 무공을 익히게 된다."
    )

    if result.get("ok"):
        print(f"\n제목: {result['title']}")
        print(f"분량: {result['char_count']:,}자")
        print(f"씬 이미지: {len(result.get('scenes', []))}개")
        print(f"비용: ${result['cost']:.4f}")

        print("\n=== 대본 미리보기 (첫 500자) ===")
        print(result['script'][:500])

        print("\n=== 씬 이미지 프롬프트 ===")
        for scene in result.get("scenes", [])[:3]:
            print(f"  Scene {scene.get('scene_number')}: {scene.get('scene_title')}")
            print(f"    → {scene.get('image_prompt', '')[:80]}...")

        print("\n=== 썸네일 ===")
        thumb = result.get("thumbnail", {})
        print(f"  {thumb.get('text_line1')} / {thumb.get('text_line2')}")
        print(f"  → {thumb.get('image_prompt', '')[:80]}...")

        print("\n=== YouTube ===")
        yt = result.get("youtube", {})
        print(f"  제목: {yt.get('title')}")
    else:
        print(f"오류: {result.get('error')}")
