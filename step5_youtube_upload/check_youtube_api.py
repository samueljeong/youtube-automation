"""
YouTube API & OAuth 상태 점검 스크립트
실제 업로드 전에 권한/설정이 정상인지 확인

Usage:
    python3 -m step5_youtube_upload.check_youtube_api
    또는
    python3 step5_youtube_upload/check_youtube_api.py --token token.json
"""

import os
import sys
import json
import argparse
from typing import Optional

# YouTube API scope
SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube",
]


def check_dependencies() -> bool:
    """필요한 라이브러리 설치 확인"""
    missing = []

    try:
        from googleapiclient.discovery import build
    except ImportError:
        missing.append("google-api-python-client")

    try:
        from google.oauth2.credentials import Credentials
    except ImportError:
        missing.append("google-auth")

    if missing:
        print("❌ 필요한 라이브러리가 설치되지 않았습니다:")
        for lib in missing:
            print(f"   pip install {lib}")
        return False

    return True


def load_credentials_from_token(token_path: str) -> Optional[object]:
    """토큰 파일에서 자격증명 로드"""
    from google.oauth2.credentials import Credentials

    if not os.path.exists(token_path):
        print(f"❌ 토큰 파일을 찾을 수 없습니다: {token_path}")
        print("   OAuth 인증을 먼저 완료하세요.")
        return None

    try:
        with open(token_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        creds = Credentials.from_authorized_user_info(data, SCOPES)

        if not creds:
            print("❌ 토큰을 파싱할 수 없습니다.")
            return None

        if creds.expired:
            print("⚠️  토큰이 만료되었습니다. 리프레시 시도 중...")
            if creds.refresh_token:
                from google.auth.transport.requests import Request
                creds.refresh(Request())
                print("✅ 토큰 리프레시 성공")

                # 리프레시된 토큰 저장
                with open(token_path, "w", encoding="utf-8") as f:
                    f.write(creds.to_json())
            else:
                print("❌ 리프레시 토큰이 없습니다. 재인증이 필요합니다.")
                return None

        return creds

    except json.JSONDecodeError as e:
        print(f"❌ 토큰 파일 JSON 파싱 오류: {e}")
        return None
    except Exception as e:
        print(f"❌ 토큰 로드 중 오류: {e}")
        return None


def check_youtube_api(token_path: str = "token.json") -> bool:
    """YouTube API 상태 전체 점검"""
    print("=" * 50)
    print("🔎 YouTube API & OAuth 상태 점검")
    print("=" * 50)

    # 1) 의존성 확인
    print("\n[1/4] 라이브러리 확인...")
    if not check_dependencies():
        return False
    print("✅ 필요한 라이브러리 설치됨")

    # 2) 토큰 로드
    print(f"\n[2/4] 토큰 파일 로드: {token_path}")
    creds = load_credentials_from_token(token_path)
    if not creds:
        return False
    print("✅ 토큰 로드 완료")

    # Scope 확인
    if hasattr(creds, 'scopes') and creds.scopes:
        print("   포함된 scopes:")
        for s in creds.scopes:
            print(f"     - {s}")

    # 3) YouTube API 클라이언트 생성
    print("\n[3/4] YouTube API 클라이언트 생성...")
    try:
        from googleapiclient.discovery import build
        youtube = build("youtube", "v3", credentials=creds)
        print("✅ YouTube 클라이언트 생성 성공")
    except Exception as e:
        print(f"❌ YouTube 클라이언트 생성 실패: {e}")
        return False

    # 4) 채널 정보 조회 (권한 테스트)
    print("\n[4/4] 채널 정보 조회 (권한 테스트)...")
    try:
        request = youtube.channels().list(
            part="snippet,contentDetails,statistics",
            mine=True,
        )
        response = request.execute()

        items = response.get("items", [])
        if not items:
            print("❌ 채널 정보를 가져오지 못했습니다.")
            print("   - 계정에 YouTube 채널이 있는지 확인하세요.")
            print("   - OAuth scope에 youtube.upload이 포함되어 있는지 확인하세요.")
            return False

        channel = items[0]
        snippet = channel.get("snippet", {})
        stats = channel.get("statistics", {})

        print("✅ 채널 조회 성공")
        print(f"   - 채널명: {snippet.get('title', 'N/A')}")
        print(f"   - 채널 ID: {channel.get('id', 'N/A')}")
        print(f"   - 구독자 수: {stats.get('subscriberCount', 'N/A')}")
        print(f"   - 동영상 수: {stats.get('videoCount', 'N/A')}")

    except Exception as e:
        print(f"❌ 채널 조회 실패: {e}")
        return False

    # 최종 결과
    print("\n" + "=" * 50)
    print("🎉 YouTube API & OAuth 설정이 정상입니다!")
    print("=" * 50)
    print("\n이제 Step5 업로드를 실행할 수 있습니다.")

    return True


def check_client_secrets(secrets_path: str = "client_secrets.json") -> bool:
    """OAuth 클라이언트 시크릿 파일 확인"""
    print(f"\n[추가] OAuth 클라이언트 시크릿 확인: {secrets_path}")

    if not os.path.exists(secrets_path):
        print(f"⚠️  클라이언트 시크릿 파일이 없습니다: {secrets_path}")
        print("   (이미 token.json이 있으면 필요 없을 수 있습니다)")
        return False

    try:
        with open(secrets_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        # Web 또는 Installed 앱 타입 확인
        app_type = None
        if "web" in data:
            app_type = "web"
            client_data = data["web"]
        elif "installed" in data:
            app_type = "installed"
            client_data = data["installed"]
        else:
            print("❌ 알 수 없는 클라이언트 시크릿 형식")
            return False

        print(f"✅ 클라이언트 타입: {app_type}")
        print(f"   - Client ID: {client_data.get('client_id', 'N/A')[:50]}...")

        redirect_uris = client_data.get("redirect_uris", [])
        if redirect_uris:
            print("   - Redirect URIs:")
            for uri in redirect_uris[:3]:
                print(f"     {uri}")

        return True

    except Exception as e:
        print(f"❌ 클라이언트 시크릿 파싱 오류: {e}")
        return False


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="YouTube API & OAuth 상태 점검"
    )
    parser.add_argument(
        "--token",
        default="token.json",
        help="OAuth 토큰 파일 경로 (기본: token.json)"
    )
    parser.add_argument(
        "--secrets",
        default="client_secrets.json",
        help="클라이언트 시크릿 파일 경로 (기본: client_secrets.json)"
    )

    args = parser.parse_args()

    # 클라이언트 시크릿 확인 (선택적)
    check_client_secrets(args.secrets)

    # 메인 체크
    success = check_youtube_api(args.token)

    sys.exit(0 if success else 1)
