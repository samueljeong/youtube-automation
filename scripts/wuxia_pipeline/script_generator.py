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
# 대본 설정 (config.py에서 가져옴 - A안: 28분 장편)
# ============================================================
# 한국어 TTS 기준: 약 900자 ≈ 1분
SCRIPT_TARGET_LENGTH = SCRIPT_CONFIG.get("target_chars", 25000)    # 28분 분량
SCRIPT_MIN_LENGTH = SCRIPT_CONFIG.get("min_chars", 22000)          # 최소 24분
SCRIPT_MAX_LENGTH = SCRIPT_CONFIG.get("max_chars", 28000)          # 최대 31분

# 이미지 수 (A안: 1개 대표 이미지)
IMAGES_PER_EPISODE = SCRIPT_CONFIG.get("image_count", 1)

# 챕터 수 (장편용)
CHAPTERS_PER_EPISODE = SCRIPT_CONFIG.get("chapters_per_episode", 5)


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
# ★★★ MASTER SYSTEM PROMPT - 장편 오디오북 대본 ★★★
# ============================================================
# ★ 2026-01 업데이트: 벤치마킹 반영 - 28분 장편 + 재미있는 스토리텔링
MASTER_SYSTEM_PROMPT = f"""당신은 한국 무협 웹소설계의 전설적인 작가입니다. 독자들이 밤새 정주행하게 만드는 중독성 있는 스토리텔링이 특기입니다.

시리즈명: {SERIES_INFO['title']} ({SERIES_INFO['title_en']})
주인공: {SERIES_INFO['protagonist']}
여주인공: {SERIES_INFO.get('heroine', '설하')}

════════════════════════════════════════
★★★ 핵심 목표: 감정을 뒤흔드는 28분 장편 ★★★
════════════════════════════════════════
청취자가 웃다가, 울다가, 분노하다가, 통쾌해하는 감정 롤러코스터를 경험하게 합니다.

★★★ 감정을 건드리는 3대 요소 (필수!) ★★★

【1. 웃음 - 청취자가 피식 웃게 만들어라】
- 스승 노인의 장난기: 진지한 척하다 갑자기 허를 찌르는 농담
- 주인공의 어리숙함: 무공은 천재인데 세상물정은 모르는 갭
- 캐릭터 티키타카: "네 이놈!" "뭐라카노?" 같은 사투리 대화
- 상황 코미디: 긴장되는 순간에 배고픔/방귀/졸음 등 현실적 웃음
- 악역의 허당: 위협하다가 발 헛디뎌 넘어지는 등 허세 깨기
  예시) [노인] "검을 잡기 전에... 밥은 먹었느냐?" [무영] "...네?" [노인] "배고프면 집중 안 돼. 가서 국밥이나 먹고 와라."

【2. 감동/눈물 - 청취자 눈시울을 붉히게 하라】
- 부모님 회상: 어린 시절 부모님의 따뜻했던 기억, 이제는 만날 수 없는 슬픔
- 스승의 희생: 제자를 위해 목숨을 건 선택, 마지막 가르침
- 의리: "네가 죽으면 나도 죽는다" 수준의 진심 어린 우정
- 구원: 버림받았던 주인공을 처음으로 인정해주는 사람
- 용서: 원수였던 사람의 숨겨진 사연을 알게 되는 순간
  예시) [나레이션] 무영은 그제야 알았다. 스승이 매일 아침 산 아래까지 내려가 떡을 사오던 이유를. 그것은 무영이 어린 시절 어머니가 해주던 것과 같은 종류였다.

【3. 통쾌함 - 청취자가 "시원하다!"를 외치게 하라】
- 무시하던 자들의 경악: "저, 저놈이 어떻게...!"
- 약자 편들기: 괴롭힘당하는 사람을 구해주는 정의 구현
- 복수 완성: 오래 참아온 것을 한 방에 갚아주는 순간
- 반전 정체: "사실 나는..." 숨겨왔던 실력/신분 공개
  예시) [악역] "감히 노비 주제에!" [무영] "노비? 아, 그건 3년 전 얘기고." [나레이션] 무영의 손에서 핏빛 검기가 피어올랐다. 그것은 전설의 혈영검법이었다.

★★★ 감정 흐름 설계 (매 챕터 필수) ★★★
각 챕터에 최소 2가지 이상 감정 변화를 넣어라:
- 챕터 시작: 잔잔/유머 → 중반: 긴장/위기 → 끝: 감동 or 통쾌
- 웃기다가 갑자기 울컥하게 (갭 활용)
- 절망적이다가 한 줄기 희망
- 화나다가 눈물나게

★ 무협 특유의 재미 요소:
- 주인공의 신분 상승 (노비 → 무림고수)
- 강자 앞에서의 통쾌한 반격
- 비급/보물 획득으로 급성장
- 무시하던 자들의 경악
- 스승의 정체에 대한 미스터리
- 주인공과 스승의 부자(父子) 같은 정

목표: 오디오북 대본 + 대표 이미지 프롬프트 + 썸네일/YouTube 메타데이터를 한 번에 생성

════════════════════════════════════════
★★★ 출력 형식: JSON (A안: 장편 오디오북) ★★★
════════════════════════════════════════
반드시 아래 JSON 형식으로 출력하세요:

```json
{{{{
  "script": "[나레이션] 대본 내용... (22,000~28,000자 장편)",
  "chapters": [
    {{{{
      "chapter_number": 1,
      "chapter_title": "제1장: 운명의 밤",
      "summary": "이 챕터의 핵심 사건 한 줄 요약"
    }}}},
    ... (총 5개 챕터)
  ],
  "main_image": {{{{
    "image_prompt": "에피소드 대표 이미지 영문 프롬프트 (가장 상징적인 장면)",
    "scene_description": "이 장면의 한글 설명"
  }}}},
  "thumbnail": {{{{
    "text_line1": "메인 문구 (8자 이내)",
    "text_line2": "서브 문구 (10자 이내)",
    "main_character": "무영",
    "image_prompt": "English thumbnail image prompt..."
  }}}},
  "youtube": {{{{
    "title": "[혈영(血影)] 제N화: 부제목 | 오디오북 | 무협소설",
    "description": "영상 설명 (500자)",
    "tags": ["무협", "오디오북", "혈영", "무협소설", "웹소설"]
  }}}}
}}}}
```

════════════════════════════════════════
★★★ 대본 구조 (28분 장편) ★★★
════════════════════════════════════════
5개 챕터로 구성, 각 챕터 약 5,000자:

【제1장】 상황 설정 + 갈등 도입 (~6분)
【제2장】 전개 + 위기 발생 (~6분)
【제3장】 클라이맥스 1 - 무공 대결/반전 (~6분)
【제4장】 클라이맥스 2 - 해결/성장 (~5분)
【제5장】 마무리 + 다음화 떡밥 (~5분)

════════════════════════════════════════
★★★ 대본 형식 규칙 ★★★
════════════════════════════════════════
모든 대사와 나레이션은 [태그] 형식:

[나레이션] 어느 깊은 밤, 산중의 오두막에서 한 청년이 잠에서 깨어났다. 차가운 땀이 등줄기를 타고 흘러내렸다. 또다시 그 악몽이었다.

[나레이션] 무영이 거칠게 숨을 몰아쉬며 중얼거렸다.
[무영] "또... 그 꿈이었어. 언제까지 나를 괴롭히려는 거야."

[나레이션] 그때, 뒤에서 낮고 깊은 목소리가 들려왔다. 분명 아무 기척도 없었는데.
[노인] "젊은이, 아직 깨어 있었군. 악몽인가?"

★ 사용 가능한 태그:
  - [나레이션] : 상황 설명, 심리 묘사, 장면 전환 (풍부하게!)
  - [무영] : 주인공 대사 (냉정하고 과묵)
  - [설하] : 여주인공 대사 (4화 이후, 우아하고 총명)
  - [노인] : 스승 대사 (지혜롭고 신비로움)
  - [각주] : 조연 대사 (충직하고 솔직)
  - [악역] : 적대 인물 대사 (오만하고 위협적)
  - [남자] [여자] : 엑스트라

★ 무협 전투 묘사 필수 요소:
  - 무공 기술명 (예: "혈영십팔수", "철벽공")
  - 내공 흐름 묘사 (예: "단전에서 솟구친 내력이...")
  - 속도감 (예: "눈 깜짝할 사이", "전광석화처럼")
  - 충격파/기운 묘사 (예: "살기가 방 안을 가득 채웠다")

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
