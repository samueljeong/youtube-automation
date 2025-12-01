"""
YouTube Auth for Step 5
YouTube Data API v3 OAuth2 인증
- 환경변수 지원 (YOUTUBE_CLIENT_ID, YOUTUBE_CLIENT_SECRET)
- 파일 지원 (config/client_secret.json)
"""

import os
import json
from typing import Any, Optional, Dict

# OAuth2 관련 상수
CLIENT_SECRET_FILE = os.getenv("YOUTUBE_CLIENT_SECRET_PATH", "config/client_secret.json")
TOKEN_FILE = os.getenv("YOUTUBE_TOKEN_PATH", "config/youtube_token.json")

# 환경변수에서 OAuth 정보 가져오기
YOUTUBE_CLIENT_ID = os.getenv('YOUTUBE_CLIENT_ID') or os.getenv('GOOGLE_CLIENT_ID')
YOUTUBE_CLIENT_SECRET = os.getenv('YOUTUBE_CLIENT_SECRET') or os.getenv('GOOGLE_CLIENT_SECRET')
YOUTUBE_REDIRECT_URI = os.getenv('YOUTUBE_REDIRECT_URI', 'https://drama-s2ns.onrender.com/api/youtube/callback')

# YouTube API 스코프
SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.readonly"
]


def has_env_credentials() -> bool:
    """환경변수에 OAuth 정보가 있는지 확인"""
    return bool(YOUTUBE_CLIENT_ID and YOUTUBE_CLIENT_SECRET)


def has_file_credentials() -> bool:
    """파일에 OAuth 정보가 있는지 확인"""
    return os.path.exists(CLIENT_SECRET_FILE)


def get_youtube_client() -> Any:
    """
    YouTube Data API v3 클라이언트 획득

    OAuth2 인증을 수행하고 YouTube API 서비스 객체를 반환합니다.
    - 토큰 파일이 있으면 재사용
    - 없으면 OAuth 플로우 시작

    Returns:
        YouTube API 서비스 객체

    Raises:
        FileNotFoundError: client_secret 파일이 없는 경우
        Exception: 인증 실패 시
    """
    try:
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
        from google.auth.transport.requests import Request
        from googleapiclient.discovery import build
    except ImportError:
        print("[YOUTUBE-AUTH] google-auth 패키지가 설치되지 않았습니다.")
        print("[YOUTUBE-AUTH] 설치: pip install google-auth google-auth-oauthlib google-api-python-client")
        return None

    creds = None

    # 기존 토큰 파일 확인
    if os.path.exists(TOKEN_FILE):
        try:
            with open(TOKEN_FILE, 'r') as token:
                token_data = json.load(token)
                creds = Credentials.from_authorized_user_info(token_data, SCOPES)
            print(f"[YOUTUBE-AUTH] 기존 토큰 로드: {TOKEN_FILE}")
        except Exception as e:
            print(f"[YOUTUBE-AUTH] 토큰 로드 오류: {e}")
            creds = None

    # 토큰이 없거나 만료된 경우
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            # 토큰 갱신
            try:
                creds.refresh(Request())
                print("[YOUTUBE-AUTH] 토큰 갱신 완료")
            except Exception as e:
                print(f"[YOUTUBE-AUTH] 토큰 갱신 실패: {e}")
                creds = None

        if not creds:
            # 새 OAuth 플로우 시작
            if not os.path.exists(CLIENT_SECRET_FILE):
                print(f"[YOUTUBE-AUTH] Client secret 파일 없음: {CLIENT_SECRET_FILE}")
                raise FileNotFoundError(
                    f"Client secret file not found: {CLIENT_SECRET_FILE}\n"
                    "Please download from Google Cloud Console."
                )

            flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRET_FILE, SCOPES)
            creds = flow.run_local_server(port=0)
            print("[YOUTUBE-AUTH] 새 OAuth 인증 완료")

        # 토큰 저장
        if creds:
            os.makedirs(os.path.dirname(TOKEN_FILE), exist_ok=True)
            with open(TOKEN_FILE, 'w') as token:
                token.write(creds.to_json())
            print(f"[YOUTUBE-AUTH] 토큰 저장: {TOKEN_FILE}")

    # YouTube API 서비스 빌드
    youtube = build('youtube', 'v3', credentials=creds)
    print("[YOUTUBE-AUTH] YouTube 클라이언트 생성 완료")
    return youtube


