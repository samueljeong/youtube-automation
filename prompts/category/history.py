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

### Thumbnail Style: HISTORICAL CONCEPT ART
⚠️ Historical setting and costume matching the era
⚠️ Dramatic lighting, serious or contemplative expression

**ai_prompts templates:**
- A: Historical figure with dramatic expression, period costume
- B: Battle or court scene with tension
- C: Split composition showing before/after or contrast

---

## ★★★ IMAGE PROMPT STYLE FOR HISTORY (CRITICAL!) ★★★

### Style Definition: HISTORICAL CONCEPT ART
This is NOT webtoon/manhwa style. Use cinematic historical illustration style.

### MANDATORY Style Keywords (MUST include in every image_prompt):
```
Historical concept art, [SCENE DESCRIPTION],
sepia and earth tone color palette,
aged parchment texture border, vintage canvas feel,
digital painting with visible brush strokes,
dramatic lighting, misty atmospheric perspective,
clearly artistic interpretation NOT photograph,
NO text, NO watermark, NO labels,
16:9 cinematic composition
```

### Scene Type Templates:

**1. Single Character (인물 단독):**
```
Historical concept art, ancient Korean [ERA] [ROLE],
[POSE/ACTION] at [LOCATION],
traditional period-accurate clothing and accessories,
sepia and earth tone palette, aged parchment texture,
dramatic [TIME OF DAY] lighting,
digital painting with visible brush strokes,
epic landscape background with mountains/fortress,
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
