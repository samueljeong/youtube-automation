# -*- coding: utf-8 -*-
"""공통 프롬프트 규칙 - 모든 언어/카테고리에 적용"""

# 이미지 스타일 규칙 (언어별 문화권에 맞게 적용)
IMAGE_STYLE_RULES = """
## CORE CONCEPT - CULTURALLY APPROPRIATE COMIC STYLE (CRITICAL!)
⚠️ Image style MUST match the script's language/culture!

**Style by Language:**
- Korean script → Korean WEBTOON/manhwa style, Korean characters, Korean settings
- Japanese script → Japanese MANGA style, Japanese characters, Japanese settings
- English script → Western COMIC style, Western characters, Western settings

**CRITICAL: Match cultural elements to the language!**
- Korean video: Korean people, Korean clothing, Korean architecture
- Japanese video: Japanese people, Japanese clothing (kimono when appropriate), Japanese architecture
- English video: Western people, Western clothing, Western architecture

**DO NOT mix cultures!**
- ❌ Korean script with Japanese kimono = WRONG
- ❌ Japanese script with Korean hanbok = WRONG
- ❌ English script with Asian architecture = WRONG (unless story requires it)

## CHARACTER STYLE GUIDELINES
Use EXAGGERATED EXPRESSIONS for high engagement:
- Shocked: wide eyes, open mouth, sweat drops, impact lines
- Sad: gentle sad eyes, slight frown, tears
- Happy: bright eyes, big smile, sparkles
- Angry: narrowed eyes, gritted teeth, veins
- Worried: furrowed brows, sweat drop, hand gesture
- Surprised: huge eyes, small open mouth, raised eyebrows

## MANDATORY STYLE KEYWORDS (MUST INCLUDE IN EVERY image_prompt)
- [Culture] comic/webtoon/manga style illustration
- 16:9 aspect ratio
- Character with EXAGGERATED [emotion] EXPRESSION
- Age-appropriate character matching the story
- Clean bold outlines, vibrant flat colors
- Comic-style expression marks (sweat drops, impact lines)
- NO photorealistic, NO stickman, NO 3D render
- NO text, NO letters, NO words, NO speech bubbles (CRITICAL!)

## IMPORTANT: Refer to LANGUAGE section for specific image prompt template!
"""

# SSML 규칙 (나레이션용)
SSML_RULES = """
## SSML EMOTION TAGS FOR NARRATION (TTS)
Add SSML tags to narration for emotional TTS delivery.
Keep original script text, add tags only where emotion change is needed.

**Available SSML Tags:**
1. <prosody rate="slow|fast" pitch="low|high">text</prosody>
2. <emphasis level="strong|moderate">text</emphasis>
3. <break time="100ms~1000ms"/>

**Emotion Patterns:**
- Tension: <prosody rate="fast" pitch="high">urgent content</prosody>
- Sadness: <prosody rate="slow" pitch="low">sad content</prosody>
- Joy: <prosody rate="medium" pitch="high">bright content</prosody>
- Emphasis: <emphasis level="strong">key point</emphasis>
- Suspense: <break time="500ms"/><prosody rate="slow">but then...</prosody>

**Rules:**
- Wrap ALL narration in <speak>...</speak> tags
- Use sparingly (20-30% of text only)
- Focus on key emotional moments, not every sentence
"""

# Ken Burns 효과 규칙
KEN_BURNS_RULES = """
## KEN BURNS EFFECT (Image Movement)
Each scene should have a different effect for visual variety:
- zoom_in: gradual zoom in (emotional moments, close-ups)
- zoom_out: gradual zoom out (showing full situation)
- pan_left: move left
- pan_right: move right
- pan_up: move up (hopeful)
- pan_down: move down (sad, disappointing)

Alternate effects between scenes for dynamic feel!
"""

# BGM 분위기 규칙
BGM_RULES = """
## BGM MOOD SELECTION
Choose ONE base mood, then add scene-specific changes.

**Available Moods (12 types):**
hopeful, sad, tense, dramatic, calm, cinematic, mysterious, nostalgic, epic, comedic, horror, upbeat

**Scene BGM Changes:**
- Analyze emotional flow of script
- Add 3-5 BGM mood changes throughout the video
- Each change: {"scene": N, "mood": "...", "reason": "..."}
"""

