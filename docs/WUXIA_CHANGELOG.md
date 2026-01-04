# 혈영(血影) 무협 파이프라인 작업 로그

## 개요
- 시리즈명: 혈영 (Blood Shadow)
- 시트: AUTOMATION_SHEET_ID 내 "혈영" 탭
- 채널ID: UCRvuRallZ5S40Ccd3vhiFxQ

---

## 2026-01-04 (최신)

### 1. 대본 생성 모델 변경
- **변경 전**: Claude Opus 4.5 (`anthropic/claude-opus-4.5`)
- **변경 후**: Claude Sonnet 4 (`anthropic/claude-sonnet-4`)
- **이유**: 비용 효율성
- **파일**: `scripts/wuxia_pipeline/config.py`

### 2. 자동 대본 생성 로직 추가
- **파일**: `drama_server.py` (api_sheets_check_and_process 함수)
- **동작**:
  - cron이 혈영 시트 확인
  - "준비" 상태 + 대본 없음 → 대본 자동 생성
  - 생성 완료 → 상태를 "대기"로 변경
  - 다음 cron에서 영상 생성
- **커밋**: `c0e2155`

### 3. 감정 스토리텔링 프롬프트 재작성
- **파일**: `scripts/wuxia_pipeline/script_generator.py`
- **내용**:
  - 4대 원칙: 속내 보여주기, 대조/갭 활용, 작위적 감동 금지, 캐릭터 사연
  - 자연스러운 감정선 예시 추가
  - 캐릭터 관계 설정 (무영↔노인, 무영↔설하, 무영↔악역)
- **커밋**: `f7d4b33`

### 4. 대본 길이 설정
- **파일**: `scripts/wuxia_pipeline/config.py`
- **설정**:
  - 목표: 25,000자 (50분)
  - 범위: 22,000~28,000자
  - 챕터당: 5,000자 (5개 챕터)
  - 기준: 500자 ≈ 1분 (TTS 실측)
- **커밋**: `238f4d5`

### 5. A안 영상 구조 (장편 오디오북)
- **파일**: `drama_server.py`, `config.py`
- **내용**:
  - 시리즈 대표 이미지 1개 재사용 (비용 99% 절감)
  - 시리즈 통일 썸네일 (동일 이미지 + 텍스트 오버레이)
  - YouTube 제목 한자 병기: `[혈영(血影)] 제N화: 부제목 | 무협 오디오북`
- **커밋**: `6af5933`

### 6. 타입 힌트 에러 수정
- **파일**: `drama_server.py`
- **문제**: `Dict[str, Any]` 타입 힌트로 Python 3.13에서 NameError
- **해결**: `dict`로 변경
- **커밋**: `03140ba`

---

## 시트 구조

| 행 | A | B | ... | H | I | J |
|----|---|---|-----|---|---|---|
| 1 | 채널ID | UCRvuRallZ5S40Ccd3vhiFxQ | | | | |
| 2 | episode | title | ... | 상태 | thumbnail_copy | 대본 |
| 3 | EP001 | 운명의 시작 | ... | 준비 | | (자동생성) |

### 자동화 흐름
```
[준비] + 대본 없음
    ↓ cron (5분마다)
대본 자동 생성 (Claude Sonnet 4)
    ↓
상태 → [대기]
    ↓ 다음 cron
영상 생성 (TTS + 이미지 + 렌더링)
    ↓
YouTube 업로드
    ↓
상태 → [완료]
```

---

## 환경변수

| 변수 | 용도 |
|------|------|
| OPENROUTER_API_KEY | Claude Sonnet 4 대본 생성 |
| AUTOMATION_SHEET_ID | Google Sheets ID |
| GOOGLE_API_KEY | Gemini TTS |

---

## 파일 구조

```
scripts/wuxia_pipeline/
├── __init__.py
├── config.py          # 설정 (시리즈 정보, 대본 길이, API)
├── script_generator.py # 대본 생성 (Claude Sonnet 4)
├── multi_voice_tts.py  # 다중 음성 TTS
├── sheets.py          # Google Sheets 연동
└── run.py             # 파이프라인 오케스트레이터
```
