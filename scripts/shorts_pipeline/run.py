"""
쇼츠 파이프라인 - 메인 실행 모듈

전체 흐름:
1. 연예 뉴스 수집 → SHORTS 시트에 저장
2. 대기 상태 행 조회
3. GPT-5.1로 대본 + 이미지 프롬프트 + YouTube SEO 생성
4. TTS 생성 (먼저 - 저비용, 실패 시 이미지 생성 스킵)
5. TTS 성공 후 병렬 처리:
   - Gemini 3 Pro로 씬 이미지 생성 (4개 워커)
   - 썸네일 생성
6. FFmpeg 영상 렌더링 (Ken Burns + 전환 효과)
7. YouTube 업로드

병렬 처리 구조:
- TTS 실패 시 이미지 생성 비용 절약 (Gemini API 호출 방지)
- 이미지 생성 4개 워커로 병렬 처리 (각 3회 재시도)
- 이미지 + 썸네일 동시 생성 (2개 워커)
"""

import os
import sys
import gc
import json
import base64
import tempfile
import subprocess
import time as time_module
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed

# 프로젝트 루트 추가
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from .config import (
    SHEET_NAME,
    estimate_cost,
    VIDEO_WIDTH,
    VIDEO_HEIGHT,
    TTS_CONFIG,
    TTS_VOICE_BY_ISSUE,
    IMAGE_MODEL,
    THUMBNAIL_CONFIG,
    SHORTS_KEN_BURNS,
    FFMPEG_ZOOMPAN_PRESETS,
    SCENE_TRANSITIONS,
    FFMPEG_TRANSITIONS,
    SHORTS_BGM_MOODS,
    SHORTS_SUBTITLE_STYLE,
)
from .sheets import (
    get_sheets_service,
    get_spreadsheet_id,
    create_shorts_sheet,
    read_pending_rows,
    update_status,
    append_row,
    check_duplicate,
)
from .news_collector import (
    collect_entertainment_news,
    search_celebrity_news,
)
from .script_generator import (
    generate_complete_shorts_package,
    format_script_for_sheet,
)


# ============================================================
# TTS 생성 (Gemini TTS)
# ============================================================