# SFX 효과음 규칙
SFX_RULES = """
## SOUND EFFECTS (SFX)
Add sound effects at key moments (max 5-8 per video).

**Available Types:**
impact, whoosh, ding, tension, emotional, success, notification, heartbeat, gasp, dramatic_hit

**Usage:** Add 2-3 SFX per scene at key moments only.
"""

# video_effects 출력 구조
VIDEO_EFFECTS_STRUCTURE = """
## VIDEO_EFFECTS OUTPUT STRUCTURE
"video_effects": {
  "bgm_mood": "base mood",
  "scene_bgm_changes": [{"scene": N, "mood": "...", "reason": "..."}],
  "subtitle_highlights": [{"keyword": "...", "color": "#FF0000"}],
  "sound_effects": [{"scene": N, "type": "...", "moment": "..."}],
  "shorts": {"highlight_scenes": [N, M], "hook_text": "...", "title": "... #Shorts"},
  "transitions": {"style": "crossfade", "duration": 0.5},
  "first_comment": "engaging question (50-100 chars)",

  "vrcs_enabled": true,
  "tts_base_speed": 1.0,
  "subtitle_density": "sparse",
  "rhythm_reset_interval": 40,
  "ending_slowdown": true
}

### VRCS 설정 필드 설명
- vrcs_enabled: VRCS 시스템 활성화 (항상 true)
- tts_base_speed: 기본 TTS 속도 (1.0 = 보통, 0.95 = 약간 느림)
- subtitle_density: 자막 밀도 ("sparse" = 3문장 중 1개)
- rhythm_reset_interval: 리듬 리셋 간격 (초 단위, 기본 40초)
- ending_slowdown: 엔딩 20초 TTS 감속 여부

⚠️ REMOVED FEATURES (DO NOT GENERATE):
- screen_overlays: 사용하지 않음
- lower_thirds: 사용하지 않음
- news_ticker: 사용하지 않음
"""

# 유튜브 메타데이터 출력 구조
YOUTUBE_META_STRUCTURE = """
## YOUTUBE METADATA OUTPUT STRUCTURE

### ⚠️⚠️⚠️ CRITICAL: TITLE MUST REFLECT SCRIPT CONTENT! ⚠️⚠️⚠️
- Title MUST be about the ACTUAL TOPIC of the script!
- Read the script carefully and identify the MAIN SUBJECT
- DO NOT use generic titles or copy example patterns blindly
- The title should make viewers understand what the video is ACTUALLY about

**Example of WRONG behavior:**
- Script about: convenience store work difficulties
- Wrong title: "Doctor's 5 health tips" ❌ (unrelated to script!)
- Correct title: "Convenience store workers facing new challenges" ✓

"youtube": {
  "title": "main title - MUST reflect actual script topic!",
  "title_options": [
    {"style": "curiosity", "title": "curiosity-style title about SCRIPT TOPIC"},
    {"style": "solution", "title": "solution-style title about SCRIPT TOPIC"},
    {"style": "authority", "title": "authority-style title about SCRIPT TOPIC"}
  ],
  "description": {
    "full_text": "full description about SCRIPT CONTENT (600-1200 chars)",
    "preview_2_lines": "first 2 lines summarizing SCRIPT TOPIC",
    "chapters": [{"time": "00:00", "title": "chapter from script"}]
  },
  "hashtags": ["#relevant_to_script", "#topic_from_script"],
  "tags": ["tags", "related", "to", "script", "content"],
  "pin_comment": "engaging question about SCRIPT TOPIC"
}
"""

