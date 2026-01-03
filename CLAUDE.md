# Google Sheets 자동화 파이프라인

## 현재 브랜치
`claude/continue-image-feature-01TKLum1D1TXAq62rsae92vZ`

## 프로젝트 개요
Google Sheets 기반 YouTube 영상 자동 생성 시스템

---

## 🛠️ Claude 보조 도구 (AI Tools) - 내가 못하는 것 대신하기

**사용자가 YouTube 검색, 이미지 생성, 트렌드 확인을 요청하면 이 API를 호출하세요!**

### 사용 가능한 도구

| 도구 | API | 용도 |
|------|-----|------|
| YouTube 리서처 | `/api/ai-tools/youtube` | 영상 검색, 자막 추출, 댓글 분석 |
| 트렌드 스캐너 | `/api/ai-tools/trend` | 실시간 뉴스, 검색어 트렌드 |
| 이미지 생성 | `/api/ai-tools/image-generate` | Gemini Imagen으로 이미지 생성 |
| 이미지 분석 | `/api/ai-tools/vision` | Gemini Vision으로 이미지/URL 분석 |

### Claude가 직접 호출하는 방법

```bash
# YouTube 검색
curl -X POST http://localhost:5059/api/ai-tools/youtube \
  -H "Content-Type: application/json" \
  -d '{"query": "검색어", "action": "search", "limit": 10}'

# 자막 추출
curl -X POST http://localhost:5059/api/ai-tools/youtube \
  -H "Content-Type: application/json" \
  -d '{"query": "VIDEO_ID", "action": "transcript"}'

# 뉴스 트렌드
curl -X POST http://localhost:5059/api/ai-tools/trend \
  -H "Content-Type: application/json" \
  -d '{"source": "news", "category": "economy"}'

# 이미지 생성
curl -X POST http://localhost:5059/api/ai-tools/image-generate \
  -H "Content-Type: application/json" \
  -d '{"prompt": "이미지 설명", "style": "realistic", "ratio": "16:9"}'

# 이미지 분석
curl -X POST http://localhost:5059/api/ai-tools/vision \
  -H "Content-Type: application/json" \
  -d '{"url": "이미지URL", "prompt": "분석 요청"}'
```

### 웹 UI
- `/ai-tools` 페이지에서 사용자가 직접 사용 가능

---

## [필수] 세션 시작 시 확인할 로그 파일

세션이 길어지면 이전 내용을 기억하지 못합니다. **작업 시작 전 반드시 아래 파일을 확인하세요!**

| 파일 | 목적 | 확인 시점 |
|------|------|----------|
| `docs/SERMON_CHANGELOG.md` | Sermon 페이지 작업 로그 | Sermon 관련 작업 시 |
| `SERMON_MODULE_STRUCTURE.md` | Sermon 모듈화 구조 | Sermon 코드 수정 시 |
| `TODO_SERMON.md` | Sermon 개발 계획 | Sermon 기능 추가 시 |

### 작업 완료 후
- 작업 내용을 해당 로그 파일에 기록하세요
- 날짜, 문제, 수정 내용, 커밋 해시 포함

---

## 🤖 Claude 슈퍼바이저 역할 (필수 준수)

### 커밋 전 코드 검증 체크리스트

**절대 커밋하기 전에 아래 항목을 확인하세요!**

| 체크 | 항목 | 설명 |
|:---:|------|------|
| ☐ | **함수 호출 체인 추적** | A → B → C 호출 시 각 함수의 전제조건(if문, 필수 변수) 확인 |
| ☐ | **전역 변수 의존성** | `window.xxx` 변수가 필요한 곳에서 실제로 설정되는지 확인 |
| ☐ | **에러 경로 확인** | `if (!조건) return/alert` 패턴이 있으면 해당 조건이 충족되는지 검증 |
| ☐ | **이벤트 바인딩 확인** | 동적 생성 요소의 이벤트가 제대로 바인딩되는지 확인 |
| ☐ | **데이터 형식 호환성** | API 응답 형식 변경 시, 해당 데이터를 사용하는 모든 코드 확인 |

### 실패 사례 기록 (교훈)

| 날짜 | 문제 | 원인 | 교훈 |
|------|------|------|------|
| 2025-12-26 | 시작 버튼 미작동 | `selectRecommendation()`에서 `window.currentStyleId` 미설정 | `startAutoAnalysis()`의 전제조건을 확인했어야 함 |
| 2025-12-26 | 시작 버튼 안보임 | `startAutoAnalysis()`에서 버튼 숨김 후 복구 안함 | UI 숨김 코드가 있으면 복구 코드도 확인 |
| 2025-12-26 | 시작 버튼 안보임 (재발) | `finally`에서 `analysisInProgress=false` 설정 후 `updateAnalysisUI()` 미호출 | **상태 변경 후 UI 업데이트 함수 호출 필수** |

### 검증 방법

1. **호출되는 함수 읽기**: 내가 수정한 함수가 호출하는 다른 함수들의 시작 부분 확인
2. **필수 변수 역추적**: 함수에서 사용하는 전역 변수가 어디서 설정되는지 확인
3. **UI 흐름 시뮬레이션**: 사용자 클릭 → 함수 호출 → 상태 변경 흐름을 머릿속으로 따라가기

**브라우저 테스트는 못하지만, 코드 분석으로 잡을 수 있는 버그는 반드시 커밋 전에 잡아야 한다!**

---

## ⚠️ 자동화 파이프라인 흐름 (중요!)

