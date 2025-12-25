# Sermon 슈퍼바이저 에이전트 시스템

> **역할**: 사용자의 지시를 받아 하위 에이전트들을 효율적으로 관리하고 Sermon 시스템 개발/운영을 총괄

---

## 시스템 개요

```
┌──────────────────────────────────────────────────────────────────────┐
│                         사용자 (User)                                 │
│                              │                                        │
│                         지시/요청                                     │
│                              ▼                                        │
│  ┌────────────────────────────────────────────────────────────────┐  │
│  │                 슈퍼바이저 에이전트 (Supervisor)                │  │
│  │                                                                 │  │
│  │  - 사용자 요청 분석 및 작업 분배                               │  │
│  │  - 하위 에이전트 결과 검수 및 품질 관리                        │  │
│  │  - 전체 워크플로우 관리                                        │  │
│  └────────────────────────────────────────────────────────────────┘  │
│                              │                                        │
│         ┌────────────────────┼────────────────────┐                  │
│         ▼                    ▼                    ▼                  │
│  ┌─────────────┐     ┌─────────────┐      ┌─────────────┐           │
│  │  1순위 팀   │     │  2순위 팀   │      │  서비스 팀  │           │
│  │  (핵심개발) │     │  (개발지원) │      │  (런타임)   │           │
│  └─────────────┘     └─────────────┘      └─────────────┘           │
│         │                    │                    │                  │
│    ┌────┼────┐          ┌────┼────┐          ┌────┼────┐            │
│    ▼    ▼    ▼          ▼    ▼    ▼          ▼    ▼    ▼            │
│  [Ana][Wri][Tst]      [UI][API][Doc]      [S1][S2][S3]...           │
└──────────────────────────────────────────────────────────────────────┘
```

---

## 개발 에이전트 (1순위 + 2순위)

### 1순위: 핵심 개발팀

#### AnalyzerAgent (프롬프트 분석)
| 항목 | 내용 |
|------|------|
| **역할** | Step1~4 프롬프트 분석, 토큰 최적화, 품질 개선 |
| **담당 파일** | `sermon_modules/step3_prompt_builder.py`, `static/js/sermon-step4-copy.js` |
| **주요 작업** | 프롬프트 토큰 최적화, 출력 품질 개선, 글자수 기준 조정 |
| **관련 로그** | `docs/SERMON_CHANGELOG.md` (Step3/Step4 섹션) |

**호출 시점:**
- 프롬프트 토큰 초과 문제 발생 시
- GPT 출력 품질 문제 발생 시
- 새로운 스타일/분량 추가 시

---

#### WriterAgent (설교문 품질)
| 항목 | 내용 |
|------|------|
| **역할** | 설교문 품질 검증, 글자수 검증, 구조 검토 |
| **담당 파일** | `sermon_modules/api_sermon.py` (gpt-pro 엔드포인트) |
| **주요 작업** | 글자수 미달 수정, 구조 검증 로직, 재생성 트리거 |
| **품질 기준** | 분당 270자, 서론 15% / 본론 65% / 결론 20% |

**검증 항목:**
- 최소 글자수 충족 여부
- 대지/소대지 구조 완성도
- 예화 포함 여부 (25분 이상)
- 존대어 사용 여부

---

#### TestAgent (테스트/검증)
| 항목 | 내용 |
|------|------|
| **역할** | 기능 테스트, 버그 검증, 회귀 테스트 |
| **담당 파일** | 전체 (수정된 파일 중심) |
| **주요 작업** | API 호출 테스트, UI 동작 확인, 에러 재현 |
| **테스트 방법** | curl 명령, 브라우저 테스트, 로그 분석 |

**테스트 체크리스트:**
```
[ ] API 응답 정상 (200 OK)
[ ] JSON 파싱 성공
[ ] 글자수 기준 충족
[ ] UI 렌더링 정상
[ ] 에러 핸들링 동작
```

---

### 2순위: 개발 지원팀

#### UIAgent (프론트엔드)
| 항목 | 내용 |
|------|------|
| **역할** | 프론트엔드 JS/CSS 수정, UI 버그 수정 |
| **담당 파일** | `static/js/sermon-*.js`, `static/css/sermon.css`, `templates/sermon.html` |
| **주요 작업** | 버튼 동작, 렌더링, 스타일 수정 |

