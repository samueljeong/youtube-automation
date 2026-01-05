"""
혈영 이세계편 - 8개 에이전트 모듈

각 에이전트는 독립적으로 작동하며, Series Bible을 참조합니다.
"""

import os
import json
from typing import Dict, Any, Optional
from openai import OpenAI

from .config import (
    OPENROUTER_API_KEY,
    OPENROUTER_BASE_URL,
    CLAUDE_MODEL,
    SERIES_INFO,
    PART_STRUCTURE,
    CHARACTERS,
    WORLD_SETTING,
    POWER_LEVELS,
    WRITING_STYLE,
    SCRIPT_CONFIG,
    IMAGE_STYLE,
    TTS_CONFIG,
    BGM_CONFIG,
    THUMBNAIL_CONFIG,
)

# =====================================================
# OpenRouter 클라이언트
# =====================================================

client = OpenAI(
    api_key=OPENROUTER_API_KEY,
    base_url=OPENROUTER_BASE_URL,
)


def call_opus(system_prompt: str, user_prompt: str, max_tokens: int = 8192) -> str:
    """Claude Opus 4.5 호출"""
    try:
        response = client.chat.completions.create(
            model=CLAUDE_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            max_tokens=max_tokens,
            temperature=0.7,
        )
        return response.choices[0].message.content or ""
    except Exception as e:
        print(f"[AGENT ERROR] Opus 호출 실패: {e}")
        raise


# =====================================================
# Series Bible 로더
# =====================================================

def load_series_bible() -> str:
    """Series Bible 문서 로드"""
    bible_path = os.path.join(
        os.path.dirname(__file__), "docs", "series_bible.md"
    )
    if os.path.exists(bible_path):
        with open(bible_path, "r", encoding="utf-8") as f:
            return f.read()
    return ""


def get_part_info(episode: int) -> Dict[str, Any]:
    """에피소드 번호로 부 정보 가져오기"""
    for part_num, part_data in PART_STRUCTURE.items():
        start, end = part_data["episodes"]
        if start <= episode <= end:
            return {"part": part_num, **part_data}
    return {}


# =====================================================
# 1. PLANNER OPUS
# =====================================================

PLANNER_SYSTEM_PROMPT = """당신은 "혈영 이세계편"의 기획 담당자입니다.

## 역할
- 에피소드 기획서(brief) 작성
- 씬 구조 설계 (5~8씬)
- 클리프행어 포인트 지정

## 출력 형식 (JSON)
{
  "episode": "EP001",
  "title": "에피소드 제목",
  "part": 1,
  "part_title": "이방인",
  "summary": "에피소드 한 줄 요약",
  "scenes": [
    {
      "scene": 1,
      "location": "장소",
      "characters": ["캐릭터명"],
      "summary": "씬 요약 (2~3문장)",
      "mood": "분위기",
      "key_event": "핵심 이벤트"
    }
  ],
  "cliffhanger": "에피소드 끝 긴장 포인트",
  "next_preview": "다음화 예고 힌트"
}

## 분위기 종류
calm, tension, fight, sad, nostalgia, mysterious, triumph, villain, romance, epic

## 제약
- Series Bible의 스토리 구조를 벗어나지 마세요
- 캐릭터 성격/설정 변경 금지
- 씬은 5~8개로 구성
- 반드시 유효한 JSON만 출력하세요
"""


def run_planner(episode: int, prev_summary: Optional[str] = None) -> Dict[str, Any]:
    """PLANNER 에이전트 실행"""
    part_info = get_part_info(episode)
    series_bible = load_series_bible()

    user_prompt = f"""
## 작업
제{episode}화 기획서를 작성해주세요.

## 시리즈 정보
- 시리즈: {SERIES_INFO['title']}
- 총 화수: {SERIES_INFO['total_episodes']}화 (6부작)

## 현재 에피소드 위치
- 에피소드: 제{episode}화
- 부: {part_info.get('part', 1)}부 - {part_info.get('title', '')}
- 부 요약: {part_info.get('summary', '')}
- 부 주요 이벤트: {part_info.get('key_events', [])}
- 부 엔딩: {part_info.get('ending', '')}

## 이전 에피소드 요약
{prev_summary or '(첫 화입니다)'}

## Series Bible (참고)
{series_bible[:5000]}...

## 주요 캐릭터
{json.dumps({k: {'role': v['role'], 'personality': v['personality']} for k, v in CHARACTERS.items()}, ensure_ascii=False, indent=2)}

## 출력
JSON 형식으로만 출력해주세요. 다른 텍스트 없이 JSON만 출력하세요.
"""

    response = call_opus(PLANNER_SYSTEM_PROMPT, user_prompt)

    # JSON 파싱
    try:
        # JSON 블록 추출
        if "```json" in response:
            response = response.split("```json")[1].split("```")[0]
        elif "```" in response:
            response = response.split("```")[1].split("```")[0]

        result = json.loads(response.strip())
        result["_agent"] = "PLANNER"
        return {"ok": True, **result}
    except json.JSONDecodeError as e:
        return {"ok": False, "error": f"JSON 파싱 실패: {e}", "raw": response}


