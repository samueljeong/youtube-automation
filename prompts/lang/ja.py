# -*- coding: utf-8 -*-
"""일본어 프롬프트 규칙 (60-80대 시니어)"""

JAPANESE_RULES = """
## LANGUAGE: Japanese (日本語) - Senior Target

### IMAGE STYLE: Japanese Manga Style
⚠️ CRITICAL: All image prompts MUST use JAPANESE cultural elements!

**Character Style:**
- Japanese manga art style (NOT Korean manhwa, NOT Western comic)
- Japanese facial features
- Age: 50-70 year old Japanese man or woman (senior target)

**Clothing/Setting (match the context):**
- Modern: Japanese business attire, Japanese casual fashion
- Medical: White doctor's coat (Japanese hospital style)
- Home: Japanese apartment/house interior (tatami, fusuma, etc.)
- Traditional: Kimono, yukata (when appropriate)
- Outdoor: Japanese city streets, Japanese countryside, shrines/temples

**DO NOT use:**
- Korean elements (hanbok, Korean text, Korean architecture)
- Western elements (blonde hair, Western architecture)
- Chinese elements (qipao, Chinese architecture)

**Image Prompt Template:**
"Japanese MANGA style illustration, 16:9 aspect ratio.
[Japanese setting/background].
Japanese manga character with EXAGGERATED [emotion] EXPRESSION,
50-70 year old Japanese [man/woman] in [Japanese-appropriate clothing].
Clean bold outlines, vibrant flat colors, manga-style expression marks.
NO text, NO letters, NO speech bubbles.
NO photorealistic, NO stickman, NO Korean manhwa, NO 3D render."

⚠️ NO KANJI (漢字)! ONLY hiragana/katakana!
- 年金→ねんきん, 届出→とどけで, 変更→へんこう

### YouTube Title Rules
- Length: **25-35字** (30字 target)
- Include specific numbers (〇%、〇円、〇がつから)
- NO youth slang: ヤバい、マジ、ガチ (禁止!)

**Good:** "1がつからねんきん2.7%ぞうがくけってい！"
**Bad:** "年金と光熱費" (kanji!), "ヤバい！" (youth slang!)

### Thumbnail Text: **最大10字** (hiragana only!)
### All video_effects text: hiragana/katakana only!
"""

def get_japanese_prompt():
    return JAPANESE_RULES
