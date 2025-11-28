"""
Step4 Video Builder - FFmpeg Standalone Version
독립 실행 가능한 FFmpeg 기반 영상 조립 모듈

Features:
    - Ken Burns 스타일 줌 + 패닝 (랜덤 오프셋)
    - 썸네일 인트로 (2초)
    - BGM 자동 믹싱
    - 필름 그레인 + 비네트 + 색감 보정

Usage:
    python3 step4_video_ffmpeg.py \\
        --input outputs/step4_input.json \\
        --output outputs/final_video.mp4 \\
        --bgm_folder assets/bgm
"""

import json
import os
import random
import shutil
import subprocess
import tempfile
from typing import List, Dict, Any, Optional


# ---------------------------------------------------------
# 공통 FFmpeg 실행 함수
# ---------------------------------------------------------
def run_ffmpeg(cmd: List[str]) -> None:
    """FFmpeg 명령어 실행"""
    print("[FFMPEG]", " ".join(cmd))
    proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    if proc.returncode != 0:
        print(proc.stdout)
        raise RuntimeError(f"FFmpeg failed with code {proc.returncode}")


# ---------------------------------------------------------
# 1) 씬별 클립 생성 (Ken Burns + 페이드 인/아웃 + 오디오 페이드)
# ---------------------------------------------------------
def generate_scene_clip(
    image_path: str,
    audio_path: str,
    duration: float,
    out_path: str
) -> None:
    """
    하나의 씬(part 영상)을 제작 (애니메이션형 스타일).

    Args:
        image_path: 장면 이미지 (정지 이미지)
        audio_path: 장면 오디오 (TTS wav/mp3)
        duration: 초 단위 (float)
        out_path: 결과 저장될 mp4

    효과:
        - 1080p, 30fps
        - 이미지에 느린 줌인 + 부드러운 패닝 (켄 번즈 스타일)
        - 영상: 페이드 인/아웃 (duration 비례)
        - 오디오: 페이드 인/아웃
        - 약한 필름 그레인 + 비네트 + 살짝 강화된 색감
    """
    fps = 30
    frame_count = int(duration * fps)

    # duration이 너무 짧을 때 안전장치
    fade_in_d = min(1.0, max(duration * 0.2, 0.3))   # 최소 0.3초, 최대 1초
    fade_out_d = fade_in_d
    fade_out_start = max(duration - fade_out_d, 0)

    audio_fade_in_d = min(0.5, max(duration * 0.1, 0.2))
    audio_fade_out_d = audio_fade_in_d
    audio_fade_out_start = max(duration - audio_fade_out_d, 0)

    # 약간의 랜덤 패닝 오프셋 (씬마다 다른 느낌)
    offset_x = random.randint(-30, 30)
    offset_y = random.randint(-20, 20)

    vf_filter = (
        "[0:v]"
        "scale=2200:1238,"
        "zoompan="
        "z='1.03+0.0008*on':"
        f"x='(iw-1920)/2 + {offset_x} - 40*sin(on/90)':"
        f"y='(ih-1080)/2 + {offset_y} + 30*cos(on/110)':"
        f"d={frame_count}:s=1920x1080:fps={fps},"
        f"fade=t=in:st=0:d={fade_in_d},"
        f"fade=t=out:st={fade_out_start}:d={fade_out_d},"
        "eq=saturation=0.98:contrast=1.03:brightness=0.02,"
        "noise=alls=3:allf=t,"
        "vignette=PI/7,"
        "format=yuv420p"
        "[v]"
    )

    af_filter = (
        f"[1:a]afade=t=in:st=0:d={audio_fade_in_d},"
        f"afade=t=out:st={audio_fade_out_start}:d={audio_fade_out_d}[a]"
    )

    filter_complex = f"{vf_filter};{af_filter}"

    cmd = [
        "ffmpeg",
        "-y",
        "-loop", "1",
        "-i", image_path,   # 0:v
        "-i", audio_path,   # 1:a
        "-filter_complex", filter_complex,
        "-t", str(duration),
        "-map", "[v]",
        "-map", "[a]",
        "-c:v", "libx264",
        "-preset", "medium",
        "-crf", "23",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac",
        "-b:a", "192k",
        "-shortest",
        out_path,
    ]

    run_ffmpeg(cmd)