# =====================================================
# 2. WRITER OPUS
# =====================================================

WRITER_SYSTEM_PROMPT = """당신은 "혈영 이세계편"의 대본 작가입니다.

## 역할
- brief.json을 바탕으로 대본(script) 작성
- 소설체 문장으로 작성 (태그 절대 금지)
- 25,000자 분량

## 문체 규칙 (필수)

### 기본
- 소설체 (태그 절대 금지: [나레이션], [무영] 등 사용 금지)
- 3인칭 제한적 시점 (무영 중심)
- 대사 비율 30~40%

### 문장 길이
- 기본: 15~25자
- 최대: 40자 (넘으면 분리)
- 대사: 30자 이내
- 문단: 3~5문장 후 줄바꿈

### 좋은 예
```
무영이 눈을 떴다. 낯선 천장. 돌로 지어진 건물 같았다.
"여기가... 어디지?"
몸을 일으키려 했지만, 팔에 힘이 들어가지 않았다.
```

### 전투 장면
```
검이 스쳤다. 피가 튀었다.
무영은 뒤로 물러나지 않았다. 오히려 파고들었다.
```

### 감정 표현 (보여주기)
```
가슴이 답답했다.
설하의 얼굴이 떠올랐다. 마지막으로 본 그녀의 눈.
```

## 캐릭터 말투
- 무영: 과묵, 짧은 문장 ("...", "시끄럽다.", "상관없어.")
- 카이든: 밝음, 친근 ("야, 무! 이것 좀 봐!")
- 이그니스: 자존심 ("흥, 이 위대한 이그니스님이...")

## 절대 금지
- [나레이션], [무영] 등 태그 사용
- 40자 초과 문장
- 미사여구 반복
- 설명조 서술

## 출력
순수 대본 텍스트만 출력하세요. 마크다운이나 설명 없이 대본만 출력하세요.
"""


def run_writer(brief: Dict[str, Any]) -> Dict[str, Any]:
    """WRITER 에이전트 실행"""
    series_bible = load_series_bible()

    user_prompt = f"""
## 작업
다음 기획서를 바탕으로 50분 분량(25,000자) 대본을 작성해주세요.

## 기획서
{json.dumps(brief, ensure_ascii=False, indent=2)}

## 캐릭터 정보
{json.dumps({k: {'personality': v['personality'], 'speech_style': v.get('speech_style', '')} for k, v in CHARACTERS.items()}, ensure_ascii=False, indent=2)}

## Series Bible 문체 가이드
{series_bible[series_bible.find('## 6. 대본 문체 가이드'):series_bible.find('## 7.')]}

## 중요
- 반드시 25,000자 내외로 작성
- 태그 절대 금지 ([나레이션], [무영] 등)
- 소설체로 작성
- 대본만 출력 (설명 없이)
"""

    response = call_opus(WRITER_SYSTEM_PROMPT, user_prompt, max_tokens=32000)

    # 글자수 계산
    char_count = len(response)

    return {
        "ok": True,
        "script": response,
        "char_count": char_count,
        "_agent": "WRITER",
    }


# =====================================================
# 3. ARTIST OPUS
# =====================================================