```
┌─────────────────────────────────────────────────────────┐
│  1. GPT-4o 대본 분석 (한 번의 API 호출로 모두 생성)       │
│     ├── 유튜브 메타데이터 (제목, 설명)                   │
│     ├── 썸네일 프롬프트 (ai_prompts)                    │
│     ├── 씬별 이미지 프롬프트                            │
│     └── 씬 구조 (나레이션은 코드에서 강제 분할)          │
│                                                         │
│  ★ 대본 강제 분할 (2025-12-17)                          │
│     - GPT 응답 후 코드에서 원본 대본을 씬별로 균등 분할   │
│     - 문장 단위로 자연스럽게 끊어서 배분                  │
│     - GPT가 요약/재작성하는 문제 완전 해결               │
│     - 대본 100%가 TTS로 변환됨 (유실 없음)               │
└─────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────┐
│  2a. TTS 생성 (먼저 실행 - 저비용)                       │
│      └── Google TTS → 음성 + 자막 생성                  │
└─────────────────────────────────────────────────────────┘
                          │
                          ▼ (TTS 성공 시)
┌─────────────────────────────────────────────────────────┐
│  2b. 병렬 처리 (TTS 성공 후)                             │
│     ├── Gemini 3 Pro → 썸네일 이미지 생성               │
│     └── Gemini 2.5 Flash → 씬 배경 이미지 생성          │
└─────────────────────────────────────────────────────────┘
                          │
                          ▼ (모두 완료 후)
┌─────────────────────────────────────────────────────────┐
│  3. FFmpeg 영상 생성                                     │
│     - 이미지 + 오디오 + 자막 합성                        │
└─────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────┐
│  4. YouTube 업로드                                       │
│     - 썸네일 설정                                        │
│     - 플레이리스트 추가 (R열에 ID 있는 경우)             │
│     - 예약 공개 (있는 경우)                              │
└─────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────┐
│  5. 쇼츠 자동 생성 (옵션)                                │
│     - 하이라이트 씬 추출 (60초 이하)                     │
│     - 세로 영상(9:16) 변환                               │
│     - 원본 영상 링크 포함하여 업로드                     │
└─────────────────────────────────────────────────────────┘
```

**주의:** "Step1-6" 같은 UI 용어 사용 금지. 위 흐름이 자동화 파이프라인의 정확한 구조임.

---

## Google Sheets 구조 (채널별 시트)

### 시트 구조 개요

```
Google Sheets 파일
├── 뉴스채널      ← 채널별 탭 (탭 이름 = 채널명)
├── 드라마채널
├── 시니어채널
└── _설정        ← 언더스코어 시작 = 처리 제외 (선택)
```

### 각 시트 구조

**행 1: 채널 설정 (고정)**
| A1 | B1 |
|----|-----|
| 채널ID | UCxxxxxxxxxxxx |

**행 2: 헤더 (열 순서 자유 - 동적 매핑)**

| 헤더명 | 입/출력 | 설명 |
|--------|---------|------|
| 상태 | 입출력 | 대기/처리중/완료/실패 |
| 공개설정 | 입력 | public/private/unlisted |
| 플레이리스트ID | 입력 | YouTube 플레이리스트 ID |
| 작업시간 | 출력 | 파이프라인 실행 시간 |
| 예약시간 | 입력 | YouTube 공개 예약 시간 |
| 영상URL | 출력 | 업로드된 URL |
| CTR | 출력 | 클릭률 (%) - 자동 조회 |
| 노출수 | 출력 | impressions - 자동 조회 |
| 제목 (GPT 생성) | 출력 | GPT가 생성한 제목 |
| 제목(입력) | 입력 | ★ 사용자 입력 제목 (있으면 GPT 생성 제목 대신 사용) |
| 썸네일문구(입력) | 입력 | ★ 사용자 입력 썸네일 문구 (줄바꿈으로 line1/line2 분리) |
| 제목2 | 출력 | 대안 제목 (solution 스타일) |
| 제목3 | 출력 | 대안 제목 (authority 스타일) |
| 제목변경일 | 출력 | CTR 자동화로 변경된 날짜 |
| 대본 | 입력 | 영상 대본 전문 (★ 100% 그대로 TTS 변환됨) |
| 카테고리 | 출력 | GPT 감지 (news/story) |
| 에러메시지 | 출력 | 실패 시 에러 |
| 비용 | 출력 | 생성 비용 ($x.xx) |

**행 3~: 데이터**

### 처리 우선순위

1. **예약시간 있음**: 예약시간 빠른 순으로 처리
2. **예약시간 없음**: 시트 탭 순서대로 처리
3. **처리중 상태**: 어떤 시트에서든 처리중이면 전체 대기

### 제목 A/B 테스트 자동화

- **자동 CTR 확인**: 업로드 후 7일 경과한 영상의 CTR 자동 조회
- **자동 제목 변경**: CTR 3% 미만 + 노출 100회 이상 시 제목2 → 제목3 순서로 변경
- **변경 기록**: 제목변경일에 변경 일시 자동 기록
- **API**: `POST /api/sheets/check-ctr-and-update-titles` (매일 1회 cron 권장)

### 열 순서 자유 변경

헤더 기반 동적 매핑으로 열 순서를 자유롭게 변경할 수 있습니다.
예시:
```
A: 상태 | B: 대본 | C: 제목 | D: 영상URL | ...  (순서 1)
A: 대본 | B: 상태 | C: 영상URL | D: 제목 | ...  (순서 2) - 둘 다 OK
```

**주의**: 헤더 이름은 정확히 일치해야 합니다.

---

## 이미지 개수 계산

```python
# 한국어 TTS 기준: 910자 ≈ 1분
# 히스토리 채널: 12,000~15,000자 (약 13~16분 영상)
# ~8분: 5컷, 8~10분: 8컷, 10~15분: 11컷, 15분+: 12컷
estimated_minutes = len(script) / 910
```

- 최소 5개, 최대 12개
- 대본 길이에 따라 동적 결정

---

## 주요 API 엔드포인트

### 자동화용 (cron job)
- `POST /api/sheets/check-and-process` - 영상 생성 파이프라인 (5분마다)
- `POST /api/sheets/check-ctr-and-update-titles` - CTR 기반 제목 자동 변경 (매일 1회)

### 파이프라인 내부
- `POST /api/image/analyze-script` - GPT-5.1 대본 분석
- `POST /api/drama/generate-image` - Gemini 이미지 생성
- `POST /api/image/generate-assets-zip` - TTS + 자막 생성
- `POST /api/thumbnail-ai/generate-single` - 단일 썸네일 생성
- `POST /api/image/generate-video` - FFmpeg 영상 생성
- `POST /api/youtube/upload` - YouTube 업로드

