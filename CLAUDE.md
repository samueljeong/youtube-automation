# Drama Page 재구축 프로젝트

## 현재 브랜치
`claude/continue-drama-session-01UA73Rm8DTaYNdoLjaZGFiA`

## 프로젝트 개요
Drama Lab - AI 기반 드라마 영상 자동 생성 시스템

## 작업 진행 상황

### 완료된 작업 (백엔드 파이프라인)
- [x] Step1: 공식 스펙 확정 - 스키마 및 프롬프트
- [x] Step2: 이미지 생성 스펙 및 뼈대 코드
- [x] Step3: TTS & 자막 생성 모듈 구축
- [x] Step4: 영상 조립 모듈 구축
- [x] Step5: YouTube 업로드 자동화 모듈 구축
- [x] 전체 파이프라인 통합 컨트롤러 구현

### 완료된 작업 (프론트엔드 UI) - 2024-11-29
- [x] drama.html - 전체 5스텝 UI 완성
- [x] drama-main.js - 메인 모듈 (스텝 전환, 세션 관리)
- [x] drama-step1.js - 대본 생성 모듈
- [x] drama-step2.js - 이미지 생성 모듈 (캐릭터/씬 분석)
- [x] drama-step3.js - TTS 음성합성 모듈
- [x] drama-step4.js - 영상 제작 모듈
- [x] drama-step5.js - YouTube 업로드 모듈
- [x] drama-session.js - 세션 및 Q&A 기록 관리
- [x] drama-utils.js - 유틸리티 함수
- [x] drama.css - 전체 스타일 완성 (character-card, scene-card 스타일 포함)

## 파일 구조

### 백엔드
- `drama_server.py` (6241줄) - 메인 서버, 모든 API 엔드포인트 포함

### 프론트엔드 (완성됨)
- `templates/drama.html` - 메인 템플릿 (5스텝 UI)
- `static/css/drama.css` - 스타일시트 (1100줄+)
- `static/js/drama-main.js` - 메인 모듈 (348줄)
- `static/js/drama-step1.js` - 대본 생성 (275줄)
- `static/js/drama-step2.js` - 이미지 생성 (332줄)
- `static/js/drama-step3.js` - TTS 음성합성 (289줄)
- `static/js/drama-step4.js` - 영상 제작 (275줄)
- `static/js/drama-step5.js` - YouTube 업로드 (379줄)
- `static/js/drama-utils.js` - 유틸리티 함수 (194줄)
- `static/js/drama-session.js` - 세션 관리 (250줄)

### 가이드/설정
- `guides/drama.json` - 드라마 설정
- `guides/nostalgia-drama-prompts.json` - 향수 드라마 프롬프트
- `guides/nostalgia-drama-sample.json` - 샘플 데이터
- `guides/korean-senior-image-prompts.json` - **한국인 시니어 이미지 프롬프트 가이드 (NEW)**

## 알려진 이슈 (drama_issue_code.md 참조)

### 1. ~~TTS 음성 생성 오류~~ ✅ 해결됨 (2024-11-29)
- ~~Google TTS API 5000바이트 제한 초과 문제~~
- **해결책**: 새 TTS 파이프라인 구현
  - `tts_chunking.py`: 문장 단위 분리 + 바이트 제한 청킹
  - `tts_service.py`: 청크별 TTS + FFmpeg 병합 + SRT 자막 생성
  - 새 API: `POST /api/drama/step3/tts`

### 2. ~~한국인 이미지 생성 문제~~ ✅ 개선됨 (2024-11-29)
- ~~한국 할머니/할아버지 생성 시 외국인 이미지 출력~~
- **해결책**: 상세한 한국인 시니어 프롬프트 가이드 추가
  - `guides/korean-senior-image-prompts.json`: 한국인 시니어 이미지 프롬프트 가이드
  - 할머니(halmeoni)/할아버지(harabeoji) 별도 프롬프트 정의
  - 한국인 얼굴 특징 상세 명시: 둥근 얼굴, 홑꺼풀/속쌍꺼풀, 한국인 피부톤
  - 1970~80년대 빈티지 필름 스타일 적용: film grain, faded warm colors

### 3. ~~Step2 캐릭터 일관성 문제~~ ✅ 해결됨 (2024-11-29)
- ~~주인공 카드와 씬 이미지의 인물이 분리됨~~
- **해결책**: 씬 프롬프트에 main_character 정보 강제 포함
  - `drama-step2.js`: `buildCharacterConsistencyPrompt()` 함수 추가
  - 씬 이미지 생성 시 주인공 정보를 프롬프트 맨 앞에 배치
  - 한국인 할머니/할아버지 전용 일관성 프롬프트 적용

