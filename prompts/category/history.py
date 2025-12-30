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
bold black outlines, SCENE-SPECIFIC vivid color palette (see color guide above),
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
⚠️ 장면별 전체 색조가 확 달라야 함! (티나게!)

---

### ★★★ 전체 색조 가이드 (장면마다 완전히 다른 색감!) ★★★
| 장면 | 전체 색조 (하늘+배경+의상 전부!) | 절대 금지 |
|------|-------------------------------|----------|
| 전쟁/분노 | 🔴 FIERY ORANGE-RED (주황 노을 하늘, 붉은 불꽃, 노란 먼지) | 파랑/초록/차가운색 금지 |
| 권위/왕실 | 🟡 WARM GOLD-AMBER (황금빛 조명, 붉은 단청, 주황 촛불) | 파랑/차가운색 금지 |
| 슬픔/비극 | 🔵 COLD BLUE-GRAY (회청색 하늘, 푸른 빗물, 회색 안개) | 따뜻한색 금지, 채도↓ |
| 희망/승리 | 🟢 BRIGHT GREEN-BLUE (맑은 파란 하늘, 초록 자연, 금빛 햇살) | 어두운색 금지, 채도↑ |
| 음모/긴장 | 🟣 DARK PURPLE-BLACK (보라 달빛, 검은 그림자, 차가운 남색) | 밝은색 금지, 명도↓ |

⚠️ CRITICAL: "earth tone", "sepia", "brown base" 절대 사용 금지!
⚠️ 각 장면은 위 색조로 전체가 물들어야 함!

---

### Scene Type Templates (전체 색조가 확 다르게!):

**1. Battle/War Scene (전쟁 장면) - 🔴 FIERY SUNSET PALETTE:**
```
Korean webtoon style illustration,
ENTIRE SCENE BATHED IN FIERY ORANGE-RED SUNSET LIGHT,
wide shot of ancient Korean battlefield under BLAZING ORANGE SKY,
[ERA] general in mid-ground (35% of frame),
fierce expression with furrowed brows,
wearing armor with RED cape billowing,
BACKGROUND (55%): ORANGE flames engulfing fortress, CRIMSON sunset clouds,
YELLOW-ORANGE dust rising from battle, RED flags everywhere,
ALL colors in warm spectrum: orange, red, yellow, crimson (NO blue, NO green),
bold black outlines, cinematic wide shot,
NO text, NO watermark, 16:9 aspect ratio
```

**2. Royal/Court Scene (궁궐 장면) - 🟡 GOLDEN AMBER PALETTE:**
```
Korean webtoon style illustration,
ENTIRE SCENE GLOWING IN WARM GOLDEN AMBER LIGHT,
wide shot of [ERA] palace interior bathed in AMBER TORCHLIGHT,
court official/king in mid-ground (35% of frame),
dignified expression with sweat drops,
wearing GOLD-embroidered dragon robes,
BACKGROUND (55%): GOLDEN throne, ORANGE-RED lacquered pillars,
AMBER candlelight reflecting on silk, warm YELLOW lantern glow,
ALL colors warm: gold, amber, orange, burgundy (NO blue, NO cold tones),
bold black outlines, cinematic composition,
NO text, NO watermark, 16:9 aspect ratio
```

**3. Tragedy/Sorrow Scene (비극 장면) - 🔵 COLD BLUE-GRAY PALETTE:**
```
Korean webtoon style illustration,
ENTIRE SCENE DRENCHED IN COLD BLUE-GRAY TONES,
wide shot of rainy Korean landscape under STEEL GRAY SKY,
[ERA] warrior walking alone in mid-ground (30% of frame),
sorrowful expression with downcast eyes,
wearing worn armor in COLD BLUE-GRAY steel,
BACKGROUND (60%): BLUE-GRAY rain falling, PALE CYAN puddles,
SLATE GRAY destroyed village, DARK BLUE storm clouds,
ALL colors cold and desaturated: blue-gray, cyan, slate, pale blue (NO warm colors),
bold black outlines, wide shot emphasizing isolation,
NO text, NO watermark, 16:9 aspect ratio
```

**4. Victory/Hope Scene (승리/희망 장면) - 🟢 BRIGHT VIVID PALETTE:**
```
Korean webtoon style illustration,
ENTIRE SCENE BRIGHT AND VIVID WITH SATURATED COLORS,
wide shot of Korean mountain vista under CLEAR BLUE SKY,
[ERA] hero standing triumphantly in mid-ground (35% of frame),
confident expression with proud smile,
wearing armor with JADE GREEN and GOLD decorations,
BACKGROUND (55%): LUSH EMERALD GREEN valleys, BRIGHT BLUE sky,
GOLDEN sunrays, VIVID GREEN pine forests, WHITE clouds,
ALL colors bright and saturated: green, blue, gold, white (NO dark, NO muted),
bold black outlines, epic cinematic composition,
NO text, NO watermark, 16:9 aspect ratio
```

