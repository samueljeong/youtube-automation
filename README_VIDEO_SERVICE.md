# Video Service (Optional)

비디오 생성 기능은 선택적입니다. 이 기능을 사용하려면 추가 시스템 의존성과 Python 패키지가 필요합니다.

## 시스템 요구사항

비디오 서비스를 사용하려면 다음 시스템 패키지가 설치되어 있어야 합니다:

- **ffmpeg**: 비디오 처리를 위한 필수 도구

### Ubuntu/Debian
```bash
sudo apt-get update
sudo apt-get install ffmpeg
```

### macOS
```bash
brew install ffmpeg
```

### Windows
[FFmpeg 공식 사이트](https://ffmpeg.org/download.html)에서 다운로드 후 설치

## Python 의존성 설치

시스템 의존성 설치 후, 비디오 관련 Python 패키지를 설치하세요:

```bash
pip install -r requirements-video.txt
```

## 기능

비디오 서비스가 활성화되면 다음 기능을 사용할 수 있습니다:

1. **설교 메시지 비디오 생성**: 텍스트 기반 설교 메시지를 비디오로 변환
2. **멀티플랫폼 업로드**: YouTube, Instagram, TikTok 등에 자동 업로드

## 비활성화 시

비디오 서비스 의존성이 설치되어 있지 않아도 앱은 정상적으로 작동합니다:

- ✅ 성경 드라마 자동 생성
- ✅ 설교 메시지 작성
- ✅ 매일성경 페이지
- ❌ 비디오 생성/업로드 (503 에러 반환)

## 배포 환경

Render.com 같은 클라우드 환경에서는:

1. 메인 앱은 `requirements.txt`만으로 배포 가능
2. 비디오 기능이 필요하면 Render의 Build Command에서 ffmpeg 설치:
   ```bash
   apt-get update && apt-get install -y ffmpeg && pip install -r requirements.txt && pip install -r requirements-video.txt
   ```
