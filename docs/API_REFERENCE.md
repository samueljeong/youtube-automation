# API Reference

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

### 성경통독 파이프라인
- `POST /api/bible/check-and-process` - 성경통독 영상 생성 (cron job)

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
| 처리중 상태 타임아웃 | 90분 (환경변수로 조정 가능) |
| gunicorn timeout | 90분 |

**참고**: 10분 영상 생성에 ~20분 소요 (Render 1vCPU 환경)

---

## 환경변수 설정

| 환경변수 | 기본값 | 설명 |
|---------|-------|------|
| `VIDEO_PARALLEL_WORKERS` | `1` | 씬 클립 생성 병렬 워커 수 |
| `OPENROUTER_API_KEY` | - | OpenRouter API 키 (Claude Opus 4.5 대본 생성용) |
| `PROCESSING_TIMEOUT_MINUTES` | `90` | 처리중 상태 타임아웃 (분) |

### VIDEO_PARALLEL_WORKERS 설정 가이드

| Render 플랜 | 메모리 | 권장 값 | 예상 속도 |
|------------|-------|--------|----------|
| Standard | 2GB | `1` (순차) | 기준 |
| **Pro** | **4GB** | **`2`** | **~1.5-1.8배** |
| Pro Plus | 8GB | `3` | ~2배 |

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

```python
from openai import OpenAI

# OpenRouter 설정
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
CLAUDE_OPUS_MODEL = "anthropic/claude-opus-4.5"

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
