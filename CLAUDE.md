# Google Sheets 자동화 파이프라인

## 현재 브랜치
`claude/continue-image-feature-01TKLum1D1TXAq62rsae92vZ`

## 프로젝트 개요
Google Sheets 기반 YouTube 영상 자동 생성 시스템

---

## ⚠️ 자동화 파이프라인 흐름 (중요!)

```
┌─────────────────────────────────────────────────────────┐
│  1. GPT-5.1 대본 분석 (한 번의 API 호출로 모두 생성)      │
│     ├── 유튜브 메타데이터 (제목, 설명)                   │
│     ├── 썸네일 프롬프트 (ai_prompts)                    │
│     ├── 씬별 이미지 프롬프트                            │
│     └── 씬별 나레이션 (TTS용)                           │
└─────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────┐
│  2. 병렬 처리 (동시 실행)                                │
│     ├── Gemini 3 Pro → 썸네일 이미지 생성               │
│     ├── Gemini 2.5 Flash → 씬 배경 이미지 생성          │
│     └── Google TTS → 음성 + 자막 생성                   │
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

## Google Sheets 컬럼 구조

| 열 | 필드명 | 설명 |
|---|--------|------|
| A | 상태 | 대기중/처리중/완료/실패 |
| B | 작업시간 | 파이프라인 실행 시간 |
| C | 채널ID | YouTube 채널 ID |
| D | 채널명 | 참고용 (코드에서 미사용) |
| E | 예약시간 | YouTube 공개 예약 시간 |
| F | 대본 | 영상 대본 전문 |
| G | 제목 | YouTube 제목 (GPT 생성 메인, 입력 시 우선) |
| H | 제목2 | 대안 제목 1 - solution 스타일 (출력) |
| I | 제목3 | 대안 제목 2 - authority 스타일 (출력) |
| J | 비용 | 생성 비용 (출력) |
| K | 공개설정 | public/private/unlisted |
| L | 영상URL | 업로드된 URL (출력) |
| M | 에러메시지 | 실패 시 에러 (출력) |
| N | 음성 | TTS 음성 (입력/출력) |
| O | 타겟 | general/senior (입력/출력) |
| P | 카테고리 | GPT 감지 카테고리 - news/story (출력) |
| Q | 쇼츠URL | 자동 생성된 쇼츠 URL (출력) |
| R | 플레이리스트ID | YouTube 플레이리스트 ID (입력, 선택) |

**제목 A/B 테스트**: G열에 메인 제목, H/I열에 대안 제목이 자동 저장됩니다.
CTR이 낮을 경우 YouTube Studio에서 H 또는 I열의 제목으로 변경하여 테스트할 수 있습니다.

**플레이리스트 자동 추가**: R열에 플레이리스트 ID를 입력하면 업로드된 영상이 자동으로 해당 플레이리스트에 추가됩니다.
플레이리스트 ID는 YouTube Studio > 플레이리스트 > URL에서 `list=` 뒤의 값입니다 (예: `PLxxxxxxxxxxxxxxxxxx`).

---

## 이미지 개수 계산

```python
# 1분당 1개 이미지 (한국어 150자 ≈ 1분)
image_count = max(3, len(script) // 150)
```

- 최소 3개
- 상한 없음 (대본 길이에 따라 동적)

---

## 주요 API 엔드포인트

### 자동화용
- `POST /api/sheets/check-and-process` - cron job 트리거
- `POST /api/image/analyze-script` - GPT-5.1 대본 분석
- `POST /api/drama/generate-image` - Gemini 이미지 생성
- `POST /api/image/generate-assets-zip` - TTS + 자막 생성
- `POST /api/thumbnail-ai/generate-single` - 단일 썸네일 생성
- `POST /api/image/generate-video` - FFmpeg 영상 생성
- `POST /api/youtube/upload` - YouTube 업로드

### 상태 확인
- `GET /api/image/video-status/{job_id}` - 영상 생성 상태

---

## 타임아웃 설정

| 작업 | 타임아웃 |
|-----|---------|
| 대본 분석 | 120초 |
| 이미지 생성 (개당) | 60초 |
| TTS 생성 | 300초 |
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
| TTS (Google) | ~$0.000004/글자 |

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