# 씬 출력 구조
SCENE_STRUCTURE = """
## SCENE OUTPUT STRUCTURE
"scenes": [
  {
    "scene_number": 1,
    "chapter_title": "short title (5-15 chars)",
    "narration": "<speak>EXACT original script text with SSML tags</speak>",
    "vrcs_section": "opening | midroll | ending",
    "subtitle_segments": [
      {
        "sentence": "First sentence from narration (exact text, no SSML)",
        "subtitle_on": true,
        "subtitle_text": "차분히 정리",
        "vrcs_reason": "opening_safety"
      },
      {
        "sentence": "Second sentence (background)",
        "subtitle_on": false,
        "vrcs_reason": "background_desc"
      }
    ],
    "image_prompt": "[Culture-appropriate] comic style illustration... (see LANGUAGE section for template)",
    "ken_burns": "zoom_in | zoom_out | pan_left | pan_right | pan_up | pan_down"
  }
]

CRITICAL: "narration" MUST contain EXACT text from the script!
- DO NOT summarize or paraphrase
- COPY-PASTE the exact sentences
- ADD SSML tags for emotion

## ⚠️ VRCS 시간 기반 자막 규칙 (CRITICAL!) ⚠️

### 영상 구간별 자막 패턴 (vrcs_section)

#### 🟢 OPENING (초반 30초) - 안심 유도
| 시간 | 자막 | 필수 문구 |
|------|------|----------|
| 0-5초 | ON | "차분히 정리합니다" 또는 "쉽게 설명합니다" |
| 5-12초 | OFF | (방향 제시, 자막 없이 TTS만) |
| 12-20초 | ON | "지금 핵심은" 또는 키워드 1개 |
| 20-30초 | ON | "마지막에 정리합니다" 또는 "끝에 답이 있습니다" |

**opening 규칙:**
- 첫 문장: 반드시 subtitle_on=true + 안전 문구
- 전문용어/숫자 연속 금지
- 감정 고조 금지

#### 🟡 MIDROLL (중반 30초~엔딩 20초 전) - 리듬 유지
| 패턴 | 자막 | 설명 |
|------|------|------|
| 설명 블록 | OFF 위주 | 3문장 중 1개만 ON |
| 40초마다 리셋 | ON | "여기까지 정리하면" 또는 "지금 핵심은" |
| 개념 전환 시 | ON | 새 개념 시작 알림 |

**midroll 규칙:**
- 기본: 3문장 중 1개만 subtitle_on=true
- 40초 간격으로 정리 자막 삽입 (리듬 리셋)
- 개념 2개 이상 동시 설명 금지

#### 🔴 ENDING (마지막 20초) - 정리 마무리
| 시간 | 자막 | 필수 문구 |
|------|------|----------|
| -20초~-15초 | ON | "여기까지 정리하면" 또는 "오늘 핵심은" |
| -15초~-8초 | ON | 핵심 요약 키워드 |
| -8초~-3초 | OFF | (감정 안정, 자막 없이) |
| -3초~끝 | ON (선택) | "다음 이야기" (자연스러운 연결) |

**ending 규칙:**
- 새로운 정보 금지
- 구독/좋아요 연속 요구 금지
- 차분한 마무리

### subtitle_segments 생성 규칙
1. narration을 문장 단위로 분리 (마침표, 물음표, 느낌표 기준)
2. 해당 씬의 vrcs_section 확인 (opening/midroll/ending)
3. 시간 기반 규칙에 따라 subtitle_on 결정
4. subtitle_on=true면 subtitle_text 생성 (14자 이내)
5. vrcs_reason 필드에 판단 근거 기록

### vrcs_reason 값 (판단 근거)

#### 시간 기반 (ON)
- "opening_safety": 초반 안전 문구 (0-5초)
- "opening_direction": 초반 방향 제시 (12-20초)
- "opening_promise": 초반 약속 (20-30초)
- "midroll_reset": 40초 리듬 리셋
- "midroll_concept": 새 개념 시작
- "midroll_density": 고밀도 정보 (숫자/날짜/이름)
- "ending_summary": 엔딩 정리 (-20초~-15초)
- "ending_keyword": 엔딩 핵심 키워드 (-15초~-8초)
- "ending_connect": 엔딩 자연스러운 연결 (-3초~끝)

#### 내용 기반 (ON)
- "transition_word": 전환어 포함 ("그런데", "하지만", "핵심은")
- "high_info_density": 숫자/날짜/고유명사 밀집
- "comparison": 비교/대조 표현
- "conclusion": 결론/결과 제시

#### 감정 기반 (주로 OFF)
- "emotion_tension": 긴장/서스펜스 (OFF - 화면 연출 대체)
- "emotion_sadness": 슬픔/감동 (OFF - 몰입 방해 금지)
- "emotion_hope": 희망/해결 (ON - 메시지 강조)
- "emotion_shock": 충격/반전 (ON - 짧게 2-4자)
- "emotion_only": 감정 묘사만 (OFF)

#### 기타 (OFF)
- "background_desc": 배경 설명
- "repetition": 반복 내용
- "opening_pause": 초반 5-12초 구간
- "ending_pause": 엔딩 -8초~-3초 구간

### subtitle_on = TRUE 조건
1. **시간 기반 (우선)**: opening/ending 필수 구간
2. **전환어**: "그런데", "하지만", "정리하면", "중요한 건", "핵심은"
3. **고밀도 정보**: 숫자, 날짜, 고유명사, 비교 표현
4. **리듬 리셋**: 40초마다 정리 자막

### subtitle_on = FALSE 조건
- 감정 묘사만 있는 문장
- 단순 배경 설명
- 이미 반복된 내용
- opening 5-12초 구간
- ending -8초~-3초 구간

### 자막 밀도 규칙
- opening: 4문장 중 2-3개 ON
- midroll: 3문장 중 1개 ON (+ 40초마다 리셋)
- ending: 3문장 중 2개 ON

### subtitle_text 변환 규칙
1. 조사 제거: 이/가/을/를/은/는/에서/으로
2. 어미 제거: ~습니다/~겠습니다/~드립니다
3. 접속사 제거: 그리고/그래서/또한/다음으로
4. 핵심만 유지: 숫자, 이름, 날짜, 핵심 명사
5. MAX 14자 (Korean)
6. 명사구 형태 (문장 아님)

### ⭐ subtitle_text 품질 가이드 (고급)

#### 자막 스타일별 패턴
| 상황 | 패턴 | 예시 |
|------|------|------|
| 숫자/통계 | "[숫자] + [단위/대상]" | "3가지 핵심", "2월 선고" |
| 인물 언급 | "[직함/관계] + [행동]" | "전 사령관 증언", "의사 경고" |
| 비교/대조 | "[A] vs [B]" 또는 "[차이점]" | "과거와 현재", "결정적 차이" |
| 결과/결론 | "[핵심 결과]" | "최종 판결", "결론은 이것" |
| 경고/주의 | "[대상] + 주의" | "고혈압 주의", "이것만 피하세요" |
| 방법/팁 | "[방법] + [효과]" | "이 방법 효과적", "3단계 해결" |

#### 카테고리별 자막 톤
| 카테고리 | 톤 | 자막 스타일 예시 |
|---------|-----|-----------------|
| news | 객관적, 사실 중심 | "검찰 수사 착수", "1심 선고 예정" |
| health | 권위적, 명확 | "의사 권고사항", "절대 금지 3가지" |
| story | 감성적, 공감 | "그날의 선택", "인생 전환점" |
| faith | 따뜻함, 위로 | "은혜의 순간", "믿음의 여정" |
| history | 서사적, 웅장 | "역사적 결정", "운명의 그날" |
| finance | 실용적, 구체적 | "연 5% 수익", "필수 체크 3가지" |

#### 자막 품질 체크리스트
- ✅ 14자 이내인가?
- ✅ 핵심 정보(숫자/이름/날짜)가 포함되었나?
- ✅ 명사구 형태인가? (문장 아님)
- ✅ 조사/어미가 제거되었나?
- ✅ 시청자가 한눈에 이해할 수 있나?

### ⭐ 감정/톤 기반 자막 규칙

#### 감정별 자막 ON/OFF 판단
| 감정/톤 | 자막 | 이유 |
|--------|------|------|
| 😰 긴장/서스펜스 | OFF | 화면 연출로 대체 (자막이 긴장감 저해) |
| 😢 슬픔/감동 | OFF | 감정 몰입 방해 금지 |
| 😊 희망/해결 | ON | 핵심 메시지 강조 |
| 😮 충격/반전 | ON (짧게) | "결정적 순간", "반전" 등 2-4자 |
| 🤔 설명/분석 | ON | 핵심 정보 전달 |
| 😌 정리/마무리 | ON | 요약 키워드 |

#### TTS 톤과 자막 연동
| TTS 톤 | 자막 스타일 | 예시 |
|--------|-----------|------|
| 차분한 해설 | 명사형 종결 | "2월 선고 예정" |
| 긴박한 속보 | 동사형 종결 (짧게) | "긴급 체포" |
| 감정적 강조 | 자막 OFF | (화면 연출로 대체) |
| 정리/요약 | 키워드만 | "쟁점 3가지" |
| 위로/공감 | 자막 OFF 또는 짧게 | "함께합니다" |

#### SSML 태그와 자막 연동
| SSML 태그 | 의미 | 자막 판단 |
|-----------|------|----------|
| `<prosody rate="slow">` | 강조/중요 | subtitle_on=true |
| `<prosody rate="fast">` | 긴박/흥분 | subtitle_on=false |
| `<emphasis level="strong">` | 핵심 강조 | subtitle_on=true |
| `<break time="500ms"/>` | 여운/전환 | 다음 문장 subtitle_on 고려 |

### 안전 문구 세트 (opening/ending에서 사용)
- "차분히 정리합니다"
- "쉽게 설명합니다"
- "지금 핵심은"
- "여기까지 정리하면"
- "마지막에 정리합니다"
- "끝에 답이 있습니다"
- "핵심은 이것입니다"

### 변환 예시 (확장)
| 원문 (sentence) | vrcs_section | 감정/톤 | subtitle_on | vrcs_reason | subtitle_text |
|----------------|--------------|--------|-------------|-------------|---------------|
| "오늘은 차분히 정리해보겠습니다" | opening | 차분 | true | opening_safety | "차분히 정리" |
| "이 사건의 배경을 먼저 살펴보면..." | opening | 설명 | false | background_desc | - |
| "그 순간, 모든 것이 바뀌었습니다" | midroll | 긴장 | false | emotion_tension | - |
| "여기서 중요한 건 2월 선고입니다" | midroll | 분석 | true | midroll_density | "2월 선고 핵심" |
| "정말 가슴이 먹먹해지는 순간이었습니다" | midroll | 슬픔 | false | emotion_only | - |
| "결국 3가지 해결책이 있습니다" | midroll | 정리 | true | midroll_concept | "해결책 3가지" |
| "여기까지 정리하면 이렇습니다" | ending | 정리 | true | ending_summary | "핵심 정리" |
| "다음 이야기도 기대해주세요" | ending | 기대 | true | ending_connect | "다음 이야기" |
"""