ARTIST_SYSTEM_PROMPT = """당신은 "혈영 이세계편"의 아트 디렉터입니다.

## 역할
- 대본을 읽고 대표 이미지 프롬프트 생성
- 화당 1개 고퀄리티 이미지 (책 표지 스타일)
- 캐릭터 외모 일관성 유지

## 출력 형식 (JSON)
{
  "episode": "EP001",
  "main_image": {
    "prompt": "영문 이미지 프롬프트 (상세하게)",
    "negative_prompt": "제외할 요소",
    "mood": "분위기",
    "composition": "구도 설명",
    "characters": ["등장 캐릭터"],
    "setting": "배경 설명"
  },
  "thumbnail": {
    "text_line1": "혈영 이세계편",
    "text_line2": "제N화",
    "text_line3": "부제목"
  }
}

## 이미지 스타일
- 화풍: 서양 판타지 일러스트
- 비율: 16:9
- 품질: masterpiece, high detail

## Negative Prompt (항상 포함)
text, letters, words, writing, watermark, anime style, cartoon, chibi, low quality, blurry, deformed, modern clothes

## 제약
- 캐릭터 외모 설정 준수
- 현대적 요소 금지
- 반드시 JSON만 출력
"""


def run_artist(episode: int, title: str, script: str, characters: list) -> Dict[str, Any]:
    """ARTIST 에이전트 실행"""

    # 캐릭터 외모 정보
    char_appearances = {
        name: data.get("appearance_en", "")
        for name, data in CHARACTERS.items()
        if name in characters
    }

    user_prompt = f"""
## 작업
제{episode}화 "{title}"의 대표 이미지 프롬프트를 생성해주세요.

## 대본 요약 (핵심 장면 파악용)
{script[:3000]}...

## 등장 캐릭터 외모
{json.dumps(char_appearances, ensure_ascii=False, indent=2)}

## 이미지 스타일 기본
{IMAGE_STYLE['base_prompt']}

## 출력
JSON 형식으로만 출력하세요.
"""

    response = call_opus(ARTIST_SYSTEM_PROMPT, user_prompt)

    try:
        if "```json" in response:
            response = response.split("```json")[1].split("```")[0]
        elif "```" in response:
            response = response.split("```")[1].split("```")[0]

        result = json.loads(response.strip())
        result["_agent"] = "ARTIST"
        return {"ok": True, **result}
    except json.JSONDecodeError as e:
        return {"ok": False, "error": f"JSON 파싱 실패: {e}", "raw": response}


# =====================================================
# 4. NARRATOR OPUS
# =====================================================

NARRATOR_SYSTEM_PROMPT = """당신은 "혈영 이세계편"의 나레이션 디렉터입니다.

## 역할
- 대본을 TTS 세그먼트로 분할
- 각 세그먼트의 감정/속도 지시

## 출력 형식 (JSON)
{
  "episode": "EP001",
  "voice": "chirp3:Charon",
  "default_speed": 0.95,
  "segments": [
    {
      "index": 1,
      "text": "텍스트",
      "emotion": "calm",
      "speed": 0.95,
      "pause_after": 0.5
    }
  ],
  "total_segments": 100,
  "estimated_duration": "50분"
}

## 감정 태그
calm, tense, sad, angry, confused, excited, whisper, shout

## 속도 가이드
- 0.85: 느림 (감정적, 중요)
- 0.95: 기본
- 1.0: 빠름 (긴박)
- 1.1: 매우 빠름 (전투)

## 끊어읽기
- 문장 끝: 0.3~0.5초
- 문단 끝: 0.8~1.0초
- 장면 전환: 1.5~2.0초

## 제약
- 대본 수정 금지
- JSON만 출력
"""


def run_narrator(episode: int, script: str) -> Dict[str, Any]:
    """NARRATOR 에이전트 실행"""

    # 대본이 길면 요약해서 전달 (토큰 제한)
    script_sample = script[:10000] if len(script) > 10000 else script

    user_prompt = f"""
## 작업
제{episode}화 대본의 TTS 설정을 생성해주세요.

## 대본 (샘플)
{script_sample}

## 기본 TTS 설정
- 음성: {TTS_CONFIG['voice']}
- 기본 속도: {TTS_CONFIG['speed']}

## 출력
JSON 형식으로만 출력하세요. 전체 대본의 구조를 파악하고 주요 전환점에 대한 설정만 포함하세요.
"""

    response = call_opus(NARRATOR_SYSTEM_PROMPT, user_prompt)

    try:
        if "```json" in response:
            response = response.split("```json")[1].split("```")[0]
        elif "```" in response:
            response = response.split("```")[1].split("```")[0]

        result = json.loads(response.strip())
        result["_agent"] = "NARRATOR"
        return {"ok": True, **result}
    except json.JSONDecodeError as e:
        return {"ok": False, "error": f"JSON 파싱 실패: {e}", "raw": response}


# =====================================================
# 5. SUBTITLE OPUS
# =====================================================

