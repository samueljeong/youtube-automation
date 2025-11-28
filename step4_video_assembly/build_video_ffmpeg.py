"""
FFmpeg-based Video Builder for Step 4
Creatomate 대신 FFmpeg를 사용한 무료 영상 조립 + 자막 번인

Requirements:
    - FFmpeg 설치 필요 (apt-get install ffmpeg 또는 brew install ffmpeg)
    - FFmpeg가 libass로 빌드되어야 subtitles 필터 사용 가능
    - 실제 이미지 파일 (outputs/images/scene1.png 등)
    - 실제 오디오 파일 (outputs/audio/scene1.mp3 등)
"""

import os
import subprocess
import json
import uuid
from pathlib import Path
from typing import Dict, Any, List, Optional


def run_ffmpeg(cmd: List[str]) -> subprocess.CompletedProcess:
    """
    FFmpeg 명령어 실행

    Args:
        cmd: FFmpeg 명령어 리스트

    Returns:
        subprocess.CompletedProcess

    Raises:
        RuntimeError: FFmpeg 실행 실패 시
    """
    print("[FFMPEG]", " ".join(cmd))
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if result.returncode != 0:
        print("[ERROR] FFmpeg failed:")
        print(result.stderr.decode())
        raise RuntimeError("FFmpeg error")
    return result