### 상태 확인
- `GET /api/image/video-status/{job_id}` - 영상 생성 상태

### 디버깅
- `GET /api/sheets/read` - 시트 데이터 읽기
- `POST /api/sheets/update` - 시트 셀 업데이트

### 시트 관리
- `GET /api/sheets/create-unified` - 통합 시트 생성 (NEWS, HISTORY, MYSTERY)
- `GET /api/sheets/create-bible` - 성경통독 BIBLE 시트 생성 (106개 에피소드)

### 성경통독 파이프라인 (2025-12-22)
- `POST /api/bible/check-and-process` - 성경통독 영상 생성 (cron job)

---

## 성경통독 파이프라인 (2025-12-22)

### 개요

100일 성경통독 영상 자동 생성 시스템 (106개 에피소드)

```
┌─────────────────────────────────────────────────────────┐
│  1. BIBLE 시트에서 상태='대기' 에피소드 조회            │
└─────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────┐
│  2. TTS 생성 (절 번호 제외, 본문만 낭독)                │
│     └── Gemini TTS (chirp3:Charon) - 차분한 목소리     │
└─────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────┐
│  3. 배경 이미지 확인/생성                               │
│     ├── 구약: 파란색 계열 그라데이션                   │
│     └── 신약: 붉은색 계열 그라데이션                   │
└─────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────┐
│  4. 썸네일 생성                                         │
│     └── "100일 성경통독 Day X / 창세기1장~15장"        │
└─────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────┐
│  5. 영상 렌더링 (FFmpeg)                                │
│     ├── 배경 이미지 + TTS 오디오                       │
│     └── ASS 자막 (절 번호 포함, 페이드 효과 300ms)     │
└─────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────┐
│  6. YouTube 업로드                                       │
│     └── 플레이리스트, 예약 공개 지원                   │
└─────────────────────────────────────────────────────────┘
```

### BIBLE 시트 구조

| 컬럼 | 설명 |
|------|------|
| 에피소드 | EP001 ~ EP106 |
| 책 | 창세기, 출애굽기, ... |
| 시작장 | 시작 장 번호 |
| 끝장 | 끝 장 번호 |
| 예상시간(분) | TTS 예상 재생 시간 |
| 글자수 | 총 텍스트 길이 |
| 상태 | (빈칸)/대기/처리중/완료/실패 |
| 제목 | 자동 생성 (예: [100일 성경통독] Day 1 - 창세기 1-15장) |
| 음성 | TTS 음성 (기본: chirp3:Charon) |
| 공개설정 | public/private/unlisted |
| 예약시간 | YouTube 예약 공개 시간 |
| 플레이리스트ID | YouTube 플레이리스트 ID |
| 영상URL | 업로드된 YouTube URL (출력) |
| 에러메시지 | 실패 시 에러 (출력) |
| 작업시간 | 파이프라인 실행 시간 (출력) |
| 생성일 | 행 생성 날짜 |

### API 사용법

```bash
# BIBLE 시트 생성 (106개 에피소드 자동 등록)
curl "https://drama-s2ns.onrender.com/api/sheets/create-bible"

# 채널 ID 포함
curl "https://drama-s2ns.onrender.com/api/sheets/create-bible?channel_id=UCxxx"

# 기존 시트 삭제 후 재생성
curl "https://drama-s2ns.onrender.com/api/sheets/create-bible?force=1"

# 영상 생성 파이프라인 실행 (cron job)
curl -X POST "https://drama-s2ns.onrender.com/api/bible/check-and-process"
```

### 참고 파일

- `scripts/bible_pipeline/run.py` - 에피소드 분할 로직 (106개)
- `scripts/bible_pipeline/config.py` - 설정 (TTS 음성, 시트 헤더)
- `scripts/bible_pipeline/sheets.py` - Google Sheets 연동
- `scripts/bible_pipeline/thumbnail.py` - 썸네일 생성
- `scripts/bible_pipeline/renderer.py` - ASS 자막 + FFmpeg 영상 렌더링
- `scripts/bible_pipeline/background.py` - 배경 이미지 생성

---

## 통합 시트 구조 (2025-12-19)

### 개요

기존 수집 전용 시트(OPUS_INPUT_ECON, HISTORY_OPUS_INPUT, MYSTERY_OPUS_INPUT)를
**수집 + 영상 자동화** 통합 시트로 변경:

```
┌─────────────────────────────────────────────────────────────────┐
│ NEWS / HISTORY / MYSTERY 통합 시트                              │
├─────────────────────────────────────────────────────────────────┤
│ 행 1: 채널ID | UCxxxxxxxxxxxx                                   │
├─────────────────────────────────────────────────────────────────┤
│ 행 2: 헤더                                                       │
│                                                                  │
│ [수집 영역]                    [영상 자동화 영역]                │
│ ├── category                  ├── 상태 (대기/처리중/완료)       │
│ ├── core_points               ├── 대본 ★                       │
│ ├── opus_prompt_pack          ├── 제목(GPT생성)                 │
│ └── thumbnail_copy            ├── 제목(입력) ★                 │
│                               ├── 썸네일문구(입력) ★            │
│                               ├── 공개설정                      │
│                               ├── 예약시간                      │
│                               └── 영상URL                       │
├─────────────────────────────────────────────────────────────────┤
│ 행 3~: 데이터                                                    │
│                                                                  │
│ 흐름: 수집 → opus_prompt_pack 생성 →                            │
│       (사용자/자동) 대본 작성 → 상태='대기' →                    │
│       영상 생성 파이프라인 자동 시작                             │
└─────────────────────────────────────────────────────────────────┘
```

### API: 통합 시트 생성

```bash
# 3개 시트 모두 생성
curl "https://drama-s2ns.onrender.com/api/sheets/create-unified"

# 특정 시트만 생성
curl "https://drama-s2ns.onrender.com/api/sheets/create-unified?sheets=NEWS,MYSTERY"

# 채널 ID 포함
curl "https://drama-s2ns.onrender.com/api/sheets/create-unified?channel_id_NEWS=UCxxx&channel_id_MYSTERY=UCyyy"
```

