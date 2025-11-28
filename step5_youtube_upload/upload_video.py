import os
import json
from typing import Dict, Any, Optional

import requests


def get_upload_endpoint() -> Optional[str]:
    """
    YouTube 업로드용 내부 API 엔드포인트를 환경변수에서 읽어온다.
    예: https://my-domain.com/api/youtube/upload
    """
    return os.getenv("YOUTUBE_UPLOAD_URL")


def upload_video_to_youtube(
    file_path: str,
    metadata: Dict[str, Any],
    thumbnail_url: str,
) -> Dict[str, Any]:
    """
    내부 YouTube 업로드 API에 영상을 업로드한다.

    실제 업로드는 서버 측에서 처리하고,
    이 함수는 해당 API를 호출하는 역할만 한다.
    """
    endpoint = get_upload_endpoint()
    if not endpoint:
        # 로컬/테스트 환경에서 endpoint가 없으면, 업로드를 생략하고 mock 응답 반환
        return {
            "status": "skipped",
            "reason": "YOUTUBE_UPLOAD_URL not set",
            "file_path": file_path,
            "metadata": metadata,
            "thumbnail_url": thumbnail_url,
        }

    payload = {
        "video_file_path": file_path,
        "title": metadata.get("title", ""),
        "description": metadata.get("description", ""),
        "tags": metadata.get("tags", []),
        "thumbnail_url": thumbnail_url,
    }

    try:
        response = requests.post(
            endpoint,
            json=payload,
            timeout=60,
        )
        response.raise_for_status()
        return {
            "status": "success",
            "api_response": response.json(),
        }
    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "endpoint": endpoint,
        }