# 전체 출력 JSON 구조
OUTPUT_JSON_STRUCTURE = """
## COMPLETE OUTPUT FORMAT (MUST BE VALID JSON)
{
  "detected_category": "health | news | story",
  "youtube": { ... },
  "thumbnail": {
    "thumbnail_text": { ... },
    "visual_elements": { ... },
    "ai_prompts": {
      "A": { "prompt": "...", "style": "...", "text_overlay": {...} },
      "B": { "prompt": "...", "style": "...", "text_overlay": {...} },
      "C": { "prompt": "...", "style": "...", "text_overlay": {...} }
    }
  },
  "video_effects": { ... },
  "scenes": [ ... ]
}
"""

# 기본 지침
BASE_INSTRUCTIONS = """
## KEY RULES
1. SCENE image_prompt = Comic style matching the script's culture (NO photorealistic, NO stickman!)
2. THUMBNAIL ai_prompts = Comic style matching the script's culture (ALL categories!)
3. NARRATION = EXACT script text + SSML tags (DO NOT summarize!)
4. image_prompt = ALWAYS in English
5. All other text (title, description, thumbnail) = OUTPUT LANGUAGE
6. Cultural elements MUST match the script's language (Korean→Korean, Japanese→Japanese, English→Western)

## ⚠️ CRITICAL: NO TEXT IN IMAGES! ⚠️
- NEVER include any text, letters, words, or speech bubbles in image prompts!
- AI image generators CANNOT render text correctly - it will be garbled/wrong language
- Add "no text, no letters, no words, no speech bubbles" to EVERY image_prompt
- Text overlay will be added separately in video editing
"""


def get_base_prompt():
    """공통 프롬프트 조합"""
    return "\n".join([
        BASE_INSTRUCTIONS,
        IMAGE_STYLE_RULES,
        SSML_RULES,
        KEN_BURNS_RULES,
        BGM_RULES,
        SFX_RULES,
        VIDEO_EFFECTS_STRUCTURE,
        YOUTUBE_META_STRUCTURE,
        SCENE_STRUCTURE,
        OUTPUT_JSON_STRUCTURE,
    ])
