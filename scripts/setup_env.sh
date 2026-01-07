#!/bin/bash
# 한국사 파이프라인 환경 설정 스크립트
# 세션 시작 시 실행: bash scripts/setup_env.sh

echo "=== 환경 설정 시작 ==="

# 1. FFmpeg 설치 확인/설치
if command -v ffmpeg &> /dev/null; then
    echo "✓ FFmpeg 이미 설치됨"
else
    echo "→ FFmpeg 설치 중..."
    apt-get update -qq && apt-get install -y -qq ffmpeg 2>/dev/null
    if command -v ffmpeg &> /dev/null; then
        echo "✓ FFmpeg 설치 완료"
    else
        echo "✗ FFmpeg 설치 실패"
    fi
fi

# 2. API 키 확인
if [ -n "$GOOGLE_CLOUD_API_KEY" ]; then
    echo "✓ GOOGLE_CLOUD_API_KEY 설정됨"
else
    echo "⚠ GOOGLE_CLOUD_API_KEY 없음 - TTS 불가"
fi

# 3. 출력 디렉토리 생성
mkdir -p outputs/history/{audio,subtitles,videos,images,scripts,briefs}
echo "✓ 출력 디렉토리 준비 완료"

echo "=== 환경 설정 완료 ==="
