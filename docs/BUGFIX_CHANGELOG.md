# 버그 수정 이력

## 2025-12-07: Worker OOM 크래시 수정

**증상**: 영상 생성 3단계에서 Worker가 SIGKILL로 종료
```
[2025-12-07 04:25:06 +0000] [38] [ERROR] Worker (pid:58) was sent SIGKILL! Perhaps out of memory?
```

**원인**: `subprocess.run(capture_output=True)`가 FFmpeg의 모든 stdout/stderr를 메모리에 버퍼링. FFmpeg는 인코딩 중 수백MB의 출력을 생성하여 2GB 메모리 초과.

**수정** (`drama_server.py`):
- 11621-11623행 (concat): `capture_output=True` → `stdout=DEVNULL, stderr=PIPE`
- 11672-11677행 (subtitle burn-in): `capture_output=True` → `stdout=DEVNULL, stderr=PIPE`
- subprocess 완료 후 `del` + `gc.collect()` 추가

---

## 2025-12-07: YouTube 업로드 전 영상 검증 강화

**증상**: YouTube 업로드 성공했으나 영상이 Studio에 표시되지 않음

**원인**:
1. 손상된 영상 파일이 업로드되어 YouTube 처리 중 자동 삭제됨
2. 검증 Exception 발생 시 업로드를 계속 진행하는 버그

**수정** (`drama_server.py` 9575-9683행):
- **1단계: ffprobe 메타데이터 검증**
  - duration (최소 1초)
  - size (최소 100KB)
  - video/audio 스트림 존재 여부 (둘 다 필수)
  - 해상도 (최소 100x100)
  - 코덱 정보 로깅
- **2단계: 실제 프레임 디코딩 테스트**
  - ffmpeg로 첫 1초 디코딩 시도
  - 디코딩 실패 시 업로드 차단
- **3단계: YouTube 업로드 후 상태 확인**
  - videos().list API로 uploadStatus/rejectionReason 확인
  - 거부/실패 시 에러 반환
- **Exception 처리 수정**: 검증 실패 시 업로드 차단 (이전: 계속 진행)
- **이미지 생성 실패 체크 추가** (15104-15109행): 모든 이미지 생성 실패 시 중단

---

## 2025-12-07: YouTube 재생 호환성 수정

**증상**: 영상 업로드 성공했으나 YouTube에서 재생 불가

**원인**:
1. `-movflags +faststart` 없음 (스트리밍 호환 문제)
2. 오디오 `-c:a copy` 사용 (코덱 호환성 문제)
3. 클립 간 오디오 설정 불일치

**수정** (`drama_server.py`):
- **자막 burn-in** (11838-11844행): YouTube 호환 설정 추가
  - `-profile:v high -level 4.0`
  - `-c:a aac -b:a 128k -ar 44100`
  - `-movflags +faststart`
- **클립 생성** (11714-11739행): 오디오 설정 통일
  - 모든 클립에 `-ar 44100` 추가
- **Fallback 재인코딩**: 자막 burn-in 실패 시에도 YouTube 호환으로 재인코딩

---

## 2025-12-07: 새로운 기능 추가

**쇼츠 자동 생성 및 업로드**
- GPT-5.1이 하이라이트 씬 선택 (`video_effects.shorts.highlight_scenes`)
- 세로 영상(9:16) 자동 변환 (`_generate_shorts_video()`)
- 원본 영상 링크 포함하여 업로드
- Google Sheets O열에 쇼츠 URL 저장

**전환 효과 (Transitions)**
- 씬 사이에 crossfade/fade_black/fade_white 효과 적용
- GPT-5.1이 자동 선택 (`video_effects.transitions`)
- `_apply_transitions()` 함수로 FFmpeg xfade 필터 적용

**YouTube 자막 자동 업로드**
- `_upload_youtube_captions()` 함수 추가
- SRT 파일을 YouTube Captions API로 직접 업로드

---

## 2025-12-08: Google Sheets API 재시도 로직 추가

**증상**: 간헐적으로 Google Sheets API 호출 실패
```
[SHEETS] 읽기 실패: <HttpError 500 when requesting https://sheets.googleapis.com/v4/spreadsheets/... returned "Authentication backend unknown error.". Details: "Authentication backend unknown error.">
```

**원인**:
1. Google API의 일시적 백엔드 오류 (Authentication backend unknown error)
2. 재시도 로직 없이 즉시 실패 처리
3. API 실패와 빈 시트를 구분하지 않음 (`[]` 반환으로 동일 처리)

**수정** (`drama_server.py`):
- **`sheets_read_rows()` (17738-17787행)**: 재시도 로직 추가
  - 최대 3회 재시도
  - 지수 백오프 (2초, 4초, 8초)
  - 일시적 오류 패턴 자동 감지 (500, 502, 503, 504, timeout, backend error 등)
  - API 실패 시 `None` 반환 (빈 시트 `[]`와 구분)
- **`sheets_update_cell()` (17790-17843행)**: 동일한 재시도 로직 추가
- **`api_sheets_check_and_process()` (19432-19444행)**: API 실패와 빈 시트 구분
  - `None` (API 실패) → HTTP 503 에러 반환
  - `[]` (빈 시트) → 정상 응답 (처리할 작업 없음)

---

## 2026-01-10: FFmpeg concat + 자막 싱크 불일치 수정

**증상**: 한국사 EP018 영상에서 자막이 음성과 점점 더 어긋남 (뒤로 갈수록 심해짐)

**원인**:
1. FFmpeg `concat` demuxer로 이미지 슬라이드쇼 생성 시 `-shortest` 옵션이 제대로 작동하지 않음
2. 비디오 스트림: **1072초**, 오디오 스트림: **998초** → 73초 차이
3. 자막은 오디오 타이밍 기준인데 비디오가 더 느리게 진행 → 자막이 점점 빨리 나타남

**수정** (`scripts/history_pipeline/renderer.py` 또는 수동 렌더링 시):
- `-shortest` 옵션 대신 `-t` 옵션으로 오디오 길이에 맞춰 명시적으로 비디오 길이 제한
```bash
# 기존 (문제)
ffmpeg -f concat -safe 0 -i images.txt -i audio.mp3 -shortest ...

# 수정 (해결)
DURATION=$(ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 audio.mp3)
ffmpeg -f concat -safe 0 -i images.txt -i audio.mp3 -t $DURATION ...
```

**검증 방법**:
```bash
# 비디오와 오디오 스트림 길이가 일치하는지 확인
ffprobe -v error -select_streams v:0 -show_entries stream=duration -of default=noprint_wrappers=1:nokey=1 output.mp4
ffprobe -v error -select_streams a:0 -show_entries stream=duration -of default=noprint_wrappers=1:nokey=1 output.mp4
```

**교훈**: FFmpeg `concat` demuxer와 `-shortest` 조합은 신뢰할 수 없음. 항상 `-t` 옵션으로 명시적 길이 제한 필요.
