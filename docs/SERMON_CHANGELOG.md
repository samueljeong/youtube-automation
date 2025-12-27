# Sermon 페이지 작업 로그

> **세션 시작 시 반드시 이 파일을 확인하세요!**
> 이전 세션에서 완료된 작업과 다음 할 일을 파악할 수 있습니다.

---

## 2025-12-26 세션

### 대지(본론) 풍성함 지침 강화

**커밋**: `85c8097`

**문제**: 설교문의 대지(본론) 부분이 짧고 빈약함

**수정**:
- `step3_prompt_builder.py:964-976`: 대지 출력 형식에 5가지 요소 명시
- `step3_prompt_builder.py:991-1002`: 설교 작성 원칙 2번 "각 대지는 풍성하게" 추가
- `sermon-step4-copy.js:436-449`: Step4에도 동일 지침 추가

**대지 5가지 요소**:
1. 도입: 핵심 질문/주제 제시 (2-3문장)
2. 본문 해설: 스토리텔링으로 설명 (5-8문장)
3. 예화: 구체적 인물/상황/감정 (5-8문장)
4. 적용: 실천 가능한 제안 (3-5문장)
5. 전환: 다음 대지로 연결 (1-2문장)

**목표**: 각 대지 최소 15-20문장 이상

---

### ★ Step3 시스템 프롬프트 미적용 버그 수정

**커밋**: `42890ae`

**문제**: `build_step3_system_prompt()` 함수가 정의되어 있었지만 API에서 호출되지 않아, 스토리텔링/대화체 지침이 실제로 적용되지 않음

**원인**: `api_sermon.py`에서 시스템 프롬프트를 직접 문자열로 구성하고 있었음
```python
# 이전 (문제)
system_content = "당신은 한국어 설교 전문가입니다..."
```

**수정**:
- `api_sermon.py:38`: `build_step3_system_prompt` import 추가
- `api_sermon.py:973`: 시스템 프롬프트 초기값으로 함수 호출
```python
# 수정 후
system_content = build_step3_system_prompt()
```

**결과**: 이제 Step3 설교문 생성 시 다음 지침이 실제로 적용됨:
- 서론에서 배경을 스토리텔링으로 설명
- 대화체 문체 (~거든요, ~잖아요 등)
- 청중에게 질문을 던지며 함께 생각하게

---

### 대화체 문체 지침 추가

**커밋**: `8d1a2ea`

**문제**: 설교문의 문체가 딱딱하고 격식적이어서 거리감이 있음

**수정**:
- `step3_prompt_builder.py:1022-1038`: 대화체 문체 지침 추가 (7번 원칙)
- `sermon-step4-copy.js:418-434`: Step4에도 동일하게 추가

**지침 내용**:
```
✗ "믿음의 첫 걸음은 떠남입니다. 떠남은 로맨틱한 모험이 아니라..."
✓ "믿음의 첫 걸음이 뭘까요? 떠남이에요. 근데 이 떠남, 영화에서
   보는 것처럼 멋진 모험이 아니거든요..."
```

- "~거든요", "~잖아요", "~죠" 같은 부드러운 어미 사용
- 청중에게 질문을 던지며 함께 생각하게
- 정의보다 예시와 이야기로 설명

---

### 배경 설명 스토리텔링 지침 추가

**커밋**: `7dd53bc`

**문제**: 설교문의 역사적/신학적 배경 설명이 딱딱한 정보 전달 방식

**수정**:
- `step3_prompt_builder.py:960,1012-1020`: Step3 프롬프트에 스토리텔링 지침 추가
- `sermon-step4-copy.js:402-416`: Step4 복사에도 동일하게 추가

**지침 내용**:
```
✗ "이사야서는 주전 8세기에 기록되었으며, 당시 앗수르의 위협이..."
✓ "지금 이 순간, 이스라엘 백성들은 두려움에 떨고 있습니다. 앗수르라는
   거대한 제국이 코앞까지 밀려왔기 때문입니다..."
```

- 역사적 배경을 '사실 나열'이 아닌 '장면 묘사'로 전달
- 청중이 그 시대, 그 장소에 있는 것처럼 느끼게
- 인물의 감정, 고민, 상황을 생생하게

---

### 분당 글자 수 650자로 변경

**커밋**: `59a2e97`

**변경**: `sermon_config.py` - CHARS_PER_MIN: 433 → 650

**결과**: 20분 설교 기준 8,660자 → 13,000자

---

### Step3 로딩 화면 및 중복 클릭 방지

**커밋**: `c0d67aa`

**문제**: Step3 실행 시 로딩 화면이 없어 진행 상황을 알 수 없음

