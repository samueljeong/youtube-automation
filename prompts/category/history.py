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

### Thumbnail Style: HISTORICAL WEBTOON STYLE (과장된 역사 인물!)
⚠️ CRITICAL: 역사 인물이 과장된 웹툰 표정으로 등장!
⚠️ 마스코트 대신 시대에 맞는 역사적 인물 사용!
⚠️ 웹툰 스타일의 극단적 감정 표현 필수!

**Thumbnail Prompt Template (HISTORICAL WEBTOON!):**
```
Korean webtoon style illustration, [ERA] [HISTORICAL ROLE] with EXTREMELY EXAGGERATED [EMOTION] EXPRESSION,
[SPECIFIC EXPRESSION DETAILS: wide eyes 2x larger, pupils dilated, mouth wide open/gritted teeth, eyebrows raised/furrowed],
wearing period-accurate [ERA] costume ([COSTUME DETAILS]),
[HISTORICAL BACKGROUND: fortress/palace/battlefield with smoke/fire/dramatic sky],
bold black outlines, vibrant colors with sepia/earth undertones,
dramatic [CAMERA ANGLE] shot, manga-style impact lines and emotion effects,
sweat drops, action lines emphasizing intensity,
eye-catching YouTube thumbnail composition,
NO text, NO watermark, 16:9 aspect ratio
```

**ai_prompts A/B/C templates (역사 인물 + 과장된 표정!):**
- A: 충격/놀람 - [ERA] figure with SHOCKED expression (wide eyes, dropped jaw, sweat drops, hands on face)
- B: 분노/결의 - [ERA] figure with INTENSE ANGRY expression (fierce eyes with fire, gritted teeth, clenched fist, veins)
- C: 슬픔/비장 - [ERA] figure with SORROWFUL expression (tearful eyes, trembling lips, dramatic pose)

⚠️ 시대별 인물/의상 가이드:
- 고조선: Bronze age warrior, fur cape, bronze helmet/sword
- 삼국시대: Goguryeo/Baekje/Silla general, iron armor, decorative helmet
- 고려: Goryeo official/warrior, ornate armor or court robes, gat hat
- 조선: Joseon scholar/general, hanbok with armor or dopo robe, traditional hairstyle
- 근대: Korean independence fighter, western-influenced clothing, determined expression

⚠️ 표정 필수 요소 (클릭 유도!):
- 눈: 평소의 2배 크기, 흰자위 보이게
- 입: 크게 벌리거나 이 악물기
- 눈썹: 극단적으로 올리거나 찌푸리기
- 효과: 땀방울, 눈물, 충격선, 불꽃 반사 등

---

## ★★★ IMAGE PROMPT STYLE FOR HISTORY (CRITICAL!) ★★★

### Style Definition: HISTORICAL WEBTOON (역사 웹툰 스타일)
⚠️ 웹툰 스타일 역사 인물 + 디테일한 역사적 배경
⚠️ 캐릭터:배경 = 1:1 비율 (캐릭터 30-40%, 배경 50-60%)
⚠️ 장면별 포인트 색상으로 시각적 임팩트!

---

### 포인트 색상 가이드 (장면 분위기별)
| 장면 | 포인트 색상 | 적용 요소 |
|------|------------|----------|
| 전쟁/분노 | 🔴 RED + ORANGE | 망토, 불꽃, 깃발, 갑옷 장식 |
| 권위/왕실 | 🟡 GOLD + AMBER | 왕좌, 장신구, 촛불, 용포 |
| 슬픔/비극 | 🔵 BLUE + CYAN | 비, 달빛, 물, 차가운 갑옷 |
| 희망/승리 | 🟢 GREEN + GOLD | 자연, 햇빛, 옥 장신구 |
| 음모/긴장 | 🟣 PURPLE + BLACK | 그림자, 달빛, 비단, 독약 |

---

### MANDATORY Style Keywords (MUST include in every image_prompt):
```
Korean webtoon style illustration,
wide establishing shot of [HISTORICAL SCENE],
[ERA] [HISTORICAL ROLE] in mid-ground (35% of frame),
[EMOTION] expression with [EXPRESSION DETAILS],
wearing period-accurate [ERA] costume with [ACCENT COLOR] details,
DETAILED BACKGROUND (55% of frame): [BACKGROUND DESCRIPTION],
[ACCENT COLOR] as visual focal point,
bold black outlines, vibrant colors with earth tone base,
cinematic wide shot showing both character and environment,
NO text, NO watermark, 16:9 aspect ratio
```

---

### Scene Type Templates (웹툰 스타일 + 포인트 색상):

