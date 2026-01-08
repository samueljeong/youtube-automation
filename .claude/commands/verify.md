# 코드 검증 (Verify)

작업 완료 후 코드가 정상 동작하는지 검증합니다.

## 사용법

`/verify` - 전체 검증 실행

## 검증 단계

### 1단계: 문법 검사
```bash
python -m py_compile drama_server.py
python -m py_compile blueprints/*.py
```

### 2단계: 린터 검사
```bash
ruff check drama_server.py blueprints/
```

### 3단계: Import 검증
```bash
python -c "import drama_server; print('Import OK')"
```

### 4단계: 서버 시작 테스트 (선택)
```bash
timeout 5 python drama_server.py || true
```

## 검증 결과

| 결과 | 의미 | 행동 |
|------|------|------|
| ✅ 통과 | 모든 검사 통과 | 커밋 가능 |
| ⚠️ 경고 | 린터 경고 있음 | 검토 후 커밋 |
| ❌ 실패 | 문법/import 오류 | 수정 필요 |

## 자동 검증 항목

1. **Python 문법**: py_compile로 문법 오류 검사
2. **Import 체인**: 모든 import가 정상 동작하는지 확인
3. **린터 규칙**: ruff 규칙 위반 검사
4. **타입 힌트**: 주요 함수 타입 힌트 확인

## 도메인별 추가 검증

### API 엔드포인트
```bash
curl -s http://localhost:5000/health | jq .
```

### TTS 기능
```bash
curl -X POST http://localhost:5000/api/drama/generate-tts \
  -H "Content-Type: application/json" \
  -d '{"text": "테스트", "speaker": "ko-KR-Neural2-C"}' | jq .ok
```

### 파이프라인 상태
```bash
curl -s http://localhost:5000/api/sheets/status | jq .
```
