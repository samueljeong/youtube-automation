# -*- coding: utf-8 -*-
"""건강/의료 카테고리 프롬프트 규칙 - 웹툰 스타일"""

HEALTH_RULES = """
## CATEGORY: HEALTH (건강/의료)

### Category Detection
Health, medical, symptoms, treatment, prevention, doctor, hospital topics

### ⚠️⚠️⚠️ YOUTUBE TITLE RULES FOR HEALTH (CRITICAL!) ⚠️⚠️⚠️

**Algorithm Optimization:**
- **First 20 chars**: MUST contain body part/condition/habit keyword
- **Total length**: 25-45 chars
- **Structure**: [Body/Habit] + [Change/Effect] + [Target]
- Use gentle warnings, avoid sensationalism

**Title Formulas:**

1. **Symptom/Signal (증상/신호형)**:
   - `{부위/상태}가 보내는 신호`
   - `{증상}이 나타나는 이유`
   - `{나이}가 되면 달라지는 {부위}`
   - `무심코 놓치기 쉬운 {증상}`

2. **Habit/Cause (습관/원인형)**:
   - `{결과}를 만드는 생활 습관`
   - `무심코 반복하는 {나쁜 습관}`
   - `{문제}가 생기는 과정`
   - `{상태}를 악화시키는 행동`

3. **Effect/Change (영향/변화형)**:
   - `{요인}이 {부위}에 미치는 영향`
   - `{습관}이 남기는 흔적`
   - `{상태}가 지속될 때 생기는 일`

4. **Age/Target (연령별/대상별)**:
   - `{나이}대 이후 중요해지는 것`
   - `{나이}에 따라 달라지는 기준`
   - `{나이}대가 주의해야 할 {주제}`

5. **Prevention/Management (예방/관리형)**:
   - `{목표}를 지키는 기본 원칙`
   - `{문제} 예방을 위해 알아야 할 것`
   - `{상태}를 개선하는 방법`

**Universal Templates:**
- `{keyword}가 보내는 신호`
- `{keyword}이 나타나는 이유`
- `{keyword}를 만드는 생활 습관`
- `{keyword}에 미치는 영향`
- `{keyword}대가 주의해야 할 것`

⚠️ CRITICAL: Extract {keyword} from the ACTUAL SCRIPT CONTENT!

### Thumbnail Style: COMIC STYLE DOCTOR (문화권에 맞게)
⚠️ NO PHOTOREALISTIC! Use comic/webtoon/manga style matching the script's language!
⚠️ NO TEXT in images! Text will be added separately!
⚠️ Doctor/character appearance MUST match the script's culture!

**Thumbnail Text Patterns (for text_overlay - write in OUTPUT LANGUAGE):**
- Numbers: specific numbers from script (age, percentage, count, time)
- Warning: warning phrases related to script content
- Result: outcome phrases related to script topic
⚠️ CRITICAL: Text MUST relate to the ACTUAL SCRIPT CONTENT, not generic health topics!

### ai_prompts Structure (3 COMIC styles - adapt to script's culture)
⚠️ Use the image prompt template from the LANGUAGE section!

**A = Comic Doctor Close-up:**
- Comic style doctor character matching script's culture
- Exaggerated concerned/serious expression
- Prompt template: "[Culture] comic style illustration, 16:9 aspect ratio. [Culture] comic character DOCTOR with SERIOUS/CONCERNED EXPRESSION (furrowed brows, slight frown), 50 year old [nationality] man in white coat. Clean bold outlines, professional colors, medical office background. Comic-style expression marks. NO text, NO letters, NO speech bubbles. NO photorealistic, NO stickman."

**B = Comic Doctor Warning Gesture:**
- Doctor character with warning hand gesture
- Prompt template: "[Culture] comic style illustration, 16:9 aspect ratio. [Culture] comic character DOCTOR pointing finger in WARNING gesture with STERN EXPRESSION, 50 year old [nationality] woman in white coat. Clean bold outlines, dramatic pose, hospital background. Comic-style impact lines. NO text, NO letters, NO speech bubbles. NO photorealistic, NO stickman."

**C = Comic Medical Scene:**
- Doctor with medical equipment/chart (no text on chart)
- Prompt template: "[Culture] comic style illustration, 16:9 aspect ratio. [Culture] comic character DOCTOR with WORRIED EXPRESSION looking at medical equipment, 50 year old [nationality] man in white coat. Hospital room with medical devices. Clean bold outlines, professional atmosphere. NO text, NO letters, NO speech bubbles, NO readable charts. NO photorealistic, NO stickman."

### text_overlay for Health (write in OUTPUT LANGUAGE based on script content)
{
  "warning": "warning phrase from script topic",
  "numbers": "specific numbers from script",
  "result": "outcome related to script"
}
⚠️ NEVER use generic examples! Extract actual topics from the script!

### Output Structure
"thumbnail": {
  "thumbnail_text": {
    "quote": "key phrase from script (OUTPUT LANGUAGE)",
    "headline": "main headline from script topic",
    "numbers": "numbers mentioned in script"
  },
  "visual_elements": {
    "main_subject": "actual health topic from script",
    "person_description": "doctor character matching script's culture",
    "scene_description": "medical setting matching script's culture",
    "emotion": "appropriate emotion",
    "color_scheme": "red-urgent"
  },
  "ai_prompts": { "A": {...}, "B": {...}, "C": {...} }
}
"""

def get_health_prompt():
    return HEALTH_RULES
