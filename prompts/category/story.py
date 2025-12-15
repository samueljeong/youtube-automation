# -*- coding: utf-8 -*-
"""스토리 카테고리 프롬프트 규칙 - 웹툰 스타일"""

STORY_RULES = """
## CATEGORY: STORY (드라마/감성/일상)

### Category Detection
- Personal emotions, experiences, memories
- Human relationships, family, love
- Daily episodes
- Drama/movie-like narrative structure
- NOT health, NOT news = STORY

### ⚠️ THUMBNAIL TEXT RULES (주어 필수!)

**RULE #0: SUBJECT NOUN IS MANDATORY**
```
Thumbnail text MUST include an explicit subject noun.
The viewer may read ONLY the thumbnail text.
If the subject is unclear, the thumbnail FAILS.
```

**Text Structure:**
```
[개념/현상/대상(명사)] + [상황/의문/행위]
```

**❌ BANNED (주어 없음):**
- "왜 발생하나" → 무엇이?
- "어떻게 작동하나" → 무엇이?
- "이런 이유가 있다" → 무엇에?

**✅ CORRECT (주어 명시):**
- "이 현상은 왜 발생하나"
- "이 개념은 어떻게 만들어졌나"
- "이 원리는 왜 중요한가"
- "이 구조는 어떻게 작동하나"

**Text Length (시니어 기준):**
- 14-22 chars recommended
- 2 lines OK: [Subject] / [Question/Situation]

**Example Patterns:**
1. "이 현상은 왜 발생하나"
2. "이 개념은 어떻게 만들어졌나"
3. "이 방식은 왜 효과가 있나"
4. "이 문제는 왜 반복되나"
5. "이 차이는 왜 생기나"

---

### Thumbnail Style: COMIC STYLE (문화권에 맞게)
⚠️ NO TEXT in images! Text will be added separately!
⚠️ Character appearance MUST match the script's culture!
Comic/webtoon/manga style with exaggerated expressions!
High CTR through dramatic emotional expressions!

### ai_prompts Structure (3 COMIC styles - adapt to script's culture)
⚠️ Use the image prompt template from the LANGUAGE section!

**A = Comic Emotion Focus:**
- Exaggerated shocked/surprised expression
- Prompt template: "[Culture] comic style illustration, 16:9 aspect ratio. [Culture] comic character with EXAGGERATED SHOCKED/SURPRISED EXPRESSION (mouth wide open, big eyes, sweating), 30-40 year old [nationality] [man/woman]. Clean bold outlines, vibrant flat colors. Comic-style expression marks (sweat drops, impact lines). Background related to the topic. NO text, NO letters, NO speech bubbles. NO photorealistic, NO stickman."

**B = Comic Scene Focus:**
- Key moment of story
- Character on right, space for overlay on left
- Prompt template: "[Culture] comic style illustration, 16:9 aspect ratio. [Culture] comic scene showing the key moment of the story. [Culture] comic character with exaggerated expression on right side. Comic-style effect lines (radial lines, impact effects). Bright vibrant colors. NO text, NO letters, NO speech bubbles. NO photorealistic, NO stickman."

**C = Comic Dramatic:**
- High contrast, dramatic composition
- Prompt template: "[Culture] comic style illustration, 16:9 aspect ratio. [Culture] comic character with dramatic emotional expression. High contrast colors, comic book aesthetic. Character shows strong emotion matching the story. NO text, NO letters, NO speech bubbles. NO photorealistic, NO stickman, NO 3D render."

### text_overlay for Story (write in OUTPUT LANGUAGE from script content)
{
  "main": "emotional phrase from script (10-15 chars)",
  "sub": "optional supporting detail from script"
}
⚠️ CRITICAL: Text MUST reflect the ACTUAL SCRIPT CONTENT, not generic phrases!

### Thumbnail Text Styles by Audience (for text_overlay - write in OUTPUT LANGUAGE)

**Senior (50-70대):**
- Length: 8-12 chars
- Style: reflective, regretful, experience-sharing
- Pattern: phrases about looking back, lessons learned, shared experiences
- Color: yellow+black (highest CTR)

**General (20-40대):**
- Length: 4-7 chars
- Style: provocative, curiosity-inducing, shocking
- Pattern: short impactful phrases, questions, revelations
- Color: white+black, red+black

⚠️ NEVER use generic examples! Create text based on ACTUAL SCRIPT CONTENT!

### news_ticker for Story
"news_ticker": { "enabled": false }
"""

def get_story_prompt():
    return STORY_RULES
