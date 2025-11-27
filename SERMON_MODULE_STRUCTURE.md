# Sermon 모듈화 구조 설계

## 작업 완료 현황

### 원본 파일 크기
```
templates/sermon.html     (266KB, 6,836줄) → (현재: ~35KB, 1,063줄)
sermon_server.py          (154KB, 3,929줄) → (변경 없음, Blueprint 분리 예정)
```

---

## 1. CSS 분리 ✅ 완료
```
static/css/sermon.css     - 모든 스타일 (916줄)
```

---

## 2. JavaScript 모듈 분리 ✅ 완료

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
| sermon-init.js | 앱 초기화, 이벤트 바인딩 | ✅ |

### 모듈 로딩 순서
```html
<!-- 1. Firebase SDK -->
<script src="https://www.gstatic.com/firebasejs/9.22.1/firebase-app-compat.js"></script>
<script src="https://www.gstatic.com/firebasejs/9.22.1/firebase-firestore-compat.js"></script>

<!-- 2. Sermon JS Modules -->
<script src="sermon-utils.js"></script>
<script src="sermon-firebase.js"></script>
<script src="sermon-main.js"></script>
<script src="sermon-render.js"></script>
<script src="sermon-step.js"></script>
<script src="sermon-gpt-pro.js"></script>
<script src="sermon-admin.js"></script>
<script src="sermon-qa.js"></script>
<script src="sermon-meditation.js"></script>
<script src="sermon-design.js"></script>
<script src="sermon-init.js"></script>
```

### 전역 노출 패턴
모든 모듈은 `window.함수명 = 함수명;` 패턴으로 전역에 노출

---

## 3. HTML 경량화 ✅ 완료

### 변경 사항
- 인라인 CSS 제거 → 외부 CSS 링크
- 인라인 JavaScript 제거 (약 4,850줄) → 11개 외부 모듈
- 파일 크기: 6,836줄 → 1,063줄 (84% 감소)

### 현재 sermon.html 구조
```html
<!DOCTYPE html>
<html lang="ko">
<head>
  <meta charset="UTF-8" />
  <title>BIBLE LAB</title>
  <link rel="stylesheet" href="sermon.css">
</head>
<body>
  <!-- HTML 마크업만 (약 1,000줄) -->

  <!-- Scripts -->
  <script src="firebase-app-compat.js"></script>
  <script src="firebase-firestore-compat.js"></script>
  <script src="sermon-utils.js"></script>
  <!-- ... 11개 모듈 ... -->
  <script src="sermon-init.js"></script>
</body>
</html>
```

---

## 4. Python 백엔드 모듈 분리 (진행 중)

### 생성된 파일
```
sermon_modules/
├── __init__.py          ✅ Blueprint 기본 구조
└── db.py                ✅ 데이터베이스 연결 및 초기화
```

### 예정된 모듈
| 파일 | 주요 기능 | 상태 |
|------|----------|------|
| sermon_modules/auth.py | 인증, 크레딧 관리 | 📋 예정 |
| sermon_modules/step.py | /api/sermon/process | 📋 예정 |
| sermon_modules/gpt_pro.py | /api/sermon/gpt-pro | 📋 예정 |
| sermon_modules/prompt.py | 프롬프트 빌더 | 📋 예정 |
| sermon_modules/qa.py | Q&A, 본문 추천 API | 📋 예정 |
| sermon_modules/meditation.py | 묵상메시지 API | 📋 예정 |
| sermon_modules/banner.py | 배너/현수막 API | 📋 예정 |
| sermon_modules/benchmark.py | 벤치마크 분석 | 📋 예정 |
| sermon_modules/chat.py | AI 챗봇 API | 📋 예정 |

> Python 모듈화는 Flask Blueprint 리팩토링이 필요하며, 별도 작업으로 진행 예정

---

## 파일 위치

```
my_page_v2/
├── static/
│   ├── css/
│   │   └── sermon.css              ✅ 생성됨 (916줄)
│   └── js/
│       ├── sermon-utils.js         ✅ 생성됨
│       ├── sermon-firebase.js      ✅ 생성됨
│       ├── sermon-main.js          ✅ 생성됨
│       ├── sermon-render.js        ✅ 생성됨
│       ├── sermon-step.js          ✅ 생성됨
│       ├── sermon-gpt-pro.js       ✅ 생성됨
│       ├── sermon-admin.js         ✅ 생성됨
│       ├── sermon-qa.js            ✅ 생성됨
│       ├── sermon-meditation.js    ✅ 생성됨
│       ├── sermon-design.js        ✅ 생성됨
│       └── sermon-init.js          ✅ 생성됨
├── sermon_modules/
│   ├── __init__.py                 ✅ 생성됨
│   └── db.py                       ✅ 생성됨
├── templates/
│   └── sermon.html                 ✅ 경량화됨 (1,063줄)
├── sermon_server.py                (변경 없음)
└── SERMON_MODULE_STRUCTURE.md      ✅ 이 문서
```

---

## 파일 크기 비교

| 파일 | 이전 | 이후 | 감소율 |
|------|------|------|--------|
| sermon.html | 266KB (6,836줄) | ~35KB (1,063줄) | 84% |
| 인라인 JS | ~5,000줄 | 0줄 | 100% |
| 인라인 CSS | ~920줄 | 0줄 | 100% |

### 새로 생성된 파일
| 파일 | 크기 |
|------|------|
| sermon.css | ~25KB |
| sermon-*.js (11개) | ~80KB 총합 |
| sermon_modules/*.py (2개) | ~15KB |

---

## 주의사항

1. **전역 변수**: `window.*` 객체로 노출되므로 이름 충돌 주의
2. **로딩 순서**: 의존성 순서대로 로드 필수
3. **캐시 무효화**: 배포 시 `?v=버전` 쿼리스트링 추가 권장
4. **Python Blueprint**: 아직 메인 서버에 통합되지 않음
