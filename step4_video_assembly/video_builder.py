"""
Video Builder for Step 4
Step3 결과를 받아 Step4 영상 조립 전체 프로세스 실행

지원 엔진:
    - FFmpeg (기본, 무료)
    - Creatomate (유료, 고급 기능)
"""

import os
from typing import Dict, Any, List, Optional

# 엔진 선택: "ffmpeg" (무료) 또는 "creatomate" (유료)
VIDEO_ENGINE = os.getenv("VIDEO_ENGINE", "ffmpeg")


def build_video(
    step4_input: Dict[str, Any],
    step3_output: Optional[Dict[str, Any]] = None,
    burn_subs: bool = True,
    bgm_path: Optional[str] = None,
    bgm_folder: Optional[str] = None,
    bgm_volume: float = 0.15,
    thumbnail_path: Optional[str] = None,
    intro_duration: float = 1.5
) -> Dict[str, Any]:
    """
    Step4 입력을 받아 영상을 조립하고 결과를 반환

    Args:
        step4_input: Step4 입력 JSON (step4_video 포맷)
        step3_output: Step3 출력 (자막 생성용, 선택적)
        burn_subs: 자막 번인 여부 (FFmpeg 엔진에서만 지원)
        bgm_path: BGM 파일 경로 (직접 지정)
        bgm_folder: BGM 폴더 경로 (랜덤 선택용)
        bgm_volume: BGM 볼륨 (0.0~1.0, 기본 0.15)
        thumbnail_path: 썸네일 이미지 경로 (인트로 생성용)
        intro_duration: 썸네일 인트로 길이 (초, 기본 1.5초)

    Returns:
        Step4 출력 JSON (step4_video_result 포맷)
    """
    # 엔진 선택에 따라 분기
    if VIDEO_ENGINE == "ffmpeg":
        return _build_video_ffmpeg(
            step4_input, step3_output, burn_subs,
            bgm_path, bgm_folder, bgm_volume,
            thumbnail_path, intro_duration
        )
    else:
        return _build_video_creatomate(step4_input)


def _build_video_ffmpeg(
    step4_input: Dict[str, Any],
    step3_output: Optional[Dict[str, Any]] = None,
    burn_subs: bool = True,
    bgm_path: Optional[str] = None,
    bgm_folder: Optional[str] = None,
    bgm_volume: float = 0.15,
    thumbnail_path: Optional[str] = None,
    intro_duration: float = 1.5
) -> Dict[str, Any]:
    """FFmpeg 기반 영상 제작 (무료) + 썸네일 인트로 + BGM 믹싱 + 자막 번인"""
    from .build_video_ffmpeg import build_video_ffmpeg
    return build_video_ffmpeg(
        step4_input,
        step3_output=step3_output,
        burn_subs=burn_subs,
        bgm_path=bgm_path,
        bgm_folder=bgm_folder,
        bgm_volume=bgm_volume,
        thumbnail_path=thumbnail_path,
        intro_duration=intro_duration
    )


