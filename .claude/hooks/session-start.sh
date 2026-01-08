#!/bin/bash
# Claude Code 세션 시작 시 자동 실행되는 코드 정리 스크립트

echo "🔍 코드 상태 점검 중..."

# 1. Python 문법 검사
echo ""
echo "📝 Python 문법 검사..."
if python3 -m py_compile drama_server.py 2>/dev/null; then
    echo "  ✅ drama_server.py - OK"
else
    echo "  ❌ drama_server.py - 문법 오류 있음!"
fi

# 2. Blueprint 문법 검사
for file in blueprints/*.py; do
    if [ -f "$file" ]; then
        if python3 -m py_compile "$file" 2>/dev/null; then
            echo "  ✅ $file - OK"
        else
            echo "  ❌ $file - 문법 오류!"
        fi
    fi
done

# 3. 린터 경고 개수
echo ""
echo "🔧 린터 검사 (ruff)..."
WARNING_COUNT=$(ruff check drama_server.py blueprints/ 2>/dev/null | wc -l)
if [ "$WARNING_COUNT" -gt 0 ]; then
    echo "  ⚠️ 린터 경고 ${WARNING_COUNT}개 발견"
    echo "  💡 '/simplify drama_server.py' 로 정리 가능"
else
    echo "  ✅ 린터 경고 없음"
fi

# 4. 코드 라인 수
echo ""
echo "📊 코드 현황..."
DRAMA_LINES=$(wc -l < drama_server.py 2>/dev/null || echo "0")
echo "  - drama_server.py: ${DRAMA_LINES}줄"

# 5. Git 상태
echo ""
echo "📁 Git 상태..."
CHANGED=$(git status --porcelain 2>/dev/null | wc -l)
if [ "$CHANGED" -gt 0 ]; then
    echo "  ⚠️ 커밋되지 않은 변경사항 ${CHANGED}개"
else
    echo "  ✅ 작업 디렉토리 깨끗함"
fi

echo ""
echo "✨ 점검 완료!"