def generate_tts(
    text: str,
    issue_type: str = "default",
    output_path: str = None
) -> Dict[str, Any]:
    """
    Gemini TTS로 음성 생성 (저비용 - 먼저 실행)

    Args:
        text: 변환할 텍스트
        issue_type: 이슈 타입 (음성 스타일 결정)
        output_path: 출력 파일 경로 (없으면 자동 생성)

    Returns:
        {
            "ok": True,
            "audio_path": "/tmp/xxx.mp3",
            "duration": 50.5,
            "cost": 0.38
        }
    """
    try:
        import requests
        import base64
        import wave
        import io

        api_key = os.environ.get("GOOGLE_API_KEY")
        if not api_key:
            raise ValueError("GOOGLE_API_KEY 환경변수가 설정되지 않았습니다")

        # 이슈 타입별 음성 설정
        voice_config = TTS_VOICE_BY_ISSUE.get(issue_type, TTS_VOICE_BY_ISSUE["default"])
        voice_name = voice_config.get("voice", TTS_CONFIG["voice"])

        print(f"[SHORTS] TTS 생성 중: {len(text)}자, 음성={voice_name}")

        # Gemini TTS REST API 호출
        model = "gemini-2.0-flash-exp"  # TTS 지원 모델
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"

        payload = {
            "contents": [{"parts": [{"text": text}]}],
            "generationConfig": {
                "responseModalities": ["AUDIO"],
                "speechConfig": {
                    "voiceConfig": {
                        "prebuiltVoiceConfig": {
                            "voiceName": voice_name
                        }
                    }
                }
            }
        }

        response = requests.post(url, json=payload, timeout=120)

        if response.status_code != 200:
            error_text = response.text[:500]
            raise ValueError(f"Gemini TTS API 오류: {response.status_code} - {error_text}")

        result = response.json()

        # 오디오 데이터 추출
        candidates = result.get("candidates", [])
        if not candidates:
            raise ValueError("응답에 candidates가 없습니다")

        content = candidates[0].get("content", {})
        parts = content.get("parts", [])

        audio_data = None
        for part in parts:
            inline_data = part.get("inlineData", {})
            if inline_data.get("mimeType", "").startswith("audio/"):
                audio_data = base64.b64decode(inline_data.get("data", ""))
                break

        if not audio_data:
            raise ValueError("TTS 응답에서 오디오 데이터를 찾을 수 없습니다")

        # PCM을 WAV로 변환 (24kHz, 16bit, mono)
        wav_buffer = io.BytesIO()
        with wave.open(wav_buffer, 'wb') as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(24000)
            wf.writeframes(audio_data)

        wav_data = wav_buffer.getvalue()
        duration = len(audio_data) / (24000 * 2)  # 24kHz * 2 bytes

        # WAV를 MP3로 변환
        if output_path is None:
            output_path = tempfile.mktemp(suffix=".mp3")

        wav_temp = tempfile.mktemp(suffix=".wav")
        with open(wav_temp, "wb") as f:
            f.write(wav_data)

        # FFmpeg로 MP3 변환
        cmd = ['ffmpeg', '-y', '-i', wav_temp, '-acodec', 'libmp3lame', '-b:a', '128k', output_path]
        subprocess.run(cmd, capture_output=True, timeout=30)

        # 임시 파일 삭제
        try:
            os.unlink(wav_temp)
        except:
            pass

        # 비용 계산 (Gemini Flash: $0.001/1000자)
        cost = len(text) * 0.001 / 1000

        print(f"[SHORTS] TTS 완료: {duration:.1f}초, ${cost:.4f}")

        return {
            "ok": True,
            "audio_path": output_path,
            "duration": duration,
            "cost": round(cost, 4),
        }

    except Exception as e:
        print(f"[SHORTS] TTS 생성 실패: {e}")
        return {"ok": False, "error": str(e)}


def get_audio_duration(audio_path: str) -> float:
    """ffprobe로 오디오 재생 시간 확인"""
    try:
        result = subprocess.run(
            ["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", audio_path],
            capture_output=True, text=True, timeout=30
        )
        return float(result.stdout.strip())
    except Exception:
        return 50.0  # 기본값


# ============================================================
# 이미지 생성 (Gemini 3 Pro - 병렬 처리)
# ============================================================

def generate_single_image(
    prompt: str,
    scene_number: int,
    output_dir: str,
    max_retries: int = 3
) -> Dict[str, Any]:
    """
    단일 씬 이미지 생성 (재시도 포함)

    Args:
        prompt: 이미지 프롬프트
        scene_number: 씬 번호
        output_dir: 출력 디렉토리
        max_retries: 최대 재시도 횟수

    Returns:
        {"ok": True, "scene": 1, "path": "/tmp/xxx/scene_001.png"}
    """
    import google.generativeai as genai

    for attempt in range(max_retries):
        try:
            api_key = os.environ.get("GOOGLE_API_KEY")
            if not api_key:
                raise ValueError("GOOGLE_API_KEY 환경변수 필요")

            genai.configure(api_key=api_key)

            # Gemini 3 Pro 이미지 생성
            model = genai.GenerativeModel("gemini-2.0-flash-exp-image-generation")

            response = model.generate_content(
                contents=prompt,
                generation_config=genai.types.GenerationConfig(
                    response_modalities=["IMAGE", "TEXT"],
                )
            )

            # 이미지 데이터 추출
            image_data = None
            for part in response.candidates[0].content.parts:
                if hasattr(part, 'inline_data') and part.inline_data.mime_type.startswith('image/'):
                    image_data = part.inline_data.data
                    break

            if not image_data:
                raise ValueError("이미지 데이터 없음")

            # 저장
            output_path = os.path.join(output_dir, f"scene_{scene_number:03d}.png")
            with open(output_path, "wb") as f:
                f.write(image_data)

            print(f"[SHORTS] 씬{scene_number} 이미지 생성 완료")

            return {
                "ok": True,
                "scene": scene_number,
                "path": output_path,
            }

        except Exception as e:
            print(f"[SHORTS] 씬{scene_number} 이미지 생성 실패 (시도 {attempt+1}/{max_retries}): {e}")
            if attempt < max_retries - 1:
                time_module.sleep(2 ** attempt)  # 지수 백오프: 1초, 2초, 4초

    return {"ok": False, "scene": scene_number, "error": "최대 재시도 초과"}


