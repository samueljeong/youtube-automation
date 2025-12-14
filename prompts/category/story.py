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

### Thumbnail Style: KOREAN WEBTOON
⚠️ NO TEXT in images! Text will be added separately!
Korean webtoon/manhwa style with exaggerated expressions!
High CTR through dramatic emotional expressions!

### ai_prompts Structure (3 WEBTOON styles)

**A = Webtoon Emotion Focus:**
- Exaggerated shocked/surprised expression
- Prompt: "Korean WEBTOON/manhwa style illustration, 16:9 aspect ratio. Korean webtoon character with EXAGGERATED SHOCKED/SURPRISED EXPRESSION (mouth wide open, big eyes, sweating), 30-40 year old Korean [man/woman]. Clean bold outlines, vibrant flat colors. Comic-style expression marks (sweat drops, impact lines). Background related to the topic. NO text, NO letters, NO speech bubbles. NO photorealistic, NO stickman."

**B = Webtoon Scene Focus:**
- Key moment of story
- Character on right, space for overlay on left
- Prompt: "Korean WEBTOON/manhwa style illustration, 16:9 aspect ratio. Korean webtoon scene showing the key moment of the story. Korean webtoon character with exaggerated expression on right side. Comic-style effect lines (radial lines, impact effects). Bright vibrant colors. NO text, NO letters, NO speech bubbles. NO photorealistic, NO stickman."

**C = Webtoon Dramatic:**
- High contrast, dramatic composition
- Prompt: "Korean WEBTOON/manhwa style illustration, 16:9 aspect ratio. Korean webtoon character with dramatic emotional expression. High contrast colors, comic book aesthetic. Character shows strong emotion matching the story. NO text, NO letters, NO speech bubbles. NO photorealistic, NO stickman, NO 3D render."

### text_overlay for Story (applied separately, NOT in image)
{
  "main": "감정 텍스트 (10-15자)",
  "sub": "optional (부연 설명)"
}

### Thumbnail Text Styles by Audience (for text_overlay)

**Senior (50-70대):**
- Length: 8-12자
- Style: 회상형, 후회형, 경험공유형
- Examples: "그날을 잊지 않는다", "하는게 아니었다", "늦게 알았다"
- Color: 노랑+검정 (highest CTR)

**General (20-40대):**
- Length: 4-7자
- Style: 자극형, 궁금증형, 충격형
- Examples: "결국 터졌다", "이게 실화?", "소름 돋았다"
- Color: 흰색+검정, 빨강+검정

### news_ticker for Story
"news_ticker": { "enabled": false }
"""

def get_story_prompt():
    return STORY_RULES
