# -*- coding: utf-8 -*-
"""건강/의료 카테고리 프롬프트 규칙 - 웹툰 스타일"""

HEALTH_RULES = """
## CATEGORY: HEALTH (건강/의료)

### Category Detection Keywords
건강, 질병, 증상, 치료, 예방, 의사, 병원, 약, 검사, 진단,
혈압, 혈당, 관절, 심장, 뇌, 영양제, 운동법, 노화, 장수,
치매, 암, 당뇨, "~하면 안됩니다", "~하지 마세요"

### Thumbnail Style: COMIC STYLE DOCTOR (문화권에 맞게)
⚠️ NO PHOTOREALISTIC! Use comic/webtoon/manga style matching the script's language!
⚠️ NO TEXT in images! Text will be added separately!
⚠️ Doctor/character appearance MUST match the script's culture!

**Thumbnail Text Patterns (for text_overlay, NOT in image):**
- Numbers: "5가지", "3초", "90대", "8시간", "30%"
- Warning: "절대 하지마세요", "~하면 끝!", "의사도 경고"
- Shock: "99%는 몰라서 후회", "이것만 알면", "당장 중단하세요"
- Result: "~이 사라집니다", "~이 좋아집니다"

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

### text_overlay for Health (applied separately, NOT in image)
{
  "line1": "70대가 넘으면",
  "line2": "절대 하지마세요",
  "line3": "5가지 검사는",
  "line4": "의사들도 피합니다",
  "highlight": "5가지 검사"
}

### Output Structure
"thumbnail": {
  "thumbnail_text": {
    "person_name": "",
    "entity_name": "",
    "quote": "경고/충격 문구",
    "headline": "핵심 헤드라인",
    "numbers": "강조 숫자"
  },
  "visual_elements": {
    "main_subject": "건강 주제",
    "person_description": "50대 의사 캐릭터 (문화권에 맞게)",
    "scene_description": "병원 진료실 (문화권에 맞는 만화 스타일)",
    "emotion": "우려",
    "color_scheme": "red-urgent"
  },
  "ai_prompts": { "A": {...}, "B": {...}, "C": {...} }
}
"""

def get_health_prompt():
    return HEALTH_RULES