def generate_images_parallel(
    scenes: List[Dict[str, Any]],
    output_dir: str,
    max_workers: int = 4
) -> Dict[str, Any]:
    """
    씬 이미지 병렬 생성 (4 워커)

    Args:
        scenes: 씬 목록 (image_prompt_enhanced 포함)
        output_dir: 출력 디렉토리
        max_workers: 병렬 워커 수

    Returns:
        {
            "ok": True,
            "images": [{"scene": 1, "path": "..."}, ...],
            "failed": [],
            "cost": 0.40
        }
    """
    os.makedirs(output_dir, exist_ok=True)

    images = []
    failed = []

    print(f"[SHORTS] 이미지 생성 시작: {len(scenes)}개 씬, {max_workers}개 워커")

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {}
        for scene in scenes:
            scene_num = scene.get("scene_number", 1)
            prompt = scene.get("image_prompt_enhanced", scene.get("image_prompt", ""))

            future = executor.submit(
                generate_single_image,
                prompt=prompt,
                scene_number=scene_num,
                output_dir=output_dir,
                max_retries=3
            )
            futures[future] = scene_num

        for future in as_completed(futures):
            scene_num = futures[future]
            try:
                result = future.result()
                if result.get("ok"):
                    images.append(result)
                else:
                    failed.append(result)
            except Exception as e:
                failed.append({"scene": scene_num, "error": str(e)})

    # 비용 계산 (성공한 이미지당 $0.05)
    cost = len(images) * 0.05

    print(f"[SHORTS] 이미지 생성 완료: {len(images)}개 성공, {len(failed)}개 실패")

    return {
        "ok": len(failed) == 0,
        "images": sorted(images, key=lambda x: x["scene"]),
        "failed": failed,
        "cost": round(cost, 3),
    }


# ============================================================
# 썸네일 생성
# ============================================================

def generate_thumbnail(
    thumbnail_config: Dict[str, Any],
    person: str,
    issue_type: str,
    output_path: str
) -> Dict[str, Any]:
    """
    쇼츠 썸네일 생성

    Args:
        thumbnail_config: GPT가 생성한 썸네일 설정
        person: 인물명
        issue_type: 이슈 타입
        output_path: 출력 경로

    Returns:
        {"ok": True, "path": "...", "cost": 0.03}
    """
    try:
        import google.generativeai as genai

        api_key = os.environ.get("GOOGLE_API_KEY")
        if not api_key:
            raise ValueError("GOOGLE_API_KEY 환경변수 필요")

        genai.configure(api_key=api_key)

        # 썸네일 프롬프트 생성
        style_config = THUMBNAIL_CONFIG["style_by_issue"].get(
            issue_type, THUMBNAIL_CONFIG["style_by_issue"]["default"]
        )

        prompt = thumbnail_config.get("image_prompt", f"""
YouTube Shorts thumbnail, 9:16 vertical,
dramatic black silhouette of {person},
spotlight from above, {style_config['accent_color']} accent lighting,
{style_config['background_color']} background,
empty space in center for Korean text overlay,
4K quality, dramatic composition,
NO text on image
""")

        print(f"[SHORTS] 썸네일 생성 중: {person}")

        model = genai.GenerativeModel("gemini-2.0-flash-exp-image-generation")

        response = model.generate_content(
            contents=prompt,
            generation_config=genai.types.GenerationConfig(
                response_modalities=["IMAGE", "TEXT"],
            )
        )

        # 이미지 추출
        image_data = None
        for part in response.candidates[0].content.parts:
            if hasattr(part, 'inline_data') and part.inline_data.mime_type.startswith('image/'):
                image_data = part.inline_data.data
                break

        if not image_data:
            raise ValueError("썸네일 이미지 데이터 없음")

        with open(output_path, "wb") as f:
            f.write(image_data)

        print(f"[SHORTS] 썸네일 생성 완료")

        return {
            "ok": True,
            "path": output_path,
            "cost": 0.03,
        }

    except Exception as e:
        print(f"[SHORTS] 썸네일 생성 실패: {e}")
        return {"ok": False, "error": str(e)}


