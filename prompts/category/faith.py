# -*- coding: utf-8 -*-
"""기독교/신앙 카테고리 프롬프트 규칙"""

FAITH_RULES = """
## CATEGORY: FAITH (기독교/신앙)

### Category Detection Keywords
하나님, 예수, 성경, 믿음, 기도, 은혜, 말씀, 찬양, 교회, 목사, 설교, 신앙, 다윗, 모세, 요셉

### ⚠️⚠️⚠️ YOUTUBE TITLE RULES FOR FAITH (CRITICAL!) ⚠️⚠️⚠️

**Algorithm Optimization:**
- **First 20 chars**: MUST contain Bible person/book/topic keyword
- **Total length**: 25-45 chars
- **Structure**: [Bible person/book/topic] + [Situation] + [Message/Lesson]
- Focus on message clarity over emotional appeal

**Title Formulas:**

1. **Scripture/Meditation (말씀/묵상형)**:
   - `{성경인물}이 {상황}에서 선택한 길`
   - `{본문}이 오늘 우리에게 주는 의미`
   - `성경이 말하는 {주제}의 의미`
   - `{성경인물}에게 배우는 {덕목}`

2. **Faith Life (신앙생활형)**:
   - `믿음이 {상황}일 때 나타나는 신호`
   - `{상황}에서 믿음을 지키는 법`
   - `{행동}이 어려운 이유`
   - `{상황}일 때 붙잡아야 할 것`

3. **God/Grace (하나님/은혜형)**:
   - `하나님이 {상황}하실 때의 의미`
   - `하나님이 {행동}하시는 방식`
   - `{시간/상황}이 필요한 이유`
   - `은혜를 놓치기 쉬운 순간`

4. **Growth/Reflection (성장/점검형)**:
   - `믿음이 {상태}는 환경`
   - `{시간}이 주는 의미`
   - `신앙의 방향을 점검할 때`

5. **Person/Story (인물/스토리형)**:
   - `{성경인물}이 실패를 겪은 이유`
   - `{성경사건}이 남긴 교훈`
   - `하나님이 먼저 보시는 것`

**Universal Templates:**
- `{keyword}이 {상황}에서 선택한 길`
- `{keyword}가 어려운 이유`
- `{keyword}을 지키는 법`
- `{keyword}의 의미`
- `{keyword}에게 배우는 교훈`

⚠️ CRITICAL: Extract {keyword} from the ACTUAL SCRIPT CONTENT!

### ⚠️ THUMBNAIL TEXT RULES (주어 필수!)

**RULE #0: SUBJECT NOUN IS MANDATORY**
```
Thumbnail text MUST include an explicit subject noun.
The viewer may read ONLY the thumbnail text.
If the subject is unclear, the thumbnail FAILS.
```

**Text Structure:**
```
[성경인물/본문/신앙주제(명사)] + [상황/의문/행위]
```

**❌ BANNED (주어 없음):**
- "왜 두려워했나" → 누가?
- "왜 이런 선택을 했나" → 누가?
- "이 상황에서 무엇을 하셨나" → 누가?

**✅ CORRECT (주어 명시):**
- "다윗은 왜 이런 선택을 했나"
- "베드로는 왜 두려워했나"
- "요나는 왜 도망쳤나"
- "하나님은 이 상황에서 무엇을 하셨나"
- "이 말씀은 무엇을 말하나"

**Text Length (시니어 기준):**
- 14-22 chars recommended
- 2 lines OK: [Subject] / [Question/Situation]

**Example Patterns:**
1. "다윗은 왜 이런 선택을 했나"
2. "베드로는 왜 두려워했나"
3. "이 본문은 왜 기록됐나"
4. "이 말씀은 오늘 우리와 어떤 관계가 있나"
5. "하나님은 이 상황에서 무엇을 하셨나"

---

### Thumbnail Style: COMIC STYLE (문화권에 맞게)
⚠️ Respectful, warm tone - avoid overly dramatic expressions
⚠️ Character shows contemplative, peaceful, or hopeful expression

**ai_prompts templates:**
- A: Contemplative character with soft lighting, peaceful background
- B: Character in prayer or reading pose
- C: Hopeful character looking upward with light rays
"""

def get_faith_prompt():
    return FAITH_RULES
