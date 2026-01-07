"""
한국사 파이프라인 - 영상 렌더링 모듈 (FFmpeg 기반)

- 이미지 + 오디오 합성
- SRT → ASS 자막 변환 및 하드코딩
- 독립 실행 가능 (외부 의존성 없음)
"""

import os
import re
import subprocess
import tempfile
import shutil
from typing import Dict, Any, List


def get_audio_duration(audio_path: str) -> float:
    """오디오 파일의 재생 시간(초) 반환"""
    try:
        result = subprocess.run(
            ['ffprobe', '-v', 'error', '-show_entries', 'format=duration',
             '-of', 'default=noprint_wrappers=1:nokey=1', audio_path],
            capture_output=True, text=True, timeout=30
        )
        return float(result.stdout.strip()) if result.stdout.strip() else 60.0
    except Exception:
        return 60.0


def srt_to_ass(srt_content: str, font_name: str = "NotoSansKR-Bold") -> str:
    """SRT를 ASS 형식으로 변환"""

    def srt_to_ass_time(srt_time: str) -> str:
        """SRT 타임스탬프를 ASS 형식으로 변환"""
        hours, minutes, seconds_ms = srt_time.split(':')
        seconds, milliseconds = seconds_ms.split(',')
        centiseconds = int(milliseconds) // 10
        return f"{int(hours)}:{minutes}:{seconds}.{centiseconds:02d}"

    ass_header = f"""[Script Info]
ScriptType: v4.00+
Collisions: Normal
PlayResX: 1920
PlayResY: 1080

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,{font_name},40,&HFFFFFF,&H000000FF,&H00000000,&H80000000,1,0,0,0,100,100,0,0,4,1,0,2,20,20,50,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

    ass_events = []
    srt_normalized = srt_content.replace('\r\n', '\n').strip()
    srt_blocks = re.split(r'\n\s*\n', srt_normalized)

    for block in srt_blocks:
        lines = block.strip().split('\n')
        if len(lines) >= 3:
            time_match = re.match(
                r'(\d{2}:\d{2}:\d{2},\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2},\d{3})',
                lines[1]
            )
            if time_match:
                start_time = srt_to_ass_time(time_match.group(1))
                end_time = srt_to_ass_time(time_match.group(2))
                text = '\\N'.join(lines[2:])
                ass_events.append(f"Dialogue: 0,{start_time},{end_time},Default,,0,0,0,,{text}")

    return ass_header + '\n'.join(ass_events)


def render_video(
    audio_path: str,
    image_path: str,
    output_path: str,
    srt_path: str = None,
    resolution: str = "1920x1080",
    fps: int = 30,
) -> Dict[str, Any]:
    """
    단일 이미지 + 오디오로 영상 생성

    Args:
        audio_path: TTS 오디오 파일 경로
        image_path: 배경 이미지 경로
        output_path: 출력 영상 경로
        srt_path: SRT 자막 파일 경로 (선택)
        resolution: 해상도 (기본: 1920x1080)
        fps: 프레임레이트 (기본: 30)

    Returns:
        {"ok": True, "video_path": "...", "duration": 900.5}
    """
    try:
        # FFmpeg 확인
        ffmpeg_path = shutil.which('ffmpeg')
        if not ffmpeg_path:
            return {"ok": False, "error": "FFmpeg가 설치되어 있지 않습니다."}

        # 오디오 길이 확인
        duration = get_audio_duration(audio_path)
        print(f"[HISTORY-RENDERER] 오디오 길이: {duration:.1f}초")

        # 임시 디렉토리 생성
        with tempfile.TemporaryDirectory() as temp_dir:
            width, height = resolution.split('x')

            # 기본 FFmpeg 필터
            vf_filter = f"scale={width}:{height}:force_original_aspect_ratio=decrease,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2"

            # 자막 처리
            if srt_path and os.path.exists(srt_path):
                print(f"[HISTORY-RENDERER] 자막 파일: {srt_path}")
                with open(srt_path, 'r', encoding='utf-8') as f:
                    srt_content = f.read()

                # SRT → ASS 변환
                ass_content = srt_to_ass(srt_content)
                ass_path = os.path.join(temp_dir, "subtitle.ass")
                with open(ass_path, 'w', encoding='utf-8') as f:
                    f.write(ass_content)

                # ASS 필터 추가
                escaped_ass_path = ass_path.replace('\\', '\\\\').replace(':', '\\:')
                vf_filter = f"{vf_filter},ass={escaped_ass_path}"

            # FFmpeg 명령어 구성
            ffmpeg_cmd = [
                'ffmpeg', '-y',
                '-loop', '1', '-i', image_path,  # 이미지를 무한 루프
                '-i', audio_path,
                '-vf', vf_filter,
                '-c:v', 'libx264', '-preset', 'ultrafast', '-crf', '28',
                '-c:a', 'aac', '-b:a', '128k',
                '-r', str(fps),
                '-shortest',  # 오디오 길이에 맞춤
                '-pix_fmt', 'yuv420p',
                '-threads', '2',
                output_path
            ]

            print(f"[HISTORY-RENDERER] FFmpeg 실행 중...")
            process = subprocess.run(
                ffmpeg_cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                timeout=1800  # 30분 타임아웃
            )

            if process.returncode != 0:
                error_msg = process.stderr.decode('utf-8', errors='ignore')[:500]
                print(f"[HISTORY-RENDERER] FFmpeg 오류: {error_msg}")
                return {"ok": False, "error": f"FFmpeg 오류: {error_msg[:200]}"}

            # 결과 확인
            if os.path.exists(output_path):
                file_size = os.path.getsize(output_path)
                print(f"[HISTORY-RENDERER] 완료: {output_path} ({file_size / 1024 / 1024:.1f}MB)")
                return {
                    "ok": True,
                    "video_path": output_path,
                    "duration": duration,
                }
            else:
                return {"ok": False, "error": "출력 파일이 생성되지 않았습니다."}

    except subprocess.TimeoutExpired:
        return {"ok": False, "error": "FFmpeg 타임아웃 (30분 초과)"}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def render_multi_image_video(
    audio_path: str,
    image_paths: List[str],
    output_path: str,
    srt_path: str = None,
    resolution: str = "1920x1080",
    fps: int = 30,
) -> Dict[str, Any]:
    """
    여러 이미지 + 오디오로 영상 생성 (시간 균등 분배)

    Args:
        audio_path: TTS 오디오 파일 경로
        image_paths: 배경 이미지 경로 목록
        output_path: 출력 영상 경로
        srt_path: SRT 자막 파일 경로 (선택)
        resolution: 해상도
        fps: 프레임레이트

    Returns:
        {"ok": True, "video_path": "...", "duration": 900.5}
    """
    if not image_paths:
        return {"ok": False, "error": "이미지가 없습니다."}

    if len(image_paths) == 1:
        return render_video(
            audio_path=audio_path,
            image_path=image_paths[0],
            output_path=output_path,
            srt_path=srt_path,
            resolution=resolution,
            fps=fps,
        )

    try:
        ffmpeg_path = shutil.which('ffmpeg')
        if not ffmpeg_path:
            return {"ok": False, "error": "FFmpeg가 설치되어 있지 않습니다."}

        # 오디오 길이 확인
        duration = get_audio_duration(audio_path)
        image_duration = duration / len(image_paths)
        print(f"[HISTORY-RENDERER] 오디오: {duration:.1f}초, 이미지당: {image_duration:.1f}초")

        with tempfile.TemporaryDirectory() as temp_dir:
            width, height = resolution.split('x')

            # 이미지 리스트 파일 생성
            list_path = os.path.join(temp_dir, "images.txt")
            with open(list_path, 'w') as f:
                for img_path in image_paths:
                    f.write(f"file '{img_path}'\n")
                    f.write(f"duration {image_duration}\n")
                f.write(f"file '{image_paths[-1]}'\n")  # 마지막 이미지 한번 더

            # 기본 필터
            vf_filter = f"scale={width}:{height}:force_original_aspect_ratio=decrease,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2"

            # 자막 처리
            if srt_path and os.path.exists(srt_path):
                with open(srt_path, 'r', encoding='utf-8') as f:
                    srt_content = f.read()

                ass_content = srt_to_ass(srt_content)
                ass_path = os.path.join(temp_dir, "subtitle.ass")
                with open(ass_path, 'w', encoding='utf-8') as f:
                    f.write(ass_content)

                escaped_ass_path = ass_path.replace('\\', '\\\\').replace(':', '\\:')
                vf_filter = f"{vf_filter},ass={escaped_ass_path}"

            # FFmpeg 명령어
            ffmpeg_cmd = [
                'ffmpeg', '-y',
                '-f', 'concat', '-safe', '0', '-i', list_path,
                '-i', audio_path,
                '-vf', vf_filter,
                '-c:v', 'libx264', '-preset', 'ultrafast', '-crf', '28',
                '-c:a', 'aac', '-b:a', '128k',
                '-r', str(fps),
                '-shortest',
                '-pix_fmt', 'yuv420p',
                '-threads', '2',
                output_path
            ]

            print(f"[HISTORY-RENDERER] FFmpeg 실행 중... ({len(image_paths)}개 이미지)")
            process = subprocess.run(
                ffmpeg_cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                timeout=1800
            )

            if process.returncode != 0:
                error_msg = process.stderr.decode('utf-8', errors='ignore')[:500]
                return {"ok": False, "error": f"FFmpeg 오류: {error_msg[:200]}"}

            if os.path.exists(output_path):
                file_size = os.path.getsize(output_path)
                print(f"[HISTORY-RENDERER] 완료: {output_path} ({file_size / 1024 / 1024:.1f}MB)")
                return {
                    "ok": True,
                    "video_path": output_path,
                    "duration": duration,
                }
            else:
                return {"ok": False, "error": "출력 파일이 생성되지 않았습니다."}

    except subprocess.TimeoutExpired:
        return {"ok": False, "error": "FFmpeg 타임아웃"}
    except Exception as e:
        return {"ok": False, "error": str(e)}


if __name__ == "__main__":
    print("history_pipeline/renderer.py 로드 완료")