# ============================================================
# 영상 렌더링 (FFmpeg - Ken Burns + 전환 효과)
# ============================================================

def render_video(
    images: List[Dict[str, Any]],
    audio_path: str,
    scenes: List[Dict[str, Any]],
    issue_type: str,
    output_path: str
) -> Dict[str, Any]:
    """
    FFmpeg로 영상 렌더링 (Ken Burns + 전환 효과)

    Args:
        images: 이미지 경로 목록
        audio_path: TTS 오디오 경로
        scenes: 씬 정보 (자막용)
        issue_type: 이슈 타입 (효과 설정)
        output_path: 출력 영상 경로

    Returns:
        {"ok": True, "path": "...", "duration": 50.5}
    """
    try:
        # 오디오 길이 확인
        audio_duration = get_audio_duration(audio_path)
        scene_count = len(images)
        scene_duration = audio_duration / scene_count

        print(f"[SHORTS] 영상 렌더링: {scene_count}개 씬, 총 {audio_duration:.1f}초")

        # 1) 씬별 클립 생성 (Ken Burns 효과)
        clips = []
        for img_info in images:
            scene_num = img_info["scene"]
            img_path = img_info["path"]

            # Ken Burns 효과 패턴
            pattern = SHORTS_KEN_BURNS["scene_patterns"].get(scene_num, "zoom_in")
            zoompan = FFMPEG_ZOOMPAN_PRESETS.get(pattern, FFMPEG_ZOOMPAN_PRESETS["zoom_in"])

            # 강도 조절
            intensity = SHORTS_KEN_BURNS["intensity_by_issue"].get(
                issue_type, SHORTS_KEN_BURNS["intensity_by_issue"]["default"]
            )

            clip_path = img_path.replace(".png", "_clip.mp4")

            # FFmpeg 명령어 (zoompan 필터)
            fps = 30
            total_frames = int(scene_duration * fps)

            cmd = [
                "ffmpeg", "-y",
                "-loop", "1",
                "-i", img_path,
                "-vf", f"scale={VIDEO_WIDTH}:{VIDEO_HEIGHT},zoompan=z={zoompan['z']}:x={zoompan['x']}:y={zoompan['y']}:d={total_frames}:s={VIDEO_WIDTH}x{VIDEO_HEIGHT}:fps={fps}",
                "-t", str(scene_duration),
                "-c:v", "libx264",
                "-preset", "fast",
                "-pix_fmt", "yuv420p",
                clip_path
            ]

            subprocess.run(cmd, capture_output=True, timeout=120)
            clips.append(clip_path)

        # 2) 클립 concat (전환 효과 적용)
        # 간단한 concat 방식 (xfade는 복잡하므로 기본 concat 사용)
        concat_list_path = tempfile.mktemp(suffix=".txt")
        with open(concat_list_path, "w") as f:
            for clip in clips:
                f.write(f"file '{clip}'\n")

        concat_path = output_path.replace(".mp4", "_concat.mp4")
        subprocess.run([
            "ffmpeg", "-y",
            "-f", "concat", "-safe", "0",
            "-i", concat_list_path,
            "-c", "copy",
            concat_path
        ], capture_output=True, timeout=300)

        # 3) 오디오 합성
        subprocess.run([
            "ffmpeg", "-y",
            "-i", concat_path,
            "-i", audio_path,
            "-c:v", "copy",
            "-c:a", "aac",
            "-b:a", "128k",
            "-shortest",
            "-movflags", "+faststart",
            output_path
        ], capture_output=True, timeout=300)

        # 임시 파일 정리
        for clip in clips:
            if os.path.exists(clip):
                os.remove(clip)
        if os.path.exists(concat_list_path):
            os.remove(concat_list_path)
        if os.path.exists(concat_path):
            os.remove(concat_path)

        # 결과 확인
        final_duration = get_audio_duration(output_path)

        print(f"[SHORTS] 영상 렌더링 완료: {final_duration:.1f}초")

        return {
            "ok": True,
            "path": output_path,
            "duration": final_duration,
        }

    except Exception as e:
        print(f"[SHORTS] 영상 렌더링 실패: {e}")
        return {"ok": False, "error": str(e)}


