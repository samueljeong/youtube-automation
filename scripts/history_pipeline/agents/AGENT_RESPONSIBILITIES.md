# 한국사 파이프라인 - 에이전트 역할 및 책임 명세서

> **작성자**: PlannerAgent (기획 에이전트)
> **목적**: 각 에이전트의 역할을 명확히 하고, 품질 기준을 강제하여 완성도 높은 영상 제작

---

## 1. 전체 파이프라인 흐름

```
┌─────────────────────────────────────────────────────────────────┐
│  PlannerAgent (기획)                                            │
│  - 에피소드 구조 설계                                           │
│  - 하위 에이전트 지침 하달                                       │
│  - 품질 기준 설정                                               │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  ScriptAgent (대본)                                             │
│  - 12,000~15,000자 대본 작성                                    │
│  - YouTube 메타데이터 생성                                       │
│  ⚠️ 글자수 미달 시 진행 차단                                    │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  ReviewAgent (검수) - 1차                                       │
│  - 대본 품질 검증                                               │
│  - 역사적 정확성 확인                                           │
│  ⚠️ 검수 실패 시 ScriptAgent로 피드백                           │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  ImageAgent (이미지)                                            │
│  - 시대별 스타일 적용                                           │
│  - 5~12개 이미지 프롬프트 생성                                   │
│  - 썸네일 가이드 생성                                           │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  ReviewAgent (검수) - 2차                                       │
│  - 이미지 프롬프트 적합성 확인                                   │
│  - 시대 고증 오류 체크                                          │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  YouTubeAgent (메타데이터)                                       │
│  - SEO 최적화 제목 생성 (3가지 스타일)                          │
│  - 검색 친화적 설명 작성                                        │
│  - 태그 및 썸네일 텍스트 생성                                   │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  실행 단계 (workers.py)                                         │
│  - TTS 생성                                                     │
│  - 이미지 생성                                                   │
│  - 영상 렌더링                                                   │
│  - YouTube 업로드                                               │
└─────────────────────────────────────────────────────────────────┘
```

---

## 2. 각 에이전트 상세 책임

### 2.1 PlannerAgent (기획 에이전트)

**역할**: 총괄 기획 및 하위 에이전트 지휘

**입력**:
- 시대 (era_name)
- 주제/제목 (title)
- 참고 자료 URL (optional)

**출력**:
- 에피소드 기획서 (brief)
- 구조 설계 (인트로/배경/본론1/본론2/마무리)
- 핵심 포인트 3~5개
- 다음화 예고 훅

**검증 기준**:
| 항목 | 기준 | 실패 시 |
|------|------|---------|
| 구조 완성도 | 5개 섹션 모두 정의 | 재작성 |
| 핵심 포인트 | 최소 3개 | 재작성 |
| 시대 정보 | ERA_STYLE_PRESETS에 존재 | 기본값 사용 |

**하위 에이전트 지침 하달**:
```python
{
    "script_agent": {
        "target_length": 13500,
        "min_length": 12000,
        "max_length": 15000,
        "style": "대화체",
        "structure": ["인트로", "배경", "본론1", "본론2", "마무리"],
    },
    "image_agent": {
        "era_style": "발해",  # ERA_STYLE_PRESETS 키
        "image_count": "auto",  # 대본 길이 기반 자동 계산
        "aspect_ratio": "16:9",
    },
    "review_agent": {
        "check_length": True,
        "check_accuracy": True,
        "check_style": True,
        "max_attempts": 3,
    }
}
```

---

### 2.2 ScriptAgent (대본 에이전트)

**역할**: 역사 다큐멘터리 대본 작성

**입력**:
- 기획서 (brief) from PlannerAgent
- 피드백 (optional) from ReviewAgent

**출력**:
- 대본 (script): 12,000~15,000자
- YouTube 메타데이터 (title, description, tags)
- 인용 출처 (citations)

**필수 검증 (자체)**:
```python
def validate_script(self, script: str) -> bool:
    length = len(script)

    # ❌ 절대 통과 불가 조건
    if length < self.min_length:
        raise ValueError(f"대본 길이 부족: {length}자 (최소 {self.min_length}자)")

    if length > self.max_length:
        raise ValueError(f"대본 길이 초과: {length}자 (최대 {self.max_length}자)")

    # ⚠️ 경고 조건
    if length < self.target_length:
        self.log_warning(f"목표 미달: {length}자 (목표 {self.target_length}자)")

    return True
```