### 4. ~~Step3 TTS 설명문 읽기 문제~~ ✅ 해결됨 (2024-11-29)
- ~~TTS가 "1. 주인공 설정 – 이름: 이순자..." 같은 메타 설명을 읽음~~
- **해결책**: 순수 나레이션만 추출하도록 수정
  - `drama-step3.js`: `getScriptTexts()` 함수 개선
  - 메타 설명 패턴 필터링 추가 (주인공 설정, 스토리 컨셉, 배경 등)
  - `extractNarrationFromScene()` 함수로 순수 나레이션만 추출

### 5. ~~Step4 500 에러~~ ✅ 디버깅 강화 (2024-11-29)
- ~~`/api/drama/generate-video` 500 에러 발생~~
- **해결책**: 상세 디버깅 로그 추가
  - 요청 데이터 구조 출력
  - cuts 배열 상세 정보 출력
  - traceback 출력 추가

### 6. ~~Step4 영상 생성 타임아웃~~ ✅ 병렬 처리로 해결 (2024-12-01)
- ~~씬별 순차 처리로 300초 타임아웃 발생~~
- **해결책**: ThreadPoolExecutor를 사용한 병렬 처리 도입
  - `_create_scene_clip()`: 개별 씬 클립 생성 함수 분리
  - `_generate_video_with_cuts()`: 병렬 처리 적용
  - 최대 4개 워커로 씬 클립 동시 생성
  - 모든 클립 생성 후 순서대로 concat 병합
  - 예상 속도 향상: 4배 (10개 씬 기준)

## 주요 API 엔드포인트 (drama_server.py)
- `/api/drama/gpt-plan-step1` - 대본 생성
- `/api/drama/analyze-characters` - 캐릭터/씬 분석
- `/api/drama/generate-image` - 이미지 생성
- `/api/drama/generate-tts` - TTS 음성 생성 (기존)
- `/api/drama/step3/tts` - **새 TTS 파이프라인 (5000바이트 제한 해결 + SRT 자막)**
- `/api/drama/generate-video` - 영상 제작
- `/api/drama/video-status/{jobId}` - 영상 작업 상태 확인
- `/api/youtube/auth-status` - YouTube 인증 상태
- `/api/youtube/upload` - YouTube 업로드

## 다음 세션에서 할 일
1. ~~drama.html UI 완성~~ ✅ 완료
2. ~~각 step별 JS 모듈 구현~~ ✅ 완료
3. ~~TTS 5000바이트 제한 해결~~ ✅ 완료
4. ~~이미지 프롬프트 튜닝 - 한국인/70-80년대 감도~~ ✅ 완료
5. ~~실제 동작 테스트~~ ✅ 완료 (2024-12-01)
6. ~~전체 파이프라인 통합 테스트~~ ✅ 완료 - YouTube 업로드 성공!

## 🎉 프로젝트 완료 (2024-12-01)
- 전체 5스텝 파이프라인 정상 동작 확인
- Step1(대본) → Step2(이미지) → Step3(TTS) → Step4(영상) → Step5(YouTube 업로드) 완주

## 🆕 수동 대본 입력 모드 (2024-12-01)
- Step1 UI 변경: 자동 생성 → 수동 입력 5개 박스
  - 박스1: 주인공 소개 + 이미지 프롬프트
  - 박스2-5: 씬1-4 나레이션
- YouTube 인증을 Step1 상단으로 이동
- 주인공 성별 선택 → TTS 음성 자동 매칭
  - 여성: ko-KR-Wavenet-A / Neural2-A
  - 남성: ko-KR-Wavenet-C / Neural2-B
- TTS 음성 품질 선택 (Standard/Wavenet/Neural2)

## 알려진 이슈 (진행 중)
- 영상에 소리/자막 누락 문제 - 서버 로그 확인 필요
  - `[DRAMA-PARALLEL] 씬 X: 오디오=True/False` 로그 확인

## 참고 사항
- 이미지 생성: Gemini (기본) / FLUX.1 Pro / DALL-E 3 지원
- TTS: Google Cloud TTS (기본) / 네이버 클로바 지원
- 백엔드/프론트엔드 파이프라인 모두 완성 상태
- 실행을 위해 필요한 환경 변수: OPENAI_API_KEY, GOOGLE_API_KEY 등