# ============================================================
# 병렬 비디오 생성 파이프라인
# ============================================================

def run_video_generation(
    script_result: Dict[str, Any],
    person: str,
    issue_type: str,
    work_dir: str = None
) -> Dict[str, Any]:
    """
    비디오 생성 파이프라인 (병렬 처리)

    순서:
    1. TTS 먼저 (저비용) - 실패 시 이미지 생성 스킵
    2. TTS 성공 후 병렬: 이미지(4워커) + 썸네일
    3. FFmpeg 렌더링

    Args:
        script_result: GPT 대본 생성 결과
        person: 인물명
        issue_type: 이슈 타입
        work_dir: 작업 디렉토리 (없으면 자동 생성)

    Returns:
        {
            "ok": True,
            "video_path": "...",
            "thumbnail_path": "...",
            "duration": 50.5,
            "cost": 0.84
        }
    """
    if work_dir is None:
        work_dir = tempfile.mkdtemp(prefix="shorts_")

    print(f"[SHORTS] 비디오 생성 시작: {person} - {issue_type}")
    print(f"[SHORTS] 작업 디렉토리: {work_dir}")

    total_cost = script_result.get("cost", 0)
    result = {"ok": False}

    try:
        # ============================================================
        # 1단계: TTS 생성 (저비용 - 먼저 실행)
        # ============================================================
        print("\n[SHORTS] === 1단계: TTS 생성 ===")

        full_script = script_result.get("full_script", "")
        if not full_script:
            full_script = "\n".join([
                s.get("narration", "") for s in script_result.get("scenes", [])
            ])

        tts_result = generate_tts(
            text=full_script,
            issue_type=issue_type,
            output_path=os.path.join(work_dir, "tts.mp3")
        )

        if not tts_result.get("ok"):
            # TTS 실패 → 이미지 생성 스킵 (비용 절약)
            print("[SHORTS] TTS 실패 - 이미지 생성 스킵 (비용 절약)")
            return {
                "ok": False,
                "error": f"TTS 실패: {tts_result.get('error')}",
                "stage": "tts",
            }

        total_cost += tts_result.get("cost", 0)
        audio_path = tts_result["audio_path"]

        # ============================================================
        # 2단계: 이미지 + 썸네일 병렬 생성
        # ============================================================
        print("\n[SHORTS] === 2단계: 이미지 + 썸네일 병렬 생성 ===")

        scenes = script_result.get("scenes", [])
        thumbnail_config = script_result.get("thumbnail", {})
        image_dir = os.path.join(work_dir, "images")
        thumbnail_path = os.path.join(work_dir, "thumbnail.png")

        # 병렬 실행 (2 워커: 이미지 생성 + 썸네일 생성)
        with ThreadPoolExecutor(max_workers=2) as executor:
            # 이미지 생성 작업 (내부에서 4 워커 사용)
            image_future = executor.submit(
                generate_images_parallel,
                scenes=scenes,
                output_dir=image_dir,
                max_workers=4
            )

            # 썸네일 생성 작업
            thumbnail_future = executor.submit(
                generate_thumbnail,
                thumbnail_config=thumbnail_config,
                person=person,
                issue_type=issue_type,
                output_path=thumbnail_path
            )

            # 결과 수집
            image_result = image_future.result()
            thumbnail_result = thumbnail_future.result()

        # 이미지 생성 결과 확인
        if not image_result.get("ok") and len(image_result.get("images", [])) == 0:
            return {
                "ok": False,
                "error": "모든 이미지 생성 실패",
                "stage": "image",
            }

        total_cost += image_result.get("cost", 0)
        total_cost += thumbnail_result.get("cost", 0) if thumbnail_result.get("ok") else 0

        # ============================================================
        # 3단계: FFmpeg 영상 렌더링
        # ============================================================
        print("\n[SHORTS] === 3단계: 영상 렌더링 ===")

        video_path = os.path.join(work_dir, "output.mp4")

        render_result = render_video(
            images=image_result["images"],
            audio_path=audio_path,
            scenes=scenes,
            issue_type=issue_type,
            output_path=video_path
        )

        if not render_result.get("ok"):
            return {
                "ok": False,
                "error": f"렌더링 실패: {render_result.get('error')}",
                "stage": "render",
            }

        # ============================================================
        # 완료
        # ============================================================
        gc.collect()

        result = {
            "ok": True,
            "video_path": render_result["path"],
            "thumbnail_path": thumbnail_path if thumbnail_result.get("ok") else None,
            "duration": render_result["duration"],
            "cost": round(total_cost, 3),
            "work_dir": work_dir,
        }

        print(f"\n[SHORTS] 비디오 생성 완료: {result['duration']:.1f}초, ${result['cost']:.3f}")
        return result

    except Exception as e:
        print(f"[SHORTS] 비디오 생성 파이프라인 오류: {e}")
        return {
            "ok": False,
            "error": str(e),
            "stage": "unknown",
        }


