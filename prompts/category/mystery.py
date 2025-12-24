# -*- coding: utf-8 -*-
"""미스터리/미제사건 카테고리 프롬프트 규칙"""

MYSTERY_RULES = """
## CATEGORY: MYSTERY (미스터리/미제사건)

### Category Detection Keywords
미스터리, 미제, 실종, 괴담, UFO, 외계인, 초자연, 유령, 귀신, 저주, 암살, 음모론,
버뮤다, 지하세계, 비밀, 미해결, 사라진, 발견된, 숨겨진, 의문의, 정체불명

### ⚠️⚠️⚠️ YOUTUBE TITLE RULES FOR MYSTERY (CRITICAL!) ⚠️⚠️⚠️

**Algorithm Optimization:**
- **First 20 chars**: MUST contain mystery hook keyword
- **Total length**: 25-45 chars
- **Structure**: [Mystery Hook] + [Key Detail] + [Unresolved Question]
- Build suspense without revealing conclusion

**Title Formulas:**

1. **Unsolved Case (미제사건형)**:
   - `{사건}의 마지막 단서`
   - `아직도 풀리지 않은 {사건}`
   - `{시간} 뒤에 발견된 {증거}`
   - `{장소}에서 사라진 사람들`

2. **Conspiracy/Secret (음모/비밀형)**:
   - `{조직}이 숨기려 했던 기록`
   - `공개되지 않은 {사건}의 진실`
   - `{인물}이 남긴 마지막 메시지`
   - `{기관}이 삭제한 파일`

3. **Supernatural (초자연형)**:
   - `설명할 수 없는 {현상}`
   - `과학이 포기한 {사건}`
   - `{장소}에서 목격된 것`
   - `{시간} 동안 기록된 이상현상`

4. **Discovery/Revelation (발견/폭로형)**:
   - `{연도}년 만에 밝혀진 사실`
   - `{증거}가 가리키는 방향`
   - `{사건} 재수사 결과`
   - `새로 공개된 {자료}`

5. **Question/Suspense (의문/서스펜스형)**:
   - `왜 {인물}은 {행동}했을까`
   - `{사건}의 유일한 생존자`
   - `{시간} 전에 무슨 일이`
   - `마지막으로 목격된 순간`

**Universal Templates:**
- `{keyword}의 마지막 순간`
- `{keyword}에서 발견된 증거`
- `아무도 모르는 {keyword}의 진실`
- `{keyword}가 사라진 이유`
- `{keyword} 뒤에 숨겨진 이야기`

⚠️ CRITICAL: Extract {keyword} from the ACTUAL SCRIPT CONTENT!

---

## ★★★ IMAGE PROMPT STYLE FOR MYSTERY (CRITICAL!) ★★★

### Style Definition: DARK CINEMATIC THRILLER
Moody, atmospheric, film noir inspired.
High contrast with deep shadows and selective lighting.

---

### MANDATORY Style Keywords (MUST include in every image_prompt):
```
Dark cinematic thriller illustration, [SCENE DESCRIPTION],
film noir inspired lighting with deep shadows,
muted desaturated color palette (dark blues, grays, blacks),
high contrast dramatic lighting,
mysterious atmospheric fog or haze,
single spotlight or moonlight source,
suspenseful tense atmosphere,
clearly artistic illustration NOT photograph,
NO text, NO watermark, NO labels,
16:9 cinematic composition
```

### Scene Type Templates:

**1. Crime Scene (범죄 현장):**
```
Dark cinematic thriller illustration, abandoned crime scene,
yellow police tape, scattered evidence markers,
single flashlight beam cutting through darkness,
muted colors with yellow accent lighting,
film noir shadows, forensic atmosphere,
suspenseful tension, empty and haunting,
NO text, NO watermark
```

**2. Abandoned Location (버려진 장소):**
```
Dark cinematic thriller illustration, abandoned building interior,
broken windows with moonlight streaming through,
dust particles floating in light beams,
decayed furniture and debris,
deep shadows, cold blue-gray palette,
eerie silence atmosphere,
NO text, NO watermark
```

**3. Document/Evidence (문서/증거):**
```
Dark cinematic thriller illustration, old documents and photos,
scattered on desk under single lamp light,
aged paper texture, faded photographs,
warm spotlight on evidence, dark surroundings,
detective investigation mood,
noir office atmosphere,
NO text visible on documents, NO watermark
```

**4. Night Exterior (야외 야경):**
```
Dark cinematic thriller illustration, night street scene,
wet pavement reflecting street lights,
fog rolling through empty streets,
long shadows from single light source,
noir urban atmosphere,
mysterious figure silhouette optional,
NO text, NO watermark
```

**5. Surveillance/Watching (감시/관찰):**
```
Dark cinematic thriller illustration, surveillance setup,
multiple monitors glowing in dark room,
security footage aesthetic,
green-tinted night vision elements,
paranoid tense atmosphere,
watcher's perspective,
NO text on screens, NO watermark
```

**6. Portal/Supernatural (초자연/이상현상):**
```
Dark cinematic thriller illustration, supernatural phenomenon,
unexplainable light anomaly in darkness,
reality distortion effect,
cold blue otherworldly glow,
scientific equipment abandoned nearby,
fear and wonder atmosphere,
NO text, NO watermark
```

**7. Forest/Remote (숲/외딴 곳):**
```
Dark cinematic thriller illustration, dense forest at night,
twisted tree silhouettes,
single flashlight or moonbeam,
mist crawling along ground,
isolation and vulnerability,
something watching from shadows,
NO text, NO watermark
```

**8. Interview/Testimony (인터뷰/증언):**
```
Dark cinematic thriller illustration, interrogation room,
harsh overhead light casting sharp shadows,
silhouette figure at table,
sparse institutional setting,
psychological tension,
truth-seeking atmosphere,
NO text, NO watermark
```

---

## Thumbnail Style: DARK MYSTERY POSTER

### Thumbnail Prompt Template:
```
Dark mystery thriller thumbnail, [MAIN SCENE DESCRIPTION],
high contrast dramatic lighting,
deep shadows with selective spotlight,
muted desaturated colors (dark blue, gray, black),
film noir atmosphere,
suspenseful tension,
LEFT/RIGHT SIDE: large bold question mark or mystery symbol optional,
eye-catching YouTube thumbnail composition,
NO text, NO watermark, 16:9 aspect ratio
```

### Thumbnail Text Rules:
- Maximum 10 characters for Korean text
- 1-2 lines maximum
- Question or suspense tone preferred
- Example text overlays:
  - "진실은?" / "사라진 이유"
  - "미공개 증거" / "마지막 목격"
  - "숨겨진 기록" / "아무도 몰랐던"

---

### ⛔ FORBIDDEN for Mystery Category:
- Bright cheerful colors
- Cartoon/anime style
- Gore or graphic violence
- Cheap horror clichés (excessive blood, screaming faces)
- Photorealistic human faces
- Any text or labels in image
- Saturated vivid colors

### ✅ REQUIRED for Mystery Category:
- Dark moody atmosphere
- Film noir lighting (high contrast)
- Muted desaturated palette
- Fog, haze, or atmospheric effects
- Suspenseful tension (NOT cheap horror)
- Professional cinematic quality
- Mystery and intrigue (NOT gore)

---

## ai_prompts Structure (3 styles)

**A = Location/Atmosphere (장소/분위기):**
- Emphasizes mysterious location
- Dark atmospheric setting
- Viewer feels like they're entering the scene

**B = Evidence/Clue (증거/단서):**
- Focus on key evidence or document
- Spotlight on mysterious object
- Investigation mood

**C = Silhouette/Shadow (실루엣/그림자):**
- Human figure in shadow
- Identity concealed
- Suspense and uncertainty

---

## text_overlay for Mystery

```json
{
  "main": "mystery hook (max 6 chars Korean)",
  "sub": "supporting detail (max 8 chars)",
  "style": "mystery"
}
```

⚠️ Text should create suspense, NOT reveal conclusion!
⚠️ Prefer questions or incomplete statements!
"""

def get_mystery_prompt():
    return MYSTERY_RULES
