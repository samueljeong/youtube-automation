# Sermon 모듈화 구조 설계

## 작업 완료 현황

### 원본 파일 크기
```
templates/sermon.html     (266KB, 6,836줄) → (현재: ~35KB, 1,063줄) ✅ 84% 감소
sermon_server.py          (154KB, 3,929줄) → (모듈 분리 준비 완료)
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
| sermon-utils.js | 유틸리티 함수 | ✅ |
| sermon-firebase.js | Firebase 연동 | ✅ |
| sermon-main.js | 전역 변수, 설정 | ✅ |
| sermon-render.js | UI 렌더링 | ✅ |
| sermon-step.js | Step 처리 | ✅ |
| sermon-gpt-pro.js | GPT PRO 처리 | ✅ |
| sermon-admin.js | 관리자 기능 | ✅ |
| sermon-qa.js | Q&A, 챗봇 | ✅ |
| sermon-meditation.js | 묵상메시지 | ✅ |
| sermon-design.js | 디자인 도우미 | ✅ |
| sermon-init.js | 앱 초기화 | ✅ |

---

## 3. HTML 경량화 ✅ 완료

- 인라인 CSS 제거 → 외부 CSS 링크
- 인라인 JavaScript 제거 (약 4,850줄) → 11개 외부 모듈
- **파일 크기: 6,836줄 → 1,063줄 (84% 감소)**

---

## 4. Python 백엔드 모듈 분리 ✅ 기본 구조 완료

### 생성된 파일
```
sermon_modules/
├── __init__.py          ✅ 패키지 초기화, 모든 모듈 export
├── db.py                ✅ 데이터베이스 연결 및 초기화 (280줄)
├── utils.py             ✅ 유틸리티 함수 (100줄)
├── auth.py              ✅ 인증, 크레딧, 데코레이터 (250줄)
└── prompt.py            ✅ 프롬프트 빌더 (230줄)
```

### 모듈 상세

#### db.py
- `get_db_connection()` - PostgreSQL/SQLite 연결
- `init_db()` - 테이블 초기화
- `get_setting()`, `set_setting()` - 설정 관리

#### utils.py
- `calculate_cost()` - API 비용 계산
- `format_json_result()` - JSON 포맷팅
- `remove_markdown()` - 마크다운 제거
- `is_json_guide()`, `parse_json_guide()` - JSON 지침 파싱

#### auth.py
- `login_required`, `admin_required`, `api_login_required` - 데코레이터
- `get_user_credits()`, `use_credit()`, `add_credits()`, `set_credits()` - 크레딧 관리
- `auth_bp` - Flask Blueprint (회원가입, 로그인, 로그아웃)

#### prompt.py
- `get_system_prompt_for_step()` - 단계별 시스템 프롬프트
- `build_prompt_from_json()` - JSON 지침 기반 프롬프트 생성
- `build_step3_prompt_from_json()` - Step3 전용 프롬프트

### 사용법
```python
# sermon_server.py에서 모듈 import
from sermon_modules import (
    get_db_connection, init_db,
    calculate_cost, format_json_result,
    login_required, api_login_required,
    build_prompt_from_json
)

# 또는 개별 모듈에서
from sermon_modules.db import get_db_connection
from sermon_modules.auth import login_required
from sermon_modules.prompt import build_step3_prompt_from_json
```

### API 라우트 분리 (예정)
```
sermon_modules/
├── api_sermon.py        📋 설교 처리 API (/api/sermon/*)
├── api_banner.py        📋 배너 API (/api/banner/*)
└── api_admin.py         📋 관리자 API (/admin/*)
```

> 전체 API 라우트 분리는 별도 작업으로 진행 예정
> 현재 sermon_server.py는 모듈을 import하여 점진적 교체 가능

---

## 파일 위치

```
my_page_v2/
├── static/
│   ├── css/
│   │   └── sermon.css              ✅ (916줄)
│   └── js/
│       ├── sermon-utils.js         ✅
│       ├── sermon-firebase.js      ✅
│       ├── sermon-main.js          ✅
│       ├── sermon-render.js        ✅
│       ├── sermon-step.js          ✅
│       ├── sermon-gpt-pro.js       ✅
│       ├── sermon-admin.js         ✅
│       ├── sermon-qa.js            ✅
│       ├── sermon-meditation.js    ✅
│       ├── sermon-design.js        ✅
│       └── sermon-init.js          ✅
├── sermon_modules/
│   ├── __init__.py                 ✅
│   ├── db.py                       ✅
│   ├── utils.py                    ✅
│   ├── auth.py                     ✅
│   └── prompt.py                   ✅
├── templates/
│   └── sermon.html                 ✅ (1,063줄)
├── sermon_server.py                (원본 유지, 모듈 import 가능)
└── SERMON_MODULE_STRUCTURE.md      ✅ 이 문서
```

---

## 파일 크기 비교

| 항목 | 이전 | 이후 | 변화 |
|------|------|------|------|
| sermon.html | 6,836줄 | 1,063줄 | -84% |
| 인라인 JS | ~5,000줄 | 0줄 | -100% |
| 인라인 CSS | ~920줄 | 0줄 | -100% |

### 새로 생성된 파일
| 파일 | 줄 수 |
|------|-------|
| sermon.css | 916줄 |
| sermon-*.js (11개) | ~2,500줄 |
| sermon_modules/*.py (4개) | ~860줄 |

---

## 다음 단계

1. **sermon_server.py 점진적 교체**
   - 기존 함수를 모듈 import로 교체
   - API Blueprint 분리

2. **테스트**
   - 모듈 import 확인
   - 기능 동작 테스트

---

## 주의사항

1. **JS 전역 변수**: `window.*` 노출로 호환성 유지
2. **로딩 순서**: 의존성 순서대로 로드 필수
3. **Python import**: 순환 import 주의
4. **캐시 무효화**: 배포 시 버전 쿼리스트링 추가
