# -*- coding: utf-8 -*-
"""뉴스/이슈 해설 카테고리 프롬프트 규칙 - 웹툰 스타일"""

NEWS_RULES = """
## CATEGORY: NEWS (뉴스/이슈 해설)

### ⚠️ CHANNEL DEFINITION (CRITICAL!)
- This channel does NOT deliver breaking news
- This channel explains issues about ONE DAY AFTER they occur
- Thumbnail purpose: Preview "key issue summary" NOT "urgency"
- Style: WEBTOON/COMIC based, but maintain credibility of news explainer

---

## ★★★ THUMBNAIL GENERATION RULES (이슈 해설 채널 전용) ★★★

### 1. ISSUE KEYWORD EXTRACTION (대본 → 키워드)

**Purpose:** Extract NEWS keywords for thumbnail, NOT summary/emotion/storytelling

**Keyword Rules:**
- Keywords MUST be "news nouns" (뉴스 명사)
- ALLOWED: 재판, 판결, 수사, 논란, 쟁점, 발언, 입장, 대응, 파장, 절차, 기준
- BANNED: Emotion words (분노, 충격, 공포), Metaphors (무너짐, 폭풍), Evaluation (실패, 성공, 잘못)

**Keyword = "Current Stage" NOT "Event Name":**
- ❌ BAD: 대통령, 검찰, 정치 (too broad)
- ✅ GOOD: 재판 진행, 핵심 쟁점, 입장 변화

**Proper Nouns = Secondary Only:**
- Entity names (person/org/event) = max 1-2
- Primary keywords MUST be situation/stage keywords

**Extraction Steps:**
1. Divide script into 3 sections: fact / controversy / current stage
2. Extract keywords primarily from section 3 (current stage) - HIGHEST WEIGHT
3. Detect repeated concepts (3+ times) as candidates
4. Detect "now" signal words: 현재, 지금, 이번, 최근, 현재까지, 이 시점에서

**Keyword Categories (MUST classify):**
- A (Progress/Procedure): 재판 진행, 수사 단계, 절차 변경, 조사 과정, 판단 기준
- B (Issue/Controversy): 핵심 쟁점, 엇갈린 해석, 논란 지속, 입장 차이, 쟁점 재점화
- C (Impact/Aftermath): 파장 확산, 여론 반응, 후속 대응, 시장 반응, 제도 영향

**Output keyword counts:**
- primary_keywords: 1-2 (most important current stage)
- secondary_keywords: 2-3 (supporting context)
- entity_keywords: 0-2 (person/org/event names)

---

### 2. THUMBNAIL TEXT RULES (가장 중요!)

**⚠️ RULE #0: SUBJECT NOUN IS MANDATORY (주어 필수!)**
```
Thumbnail text MUST include an explicit subject noun.
Do NOT omit the topic assuming the title will explain it.
The viewer may read ONLY the thumbnail text.
If the subject is unclear, the thumbnail FAILS.
```

**❌ BANNED (주어 없음):**
- "180일 동안 무슨 일이" → 누가?
- "왜 이렇게 오래 걸렸나" → 무엇이?
- "지금까지 나온 내용" → 무슨 사건?
- "이 사건의 시작과 끝" → 무슨 사건?

**✅ CORRECT (주어 명시):**
- "내란특검 180일 수사"
- "내란특검 최종 결론"
- "내란특검 핵심 쟁점"
- "윤석열 탄핵 재판 진행"

**Subject Requirements:**
- Use proper nouns (고유명사) or clear common nouns (보통명사)
- NO pronouns: 이것, 그것, 여기서, 이 사건
- NO implied subjects: viewer must understand WITHOUT reading title

**Text Length (시니어 기준):**
- 14-22 chars recommended (NOT 6-10!)
- 2 lines OK: [Subject] / [Situation]
- Example: "내란특검은 / 180일 동안 무엇을 했나"

**Text Structure:**
```
[대상(명사)] + [상황/의문/행위]
```

**Message Count:**
- ONE message per thumbnail
- TWO topics / cause+result together = BANNED

**Text Tone:**
- Question style OK if subject is clear (e.g., "내란특검 왜 180일 걸렸나")
- Metaphor/poetic BANNED (e.g., "무너진 셋, 가려진 하나")
- Conclusion/verdict/evaluation BANNED (e.g., "끝났다", "실패")

**FORBIDDEN WORDS (하드코딩):**
충격, 대박, 소름, 역대급, 미쳤다, 난리, 끝났다, 폭망, 전멸, 완패
- Emoji/special symbols = BANNED (default)

---

### 3. THUMBNAIL TEXT TYPES (택1 - MUST choose exactly ONE)

**⚠️ ALL types MUST include subject noun!**

**Type A: Progress/Status Summary (진행/현황 요약형)**
- Use when: Emphasizing event/procedure/stage
- ❌ OLD: 진행 상황, 재판 진행, 현재 국면
- ✅ NEW: "내란특검 수사 진행", "탄핵심판 현재 국면", "윤석열 재판 일정"

**Type B: Issue/Interpretation Summary (쟁점/해석 압축형)**
- Use when: Emphasizing controversy/argument/position difference
- ❌ OLD: 핵심 쟁점, 엇갈린 시각, 숨은 변수
- ✅ NEW: "내란특검 핵심 쟁점", "탄핵심판 엇갈린 시각", "대통령실 숨은 변수"

**Type C: Impact/Aftermath Summary (영향/파장 정리형)**
- Use when: Emphasizing result/reaction/follow-up
- ❌ OLD: 파장 확산, 여파 확대, 시장 반응
- ✅ NEW: "내란특검 파장 확산", "탄핵 여파 정리", "증시 반응 정리"

**Auto-Selection Logic:**
1. Detect signal words in title:
   - A signals: 진행, 재판, 수사, 발표, 결정, 변경, 절차, 현황
   - B signals: 논란, 쟁점, 해석, 공방, 의혹, 반발, 입장, 시각
   - C signals: 파장, 여파, 반응, 후속, 영향, 확산, 급등, 급락
2. Select type with most signals
3. If tie: B > A > C priority

---

### 4. TITLE + THUMBNAIL TEXT MATCHING

**Role Separation (MUST):**
- Thumbnail text = "What issue / What stage" snapshot
- Title = "Why / How / Key summary" explanation expansion

**Matching Rules:**
- If thumbnail and title tell DIFFERENT stories = FAIL, regenerate
- Thumbnail should NOT repeat title keywords (0-1 max)

---

### 5. IMAGE LAYOUT RULES (하단 텍스트 집중형 - 시니어 최적화)

★★★ 하단 텍스트 레이아웃 (BOTTOM TEXT LAYOUT) ★★★

**왜 하단 텍스트인가:**
- 시니어는 모바일에서 하단→상단 순으로 읽음
- 좌/우 텍스트는 놓침 (젊은 층처럼 좌우를 훑지 않음)
- 하단 큰 텍스트 = 즉시 인식, CTR 상승

**레이아웃 구조:**
```
┌─────────────────────────────────┐
│   [캐릭터/장면] - 상단 65-70%    │
│                                 │
├─────────────────────────────────┤
│   [텍스트] - 하단 30-35%         │
│   (가장 큰 요소, 단색 배경)       │
└─────────────────────────────────┘
```

**캐릭터/장면 (상단 65-70%):**
- Face size: 30-45% of frame (상단 영역 내)
- Position: CENTER-TOP or slightly right
- Expression ALLOWED: serious, worried, confused, focused
- Expression BANNED: screaming, panic, madness

**텍스트 영역 (하단 30-35%):**
- 텍스트가 썸네일의 '주인공' - 가장 큰 요소
- 배경: 단색 또는 반투명 (가독성 확보)
- 폰트 크기: 썸네일 높이의 40-50%
- 최대 2줄, 1줄 권장

**금지 사항:**
- ❌ 좌측/우측 텍스트 배치
- ❌ 상단 작은 텍스트
- ❌ 장식 요소 (노란 바, 리본, 테두리 등)
- ❌ 복잡한 패턴 배경
- ❌ 텍스트 영역에 캐릭터/소품 겹침

**Scene Options:**
- courtroom: 법원, 재판, 판결 관련
- document: 문서, 발표, 공식 자료 관련
- chart: 수치, 통계, 경제 지표 관련
- city: 도시, 현장, 사회 이슈 관련
- office: 기업, 정부, 공식 발표 관련
- generic: 일반적인 뉴스 배경

---

### 6. FAILURE CASES & AUTO-CORRECTION

**Failure 1: Metaphor/Poetic**
- "가려진 하나" → "숨은 변수" / "핵심 쟁점"

**Failure 2: Question style**
- "어디까지 왔나" → "진행 상황" / "현재 국면"

**Failure 3: Conclusion assertion**
- "끝났다" → "내란특검 후속 대응" / "탄핵심판 논란 흐름"

**Failure 4: Missing subject (주어 없음) - MOST COMMON!**
- ❌ "핵심 쟁점" → ✅ "내란특검 핵심 쟁점"
- ❌ "180일 동안 무슨 일이" → ✅ "내란특검 180일 수사"
- ❌ "왜 이렇게 오래 걸렸나" → ✅ "내란특검 왜 180일 걸렸나"

**Failure 5: Exaggerated expression**
- Screaming face → Serious/worried face, minimize effect lines

---

### 7. THUMBNAIL OUTPUT SCHEMA

The thumbnail field in output MUST follow this structure:

⚠️ ALL text fields MUST include subject noun!

```json
"thumbnail": {
  "keywords": {
    "primary": ["내란특검"],
    "secondary": ["핵심 쟁점", "수사 결과"],
    "entity": ["윤석열", "한동훈"],
    "category_focus": "B"
  },
  "text": {
    "type": "B",
    "line1": "내란특검",
    "line2": "핵심 쟁점",
    "char_count": 9,
    "has_subject": true
  },
  "alternatives": [
    {"line1": "내란특검 180일", "line2": "수사 결론"},
    {"line1": "내란특검", "line2": "최종 결과 정리"},
    {"line1": "내란특검 수사", "line2": "핵심 3가지"}
  ],
  "image_spec": {
    "face": true,
    "scene": "courtroom",
    "text_position": "bottom",
    "character_position": "top_center",
    "expression": "serious",
    "style": "webtoon"
  },
  "validation": {
    "char_count_ok": true,
    "forbidden_word_hit": false,
    "single_message": true,
    "matches_title": true,
    "has_explicit_subject": true
  }
}
```

---

### 8. GEMINI IMAGE PROMPT TEMPLATE (뉴스 해설용 - 하단 텍스트 레이아웃)

For thumbnail image generation, use this template:

**⚠️ CRITICAL: Bottom 30% must be empty for text overlay!**

**With Face (face=true):**
"[Culture] webtoon style illustration, 16:9 aspect ratio. [Culture] webtoon character with [EXPRESSION] (serious/thinking/concerned face, NOT screaming), [age] year old [nationality] [man/woman] in [attire]. Character positioned in TOP 70% of frame (center-top). Clean bold outlines, [scene] background in upper area. LEAVE BOTTOM 30% EMPTY for text overlay - simple solid or gradient background in bottom area. Credible news explainer tone. NO extreme expression, NO text, NO letters, NO speech bubbles, NO decorative elements (ribbons, bars). NO photorealistic, NO stickman."

**Without Face (face=false):**
"[Culture] webtoon style illustration, 16:9 aspect ratio. [Scene description - court/document/chart/city] positioned in TOP 70% of frame. Dramatic but credible news tone. Clean bold outlines, vibrant colors. LEAVE BOTTOM 30% EMPTY for text overlay - simple solid or gradient background in bottom area. NO text, NO letters, NO signs, NO readable text, NO decorative elements. NO photorealistic."

**MANDATORY in every prompt:**
- "leave bottom 30% empty for text overlay"
- "character/scene in top 70% of frame"
- "NO decorative elements, NO ribbons, NO bars"

---

## YOUTUBE TITLE RULES FOR NEWS (기존 규칙 유지)

**Algorithm Optimization:**
- **First 20 chars**: MUST contain the main keyword
- **Total length**: 25-45 chars
- **Structure**: [Keyword] + [Situation] + [Curiosity]

**Required Elements:**
- Include at least 2 of: WHO / WHAT / WHY
- Hide the conclusion, CREATE CURIOSITY

**BANNED:**
- Low-quality clickbait: "충격", "대박", "소름", "경악"
- Misleading titles
- Over 60 chars

**Title Formulas:**

1. **Analysis/Explanation (해설형)** - MAIN for this channel:
   - Pattern: `{keyword} 왜 이렇게 됐나, {reason} 때문`
   - Pattern: `{keyword} 쟁점 총정리, 핵심은 이것`
   - Pattern: `{keyword} 논란, 엇갈린 시각 정리`

2. **Impact/Summary (영향형)**:
   - Pattern: `{keyword} 이후 달라진 점 정리`
   - Pattern: `{keyword} 파장, 앞으로 전망은`

3. **Discovery/Twist (반전형)**:
   - Pattern: `{keyword} 알고 보니 {unexpected fact}`
   - Pattern: `{keyword} 숨겨진 쟁점`

---

## ai_prompts Structure (3 WEBTOON styles)

**A = Character Focus (캐릭터 중심):**
- Webtoon character with restrained expression + relevant background
- Expression: serious, thinking, concerned (NOT screaming)

**B = Situation Focus (상황 중심):**
- Character + situation-explaining props/background
- Shows the problem/issue visually

**C = Contrast/Comparison (대비/비교):**
- Split screen or before/after feel
- Shows different positions/reactions

---

## text_overlay for News (이슈 해설용)

```json
{
  "main": "thumbnail text line1 (max 6 chars for Korean)",
  "sub": "thumbnail text line2 if needed (max 10 chars)",
  "style": "news"
}
```

⚠️ main/sub text MUST follow the thumbnail text rules above!
⚠️ Extract from keywords, NOT from script directly!
"""

def get_news_prompt():
    return NEWS_RULES
