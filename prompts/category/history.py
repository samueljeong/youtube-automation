# -*- coding: utf-8 -*-
"""역사 카테고리 프롬프트 규칙"""

HISTORY_RULES = """
## CATEGORY: HISTORY (역사)

### Category Detection Keywords
역사, 조선, 고려, 삼국, 일제, 전쟁, 왕, 황제, 고대, 중세, 근대, 임진왜란, 병자호란

### ⚠️⚠️⚠️ YOUTUBE TITLE RULES FOR HISTORY (CRITICAL!) ⚠️⚠️⚠️

**Algorithm Optimization:**
- **First 20 chars**: MUST contain era/person/event keyword
- **Total length**: 25-45 chars
- **Structure**: [Era/Person/Event] + [Background/Situation] + [Result hint]
- Dramatic but fact-based storytelling

**Title Formulas:**

1. **Person (인물형)**:
   - `{인물}이 가장 두려워했던 순간`
   - `{인물}의 선택이 남긴 결과`
   - `{인물}이 {상황}에서 내린 결정`
   - `조용히 사라진 {인물}의 이야기`

2. **Event/War (사건/전쟁형)**:
   - `한 번의 {행동}이 역사를 바꿨다`
   - `{결과}가 시작된 결정적 순간`
   - `{사건} 뒤에 숨겨진 이야기`
   - `{상황}이 폭발하기 직전의 신호`

3. **Pattern/Analysis (패턴/분석형)**:
   - `역사에서 반복된 {주제}`
   - `역사가 같은 {행동}을 반복한 이유`
   - `{결과}를 무너뜨린 {원인}`
   - `반복해서 등장하는 {현상}의 징조`

4. **Lesson/Insight (교훈/통찰형)**:
   - `역사가 남긴 {주제}`
   - `우리가 교과서에서 놓친 장면`
   - `역사가 우리에게 묻는 질문`

5. **Era/Change (시대/변화형)**:
   - `시대가 바뀌는 경계선`
   - `역사의 흐름을 바꾼 결정`
   - `{시대}에서 가장 치명적이었던 판단`

**Universal Templates:**
- `{keyword}이 가장 두려워했던 순간`
- `{keyword}의 선택이 남긴 결과`
- `{keyword}에서 반복된 실수`
- `{keyword} 뒤에 숨겨진 이야기`
- `{keyword}가 무너진 결정적 이유`

⚠️ CRITICAL: Extract {keyword} from the ACTUAL SCRIPT CONTENT!

### Thumbnail Style: HISTORICAL CONCEPT ART + MASCOT (SAME STYLE AS SCENES!)
⚠️ CRITICAL: Thumbnail MUST use the EXACT SAME style as scene images!
⚠️ Historical setting and costume matching the era
⚠️ SAME MASCOT CHARACTER as scenes (larger size for thumbnail visibility)

**Thumbnail Prompt Template (MUST MATCH SCENE STYLE!):**
```
Historical concept art thumbnail, [MAIN SCENE DESCRIPTION],
sepia and earth tone color palette, aged parchment texture border, vintage canvas feel,
digital painting with visible brush strokes, dramatic cinematic lighting,
LEFT SIDE (30% of frame): EXACT MASCOT - cute Korean scholar character with round face, circular wire-frame glasses, black traditional topknot (sangtu) hairstyle, wearing cream/beige hanbok with olive-green patterned vest, holding bamboo scroll, warm earth tone colors only, thick clean outlines, friendly expression, expressive pose pointing at or reacting to scene,
historical scene on right side with period-accurate costumes,
aged vintage feel, eye-catching YouTube thumbnail composition,
NO text, NO watermark, NO labels, 16:9 aspect ratio
```

**ai_prompts A/B/C templates (ALL use EXACT SAME MASCOT!):**
- A: Wide historical scene + mascot on LEFT (30%) pointing at key element with curious expression
- B: Battle/court scene + mascot on LEFT (30%) reacting with surprised/concerned expression
- C: Dramatic moment + mascot on LEFT (30%) with thoughtful/contemplative expression

⚠️ MASCOT MUST BE IDENTICAL IN ALL IMAGES:
- Round face, circular wire-frame glasses
- Black topknot (sangtu) on top of head
- Cream/beige hanbok with olive-green patterned vest
- Holding bamboo scroll or book
- Warm earth tones ONLY (beige, cream, olive, muted gold)
- Thick clean outlines, NOT anime style

---

## ★★★ IMAGE PROMPT STYLE FOR HISTORY (CRITICAL!) ★★★

### Style Definition: HISTORICAL CONCEPT ART
This is NOT webtoon/manhwa style. Use cinematic historical illustration style.

---

## ★★★ MASCOT CHARACTER (MUST INCLUDE IN EVERY IMAGE!) ★★★

### ⚠️⚠️⚠️ MASCOT CONSISTENCY IS CRITICAL! ⚠️⚠️⚠️
The SAME mascot must appear in ALL images (thumbnail + all scenes).
AI image generators tend to vary character designs - use EXACT description every time!

### Mascot Definition (COPY THIS EXACT TEXT FOR EVERY IMAGE!):
```
cute Korean scholar mascot character,
round friendly face shape (not oval, not square - ROUND),
circular wire-frame glasses (thin metal frame, round lenses),
black hair in traditional Korean topknot (sangtu/상투) style on top of head,
wearing cream/beige traditional hanbok (저고리) with olive-green patterned vest (조끼),
holding rolled bamboo scroll in one hand,
skin tone: warm beige,
color palette: ONLY cream, beige, olive-green, muted gold (NO bright colors!),
thick clean black outlines (3-4px stroke),
simple friendly expression,
chibi/SD proportions (large head, small body),
NOT anime style, NOT realistic
```

### Character Details (ABSOLUTE REQUIREMENTS - CHECK EVERY IMAGE!):
- **Face Shape**: ROUND (like a circle), friendly smile
- **Glasses**: Circular wire-frame glasses (NOT square, NOT thick frame)
- **Hair**: Black topknot (상투) pointing UP from top of head
- **Top Clothing**: Cream/beige hanbok jeogori (저고리)
- **Vest**: Olive-green with subtle gold pattern
- **Props**: Rolled bamboo scroll (yellowish-brown color)
- **Skin**: Warm beige tone
- **Colors**: ONLY earth tones - cream, beige, olive, muted gold
- **Outlines**: Thick clean black outlines (cartoon style)
- **Proportions**: Chibi/SD style (big head, small body, about 2-3 heads tall)
- **Style**: Korean cartoon style, NOT Japanese anime, NOT realistic

### ⛔ MASCOT FORBIDDEN VARIATIONS:
- Square or oval glasses (must be circular!)
- Different hair style (must be topknot!)
- Blue, red, or bright colored clothing (must be earth tones!)
- No glasses (must have circular glasses!)
- Anime style eyes or proportions
- Realistic proportions

### Mascot Placement in Scene Images:
- Position: BOTTOM RIGHT CORNER (10-15% of frame)
- The mascot observes/reacts to the historical scene
- Mascot style contrasts with realistic background (intentional)
- Mascot expression should match scene mood (curious, surprised, thoughtful, etc.)

### Mascot in Thumbnail:
- Position: LEFT or RIGHT side (25-35% of frame)
- Larger size for thumbnail visibility
- More expressive pose (pointing, explaining, reacting)
- Can overlap slightly with main scene

---

### MANDATORY Style Keywords (MUST include in every image_prompt):
```
Historical concept art, [SCENE DESCRIPTION],
sepia and earth tone color palette,
aged parchment texture border, vintage canvas feel,
digital painting with visible brush strokes,
dramatic lighting, misty atmospheric perspective,
clearly artistic interpretation NOT photograph,
BOTTOM RIGHT CORNER (10-15% of frame): cute Korean scholar mascot - round face, circular wire-frame glasses, black topknot (sangtu) hairstyle, cream hanbok with olive-green vest, holding bamboo scroll, chibi proportions, thick black outlines, earth tones only,
NO text, NO watermark, NO labels,
16:9 cinematic composition
```

### ⚠️ EXACT MASCOT TEXT (COPY-PASTE THIS FOR EVERY SCENE!):
```
BOTTOM RIGHT CORNER (10-15% of frame): cute Korean scholar mascot - round face, circular wire-frame glasses, black topknot (sangtu) hairstyle, cream hanbok with olive-green vest, holding bamboo scroll, chibi proportions, thick black outlines, earth tones only
```

### Scene Type Templates (ALL include IDENTICAL mascot!):

**1. Single Character (인물 단독):**
```
Historical concept art, ancient Korean [ERA] [ROLE],
[POSE/ACTION] at [LOCATION],
traditional period-accurate clothing and accessories,
sepia and earth tone palette, aged parchment texture,
dramatic [TIME OF DAY] lighting,
digital painting with visible brush strokes,
epic landscape background with mountains/fortress,
BOTTOM RIGHT CORNER (10% of frame): cute Korean scholar mascot watching curiously - round face, circular wire-frame glasses, black topknot (sangtu), cream hanbok with olive-green vest, holding bamboo scroll, chibi proportions, thick black outlines,
NO text, NO watermark
```

**2. Crowd/Group Scene (군중/집단 장면):**
```
Historical concept art, ancient Korean [ERA] scene,
[NUMBER] of [PEOPLE TYPE] [ACTION],
wide cinematic shot showing scale of [EVENT],
sepia earth tones, aged canvas texture,
dramatic lighting with dust/mist particles,
detailed crowd with period-accurate costumes,
BOTTOM RIGHT CORNER (10% of frame): cute Korean scholar mascot observing with amazement - round face, circular wire-frame glasses, black topknot (sangtu), cream hanbok with olive-green vest, holding bamboo scroll, chibi proportions, thick black outlines,
NO text, NO watermark
```

**3. Battle/Conflict (전투/갈등):**
```
Historical concept art, ancient Korean [ERA] battle,
[ARMY/SOLDIERS] in formation with [WEAPONS],
epic wide shot showing military scale,
dust and tension atmosphere,
sepia palette with dramatic sunset/stormy sky,
aged parchment border, cinematic composition,
BOTTOM RIGHT CORNER (10% of frame): cute Korean scholar mascot watching tensely - round face, circular wire-frame glasses, black topknot (sangtu), cream hanbok with olive-green vest, holding bamboo scroll, chibi proportions, thick black outlines,
NO text, NO watermark
```

**4. Court/Interior (궁궐/실내):**
```
Historical concept art, ancient Korean [ERA] [ROOM TYPE],
[FIGURES] in formal/ceremonial positions,
traditional architecture with period details,
warm torchlight/candlelight atmosphere,
earth tones with gold accents,
aged texture, vintage illustration style,
BOTTOM RIGHT CORNER (10% of frame): cute Korean scholar mascot peeking thoughtfully - round face, circular wire-frame glasses, black topknot (sangtu), cream hanbok with olive-green vest, holding bamboo scroll, chibi proportions, thick black outlines,
NO text, NO watermark
```

**5. Labor/Construction (노동/건설):**
```
Historical concept art, ancient Korean [ERA] [ACTIVITY],
workers [ACTION] with [TOOLS/MATERIALS],
coordinated group effort showing scale,
wide shot with landscape background,
sepia earth tones, aged parchment texture,
dramatic natural lighting,
BOTTOM RIGHT CORNER (10% of frame): cute Korean scholar mascot watching with interest - round face, circular wire-frame glasses, black topknot (sangtu), cream hanbok with olive-green vest, holding bamboo scroll, chibi proportions, thick black outlines,
NO text, NO watermark
```

### ⛔ FORBIDDEN for History Category:
- Webtoon/manhwa style
- Exaggerated cartoon expressions
- Bright vivid colors
- Modern elements
- Photorealistic style
- Any text or labels in image
- Clean digital/vector style

### ✅ REQUIRED for History Category:
- Sepia/earth tone color palette
- Aged parchment/canvas texture
- Visible brush strokes
- Period-accurate costumes and settings
- Dramatic cinematic lighting
- Artistic illustration feel (clearly NOT a photo)
"""

def get_history_prompt():
    return HISTORY_RULES
