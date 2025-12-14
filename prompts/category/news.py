# -*- coding: utf-8 -*-
"""뉴스 카테고리 프롬프트 규칙 - 웹툰 스타일"""

NEWS_RULES = """
## CATEGORY: NEWS (뉴스/시사)

### Category Detection
Politics, economy, social issues, companies, legal matters, current events

### Thumbnail Style: COMIC STYLE (문화권에 맞게)
⚠️ NO PHOTOREALISTIC! Use comic/webtoon/manga style matching the script's language!
⚠️ NO TEXT in images! Text will be added separately!
⚠️ Character appearance MUST match the script's culture!

**Extract from script (for text_overlay - write in OUTPUT LANGUAGE):**
- person_name: key person name FROM THE SCRIPT
- entity_name: company/organization name FROM THE SCRIPT
- quote: shocking/interesting statement FROM THE SCRIPT
- headline: main headline FROM THE SCRIPT topic
- numbers: specific numbers FROM THE SCRIPT
⚠️ CRITICAL: ALL text MUST come from the ACTUAL SCRIPT CONTENT!

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

### text_overlay for News (write in OUTPUT LANGUAGE from script content)
{
  "name": "person or entity name from script",
  "main": "key phrase from script (max 15 chars)",
  "sub": "supporting detail from script (max 20 chars)",
  "color": "yellow | cyan | pink"
}
⚠️ NEVER use generic examples! Extract actual names/topics from the script!

### news_ticker (for video effects - write in OUTPUT LANGUAGE)
"news_ticker": {
  "enabled": true,
  "headlines": ["breaking news from script...", "key point from script..."]
}
"""

def get_news_prompt():
    return NEWS_RULES