**품질 체크리스트**:
| 항목 | 기준 | 검증 방법 |
|------|------|----------|
| 글자수 | 12,000~15,000자 | `len(script)` |
| 섹션 구조 | 5개 섹션 존재 | 구분자 체크 |
| 문체 | 대화체 (~거든요, ~었어요) | 패턴 매칭 |
| 연도 표기 | 최소 5개 이상 | 정규식 |
| 인물명 | 최소 3명 이상 | 정규식 |

---

### 2.3 ImageAgent (이미지 에이전트)

**역할**: 시대별 스타일에 맞는 이미지 프롬프트 생성

**입력**:
- 대본 (script) from ScriptAgent
- 시대 스타일 (era_style) from PlannerAgent

**출력**:
- 이미지 프롬프트 목록 (5~12개)
- 썸네일 가이드
- 스타일 가이드

**필수 적용 - 시대별 스타일**:
```python
ERA_STYLE_PRESETS = {
    "고조선": {"style": "mythological, ancient Korean", "mood": "mysterious"},
    "삼국시대": {"style": "Three Kingdoms period", "mood": "heroic"},
    "발해": {"style": "Balhae kingdom, northern Korean", "mood": "vast, powerful"},
    "고려": {"style": "Goryeo dynasty, Buddhist", "mood": "elegant"},
    "조선": {"style": "Joseon dynasty, Confucian", "mood": "dignified"},
    # ... 등
}
```

**프롬프트 생성 규칙**:
1. **시대 스타일 필수 포함**: `{era_style['style']}, {era_style['mood']}`
2. **네거티브 프롬프트 필수**: `text, watermark, modern elements`
3. **해상도 명시**: `16:9 aspect ratio, high detail`

**이미지 개수 계산**:
```python
def calculate_image_count(script_length: int) -> int:
    minutes = script_length / 910  # 한국어 TTS 기준
    if minutes < 8: return 5
    elif minutes < 10: return 8
    elif minutes < 15: return 11
    else: return 12
```

---

### 2.4 YouTubeAgent (유튜브 메타데이터 에이전트)

**역할**: SEO 전문가 및 YouTube 알고리즘 최적화

**입력**:
- 대본 (script) from ScriptAgent
- 기획서 (brief) from PlannerAgent

**출력**:
- 제목 (3가지 스타일: curiosity/solution/authority)
- 설명 (SEO 최적화)
- 태그 (최대 500자)
- 썸네일 텍스트 제안
- 타임스탬프 제안

**제목 스타일**:
| 스타일 | 예시 | 용도 |
|--------|------|------|
| curiosity | "발해의 숨겨진 비밀" | 호기심 유발 |
| solution | "발해 완벽 정리" | 정보 제공 |
| authority | "[한국사] 발해 \| 대조영의 건국" | 권위 강조 |

**SEO 원칙**:
```python
{
    "title": {
        "max_length": 100,  # YouTube 최대
        "optimal_length": 50,  # 권장 (검색 결과에서 잘리지 않음)
        "keyword_position": "앞배치",  # 핵심 키워드를 제목 앞에
    },
    "description": {
        "first_2_lines": "핵심 정보",  # 검색 결과에 표시
        "hashtags": ["#한국사", "#시대명", "#키워드"],
        "cta": "구독/좋아요 유도",
    },
    "tags": {
        "order": "대주제 → 세부주제",  # 한국사 → 발해 → 대조영
        "max_length": 500,
    }
}
```

---

### 2.5 ReviewAgent (검수 에이전트)

**역할**: 품질 검증 및 피드백 생성

**검수 대상**:
1. 대본 (ScriptAgent 출력)
2. 이미지 프롬프트 (ImageAgent 출력)
3. 코드 변경사항 (CodeReviewAgent)

**대본 검수 체크리스트**:
| 항목 | 기준 | 통과 조건 |
|------|------|----------|
| 글자수 | 12,000~15,000자 | 필수 |
| 역사적 정확성 | 명백한 오류 없음 | 필수 |
| 문체 일관성 | 대화체 유지 | 권장 |
| 구조 완성도 | 5개 섹션 | 필수 |
| 인물/연도 | 최소 기준 충족 | 필수 |

