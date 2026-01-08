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
| [docs/pipelines/BIBLE.md](docs/pipelines/BIBLE.md) | 성경통독 파이프라인 |

### 변경 이력
| 문서 | 설명 |
|------|------|
| [docs/BUGFIX_CHANGELOG.md](docs/BUGFIX_CHANGELOG.md) | 버그 수정 이력 |
| [docs/SERMON_CHANGELOG.md](docs/SERMON_CHANGELOG.md) | Sermon 페이지 변경 이력 |

---

## 주요 파일 구조

```
drama_server.py          # 메인 서버 (모든 API)
blueprints/              # Flask Blueprint 모듈
├── gpt.py               # GPT Chat API
├── ai_tools.py          # AI 도구 API
├── shorts.py            # Shorts Pipeline
├── isekai.py            # Isekai Pipeline
├── bible.py             # Bible Pipeline
├── history.py           # History Pipeline
└── tts.py               # TTS API
scripts/
├── common/              # 공통 모듈 (에이전트 기본 클래스, SRT 유틸리티)
├── history_pipeline/    # 한국사 파이프라인
├── isekai_pipeline/     # 이세계 파이프라인 (혈영 이세계편)
├── bible_pipeline/      # 성경통독 파이프라인
└── migrations/          # DB 마이그레이션 스크립트
```

---

## 🎯 자가 검증 방법 (Self-Verification)

작업 완료 후 반드시 아래 방법으로 검증:

### Python 문법 검사
```bash
python -m py_compile drama_server.py
python -m py_compile blueprints/*.py
```

### API 테스트
```bash
# 헬스체크
curl http://localhost:5000/health

# TTS 테스트
curl -X POST http://localhost:5000/api/drama/generate-tts \
  -H "Content-Type: application/json" \
  -d '{"text": "테스트", "speaker": "ko-KR-Neural2-C"}'
```

### 린터 실행
```bash
ruff check drama_server.py --fix
```

---

## ⚠️ 과거 실수 기록 (반복 금지)

| 날짜 | 실수 | 교훈 |
|------|------|------|
| 2025-12 | FFmpeg `capture_output=True` → OOM | `stdout=DEVNULL, stderr=PIPE` 사용 |
| 2025-12 | 함수 내부 import → 성능 저하 | 파일 상단에서 import |
| 2025-12 | 전역 변수 미확인 → 런타임 에러 | 의존성 주입 패턴 사용 |
| 2026-01 | 존재하지 않는 함수 import → 서버 크래시 | import 전 함수 존재 확인 |

---

## 🔧 커스텀 커맨드 (/.claude/commands/)

| 커맨드 | 설명 |
|--------|------|
| `/deploy` | Render 배포 |
| `/fix-bug` | 버그 수정 워크플로우 |
| `/code-review` | 코드 리뷰 실행 |
| `/test-local` | 로컬 테스트 |
| `/simplify` | 코드 정리 (불필요 코드 제거, 최적화) |
| `/verify` | 코드 검증 (문법, import, 린터) |
| `/pipeline-run` | 파이프라인 실행 |
| `/video-status` | 영상 생성 상태 확인 |

---

## 💡 작업 팁

1. **Plan Mode 활용**: 복잡한 작업은 Shift+Tab으로 Plan Mode 진입 후 계획 수립
2. **Thinking Mode**: 항상 활성화 (더 정확한 결과)
3. **병렬 작업**: 독립적인 작업은 여러 세션에서 동시 진행 가능
4. **백그라운드 실행**: 긴 작업은 `/end`로 백그라운드 전환