**수정**:
- `sermon-utils.js`: `showStep3Overlay()` / `hideStep3Overlay()` 재작성
  - `.dual-row` (존재하지 않음) 대신 `body`에 오버레이 추가
  - 전체 화면 로딩 오버레이 (z-index: 9999)
  - 버튼 disabled 상태로 중복 클릭 방지

---

### Step1→Step3 누락 데이터 수정 (중요!)

**문제**: Step1에서 수집한 중요 데이터가 Step3 프롬프트에 전달되지 않음

**원인**: 토큰 절약을 위해 데이터를 축약하는 과정에서 일부 항목이 완전히 누락됨

**누락된 항목**:
| 항목 | Step1 수집 | Step3 전달 | 중요도 |
|------|-----------|-----------|--------|
| cross_references | ✅ (주제설교 5개+) | ❌ 미포함 | **높음** |
| context_links | ✅ (앞뒤 문맥) | ❌ 미포함 | 중간 |
| geography_people | ✅ (지리/인물) | ❌ 미포함 | 중간 |

**수정**:
- `step3_prompt_builder.py:1302-1369`: 누락된 3개 항목 Step3 프롬프트에 추가
- `sermon-step4-copy.js:167-217`: Step4 복사에도 동일하게 추가

```python
# step3_prompt_builder.py에 추가된 코드
# 9. cross_references (★ 2025-12-26 추가)
# 10. context_links (★ 2025-12-26 추가)
# 11. geography_people (★ 2025-12-26 추가)
```

**결과**: Step1에서 스타일별로 수집된 데이터가 Step3에서 100% 활용됨

---

### 설교 준비 시작 버튼 안보임 수정

**문제**: 추천 선택 후 "✨ 설교 준비 시작" 버튼이 보이지 않음

**원인**:
1. `startAutoAnalysis()` 완료 후 `finally` 블록에서 `analysisInProgress = false` 설정
2. 하지만 `updateAnalysisUI()`를 호출하지 않아 버튼이 숨겨진 상태로 유지
3. `confirmSelection()` 끝에서도 `updateAnalysisUI()`를 호출하지 않음

**수정**:
- `sermon-render.js:423`: `finally` 블록에서 `updateAnalysisUI()` 호출 추가
- `sermon-init.js:1104`: `confirmSelection()` 끝에서 `updateAnalysisUI()` 호출 추가

**검증 체크리스트 교훈**:
- UI 상태 변경 후 항상 `updateAnalysisUI()` 호출 필요
- `finally` 블록에서 상태 변경 시 UI 업데이트도 함께 해야 함

---

### 3순위 운영 지원팀 에이전트 추가

**커밋**: `520a1ed`

**추가된 에이전트**:
| 에이전트 | 역할 |
|---------|------|
| MonitorAgent | 프로덕션 로그 모니터링, 에러 감지 |
| CacheAgent | Step1/Step2 결과 캐싱, 비용 절감 |
| BenchmarkAgent | 설교문 품질 평가, A/B 테스트 |

---

## 2025-12-25 세션

### 슈퍼바이저 에이전트 시스템 구축

**작업 내용**: 개발 효율화를 위한 슈퍼바이저 에이전트 시스템 도입

**생성된 파일**: `docs/SUPERVISOR_AGENT.md`

**에이전트 구조**:
- **1순위 팀 (핵심개발)**: AnalyzerAgent, WriterAgent, TestAgent
- **2순위 팀 (개발지원)**: UIAgent, APIAgent, DocAgent
- **서비스 팀 (런타임)**: Step1~3 Agent, Meditation, QA, Design

---

### Step2 Unit-Anchor 범위 검증 동적화

**문제**: `section_verse_ranges`가 하드코딩되어 모든 본문에 1-2절/3-5절/6-7절 범위 적용

**원인**: Step1의 `structure_outline`에서 동적으로 범위를 가져오지 않음

**수정**:
- `step3_prompt_builder.py:1839-1862`: Step1의 structure_outline에서 동적 범위 추출
- `api_sermon.py:393,649-660`: Step2 검증 시 Step1 결과 전달

```python
# 변경 전 (하드코딩)
section_verse_ranges = {
    "section_1": (1, 2),  # 고정
    "section_2": (3, 5),
    "section_3": (6, 7),
}

# 변경 후 (동적)
for idx, unit in enumerate(structure_outline):
    verse_range = unit.get("verse_range", "")
    verse_nums = re.findall(r"(\d+)", verse_range)
    section_verse_ranges[f"section_{idx+1}"] = (min_v, max_v)
```

---

### Step3 서버 측 글자수 검증 추가

**문제**: GPT의 self_check만으로 글자수 검증 → 실제 글자수와 불일치 가능

**수정**: `api_sermon.py:1426-1454` - 서버에서 실제 글자수 확인 후 응답에 포함

**응답 추가 필드**:
```json
{
  "char_info": {
    "actual": 5432,
    "target": 5400,
    "min": 4860,
    "max": 5940,
    "status": "ok|insufficient|excessive",
    "shortage": 0  // 미달 시 부족 글자수
  }
}
```

