"""
YouTube Video Upload for Step 5
YouTube Data API v3를 사용한 실제 영상 업로드
"""

import os
import json
import time
from typing import Dict, Any, Optional

from .youtube_auth import get_youtube_client, check_auth_status


def upload_video_to_youtube(
    video_path: str,
    title: str,
    description: str = "",
    tags: list = None,
    category_id: str = "22",  # People & Blogs
    privacy_status: str = "private",
    thumbnail_path: str = None
) -> Dict[str, Any]:
    """
    YouTube에 영상 업로드

    Args:
        video_path: 업로드할 영상 파일 경로
        title: 영상 제목
        description: 영상 설명
        tags: 태그 리스트
        category_id: YouTube 카테고리 ID (기본: 22 - People & Blogs)
            - 1: Film & Animation
            - 2: Autos & Vehicles
            - 10: Music
            - 15: Pets & Animals
            - 17: Sports
            - 19: Travel & Events
            - 20: Gaming
            - 22: People & Blogs (기본값)
            - 23: Comedy
            - 24: Entertainment
            - 25: News & Politics
            - 26: Howto & Style
            - 27: Education
            - 28: Science & Technology
        privacy_status: 공개 설정 (private, unlisted, public)
        thumbnail_path: 썸네일 이미지 경로 (선택)

    Returns:
        업로드 결과 딕셔너리
    """
    print(f"[YOUTUBE-UPLOAD] 업로드 시작: {title}")
    print(f"[YOUTUBE-UPLOAD] 영상 파일: {video_path}")
    print(f"[YOUTUBE-UPLOAD] 공개 설정: {privacy_status}")

    # 1. 인증 상태 확인
    auth_status = check_auth_status()
    if not auth_status.get("connected"):
        return {
            "ok": False,
            "mode": "test",
            "error": auth_status.get("message", "YouTube 인증이 필요합니다."),
            "videoId": None,
            "videoUrl": None
        }

    # 2. 파일 존재 확인
    if not os.path.exists(video_path):
        return {
            "ok": False,
            "error": f"영상 파일을 찾을 수 없습니다: {video_path}",
            "videoId": None,
            "videoUrl": None
        }

    # 3. YouTube 클라이언트 획득
    try:
        youtube = get_youtube_client()
        if not youtube:
            return {
                "ok": False,
                "mode": "test",
                "error": "YouTube 클라이언트를 생성할 수 없습니다.",
                "videoId": None,
                "videoUrl": None
            }
    except Exception as e:
        return {
            "ok": False,
            "error": f"YouTube 인증 오류: {str(e)}",
            "videoId": None,
            "videoUrl": None
        }

    # 4. MediaFileUpload 준비
    try:
        from googleapiclient.http import MediaFileUpload
    except ImportError:
        return {
            "ok": False,
            "error": "google-api-python-client 패키지가 설치되지 않았습니다.",
            "videoId": None,
            "videoUrl": None
        }

    # 5. 영상 메타데이터 설정
    body = {
        "snippet": {
            "title": title[:100],  # 최대 100자
            "description": description[:5000] if description else "",  # 최대 5000자
            "tags": tags[:500] if tags else [],  # 최대 500개
            "categoryId": category_id
        },
        "status": {
            "privacyStatus": privacy_status,
            "selfDeclaredMadeForKids": False
        }
    }

    # 6. 업로드 실행
    media = MediaFileUpload(
        video_path,
        mimetype='video/*',
        resumable=True,
        chunksize=1024*1024  # 1MB 청크
    )

    try:
        print("[YOUTUBE-UPLOAD] API 호출 시작...")

        request = youtube.videos().insert(
            part="snippet,status",
            body=body,
            media_body=media
        )

        response = None
        while response is None:
            status, response = request.next_chunk()
            if status:
                progress = int(status.progress() * 100)
                print(f"[YOUTUBE-UPLOAD] 업로드 진행률: {progress}%")

        video_id = response.get("id")
        video_url = f"https://www.youtube.com/watch?v={video_id}"

        print(f"[YOUTUBE-UPLOAD] 업로드 완료!")
        print(f"[YOUTUBE-UPLOAD] Video ID: {video_id}")
        print(f"[YOUTUBE-UPLOAD] URL: {video_url}")

        # 7. 썸네일 업로드 (선택)
        thumbnail_uploaded = False
        if thumbnail_path and os.path.exists(thumbnail_path):
            try:
                print(f"[YOUTUBE-UPLOAD] 썸네일 업로드 중: {thumbnail_path}")

                youtube.thumbnails().set(
                    videoId=video_id,
                    media_body=MediaFileUpload(thumbnail_path, mimetype='image/jpeg')
                ).execute()

                thumbnail_uploaded = True
                print("[YOUTUBE-UPLOAD] 썸네일 업로드 완료")
            except Exception as thumb_error:
                print(f"[YOUTUBE-UPLOAD] 썸네일 업로드 실패: {thumb_error}")

        return {
            "ok": True,
            "mode": "live",
            "videoId": video_id,
            "videoUrl": video_url,
            "title": title,
            "privacyStatus": privacy_status,
            "thumbnailUploaded": thumbnail_uploaded,
            "message": "YouTube 업로드 완료!"
        }

    except Exception as e:
        error_msg = str(e)
        print(f"[YOUTUBE-UPLOAD] 업로드 오류: {error_msg}")

        # 일반적인 오류 메시지 개선
        if "quotaExceeded" in error_msg:
            error_msg = "YouTube API 할당량을 초과했습니다. 내일 다시 시도해주세요."
        elif "invalidCredentials" in error_msg:
            error_msg = "인증이 만료되었습니다. 다시 로그인해주세요."
        elif "forbidden" in error_msg.lower():
            error_msg = "업로드 권한이 없습니다. YouTube 채널 설정을 확인해주세요."

        return {
            "ok": False,
            "error": error_msg,
            "videoId": None,
            "videoUrl": None
        }