### 시트별 헤더 구조

| 시트 | 수집 헤더 | 영상 자동화 헤더 |
|------|----------|-----------------|
| NEWS | run_id, selected_rank, category, issue_one_line, core_points, brief, thumbnail_copy, opus_prompt_pack | 상태, 대본, 제목(GPT생성), 제목(입력), 썸네일문구(입력), 공개설정, 예약시간, 플레이리스트ID, 음성, 영상URL, 쇼츠URL, 제목2, 제목3, 비용, 에러메시지, 작업시간 |
| HISTORY | era, episode_slot, structure_role, core_question, facts, human_choices, impact_candidates, source_url, opus_prompt_pack, thumbnail_copy | (동일) |
| MYSTERY | episode, category, title_en, title_ko, wiki_url, summary, full_content, opus_prompt, thumbnail_copy | (동일) |

---

## 타임아웃 설정

| 작업 | 타임아웃 |
|-----|---------|
| 대본 분석 (GPT-5.1) | 600초 (10분) |
| 대본 분석 HTTP 요청 | 660초 (11분) |
| 이미지 생성 (개당) | 60초 |
| TTS 생성 | 600초 (10분) |
| 썸네일 생성 | 180초 |
| 영상 생성 폴링 | 40분 (1200 * 2초) |
| YouTube 업로드 | 300초 |
| 처리중 상태 타임아웃 | 40분 |
| gunicorn timeout | 45분 |

**참고**: 10분 영상 생성에 ~20분 소요 (Render 1vCPU 환경)

---

## 환경변수 설정

| 환경변수 | 기본값 | 설명 |
|---------|-------|------|
| `VIDEO_PARALLEL_WORKERS` | `1` | 씬 클립 생성 병렬 워커 수 |
| `OPENROUTER_API_KEY` | - | OpenRouter API 키 (Claude Opus 4.5 대본 생성용) |

### VIDEO_PARALLEL_WORKERS 설정 가이드

| Render 플랜 | 메모리 | 권장 값 | 예상 속도 |
|------------|-------|--------|----------|
| Standard | 2GB | `1` (순차) | 기준 |
| **Pro** | **4GB** | **`2`** | **~1.5-1.8배** |
| Pro Plus | 8GB | `3` | ~2배 |

**Render 대시보드에서 설정**:
1. Dashboard → Service → Environment
2. `VIDEO_PARALLEL_WORKERS` = `2` 추가
3. 문제 발생 시 `1`로 변경 (코드 재배포 불필요)

---

## GPT-5.1 API 사용 가이드

GPT-5.1은 **Responses API** 사용 필수:

```python
from openai import OpenAI
client = OpenAI()

response = client.responses.create(
    model="gpt-5.1",
    input=[
        {"role": "system", "content": [{"type": "input_text", "text": "시스템 프롬프트"}]},
        {"role": "user", "content": [{"type": "input_text", "text": "사용자 프롬프트"}]}
    ],
    temperature=0.7
)

# 결과 추출
if getattr(response, "output_text", None):
    result = response.output_text.strip()
else:
    text_chunks = []
    for item in getattr(response, "output", []) or []:
        for content in getattr(item, "content", []) or []:
            if getattr(content, "type", "") == "text":
                text_chunks.append(getattr(content, "text", ""))
    result = "\n".join(text_chunks).strip()
```

---

## Claude Opus 4.5 API 사용 가이드 (OpenRouter)

히스토리 파이프라인 대본 생성에 Claude Opus 4.5를 사용합니다.
OpenRouter를 통해 접근하므로 **OpenAI 호환 API** 사용:

```python
from openai import OpenAI

# OpenRouter 설정
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
CLAUDE_OPUS_MODEL = "anthropic/claude-opus-4-5-20251101"

client = OpenAI(
    api_key=os.environ.get("OPENROUTER_API_KEY"),
    base_url=OPENROUTER_BASE_URL,
)

response = client.chat.completions.create(
    model=CLAUDE_OPUS_MODEL,
    max_tokens=8192,
    messages=[
        {"role": "system", "content": "시스템 프롬프트"},
        {"role": "user", "content": "사용자 프롬프트"}
    ],
    temperature=0.7,
)

# 결과 추출
text = response.choices[0].message.content or ""
```

### 비용 (2026-01 기준)

| 항목 | 가격 |
|------|------|
| Input (정가) | $15 / 1M tokens |
| Input (캐시) | $1.5 / 1M tokens (90% 할인) |
| Output | $75 / 1M tokens |

**Prompt Caching**: System Prompt가 1024 토큰 이상이면 자동 캐싱됨.

---

## 호스팅 환경

- **Render Standard 플랜**
- 메모리: 2GB
- CPU: 1 vCPU
- URL: https://drama-s2ns.onrender.com

---

## 비용 추적

| 항목 | 단가 |
|-----|------|
| 대본 분석 (GPT-5.1) | ~$0.03 |
| 이미지 생성 (Gemini 2.5) | ~$0.02/장 |
| 썸네일 생성 (Gemini 3 Pro) | ~$0.03 |
| TTS (Google Cloud Neural2) | ~$0.016/1000자 |
| TTS (Gemini Flash) | ~$0.001/1000자 |
| TTS (Gemini Pro) | ~$0.016/1000자 |

---

## TTS 음성 설정 (Google Sheets N열)

### 기본값
기본값: `ko-KR-Neural2-C` (Google Cloud TTS 남성 음성)

### Google Cloud TTS 음성
| 음성 ID | 설명 |
|---------|------|
| `ko-KR-Neural2-A` | 여성, 고품질 |
| `ko-KR-Neural2-B` | 남성, 고품질 |
| `ko-KR-Neural2-C` | 남성, 고품질 (기본값) |
| `ko-KR-Wavenet-A` | 여성 |
| `ko-KR-Wavenet-B` | 남성 |

### Gemini TTS 음성 (2025년 신규)
**형식**: `gemini:음성명` 또는 `gemini:pro:음성명`

