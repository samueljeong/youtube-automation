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
│     - 예약 공개 (있는 경우)                              │
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
| G | 제목 | YouTube 제목 |
| H | 비용 | 생성 비용 (출력) |
| I | 공개설정 | public/private/unlisted |
| J | 영상URL | 업로드된 URL (출력) |
| K | 에러메시지 | 실패 시 에러 (출력) |
| L | 음성 | TTS 음성 선택 (선택) |
| M | 타겟 | general/senior (선택) |
| N | 카테고리 | 뉴스/시사/정치/경제 → 뉴스 스타일 썸네일 |

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
| 영상 생성 폴링 | 20분 (600 * 2초) |
| YouTube 업로드 | 300초 |

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
