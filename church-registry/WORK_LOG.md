# 작업 기록 (Work Log)

교적 관리 시스템 개발 작업 기록입니다.

---

## 2024-12-21: 전체 기능 구현 완료

### 완료된 작업

1. **교인 관리 (CRUD)**
   - 교인 등록/수정/삭제/상세보기
   - 이름/상태/그룹별 검색 및 필터링
   - 템플릿: `members/list.html`, `members/form.html`, `members/detail.html`

2. **그룹 관리 (셀/구역/목장)**
   - 그룹 등록/수정/삭제/상세보기
   - 리더 지정 기능
   - 템플릿: `groups/list.html`, `groups/form.html`, `groups/detail.html`

3. **출석 체크**
   - 날짜/예배 종류별 출석 체크
   - 전체 선택/해제 기능
   - 출석 통계
   - 템플릿: `attendance/list.html`, `attendance/stats.html`

4. **심방 기록**
   - 심방 기록 등록/삭제
   - 교인별 심방 이력 조회
   - 템플릿: `visits/list.html`, `visits/form.html`

5. **헌금 기록**
   - 헌금 기록 등록/삭제
   - 월별 조회 및 합계
   - 헌금 종류별 분류 (십일조, 감사헌금 등)
   - 템플릿: `offerings/list.html`, `offerings/form.html`

6. **새신자 관리**
   - 새신자 목록 조회
   - 심방 바로가기 연동
   - 템플릿: `newcomers/list.html`

7. **생일 알림**
   - 이번 달 생일자 목록
   - 템플릿: `birthdays/list.html`

8. **엑셀 내보내기/가져오기**
   - 교인 목록 xlsx 내보내기
   - 교인 목록 xlsx 가져오기 (중복 체크)
   - 템플릿: `import/members.html`

---

## 기능 요구사항 체크리스트

- [x] 교인 등록/수정/삭제
- [x] 교인 검색
- [ ] 가족 관계 관리 (추후 구현)
- [x] 셀/구역/목장 그룹 관리
- [x] 출석 체크
- [x] 심방 기록
- [x] 헌금 기록
- [x] 새신자 관리
- [x] 생일/기념일 알림
- [x] 엑셀 내보내기/가져오기

---

## 2024-12-21: 프로젝트 초기 세팅

### 완료된 작업

1. **프로젝트 구조 생성**
   - Flask 프로젝트 기본 구조 세팅
   - 디렉토리: `templates/`, `static/`, `models/`, `routes/`

2. **데이터베이스 모델 설계**
   - `Member`: 교인 정보 (이름, 연락처, 주소, 생년월일, 세례일 등)
   - `Family`: 가족 그룹
   - `Group`: 셀/구역/목장 그룹
   - `Attendance`: 출석 기록
   - `Visit`: 심방 기록
   - `Offering`: 헌금 기록

3. **기본 UI 템플릿 생성**
   - `base.html`: 기본 레이아웃 (Bootstrap 5)
   - `index.html`: 대시보드 메인 페이지

4. **의존성 설정**
   - Flask, SQLAlchemy, Flask-Login, openpyxl 등

---

## 버그 수정 이력

(아직 없음)

---

## 참고사항

- Render 배포 예정
- SQLite → PostgreSQL 마이그레이션 계획
- 가족 관계 관리 기능은 추후 구현 예정
