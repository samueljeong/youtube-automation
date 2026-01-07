# TTS 음성 설정 가이드

Google Sheets N열에서 음성을 설정합니다.

## 기본값

`ko-KR-Neural2-C` (Google Cloud TTS 남성 음성)

## Google Cloud TTS 음성

| 음성 ID | 설명 |
|---------|------|
| `ko-KR-Neural2-A` | 여성, 고품질 |
| `ko-KR-Neural2-B` | 남성, 고품질 |
| `ko-KR-Neural2-C` | 남성, 고품질 (기본값) |
| `ko-KR-Wavenet-A` | 여성 |
| `ko-KR-Wavenet-B` | 남성 |

## Gemini TTS 음성 (2025년 신규)

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

## 환경변수

- `GOOGLE_CLOUD_API_KEY`: Google Cloud TTS용
- `GOOGLE_API_KEY`: Gemini TTS용 (Google AI Studio에서 발급)
