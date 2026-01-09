# 이세계 파이프라인 작업 로그

## 2026-01-08

### 22:00 - 세션 시작 (이전 세션 이어서)
- EP001 대본 검토
- 씬 제목 5개 제거 (TTS 읽기 방지)
  - "씬1: 오프닝 - 무림 전투" 등

### 22:30 - ARTIST 에이전트 프롬프트 업데이트
- 1980년대 스타일 → 2025년 트렌드 반영
- 추가된 키워드:
  - Korean manhwa style
  - xianxia aesthetic
  - teal and orange color grading
  - volumetric lighting
  - Netflix poster quality
- 파일: `scripts/isekai_pipeline/docs/agent_prompts.md`

### 23:00 - API 키 이슈 해결
- 기존 GOOGLE_API_KEY 유출로 차단됨
- 새 API 키 발급 및 .env 업데이트
- .env 위치: `/Users/samueljeong/Desktop/my_page_v2/.env`

### 23:15 - 썸네일 생성 테스트
- Imagen 4.0 API 사용 (imagen-4.0-generate-001)
- 생성 성공: `outputs/isekai/EP001/thumbnail_test.png`
- 결과: 이전보다 훨씬 좋은 품질

### 23:30 - 썸네일 PIL 텍스트 오버레이
- 폰트: AppleSDGothicNeo (Mac)
- 텍스트 배치:
  - "혈영 이세계편" → 왼쪽 상단 (금색)
  - "제1화" → 오른쪽 하단 (흰색)
  - "이방인" → 오른쪽 하단 (빨간색)
- 결과: `outputs/isekai/EP001/thumbnail_with_text.png`

### 23:45 - 씬 이미지 생성 테스트
- 1차: 무협 스타일로 잘못 생성
- 2차: 서양 판타지로 수정했으나 아저씨 등장
- 3차: 썸네일 주인공 묘사 그대로 사용 → 성공
- 결과: `outputs/isekai/EP001/scene_test.png`

### 00:00 - TTS 테스트
- Google Cloud TTS (ko-KR-Neural2-C) 테스트
- 음성 선택 논의 필요

---

### 00:30 - TTS 설정 업데이트
- 음성 변경: chirp3:Charon → **chirp3:Puck**
- 수정 파일:
  - `scripts/isekai_pipeline/docs/series_bible.md`
  - `scripts/isekai_pipeline/docs/agent_prompts.md`

### 00:45 - 동기화 이슈
- 회사에서 작업한 감정 흐름 규칙이 동기화 안 됨
- 원격 접속 느려서 푸시 포기
- **내일 회사에서 직접 동기화 필요**

---

## 2026-01-09

### 04:30 - ElevenLabs TTS 설정
- API 키 발급 및 .env 추가
- 모델 비교 테스트:
  - Multilingual V2: 1크레딧/글자
  - Eleven V3: 1크레딧/글자 (감정 표현 우수)
  - Flash V2.5: 0.5크레딧/글자 (저렴)
- **Creator 플랜**: 100,000자/월 → 약 8편 가능

### 04:45 - 한국어 남성 음성 테스트
- Jung_Narrative (내레이션 전용) 선택
- Voice ID: `aurnUodFzOtofecLd3T1`
- V3 모델 호환 확인

### 05:00 - EP001 TTS 생성 완료
- 대본 정리: `.....` 등 부호 제거 (12,140자 → 12,054자)
- TTS 생성: Jung_Narrative V3
- 청크 3개로 분할 (4,500자 제한)
- **결과**:
  - 파일: `EP001_elevenlabs.mp3`
  - 재생 시간: **23분 58초**
  - 사용 크레딧: 12,048자
  - 남은 크레딧: 약 87,952자

### 05:15 - 영상 생성 완료
- 이미지: `scene_test.png` (1408x768)
- 오디오: `EP001_elevenlabs.mp3`
- **결과**:
  - 파일: `EP001_elevenlabs_video.mp4`
  - 크기: 79.2 MB
  - 재생 시간: 24분

### YouTube 업로드 대기
- 로컬에 YouTube OAuth 인증 미설정
- `.env`에 `YOUTUBE_CLIENT_ID`, `YOUTUBE_CLIENT_SECRET` 필요
- 또는 Render 서버의 `/api/youtube/upload` 사용

---

## 미해결 이슈

### 회사-집 동기화
- [ ] 회사 브랜치에서 감정 흐름 규칙 가져오기
- [ ] 퇴근 전 푸시 습관화 (`git add -A && git push`)

### 이미지 프롬프트 표준화
- [ ] EP001_image_prompts.json 업데이트 필요
- 씬 이미지는 1개만 사용 (메인 이미지)

---

## 파일 위치 참고

| 파일 | 경로 |
|------|------|
| .env | `/Users/samueljeong/Desktop/my_page_v2/.env` |
| 에이전트 프롬프트 | `scripts/isekai_pipeline/docs/agent_prompts.md` |
| EP001 대본 | `outputs/isekai/EP001/EP001_script.txt` |
| EP001 이미지 프롬프트 | `outputs/isekai/EP001/EP001_image_prompts.json` |
| 썸네일 | `outputs/isekai/EP001/thumbnail_with_text.png` |
| 씬 이미지 | `outputs/isekai/EP001/scene_test.png` |