**파일별 역할:**
| 파일 | 담당 기능 |
|------|----------|
| sermon-main.js | 전역 변수, 설정 |
| sermon-step.js | Step 처리 로직 |
| sermon-step4-copy.js | Step4 전체 복사 |
| sermon-render.js | UI 렌더링 |
| sermon-qa.js | Q&A, 챗봇 |
| sermon-meditation.js | 묵상 메시지 |
| sermon-design.js | 디자인 도우미 |
| sermon-admin.js | 관리자 기능 |
| sermon-firebase.js | Firebase 연동 |
| sermon-utils.js | 유틸리티 |
| sermon-init.js | 앱 초기화 |

---

#### APIAgent (백엔드)
| 항목 | 내용 |
|------|------|
| **역할** | 백엔드 API 수정, 새 엔드포인트 추가 |
| **담당 파일** | `sermon_modules/api_sermon.py`, `sermon_modules/api_banner.py`, `sermon_server.py` |
| **주요 작업** | API 로직 수정, 에러 핸들링, DB 연동 |

**API 엔드포인트:**
| 엔드포인트 | 파일 위치 | 기능 |
|-----------|----------|------|
| `/api/sermon/process` | api_sermon.py:367 | Step1, Step2 |
| `/api/sermon/gpt-pro` | api_sermon.py:862 | Step3 |
| `/api/sermon/meditation` | api_sermon.py:704 | 묵상 |
| `/api/sermon/qa` | api_sermon.py:1429 | Q&A |
| `/api/sermon/chat` | api_sermon.py:1585 | 챗봇 |

---

#### DocAgent (문서화)
| 항목 | 내용 |
|------|------|
| **역할** | CHANGELOG 업데이트, 문서 정리, 작업 기록 |
| **담당 파일** | `docs/SERMON_CHANGELOG.md`, `SERMON_MODULE_STRUCTURE.md`, `TODO_SERMON.md` |
| **주요 작업** | 작업 완료 기록, 버그 수정 이력, 다음 작업 정리 |

**문서 작성 규칙:**
```markdown
## YYYY-MM-DD 세션

### 작업 제목

**문제**: 문제 상황 설명
**원인**: 근본 원인
**수정**: 수정 내용 (파일:라인)
**커밋**: 해시값
```

---

### 3순위: 운영 지원팀

#### MonitorAgent (모니터링)
| 항목 | 내용 |
|------|------|
| **역할** | 프로덕션 로그 모니터링, 에러 감지, 알림 |
| **담당 파일** | `logs/`, `sermon_server.py` (로깅 부분), `sermon_modules/api_sermon.py` |
| **주요 작업** | 에러 패턴 분석, 성능 병목 감지, 사용량 추적 |
| **출력** | 에러 리포트, 성능 대시보드, 알림 트리거 |

**모니터링 항목:**
| 항목 | 임계값 | 대응 |
|------|--------|------|
| API 에러율 | > 5% | 즉시 알림 |
| 응답 시간 | > 30초 | 성능 분석 |
| 글자수 미달율 | > 20% | AnalyzerAgent 호출 |
| API 호출 실패 | 연속 3회 | 재시도 로직 검토 |

**로그 분석 패턴:**
```python
# 주요 감시 패턴
ERROR_PATTERNS = [
    r"API.*failed",
    r"timeout",
    r"글자수.*미달",
    r"토큰.*초과",
    r"JSON.*parse.*error"
]
```

---

#### CacheAgent (캐시 관리)
| 항목 | 내용 |
|------|------|
| **역할** | Step1/Step2 결과 캐싱, 중복 호출 방지, 비용 절감 |
| **담당 파일** | `sermon_modules/cache.py` (생성 예정), `sermon_modules/api_sermon.py` |
| **주요 작업** | 캐시 키 생성, TTL 관리, 캐시 무효화 |
| **저장소** | Redis (프로덕션), 메모리 (개발) |

**캐시 전략:**
| 단계 | 캐시 키 | TTL | 이유 |
|------|---------|-----|------|
| Step1 | `sermon:step1:{book}:{chapter}:{verse}:{style}` | 24시간 | 본문 분석은 거의 변하지 않음 |
| Step2 | `sermon:step2:{step1_hash}:{duration}` | 12시간 | 분량에 따라 구조 변경 가능 |
| Strong's | `strongs:{word_id}` | 7일 | 원어 분석은 불변 |
| 주석 | `commentary:{verse}:{style}` | 7일 | 주석은 거의 불변 |

**비용 절감 효과:**
```
예상 캐시 히트율: 30~40%
예상 비용 절감: 월 $50~100 (gpt-4o 기준)
```