# ---------------------------------------------------------
# 2) 썸네일 인트로(2초) 생성
# ---------------------------------------------------------
def create_thumbnail_intro(
    thumbnail_path: str,
    duration: float,
    out_path: str
) -> None:
    """
    썸네일 이미지를 이용해 duration초짜리 인트로 영상 생성.

    Args:
        thumbnail_path: 썸네일 이미지 경로
        duration: 인트로 길이 (초, 기본 2.0 권장)
        out_path: 출력 mp4 경로

    Note:
        - 시니어 타겟은 1.5~2초 권장
        - 부드러운 페이드 인 효과 적용
        - 무음 오디오 포함 (concat 호환용)
    """
    vf_filter = (
        "[0:v]"
        "scale=1920:1080:force_original_aspect_ratio=increase,"
        "crop=1920:1080,"
        "fade=t=in:st=0:d=1.0,"
        "format=yuv420p"
        "[v]"
    )

    cmd = [
        "ffmpeg",
        "-y",
        "-loop", "1",
        "-i", thumbnail_path,
        "-f", "lavfi",
        "-i", "anullsrc=r=44100:cl=stereo",  # 무음 오디오
        "-filter_complex", vf_filter,
        "-t", str(duration),
        "-map", "[v]",
        "-map", "1:a",
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac",
        "-shortest",
        out_path,
    ]
    run_ffmpeg(cmd)


# ---------------------------------------------------------
# 3) 여러 클립 concat
# ---------------------------------------------------------
def concat_videos(video_paths: List[str], out_path: str) -> None:
    """
    ffmpeg concat demuxer를 이용해 여러 mp4를 하나로 합친다.

    Args:
        video_paths: 합칠 영상 경로 리스트
        out_path: 출력 영상 경로

    Note:
        모든 영상은 같은 코덱/해상도/프레임레이트여야 한다.
    """
    if not video_paths:
        raise ValueError("No video clips to concat")

    temp_dir = tempfile.mkdtemp(prefix="concat_list_")
    list_path = os.path.join(temp_dir, "list.txt")

    with open(list_path, "w", encoding="utf-8") as f:
        for p in video_paths:
            f.write(f"file '{os.path.abspath(p)}'\n")

    cmd = [
        "ffmpeg",
        "-y",
        "-f", "concat",
        "-safe", "0",
        "-i", list_path,
        "-c", "copy",
        out_path,
    ]
    try:
        run_ffmpeg(cmd)
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


# ---------------------------------------------------------
# 4) BGM 선택 + 믹싱
# ---------------------------------------------------------
def select_random_bgm(bgm_folder: str) -> Optional[str]:
    """BGM 폴더에서 랜덤하게 파일 선택"""
    if not os.path.isdir(bgm_folder):
        return None
    files = [
        f for f in os.listdir(bgm_folder)
        if f.lower().endswith((".mp3", ".wav", ".m4a"))
    ]
    if not files:
        return None
    return os.path.join(bgm_folder, random.choice(files))