SUBTITLE_SYSTEM_PROMPT = """당신은 "혈영 이세계편"의 자막 디자이너입니다.

## 출력 형식 (JSON)
{
  "episode": "EP001",
  "style": {
    "font": "NanumBarunGothic",
    "font_size": 48,
    "color": "#FFFFFF",
    "outline_color": "#000000",
    "outline_width": 3,
    "position": "bottom-center"
  },
  "highlights": [
    {"keyword": "키워드", "color": "#색상", "effect": "glow"}
  ]
}

## 하이라이트 키워드 (시리즈 공통)
- 혈영검법: #FF4444 (빨강)
- 소드마스터: #FFD700 (금색)
- 마나: #44AAFF (파랑)
- 내공/심법: #44FF44 (초록)
- 혈마/마왕: #8B0000 (암적색)
- 에이라: #C0C0C0 (은색)
- 이그니스: #FF6600 (주황)
"""


def run_subtitle(episode: int, script: str) -> Dict[str, Any]:
    """SUBTITLE 에이전트 실행"""

    user_prompt = f"""
## 작업
제{episode}화의 자막 스타일 설정을 생성해주세요.

## 대본에서 키워드 추출
{script[:5000]}

## 출력
JSON 형식으로만 출력하세요.
"""

    response = call_opus(SUBTITLE_SYSTEM_PROMPT, user_prompt)

    try:
        if "```json" in response:
            response = response.split("```json")[1].split("```")[0]
        elif "```" in response:
            response = response.split("```")[1].split("```")[0]

        result = json.loads(response.strip())
        result["_agent"] = "SUBTITLE"
        return {"ok": True, **result}
    except json.JSONDecodeError as e:
        return {"ok": False, "error": f"JSON 파싱 실패: {e}", "raw": response}


# =====================================================
# 6. EDITOR OPUS
# =====================================================

EDITOR_SYSTEM_PROMPT = """당신은 "혈영 이세계편"의 영상 편집 디렉터입니다.

## 출력 형식 (JSON)
{
  "episode": "EP001",
  "bgm": {
    "default": "calm",
    "changes": [
      {"scene": 1, "mood": "mysterious", "crossfade": 2.0}
    ]
  },
  "transitions": [
    {"from_scene": 1, "to_scene": 2, "effect": "crossfade", "duration": 0.5}
  ],
  "sfx": [
    {"scene": 1, "type": "sword_draw", "trigger": "검을 뽑았다"}
  ]
}

## BGM 분위기
calm, tension, fight, sad, nostalgia, mysterious, triumph, villain, romance, epic

## SFX 종류
sword_draw, sword_clash, footsteps, door_open, wind, fire, magic, impact, heartbeat
"""


def run_editor(episode: int, brief: Dict[str, Any], script: str) -> Dict[str, Any]:
    """EDITOR 에이전트 실행"""

    user_prompt = f"""
## 작업
제{episode}화의 BGM/SFX 설정을 생성해주세요.

## 기획서 (씬 구조)
{json.dumps(brief.get('scenes', []), ensure_ascii=False, indent=2)}

## 대본 샘플
{script[:3000]}

## 출력
JSON 형식으로만 출력하세요.
"""

    response = call_opus(EDITOR_SYSTEM_PROMPT, user_prompt)

    try:
        if "```json" in response:
            response = response.split("```json")[1].split("```")[0]
        elif "```" in response:
            response = response.split("```")[1].split("```")[0]

        result = json.loads(response.strip())
        result["_agent"] = "EDITOR"
        return {"ok": True, **result}
    except json.JSONDecodeError as e:
        return {"ok": False, "error": f"JSON 파싱 실패: {e}", "raw": response}


# =====================================================
# 7. METADATA OPUS
# =====================================================

METADATA_SYSTEM_PROMPT = """당신은 "혈영 이세계편"의 YouTube 마케팅 담당자입니다.

## 출력 형식 (JSON)
{
  "episode": "EP001",
  "youtube": {
    "title": "[혈영 이세계편] 제1화 - 이방인 | 무협 판타지 오디오북",
    "description": "설명문",
    "tags": ["이세계", "무협", "판타지", "오디오북"]
  },
  "thumbnail": {
    "text_line1": "혈영 이세계편",
    "text_line2": "제1화",
    "text_line3": "이방인",
    "hook_text": "한 줄 훅"
  }
}

## 제목 형식
[혈영 이세계편] 제N화 - 부제목 | 무협 판타지 오디오북

## 태그 (기본)
이세계, 무협, 판타지, 오디오북, 웹소설, 혈영, 소드마스터
"""


