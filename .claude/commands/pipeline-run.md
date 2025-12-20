# 영상 생성 파이프라인 실행

Google Sheets에서 "대기" 상태인 항목을 찾아 영상 생성 파이프라인을 실행합니다.

## 실행 명령

```bash
curl -X POST "https://drama-s2ns.onrender.com/api/sheets/check-and-process"
```

## 파이프라인 흐름

1. GPT-5.1 대본 분석 (제목, 썸네일, 씬 구조)
2. TTS 생성 (음성 + 자막)
3. Gemini 이미지 생성 (썸네일 + 씬 배경)
4. FFmpeg 영상 합성
5. YouTube 업로드

## 예상 시간

- 10분 영상: ~20분 소요 (Render 1vCPU 환경)

## 주의사항

- 5분마다 자동 실행됨 (cron job)
- "처리중" 상태가 40분 이상 지속되면 타임아웃
