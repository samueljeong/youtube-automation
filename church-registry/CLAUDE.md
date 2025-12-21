# 교적 관리 시스템 (Church Registry)

## 프로젝트 개요

교회에서 사용할 교인 관리 시스템입니다.

---

## 기술 스택

- **백엔드**: Flask (Python)
- **데이터베이스**: SQLite (개발) → PostgreSQL (프로덕션)
- **프론트엔드**: Bootstrap 5, Jinja2 템플릿
- **배포**: Render

---

## 프로젝트 구조

```
church-registry/
├── app.py              # 메인 Flask 앱
├── requirements.txt    # 의존성
├── CLAUDE.md           # 프로젝트 지침 (이 파일)
├── WORK_LOG.md         # 작업 기록
├── templates/          # HTML 템플릿
│   ├── base.html
│   ├── index.html
│   └── members/
│       └── list.html
├── static/             # 정적 파일
│   ├── css/
│   └── js/
├── models/             # DB 모델 (추후 분리)
└── routes/             # 라우트 (추후 분리)
```

---

## 데이터베이스 모델

### Member (교인)
| 필드 | 타입 | 설명 |
|------|------|------|
| id | Integer | PK |
| name | String | 이름 |
| phone | String | 전화번호 |
| email | String | 이메일 |
| address | String | 주소 |
| birth_date | Date | 생년월일 |
| gender | String | 성별 |
| baptism_date | Date | 세례일 |
| registration_date | Date | 등록일 |
| group_id | FK | 소속 그룹 |
| family_id | FK | 가족 |
| family_role | String | 가족 내 역할 |
| status | String | 상태 (active/inactive/newcomer) |
| notes | Text | 메모 |

### Family (가족)
| 필드 | 타입 | 설명 |
|------|------|------|
| id | Integer | PK |
| family_name | String | 가족명 |

### Group (셀/구역/목장)
| 필드 | 타입 | 설명 |
|------|------|------|
| id | Integer | PK |
| name | String | 그룹명 |
| group_type | String | 유형 (cell/district/mokjang) |
| leader_id | Integer | 리더 교인 ID |

### Attendance (출석)
| 필드 | 타입 | 설명 |
|------|------|------|
| id | Integer | PK |
| member_id | FK | 교인 |
| date | Date | 날짜 |
| service_type | String | 예배 종류 |
| attended | Boolean | 출석 여부 |

### Visit (심방)
| 필드 | 타입 | 설명 |
|------|------|------|
| id | Integer | PK |
| member_id | FK | 교인 |
| visit_date | Date | 심방일 |
| visitor_name | String | 심방자 |
| purpose | String | 목적 |
| notes | Text | 내용 |

### Offering (헌금)
| 필드 | 타입 | 설명 |
|------|------|------|
| id | Integer | PK |
| member_id | FK | 교인 |
| date | Date | 날짜 |
| amount | Integer | 금액 |
| offering_type | String | 유형 (십일조/감사헌금 등) |

---

## API 엔드포인트

### 기본
- `GET /` - 대시보드
- `GET /health` - 헬스 체크

### 교인 관리
- `GET /members` - 교인 목록
- `GET /members/<id>` - 교인 상세
- `POST /members` - 교인 등록
- `PUT /members/<id>` - 교인 수정
- `DELETE /members/<id>` - 교인 삭제

### 출석 관리 (예정)
- `GET /attendance` - 출석 현황
- `POST /attendance` - 출석 체크

### 엑셀 (예정)
- `GET /export/members` - 교인 목록 내보내기
- `POST /import/members` - 교인 목록 가져오기

---

## 환경변수

| 변수명 | 필수 | 설명 | 기본값 |
|--------|------|------|--------|
| SECRET_KEY | O | Flask 비밀키 | dev-secret-key |
| DATABASE_URL | O | DB 연결 URL | sqlite:///church.db |

---

## 개발 가이드

### 로컬 실행
```bash
pip install -r requirements.txt
python app.py
```

### Render 배포
1. GitHub에 push
2. Render에서 Web Service 생성
3. 환경변수 설정
4. 배포

---

## 작업 기록

작업 완료 시 `WORK_LOG.md`에 기록할 것.