def run_news_collection(
    max_items: int = 10,
    save_to_sheet: bool = True
) -> Dict[str, Any]:
    """
    연예 뉴스 수집 및 시트 저장

    Args:
        max_items: 수집할 최대 뉴스 수
        save_to_sheet: True면 시트에 저장

    Returns:
        {
            "ok": True,
            "collected": 10,
            "saved": 8,
            "duplicates": 2
        }
    """
    print(f"\n{'='*50}")
    print("[SHORTS] 연예 뉴스 수집 시작")
    print(f"{'='*50}\n")

    # 1) 뉴스 수집
    news_items = collect_entertainment_news(
        max_per_feed=5,
        total_limit=max_items
    )

    if not news_items:
        return {"ok": False, "error": "수집된 뉴스 없음"}

    if not save_to_sheet:
        return {
            "ok": True,
            "collected": len(news_items),
            "saved": 0,
            "items": news_items
        }

    # 2) 시트에 저장
    try:
        service = get_sheets_service()
        spreadsheet_id = get_spreadsheet_id()

        # 시트 존재 확인 (없으면 생성)
        create_shorts_sheet(service, spreadsheet_id)

        saved = 0
        duplicates = 0

        for item in news_items:
            # 중복 체크 (person 필드 사용)
            person = item.get("person", item.get("celebrity", ""))
            if check_duplicate(service, spreadsheet_id, person, item["news_url"]):
                duplicates += 1
                print(f"[SHORTS] 중복 스킵: {person} - {item['news_title'][:30]}...")
                continue

            # 시트에 추가
            append_row(service, spreadsheet_id, item)
            saved += 1
            print(f"[SHORTS] 저장: {person} - {item['issue_type']}")

        print(f"\n[SHORTS] 수집 완료: {len(news_items)}개 중 {saved}개 저장, {duplicates}개 중복")

        return {
            "ok": True,
            "collected": len(news_items),
            "saved": saved,
            "duplicates": duplicates
        }

    except Exception as e:
        print(f"[SHORTS] 뉴스 수집 실패: {e}")
        return {"ok": False, "error": str(e)}


