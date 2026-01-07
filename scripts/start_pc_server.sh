#!/bin/bash
# ============================================================
# PC 서버 시작 스크립트
#
# 사용법:
#   1. 환경변수 설정 (.env 파일 또는 export)
#   2. PC에서 실행: bash scripts/start_pc_server.sh
#   3. ngrok URL을 복사해서 Claude Code에서 사용
#
# 환경변수 설정 방법:
#   옵션 A) .env 파일 생성 (권장)
#     echo 'export GOOGLE_API_KEY="your-key"' >> .env
#     echo 'export GOOGLE_CLOUD_API_KEY="your-key"' >> .env
#     echo 'export OPENROUTER_API_KEY="your-key"' >> .env
#
#   옵션 B) 직접 export
#     export GOOGLE_API_KEY="your-key"
#     export GOOGLE_CLOUD_API_KEY="your-key"
#     export OPENROUTER_API_KEY="your-key"
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

# 0. 로그 디렉토리 먼저 생성
mkdir -p logs

# 1. .env 파일 로드 (있으면)
if [ -f ".env" ]; then
    echo ""
    echo "[0/4] .env 파일 로드..."
    source .env
    echo "✓ .env 파일 로드 완료"
fi

# 1. 필수 환경변수 확인
echo ""
echo "[1/4] 환경변수 확인..."

MISSING_KEYS=0

if [ -z "$GOOGLE_CLOUD_API_KEY" ]; then
    echo "⚠ GOOGLE_CLOUD_API_KEY 설정 필요 (TTS용)"
    MISSING_KEYS=1
else
    echo "✓ GOOGLE_CLOUD_API_KEY 설정됨"
fi

if [ -z "$GOOGLE_API_KEY" ]; then
    echo "⚠ GOOGLE_API_KEY 설정 필요 (이미지 생성용)"
    MISSING_KEYS=1
else
    echo "✓ GOOGLE_API_KEY 설정됨"
fi

if [ -z "$OPENROUTER_API_KEY" ]; then
    echo "⚠ OPENROUTER_API_KEY 설정 필요 (대본 생성용)"
    # OPENROUTER는 필수가 아님 (이미지만 생성할 수도 있으므로)
else
    echo "✓ OPENROUTER_API_KEY 설정됨"
fi

if [ $MISSING_KEYS -eq 1 ]; then
    echo ""
    echo "환경변수 설정 방법:"
    echo "  1) .env 파일 생성:"
    echo "     echo 'export GOOGLE_API_KEY=\"your-key\"' >> .env"
    echo ""
    echo "  2) 또는 직접 export 후 다시 실행:"
    echo "     export GOOGLE_API_KEY=\"your-key\""
    echo ""
fi

# 1.5. venv 활성화 (있으면)
if [ -d "venv" ]; then
    echo ""
    echo "[1.5/4] venv 활성화..."
    source venv/bin/activate
    echo "✓ venv 활성화 완료"
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

echo ""
echo "로그 확인:"
echo "  서버: tail -f logs/drama_server.log"
echo "  ngrok: tail -f logs/ngrok.log"
echo ""
echo "종료하려면: bash scripts/stop_pc_server.sh"
