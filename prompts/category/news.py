# -*- coding: utf-8 -*-
"""뉴스 카테고리 프롬프트 규칙 - 웹툰 스타일"""

NEWS_RULES = """
## CATEGORY: NEWS (뉴스/시사)

### Category Detection Keywords
정치인, 대통령, 국회, 정당, 경제, 주가, 환율, 부동산,
사건, 사고, 사회 이슈, 논쟁, 갈등, 기업, 브랜드,
법원, 검찰, 재판

### Thumbnail Style: KOREAN WEBTOON
⚠️ NO PHOTOREALISTIC! Use Korean webtoon/manhwa style!
⚠️ NO TEXT in images! Text will be added separately!

**Extract from script (for text_overlay, NOT in image):**
- person_name: 핵심 인물 이름 (조진웅, 윤석열 등)
- entity_name: 기업/기관명 (쿠팡, 삼성전자 등)
- quote: 충격적/흥미로운 발언 "따옴표"
- headline: 핵심 헤드라인 2줄
- numbers: 강조 숫자 (30년, 3370만)

### ai_prompts Structure (3 WEBTOON styles)

**A = Webtoon Person Close-up:**
- Korean webtoon style character representing the key person
- Exaggerated emotional expression matching the news tone
- Prompt: "Korean WEBTOON/manhwa style illustration, 16:9 aspect ratio. Korean webtoon character with SHOCKED/SERIOUS EXPRESSION (wide eyes, tense face), 40-50 year old Korean [man/woman] in [suit/formal wear]. Clean bold outlines, dramatic lighting, news studio or office background. Comic-style expression marks. NO text, NO letters, NO speech bubbles, NO name tags. NO photorealistic, NO stickman, NO anime."

**B = Webtoon Scene/Event:**
- Korean webtoon style scene related to the news
- Prompt: "Korean WEBTOON/manhwa style illustration, 16:9 aspect ratio. Korean webtoon scene showing [related location/event]. Korean webtoon character with CONCERNED EXPRESSION in the scene. Clean bold outlines, dramatic mood, vibrant colors. Comic-style atmosphere. NO text, NO letters, NO speech bubbles, NO signs, NO readable text. NO photorealistic, NO stickman."

**C = Webtoon Split/Contrast:**
- Split composition showing contrast or comparison
- Prompt: "Korean WEBTOON/manhwa style illustration, 16:9 aspect ratio. Split composition: left side Korean webtoon character with [emotion A], right side Korean webtoon character with [emotion B]. Clean bold outlines, contrasting colors (left calm, right dramatic). Comic-style dramatic effect. NO text, NO letters, NO speech bubbles. NO photorealistic, NO stickman."

### Color Schemes (for design reference, NOT in image)
- yellow-highlight: General news
- cyan-news: Info news
- pink-scandal: Entertainment/scandal
- red-urgent: Breaking news
- blue-trust: Official announcement

### text_overlay for News (applied separately)
{
  "name": "인물명 또는 기업명",
  "main": "핵심 문구 (15자 이내)",
  "sub": "부연 설명 (20자 이내)",
  "color": "yellow | cyan | pink"
}

### news_ticker (for video effects, NOT in image)
"news_ticker": {
  "enabled": true,
  "headlines": ["속보: ...", "이슈: ...", "핵심: ..."]
}
"""

def get_news_prompt():
    return NEWS_RULES