def get_channel_info() -> Optional[Dict[str, Any]]:
    """
    현재 인증된 채널 정보 조회

    Returns:
        채널 정보 딕셔너리 또는 None
    """
    try:
        youtube = get_youtube_client()
        if not youtube:
            return None

        request = youtube.channels().list(
            part="snippet,contentDetails,statistics",
            mine=True
        )
        response = request.execute()

        items = response.get("items", [])
        if items:
            channel = items[0]
            return {
                "id": channel.get("id"),
                "title": channel.get("snippet", {}).get("title"),
                "description": channel.get("snippet", {}).get("description", "")[:100],
                "thumbnailUrl": channel.get("snippet", {}).get("thumbnails", {}).get("default", {}).get("url"),
                "subscriberCount": channel.get("statistics", {}).get("subscriberCount"),
                "videoCount": channel.get("statistics", {}).get("videoCount")
            }
        return None
    except Exception as e:
        print(f"[YOUTUBE-AUTH] 채널 정보 조회 오류: {e}")
        return None


def validate_credentials() -> Dict[str, Any]:
    """
    인증 정보 유효성 검사
    - 환경변수 또는 파일 기반 인증 지원

    Returns:
        {'valid': bool, 'mode': str, 'message': str, 'channel': dict|None}
    """
    # 1. 필요한 패키지 확인
    try:
        from google.oauth2.credentials import Credentials
        from googleapiclient.discovery import build
    except ImportError:
        return {
            "valid": False,
            "mode": "test",
            "message": "google-auth 패키지가 설치되지 않았습니다. pip install google-auth google-auth-oauthlib google-api-python-client",
            "channel": None
        }

    # 2. OAuth 정보 확인 (환경변수 또는 파일)
    if not has_env_credentials() and not has_file_credentials():
        return {
            "valid": False,
            "mode": "test",
            "message": "YouTube API 인증 정보가 없습니다. YOUTUBE_CLIENT_ID/YOUTUBE_CLIENT_SECRET 환경변수 또는 config/client_secret.json 파일이 필요합니다.",
            "channel": None
        }

    # 환경변수 사용 시 로그
    if has_env_credentials():
        print(f"[YOUTUBE-AUTH] 환경변수 인증 사용 (CLIENT_ID: {YOUTUBE_CLIENT_ID[:20]}...)")

    # 3. 토큰 파일 확인
    if not os.path.exists(TOKEN_FILE):
        return {
            "valid": False,
            "mode": "setup",
            "message": "OAuth 인증이 필요합니다. /api/youtube/auth로 인증을 진행해주세요.",
            "channel": None
        }

    # 4. 토큰 유효성 검사
    try:
        with open(TOKEN_FILE, 'r') as f:
            token_data = json.load(f)

        creds = Credentials.from_authorized_user_info(token_data, SCOPES)

        if not creds.valid:
            if creds.expired and creds.refresh_token:
                from google.auth.transport.requests import Request
                creds.refresh(Request())
                # 갱신된 토큰 저장
                with open(TOKEN_FILE, 'w') as f:
                    f.write(creds.to_json())
            else:
                return {
                    "valid": False,
                    "mode": "setup",
                    "message": "토큰이 만료되었습니다. 다시 인증해주세요.",
                    "channel": None
                }

        # 5. 실제 API 호출 테스트
        youtube = build('youtube', 'v3', credentials=creds)
        request = youtube.channels().list(part="snippet", mine=True)
        response = request.execute()

        items = response.get("items", [])
        if items:
            channel = items[0]
            return {
                "valid": True,
                "mode": "live",
                "message": "YouTube 연결됨",
                "channel": {
                    "id": channel.get("id"),
                    "title": channel.get("snippet", {}).get("title"),
                    "thumbnailUrl": channel.get("snippet", {}).get("thumbnails", {}).get("default", {}).get("url")
                }
            }
        else:
            return {
                "valid": False,
                "mode": "test",
                "message": "연결된 채널이 없습니다.",
                "channel": None
            }

    except Exception as e:
        return {
            "valid": False,
            "mode": "test",
            "message": f"인증 오류: {str(e)}",
            "channel": None
        }


def check_auth_status() -> Dict[str, Any]:
    """
    간단한 인증 상태 확인 (API 엔드포인트용)

    Returns:
        인증 상태 정보
    """
    result = validate_credentials()

    return {
        "ok": True,
        "authenticated": result["valid"],
        "connected": result["valid"],
        "mode": result["mode"],
        "channelName": result["channel"]["title"] if result["channel"] else None,
        "channelId": result["channel"]["id"] if result["channel"] else None,
        "channelThumbnail": result["channel"].get("thumbnailUrl") if result["channel"] else None,
        "message": result["message"]
    }


if __name__ == "__main__":
    # 테스트
    print("=== YouTube Auth Test ===")
    print(f"Client secret path: {CLIENT_SECRET_FILE}")
    print(f"Token path: {TOKEN_FILE}")

    status = check_auth_status()
    print(f"\nAuth status: {json.dumps(status, indent=2, ensure_ascii=False)}")

    if status["authenticated"]:
        channel = get_channel_info()
        if channel:
            print(f"\nChannel: {channel['title']}")
            print(f"Subscribers: {channel.get('subscriberCount', 'N/A')}")
