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
  "first_comment": "engaging question (50-100 chars)"
}

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
    "subtitle_segments": [
      {
        "sentence": "First sentence from narration (exact text, no SSML)",
        "subtitle_on": false
      },
      {
        "sentence": "Second sentence with important info (numbers, dates, names)",
        "subtitle_on": true,
        "subtitle_text": "핵심 14자 요약"
      },
      {
        "sentence": "Third sentence (background or emotion)",
        "subtitle_on": false
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

## VRCS SUBTITLE RULES (문장별 자막 ON/OFF)

### subtitle_segments 생성 규칙
1. narration을 문장 단위로 분리 (마침표, 물음표, 느낌표 기준)
2. 각 문장에 대해 subtitle_on 판단 (아래 조건 참고)
3. subtitle_on=true인 문장만 subtitle_text 생성 (14자 이내 요약)

### subtitle_on = TRUE 조건 (하나라도 충족 시)
- 전환어 포함: "그런데", "하지만", "정리하면", "중요한 건", "핵심은", "여기서"
- 고밀도 정보: 숫자, 날짜, 고유명사, 비교 표현
- 긴 문장: 예상 TTS 3.5초 이상 (약 50자 이상)

### subtitle_on = FALSE 조건
- 감정 묘사만 있는 문장
- 단순 배경 설명
- 이미 반복된 내용
- 시각적으로 명확한 상황

### 자막 밀도 규칙 (CRITICAL!)
- 약 3문장 중 1개만 subtitle_on=true
- 절대 모든 문장에 자막 금지 (all_sentences: never)
- 씬당 subtitle_on=true 문장은 1-2개로 제한

### subtitle_text 변환 규칙
1. 조사 제거: 이/가/을/를/은/는/에서/으로
2. 어미 제거: ~습니다/~겠습니다/~드립니다
3. 접속사 제거: 그리고/그래서/또한/다음으로
4. 핵심만 유지: 숫자, 이름, 날짜, 핵심 명사
5. MAX 14자 (Korean)
6. 명사구 형태 (문장 아님)

### 변환 예시
| 원문 (sentence) | subtitle_on | subtitle_text |
|----------------|-------------|---------------|
| "1월 초에 결심공판을 거쳐서 2월 중순에 1심 선고가 예상됩니다" | true | "2월 중순 1심 선고" |
| "곽종근 전 특수전사령관이 법정에서 증언했습니다" | true | "곽종근 전 사령관 증언" |
| "이 소식에 많은 사람들이 놀랐습니다" | false | (없음) |
| "정말 충격적인 상황이었습니다" | false | (없음) |
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