| 설정값 | 모델 | 음성 특징 |
|--------|------|----------|
| `gemini:Kore` | Flash (저렴) | 여성, 차분하고 따뜻한 톤 |
| `gemini:Charon` | Flash | 남성, 깊고 신뢰감 있는 톤 |
| `gemini:Puck` | Flash | 남성, 활기차고 친근한 톤 |
| `gemini:Fenrir` | Flash | 남성, 힘있고 웅장한 톤 |
| `gemini:Aoede` | Flash | 여성, 부드럽고 감성적인 톤 |
| `gemini:pro:Kore` | Pro (고품질) | 여성, 차분하고 따뜻한 톤 |
| `gemini:pro:Charon` | Pro | 남성, 깊고 신뢰감 있는 톤 |

### 환경변수
- `GOOGLE_CLOUD_API_KEY`: Google Cloud TTS용
- `GOOGLE_API_KEY`: Gemini TTS용 (Google AI Studio에서 발급)

---

## 참고 파일

- `drama_server.py` - 메인 서버 (모든 API)
- `run_automation_pipeline()` - 자동화 파이프라인 메인 함수

---

## 버그 수정 이력

### 2025-12-07: Worker OOM 크래시 수정

**증상**: 영상 생성 3단계에서 Worker가 SIGKILL로 종료
```
[2025-12-07 04:25:06 +0000] [38] [ERROR] Worker (pid:58) was sent SIGKILL! Perhaps out of memory?
```

**원인**: `subprocess.run(capture_output=True)`가 FFmpeg의 모든 stdout/stderr를 메모리에 버퍼링. FFmpeg는 인코딩 중 수백MB의 출력을 생성하여 2GB 메모리 초과.

**수정** (`drama_server.py`):
- 11621-11623행 (concat): `capture_output=True` → `stdout=DEVNULL, stderr=PIPE`
- 11672-11677행 (subtitle burn-in): `capture_output=True` → `stdout=DEVNULL, stderr=PIPE`
- subprocess 완료 후 `del` + `gc.collect()` 추가

### 2025-12-07: YouTube 업로드 전 영상 검증 강화

**증상**: YouTube 업로드 성공했으나 영상이 Studio에 표시되지 않음

**원인**:
1. 손상된 영상 파일이 업로드되어 YouTube 처리 중 자동 삭제됨
2. 검증 Exception 발생 시 업로드를 계속 진행하는 버그

**수정** (`drama_server.py` 9575-9683행):
- **1단계: ffprobe 메타데이터 검증**
  - duration (최소 1초)
  - size (최소 100KB)
  - video/audio 스트림 존재 여부 (둘 다 필수)
  - 해상도 (최소 100x100)
  - 코덱 정보 로깅
- **2단계: 실제 프레임 디코딩 테스트**
  - ffmpeg로 첫 1초 디코딩 시도
  - 디코딩 실패 시 업로드 차단
- **3단계: YouTube 업로드 후 상태 확인**
  - videos().list API로 uploadStatus/rejectionReason 확인
  - 거부/실패 시 에러 반환
- **Exception 처리 수정**: 검증 실패 시 업로드 차단 (이전: 계속 진행)
- **이미지 생성 실패 체크 추가** (15104-15109행): 모든 이미지 생성 실패 시 중단

### 2025-12-07: YouTube 재생 호환성 수정

**증상**: 영상 업로드 성공했으나 YouTube에서 재생 불가

**원인**:
1. `-movflags +faststart` 없음 (스트리밍 호환 문제)
2. 오디오 `-c:a copy` 사용 (코덱 호환성 문제)
3. 클립 간 오디오 설정 불일치

**수정** (`drama_server.py`):
- **자막 burn-in** (11838-11844행): YouTube 호환 설정 추가
  - `-profile:v high -level 4.0`
  - `-c:a aac -b:a 128k -ar 44100`
  - `-movflags +faststart`
- **클립 생성** (11714-11739행): 오디오 설정 통일
  - 모든 클립에 `-ar 44100` 추가
- **Fallback 재인코딩**: 자막 burn-in 실패 시에도 YouTube 호환으로 재인코딩

### 2025-12-07: 새로운 기능 추가

**쇼츠 자동 생성 및 업로드**
- GPT-5.1이 하이라이트 씬 선택 (`video_effects.shorts.highlight_scenes`)
- 세로 영상(9:16) 자동 변환 (`_generate_shorts_video()`)
- 원본 영상 링크 포함하여 업로드
- Google Sheets O열에 쇼츠 URL 저장

**전환 효과 (Transitions)**
- 씬 사이에 crossfade/fade_black/fade_white 효과 적용
- GPT-5.1이 자동 선택 (`video_effects.transitions`)
- `_apply_transitions()` 함수로 FFmpeg xfade 필터 적용

**YouTube 자막 자동 업로드**
- `_upload_youtube_captions()` 함수 추가
- SRT 파일을 YouTube Captions API로 직접 업로드

### 2025-12-08: Google Sheets API 재시도 로직 추가

**증상**: 간헐적으로 Google Sheets API 호출 실패
```
[SHEETS] 읽기 실패: <HttpError 500 when requesting https://sheets.googleapis.com/v4/spreadsheets/... returned "Authentication backend unknown error.". Details: "Authentication backend unknown error.">
```

**원인**:
1. Google API의 일시적 백엔드 오류 (Authentication backend unknown error)
2. 재시도 로직 없이 즉시 실패 처리
3. API 실패와 빈 시트를 구분하지 않음 (`[]` 반환으로 동일 처리)

**수정** (`drama_server.py`):
- **`sheets_read_rows()` (17738-17787행)**: 재시도 로직 추가
  - 최대 3회 재시도
  - 지수 백오프 (2초, 4초, 8초)
  - 일시적 오류 패턴 자동 감지 (500, 502, 503, 504, timeout, backend error 등)
  - API 실패 시 `None` 반환 (빈 시트 `[]`와 구분)
- **`sheets_update_cell()` (17790-17843행)**: 동일한 재시도 로직 추가
- **`api_sheets_check_and_process()` (19432-19444행)**: API 실패와 빈 시트 구분
  - `None` (API 실패) → HTTP 503 에러 반환
  - `[]` (빈 시트) → 정상 응답 (처리할 작업 없음)