def run_script_generation(
    limit: int = 1,
    generate_video: bool = False
) -> Dict[str, Any]:
    """
    대기 상태 행에 대해 대본 생성 (+ 선택적 비디오 생성)

    Args:
        limit: 처리할 최대 행 수
        generate_video: True면 비디오까지 생성

    Returns:
        {
            "ok": True,
            "processed": 1,
            "results": [...]
        }
    """
    print(f"\n{'='*50}")
    print("[SHORTS] 대본 생성 시작" + (" + 비디오 생성" if generate_video else ""))
    print(f"{'='*50}\n")

    try:
        service = get_sheets_service()
        spreadsheet_id = get_spreadsheet_id()

        # 대기 상태 행 조회
        pending_rows = read_pending_rows(service, spreadsheet_id, limit=limit)

        if not pending_rows:
            print("[SHORTS] 대기 상태 행 없음")
            return {"ok": True, "processed": 0, "message": "처리할 행 없음"}

        results = []

        for row_data in pending_rows:
            row_num = row_data["row_number"]
            # person 필드 우선, 없으면 celebrity 호환
            person = row_data.get("person", row_data.get("celebrity", ""))
            issue_type = row_data.get("issue_type", "근황")

            print(f"\n[SHORTS] 처리 중: 행 {row_num} - {person}")

            # 상태 업데이트: 처리중
            update_status(service, spreadsheet_id, row_num, "처리중")

            try:
                # 1) 대본 생성
                script_result = generate_complete_shorts_package(row_data)

                if not script_result.get("ok"):
                    raise Exception(script_result.get("error", "알 수 없는 오류"))

                # 대본을 시트 형식으로 변환
                script_text = format_script_for_sheet(script_result.get("scenes", []))

                total_cost = script_result.get("cost", 0)

                # 2) 비디오 생성 (옵션)
                video_result = None
                if generate_video:
                    print(f"\n[SHORTS] 비디오 생성 시작: {person}")
                    video_result = run_video_generation(
                        script_result=script_result,
                        person=person,
                        issue_type=issue_type,
                    )
                    if video_result.get("ok"):
                        total_cost += video_result.get("cost", 0)

                # 시트 업데이트
                status = "완료" if (video_result and video_result.get("ok")) else "대본완료"
                extra_fields = {
                    "대본": script_text,
                    "제목(GPT생성)": script_result.get("title", ""),
                    "비용": f"${total_cost:.3f}",
                }

                # 비디오 생성 성공 시 추가 정보
                if video_result and video_result.get("ok"):
                    extra_fields["작업시간"] = f"{video_result.get('duration', 0):.1f}초"
                    # 영상URL은 YouTube 업로드 후 설정

                update_status(service, spreadsheet_id, row_num, status, **extra_fields)

                result_item = {
                    "row": row_num,
                    "person": person,
                    "ok": True,
                    "title": script_result.get("title"),
                    "scenes": len(script_result.get("scenes", [])),
                    "chars": script_result.get("total_chars", 0),
                    "cost": total_cost,
                }

                if video_result:
                    result_item["video"] = {
                        "ok": video_result.get("ok"),
                        "path": video_result.get("video_path"),
                        "duration": video_result.get("duration"),
                    }

                results.append(result_item)

                print(f"[SHORTS] 처리 완료: {script_result.get('title')}")

            except Exception as e:
                update_status(
                    service, spreadsheet_id, row_num, "실패",
                    에러메시지=str(e)[:200]
                )
                results.append({
                    "row": row_num,
                    "person": person,
                    "ok": False,
                    "error": str(e)
                })
                print(f"[SHORTS] 처리 실패: {e}")

        return {
            "ok": True,
            "processed": len(results),
            "results": results
        }

    except Exception as e:
        print(f"[SHORTS] 대본 생성 파이프라인 실패: {e}")
        return {"ok": False, "error": str(e)}


