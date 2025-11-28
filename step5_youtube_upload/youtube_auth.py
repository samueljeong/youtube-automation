"""
YouTube Auth for Step 5
YouTube Data API v3 OAuth2 인증
"""

import os
from typing import Any, Optional

# TODO: 실제 사용 시 아래 패키지 설치 필요
# pip install google-auth google-auth-oauthlib google-api-python-client

# OAuth2 관련 상수
# TODO: 실제 경로로 수정 필요
CLIENT_SECRET_FILE = os.getenv("YOUTUBE_CLIENT_SECRET_PATH", "config/client_secret.json")
TOKEN_FILE = os.getenv("YOUTUBE_TOKEN_PATH", "config/youtube_token.json")

# YouTube API 스코프
SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]


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
    # TODO: 실제 구현 시 아래 주석 해제

    # from google.oauth2.credentials import Credentials
    # from google_auth_oauthlib.flow import InstalledAppFlow
    # from google.auth.transport.requests import Request
    # from googleapiclient.discovery import build
    # import json
    #
    # creds = None
    #
    # # 기존 토큰 파일 확인
    # if os.path.exists(TOKEN_FILE):
    #     with open(TOKEN_FILE, 'r') as token:
    #         token_data = json.load(token)
    #         creds = Credentials.from_authorized_user_info(token_data, SCOPES)
    #
    # # 토큰이 없거나 만료된 경우
    # if not creds or not creds.valid:
    #     if creds and creds.expired and creds.refresh_token:
    #         # 토큰 갱신
    #         creds.refresh(Request())
    #     else:
    #         # 새 OAuth 플로우 시작
    #         if not os.path.exists(CLIENT_SECRET_FILE):
    #             raise FileNotFoundError(
    #                 f"Client secret file not found: {CLIENT_SECRET_FILE}\n"
    #                 "Please download from Google Cloud Console."
    #             )
    #         flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRET_FILE, SCOPES)
    #         creds = flow.run_local_server(port=0)
    #
    #     # 토큰 저장
    #     with open(TOKEN_FILE, 'w') as token:
    #         token.write(creds.to_json())
    #
    # # YouTube API 서비스 빌드
    # youtube = build('youtube', 'v3', credentials=creds)
    # return youtube

    # 임시: 더미 객체 반환
    print("[AUTH] YouTube client requested (mock mode)")
    print(f"[AUTH] Client secret: {CLIENT_SECRET_FILE}")
    print(f"[AUTH] Token file: {TOKEN_FILE}")
    return _MockYouTubeClient()


class _MockYouTubeClient:
    """테스트용 Mock YouTube 클라이언트"""

    def videos(self):
        return _MockVideosResource()


class _MockVideosResource:
    """테스트용 Mock Videos Resource"""

    def insert(self, part: str, body: dict, media_body: Any = None):
        return _MockRequest(body)


class _MockRequest:
    """테스트용 Mock Request"""

    def __init__(self, body: dict):
        self.body = body

    def execute(self) -> dict:
        print(f"[MOCK] Would upload video: {self.body.get('snippet', {}).get('title', 'Unknown')}")
        return {
            "id": "MOCK_VIDEO_ID_12345",
            "snippet": self.body.get("snippet", {}),
            "status": self.body.get("status", {})
        }


def validate_credentials() -> bool:
    """
    인증 정보 유효성 검사

    Returns:
        True if credentials are valid
    """
    # TODO: 실제 구현
    if not os.path.exists(CLIENT_SECRET_FILE):
        print(f"[AUTH] Warning: Client secret not found at {CLIENT_SECRET_FILE}")
        return False
    return True


if __name__ == "__main__":
    # 테스트
    print("=== YouTube Auth Test ===")
    print(f"Client secret path: {CLIENT_SECRET_FILE}")
    print(f"Token path: {TOKEN_FILE}")
    print(f"Credentials valid: {validate_credentials()}")

    client = get_youtube_client()
    print(f"Client type: {type(client)}")