---

## video_effects 구조

GPT-5.1이 대본 분석 시 자동 생성하는 영상 효과 설정:

```json
{
  "bgm_mood": "기본 BGM 분위기 (13가지: hopeful/sad/tense/dramatic/calm/inspiring/mysterious/nostalgic/epic/romantic/comedic/horror/upbeat)",
  "scene_bgm_changes": [
    {"scene": 3, "mood": "tense", "reason": "긴장감 고조"},
    {"scene": 5, "mood": "hopeful", "reason": "희망적인 반전"}
  ],
  "subtitle_highlights": [{"keyword": "충격", "color": "#FF0000"}],
  "screen_overlays": [{"scene": 3, "text": "대박!", "duration": 3, "style": "impact"}],
  "sound_effects": [
    {"scene": 1, "type": "whoosh", "moment": "씬 전환"},
    {"scene": 2, "type": "notification", "moment": "중요 정보"},
    {"scene": 3, "type": "impact", "moment": "충격적 사실"}
  ],
  "lower_thirds": [{"scene": 2, "text": "출처", "position": "bottom-left"}],
  "news_ticker": {"enabled": true, "headlines": ["속보: ..."]},
  "shorts": {
    "highlight_scenes": [2, 3],
    "hook_text": "이 한마디가 모든 걸 바꿨다",
    "title": "충격적인 고백 #Shorts"
  },
  "transitions": {
    "style": "crossfade",
    "duration": 0.5
  }
}
```

### BGM 분위기 종류 (13가지)
| 분위기 | 설명 | 사용 예시 |
|--------|------|----------|
| hopeful | 희망적, 밝은 | 긍정적인 결말, 성공 스토리 |
| sad | 슬픈, 감성적 | 비극, 이별, 슬픈 사연 |
| tense | 긴장감 | 위기, 갈등, 서스펜스 |
| dramatic | 극적인 | 반전, 클라이맥스, 충격적 사실 |
| calm | 차분한 | 정보 전달, 설명, 일상 |
| inspiring | 영감 | 동기부여, 도전, 성취 |
| mysterious | 신비로운 | 미스터리, 의문, 궁금증 |
| nostalgic | 향수 | 과거 회상, 추억 |
| epic | 웅장한 | 대규모 사건, 역사적 순간 |
| romantic | 로맨틱 | 사랑, 감동적인 관계 |
| comedic | 코믹 | 유머, 웃긴 상황 |
| horror | 공포 | 무서운 사건, 소름 |
| upbeat | 신나는 | 활기찬, 에너지 넘치는 |

### SFX 효과음 종류 (13가지)
| 타입 | 설명 | 사용 예시 |
|------|------|----------|
| impact | 충격음 | 충격적인 사실, 반전, 강조 |
| whoosh | 휘익 소리 | 씬 전환, 빠른 움직임 |
| ding | 딩동 알림 | 포인트 강조, 정답 |
| tension | 긴장감 | 위기, 불안, 서스펜스 |
| emotional | 감성 | 감동, 슬픔, 여운 |
| success | 성공 | 달성, 해결, 좋은 결과 |
| notification | 알림 | 중요 정보, 팁, 강조 |
| heartbeat | 심장박동 | 긴장, 불안, 두려움 |
| clock_tick | 시계 소리 | 시간 압박, 긴박감 |
| gasp | 놀람 | 충격, 반전, 서프라이즈 |
| typing | 타이핑 | 텍스트 표시, 메시지 |
| door | 문 소리 | 등장, 퇴장, 전환점 |

### 씬별 BGM 변경 기능
- GPT-5.1이 대본의 감정 흐름을 분석하여 `scene_bgm_changes` 배열 생성
- 각 변경점에서 자동으로 크로스페이드 적용
- 최소 2~3회 BGM 전환 권장 (5씬 이상 영상)

---

## 뉴스 자동화 파이프라인 (채널 기반 A안)

### 개요

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

### 채널 구조 (A안)

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

**현재 활성 채널**: ECON (경제) - 나머지는 확장 가능 구조만 확보

### 채널별 설정

| 채널 | 이름 | 설명 | 상태 |
|------|------|------|------|
| ECON | 경제 | 내 돈·내 자산에 영향을 주는 경제 뉴스 | **활성** |
| POLICY | 정책 | 내 세금·내 복지에 영향을 주는 정책 뉴스 | 비활성 |
| SOCIETY | 사회 | 내 가족·내 동네에 영향을 주는 사회 뉴스 | 비활성 |
| WORLD | 국제 | 내 지갑에 영향을 주는 국제 뉴스 | 비활성 |

### 채널 필터 (ECON 예시)

```python
CHANNEL_FILTERS = {
    "ECON": {
        "include": ["금리", "기준금리", "환율", "물가", "부동산", "집값",
                    "전세", "연금", "주식", "대출", "예금", "적금", ...],
        "exclude": ["정치 공방", "여야 대립", "탄핵"],  # 정치 뉴스 제외
        "weight": 2.0,  # 점수 가중치
    },
}
```

- **include**: 이 키워드 중 하나라도 포함되어야 후보 선정
- **exclude**: 이 키워드 포함 시 제외
- **weight**: 채널별 점수 가중치

### 요일별 앵글

| 요일 | 앵글 |
|------|------|
| 월 | 지난주 흐름 + 이번 주 예고 |
| 화 | 이슈 정리 |
| 수 | 심층 분석 |
| 목 | 실생활 영향 |
| 금 | 주간 총정리 |
| 토 | 주간 베스트/위클리 (확장 예정) |
| 일 | 큰 흐름 + 다음 주 예고 |

### Google Sheets 탭 구조

**TAB: RAW_FEED** - RSS 원본 기사 (공용)
| 컬럼 | 설명 |
|------|------|
| ingested_at | 수집 시간 (ISO) |
| source | google_news_rss |
| feed_name | economy_daily / policy_life / society_life / global_macro |
| title | 기사 제목 |
| link | 기사 URL |
| published_at | 발행 시간 |
| summary | RSS 요약 |
| keywords | 감지된 키워드 (금리\|대출\|...) |
| hash | 중복 방지용 해시 |