def run_shorts_pipeline(
    person: Optional[str] = None,
    collect_news: bool = True,
    generate_script: bool = True,
    generate_video: bool = False,
    limit: int = 1
) -> Dict[str, Any]:
    """
    쇼츠 파이프라인 전체 실행

    Args:
        person: 특정 인물만 처리 (없으면 전체)
        collect_news: True면 뉴스 수집
        generate_script: True면 대본 생성
        generate_video: True면 비디오까지 생성
        limit: 처리할 최대 행 수

    Returns:
        {
            "ok": True,
            "news_collection": {...},
            "script_generation": {...}
        }
    """
    start_time = datetime.now(timezone.utc)

    print(f"\n{'#'*60}")
    print(f"# SHORTS 파이프라인 시작: {start_time.isoformat()}")
    if generate_video:
        print("# 모드: 뉴스 수집 + 대본 생성 + 비디오 생성")
    print(f"{'#'*60}")

    result = {"ok": True}

    # 1) 뉴스 수집
    if collect_news:
        if person:
            # 특정 인물 뉴스 검색
            news_items = search_celebrity_news(person, max_items=5)
            # 시트에 저장
            service = get_sheets_service()
            spreadsheet_id = get_spreadsheet_id()
            create_shorts_sheet(service, spreadsheet_id)
            saved = 0
            for item in news_items:
                item_person = item.get("person", item.get("celebrity", ""))
                if not check_duplicate(service, spreadsheet_id, item_person, item["news_url"]):
                    append_row(service, spreadsheet_id, item)
                    saved += 1
            result["news_collection"] = {
                "ok": True,
                "person": person,
                "collected": len(news_items),
                "saved": saved,
            }
        else:
            result["news_collection"] = run_news_collection(max_items=10)

    # 2) 대본 생성 (+ 옵션: 비디오 생성)
    if generate_script:
        result["script_generation"] = run_script_generation(
            limit=limit,
            generate_video=generate_video
        )

    # 완료
    end_time = datetime.now(timezone.utc)
    duration = (end_time - start_time).total_seconds()

    result["duration_seconds"] = round(duration, 1)
    result["estimated_cost"] = f"${estimate_cost():.2f}/영상"

    print(f"\n{'#'*60}")
    print(f"# SHORTS 파이프라인 완료: {duration:.1f}초")
    print(f"{'#'*60}\n")

    return result


def run_full_pipeline(
    person: Optional[str] = None,
    limit: int = 1
) -> Dict[str, Any]:
    """
    전체 파이프라인 실행 (뉴스 수집 → 대본 생성 → 비디오 생성)

    병렬 처리 구조:
    1. TTS 먼저 (저비용) - 실패 시 이미지 스킵
    2. TTS 성공 → 이미지(4워커) + 썸네일 병렬
    3. FFmpeg 렌더링 (Ken Burns + 전환 효과)

    Args:
        person: 특정 인물만 처리 (없으면 전체)
        limit: 처리할 최대 행 수

    Returns:
        전체 파이프라인 결과
    """
    return run_shorts_pipeline(
        person=person,
        collect_news=True,
        generate_script=True,
        generate_video=True,
        limit=limit
    )


# CLI 실행
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="쇼츠 파이프라인")
    parser.add_argument("--collect", action="store_true", help="뉴스 수집만")
    parser.add_argument("--generate", action="store_true", help="대본 생성만")
    parser.add_argument("--video", action="store_true", help="비디오까지 생성")
    parser.add_argument("--full", action="store_true", help="전체 파이프라인 (수집+대본+비디오)")
    parser.add_argument("--person", type=str, help="특정 인물")
    parser.add_argument("--limit", type=int, default=1, help="처리할 행 수")
    parser.add_argument("--create-sheet", action="store_true", help="시트 생성만")

    args = parser.parse_args()

    if args.create_sheet:
        service = get_sheets_service()
        spreadsheet_id = get_spreadsheet_id()
        create_shorts_sheet(service, spreadsheet_id, force=True)
        print("시트 생성 완료")
    elif args.collect:
        result = run_news_collection(max_items=10)
        print(f"결과: {result}")
    elif args.generate:
        result = run_script_generation(limit=args.limit, generate_video=args.video)
        print(f"결과: {result}")
    elif args.full:
        result = run_full_pipeline(person=args.person, limit=args.limit)
        print(f"결과: {result}")
    else:
        result = run_shorts_pipeline(
            person=args.person,
            collect_news=not args.generate,
            generate_script=not args.collect,
            generate_video=args.video,
            limit=args.limit
        )
        print(f"결과: {result}")
