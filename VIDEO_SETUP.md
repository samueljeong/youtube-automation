# 비디오 생성 및 공유 기능 설정 가이드

## 개요
묵상메시지를 9:16 세로 비율의 비디오로 자동 생성하고, YouTube Shorts, Instagram 릴스, TikTok에 자동 업로드하는 기능입니다.

## 설치

### 1. 의존성 설치
```bash
pip install -r requirements.txt
```

### 2. 데이터베이스 초기화
```bash
python init_db_postgres.py
```

## API 키 설정

### YouTube API 설정

1. [Google Cloud Console](https://console.cloud.google.com/) 접속
2. 새 프로젝트 생성 또는 기존 프로젝트 선택
3. "API 및 서비스" > "사용자 인증 정보" 이동
4. "OAuth 2.0 클라이언트 ID" 생성
   - 애플리케이션 유형: 웹 애플리케이션
   - 승인된 리디렉션 URI 추가
5. Client ID, Client Secret 복사
6. YouTube Data API v3 활성화
7. OAuth 2.0 Playground를 통해 Refresh Token 발급:
   - https://developers.google.com/oauthplayground/
   - Scope: `https://www.googleapis.com/auth/youtube.upload`

### Instagram API 설정

1. [Meta for Developers](https://developers.facebook.com/) 접속
2. 앱 생성
3. Instagram Graph API 추가
4. 비즈니스 계정 연결 필요
5. Access Token 발급:
   - Graph API Explorer 사용
   - 권한: `instagram_basic`, `instagram_content_publish`
6. Instagram Account ID 확인

### TikTok API 설정

1. [TikTok for Developers](https://developers.tiktok.com/) 접속
2. 앱 등록
3. Content Posting API 권한 신청
4. Access Token 발급
5. Open ID 확인

## 사용 방법

### 1. API 키 설정
- Sermon 페이지에서 "⚙️ API 키 설정" 버튼 클릭
- 각 플랫폼별 API 키 입력 후 저장

### 2. 비디오 생성
- 제목, 성경 구절, 본문 입력
- "비디오 생성" 버튼 클릭
- 약 15초 소요

### 3. 업로드
- 비디오 생성 후 플랫폼별 버튼 표시:
  - 📺 YouTube Shorts
  - 📷 Instagram 릴스
  - 🎵 TikTok
  - 🚀 모든 플랫폼에 업로드

## API 엔드포인트

### 비디오 생성
```
POST /api/video/create
{
  "title": "묵상 제목",
  "scripture_reference": "요한복음 3:16",
  "content": "본문 내용...",
  "duration": 15
}
```

### 비디오 업로드
```
POST /api/video/upload
{
  "video_id": 1,
  "platforms": ["youtube", "instagram", "tiktok"]
}
```

### API 키 저장
```
POST /api/credentials/save
{
  "platform": "youtube",
  "credentials": {
    "client_id": "...",
    "client_secret": "...",
    "refresh_token": "..."
  }
}
```

## 비디오 형식

- **해상도**: 1080x1920 (9:16 세로 비율)
- **FPS**: 30
- **길이**: 15초 (기본값)
- **포맷**: MP4
- **코덱**: H.264

## 주의사항

### YouTube
- 일일 업로드 할당량 확인 필요
- 비디오는 Shorts로 자동 분류됨 (60초 이하)

### Instagram
- 비즈니스 계정 필요
- 릴스는 15-90초 권장
- 비디오 URL은 공개 접근 가능해야 함

### TikTok
- Content Posting API 승인 필요 (심사 소요)
- 최대 10MB, 최대 60초

## 문제 해결

### 비디오 생성 실패
- ImageMagick 설치 필요 (moviepy 의존성)
```bash
# Ubuntu/Debian
sudo apt-get install imagemagick

# macOS
brew install imagemagick
```

### 폰트 오류
- Arial 폰트가 시스템에 설치되어 있어야 함
- 또는 video_service.py에서 사용 가능한 폰트로 변경

### API 업로드 실패
- API 키 및 권한 확인
- 플랫폼별 할당량 확인
- 네트워크 연결 확인

## 개발 로드맵

### 현재 구현
- ✅ 비디오 생성 (텍스트 기반)
- ✅ YouTube API 연동
- ✅ Instagram API 연동
- ✅ TikTok API 연동
- ✅ API 키 관리

### 향후 계획
- 🔲 배경 이미지 커스터마이징
- 🔲 배경 음악 추가
- 🔲 템플릿 시스템
- 🔲 비디오 미리보기
- 🔲 예약 업로드
- 🔲 업로드 이력 조회
- 🔲 비디오 다운로드

## 라이선스
MIT License