---

## 2025-12-23 세션

### Step3/Step4 프롬프트 토큰 최적화

**문제**: Step1/Step2가 추출하는 데이터가 너무 많아서 Step4에서 GPT 토큰 제한에 걸림

**원인**:
- Step1: anchors 10개+, historical_background 3개+, guardrails 15개+, key_terms 6개 등 전체 포함
- Step2: sections, illustrations, context_data 전체 포함
- Strong's 원어 분석: 7개 포함
- 시대 컨텍스트: 뉴스 카테고리당 2개, 관심사 전체 포함

**수정 (토큰 절약)**:

| 항목 | 변경 전 | 변경 후 |
|------|---------|---------|
| anchors | 전체 (10개+) | 상위 5개 |
| historical_background | 전체 (3개+) | 상위 2개 |
| key_terms/key_words | 전체 (6개) | 상위 3개 |
| guardrails.clearly_affirms | 전체 (5개+) | 상위 3개 |
| guardrails.does_not_claim | 전체 (5개+) | 상위 3개 |
| Strong's 원어 분석 | 7개 | 3개 |
| Strong's definition 길이 | 200자 | 100자 |
| 본론/대지 (sections) | 전체 | 상위 3개 |
| 예화 (illustrations) | 전체 | 상위 2개 |
| 시대 컨텍스트 뉴스 | 카테고리당 2개 | 카테고리당 1개, 최대 3개 |
| 청중 관심사 | 전체 | 상위 3개 |
| 문자열 결과 길이 제한 | 없음 | 2000자 |

**수정 파일**:
- `sermon_modules/step3_prompt_builder.py`: `build_step3_prompt_from_json()` 함수
- `static/js/sermon-step4-copy.js`: `assembleGptProDraft()` 함수

**예상 효과**: 프롬프트 토큰 약 40~50% 감소

---

## 2025-12-22 세션

### 1. Step3/Step4 프롬프트 통일 (`a276c14`)

**문제**: Step3(내부 API)와 Step4(외부 GPT 복사용)의 결과물이 달랐음

**원인**:
- Step3: JSON 파싱 후 특정 필드만 추출
- Step4: 텍스트 형식으로 상세 출력

**수정**:
- `sermon_modules/prompt.py`의 `build_step3_prompt_from_json()` 함수를 Step4 형식으로 변경
- 헤더, 최우선 지침, Strong's 분석, 시대 컨텍스트 등 동일하게 출력

---

### 2. 분량별 글자 수 기준 추가 (`347b5a6`)

**문제**: 25분 설교 요청 시 3,500자만 출력됨 (기대값 6,750자)

**원인**: 분량에 대한 구체적인 글자 수 기준이 없었음

**수정**:
- 분당 270자 기준 추가 (한국어 설교 평균 속도)
- `get_duration_char_count()` 함수 추가 (Python)
- `getDurationCharCount()` 함수 추가 (JavaScript)
- ±10% 허용 범위 설정

| 분량 | 최소 | 목표 | 최대 |
|------|------|------|------|
| 10분 | 2,430자 | 2,700자 | 2,970자 |
| 15분 | 3,645자 | 4,050자 | 4,455자 |
| 20분 | 4,860자 | 5,400자 | 5,940자 |
| 25분 | 6,075자 | 6,750자 | 7,425자 |
| 30분 | 7,290자 | 8,100자 | 8,910자 |
| 40분 | 9,720자 | 10,800자 | 11,880자 |

---

### 3. Step3/Step4 누락 필드 보완 (`b5b1538`)

**문제**:
- Step3에 소대지(subpoints) 누락
- Step4에 예화(illustrations) 누락

**수정**:
- `step3_prompt_builder.py`: Step2 결과에서 소대지 추출 로직 추가
- `sermon-step4-copy.js`: Step2 결과에서 예화 추출 로직 추가

---

### 4. Step4 이모지 제거 및 존대어 필수 지침 (`a664b85`)

**문제**:
- 프롬프트에 이모지 사용 (📖, 🚨, ⚠️ 등)
- 청소년 대상 설교 시 반말로 작성됨

**수정**:
- 모든 이모지를 텍스트로 대체:
  - `📖` → (삭제)
  - `🚨` → `[필수]`
  - `⚠️` → `[중요]`
  - `✅` → `[해야 할 것]`
  - `❌` → `[하지 말 것]`
  - `📌` → (삭제)
- 존대어 필수 지침 추가:
  ```
  [필수] 어체: 존대어 (경어체)
     - 대상이 청소년/어린이여도 반드시 존대어로 작성하세요.
     - "~합니다", "~입니다", "~하십시오" 형태를 사용하세요.
     - 반말("~해", "~야") 사용 금지.
  ```

