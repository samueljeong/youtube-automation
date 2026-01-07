# 뉴스 자동화 파이프라인

## 개요

```
┌─────────────────────────────────────────────────────────┐
│  1. Google News RSS 수집                                │
│     └── 4개 카테고리 피드에서 기사 수집 → RAW_FEED       │
└─────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────┐
│  2. 채널별 필터링 + 후보 선정 (규칙 기반, LLM ❌)         │
│     ├── 채널 필터 적용 (include/exclude 키워드)         │
│     ├── 중복 제거 (해시 기반)                           │
│     └── 점수화 (관련도 + 신선도) → CANDIDATES_{CHANNEL}  │
└─────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────┐
│  3. OPUS 입력 생성 (TOP 1만 LLM)                        │
│     └── 핵심포인트 + 요일별 앵글 → OPUS_INPUT_{CHANNEL}  │
└─────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────┐
│  4. 사람 개입 (현재)                                    │
│     └── OPUS_INPUT → Opus → 대본 작성                   │
└─────────────────────────────────────────────────────────┘
```

## 채널 구조

```
Google Sheets 파일 (NEWS_SHEET_ID)
├── RAW_FEED              ← 모든 채널 공용 (RSS 원본)
├── CANDIDATES_ECON       ← 경제채널 후보
├── OPUS_INPUT_ECON       ← 경제채널 대본 입력
├── CANDIDATES_POLICY     ← (확장용) 정책채널
├── OPUS_INPUT_POLICY     ← (확장용)
├── CANDIDATES_SOCIETY    ← (확장용) 사회채널
├── OPUS_INPUT_SOCIETY    ← (확장용)
├── CANDIDATES_WORLD      ← (확장용) 국제채널
└── OPUS_INPUT_WORLD      ← (확장용)
```

**현재 활성 채널**: ECON (경제)

## 채널별 설정

| 채널 | 이름 | 설명 | 상태 |
|------|------|------|------|
| ECON | 경제 | 내 돈·내 자산에 영향을 주는 경제 뉴스 | **활성** |
| POLICY | 정책 | 내 세금·내 복지에 영향을 주는 정책 뉴스 | 비활성 |
| SOCIETY | 사회 | 내 가족·내 동네에 영향을 주는 사회 뉴스 | 비활성 |
| WORLD | 국제 | 내 지갑에 영향을 주는 국제 뉴스 | 비활성 |

## 요일별 앵글

| 요일 | 앵글 |
|------|------|
| 월 | 지난주 흐름 + 이번 주 예고 |
| 화 | 이슈 정리 |
| 수 | 심층 분석 |
| 목 | 실생활 영향 |
| 금 | 주간 총정리 |
| 토 | 주간 베스트/위클리 (확장 예정) |
| 일 | 큰 흐름 + 다음 주 예고 |

## API 엔드포인트

| 엔드포인트 | 메서드 | 설명 |
|-----------|--------|------|
| `/api/news/run-pipeline?channel=ECON` | POST | 채널별 파이프라인 실행 |
| `/api/news/run-pipeline?channel=ECON&force=1` | POST | 강제 실행 (중복 무시) |
| `/api/news/test-rss?channel=ECON` | GET | 채널별 RSS 테스트 (시트 저장 ❌) |

## 환경변수

| 변수명 | 필수 | 설명 |
|--------|------|------|
| `NEWS_SHEET_ID` | 선택 | 뉴스용 시트 ID |
| `NEWS_CRON_KEY` | 권장 | 보안 키 |
| `LLM_ENABLED` | 선택 | TOP 1에 LLM 핵심포인트 생성 |
| `TOP_K` | 선택 | CANDIDATES에 선정할 후보 수 (기본 5) |
| `OPUS_TOP_N` | 선택 | OPUS_INPUT에 저장할 후보 수 (기본 3) |

## 참고 파일

- `scripts/news_pipeline/run.py` - 메인 파이프라인
- `scripts/news_pipeline/__init__.py` - 모듈 export

---

## 히스토리 파이프라인 통합 (2025-12-29)

뉴스 파이프라인 실행 시 **히스토리 파이프라인도 자동 실행**됩니다.

```
/api/news/run-pipeline 호출 시:
1. 뉴스 수집 파이프라인 실행
2. 히스토리 파이프라인 실행 (준비 1개 미만이면 에피소드 추가)
```

**응답 예시:**
```json
{
    "ok": true,
    "result": { ... },
    "history": {
        "success": true,
        "pending_before": 0,
        "pending_after": 1,
        "episodes_added": 1
    }
}
```

### 히스토리 파이프라인 참고 파일

- `scripts/history_pipeline/workers.py` - ★ 실행 담당 (TTS, 이미지, 영상, 업로드)
- `scripts/history_pipeline/run.py` - 메인 오케스트레이션
- `scripts/history_pipeline/config.py` - 시대/주제 설정 (11개 시대)
- `scripts/history_pipeline/collector.py` - 자료 수집 (4개 공신력 소스)
- `scripts/history_pipeline/sheets.py` - HISTORY 시트 CRUD

### 창작/실행 분리 구조 (2026-01)

```
┌────────────────────────────────┐    ┌────────────────────────────┐
│  창작 (Claude가 대화에서 직접)   │───▶│  실행 (workers.py)         │
├────────────────────────────────┤    ├────────────────────────────┤
│ • 자료 조사 및 검증             │    │ • TTS 생성                 │
│ • 에피소드 기획 (구조, 흐름)    │    │ • 이미지 생성              │
│ • 대본 작성 (12,000~15,000자)   │    │ • 영상 렌더링              │
│ • 이미지 프롬프트              │    │ • YouTube 업로드           │
│ • YouTube 메타데이터           │    │                            │
│ • 썸네일 문구 설계             │    │                            │
└────────────────────────────────┘    └────────────────────────────┘
```

### 사용법 (Claude가 대본 작성 후)

```python
from scripts.history_pipeline import execute_episode

result = execute_episode(
    episode_id="ep001",
    title="광개토왕의 정복전쟁",
    script="대본 내용...",
    image_prompts=[{"prompt": "...", "scene_index": 1}],
    metadata={"title": "...", "description": "...", "tags": [...]},
    generate_video=True,
    upload=True,
)
```

### HISTORY 시트 열 구조

```
A: era            G: 상태           M: 공개설정
B: episode_slot   H: 대본           N: 예약시간
C: core_question  I: 인용링크       O: 플레이리스트ID
D: source_url     J: 제목(GPT생성)  P: 음성
E: opus_prompt    K: 제목(입력)     Q: 영상URL
F: thumbnail_copy L: 썸네일문구(입력)
```