def get_upload_progress(video_id: str) -> Dict[str, Any]:
    """
    업로드된 영상의 처리 상태 확인

    Args:
        video_id: YouTube 영상 ID

    Returns:
        처리 상태 정보
    """
    try:
        youtube = get_youtube_client()
        if not youtube:
            return {"ok": False, "error": "YouTube 클라이언트 없음"}

        request = youtube.videos().list(
            part="status,processingDetails",
            id=video_id
        )
        response = request.execute()

        items = response.get("items", [])
        if items:
            video = items[0]
            status = video.get("status", {})
            processing = video.get("processingDetails", {})

            return {
                "ok": True,
                "videoId": video_id,
                "uploadStatus": status.get("uploadStatus"),
                "privacyStatus": status.get("privacyStatus"),
                "processingStatus": processing.get("processingStatus"),
                "processingProgress": processing.get("processingProgress", {})
            }
        else:
            return {"ok": False, "error": "영상을 찾을 수 없습니다."}

    except Exception as e:
        return {"ok": False, "error": str(e)}


# 레거시 호환용 함수 (이전 API와의 호환성)
def upload_video_legacy(
    file_path: str,
    metadata: Dict[str, Any],
    thumbnail_url: str = None,
) -> Dict[str, Any]:
    """
    레거시 API 호환용 업로드 함수
    """
    return upload_video_to_youtube(
        video_path=file_path,
        title=metadata.get("title", "Untitled"),
        description=metadata.get("description", ""),
        tags=metadata.get("tags", []),
        category_id=metadata.get("categoryId", "22"),
        privacy_status=metadata.get("privacyStatus", "private"),
        thumbnail_path=thumbnail_url
    )


if __name__ == "__main__":
    # 테스트
    print("=== YouTube Upload Test ===")

    auth_status = check_auth_status()
    print(f"Auth status: {json.dumps(auth_status, indent=2, ensure_ascii=False)}")

    if auth_status.get("connected"):
        # 테스트 업로드 (실제 파일 필요)
        test_video = "outputs/test_video.mp4"
        if os.path.exists(test_video):
            result = upload_video_to_youtube(
                video_path=test_video,
                title="테스트 영상",
                description="이것은 테스트 영상입니다.",
                tags=["test", "drama"],
                privacy_status="private"
            )
            print(f"Upload result: {json.dumps(result, indent=2, ensure_ascii=False)}")
        else:
            print(f"테스트 영상 파일이 없습니다: {test_video}")
    else:
        print("YouTube 인증이 필요합니다.")
