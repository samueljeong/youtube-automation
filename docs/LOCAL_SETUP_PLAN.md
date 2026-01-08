# 로컬 영상 생성 환경 구축 계획

> **목표**: Claude Code에서 명령 → Mac M1 서버에서 영상 생성 → YouTube 업로드
> **환경**: Mac M1 iMac (상시 전원)
> **최종 수정**: 2026-01-07

---

## 📋 전체 진행 상황

| 단계 | 설명 | 상태 |
|------|------|------|
| 1 | 환경 점검 | ⬜ 대기 |
| 2 | 환경변수 설정 | ⬜ 대기 |
| 3 | 프로젝트 클론 및 패키지 설치 | ⬜ 대기 |
| 4 | 로컬 서버 실행 테스트 | ⬜ 대기 |
| 5 | MCP 서버 연결 (Claude Code ↔ PC) | ⬜ 대기 |
| 6 | 영상 생성 테스트 | ⬜ 대기 |
| 7 | 자동 실행 설정 (선택) | ⬜ 대기 |

---

## 단계 1: 환경 점검

### 체크리스트

- [ ] Python 버전 확인 (3.9 이상 필요)
- [ ] FFmpeg 버전 확인
- [ ] Git 버전 확인
- [ ] Node.js 설치 확인 (MCP용)

### 실행 명령 (터미널에서)

```bash
# 모든 환경 한번에 점검
echo "=== Python ===" && python3 --version && \
echo "=== FFmpeg ===" && ffmpeg -version | head -1 && \
echo "=== Git ===" && git --version && \
echo "=== Node.js ===" && node --version 2>/dev/null || echo "Node.js 없음 - 설치 필요"
```

### Node.js 없으면 설치

```bash
brew install node
```

### 예상 결과

```
=== Python ===
Python 3.11.x
=== FFmpeg ===
ffmpeg version 6.x
=== Git ===
git version 2.x
=== Node.js ===
v20.x.x
```

### 결과 기록

```
실행 날짜:
Python:
FFmpeg:
Git:
Node.js:
```

---

## 단계 2: 환경변수 설정

### 필요한 API 키 목록

| 환경변수 | 용도 | 발급처 |
|----------|------|--------|
| `GOOGLE_API_KEY` | Gemini API (이미지/텍스트) | Google AI Studio |
| `GOOGLE_CLOUD_API_KEY` | Google Cloud TTS | Google Cloud Console |
| `GOOGLE_SERVICE_ACCOUNT_JSON` | Chirp3 TTS, Sheets | Google Cloud Console |
| `OPENAI_API_KEY` | GPT API | OpenAI Platform |
| `YOUTUBE_CLIENT_ID` | YouTube 업로드 | Google Cloud Console |
| `YOUTUBE_CLIENT_SECRET` | YouTube 업로드 | Google Cloud Console |

### 체크리스트

- [ ] GOOGLE_API_KEY 발급/확인
- [ ] GOOGLE_CLOUD_API_KEY 발급/확인
- [ ] GOOGLE_SERVICE_ACCOUNT_JSON 생성
- [ ] OPENAI_API_KEY 발급/확인
- [ ] YOUTUBE_CLIENT_ID 확인
- [ ] YOUTUBE_CLIENT_SECRET 확인
- [ ] .env 파일 생성

### 실행 명령

```bash
# 프로젝트 폴더로 이동
cd ~/my_page_v2  # 또는 프로젝트 경로

# .env 파일 생성
cat > .env << 'EOF'
# Google AI (Gemini)
GOOGLE_API_KEY=여기에_키_입력

# Google Cloud (TTS, Sheets)
GOOGLE_CLOUD_API_KEY=여기에_키_입력
GOOGLE_SERVICE_ACCOUNT_JSON={"type":"service_account",...전체JSON...}

# OpenAI
OPENAI_API_KEY=여기에_키_입력

# YouTube OAuth
YOUTUBE_CLIENT_ID=여기에_입력
YOUTUBE_CLIENT_SECRET=여기에_입력

# 서버 설정
FLASK_ENV=development
PORT=5000
EOF

echo "✅ .env 파일 생성 완료"
```

### 환경변수 로드 확인

```bash
# .zshrc에 자동 로드 추가 (Mac 기본 셸)
echo 'export $(cat ~/my_page_v2/.env | xargs)' >> ~/.zshrc
source ~/.zshrc

# 확인
echo $GOOGLE_API_KEY | head -c 10
```

---

## 단계 3: 프로젝트 클론 및 패키지 설치

### 체크리스트

- [ ] Git 저장소 클론
- [ ] 가상환경 생성
- [ ] 패키지 설치
- [ ] 설치 확인

