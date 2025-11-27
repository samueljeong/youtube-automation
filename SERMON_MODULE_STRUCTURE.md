# Sermon 모듈화 구조 설계

## 현재 상태
```
templates/sermon.html     (266KB, 6,819줄)
sermon_server.py          (154KB, 3,929줄)
```

## 작업 완료 현황

### 1. CSS 분리 ✅ 완료
```
static/css/sermon.css     - 모든 스타일 (916줄)
```

### 2. JavaScript 모듈 분리 ✅ 완료

| 파일 | 주요 기능 | 상태 |
|------|----------|------|
| sermon-utils.js | 유틸리티 함수 (koreanToId, showStatus, calculateCost 등) | ✅ |
| sermon-firebase.js | Firebase 초기화, 저장/로드, 실시간 동기화, 백업/복원 | ✅ |
| sermon-main.js | 전역 변수, 기본 설정, 모델 설정, 스타일 토큰 관리 | ✅ |
| sermon-render.js | UI 렌더링 (카테고리, 스타일, 처리 단계, 결과 박스) | ✅ |
| sermon-step.js | Step1/Step2/Step3 처리, executeStep() | ✅ |
| sermon-gpt-pro.js | GPT PRO 처리, 결과 조합, 복사 기능 | ✅ |
| sermon-admin.js | 관리자 기능 (카테고리/스타일/지침 관리) | ✅ |
| sermon-qa.js | Q&A, 챗봇, 본문 추천, Step3 코드 관리 | ✅ |
| sermon-meditation.js | 묵상메시지 생성 기능 | ✅ |
| sermon-design.js | 디자인 도우미, 배너 생성, 참조 이미지, 크롤링 | ✅ |

#### 모듈 로딩 순서 (의존성 고려)
```html
<!-- 1. 유틸리티 (의존성 없음) -->
<script src="sermon-utils.js"></script>

<!-- 2. Firebase (Firebase SDK 필요) -->
<script src="sermon-firebase.js"></script>

<!-- 3. 메인 설정 (utils, firebase 필요) -->
<script src="sermon-main.js"></script>

<!-- 4. 렌더링 (main 필요) -->
<script src="sermon-render.js"></script>

<!-- 5. 기능 모듈 (순서 무관) -->
<script src="sermon-step.js"></script>
<script src="sermon-gpt-pro.js"></script>
<script src="sermon-admin.js"></script>
<script src="sermon-qa.js"></script>
<script src="sermon-meditation.js"></script>
<script src="sermon-design.js"></script>
```

#### 전역 노출 패턴
모든 모듈은 `window.함수명 = 함수명;` 패턴으로 전역에 노출하여
기존 인라인 코드와 호환성을 유지합니다.

---

### 3. Python 백엔드 모듈 분리 (예정)

> Flask Blueprint를 사용한 모듈 분리는 추후 작업 예정입니다.

| 파일 | 주요 기능 | 상태 |
|------|----------|------|
| sermon_db.py | DB 연결, 테이블 생성 | 📋 |
| sermon_auth.py | 인증, 크레딧 관리 | 📋 |
| sermon_step.py | /api/sermon/process | 📋 |
| sermon_gpt_pro.py | /api/sermon/gpt-pro | 📋 |
| sermon_prompt.py | 프롬프트 빌더 | 📋 |
| sermon_qa.py | Q&A, 본문 추천 API | 📋 |
| sermon_meditation.py | 묵상메시지 API | 📋 |
| sermon_banner.py | 배너/현수막 API | 📋 |
| sermon_benchmark.py | 벤치마크 분석 | 📋 |
| sermon_chat.py | AI 챗봇 API | 📋 |

---

### 4. HTML 경량화 (진행 중)

현재 sermon.html에 모듈 스크립트 참조가 주석으로 추가되어 있습니다.
점진적 마이그레이션을 위해 인라인 코드와 병행 사용 가능합니다.

```html
<!-- 현재 상태: 주석 처리 (점진적 마이그레이션 시 활성화) -->
<!--
<script src="{{ url_for('static', filename='js/sermon-utils.js') }}"></script>
...
-->
```

---

## 파일 위치

```
my_page_v2/
├── static/
│   ├── css/
│   │   └── sermon.css          ✅ 생성됨
│   └── js/
│       ├── sermon-utils.js     ✅ 생성됨
│       ├── sermon-firebase.js  ✅ 생성됨
│       ├── sermon-main.js      ✅ 생성됨
│       ├── sermon-render.js    ✅ 생성됨
│       ├── sermon-step.js      ✅ 생성됨
│       ├── sermon-gpt-pro.js   ✅ 생성됨
│       ├── sermon-admin.js     ✅ 생성됨
│       ├── sermon-qa.js        ✅ 생성됨
│       ├── sermon-meditation.js ✅ 생성됨
│       └── sermon-design.js    ✅ 생성됨
├── templates/
│   └── sermon.html             (모듈 참조 추가됨)
├── sermon_server.py            (변경 없음)
└── SERMON_MODULE_STRUCTURE.md  ✅ 이 문서
```

---

## 마이그레이션 가이드

### 모듈 활성화 방법

1. sermon.html에서 주석 처리된 스크립트 태그 활성화
2. 해당 모듈의 인라인 코드 제거
3. 테스트 후 다음 모듈 진행

### 주의사항

1. **전역 변수**: `window.` 객체로 노출되므로 이름 충돌 주의
2. **로딩 순서**: 의존성 순서대로 로드해야 함
3. **캐시 무효화**: 배포 시 `?v=버전` 쿼리스트링 추가 권장
4. **점진적 마이그레이션**: 한 번에 하나의 모듈씩 이전 권장

---

## 예상 파일 크기

| 파일 | 현재 | 모듈화 후 |
|------|------|----------|
| sermon.html | 266KB | ~50KB (예상) |
| sermon-*.js (총합) | - | ~120KB |
| sermon.css | - | ~25KB |

총 로드 크기는 비슷하지만, 캐싱 효과로 재방문 시 로딩 속도 향상
