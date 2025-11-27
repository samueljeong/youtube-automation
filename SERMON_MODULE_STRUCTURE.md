# Sermon 모듈화 구조 설계

## 현재 상태
```
templates/sermon.html     (266KB, 6,819줄)
sermon_server.py          (154KB, 3,929줄)
```

## 목표 구조

### 1. CSS 분리 ✅ 완료
```
static/css/sermon.css     - 모든 스타일 (916줄)
```

### 2. JavaScript 모듈 분리

#### 2.1 sermon-main.js (전역 변수, 초기화)
- 줄 범위: 1987~2060
- 내용:
  - 전역 변수 (guideUnlocked, currentCategory, stepResults 등)
  - 기본 config 설정
  - 초기화 함수

#### 2.2 sermon-firebase.js (Firebase, 저장/로드)
- 줄 범위: 1966~1986, 2361~2680
- 내용:
  - Firebase 초기화
  - loadFromFirebase(), saveToFirebase()
  - 자동 저장 (autoSaveStepResults)
  - 실시간 동기화 (setupRealtimeSync)
  - 백업/복원 (exportBackup, importBackup)

#### 2.3 sermon-utils.js (유틸리티 함수)
- 줄 범위: 2060~2360
- 내용:
  - koreanToId(), generateCategoryId()
  - showStatus(), hideStatus()
  - showGptLoading(), hideGptLoading()
  - calculateCost()
  - autoResize()

#### 2.4 sermon-step.js (Step1/Step2/Step3 처리)
- 줄 범위: 4166~4356
- 내용:
  - executeStep()
  - Step 관련 헬퍼 함수

#### 2.5 sermon-gpt-pro.js (GPT PRO 처리)
- 줄 범위: 3137~3589
- 내용:
  - assembleGptProDraft()
  - executeGptPro()
  - 전체 복사 기능

#### 2.6 sermon-render.js (UI 렌더링)
- 줄 범위: 3589~4166
- 내용:
  - renderCategories()
  - switchCategoryContent()
  - renderStyles()
  - renderProcessingSteps()
  - renderResultBoxes()
  - updateAnalysisUI()

#### 2.7 sermon-admin.js (관리자 기능)
- 줄 범위: 4793~5350
- 내용:
  - 카테고리 관리 (renderCategoryManageList)
  - 스타일 관리 (renderStylesManageList)
  - 스텝 관리 (renderStepsManageList)
  - 지침 관리 (loadGuide, saveGuide)

#### 2.8 sermon-qa.js (Q&A, 챗봇)
- 줄 범위: 5461~6018, 5891~6018
- 내용:
  - Q&A 기능 (sendQAQuestion)
  - AI 챗봇 (sendSermonChatMessage)
  - 본문 추천 (searchScripture)

#### 2.9 sermon-meditation.js (묵상메시지)
- 줄 범위: 4356~4573
- 내용:
  - 묵상메시지 생성 기능
  - initMeditationDate()
  - saveMeditationTemplate()

#### 2.10 sermon-design.js (디자인 도우미)
- 줄 범위: 6265~6817
- 내용:
  - 현수막/배너 생성
  - generateBanner()
  - 참조 이미지 관리
  - 크롤링 기능

#### 2.11 sermon-code.js (Step3 코드 관리)
- 줄 범위: 5602~5891
- 내용:
  - loadStep3Codes()
  - validateAndUseCode()
  - 코드 생성/삭제

---

### 3. Python 백엔드 모듈 분리

#### 3.1 sermon_server.py (메인 라우터) - 경량화
- 라우트 등록
- Blueprint import
- 앱 초기화

#### 3.2 sermon_db.py (DB 설정)
- 줄 범위: 33~460
- 내용:
  - DB 연결 (PostgreSQL/SQLite)
  - init_db()
  - 테이블 생성

#### 3.3 sermon_auth.py (인증/크레딧)
- 줄 범위: 615~1240
- 내용:
  - login_required, admin_required
  - signup, login, logout
  - 크레딧 관리 API

#### 3.4 sermon_step.py (Step 처리 API)
- 줄 범위: 1706~1924
- 내용:
  - /api/sermon/process

#### 3.5 sermon_gpt_pro.py (GPT PRO API)
- 줄 범위: 2025~2366
- 내용:
  - /api/sermon/gpt-pro

#### 3.6 sermon_prompt.py (프롬프트 빌더)
- 줄 범위: 1244~1685
- 내용:
  - is_json_guide()
  - parse_json_guide()
  - build_prompt_from_json()
  - build_step3_prompt_from_json()

#### 3.7 sermon_qa.py (Q&A API)
- 줄 범위: 2366~2534
- 내용:
  - /api/sermon/qa
  - /api/sermon/recommend-scripture

#### 3.8 sermon_meditation.py (묵상메시지 API)
- 줄 범위: 1925~2025
- 내용:
  - /api/sermon/meditation

#### 3.9 sermon_banner.py (배너 API)
- 줄 범위: 2936~3910
- 내용:
  - /api/banner/* 모든 엔드포인트
  - 이미지 생성, 텍스트 오버레이
  - 크롤링

#### 3.10 sermon_benchmark.py (벤치마크)
- 줄 범위: 2534~2830
- 내용:
  - analyze_sermon_for_benchmark()
  - save_step1_analysis()

#### 3.11 sermon_chat.py (AI 챗봇 API)
- 줄 범위: 2829~2936
- 내용:
  - /api/sermon/chat

---

### 4. HTML 컴포넌트 분리 (선택사항)

```
templates/sermon/
├── header.html        - Auth 헤더
├── left-panel.html    - 왼쪽 패널 (입력, 스타일)
├── middle-panel.html  - 중앙 패널 (결과)
├── right-panel.html   - 오른쪽 패널 (관리자)
├── modals.html        - 모달들
└── design-helper.html - 디자인 도우미
```

---

## 마이그레이션 순서

### Phase 1: CSS 분리 ✅
1. ✅ static/css/sermon.css 생성
2. sermon.html에서 `<link rel="stylesheet">` 추가

### Phase 2: JS 모듈 분리
1. sermon-utils.js 생성 (의존성 없음)
2. sermon-firebase.js 생성
3. sermon-main.js 생성 (위 두 개 import)
4. 나머지 모듈 순차 생성
5. sermon.html에서 `<script src="">` 추가

### Phase 3: Python 모듈 분리
1. sermon_prompt.py 분리 (의존성 없음)
2. sermon_db.py 분리
3. 나머지 모듈 순차 분리
4. sermon_server.py에서 import

### Phase 4: 테스트 & 최적화
1. 각 모듈 동작 테스트
2. 로딩 순서 최적화
3. 캐싱 설정

---

## 파일 크기 예상

| 파일 | 예상 크기 |
|------|----------|
| sermon.html (경량화 후) | ~50KB |
| sermon.css | ~25KB |
| sermon-*.js (총합) | ~120KB |
| sermon_server.py (경량화 후) | ~20KB |
| sermon_*.py (총합) | ~130KB |

---

## 주의사항

1. **전역 변수 관리**: 모듈 간 공유되는 전역 변수는 sermon-main.js에서 window 객체에 할당
2. **로딩 순서**: utils → firebase → main → 나머지
3. **Flask Blueprint**: Python 모듈 분리 시 Blueprint 사용 권장
4. **캐시 무효화**: 배포 시 버전 쿼리스트링 추가 (`?v=1.0`)