**캐시 무효화 조건:**
- 프롬프트 템플릿 변경 시
- 스타일 지침 업데이트 시
- 사용자 수동 새로고침 요청 시

---

#### BenchmarkAgent (품질 평가)
| 항목 | 내용 |
|------|------|
| **역할** | 설교문 품질 자동 평가, A/B 테스트, 메트릭 수집 |
| **담당 파일** | `sermon_modules/benchmark.py` (생성 예정), `docs/BENCHMARK_RESULTS.md` |
| **주요 작업** | 품질 점수 산정, 프롬프트 A/B 테스트, 결과 비교 |
| **출력** | 품질 리포트, A/B 테스트 결과, 개선 제안 |

**품질 평가 기준:**
| 항목 | 가중치 | 측정 방법 |
|------|--------|----------|
| 글자수 충족 | 25% | 목표 대비 실제 글자수 |
| 구조 완성도 | 25% | 대지/소대지 개수, 예화 포함 |
| 본문 활용 | 20% | 성경 구절 인용 횟수 |
| 적용 구체성 | 15% | 적용 섹션 길이/구체성 |
| 신학적 정확성 | 15% | guardrails 위반 여부 |

**A/B 테스트 프레임워크:**
```python
# 테스트 예시
EXPERIMENTS = {
    "prompt_v2": {
        "control": "기존 프롬프트",
        "treatment": "개선 프롬프트",
        "metric": "char_count_satisfaction",
        "sample_size": 50,
        "duration": "7일"
    }
}
```

**품질 점수 산정 (100점 만점):**
```
총점 = (글자수_점수 × 0.25) + (구조_점수 × 0.25) +
       (본문활용_점수 × 0.20) + (적용_점수 × 0.15) +
       (신학_점수 × 0.15)

등급: A (90+), B (80-89), C (70-79), D (60-69), F (<60)
```

---

## 에이전트 호출 규칙

### 슈퍼바이저 판단 기준

| 요청 유형 | 호출 에이전트 | 순서 |
|----------|--------------|------|
| 프롬프트 문제 | AnalyzerAgent → TestAgent → DocAgent | 순차 |
| 설교문 품질 | WriterAgent → TestAgent → DocAgent | 순차 |
| UI 버그 | UIAgent → TestAgent → DocAgent | 순차 |
| API 버그 | APIAgent → TestAgent → DocAgent | 순차 |
| 새 기능 | APIAgent + UIAgent → TestAgent → DocAgent | 병렬 후 순차 |
| 에러 분석 | MonitorAgent → APIAgent/UIAgent → DocAgent | 순차 |
| 비용 최적화 | CacheAgent → TestAgent → DocAgent | 순차 |
| 품질 개선 | BenchmarkAgent → AnalyzerAgent → TestAgent | 순차 |

### 에이전트 협업 패턴

```
1. 단순 수정
   └─ 담당Agent → TestAgent → DocAgent

2. 복합 수정 (프론트+백엔드)
   ├─ APIAgent ──┐
   └─ UIAgent ───┼─→ TestAgent → DocAgent
                 └─ (병렬 실행)

3. 대규모 변경
   └─ AnalyzerAgent → APIAgent → UIAgent → TestAgent → DocAgent
```

---

## 작업 완료 체크리스트

모든 작업 완료 시 반드시 확인:

```
[ ] 1. 코드 수정 완료
[ ] 2. TestAgent 검증 통과
[ ] 3. DocAgent 문서 업데이트
[ ] 4. git commit (명확한 메시지)
[ ] 5. git push
```

---

## 서비스 에이전트 (런타임)

> 실제 설교 작성 서비스를 제공하는 에이전트들

### 1. 분석 에이전트 (Step1 Agent)
| 항목 | 내용 |
|------|------|
| **역할** | 성경 본문 배경/맥락 분석 |
| **입력** | 성경 구절, 설교 스타일, 카테고리 |
| **출력** | anchors, historical_background, key_terms, guardrails 등 |
| **API** | `POST /api/sermon/process` (step=step1) |
| **모듈** | `sermon_modules/api_sermon.py` |

**주요 분석 항목:**
- 핵심 앵커 (anchors) - 본문의 핵심 메시지
- 역사적 배경 (historical_background)
- 핵심 용어 (key_terms)
- 신학적 가드레일 (guardrails) - 해석의 한계

---

### 2. 구조 에이전트 (Step2 Agent)
| 항목 | 내용 |
|------|------|
| **역할** | 설교 구조/초안 생성 |
| **입력** | Step1 결과, 설교 스타일, 분량 |
| **출력** | sections (대지), subpoints (소대지), illustrations (예화) |
| **API** | `POST /api/sermon/process` (step=step2) |
| **모듈** | `sermon_modules/api_sermon.py` |

