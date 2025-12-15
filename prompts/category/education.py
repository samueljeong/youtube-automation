# -*- coding: utf-8 -*-
"""지식/교육 카테고리 프롬프트 규칙"""

EDUCATION_RULES = """
## CATEGORY: EDUCATION (지식/교육)

### Category Detection Keywords
지식, 교육, 학습, 과학, 심리, 뇌과학, 철학, 경제원리, 역사적사실, 설명, 원리, 이유

### ⚠️⚠️⚠️ YOUTUBE TITLE RULES FOR EDUCATION (CRITICAL!) ⚠️⚠️⚠️

**Algorithm Optimization:**
- **First 20 chars**: MUST contain the main keyword
- **Total length**: 25-45 chars
- **Structure**: [Concept/Topic] + WHY/HOW + [Explanation keyword]
- Search question-style titles work best

**Title Formulas:**

1. **Reason/Cause (이유/원인형)**:
   - `{현상}이 생기는 진짜 이유`
   - `사람들이 {행동}하는 이유`
   - `{현상}이 나타나는 과정`

2. **Method/Principle (방법/원리형)**:
   - `{주제}를 이해하는 핵심 원리`
   - `{목표} 위한 효과적인 방법`
   - `{대상}을 움직이는 구조`

3. **Misconception/Truth (오해/진실형)**:
   - `잘못 알려진 {주제} 상식`
   - `{주제}에 대한 흔한 오해`
   - `알고 보면 다른 {주제}의 진실`

4. **Comparison/Analysis (비교/분석형)**:
   - `{A}와 {B}의 결정적 차이`
   - `{현상}을 만드는 패턴`
   - `{상황}에서 나타나는 신호`

5. **Question (질문형)**:
   - `{주제}는 언제 믿어도 될까`
   - `왜 {대상}은 {현상}일까`
   - `{주제}는 어떻게 결정될까`

**Universal Templates:**
- `{keyword}이 생기는 진짜 이유`
- `{keyword}를 이해하는 핵심 원리`
- `{keyword}에 대한 흔한 오해`
- `{keyword}의 결정적 차이`
- `{keyword}는 어떻게 작동하는가`

⚠️ CRITICAL: Extract {keyword} from the ACTUAL SCRIPT CONTENT!

### Thumbnail Style: COMIC STYLE (문화권에 맞게)
⚠️ Use comic/webtoon/manga style matching the script's language!
⚠️ Character shows "curious" or "explaining" expression

**ai_prompts templates:**
- A: Curious character with question mark effects
- B: Character explaining with gesture, diagram-style background
- C: Before/After or comparison split composition
"""

def get_education_prompt():
    return EDUCATION_RULES
