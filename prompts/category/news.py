# -*- coding: utf-8 -*-
"""뉴스 카테고리 프롬프트 규칙 - 웹툰 스타일"""

NEWS_RULES = """
## CATEGORY: NEWS (뉴스/시사)

### Category Detection Keywords
정치인, 대통령, 국회, 정당, 경제, 주가, 환율, 부동산,
사건, 사고, 사회 이슈, 논쟁, 갈등, 기업, 브랜드,
법원, 검찰, 재판

### Thumbnail Style: COMIC STYLE (문화권에 맞게)
⚠️ NO PHOTOREALISTIC! Use comic/webtoon/manga style matching the script's language!
⚠️ NO TEXT in images! Text will be added separately!
⚠️ Character appearance MUST match the script's culture!

**Extract from script (for text_overlay, NOT in image):**
- person_name: 핵심 인물 이름 (조진웅, 윤석열 등)
- entity_name: 기업/기관명 (쿠팡, 삼성전자 등)
- quote: 충격적/흥미로운 발언 "따옴표"
- headline: 핵심 헤드라인 2줄
- numbers: 강조 숫자 (30년, 3370만)

### ai_prompts Structure (3 COMIC styles - adapt to script's culture)
⚠️ Use the image prompt template from the LANGUAGE section!

**A = Comic Person Close-up:**
- Comic style character representing the key person (matching script's culture)
- Exaggerated emotional expression matching the news tone
- Prompt template: "[Culture] comic style illustration, 16:9 aspect ratio. [Culture] comic character with SHOCKED/SERIOUS EXPRESSION (wide eyes, tense face), 40-50 year old [nationality] [man/woman] in [suit/formal wear]. Clean bold outlines, dramatic lighting, news studio or office background. Comic-style expression marks. NO text, NO letters, NO speech bubbles, NO name tags. NO photorealistic, NO stickman."

**B = Comic Scene/Event:**
- Comic style scene related to the news (matching script's culture)
- Prompt template: "[Culture] comic style illustration, 16:9 aspect ratio. [Culture] comic scene showing [related location/event]. [Culture] comic character with CONCERNED EXPRESSION in the scene. Clean bold outlines, dramatic mood, vibrant colors. Comic-style atmosphere. NO text, NO letters, NO speech bubbles, NO signs, NO readable text. NO photorealistic, NO stickman."

**C = Comic Split/Contrast:**
- Split composition showing contrast or comparison
- Prompt template: "[Culture] comic style illustration, 16:9 aspect ratio. Split composition: left side [culture] comic character with [emotion A], right side [culture] comic character with [emotion B]. Clean bold outlines, contrasting colors (left calm, right dramatic). Comic-style dramatic effect. NO text, NO letters, NO speech bubbles. NO photorealistic, NO stickman."

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
