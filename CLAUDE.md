# YouTube 영상 자동화 시스템

## 프로젝트 개요

Google Sheets 기반 YouTube 영상 자동 생성 시스템

**호스팅**: Render (https://drama-s2ns.onrender.com)

---

## 🔒 코드 리뷰 워크플로우 (필수)

```
╔════════════════════════════════════════════════════════════════╗
║  코드 작성 후 바로 커밋 금지!                                    ║
║  반드시 코드 리뷰 에이전트의 승인을 받은 후에만 커밋한다.          ║
╚════════════════════════════════════════════════════════════════╝
```

### 워크플로우
```
코드 작성 → 코드 리뷰 에이전트 (검증/승인) → 커밋
              ↓ 수정 필요 시
           피드백 반영 → 재검토
```

### 코드 리뷰 호출 방법
```python
Task(
    subagent_type="general-purpose",
    prompt="""
    docs/CODE_REVIEW_AGENT.md 지침에 따라 검토해주세요.
    검토 대상 파일: [수정한 파일 경로들]
    결과: 승인/수정필요/거부 중 하나로 판정
    """
)
```

### 리뷰 결과 행동
| 결과 | 행동 |
|------|------|
| ✅ 승인 | 커밋 진행 |
| ⚠️ 수정 필요 | 피드백 반영 후 재검토 |
| ❌ 거부 | 재작성 후 재검토 |

📄 상세 지침: `docs/CODE_REVIEW_AGENT.md`

---

## 🤖 Claude 슈퍼바이저 역할 (필수)

### 커밋 전 필수 체크리스트

| 체크 | 항목 |
|:---:|------|
| ☐ | 함수 호출 체인 추적 (A→B→C 전제조건 확인) |
| ☐ | 전역 변수 의존성 확인 |
| ☐ | 에러 경로 확인 |
| ☐ | 이벤트 바인딩 확인 |
| ☐ | 데이터 형식 호환성 확인 |

### 검증 방법
1. 호출되는 함수 읽기
2. 필수 변수 역추적
3. UI 흐름 시뮬레이션

**브라우저 테스트 없이도 코드 분석으로 잡을 수 있는 버그는 커밋 전에 잡는다!**

---

## [필수] 세션 시작 시 확인할 로그 파일

| 파일 | 목적 |
|------|------|
| `docs/SERMON_CHANGELOG.md` | Sermon 페이지 작업 로그 |
| `docs/BUGFIX_CHANGELOG.md` | 버그 수정 이력 |

작업 완료 후 해당 로그 파일에 기록 (날짜, 문제, 수정 내용, 커밋 해시)

---

## 📚 문서 링크

### 핵심 문서
| 문서 | 설명 |
|------|------|
| [docs/CODE_REVIEW_AGENT.md](docs/CODE_REVIEW_AGENT.md) | 코드 리뷰 에이전트 상세 지침 |
| [docs/PIPELINE_FLOW.md](docs/PIPELINE_FLOW.md) | 자동화 파이프라인 흐름 |
| [docs/API_REFERENCE.md](docs/API_REFERENCE.md) | API, 타임아웃, 환경변수, 비용 |

### 구조 문서
| 문서 | 설명 |
|------|------|
| [docs/SHEETS_STRUCTURE.md](docs/SHEETS_STRUCTURE.md) | Google Sheets 구조 |
| [docs/VIDEO_EFFECTS.md](docs/VIDEO_EFFECTS.md) | video_effects 구조 |
| [docs/TTS_GUIDE.md](docs/TTS_GUIDE.md) | TTS 음성 설정 |
| [docs/AI_TOOLS.md](docs/AI_TOOLS.md) | Claude 보조 도구 (AI Tools) |

### 파이프라인별 문서
| 문서 | 설명 |
|------|------|
| [docs/pipelines/NEWS.md](docs/pipelines/NEWS.md) | 뉴스 자동화 파이프라인 |
| [docs/pipelines/BIBLE.md](docs/pipelines/BIBLE.md) | 성경통독 파이프라인 |
| [docs/pipelines/SHORTS.md](docs/pipelines/SHORTS.md) | 쇼츠 바이럴 파이프라인 |

### 변경 이력
| 문서 | 설명 |
|------|------|
| [docs/BUGFIX_CHANGELOG.md](docs/BUGFIX_CHANGELOG.md) | 버그 수정 이력 |
| [docs/SERMON_CHANGELOG.md](docs/SERMON_CHANGELOG.md) | Sermon 페이지 변경 이력 |

---

## 주요 파일 구조

```
drama_server.py          # 메인 서버 (모든 API)
scripts/
├── history_pipeline/    # 한국사 파이프라인
├── isekai_pipeline/     # 이세계 파이프라인
├── shorts_pipeline/     # 쇼츠 파이프라인
├── bible_pipeline/      # 성경통독 파이프라인
├── news_pipeline/       # 뉴스 파이프라인
├── mystery_pipeline/    # 미스터리 파이프라인
├── wuxia_pipeline/      # 무협지 파이프라인
└── migrations/          # DB 마이그레이션 스크립트
```