### 실행 명령

```bash
# 1. 프로젝트 클론 (이미 있으면 스킵)
cd ~
git clone https://github.com/samueljeong/my_page_v2.git
cd my_page_v2

# 2. 가상환경 생성
python3 -m venv venv
source venv/bin/activate

# 3. 패키지 설치
pip install --upgrade pip
pip install -r requirements.txt

# 4. 추가 패키지 (로컬 전용)
pip install python-dotenv

# 5. 설치 확인
python -c "import flask; import openai; print('✅ 패키지 설치 완료')"
```

---

## 단계 4: 로컬 서버 실행 테스트

### 체크리스트

- [ ] 서버 시작
- [ ] 헬스체크 응답 확인
- [ ] TTS API 테스트
- [ ] 이미지 생성 테스트

### 실행 명령

```bash
# 터미널 1: 서버 시작
cd ~/my_page_v2
source venv/bin/activate
python drama_server.py

# 터미널 2: 테스트 (새 터미널 열기)
# 헬스체크
curl http://localhost:5000/health

# TTS 테스트
curl -X POST http://localhost:5000/api/drama/generate-tts \
  -H "Content-Type: application/json" \
  -d '{"text": "안녕하세요 테스트입니다", "speaker": "ko-KR-Neural2-C"}'
```

### 예상 결과

```json
{"ok": true, "status": "healthy"}
{"ok": true, "audioUrl": "data:audio/mp3;base64,..."}
```

---

## 단계 5: MCP 서버 연결 (Claude Code ↔ PC)

### 개요

MCP(Model Context Protocol)를 사용하면 Claude Code가 당신 PC의 터미널을 직접 사용할 수 있습니다.

### 체크리스트

- [ ] MCP 서버 패키지 설치
- [ ] MCP 서버 실행
- [ ] Claude Code에서 연결 테스트

### 실행 명령

```bash
# 1. MCP 서버 설치
npm install -g @anthropic-ai/claude-code-mcp

# 2. MCP 서버 실행 (프로젝트 폴더에서)
cd ~/my_page_v2
claude-code-mcp

# 출력 예시:
# MCP server listening on ws://localhost:3000
# Connection token: xxxx-xxxx-xxxx
```

### Claude Code에서 연결

Claude Code에서 MCP 서버에 연결하면:
- 당신 PC의 터미널 명령 실행 가능
- 파일 읽기/쓰기 가능
- 서버 직접 제어 가능

---

## 단계 6: 영상 생성 테스트

### 체크리스트

- [ ] 테스트 대본 준비
- [ ] TTS 생성 확인
- [ ] 이미지 생성 확인
- [ ] 영상 합성 확인
- [ ] YouTube 업로드 테스트

### 테스트 API 호출

```bash
# 전체 파이프라인 테스트 (간단한 버전)
curl -X POST http://localhost:5000/api/drama/generate-video \
  -H "Content-Type: application/json" \
  -d '{
    "images": ["https://example.com/image1.jpg"],
    "audioUrl": "/path/to/audio.mp3",
    "resolution": "1080p"
  }'
```

---

## 단계 7: 자동 실행 설정 (선택)

### Mac 시작 시 자동 실행

```bash
# LaunchAgent 생성
cat > ~/Library/LaunchAgents/com.drama.server.plist << 'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.drama.server</string>
    <key>ProgramArguments</key>
    <array>
        <string>/bin/bash</string>
        <string>-c</string>
        <string>cd ~/my_page_v2 && source venv/bin/activate && python drama_server.py</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
</dict>
</plist>
EOF

# 활성화
launchctl load ~/Library/LaunchAgents/com.drama.server.plist
```

---

## 🔧 문제 해결

### 자주 발생하는 문제

| 문제 | 원인 | 해결 |
|------|------|------|
| `ModuleNotFoundError` | 패키지 미설치 | `pip install 패키지명` |
| `GOOGLE_API_KEY not found` | 환경변수 미설정 | `.env` 파일 확인 |
| `Connection refused` | 서버 미실행 | `python drama_server.py` 실행 |
| `FFmpeg not found` | FFmpeg 미설치 | `brew install ffmpeg` |

---

## 📝 진행 기록

### 2026-01-07

- [ ] 계획 문서 생성
- [ ] 단계 1 시작 예정

### 다음 세션에서 할 일

1. 단계 1 환경 점검 실행
2. 결과 이 문서에 기록
3. 단계 2 진행

---

## 📞 도움 요청 방법

막히는 부분이 있으면:

1. 어떤 단계에서 막혔는지
2. 실행한 명령어
3. 에러 메시지 전체

를 Claude Code에 알려주세요.
