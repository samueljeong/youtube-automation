# 소셜 미디어 자동 업로드 가이드

이 문서는 Instagram과 TikTok에 묵상 비디오를 자동으로 업로드하는 기능에 대해 설명합니다.

## 📋 목차

1. [기능 개요](#기능-개요)
2. [설치 및 설정](#설치-및-설정)
3. [환경변수 설정](#환경변수-설정)
4. [사용 방법](#사용-방법)
5. [API 레퍼런스](#api-레퍼런스)
6. [문제 해결](#문제-해결)

---

## 기능 개요

### 지원하는 플랫폼

- **Instagram Reels**: 자동 업로드 및 캡션 추가
- **TikTok**: 자동 업로드 및 캡션 추가

### 주요 기능

✅ 여러 플랫폼에 동시 업로드
✅ 자동 해시태그 추가 (플랫폼별 최적화)
✅ 스케줄러 통합 (일일 자동 업로드)
✅ 헤드리스 모드 지원 (백그라운드 실행)
✅ 업로드 결과 로깅

---

## 설치 및 설정

### 1. 의존성 설치

```bash
pip install -r requirements.txt
playwright install chromium
```

**중요**: Playwright를 처음 사용하는 경우 브라우저 설치가 필요합니다:

```bash
playwright install
```

### 2. 파일 구조

```
my_page_v2/
├── instagram_uploader.py      # Instagram 업로드 모듈
├── tiktok_uploader.py          # TikTok 업로드 모듈
├── social_media_uploader.py    # 멀티 플랫폼 통합 모듈
├── devotional_scheduler.py     # 스케줄러 (업로드 통합)
└── test_social_media_upload.py # 테스트 스크립트
```

---

## 환경변수 설정

### `.env` 파일 생성

프로젝트 루트에 `.env` 파일을 생성하고 다음 내용을 추가하세요:

```bash
# Instagram 자격증명
INSTAGRAM_USERNAME=your_instagram_username
INSTAGRAM_PASSWORD=your_instagram_password

# TikTok 자격증명
TIKTOK_USERNAME=your_tiktok_email_or_username
TIKTOK_PASSWORD=your_tiktok_password

# OpenAI API (묵상 메시지 생성용)
OPENAI_API_KEY=sk-...
```

### 보안 주의사항

⚠️ **중요**: `.env` 파일을 절대 Git에 커밋하지 마세요!

`.gitignore`에 다음 내용이 있는지 확인:
```
.env
*.env
```

### 환경변수 직접 설정 (Linux/Mac)

```bash
export INSTAGRAM_USERNAME=your_username
export INSTAGRAM_PASSWORD=your_password
export TIKTOK_USERNAME=your_username
export TIKTOK_PASSWORD=your_password
```

---

## 사용 방법

### 1. 기본 사용법

#### 단일 플랫폼 업로드

```python
from social_media_uploader import SocialMediaUploader

uploader = SocialMediaUploader()

# Instagram에만 업로드
uploader.upload_to_instagram(
    video_path="output/videos/devotional_20241115_0900.mp4",
    caption="오늘의 묵상 메시지 🙏",
    headless=True
)

# TikTok에만 업로드
uploader.upload_to_tiktok(
    video_path="output/videos/devotional_20241115_0900.mp4",
    caption="오늘의 묵상 메시지 🙏",
    headless=True
)
```

#### 멀티 플랫폼 업로드

```python
# 모든 플랫폼에 업로드
results = uploader.upload_to_all(
    video_path="output/videos/devotional_20241115_0900.mp4",
    caption="오늘의 묵상 메시지 🙏",
    platforms=None,  # None = 모든 플랫폼
    headless=True
)

# 결과 확인
for platform, success in results.items():
    print(f"{platform}: {'성공' if success else '실패'}")
```

#### 특정 플랫폼만 선택

```python
# Instagram과 TikTok 중 Instagram만
results = uploader.upload_to_all(
    video_path="output/videos/devotional_20241115_0900.mp4",
    caption="오늘의 묵상 메시지 🙏",
    platforms=["instagram"],  # TikTok 제외
    headless=True
)
```

### 2. 스케줄러와 통합

#### 자동 업로드 활성화

```python
from devotional_scheduler import DevotionalScheduler

scheduler = DevotionalScheduler()

# 비디오 생성 + 자동 업로드
video_path = scheduler.create_daily_video(
    time_of_day="morning",
    use_tts=True,
    use_theme=True,
    upload_to_social=True,  # 자동 업로드 활성화
    platforms=None  # None = 모든 플랫폼
)
```

#### 스케줄 설정 (매일 자동 실행 + 업로드)

```python
# 매일 오전 9시, 저녁 8시에 비디오 생성 + 자동 업로드
scheduler.schedule_daily_tasks(
    morning_hour=9,
    evening_hour=20,
    upload_to_social=True,  # 자동 업로드 활성화
    platforms=["instagram", "tiktok"]  # 모든 플랫폼
)

scheduler.start()

# 백그라운드에서 계속 실행
import time
while True:
    time.sleep(60)
```

### 3. 테스트 스크립트 실행

```bash
# 전체 테스트 (생성 + 업로드)
python test_social_media_upload.py 1

# 비디오 생성만
python test_social_media_upload.py 2

# 자격증명 확인만
python test_social_media_upload.py 3

# 업로드만 (기존 비디오)
python test_social_media_upload.py 4

# 통합 워크플로우 (생성 + 자동 업로드)
python test_social_media_upload.py 5
```

---

## API 레퍼런스

### SocialMediaUploader

#### `__init__()`

소셜 미디어 업로더 초기화. 환경변수에서 자격증명을 로드합니다.

#### `upload_to_all(video_path, caption, platforms, headless)`

여러 플랫폼에 동시 업로드

**Parameters:**
- `video_path` (str): 업로드할 비디오 파일 경로
- `caption` (str): 캡션 텍스트 (기본: "")
- `platforms` (List[str] | None): 업로드할 플랫폼 리스트 (기본: None = 모두)
- `headless` (bool): 헤드리스 모드 (기본: True)

**Returns:**
- `Dict[str, bool]`: 플랫폼별 성공 여부
  ```python
  {"instagram": True, "tiktok": False}
  ```

#### `upload_to_instagram(video_path, caption, headless)`

Instagram Reels에만 업로드

#### `upload_to_tiktok(video_path, caption, headless)`

TikTok에만 업로드

#### `get_available_platforms()`

설정된 플랫폼 리스트 반환

**Returns:**
- `List[str]`: 예: `["instagram", "tiktok"]`

---

## 문제 해결

### 1. "Playwright가 설치되지 않았습니다"

**해결:**
```bash
pip install playwright
playwright install chromium
```

### 2. "자격증명을 찾을 수 없습니다"

**해결:**
- `.env` 파일에 자격증명이 올바르게 설정되어 있는지 확인
- 환경변수 이름 확인: `INSTAGRAM_USERNAME`, `INSTAGRAM_PASSWORD`, `TIKTOK_USERNAME`, `TIKTOK_PASSWORD`

### 3. "로그인 실패"

**원인:**
- 잘못된 사용자명/비밀번호
- 2단계 인증 활성화
- IP 차단 또는 보안 경고

**해결:**
1. 자격증명 확인
2. 2단계 인증 비활성화 또는 앱 비밀번호 사용
3. 수동으로 로그인하여 보안 경고 해제

### 4. "업로드 실패"

**원인:**
- Instagram/TikTok UI 변경
- 네트워크 문제
- 플랫폼 API 제한

**해결:**
1. `headless=False`로 설정하여 브라우저에서 직접 확인
2. 로그 확인
3. 수동 개입 필요 시 UI에서 완료

### 5. "CAPTCHA 또는 보안 검증"

Instagram과 TikTok은 자동화를 감지할 수 있습니다.

**해결:**
1. `headless=False`로 실행하여 수동으로 CAPTCHA 해결
2. 첫 로그인 후 세션 쿠키 저장 (향후 개선 예정)
3. 동일 IP에서 너무 자주 업로드하지 않기

### 6. "비디오 형식 오류"

**해결:**
- 비디오가 9:16 세로 형식인지 확인 (1080x1920)
- MP4 형식인지 확인
- 파일 크기 제한 확인 (Instagram: 4GB, TikTok: 287MB)

---

## 추가 정보

### 해시태그 자동 추가

`SocialMediaUploader`는 플랫폼별로 최적화된 해시태그를 자동으로 추가합니다.

**Instagram 해시태그:**
```
#묵상 #기도 #말씀 #devotional #prayer #faith #blessed
#godisgood #dailydevotion #reels #instareels #korea
```

**TikTok 해시태그:**
```
#묵상 #기도 #말씀 #devotional #prayer #faith #fyp
#foryou #viral #blessed #korea #christian
```

### 헤드리스 모드 vs 브라우저 모드

- **헤드리스 모드 (`headless=True`)**: 백그라운드에서 실행, UI 없음
- **브라우저 모드 (`headless=False`)**: 브라우저 창이 열림, 디버깅 및 수동 개입 가능

**권장:**
- 개발/테스트: `headless=False`
- 프로덕션: `headless=True`

### 로그 확인

업로드 결과는 `output/logs/devotional.log`에 기록됩니다:

```
============================================================
✅ 비디오 생성 성공!
시간: 2024-11-15 09:00:00
파일: output/videos/devotional_20241115_0900.mp4
크기: 2500.0 KB
메시지: 오늘 하루도 주님의 사랑 안에서...
업로드:
  instagram: ✅
  tiktok: ✅
============================================================
```

---

## 라이선스

이 프로젝트는 개인 용도로 자유롭게 사용할 수 있습니다.

## 주의사항

⚠️ Instagram과 TikTok의 서비스 약관을 준수하세요.
⚠️ 자동화 도구 사용 시 계정이 제한될 수 있습니다.
⚠️ 적절한 빈도로 업로드하고, 스팸으로 간주되지 않도록 주의하세요.