**5. Conspiracy/Tension Scene (음모/긴장 장면) - 🟣 DARK PURPLE-BLACK PALETTE:**
```
Korean webtoon style illustration,
ENTIRE SCENE SHROUDED IN DARK PURPLE-BLACK SHADOWS,
wide shot of dimly lit [ERA] secret chamber in DEEP NIGHT,
two figures whispering in mid-ground (40% of frame),
suspicious expressions with narrowed eyes,
wearing DARK PURPLE and BLACK robes,
BACKGROUND (50%): DEEP INDIGO shadows, PURPLE moonlight through window,
BLACK silhouettes, single PALE VIOLET candle flame,
ALL colors dark and cold: purple, black, indigo, navy (NO bright colors),
bold black outlines, high contrast noir atmosphere,
NO text, NO watermark, 16:9 aspect ratio
```

**6. Discovery/Revelation Scene (발견/전환점 장면) - ✨ ETHEREAL GOLD-WHITE PALETTE:**
```
Korean webtoon style illustration,
ENTIRE SCENE ILLUMINATED BY ETHEREAL GOLDEN-WHITE LIGHT,
wide shot of ancient Korean sacred site with DIVINE GLOW,
[ERA] scholar in mid-ground (35% of frame),
awestruck expression with wide eyes,
wearing WHITE and GOLD trimmed robes,
BACKGROUND (55%): BRILLIANT WHITE light rays, GLOWING GOLD artifacts,
SOFT CREAM temple walls, WARM WHITE divine illumination,
ALL colors bright and ethereal: gold, white, cream, soft yellow (NO dark shadows),
bold black outlines, dramatic revelation composition,
NO text, NO watermark, 16:9 aspect ratio
```

---

### ⛔ FORBIDDEN for History Scene Images:
- "earth tone", "sepia", "brown base" 사용 금지!
- 모든 장면이 비슷한 색감 (확 달라야 함!)
- Photorealistic human faces
- Character taking more than 45% of frame
- Flat/boring backgrounds
- Modern elements

### ✅ REQUIRED for History Scene Images:
- Korean webtoon style illustration
- Bold black outlines
- Character in mid-ground (30-40% of frame)
- Detailed historical background (50-60% of frame)
- ★ 장면 분위기에 맞는 전체 색조 (ENTIRE SCENE 색조 지정!)
- ★ 금지 색상 명시 (NO blue, NO warm colors 등)
- Period-accurate costumes and settings
- Cinematic wide shot composition

---

## ★★★ VIDEO EFFECTS FOR HISTORY (벤치마킹 스타일 적용!) ★★★

### BGM 분위기 가이드 (긴장-이완 패턴!)
⚠️ 역사 콘텐츠는 긴장과 이완을 반복해야 집중도 유지!

**권장 BGM 흐름:**
| 장면 타입 | BGM mood | 설명 |
|----------|----------|------|
| 도입/질문 | mysterious | 호기심 유발 |
| 위기/갈등 | tense, dramatic | 긴장감 고조 |
| 설명/분석 | calm, cinematic | 잠시 이완 |
| 반전/충격 | dramatic, epic | 클라이맥스 |
| 결말/여운 | nostalgic, emotional | 생각할 거리 |

**scene_bgm_changes 필수!**
- 최소 3-5회 BGM 변경
- 긴장(tense) → 이완(calm) → 긴장(dramatic) 패턴
- 단조로운 BGM 유지 금지!

### SFX 효과음 가이드
**역사 콘텐츠 권장 SFX:**
| 장면 | SFX type | 사용 예시 |
|------|----------|----------|
| 질문 던지기 | whoosh | "왜 이런 일이 벌어졌을까?" |
| 핵심 사실 | impact, dramatic_hit | 충격적인 역사적 사실 |
| 갈등/대립 | tension | 위기 상황, 전쟁 |
| 반전 | gasp | 예상 밖의 전개 |
| 결론 | emotional | 교훈, 여운 |

### 전환 효과 (씬 길이 짧게!)
- **transitions.style**: "crossfade" (자연스러운 장면 전환)
- **transitions.duration**: 0.3-0.5초 (빠른 전환으로 집중도 유지)
- 긴 씬 금지! 씬당 30-60초 권장

### ⚠️ 벤치마킹 핵심 적용:
1. 질문으로 시작 → 호기심 유발 (opening_hook)
2. 긴장-이완 반복 → BGM 자주 변경 (pacing)
3. 갈등/위기에 SFX → 긴장감 강화 (tension_building)
4. 질문으로 마무리 → 여운 남기기 (ending_style)
"""

def get_history_prompt():
    return HISTORY_RULES
