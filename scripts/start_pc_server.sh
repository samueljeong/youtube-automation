#!/bin/bash
# ============================================================
# PC 서버 시작 스크립트
#
# 사용법:
#   1. PC에서 한 번만 실행: bash scripts/start_pc_server.sh
#   2. ngrok URL을 복사해서 환경변수로 설정
#   3. 이후 Claude Code에서 자동으로 PC 서버 사용
# ============================================================

set -e

echo "============================================================"
echo "  PC 서버 시작 스크립트"
echo "============================================================"

# 프로젝트 루트로 이동
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_ROOT"

echo "프로젝트 경로: $PROJECT_ROOT"

# 1. 필수 환경변수 확인
echo ""
echo "[1/4] 환경변수 확인..."

if [ -z "$GOOGLE_CLOUD_API_KEY" ]; then
    echo "⚠ GOOGLE_CLOUD_API_KEY 설정 필요"
    echo "  export GOOGLE_CLOUD_API_KEY=\"your-key\""
fi

if [ -z "$GOOGLE_API_KEY" ]; then
    echo "⚠ GOOGLE_API_KEY 설정 필요 (이미지 생성용)"
    echo "  export GOOGLE_API_KEY=\"your-key\""
fi

# 2. 기존 프로세스 종료
echo ""
echo "[2/4] 기존 프로세스 정리..."

pkill -f "drama_server.py" 2>/dev/null || true
pkill -f "ngrok" 2>/dev/null || true
sleep 2

# 3. drama_server.py 시작
echo ""
echo "[3/4] drama_server.py 시작..."

if [ -f "drama_server.py" ]; then
    nohup python3 drama_server.py > logs/drama_server.log 2>&1 &
    SERVER_PID=$!
    echo "✓ drama_server.py 시작됨 (PID: $SERVER_PID)"

    # 서버 시작 대기
    sleep 5

    # 서버 상태 확인
    if curl -s http://localhost:5059/health > /dev/null 2>&1; then
        echo "✓ 서버 정상 작동 중 (http://localhost:5059)"
    else
        echo "⚠ 서버 응답 없음. 로그 확인: tail -f logs/drama_server.log"
    fi
else
    echo "✗ drama_server.py 파일이 없습니다."
    exit 1
fi

# 4. ngrok 시작 (설치되어 있으면)
echo ""
echo "[4/4] ngrok 시작..."

if command -v ngrok &> /dev/null; then
    nohup ngrok http 5059 --log=stdout > logs/ngrok.log 2>&1 &
    NGROK_PID=$!
    echo "✓ ngrok 시작됨 (PID: $NGROK_PID)"

    sleep 3

    # ngrok URL 가져오기
    NGROK_URL=$(curl -s http://localhost:4040/api/tunnels | python3 -c "import sys,json; print(json.load(sys.stdin)['tunnels'][0]['public_url'])" 2>/dev/null || echo "")

    if [ -n "$NGROK_URL" ]; then
        echo ""
        echo "============================================================"
        echo "  ✓ PC 서버 준비 완료!"
        echo "============================================================"
        echo ""
        echo "  ngrok URL: $NGROK_URL"
        echo ""
        echo "  Claude Code에서 사용하려면:"
        echo "  export PC_SERVER_URL=\"$NGROK_URL\""
        echo ""
        echo "============================================================"
    else
        echo "⚠ ngrok URL을 가져올 수 없습니다."
        echo "  직접 확인: http://localhost:4040"
    fi
else
    echo "⚠ ngrok이 설치되어 있지 않습니다."
    echo ""
    echo "  설치 방법:"
    echo "  - Mac: brew install ngrok"
    echo "  - Linux: snap install ngrok"
    echo "  - Windows: https://ngrok.com/download"
    echo ""
    echo "  또는 Cloudflare Tunnel 사용:"
    echo "  cloudflared tunnel --url http://localhost:5059"
    echo ""
    echo "  로컬에서만 사용하려면:"
    echo "  export PC_SERVER_URL=\"http://localhost:5059\""
fi

# 로그 디렉토리 생성
mkdir -p logs

echo ""
echo "로그 확인:"
echo "  서버: tail -f logs/drama_server.log"
echo "  ngrok: tail -f logs/ngrok.log"
echo ""
echo "종료하려면: bash scripts/stop_pc_server.sh"
