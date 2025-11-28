from typing import Dict, Any

from .build_metadata import build_metadata
from .upload_video import upload_video_to_youtube


def run_step5(
    step1_output: Dict[str, Any],
    step4_output: Dict[str, Any],
    video_file_path: str,
    mode: str = "test",
) -> Dict[str, Any]:
    """
    Step5: YouTube 메타데이터 생성 + (옵션) 업로드 실행

    :param step1_output: Step1의 최종 결과(JSON dict)
    :param step4_output: Step4의 썸네일 생성 결과(JSON dict)
    :param video_file_path: 업로드 대상 영상 파일 경로
    :param mode: "test" 또는 "prod"
    """
    metadata = build_metadata(step1_output, step4_output)
    thumbnail_url = step4_output.get("thumbnail_image_url", "")

    youtube_result: Any

    if mode == "prod":
        youtube_result = upload_video_to_youtube(
            file_path=video_file_path,
            metadata=metadata,
            thumbnail_url=thumbnail_url,
        )
    else:
        # test 모드에서는 실제 업로드를 수행하지 않는다.
        youtube_result = {
            "status": "test_mode",
            "message": "YouTube upload skipped in test mode.",
            "file_path": video_file_path,
            "metadata_preview": metadata,
            "thumbnail_url": thumbnail_url,
        }

    return {
        "metadata": metadata,
        "youtube_result": youtube_result,
    }