---

### 5. 분량별 글자 수 요구사항 강화 (`ebaa44a`)

**문제**: 글자 수 기준이 있어도 GPT가 충분히 따르지 않음

**수정**:
- 최소/목표/최대 글자 수를 명확히 구분하여 강조
- 섹션별 배분 가이드 추가:
  - 서론: 15%
  - 본론: 65%
  - 결론: 20%
- 25분 이상 설교 시 각 대지마다 예화+적용 필수 명시
- "불합격" 경고 문구 추가
- 최종 확인 섹션에서 글자 수 재확인 요청

**프롬프트 예시 (25분)**:
```
[최우선 필수] 분량: 25분 = 6,750자
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
   최소 글자 수: 6,075자 (이 미만은 불합격)
   목표 글자 수: 6,750자
   최대 글자 수: 7,425자
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
   계산 기준: 25분 × 270자/분 = 6,750자

   [분량 맞추기 전략]
   - 서론: 약 1,013자 (도입, 성경 배경)
   - 본론: 약 4,388자 (대지별 설명 + 예화 + 적용)
   - 결론: 약 1,350자 (요약 + 결단 촉구 + 기도)
   - 각 대지마다 예화 1개, 적용 1개를 반드시 포함하세요.

   [경고] 6,075자 미만 작성 시 불합격 처리됩니다.
```

---

## 2025-11-26 세션

### Step3 스타일별 지침 JSON 구조 추가

**문제 상황**:
- Step1, Step2는 스타일별로 다른 JSON 지침이 있었지만, Step3는 공통 프롬프트만 사용
- Step1/Step2에서 체계적으로 분석해도 Step3가 이를 제대로 반영하지 못함
- 결과적으로 모든 스타일의 설교가 비슷하게 나오는 문제

**해결 방향**: Step3도 스타일마다 다른 지침 JSON을 사용하도록 변경

**완료된 작업**:

#### 프론트엔드 (sermon.html)
- `renderGuideTabs()` 함수 수정
- Step1, Step2 탭 외에 **Step3 탭** 추가
- 스타일 선택 시 Step1, Step2, Step3 지침 모두 편집 가능
- Step3 API 호출 시 `step3Guide` 추가 전송
- localStorage에서 `guide-{category}-{style}-step3` 키로 불러옴

#### 백엔드 (sermon_server.py)
- `/api/sermon/gpt-pro` 엔드포인트에 `step3_guide` 추가
- `build_step3_prompt_from_json()` 함수 전면 개편
- 우선순위 체계:
  1. 홈화면 설정 (최우선)
  2. Step3 스타일별 지침
  3. Step2 설교 구조 (필수 반영)
  4. Step1 분석 자료 (참고 활용)

**관련 함수/변수 위치**:
| 위치 | 함수/변수 | 행 번호 |
|------|----------|---------|
| 프론트엔드 | `renderGuideTabs()` | ~3857행 |
| 프론트엔드 | Step3 API 호출 | ~3382행 |
| 프론트엔드 | `getGuideKey()` | ~2769행 |
| 백엔드 | `build_step3_prompt_from_json()` | ~1458행 |
| 백엔드 | `/api/sermon/gpt-pro` | ~1894행 |

---

## 수정된 파일 목록

| 파일 | 설명 |
|------|------|
| `sermon_modules/step3_prompt_builder.py` | Step3 프롬프트 빌더, 글자 수 함수 |
| `sermon_modules/api_sermon.py` | API 파라미터 전달 |
| `static/js/sermon-step4-copy.js` | Step4 프롬프트 빌더, 글자 수 함수 |
| `templates/sermon.html` | renderGuideTabs() 수정, Step3 지침 전송 |
| `sermon_server.py` | step3_guide 받기, build_step3_prompt_from_json() 개편 |

---

## 향후 고려사항 (TODO)

1. **Step3 지침 JSON 샘플 작성**: 3대지, 강해설교 등 스타일별
2. **Step3 API 응답 검증**: 글자 수 미달 시 자동 재생성 로직
3. **비용 추적**: GPT-5.1 사용 시 비용 계산 (약 40분 설교 = ₩650~1,300)
4. **A/B 테스트**: 프롬프트 변경에 따른 품질 비교

---

## Step 명칭 규칙 (참고)

| Step | 명칭 | 설명 | UI 요소 |
|------|------|------|---------|
| **Step1** | 배경 분석 | 성경 본문 배경/맥락 분석 | - |
| **Step2** | 설교 구조 | 설교 초안/구조 생성 | - |
| **Step3** | 설교문 완성 | GPT-PRO로 최종 설교문 작성 | 분홍색 버튼 |
| **Step4** | 전체 복사 | 개인 GPT에 붙여넣기용 전체 복사 | 보라색 버튼 |