def add_bgm_to_video(
    video_in: str,
    bgm_path: Optional[str],
    video_out: str,
    bgm_volume: float = 0.15
) -> None:
    """
    영상에 BGM을 믹싱.

    Args:
        video_in: concat 후 만들어진 mp4 (나레이션 오디오 포함)
        bgm_path: BGM 파일 경로
        video_out: BGM이 섞인 최종 mp4
        bgm_volume: BGM 볼륨 (0.0~1.0, 기본 0.15 = 약 -16dB)

    Note:
        - BGM을 낮은 볼륨으로 전체 구간에 깔아줌
        - 나레이션과 BGM을 amix로 믹싱
    """
    if bgm_path is None or not os.path.exists(bgm_path):
        # BGM이 없으면 그냥 복사
        shutil.copy(video_in, video_out)
        return

    filter_complex = (
        # BGM을 loop + 볼륨 적용
        f"[1:a]aloop=loop=-1:size=2e+09,volume={bgm_volume}[bga];"
        # 메인 오디오 + BGM 믹스
        "[0:a][bga]amix=inputs=2:duration=first:dropout_transition=3[outa]"
    )

    cmd = [
        "ffmpeg",
        "-y",
        "-i", video_in,
        "-i", bgm_path,
        "-filter_complex", filter_complex,
        "-map", "0:v",
        "-map", "[outa]",
        "-c:v", "copy",
        "-c:a", "aac",
        "-b:a", "192k",
        "-shortest",
        video_out,
    ]
    run_ffmpeg(cmd)


# ---------------------------------------------------------
# 5) Step4 전체 빌더
# ---------------------------------------------------------
def build_video_with_ffmpeg(
    step4_input: Dict[str, Any],
    output_path: str,
    bgm_folder: str = "assets/bgm",
    bgm_volume: float = 0.15,
    intro_duration: float = 2.0,
    thumbnail_fallback: Optional[str] = None,
) -> str:
    """
    Step4용 FFmpeg 빌더.

    Args:
        step4_input: Step4 입력 딕셔너리
        output_path: 최종 영상 출력 경로
        bgm_folder: BGM 파일들이 있는 폴더
        bgm_volume: BGM 볼륨 (0.0~1.0)
        intro_duration: 썸네일 인트로 길이 (초)
        thumbnail_fallback: 썸네일 대체 경로

    Returns:
        최종 영상 경로

    기대하는 step4_input 구조(예시):

    {
      "title": "그 시절, 우리 마을의 작은 구멍가게",
      "thumbnail_path": "outputs/thumbnails/thumb_0.png",
      "scenes": [
        {
          "id": "scene1",
          "image_path": "outputs/images/scene1.png",
          "audio_path": "outputs/audio/scene1.mp3",
          "duration_sec": 12.0
        },
        ...
      ]
    }

    또는 cuts 배열 형식도 지원:

    {
      "title": "...",
      "cuts": [
        {
          "cut_id": 1,
          "image_path": "...",
          "audio_path": "...",
          "duration_seconds": 12.0
        },
        ...
      ]
    }
    """

    temp_dir = tempfile.mkdtemp(prefix="ffmpeg_step4_")
    try:
        # 1) 썸네일 경로 결정
        thumb_path = step4_input.get("thumbnail_path")

        # thumbnail 객체 형식도 지원
        if not thumb_path:
            thumb_info = step4_input.get("thumbnail") or {}
            candidates = thumb_info.get("candidates") or []
            sel_idx = thumb_info.get("selected_index", 0)
            if candidates and 0 <= sel_idx < len(candidates):
                thumb_path = candidates[sel_idx].get("local_path")

        if not thumb_path and thumbnail_fallback:
            thumb_path = thumbnail_fallback

        # 2) 씬 정보 파싱 (scenes 또는 cuts 형식 지원)
        scenes = step4_input.get("scenes") or []
        if not scenes:
            cuts = step4_input.get("cuts") or []
            for cut in cuts:
                scenes.append({
                    "id": f"scene{cut.get('cut_id', len(scenes)+1)}",
                    "image_path": cut.get("image_path"),
                    "audio_path": cut.get("audio_path"),
                    "duration_sec": cut.get("duration_seconds", 10.0)
                })

        if not scenes:
            raise ValueError("step4_input에 scenes 또는 cuts가 비어 있습니다.")

        # 3) 씬별 클립 생성
        scene_clips: List[str] = []
        total_duration = 0.0

        for i, scene in enumerate(scenes, start=1):
            img = scene.get("image_path")
            aud = scene.get("audio_path")
            dur = float(scene.get("duration_sec") or scene.get("duration_seconds") or 10.0)

            if not img or not os.path.exists(img):
                print(f"[WARNING] Image not found for scene {i}: {img}")
                continue
            if not aud or not os.path.exists(aud):
                print(f"[WARNING] Audio not found for scene {i}: {aud}")
                continue

            part_out = os.path.join(temp_dir, f"part_scene_{i}.mp4")
            print(f"[Step4-FFMPEG] Generating scene clip {i}: {part_out}")
            generate_scene_clip(img, aud, dur, part_out)
            scene_clips.append(part_out)
            total_duration += dur

        if not scene_clips:
            raise ValueError("생성된 씬 클립이 없습니다. 이미지/오디오 파일을 확인하세요.")

        # 4) 썸네일 인트로 생성
        clips_to_concat: List[str] = []
        if thumb_path and os.path.exists(thumb_path):
            intro_path = os.path.join(temp_dir, "intro.mp4")
            print(f"[Step4-FFMPEG] Generating thumbnail intro from {thumb_path}")
            create_thumbnail_intro(thumb_path, intro_duration, intro_path)
            clips_to_concat.append(intro_path)
            total_duration += intro_duration
        else:
            print("[Step4-FFMPEG] No thumbnail found, skipping intro")

        clips_to_concat.extend(scene_clips)

        # 5) concat으로 하나로 합치기
        no_bgm_path = os.path.join(temp_dir, "video_no_bgm.mp4")
        print(f"[Step4-FFMPEG] Concatenating {len(clips_to_concat)} clips...")
        concat_videos(clips_to_concat, no_bgm_path)

        # 6) BGM 선택 + 믹싱
        bgm_src = select_random_bgm(bgm_folder)
        if bgm_src:
            print(f"[Step4-FFMPEG] Selected BGM: {bgm_src}")
        else:
            print("[Step4-FFMPEG] No BGM found, skipping BGM mixing")

        with_bgm_path = os.path.join(temp_dir, "video_with_bgm.mp4")
        add_bgm_to_video(no_bgm_path, bgm_src, with_bgm_path, bgm_volume)

        # 7) 최종 결과를 output_path로 복사
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        shutil.copy(with_bgm_path, output_path)

        print(f"\n[Step4-FFMPEG] Final video saved: {output_path}")
        print(f"[Step4-FFMPEG] Total duration: {total_duration:.1f}s")

        return output_path

    finally:
        # 중간 결과 확인이 필요하면 아래 주석 처리
        shutil.rmtree(temp_dir, ignore_errors=True)