**출력 구조:**
```json
{
  "sections": [
    {"title": "대지1", "content": "...", "subpoints": ["소대지1", "소대지2"]}
  ],
  "illustrations": ["예화1", "예화2"],
  "context_data": {...}
}
```

---

### 3. 작성 에이전트 (Step3 Agent)
| 항목 | 내용 |
|------|------|
| **역할** | 최종 설교문 작성 (GPT-PRO) |
| **입력** | Step1 + Step2 결과, 스타일 지침, 분량 |
| **출력** | 완성된 설교문 (글자 수 기준 충족) |
| **API** | `POST /api/sermon/gpt-pro` |
| **모듈** | `sermon_modules/api_sermon.py` |

**분량 기준 (분당 270자):**
| 분량 | 최소 | 목표 | 최대 |
|------|------|------|------|
| 10분 | 2,430자 | 2,700자 | 2,970자 |
| 15분 | 3,645자 | 4,050자 | 4,455자 |
| 20분 | 4,860자 | 5,400자 | 5,940자 |
| 25분 | 6,075자 | 6,750자 | 7,425자 |
| 30분 | 7,290자 | 8,100자 | 8,910자 |

---

### 4. 묵상 에이전트 (Meditation Agent)
| 항목 | 내용 |
|------|------|
| **역할** | 묵상 메시지 생성 |
| **입력** | 설교문 또는 성경 구절 |
| **출력** | 짧은 묵상 글 |
| **API** | `POST /api/sermon/meditation` |
| **모듈** | `sermon_modules/api_sermon.py` |

---

### 5. QA 에이전트 (Q&A Agent)
| 항목 | 내용 |
|------|------|
| **역할** | 설교 관련 질의응답 |
| **입력** | 질문, 설교 컨텍스트 |
| **출력** | 답변 |
| **API** | `POST /api/sermon/qa` |
| **모듈** | `sermon_modules/api_sermon.py` |

---

### 6. 디자인 에이전트 (Design Agent)
| 항목 | 내용 |
|------|------|
| **역할** | 배너, PPT, 말씀카드 생성 |
| **입력** | 설교 제목, 핵심 구절, 스타일 |
| **출력** | 이미지 파일 |
| **API** | `POST /api/banner/generate*` |
| **모듈** | `sermon_modules/api_banner.py` |

---

## 핵심 모듈 구조

```
sermon_modules/
├── __init__.py              # 패키지 초기화, 모든 모듈 export
├── api_sermon.py            # 설교 API (Step1, Step2, Step3, 묵상, QA)
├── api_banner.py            # 배너/디자인 API
├── api_admin.py             # 관리자 API
├── step3_prompt_builder.py  # 프롬프트 빌더
├── db.py                    # DB 연결 (PostgreSQL/SQLite)
├── auth.py                  # 인증, 크레딧
├── utils.py                 # 유틸리티
├── bible.py                 # 성경 본문 검색 (개역개정)
├── strongs.py               # Strong's 원어 분석
├── commentary.py            # 주석 생성
├── context.py               # 시대 컨텍스트, 예화 검증
├── sermon_config.py         # 설정
└── styles/                  # 설교 스타일별 지침
    ├── __init__.py
    ├── expository.py        # 강해설교
    ├── three_points.py      # 3대지 설교
    └── topical.py           # 주제설교
```

---

## 설교 스타일

| 스타일 ID | 이름 | 설명 |
|-----------|------|------|
| expository | 강해설교 | 본문 순서대로 해설 |
| three_points | 3대지 설교 | 3개 대지로 구성 |
| topical | 주제설교 | 특정 주제 중심 |

---

## 표준 워크플로우

### 기본 설교 작성 플로우
```
1. [분석Agent] Step1 실행
   └─ 입력: 성경 구절, 스타일, 카테고리
   └─ 출력: 본문 분석 결과 (JSON)

2. [구조Agent] Step2 실행
   └─ 입력: Step1 결과
   └─ 출력: 설교 구조 (대지, 소대지, 예화)

3. [작성Agent] Step3 실행
   └─ 입력: Step1 + Step2 결과, 분량
   └─ 출력: 완성된 설교문

4. [품질검수] 글자 수 및 구조 검증
   └─ 미달 시: Step3 재실행 또는 보완 지시
```