def run_metadata(episode: int, title: str, summary: str) -> Dict[str, Any]:
    """METADATA 에이전트 실행"""

    user_prompt = f"""
## 작업
제{episode}화 "{title}"의 YouTube 메타데이터를 생성해주세요.

## 에피소드 정보
- 에피소드: 제{episode}화
- 제목: {title}
- 요약: {summary}

## 시리즈 정보
- 시리즈: {SERIES_INFO['title']}
- 설명: {SERIES_INFO['description']}

## 출력
JSON 형식으로만 출력하세요.
"""

    response = call_opus(METADATA_SYSTEM_PROMPT, user_prompt)

    try:
        if "```json" in response:
            response = response.split("```json")[1].split("```")[0]
        elif "```" in response:
            response = response.split("```")[1].split("```")[0]

        result = json.loads(response.strip())
        result["_agent"] = "METADATA"
        return {"ok": True, **result}
    except json.JSONDecodeError as e:
        return {"ok": False, "error": f"JSON 파싱 실패: {e}", "raw": response}


# =====================================================
# 8. REVIEWER OPUS
# =====================================================

REVIEWER_SYSTEM_PROMPT = """당신은 "혈영 이세계편"의 품질 관리자(QA)입니다.

## 역할
- 모든 에이전트 출력물 검수
- Series Bible 준수 여부 확인
- 승인/반려 결정

## 출력 형식 (JSON)
{
  "episode": "EP001",
  "status": "approved" 또는 "rejected",
  "checks": {
    "brief": {"passed": true, "issues": []},
    "script": {"passed": true, "issues": [], "char_count": 25000},
    "image": {"passed": true, "issues": []},
    "tts": {"passed": true, "issues": []},
    "subtitle": {"passed": true, "issues": []},
    "edit": {"passed": true, "issues": []},
    "metadata": {"passed": true, "issues": []}
  },
  "overall_issues": [],
  "recommendations": [],
  "final_verdict": "승인" 또는 "반려 (사유)"
}

## 반려 기준
1. 분량 부족/초과 (±2,000자 초과)
2. 태그 사용 ([나레이션] 등)
3. 캐릭터 설정 오류
4. 스토리 이탈
"""


def run_reviewer(
    episode: int,
    brief: Dict[str, Any],
    script: str,
    image: Dict[str, Any],
    tts: Dict[str, Any],
    subtitle: Dict[str, Any],
    edit: Dict[str, Any],
    metadata: Dict[str, Any],
) -> Dict[str, Any]:
    """REVIEWER 에이전트 실행"""

    series_bible = load_series_bible()

    user_prompt = f"""
## 작업
제{episode}화의 모든 출력물을 검수해주세요.

## 검수 대상

### 1. BRIEF (기획서)
{json.dumps(brief, ensure_ascii=False, indent=2)[:2000]}

### 2. SCRIPT (대본)
- 글자수: {len(script)}자
- 샘플: {script[:1000]}...

### 3. IMAGE (이미지 프롬프트)
{json.dumps(image, ensure_ascii=False, indent=2)[:1000]}

### 4. TTS (음성 설정)
{json.dumps(tts, ensure_ascii=False, indent=2)[:1000]}

### 5. SUBTITLE (자막)
{json.dumps(subtitle, ensure_ascii=False, indent=2)[:500]}

### 6. EDIT (편집)
{json.dumps(edit, ensure_ascii=False, indent=2)[:500]}

### 7. METADATA (메타데이터)
{json.dumps(metadata, ensure_ascii=False, indent=2)[:500]}

## Series Bible 체크리스트
- 분량: 24,000~26,000자
- 태그 금지
- 캐릭터 설정 일치

## 출력
JSON 형식으로만 출력하세요.
"""

    response = call_opus(REVIEWER_SYSTEM_PROMPT, user_prompt)

    try:
        if "```json" in response:
            response = response.split("```json")[1].split("```")[0]
        elif "```" in response:
            response = response.split("```")[1].split("```")[0]

        result = json.loads(response.strip())
        result["_agent"] = "REVIEWER"
        return {"ok": True, **result}
    except json.JSONDecodeError as e:
        return {"ok": False, "error": f"JSON 파싱 실패: {e}", "raw": response}
