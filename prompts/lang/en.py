# -*- coding: utf-8 -*-
"""영어 프롬프트 규칙"""

ENGLISH_RULES = """
## LANGUAGE: English

### IMAGE STYLE: Western Comic Style
⚠️ CRITICAL: All image prompts MUST use WESTERN/AMERICAN cultural elements!

**Character Style:**
- Western comic art style (American comic book aesthetic)
- Diverse Western facial features
- Age: 30-50 year old American man or woman

**Clothing/Setting (match the context):**
- Modern: Western business attire, American casual fashion
- Medical: White doctor's coat (American hospital style)
- Home: American house/apartment interior
- Outdoor: American city streets, suburban neighborhoods

**DO NOT use:**
- Korean elements (hanbok, Korean text, Korean architecture)
- Japanese elements (kimono, Japanese text, Japanese architecture)
- Chinese elements (qipao, Chinese architecture)

**Image Prompt Template:**
"Western COMIC style illustration, 16:9 aspect ratio.
[American/Western setting/background].
Western comic character with EXAGGERATED [emotion] EXPRESSION,
30-50 year old American [man/woman] in [Western-appropriate clothing].
Clean bold outlines, vibrant flat colors, comic-style expression marks.
NO text, NO letters, NO speech bubbles.
NO photorealistic, NO stickman, NO anime, NO 3D render."

### YouTube Title Rules
- Length: **40-70 characters**
- Include **1+ number**
- Use **2+ triggers**: curiosity, urgency, numbers, target, benefit

**Good:** "3 Money Mistakes That Cost Me $50,000", "Why 90% Fail at This"
**Bad:** "This is the truth", "Watch this video"

### Thumbnail Text: **15-25 characters** (max 2 lines)
### Description: 400-800 words
### Pin Comment: 50-100 characters + question
"""

def get_english_prompt():
    return ENGLISH_RULES