# ---------------------------------------------------------
# 6) CLI 진입점
# ---------------------------------------------------------
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Step4 FFmpeg Video Builder - 독립 실행 버전"
    )
    parser.add_argument(
        "--input", required=True,
        help="step4_input.json 경로"
    )
    parser.add_argument(
        "--output", required=True,
        help="최종 mp4 출력 경로"
    )
    parser.add_argument(
        "--bgm_folder", default="assets/bgm",
        help="BGM 폴더 경로 (기본: assets/bgm)"
    )
    parser.add_argument(
        "--bgm_volume", type=float, default=0.15,
        help="BGM 볼륨 0.0~1.0 (기본: 0.15)"
    )
    parser.add_argument(
        "--intro_duration", type=float, default=2.0,
        help="썸네일 인트로 길이 초 (기본: 2.0)"
    )
    parser.add_argument(
        "--thumbnail", default=None,
        help="썸네일 이미지 경로 (없으면 step4_input에서 추출)"
    )

    args = parser.parse_args()

    with open(args.input, "r", encoding="utf-8") as f:
        data = json.load(f)

    result = build_video_with_ffmpeg(
        step4_input=data,
        output_path=args.output,
        bgm_folder=args.bgm_folder,
        bgm_volume=args.bgm_volume,
        intro_duration=args.intro_duration,
        thumbnail_fallback=args.thumbnail,
    )

    print(f"\nDone! Video saved to: {result}")
