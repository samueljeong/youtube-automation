"""
Schedule Upload for Step 5
YouTube 업로드 실행 및 스케줄링
"""

import os
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from zoneinfo import ZoneInfo

from .channel_router import get_channel_id, get_channel_name
from .build_metadata import build_metadata
from .youtube_auth import get_youtube_client


def schedule_or_upload(step5_input: Dict[str, Any]) -> Dict[str, Any]:
    """
    YouTube 업로드 또는 예약 업로드 실행

    Args:
        step5_input: Step5 입력 JSON (step5_youtube_upload 포맷)

    Returns:
        Step5 출력 JSON (step5_youtube_upload_result 포맷)
    """
    try:
        # 1) 채널 ID 결정
        category = step5_input.get("category", "category1")
        channel_id = get_channel_id(category)
        channel_name = get_channel_name(category)
        print(f"[UPLOAD] Target channel: {channel_name} ({channel_id})")

        # 2) 메타데이터 구성
        metadata = build_metadata(step5_input)
        print(f"[UPLOAD] Title: {metadata['title']}")
        print(f"[UPLOAD] Tags: {metadata['tags'][:5]}...")

        # 3) YouTube API 클라이언트 획득
        youtube = get_youtube_client()

        # 4) 업로드 모드 처리
        upload_mode = step5_input.get("upload_mode", "immediate")
        video_filename = step5_input.get("video_filename", "")

        if upload_mode == "scheduled":
            # 예약 업로드
            scheduled_time = _calculate_scheduled_time(
                preferred_slot=step5_input.get("preferred_slot", "09:00"),
                timezone_str=step5_input.get("timezone", "Asia/Seoul")
            )
            print(f"[UPLOAD] Scheduled for: {scheduled_time.isoformat()}")
            privacy_status = "private"
            publish_at = scheduled_time.isoformat()
        else:
            # 즉시 업로드
            scheduled_time = None
            privacy_status = "public"
            publish_at = None
            print("[UPLOAD] Mode: Immediate upload")

        # 5) YouTube API 호출
        result = _execute_upload(
            youtube=youtube,
            video_filename=video_filename,
            metadata=metadata,
            privacy_status=privacy_status,
            publish_at=publish_at
        )

        # 6) 결과 반환
        video_id = result.get("id")
        return {
            "step": "step5_youtube_upload_result",
            "status": "scheduled" if upload_mode == "scheduled" else "uploaded",
            "channel_id": channel_id,
            "video_id": video_id,
            "scheduled_time": scheduled_time.isoformat() if scheduled_time else None,
            "url": f"https://www.youtube.com/watch?v={video_id}" if video_id else None,
            "error_message": None
        }

    except Exception as e:
        print(f"[UPLOAD] Error: {str(e)}")
        return {
            "step": "step5_youtube_upload_result",
            "status": "error",
            "channel_id": step5_input.get("category", "unknown"),
            "video_id": None,
            "scheduled_time": None,
            "url": None,
            "error_message": str(e)
        }


def _calculate_scheduled_time(preferred_slot: str, timezone_str: str) -> datetime:
    """
    예약 시간 계산

    Args:
        preferred_slot: 선호 시간 슬롯 (HH:MM 형식)
        timezone_str: 시간대 문자열 (예: "Asia/Seoul")

    Returns:
        예약 시간 (timezone-aware datetime)
    """
    # 시간대 설정
    tz = ZoneInfo(timezone_str)
    now = datetime.now(tz)

    # 선호 시간 파싱
    hour, minute = map(int, preferred_slot.split(":"))

    # 오늘 날짜 기준 예약 시간
    scheduled = now.replace(hour=hour, minute=minute, second=0, microsecond=0)

    # 이미 지난 시간이면 내일로 설정
    if scheduled <= now:
        scheduled += timedelta(days=1)

    return scheduled


def _execute_upload(
    youtube: Any,
    video_filename: str,
    metadata: Dict[str, Any],
    privacy_status: str,
    publish_at: Optional[str]
) -> Dict[str, Any]:
    """
    YouTube API를 통해 영상 업로드 실행

    Args:
        youtube: YouTube API 클라이언트
        video_filename: 업로드할 영상 파일 경로
        metadata: 메타데이터 (title, description, tags, categoryId)
        privacy_status: 공개 상태 ("public", "private", "unlisted")
        publish_at: 예약 공개 시간 (ISO-8601, 예약 업로드 시)

    Returns:
        API 응답 딕셔너리
    """
    # YouTube API request body 구조
    body = {
        "snippet": {
            "title": metadata["title"],
            "description": metadata["description"],
            "tags": metadata["tags"],
            "categoryId": metadata["categoryId"]
        },
        "status": {
            "privacyStatus": privacy_status,
            "selfDeclaredMadeForKids": False
        }
    }

    # 예약 업로드인 경우 publishAt 추가
    if publish_at:
        body["status"]["publishAt"] = publish_at

    print(f"[UPLOAD] Video file: {video_filename}")
    print(f"[UPLOAD] Privacy: {privacy_status}")

    # TODO: 실제 업로드 구현
    # from googleapiclient.http import MediaFileUpload
    #
    # if not os.path.exists(video_filename):
    #     raise FileNotFoundError(f"Video file not found: {video_filename}")
    #
    # media = MediaFileUpload(
    #     video_filename,
    #     mimetype="video/mp4",
    #     resumable=True
    # )
    #
    # request = youtube.videos().insert(
    #     part="snippet,status",
    #     body=body,
    #     media_body=media
    # )
    #
    # response = None
    # while response is None:
    #     status, response = request.next_chunk()
    #     if status:
    #         print(f"[UPLOAD] Progress: {int(status.progress() * 100)}%")
    #
    # return response

    # Mock 실행
    request = youtube.videos().insert(
        part="snippet,status",
        body=body,
        media_body=None
    )
    return request.execute()


if __name__ == "__main__":
    import json

    # 테스트
    test_input = {
        "step": "step5_youtube_upload",
        "category": "category1",
        "title": "그 시절, 우리 마을의 작은 구멍가게",
        "description_seed": "1970년대 시골 마을의 따뜻한 이야기",
        "tags_seed": ["구멍가게", "70년대", "추억"],
        "video_filename": "output/final_video.mp4",
        "upload_mode": "scheduled",
        "preferred_slot": "09:00",
        "timezone": "Asia/Seoul"
    }

    print("=== Step5 Upload Test ===")
    result = schedule_or_upload(test_input)
    print("\n=== Result ===")
    print(json.dumps(result, ensure_ascii=False, indent=2))
