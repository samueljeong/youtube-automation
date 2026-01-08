# 로컬 테스트 실행

로컬 환경에서 서버를 실행하고 테스트합니다.

## 서버 시작

```bash
python drama_server.py
```

## API 테스트

### 헬스체크
```bash
curl http://localhost:5000/health
```

### TTS 테스트
```bash
curl -X POST http://localhost:5000/api/drama/generate-tts \
  -H "Content-Type: application/json" \
  -d '{"text": "테스트 음성입니다.", "speaker": "ko-KR-Neural2-C"}'
```

### 파이프라인 상태
```bash
curl http://localhost:5000/api/sheets/status
```

## Python 문법 검사

```bash
python -m py_compile drama_server.py
python -m py_compile blueprints/*.py
```

## 환경변수 확인

필수 환경변수:
- GOOGLE_API_KEY
- GOOGLE_CLOUD_API_KEY
- GOOGLE_SERVICE_ACCOUNT_JSON
- OPENAI_API_KEY

## 포트 확인

```bash
lsof -i :5000
```