**TAB: CANDIDATES_{CHANNEL}** - 채널별 TOP K 후보
| 컬럼 | 설명 |
|------|------|
| run_id | 실행 날짜 (2025-12-17) |
| rank | 순위 (1~5) |
| category | 경제/정책/사회/국제 |
| angle | 요일별 앵글 (자동 설정) |
| score_total | 총점 |
| score_recency | 신선도 점수 |
| score_relevance | 관련도 점수 |
| score_uniqueness | (MVP 미사용) |
| title | 기사 제목 |
| link | 기사 URL |
| published_at | 발행 시간 |
| why_selected | 선정 근거 |

**TAB: OPUS_INPUT_{CHANNEL}** - 채널별 대본 작성용 (TOP 3 후보)

**★ 2025-12-18 업데이트**: 매일 TOP 3 후보를 저장하여 사용자가 선택할 수 있도록 변경
- 카테고리 다양성 우선: 같은 카테고리 연속 방지 (경제→정책→사회)
- LLM 핵심포인트는 TOP 1에만 적용 (비용 절감)

| 컬럼 | 설명 |
|------|------|
| run_id | 실행 날짜 |
| selected_rank | 순위 (1, 2, 3) |
| category | 카테고리 (다양성 확보) |
| issue_one_line | 이슈 한 줄 요약 |
| core_points | 핵심포인트 (TOP 1만 LLM 생성) |
| script_brief | 대본 지시문 |
| thumbnail_copy | 썸네일 문구 |
| opus_prompt_pack | Opus에 붙여넣을 완제품 |
| status | PENDING/WRITING/DONE |
| created_at | 생성 시간 |
| selected | ★ 사용자 선택 표시 (✓) |

### API 엔드포인트

| 엔드포인트 | 메서드 | 설명 |
|-----------|--------|------|
| `/api/news/run-pipeline?channel=ECON` | POST | 채널별 파이프라인 실행 |
| `/api/news/run-pipeline?channel=ECON&force=1` | POST | 강제 실행 (중복 무시) |
| `/api/news/test-rss?channel=ECON` | GET | 채널별 RSS 테스트 (시트 저장 ❌) |

### 환경변수

| 변수명 | 필수 | 설명 |
|--------|------|------|
| `NEWS_SHEET_ID` | 선택 | 뉴스용 시트 ID (없으면 AUTOMATION_SHEET_ID 사용) |
| `NEWS_CRON_KEY` | 권장 | 보안 키 (설정 시 X-Cron-Key 헤더 필수) |
| `LLM_ENABLED` | 선택 | "1"이면 TOP 1에 LLM 핵심포인트 생성 |
| `LLM_MIN_SCORE` | 선택 | LLM 호출 최소 점수 (기본 0, 비용 절감용) |
| `MAX_PER_FEED` | 선택 | 피드당 최대 기사 수 (기본 30) |
| `TOP_K` | 선택 | CANDIDATES에 선정할 후보 수 (기본 5) |
| `OPUS_TOP_N` | 선택 | ★ OPUS_INPUT에 저장할 후보 수 (기본 3) |
| `OPENAI_MODEL` | 선택 | LLM 모델 (기본 gpt-4o-mini) |

### 안전장치

**보안**: NEWS_CRON_KEY 설정 시 X-Cron-Key 헤더 검증
```bash
# Render Cron에서 호출 시
curl -X POST -H "X-Cron-Key: YOUR_SECRET_KEY" \
  "https://drama-s2ns.onrender.com/api/news/run-pipeline?channel=ECON"
```

**Idempotency**: 같은 날 같은 채널 2회 이상 실행 시 자동 스킵 (OPUS_INPUT_{CHANNEL}의 run_id 확인)
```bash
# 강제 실행 시
curl -X POST "https://drama-s2ns.onrender.com/api/news/run-pipeline?channel=ECON&force=1"
```

**시트 자동 생성**: RAW_FEED + CANDIDATES_{CHANNEL} + OPUS_INPUT_{CHANNEL} 탭이 없으면 헤더와 함께 자동 생성

### RSS 피드 설정

4개 카테고리로 Google News 검색:

| 피드명 | 검색 쿼리 |
|--------|----------|
| economy_daily | 기준금리 OR 대출 OR 예금 OR 물가 OR 환율 OR 부동산 |
| policy_life | 세금 OR 연금 OR 건강보험료 OR 전기요금 OR 가스요금 OR 복지 |
| society_life | 고용 OR 실업 OR 집값 OR 전세 OR 의료 OR 교육비 |
| global_macro | 미국 금리 OR 달러 OR 유가 OR 반도체 수출 OR 중국 경기 |

### Render Cron 설정 예시

```bash
# 매일 오전 7시 KST (전날 22:00 UTC) - 경제 채널
0 22 * * * curl -X POST -H "X-Cron-Key: $NEWS_CRON_KEY" \
  "https://drama-s2ns.onrender.com/api/news/run-pipeline?channel=ECON"

# 다른 채널 추가 시 (예: 정책 채널, 오전 8시)
# 0 23 * * * curl -X POST -H "X-Cron-Key: $NEWS_CRON_KEY" \
#   "https://drama-s2ns.onrender.com/api/news/run-pipeline?channel=POLICY"
```

### 참고 파일

- `scripts/news_pipeline/run.py` - 메인 파이프라인 (채널 기반)
- `scripts/news_pipeline/__init__.py` - 모듈 export

### 히스토리 파이프라인 통합 (2025-12-29)

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
    "result": { ... },  // 뉴스 결과
    "history": {        // 히스토리 결과
        "success": true,
        "pending_before": 0,
        "pending_after": 1,
        "episodes_added": 1
    }
}
```

**히스토리 파이프라인 참고 파일:**
- `scripts/history_pipeline/run.py` - 메인 오케스트레이션
- `scripts/history_pipeline/config.py` - 시대/주제 설정 (11개 시대), 대본 분량 설정
- `scripts/history_pipeline/collector.py` - 자료 수집 (4개 공신력 소스)
- `scripts/history_pipeline/script_generator.py` - **Claude Opus 4.5 대본 자동 생성 (OpenRouter, 12,000~15,000자)**
- `scripts/history_pipeline/sheets.py` - HISTORY 시트 CRUD

**히스토리 파이프라인 워크플로우:**
```
1. HISTORY 시트에서 '준비' 상태 에피소드 확인
2. PENDING_TARGET_COUNT (1개) 미만이면:
   - 다음 에피소드 자료 수집 (Gemini, 한국민족문화대백과, e뮤지엄, 한국사DB)
   - Opus 프롬프트 생성 → 시트 저장 (상태: '준비')