### 묵상 메시지 플로우
```
1. [묵상Agent] 묵상 생성
   └─ 입력: 설교문 또는 성경 구절
   └─ 출력: 묵상 메시지
```

### 디자인 플로우
```
1. [디자인Agent] 배너 생성
   └─ 입력: 제목, 구절, 스타일
   └─ 출력: 이미지 파일
```

---

## 슈퍼바이저 권한

### 1. 작업 분배
- 사용자 요청 분석 후 적절한 하위 에이전트 선택
- 실행 순서 결정 (순차/병렬)

### 2. 품질 검수
- 각 단계 결과 검토
- 기준 미달 시 재작업 지시
- 글자 수, 구조, 신학적 정확성 검증

### 3. 상태 관리
- 전체 워크플로우 진행 상황 추적
- 에러 발생 시 복구 처리
- 사용자에게 진행 상황 보고

### 4. 최적화
- 캐싱: 동일 요청 재사용
- 병렬 처리: 독립 작업 동시 실행
- 비용 관리: API 호출 최소화

---

## API 엔드포인트 요약

| 엔드포인트 | 메서드 | 담당 에이전트 | 설명 |
|-----------|--------|--------------|------|
| `/api/sermon/process` | POST | 분석/구조 | Step1, Step2 처리 |
| `/api/sermon/gpt-pro` | POST | 작성 | Step3 (최종 설교문) |
| `/api/sermon/meditation` | POST | 묵상 | 묵상 메시지 생성 |
| `/api/sermon/qa` | POST | QA | 질의응답 |
| `/api/sermon/chat` | POST | 챗봇 | 대화형 상담 |
| `/api/sermon/recommend-scripture` | POST | 추천 | 본문 추천 |
| `/api/sermon/style-guide/<id>` | GET | - | 스타일 가이드 조회 |
| `/api/sermon/duration-info/<min>` | GET | - | 분량 정보 조회 |
| `/api/banner/generate*` | POST | 디자인 | 배너/이미지 생성 |

---

## 프론트엔드 모듈

| 파일 | 역할 |
|------|------|
| sermon-main.js | 전역 변수, 설정 |
| sermon-step.js | Step 처리 로직 |
| sermon-step4-copy.js | Step4 전체 복사 |
| sermon-render.js | UI 렌더링 |
| sermon-qa.js | Q&A, 챗봇 |
| sermon-meditation.js | 묵상 메시지 |
| sermon-design.js | 디자인 도우미 |
| sermon-admin.js | 관리자 기능 |
| sermon-firebase.js | Firebase 연동 |
| sermon-utils.js | 유틸리티 |
| sermon-init.js | 앱 초기화 |

---

## 슈퍼바이저 명령어 예시

```
# 기본 설교 작성
"마가복음 10:17-31로 25분 강해설교 만들어줘"
→ Step1 → Step2 → Step3 순차 실행

# 묵상 추가
"이 설교로 묵상 메시지도 만들어줘"
→ 묵상Agent 실행

# 디자인 추가
"배너 이미지도 만들어줘"
→ 디자인Agent 실행

# 전체 패키지
"마가복음 10장으로 20분 설교 + 묵상 + 배너 전부 만들어줘"
→ Step1 → Step2 → Step3 → 묵상Agent → 디자인Agent
```

---

## 에이전트 요약

### 개발 에이전트 (1순위 + 2순위 + 3순위)
| 에이전트 | 역할 | 팀 |
|---------|------|-----|
| **AnalyzerAgent** | 프롬프트 분석/최적화 | 1순위 |
| **WriterAgent** | 설교문 품질 검증 | 1순위 |
| **TestAgent** | 테스트/검증 | 1순위 |
| **UIAgent** | 프론트엔드 수정 | 2순위 |
| **APIAgent** | 백엔드 수정 | 2순위 |
| **DocAgent** | 문서화 | 2순위 |
| **MonitorAgent** | 프로덕션 모니터링, 에러 감지 | 3순위 |
| **CacheAgent** | 결과 캐싱, 비용 절감 | 3순위 |
| **BenchmarkAgent** | 품질 평가, A/B 테스트 | 3순위 |

### 서비스 에이전트 (런타임)
| 에이전트 | 역할 |
|---------|------|
| Step1 Agent | 본문 분석 |
| Step2 Agent | 구조 설계 |
| Step3 Agent | 설교문 작성 |
| Meditation Agent | 묵상 메시지 |
| QA Agent | 질의응답 |
| Design Agent | 디자인 생성 |

---

*마지막 업데이트: 2025-12-25*
