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

# SSML 규칙 제거됨 - Chirp 3 HD/Gemini TTS가 SSML 태그를 무시함

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

# video_effects 출력 구조 (단순화됨)
VIDEO_EFFECTS_STRUCTURE = """
## VIDEO_EFFECTS OUTPUT STRUCTURE
"video_effects": {
  "bgm_mood": "base mood (hopeful/sad/tense/dramatic/calm/cinematic/mysterious/nostalgic/epic/comedic/horror/upbeat)",
  "scene_bgm_changes": [{"scene": N, "mood": "...", "reason": "..."}],
  "sound_effects": [{"scene": N, "type": "impact/whoosh/ding/tension/emotional/success", "moment": "..."}],
  "transitions": {"style": "crossfade", "duration": 0.5},
  "first_comment": "engaging question (50-100 chars)"
}
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

# 씬 출력 구조 (단순화됨 - VRCS 제거)
SCENE_STRUCTURE = """
## SCENE OUTPUT STRUCTURE
"scenes": [
  {
    "scene_number": 1,
    "chapter_title": "short title (5-15 chars)",
    "narration": "EXACT original script text (plain text, no tags)",
    "image_prompt": "[Culture-appropriate] comic style illustration... (see LANGUAGE section for template)",
    "ken_burns": "zoom_in | zoom_out | pan_left | pan_right | pan_up | pan_down"
  }
]

CRITICAL: "narration" MUST contain EXACT text from the script!
- DO NOT summarize or paraphrase
- COPY-PASTE the exact sentences
- Plain text only (no SSML tags - TTS doesn't use them)
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
3. NARRATION = EXACT script text (DO NOT summarize!)
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
        KEN_BURNS_RULES,
        BGM_RULES,
        SFX_RULES,
        VIDEO_EFFECTS_STRUCTURE,
        YOUTUBE_META_STRUCTURE,
        SCENE_STRUCTURE,
        OUTPUT_JSON_STRUCTURE,
    ])