def _build_video_creatomate(step4_input: Dict[str, Any]) -> Dict[str, Any]:
    """Creatomate 기반 영상 제작 (유료)"""
    from .call_creatomate import create_video_clip
    from .timeline_merger import merge_clips, calculate_total_duration

    # 입력 파싱
    title = step4_input.get("title", "Untitled")
    cuts = step4_input.get("cuts", [])
    resolution = step4_input.get("output_resolution", "1080p")
    fps = step4_input.get("fps", 30)
    bgm_path = step4_input.get("background_music_path")

    print(f"[BUILD] Starting video build: {title}")
    print(f"[BUILD] Cuts: {len(cuts)}, Resolution: {resolution}, FPS: {fps}")

    # 1. 각 컷별로 클립 생성
    generated_clips = []
    for cut in cuts:
        cut_id = cut.get("cut_id")
        clip_filename = f"output/clip_{cut_id}.mp4"

        clip_path = create_video_clip(
            image_path=cut.get("image_path", ""),
            audio_path=cut.get("audio_path", ""),
            subtitle_path=cut.get("subtitle_path", ""),
            duration_seconds=cut.get("duration_seconds", 0.0),
            output_filename=clip_filename,
            resolution=resolution,
            fps=fps
        )

        if clip_path:
            generated_clips.append({
                "clip_path": clip_path,
                "duration": cut.get("duration_seconds", 0.0)
            })

    # 2. 클립들 병합
    output_filename = f"output/{_sanitize_filename(title)}.mp4"
    final_video = merge_clips(
        clips=generated_clips,
        output_filename=output_filename,
        fade_duration=0.5,
        background_music_path=bgm_path
    )

    # 3. 총 길이 계산
    total_duration = calculate_total_duration(generated_clips, fade_duration=0.5)

    # 4. 결과 반환
    return {
        "step": "step4_video_result",
        "title": title,
        "video_filename": final_video or output_filename,
        "duration_seconds": round(total_duration, 1)
    }


def build_step4_input(
    title: str,
    step3_result: Dict[str, Any],
    step2_images: Dict[str, Any],
    resolution: str = "1080p",
    fps: int = 30,
    bgm_path: Optional[str] = None
) -> Dict[str, Any]:
    """
    Step2, Step3 결과를 조합하여 Step4 입력 생성

    Args:
        title: 영상 제목
        step3_result: Step3 TTS 결과 (audio_files, timeline 포함)
        step2_images: Step2 이미지 생성 결과 (이미지 경로 포함)
        resolution: 출력 해상도
        fps: 프레임 레이트
        bgm_path: 배경음악 경로 (선택)

    Returns:
        Step4 입력 JSON
    """
    audio_files = step3_result.get("audio_files", [])
    images = step2_images.get("generated_images", [])

    # 컷 목록 생성
    cuts = []
    for idx, audio in enumerate(audio_files):
        scene_id = audio.get("scene_id", f"scene{idx + 1}")

        # 해당 씬의 이미지 찾기
        image_info = next(
            (img for img in images if img.get("scene_id") == scene_id),
            {}
        )

        cuts.append({
            "cut_id": idx + 1,
            "image_path": image_info.get("image_path", ""),
            "audio_path": audio.get("audio_filename", ""),
            "subtitle_path": audio.get("subtitle_filename", ""),
            "duration_seconds": audio.get("duration_seconds", 0.0)
        })

    return {
        "step": "step4_video",
        "title": title,
        "cuts": cuts,
        "output_resolution": resolution,
        "fps": fps,
        "background_music_path": bgm_path
    }


def _sanitize_filename(title: str) -> str:
    """파일명으로 사용할 수 없는 문자 제거"""
    import re
    # 특수문자 제거, 공백은 언더스코어로
    sanitized = re.sub(r'[<>:"/\\|?*]', '', title)
    sanitized = sanitized.replace(' ', '_')
    return sanitized[:50]  # 최대 50자


if __name__ == "__main__":
    import json

    # 테스트용 Step4 입력
    mock_step4_input = {
        "step": "step4_video",
        "title": "그 시절, 우리 마을의 이야기",
        "cuts": [
            {
                "cut_id": 1,
                "image_path": "images/scene1.png",
                "audio_path": "audio/scene1.mp3",
                "subtitle_path": "subtitles/scene1.srt",
                "duration_seconds": 24.5
            },
            {
                "cut_id": 2,
                "image_path": "images/scene2.png",
                "audio_path": "audio/scene2.mp3",
                "subtitle_path": "subtitles/scene2.srt",
                "duration_seconds": 30.0
            }
        ],
        "output_resolution": "1080p",
        "fps": 30,
        "background_music_path": None
    }

    # 영상 빌드 실행
    result = build_video(mock_step4_input)
    print("\n=== Step4 Result ===")
    print(json.dumps(result, ensure_ascii=False, indent=2))
