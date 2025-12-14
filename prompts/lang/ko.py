# -*- coding: utf-8 -*-
"""한국어 프롬프트 규칙"""

KOREAN_RULES = """
## LANGUAGE: Korean (한국어)

### IMAGE STYLE: Korean Webtoon/Manhwa
⚠️ CRITICAL: All image prompts MUST use KOREAN cultural elements!

**Character Style:**
- Korean webtoon/manhwa art style
- Korean facial features (East Asian appearance)
- Age: 30-50 year old Korean man or woman

**Clothing/Setting (match the context):**
- Modern: Korean business attire, casual Korean fashion
- Medical: White doctor's coat (Korean hospital style)
- Home: Korean apartment interior, Korean furniture
- Outdoor: Korean city streets, Korean countryside

**DO NOT use:**
- Japanese elements (kimono, Japanese text, Japanese architecture)
- Western elements (blonde hair, Western architecture)
- Chinese elements (qipao, Chinese architecture)

**Image Prompt Template:**
"Korean WEBTOON/manhwa style illustration, 16:9 aspect ratio.
[Korean setting/background].
Korean webtoon character with EXAGGERATED [emotion] EXPRESSION,
30-50 year old Korean [man/woman] in [Korean-appropriate clothing].
Clean bold outlines, vibrant flat colors, comic-style expression marks.
NO text, NO letters, NO speech bubbles.
NO photorealistic, NO stickman, NO anime, NO 3D render."

### YouTube Title Rules
- Length: **18-32자** (공백 포함)
- Must include **1+ number** (year, count, amount)
- Use **2+ triggers**: 호기심, 긴급성, 숫자, 타깃, 결과
- NO clickbait ("충격", "소름", "멸망" 금지)

**Good:** "60년 인생이 가르쳐준 3가지 후회", "2025년 부동산 세금 변화"
**Bad:** "충격적인 발견", "이것이 진실입니다"

### Thumbnail Text Rules
- Length: **10-15자** (max 2 lines, \\n for break)
- Styles: 질문형, 문제제기형, 해결형, 숫자+위험형

### Description: 600-1200자
### Pin Comment: 50-100자 + 질문
"""

def get_korean_prompt():
    return KOREAN_RULES
