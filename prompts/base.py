# -*- coding: utf-8 -*-
"""공통 프롬프트 규칙 - 모든 언어/카테고리에 적용"""

# 한국 웹툰 캐릭터 규칙 (씬 이미지용)
WEBTOON_RULES = """
## CORE CONCEPT - KOREAN WEBTOON STYLE (CRITICAL!)
The key visual style for scene images is KOREAN WEBTOON/MANHWA:
1. Style = KOREAN WEBTOON (not Japanese anime, not stickman, not photorealistic)
2. Characters = Korean webtoon/manhwa style with EXAGGERATED EXPRESSIONS
3. Age = 30-50 year old Korean man or woman (match the story)
4. Features = Clean bold outlines, vibrant flat colors, comic-style expression marks

## WEBTOON CHARACTER DESCRIPTION (USE THIS STYLE)
"Korean webtoon/manhwa style character with exaggerated [emotion] expression (wide eyes, [mouth expression], sweat drops),
30-50 year old Korean [man/woman], clean bold outlines, vibrant colors"

**Emotion expressions:**
- Shocked: wide eyes, open mouth, sweat drops, impact lines
- Sad: gentle sad eyes, slight frown, tears
- Happy: bright eyes, big smile, sparkles
- Angry: narrowed eyes, gritted teeth, veins
- Worried: furrowed brows, sweat drop, hand gesture
- Surprised: huge eyes, small open mouth, raised eyebrows

## MANDATORY STYLE KEYWORDS (MUST INCLUDE IN EVERY image_prompt)
- Korean WEBTOON/manhwa style illustration
- 16:9 aspect ratio
- Korean webtoon character with EXAGGERATED [emotion] EXPRESSION
- 30-50 year old Korean man or woman
- Clean bold outlines, vibrant flat colors
- Comic-style expression marks (sweat drops, impact lines)
- NO photorealistic, NO stickman, NO anime, NO 3D render
- NO text, NO letters, NO words, NO speech bubbles (CRITICAL!)

## SCENE IMAGE PROMPT TEMPLATE
"Korean WEBTOON/manhwa style illustration, 16:9 aspect ratio.
[Background description related to scene].
Korean webtoon character with EXAGGERATED [emotion] EXPRESSION ([specific expression details]),
30-50 year old Korean [man/woman].
Clean bold outlines, vibrant flat colors, comic-style expression marks.
NO text, NO letters, NO speech bubbles.
NO photorealistic, NO stickman, NO anime, NO 3D render."
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
  "screen_overlays": [{"scene": N, "text": "1-4 chars", "duration": 3, "style": "impact"}],
  "sound_effects": [{"scene": N, "type": "...", "moment": "..."}],
  "lower_thirds": [{"scene": N, "text": "...", "position": "bottom-left"}],
  "news_ticker": {"enabled": true/false, "headlines": ["...", "..."]},
  "shorts": {"highlight_scenes": [N, M], "hook_text": "...", "title": "... #Shorts"},
  "transitions": {"style": "crossfade", "duration": 0.5},
  "first_comment": "engaging question (50-100 chars)"
}
"""

# 유튜브 메타데이터 출력 구조
YOUTUBE_META_STRUCTURE = """
## YOUTUBE METADATA OUTPUT STRUCTURE
"youtube": {
  "title": "main title",
  "title_options": [
    {"style": "curiosity", "title": "..."},
    {"style": "solution", "title": "..."},
    {"style": "authority", "title": "..."}
  ],
  "description": {
    "full_text": "full description (600-1200 chars)",
    "preview_2_lines": "first 2 lines for search preview",
    "chapters": [{"time": "00:00", "title": "..."}]
  },
  "hashtags": ["#tag1", "#tag2"],
  "tags": ["tag1", "tag2"],
  "pin_comment": "pinned comment with question"
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
    "image_prompt": "Korean WEBTOON/manhwa style illustration...",
    "ken_burns": "zoom_in | zoom_out | pan_left | pan_right | pan_up | pan_down"
  }
]

CRITICAL: "narration" MUST contain EXACT text from the script!
- DO NOT summarize or paraphrase
- COPY-PASTE the exact sentences
- ADD SSML tags for emotion
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
1. SCENE image_prompt = Korean WEBTOON/manhwa style (NO photorealistic, NO stickman!)
2. THUMBNAIL ai_prompts = Korean WEBTOON/manhwa style (ALL categories!)
3. NARRATION = EXACT script text + SSML tags (DO NOT summarize!)
4. image_prompt = ALWAYS in English
5. All other text (title, description, thumbnail) = OUTPUT LANGUAGE

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
        WEBTOON_RULES,
        SSML_RULES,
        KEN_BURNS_RULES,
        BGM_RULES,
        SFX_RULES,
        VIDEO_EFFECTS_STRUCTURE,
        YOUTUBE_META_STRUCTURE,
        SCENE_STRUCTURE,
        OUTPUT_JSON_STRUCTURE,
    ])