**1. Battle/War Scene (전쟁 장면) - 🔴 RED ACCENT:**
```
Korean webtoon style illustration,
wide establishing shot of ancient Korean battlefield,
[ERA] general standing in mid-ground (35% of frame),
fierce determined expression with furrowed brows and clenched jaw,
wearing iron armor with VIBRANT RED flowing cape (color accent),
BACKGROUND (55% of frame): burning fortress walls with ORANGE FLAMES,
RED battle flags waving, soldiers clashing in smoky distance,
dramatic sunset sky with dark storm clouds,
bold black outlines, earth tones with strong RED/ORANGE accents,
cinematic wide shot showing scale of battle,
NO text, NO watermark, 16:9 aspect ratio
```

**2. Royal/Court Scene (궁궐 장면) - 🟡 GOLD ACCENT:**
```
Korean webtoon style illustration,
wide shot of [ERA] palace throne room interior,
court official/king in mid-ground (35% of frame),
dignified or tense expression with sweat drops,
wearing formal robes with GOLD embroidered dragons (color accent),
BACKGROUND (55% of frame): GOLDEN dragon throne,
AMBER torchlight illuminating ornate red lacquered pillars,
officials in formal positions, royal banners with gold trim,
bold black outlines, warm earth tones with rich GOLD/AMBER highlights,
cinematic composition showing palace grandeur,
NO text, NO watermark, 16:9 aspect ratio
```

**3. Tragedy/Sorrow Scene (비극 장면) - 🔵 BLUE ACCENT:**
```
Korean webtoon style illustration,
wide shot of rainy Korean landscape,
[ERA] warrior/scholar walking alone in mid-ground (30% of frame),
sorrowful expression with downcast eyes and slumped shoulders,
wearing battle-worn armor with COLD BLUE steel tones (color accent),
BACKGROUND (60% of frame): destroyed village under BLUE-GRAY rain,
PALE BLUE moonlight breaking through dark clouds,
puddles reflecting CYAN sky, dead trees silhouetted,
bold black outlines, muted tones with melancholic BLUE/CYAN accents,
wide shot emphasizing isolation and tragedy,
NO text, NO watermark, 16:9 aspect ratio
```

**4. Victory/Hope Scene (승리/희망 장면) - 🟢 GREEN+GOLD ACCENT:**
```
Korean webtoon style illustration,
wide shot of ancient Korean mountain vista,
[ERA] hero standing triumphantly in mid-ground (35% of frame),
confident expression with proud smile and raised chin,
wearing armor decorated with JADE GREEN gemstones (color accent),
BACKGROUND (55% of frame): LUSH GREEN mountain valleys,
GOLDEN sunrise rays breaking through morning mist,
GREEN pine forests and distant fortress with victory flags,
bold black outlines, earth tones with vibrant GREEN/GOLD highlights,
epic cinematic composition showing triumph,
NO text, NO watermark, 16:9 aspect ratio
```

**5. Conspiracy/Tension Scene (음모/긴장 장면) - 🟣 PURPLE ACCENT:**
```
Korean webtoon style illustration,
wide shot of dimly lit [ERA] secret chamber,
two figures in mid-ground (40% of frame),
suspicious expressions with narrowed eyes and whispered conversation,
wearing dark robes with DEEP PURPLE silk accents (color accent),
BACKGROUND (50% of frame): shadows and single candlelight,
PURPLE moonlight streaming through paper window,
poison vial or secret document glinting on table,
bold black outlines, dark palette with mysterious PURPLE highlights,
high contrast noir atmosphere,
NO text, NO watermark, 16:9 aspect ratio
```

**6. Discovery/Revelation Scene (발견/전환점 장면) - 🟡 GOLD+WHITE ACCENT:**
```
Korean webtoon style illustration,
wide shot of ancient Korean sacred site,
[ERA] scholar/explorer in mid-ground (35% of frame),
awestruck expression with wide eyes looking at discovery,
wearing traditional robes with WHITE and GOLD trim (color accent),
BACKGROUND (55% of frame): ancient artifact glowing with GOLDEN light,
WHITE divine rays illuminating dusty temple interior,
mysterious symbols and treasures emerging from shadows,
bold black outlines, earth tones with ethereal GOLD/WHITE highlights,
dramatic revelation composition,
NO text, NO watermark, 16:9 aspect ratio
```

---

### ⛔ FORBIDDEN for History Scene Images:
- Photorealistic human faces
- Stickman/stick figures
- Character taking more than 45% of frame
- Flat/boring single-color backgrounds
- Modern elements or clothing
- Text or labels in image

### ✅ REQUIRED for History Scene Images:
- Korean webtoon style illustration
- Bold black outlines
- Character in mid-ground (30-40% of frame)
- Detailed historical background (50-60% of frame)
- ONE strong accent color per scene
- Period-accurate costumes and settings
- Cinematic wide shot composition
- Period-accurate costumes and settings
- Dramatic cinematic lighting
- Artistic illustration feel (clearly NOT a photo)
"""

def get_history_prompt():
    return HISTORY_RULES