def check_ffmpeg_installed() -> bool:
    """FFmpeg 설치 여부 확인"""
    try:
        result = subprocess.run(
            ["ffmpeg", "-version"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        return result.returncode == 0
    except FileNotFoundError:
        return False


def generate_scene_clip(
    image_path: str,
    audio_path: str,
    duration: float,
    output_path: str,
    resolution: str = "1080p"
) -> Optional[str]:
    """
    하나의 씬(part 영상)을 제작 - Ken Burns 스타일 줌 + 페이드 효과

    효과:
        - 1080p 고정 (1920x1080)
        - 30fps
        - 이미지에 느린 줌인 (켄번즈 느낌)
        - 영상: 1초 페이드 인 + 마지막 1초 페이드 아웃
        - 오디오: 0.5초 페이드 인 + 마지막 0.5초 페이드 아웃

    Args:
        image_path: 장면 이미지 경로
        audio_path: 장면 오디오 경로
        duration: 클립 길이 (초)
        output_path: 출력 파일 경로
        resolution: 해상도 (현재 무시됨, 1080p 고정)

    Returns:
        생성된 파일 경로 또는 None
    """
    # 파일 존재 확인
    if not os.path.exists(image_path):
        print(f"[WARNING] Image not found: {image_path}")
        return None
    if not os.path.exists(audio_path):
        print(f"[WARNING] Audio not found: {audio_path}")
        return None

    # 출력 디렉토리 생성
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    # 설정값
    fps = 30
    frame_count = int(duration * fps)

    # 페이드 설정
    fade_in_d = 1.0      # 영상 페이드 인 1초
    fade_out_d = 1.0     # 영상 페이드 아웃 1초
    fade_out_start = max(0, duration - fade_out_d)

    audio_fade_in_d = 0.5   # 오디오 페이드 인 0.5초
    audio_fade_out_d = 0.5  # 오디오 페이드 아웃 0.5초
    audio_fade_out_start = max(0, duration - audio_fade_out_d)

    # 비디오 필터: 스케일 → 줌팬(Ken Burns) → 페이드 인/아웃
    # zoompan: z='1.0+0.001*on' → 프레임마다 0.1% 줌, 느린 줌인 효과
    vf_filter = (
        f"[0:v]scale=1920:1080:force_original_aspect_ratio=increase,"
        f"crop=1920:1080,"
        f"zoompan=z='1.0+0.001*on':d={frame_count}:s=1920x1080:fps={fps},"
        f"fade=t=in:st=0:d={fade_in_d},"
        f"fade=t=out:st={fade_out_start}:d={fade_out_d}[v]"
    )

    # 오디오 필터: 페이드 인/아웃
    af_filter = (
        f"[1:a]afade=t=in:st=0:d={audio_fade_in_d},"
        f"afade=t=out:st={audio_fade_out_start}:d={audio_fade_out_d}[a]"
    )

    cmd = [
        "ffmpeg",
        "-y",
        "-loop", "1",
        "-i", image_path,
        "-i", audio_path,
        "-filter_complex", f"{vf_filter};{af_filter}",
        "-map", "[v]",
        "-map", "[a]",
        "-c:v", "libx264",
        "-preset", "medium",
        "-crf", "23",
        "-t", str(duration),
        "-pix_fmt", "yuv420p",
        "-c:a", "aac",
        "-b:a", "192k",
        output_path
    ]

    try:
        run_ffmpeg(cmd)
        print(f"[FFMPEG] Created clip with Ken Burns effect: {output_path}")
        return output_path
    except RuntimeError:
        return None


def concat_videos(parts: List[str], output_path: str) -> Optional[str]:
    """
    여러 part 영상을 concat하여 최종 영상 생성

    Args:
        parts: 클립 파일 경로 리스트
        output_path: 최종 출력 파일 경로

    Returns:
        생성된 파일 경로 또는 None
    """
    if not parts:
        print("[ERROR] No parts to concatenate")
        return None

    # concat 리스트 파일 생성
    list_path = str(Path(output_path).parent / f"concat_{uuid.uuid4().hex}.txt")

    with open(list_path, "w", encoding="utf-8") as f:
        for p in parts:
            # 절대 경로로 변환
            abs_path = os.path.abspath(p)
            f.write(f"file '{abs_path}'\n")

    cmd = [
        "ffmpeg",
        "-y",
        "-f", "concat",
        "-safe", "0",
        "-i", list_path,
        "-c", "copy",
        output_path
    ]

    try:
        run_ffmpeg(cmd)
        os.remove(list_path)  # 임시 파일 삭제
        print(f"[FFMPEG] Concatenated video: {output_path}")
        return output_path
    except RuntimeError:
        if os.path.exists(list_path):
            os.remove(list_path)
        return None


# ========== 자막(SRT) 관련 유틸 ==========

def _format_timestamp(sec: float) -> str:
    """초(float)를 SRT용 HH:MM:SS,mmm 문자열로 변환."""
    millis = int(round(sec * 1000))
    hours = millis // (1000 * 60 * 60)
    millis %= (1000 * 60 * 60)
    minutes = millis // (1000 * 60)
    millis %= (1000 * 60)
    seconds = millis // 1000
    millis %= 1000
    return f"{hours:02d}:{minutes:02d}:{seconds:02d},{millis:03d}"


def generate_srt_from_step3(step3: Dict[str, Any], srt_path: str) -> str:
    """
    step3_output.json을 기반으로 전체 영상용 subtitles.srt 생성.

    Args:
        step3: Step3 출력 딕셔너리
        srt_path: SRT 파일 저장 경로

    Returns:
        생성된 SRT 파일 경로
    """
    timeline = step3.get("timeline", [])
    subtitle_lines = step3.get("subtitle_lines", [])  # 세분화된 자막이 있으면 사용

    lines = []
    index = 1

    if subtitle_lines:
        # 세부 자막 리스트가 있으면 그걸 사용
        # 형식: [{"start":0.0,"end":3.5,"text":"..."}, ...]
        for sub in subtitle_lines:
            start = _format_timestamp(sub.get("start", 0))
            end = _format_timestamp(sub.get("end", 0))
            text = sub.get("text", "").replace("\n", " ").strip()
            if not text:
                continue
            lines.append(f"{index}")
            lines.append(f"{start} --> {end}")
            lines.append(text)
            lines.append("")  # 빈 줄
            index += 1
    else:
        # fallback: 씬 단위 자막
        for scene in timeline:
            start = float(scene.get("start", 0))
            end = float(scene.get("end", start + 5.0))

            # 텍스트 후보들 중 있는 것 사용
            text = (
                scene.get("subtitle_text")
                or scene.get("narration")
                or scene.get("summary")
                or ""
            )
            text = str(text).strip()
            if not text:
                continue

            # 줄바꿈 정리
            text = text.replace("\\n", " ").replace("\n", " ")

            start_s = _format_timestamp(start)
            end_s = _format_timestamp(end)

            lines.append(f"{index}")
            lines.append(f"{start_s} --> {end_s}")
            lines.append(text)
            lines.append("")
            index += 1

    # 디렉토리 생성
    os.makedirs(os.path.dirname(srt_path), exist_ok=True)

    with open(srt_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    print(f"[Subtitles] SRT generated: {srt_path} ({index - 1} entries)")
    return srt_path


def burn_subtitles(input_video: str, srt_path: str, output_video: str) -> Optional[str]:
    """
    최종 영상에 SRT 자막을 번인(burn-in)하여 새 영상 생성.

    Args:
        input_video: 입력 영상 경로
        srt_path: SRT 자막 파일 경로
        output_video: 출력 영상 경로

    Returns:
        생성된 파일 경로 또는 None

    Note:
        FFmpeg가 libass로 빌드되어 있어야 subtitles 필터 사용 가능
    """
    if not os.path.exists(srt_path):
        print(f"[WARNING] SRT file not found: {srt_path}")
        return input_video  # 자막 없이 원본 반환

    # SRT 경로에 특수문자가 있으면 이스케이프 처리
    srt_escaped = srt_path.replace("\\", "/").replace(":", "\\:")

    cmd = [
        "ffmpeg",
        "-y",
        "-i", input_video,
        "-vf", f"subtitles={srt_escaped}:force_style='FontSize=24,FontName=Arial,PrimaryColour=&Hffffff,OutlineColour=&H000000,Outline=2'",
        "-c:a", "copy",
        output_video
    ]

    try:
        run_ffmpeg(cmd)
        print(f"[Subtitles] Video with subtitles: {output_video}")
        return output_video
    except RuntimeError:
        print("[WARNING] Subtitle burn-in failed, returning raw video")
        return input_video


# ========== 메인 빌드 함수 ==========

def build_video_ffmpeg(
    step4_input: Dict[str, Any],
    step3_output: Optional[Dict[str, Any]] = None,
    burn_subs: bool = True
) -> Dict[str, Any]:
    """
    FFmpeg 기반 영상 제작 + 자막 번인

    Args:
        step4_input: Step4 입력 JSON (cuts 배열 포함)
        step3_output: Step3 출력 (자막 생성용, 선택적)
        burn_subs: 자막 번인 여부

    Returns:
        Step4 출력 JSON
    """
    # FFmpeg 설치 확인
    if not check_ffmpeg_installed():
        print("[ERROR] FFmpeg is not installed!")
        print("  Install with: apt-get install ffmpeg (Linux) or brew install ffmpeg (Mac)")
        return {
            "step": "step4_video_result",
            "title": step4_input.get("title", "Untitled"),
            "video_filename": None,
            "duration_seconds": 0,
            "error": "FFmpeg not installed"
        }

    title = step4_input.get("title", "Untitled")
    cuts = step4_input.get("cuts", [])
    resolution = step4_input.get("output_resolution", "1080p")

    print(f"\n=== [FFmpeg] Building video: {title} ===")
    print(f"[FFmpeg] Cuts: {len(cuts)}, Resolution: {resolution}, Subtitles: {burn_subs}")

    if not cuts:
        print("[ERROR] No cuts provided")
        return {
            "step": "step4_video_result",
            "title": title,
            "video_filename": None,
            "duration_seconds": 0,
            "error": "No cuts provided"
        }

    # 출력 디렉토리
    output_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "outputs")
    os.makedirs(output_dir, exist_ok=True)

    sanitized_title = _sanitize_filename(title)
    raw_video_path = os.path.join(output_dir, f"{sanitized_title}_raw.mp4")
    srt_path = os.path.join(output_dir, "subtitles.srt")
    final_video_path = os.path.join(output_dir, f"{sanitized_title}.mp4")

    # 1) 각 씬별 클립 생성
    part_files = []
    total_duration = 0.0

    for i, cut in enumerate(cuts):
        cut_id = cut.get("cut_id", i + 1)
        image_path = cut.get("image_path", "")
        audio_path = cut.get("audio_path", "")
        duration = cut.get("duration_seconds", 10.0)

        part_path = os.path.join(output_dir, f"part_scene_{cut_id}.mp4")

        print(f"\n[Scene {cut_id}] Creating clip...")
        print(f"  Image: {image_path}")
        print(f"  Audio: {audio_path}")
        print(f"  Duration: {duration}s")

        result = generate_scene_clip(
            image_path=image_path,
            audio_path=audio_path,
            duration=duration,
            output_path=part_path,
            resolution=resolution
        )

        if result:
            part_files.append(result)
            total_duration += duration
        else:
            print(f"[WARNING] Failed to create clip for scene {cut_id}")

    if not part_files:
        print("[ERROR] No clips were generated")
        return {
            "step": "step4_video_result",
            "title": title,
            "video_filename": None,
            "duration_seconds": 0,
            "error": "No clips generated - check image/audio files"
        }

    # 2) part들 concat → raw 영상
    print(f"\n[FFmpeg] Concatenating {len(part_files)} clips...")
    concat_videos(part_files, raw_video_path)

    # 3) 자막 생성 및 번인
    final_video = raw_video_path

    if burn_subs and step3_output:
        print("\n[FFmpeg] Generating subtitles...")
        generate_srt_from_step3(step3_output, srt_path)

        print("[FFmpeg] Burning subtitles into video...")
        final_video = burn_subtitles(raw_video_path, srt_path, final_video_path)
    else:
        # 자막 없이 raw를 final로 복사/이동
        if raw_video_path != final_video_path:
            import shutil
            shutil.move(raw_video_path, final_video_path)
            final_video = final_video_path

    print(f"\n[FFmpeg] Final video saved: {final_video}")

    return {
        "step": "step4_video_result",
        "title": title,
        "video_filename": final_video,
        "duration_seconds": round(total_duration, 1),
        "clips_count": len(part_files),
        "resolution": resolution,
        "subtitles_burned": burn_subs and step3_output is not None,
        "srt_path": srt_path if burn_subs else None
    }


def build_video_from_outputs(
    step2_output_path: str,
    step3_output_path: str,
    output_video_path: str,
    images_dir: str = "outputs/images",
    audio_dir: str = "outputs/audio",
    burn_subs: bool = True
) -> Dict[str, Any]:
    """
    Step2/Step3 output 파일을 직접 읽어서 영상 생성 + 자막 번인

    Args:
        step2_output_path: step2_output.json 경로
        step3_output_path: step3_output.json 경로
        output_video_path: 최종 영상 출력 경로
        images_dir: 이미지 파일 디렉토리
        audio_dir: 오디오 파일 디렉토리
        burn_subs: 자막 번인 여부

    Returns:
        결과 딕셔너리
    """
    print("=== [FFmpeg] Building video from output files ===")

    # JSON 로드
    with open(step2_output_path, "r", encoding="utf-8") as f:
        step2 = json.load(f)

    with open(step3_output_path, "r", encoding="utf-8") as f:
        step3 = json.load(f)

    title = step3.get("title", step2.get("title", "Untitled"))
    scenes = step2.get("scenes_for_image", [])
    audio_files = step3.get("audio_files", [])

    # cuts 배열 구성
    cuts = []
    for i, scene in enumerate(scenes):
        scene_id = scene.get("scene_id", f"scene{i+1}")

        # 해당 씬의 오디오 정보 찾기
        audio_info = next(
            (a for a in audio_files if a.get("scene_id") == scene_id),
            {}
        )

        # 이미지 경로 (실제 파일이 있어야 함)
        image_path = scene.get("image_path")
        if not image_path or not os.path.exists(image_path):
            image_path = os.path.join(images_dir, f"{scene_id}.png")
            if not os.path.exists(image_path):
                image_path = os.path.join(images_dir, f"{scene_id}.jpg")

        # 오디오 경로
        audio_path = audio_info.get("audio_path") or audio_info.get("audio_filename", "")
        if audio_path and not os.path.isabs(audio_path):
            audio_path = os.path.join(os.path.dirname(step3_output_path), "..", audio_path)

        cuts.append({
            "cut_id": i + 1,
            "image_path": image_path,
            "audio_path": audio_path,
            "duration_seconds": audio_info.get("duration_seconds", 10.0)
        })

    # Step4 입력 구성
    step4_input = {
        "title": title,
        "cuts": cuts,
        "output_resolution": "1080p",
        "fps": 30
    }

    return build_video_ffmpeg(step4_input, step3_output=step3, burn_subs=burn_subs)


def _sanitize_filename(title: str) -> str:
    """파일명으로 사용할 수 없는 문자 제거"""
    import re
    sanitized = re.sub(r'[<>:"/\\|?*]', '', title)
    sanitized = sanitized.replace(' ', '_')
    sanitized = sanitized.replace(',', '_')
    return sanitized[:50]


if __name__ == "__main__":
    # FFmpeg 설치 확인
    if check_ffmpeg_installed():
        print("FFmpeg is installed ✓")
    else:
        print("FFmpeg is NOT installed")
        print("Install with:")
        print("  Linux: apt-get install ffmpeg")
        print("  Mac: brew install ffmpeg")

    # 테스트 (실제 파일이 있을 때만 동작)
    # result = build_video_from_outputs(
    #     step2_output_path="outputs/step2_output.json",
    #     step3_output_path="outputs/step3_output.json",
    #     output_video_path="outputs/final_video.mp4",
    #     burn_subs=True
    # )
    # print(json.dumps(result, ensure_ascii=False, indent=2))