3. (선택) /api/history/auto-generate 호출 시:
   - Claude Opus 4.5로 대본 자동 생성 (OpenRouter 경유, 12,000~15,000자, 약 15분 영상)
   - 시트 업데이트 (상태: '대본완료')
4. 사용자가 상태를 '대기'로 변경
5. /api/sheets/check-and-process가 자동 감지 → 영상 생성 시작
```

**대본 생성 모델 (2026-01 업데이트):**
- 모델: Claude Opus 4.5 (`anthropic/claude-opus-4-5-20251101`)
- API: OpenRouter (https://openrouter.ai/api/v1)
- 환경변수: `OPENROUTER_API_KEY`
- 비용: $15/1M input, $75/1M output (Prompt Caching 시 System Prompt 90% 할인)

**HISTORY 시트 열 구조 (VIDEO_AUTOMATION_HEADERS 포함):**
```
A: era            G: 상태           M: 공개설정
B: episode_slot   H: 대본           N: 예약시간
C: core_question  I: 인용링크       O: 플레이리스트ID
D: source_url     J: 제목(GPT생성)  P: 음성
E: opus_prompt    K: 제목(입력)     Q: 영상URL
F: thumbnail_copy L: 썸네일문구(입력)
```

---

## 연예 쇼츠 바이럴 파이프라인 (2025-12-26)

### 개요

바이럴 점수 기반 자동 쇼츠 생성 시스템

```
┌─────────────────────────────────────────────────────────┐
│  1. RSS에서 연예 뉴스 수집                               │
│     └── Google News RSS → 연예인/스포츠/국뽕 카테고리   │
└─────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────┐
│  2. 바이럴 점수 계산 (댓글 크롤링)                       │
│     ├── 네이버/다음 댓글 수집                           │
│     ├── 댓글 수(40%) + 반응(30%) + 논쟁성(20%) + 신선도(10%)│
│     └── S/A/B/C/D 등급 산정                            │
└─────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────┐
│  3. 실제 댓글 기반 대본 생성                             │
│     ├── 논쟁 주제 추출 (A vs B)                         │
│     ├── 핫한 댓글 표현 반영                             │
│     ├── 찬/반 의견 활용                                 │
│     └── 댓글 유도 씬4 생성                              │
└─────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────┐
│  4. 비디오 생성 (TTS + 이미지 + 렌더링)                  │
│     ├── Gemini TTS (문장별 싱크)                        │
│     ├── Gemini 이미지 생성 (4워커 병렬)                 │
│     └── FFmpeg 렌더링 (Ken Burns + BGM)                 │
└─────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────┐
│  5. YouTube 업로드 (옵션)                               │
│     └── 비공개/공개/예약 업로드                         │
└─────────────────────────────────────────────────────────┘
```

### API 엔드포인트

| 엔드포인트 | 메서드 | 설명 |
|-----------|--------|------|
| `/api/shorts/viral-pipeline` | POST | 바이럴 파이프라인 실행 |

**Request JSON:**
```json
{
    "min_score": 40,
    "categories": ["연예인"],
    "generate_video": true,
    "upload_youtube": false,
    "privacy_status": "private",
    "channel_id": null
}
```

**Response:**
```json
{
    "ok": true,
    "person": "아이유",
    "viral_score": {"total_score": 75, "grade": "S"},
    "script_hints": {"debate_topic": "...", "hot_phrases": [...]},
    "video": {"path": "...", "duration": 45.5},
    "youtube": {"video_url": "..."},
    "cost": 0.84
}
```

### CLI 사용법

```bash
# 바이럴 점수 기반 대본 생성만
python -m scripts.shorts_pipeline.run --viral --min-score 40

# 비디오까지 생성
python -m scripts.shorts_pipeline.run --viral --video --min-score 40

# 비디오 생성 + YouTube 업로드
python -m scripts.shorts_pipeline.run --viral --video --upload --privacy public
```

### Render Cron 설정

```bash
# 매일 오전 8시 KST (전날 23:00 UTC) - 비디오 생성만
0 23 * * * curl -X POST "https://drama-s2ns.onrender.com/api/shorts/viral-pipeline" \
  -H "Content-Type: application/json" \
  -d '{"min_score": 40, "generate_video": true}'

# 매일 오전 9시 KST - 비디오 생성 + YouTube 업로드
0 0 * * * curl -X POST "https://drama-s2ns.onrender.com/api/shorts/viral-pipeline" \
  -H "Content-Type: application/json" \
  -d '{"min_score": 40, "generate_video": true, "upload_youtube": true}'
```

### 바이럴 점수 계산 공식

```
총점 = 댓글수(40%) + 반응수(30%) + 논쟁성(20%) + 신선도(10%)

- 댓글수: 0~500개 → 0~100점
- 반응수: 0~1000개 → 0~100점
- 논쟁성: 찬반비율이 50:50에 가까울수록 높음
- 신선도: 6시간 이내 100점, 24시간 이상 50점

등급:
- S: 80점 이상 (강력 추천)
- A: 60점 이상
- B: 40점 이상
- C: 20점 이상
- D: 20점 미만
```

### 참고 파일

- `scripts/shorts_pipeline/run.py` - 메인 파이프라인
- `scripts/shorts_pipeline/news_scorer.py` - 바이럴 점수화 + 댓글 크롤링
- `scripts/shorts_pipeline/news_collector.py` - 뉴스 수집 + 점수화 통합
- `scripts/shorts_pipeline/script_generator.py` - 댓글 기반 대본 생성