**이미지 프롬프트 검수 체크리스트**:
| 항목 | 기준 | 통과 조건 |
|------|------|----------|
| 시대 스타일 | ERA_STYLE_PRESETS 적용 | 필수 |
| 개수 | 대본 길이 대비 적정 | 필수 |
| 시대 고증 | 현대적 요소 없음 | 필수 |
| 텍스트 포함 | 이미지 내 텍스트 최소화 | 권장 |

**검수 결과 형식**:
```python
class ReviewResult:
    status: Literal["APPROVED", "NEEDS_REVISION", "REJECTED"]
    issues: List[str]
    suggestions: List[str]
    blocking_issues: List[str]  # 이게 있으면 진행 불가
```

**피드백 루프**:
```
ScriptAgent → ReviewAgent → [APPROVED] → ImageAgent
                         → [NEEDS_REVISION] → ScriptAgent (피드백 반영)
                         → [REJECTED] → PlannerAgent (재기획)
```

---

## 3. 품질 게이트 (Quality Gates)

### Gate 1: 대본 완성
- [ ] 글자수 12,000~15,000자
- [ ] 5개 섹션 구조 완성
- [ ] YouTube 메타데이터 생성

### Gate 2: 대본 검수 통과
- [ ] ReviewAgent APPROVED
- [ ] 역사적 오류 없음
- [ ] 문체 일관성

### Gate 3: 이미지 가이드 완성
- [ ] 시대별 스타일 적용
- [ ] 적정 개수 (5~12개)
- [ ] 썸네일 가이드 포함

### Gate 4: YouTube 메타데이터 완성
- [ ] SEO 최적화 제목 (3가지 스타일)
- [ ] 검색 친화적 설명 (해시태그 포함)
- [ ] 태그 생성 (500자 이내)
- [ ] 썸네일 텍스트 제안

### Gate 5: 실행 준비 완료
- [ ] 모든 검수 통과
- [ ] 리소스 준비 (API 키 등)

---

## 4. 에러 처리 및 재시도

### 재시도 정책
| 에이전트 | 최대 시도 | 재시도 조건 |
|---------|----------|------------|
| ScriptAgent | 3회 | NEEDS_REVISION |
| ImageAgent | 2회 | 스타일 미적용 |
| ReviewAgent | 1회 | - |

### 에스컬레이션
- 3회 실패 → PlannerAgent에 보고
- PlannerAgent 판단 → 재기획 또는 중단

---

## 5. 로깅 및 추적

모든 에이전트는 다음을 로깅해야 함:
```python
context.add_log(
    agent_name="ScriptAgent",
    message="대본 생성 완료",
    status="success|error|warning",
    detail="13,245자, 구조 완성"
)
```

---

## 6. 코드 구현 요구사항

### 6.1 ScriptAgent 필수 추가
```python
def execute(self, context, **kwargs):
    # ... 대본 생성 ...

    # ⚠️ 필수: 자체 검증
    if not self._validate_length(script):
        raise ValueError("대본 길이 기준 미달")

    return result
```

### 6.2 ImageAgent 필수 추가
```python
def execute(self, context, **kwargs):
    # ⚠️ 필수: 시대 스타일 적용
    era_style = self._get_era_style(context.era_name)
    if not era_style:
        raise ValueError(f"시대 스타일 없음: {context.era_name}")

    # 프롬프트에 스타일 강제 포함
    for prompt in prompts:
        prompt["style_prefix"] = f"{era_style['style']}, {era_style['mood']}"
```

### 6.3 ReviewAgent 필수 추가
```python
def execute(self, context, **kwargs):
    # ⚠️ 필수: 블로킹 이슈 체크
    blocking_issues = self._check_blocking_issues(context)

    if blocking_issues:
        return AgentResult(
            success=False,
            status="REJECTED",
            blocking_issues=blocking_issues
        )
```

---

## 7. 최종 점검 체크리스트

에피소드 제작 전 확인:
- [ ] PlannerAgent 기획서 완성
- [ ] ScriptAgent 대본 12,000자 이상
- [ ] ReviewAgent 1차 검수 통과
- [ ] ImageAgent 시대 스타일 적용
- [ ] ReviewAgent 2차 검수 통과
- [ ] YouTubeAgent SEO 메타데이터 생성
- [ ] 모든 리소스 준비 완료

---

*이 문서는 PlannerAgent가 작성하며, 모든 하위 에이전트는 이 지침을 준수해야 합니다.*
