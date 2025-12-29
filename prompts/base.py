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
## YOUTUBE METADATA OUTPUT STRUCTURE (SEO OPTIMIZED)

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
  "title": "main title - MUST reflect actual script topic! (50-70 chars optimal)",
  "title_options": [
    {"style": "curiosity", "title": "curiosity-style title about SCRIPT TOPIC"},
    {"style": "solution", "title": "solution-style title about SCRIPT TOPIC"},
    {"style": "authority", "title": "authority-style title about SCRIPT TOPIC"}
  ],
  "description": {
    "full_text": "SEO-optimized description (800-1500 chars). Include: 1) Hook sentence 2) Main topic summary 3) Key points covered 4) Call-to-action. Use natural keyword placement.",
    "preview_2_lines": "First 2 lines are crucial for CTR - make them compelling and include main keyword!",
    "chapters": [{"time": "00:00", "title": "chapter title"}]
  },
  "hashtags": ["#main_keyword", "#topic1", "#topic2", "#trending", "#category"],
  "tags": [
    "Generate 15-20 SEO tags:",
    "- Main topic keywords (3-4)",
    "- Related topic keywords (3-4)",
    "- Long-tail keywords (3-4)",
    "- Trending/popular related terms (3-4)",
    "- Category/niche keywords (2-3)"
  ],
  "pin_comment": "⚠️ REQUIRED! 50-150 chars. Format: [1-2 sentences about video content] + [engaging question]. Example: 'This video covered XX - what an amazing story! What do you think? Share your thoughts in comments!'"
}

### ⚠️ PIN_COMMENT RULES (CRITICAL!):
- **MUST generate** - never leave empty!
- **Language**: Same as script language (Korean script → Korean comment)
- **Length**: 50-150 characters
- **Structure**: [Key content summary] + [Viewer engagement question]
- **Question examples**:
  - "What do you think about this?"
  - "Have you had a similar experience? Share in comments!"
  - "Which part resonated with you the most?"

### ⚠️ SEO REQUIREMENTS:
- **Tags**: Generate exactly 15-20 relevant tags. Mix short keywords and long-tail phrases.
- **Hashtags**: Generate 3-5 hashtags. First hashtag = main keyword.
- **Description**: Must be 800+ characters. Include timestamps, keywords naturally.
- **Title**: 50-70 characters optimal for YouTube search.
"""

# 씬 출력 구조 (단순화됨 - VRCS 제거)
SCENE_STRUCTURE = """
## SCENE OUTPUT STRUCTURE

⚠️⚠️⚠️ CRITICAL INSTRUCTION FOR NARRATION ⚠️⚠️⚠️
The "narration" field MUST contain the EXACT ORIGINAL SCRIPT TEXT!
- DIVIDE the script into scenes - DO NOT SUMMARIZE!
- Each scene's narration = a PORTION of the original script
- Total narration across ALL scenes = ENTIRE original script
- Example: 24,000 char script ÷ 12 scenes = ~2,000 chars per scene

❌ WRONG: "광개토대왕은 영토를 확장했습니다" (143 chars - summarized!)
✅ RIGHT: [Copy 2000+ chars from original script for this scene]

"scenes": [
  {
    "scene_number": 1,
    "chapter_title": "short title (5-15 chars)",
    "narration": "[PASTE 1500-2500 chars of ORIGINAL SCRIPT TEXT HERE - NOT A SUMMARY!]",
    "image_prompt": "[Culture-appropriate] comic style illustration...",
    "ken_burns": "zoom_in | zoom_out | pan_left | pan_right | pan_up | pan_down"
  }
]

VERIFICATION: If your script is 24,000 chars and you have 12 scenes:
- Each narration should be ~2,000 chars
- Total narration = ~24,000 chars (matches original script!)
- If total narration < 10,000 chars → YOU ARE SUMMARIZING (WRONG!)
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
3. ⚠️ NARRATION = EXACT ORIGINAL SCRIPT TEXT! (NEVER summarize - COPY the script!)
4. image_prompt = ALWAYS in English
5. All other text (title, description, thumbnail) = OUTPUT LANGUAGE
6. Cultural elements MUST match the script's language (Korean→Korean, Japanese→Japanese, English→Western)

## ⚠️⚠️⚠️ MOST IMPORTANT: NARRATION RULE ⚠️⚠️⚠️
- The "narration" field in each scene = EXACT COPY of original script text
- DO NOT write new sentences! DO NOT summarize!
- DIVIDE the script into N scenes, each containing ~2000 chars of ORIGINAL text
- Total chars in all narrations combined MUST EQUAL the original script length!

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
