#!/bin/bash
# PC 서버 종료 스크립트

echo "PC 서버 종료 중..."

pkill -f "drama_server.py" 2>/dev/null && echo "✓ drama_server.py 종료" || echo "- drama_server.py 실행 중 아님"
pkill -f "ngrok" 2>/dev/null && echo "✓ ngrok 종료" || echo "- ngrok 실행 중 아님"

echo "완료!"
