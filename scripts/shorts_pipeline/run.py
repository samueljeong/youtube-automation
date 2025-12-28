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
    FRAME_LAYOUT,
    TTS_CONFIG,
    TTS_VOICE_BY_ISSUE,
    IMAGE_MODEL,
    THUMBNAIL_CONFIG,
    SHORTS_KEN_BURNS,
    FFMPEG_ZOOMPAN_PRESETS,
    SCENE_TRANSITIONS,
    FFMPEG_TRANSITIONS,
    SHORTS_BGM_MOODS,
    SHORTS_BGM_CONFIG,
    SHORTS_SUBTITLE_STYLE,
    SHORTS_TITLE_STYLE,
    TITLE_MAX_LENGTH,
    TITLE_KEYWORDS,
    VIRAL_SUBTITLE_STYLE,
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
    collect_and_score_news,
    get_best_news_for_shorts,
)

# YouTube 트렌딩 검색 (선택적 사용)
try:
    from .youtube_search import (
        get_best_shorts_topic,
        youtube_to_news_format,
        search_shorts_by_category,
        get_video_comments,
        enrich_topic_with_news,  # 뉴스 기사 연동
    )
    YOUTUBE_SEARCH_AVAILABLE = True
except ImportError:
    YOUTUBE_SEARCH_AVAILABLE = False
    print("[SHORTS] YouTube 검색 모듈 비활성화 (googleapiclient 미설치)")
from .script_generator import (
    generate_complete_shorts_package,
    format_script_for_sheet,
)

# 메인 파이프라인 이미지 모듈 사용 (OpenRouter API)
from image import generate_image as main_generate_image, generate_thumbnail_image, GEMINI_FLASH, GEMINI_PRO


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
        model = "gemini-2.5-flash-preview-tts"  # TTS 전용 모델
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"

        # Gemini TTS 페이로드 (speakingRate 미지원 - Google Cloud TTS만 지원)
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


def generate_tts_with_timing(
    scenes: List[Dict[str, Any]],
    issue_type: str = "default",
    output_path: str = None
) -> Dict[str, Any]:
    """
    씬별 TTS 생성 + 정확한 자막 타이밍 반환

    각 씬의 narration을 문장 단위로 분리하여 개별 TTS 생성 후 합성.
    문장별 실제 재생 시간을 반환하여 자막 싱크에 활용.

    Args:
        scenes: 씬 정보 (narration 포함)
        issue_type: 이슈 타입 (음성 스타일)
        output_path: 출력 파일 경로

    Returns:
        {
            "ok": True,
            "audio_path": "/tmp/xxx.mp3",
            "duration": 35.5,
            "sentence_timings": [
                {"text": "첫 번째 문장.", "start": 0.0, "end": 2.5},
                {"text": "두 번째 문장!", "start": 2.5, "end": 5.2},
                ...
            ],
            "cost": 0.38
        }
    """
    import re
    import requests
    import base64
    import wave
    import io

    try:
        api_key = os.environ.get("GOOGLE_API_KEY")
        if not api_key:
            raise ValueError("GOOGLE_API_KEY 환경변수가 설정되지 않았습니다")

        # 음성 설정 (이슈 타입별)
        voice_config = TTS_VOICE_BY_ISSUE.get(issue_type, TTS_VOICE_BY_ISSUE["default"])
        voice_name = voice_config.get("voice", TTS_CONFIG["voice"])

        # 1) 전체 텍스트에서 문장 추출 (짧은 문장 병합)
        # ★ 한국어 뉴스 스타일: "박나래. 갑질 의혹. 그냥 의혹 아냐."
        #    → 마침표가 임팩트용이므로 너무 짧게 쪼개지면 병합
        MIN_SENTENCE_LENGTH = 15  # 최소 15자 이상으로 병합

        all_sentences = []
        for scene in scenes:
            narration = scene.get("narration", "").strip()
            if not narration:
                continue

            # 문장 분리 (. ! ? 기준)
            raw_sentences = re.split(r'(?<=[.!?。])\s*', narration)

            # 짧은 문장 병합
            merged = []
            buffer = ""
            for sent in raw_sentences:
                sent = sent.strip()
                if not sent or len(sent) <= 1:
                    continue

                if buffer:
                    buffer += " " + sent
                else:
                    buffer = sent

                # 버퍼가 충분히 길면 추가
                if len(buffer) >= MIN_SENTENCE_LENGTH:
                    merged.append(buffer)
                    buffer = ""

            # 남은 버퍼 처리
            if buffer:
                if merged and len(buffer) < MIN_SENTENCE_LENGTH:
                    # 너무 짧으면 마지막 문장에 붙이기
                    merged[-1] += " " + buffer
                else:
                    merged.append(buffer)

            all_sentences.extend(merged)

        if not all_sentences:
            raise ValueError("TTS 생성할 문장이 없습니다")

        print(f"[SHORTS] TTS 생성 중: {len(all_sentences)}개 문장, 음성={voice_name}")

        # 2) 문장별 TTS 생성
        sentence_audios = []
        sentence_timings = []
        total_cost = 0.0
        current_time = 0.0

        model = "gemini-2.5-flash-preview-tts"
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"

        for idx, sentence in enumerate(all_sentences):
            # Gemini TTS API 페이로드
            # 참고: Gemini TTS는 speakingRate를 지원하지 않음 (Google Cloud TTS만 지원)
            payload = {
                "contents": [{"parts": [{"text": sentence}]}],
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

            response = requests.post(url, json=payload, timeout=60)

            if response.status_code != 200:
                error_detail = response.text[:200] if response.text else "No error detail"
                print(f"[SHORTS] TTS 오류 (문장 {idx+1}): {response.status_code} - {error_detail}")
                continue

            result = response.json()
            candidates = result.get("candidates", [])
            if not candidates:
                continue

            # 오디오 데이터 추출
            audio_data = None
            for part in candidates[0].get("content", {}).get("parts", []):
                inline_data = part.get("inlineData", {})
                if inline_data.get("mimeType", "").startswith("audio/"):
                    audio_data = base64.b64decode(inline_data.get("data", ""))
                    break

            if not audio_data:
                continue

            # 재생 시간 계산 (24kHz, 16bit, mono)
            duration = len(audio_data) / (24000 * 2)

            # 타이밍 기록
            sentence_timings.append({
                "text": sentence,
                "start": current_time,
                "end": current_time + duration
            })
            current_time += duration

            # WAV 데이터 저장 (나중에 concat)
            sentence_audios.append(audio_data)

            # 비용 계산
            total_cost += len(sentence) * 0.001 / 1000

        if not sentence_audios:
            raise ValueError("TTS 생성 실패 - 모든 문장 실패")

        # 3) 오디오 합성 (모든 문장 연결)
        combined_audio = b''.join(sentence_audios)
        total_duration = len(combined_audio) / (24000 * 2)

        # WAV로 변환
        wav_buffer = io.BytesIO()
        with wave.open(wav_buffer, 'wb') as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(24000)
            wf.writeframes(combined_audio)

        wav_data = wav_buffer.getvalue()

        # MP3로 변환
        if output_path is None:
            output_path = tempfile.mktemp(suffix=".mp3")

        wav_temp = tempfile.mktemp(suffix=".wav")
        with open(wav_temp, "wb") as f:
            f.write(wav_data)

        cmd = ['ffmpeg', '-y', '-i', wav_temp, '-acodec', 'libmp3lame', '-b:a', '128k', output_path]
        subprocess.run(cmd, capture_output=True, timeout=30)

        try:
            os.unlink(wav_temp)
        except:
            pass

        print(f"[SHORTS] TTS 완료: {len(sentence_timings)}개 문장, {total_duration:.1f}초, ${total_cost:.4f}")

        return {
            "ok": True,
            "audio_path": output_path,
            "duration": total_duration,
            "sentence_timings": sentence_timings,
            "cost": round(total_cost, 4),
        }

    except Exception as e:
        print(f"[SHORTS] TTS 생성 실패: {e}")
        return {"ok": False, "error": str(e)}


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
    단일 씬 이미지 생성 (메인 파이프라인 image 모듈 사용)

    Args:
        prompt: 이미지 프롬프트
        scene_number: 씬 번호
        output_dir: 출력 디렉토리
        max_retries: 최대 재시도 횟수

    Returns:
        {"ok": True, "scene": 1, "path": "/tmp/xxx/scene_001.png"}
    """
    import shutil
    from urllib.request import urlopen
    from PIL import Image as PILImage
    from io import BytesIO

    # 프로젝트 루트 경로 (image 모듈이 저장하는 위치)
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

    for attempt in range(max_retries):
        try:
            # 메인 파이프라인의 image 모듈 사용 (OpenRouter API)
            # 1:1 비율로 생성 → 프레임 중앙에 배치 (크롭 없음)
            result = main_generate_image(
                prompt=prompt,
                size="1024x1024",  # 1:1 정사각형
                model=GEMINI_PRO,  # 고품질 PRO 모델
                add_aspect_instruction=False,  # 비율 지시문 생략 (1:1 유지)
            )

            if not result.get("ok"):
                raise ValueError(result.get("error", "이미지 생성 실패"))

            image_url = result.get("image_url", "")

            # 결과 이미지 경로 처리
            os.makedirs(output_dir, exist_ok=True)
            output_path = os.path.join(output_dir, f"scene_{scene_number:03d}.jpg")

            if image_url.startswith("data:"):
                # base64 데이터인 경우
                base64_data = image_url.split(",", 1)[1] if "," in image_url else image_url
                image_bytes = base64.b64decode(base64_data)
                with open(output_path, "wb") as f:
                    f.write(image_bytes)
            elif image_url.startswith("/static/"):
                # 로컬 파일 경로인 경우 - 프로젝트 루트 기준
                src_path = os.path.join(project_root, image_url.lstrip("/"))
                if os.path.exists(src_path):
                    shutil.copy(src_path, output_path)
                else:
                    raise ValueError(f"이미지 파일 없음: {src_path}")
            else:
                raise ValueError(f"알 수 없는 이미지 URL 형식: {image_url[:100]}")

            print(f"[SHORTS] 씬{scene_number} 이미지 생성 완료")

            return {
                "ok": True,
                "scene": scene_number,
                "path": output_path,
                "cost": result.get("cost", 0.039),
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
    쇼츠 썸네일 생성 (메인 파이프라인 image 모듈 사용)

    Args:
        thumbnail_config: GPT가 생성한 썸네일 설정
        person: 인물명
        issue_type: 이슈 타입
        output_path: 출력 경로

    Returns:
        {"ok": True, "path": "...", "cost": 0.05}
    """
    try:
        import shutil

        # 썸네일 프롬프트 생성
        style_config = THUMBNAIL_CONFIG["style_by_issue"].get(
            issue_type, THUMBNAIL_CONFIG["style_by_issue"]["default"]
        )

        prompt = thumbnail_config.get("image_prompt", f"""
1:1 square image composition,
dramatic black silhouette of {person},
silhouette centered in frame filling 80% of the space,
spotlight from above, {style_config['accent_color']} accent lighting,
{style_config['background_color']} background,
Korean entertainment news style,
NO facial features visible - only dark shadow outline,
4K quality, dramatic composition,
NO text on image
""")

        print(f"[SHORTS] 썸네일 생성 중: {person}")

        # 프로젝트 루트 경로
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

        # 메인 파이프라인의 image 모듈 사용 (OpenRouter API)
        # 1:1 비율로 생성 후 9:16 프레임 합성
        result = main_generate_image(
            prompt=prompt,
            size="1024x1024",  # 1:1 정사각형
            model=GEMINI_PRO,  # 고품질 PRO 모델
            add_aspect_instruction=False,  # 비율 지시문 생략
        )

        if not result.get("ok"):
            raise ValueError(result.get("error", "썸네일 생성 실패"))

        image_url = result.get("image_url", "")

        # 결과 이미지를 임시 파일로 저장 (1:1)
        output_dir = os.path.dirname(output_path)
        os.makedirs(output_dir, exist_ok=True)

        temp_1x1_path = output_path.replace(".jpg", "_1x1.jpg").replace(".png", "_1x1.jpg")

        if image_url.startswith("data:"):
            base64_data = image_url.split(",", 1)[1] if "," in image_url else image_url
            image_bytes = base64.b64decode(base64_data)
            with open(temp_1x1_path, "wb") as f:
                f.write(image_bytes)
        elif image_url.startswith("/static/"):
            src_path = os.path.join(project_root, image_url.lstrip("/"))
            if os.path.exists(src_path):
                shutil.copy(src_path, temp_1x1_path)
            else:
                raise ValueError(f"썸네일 파일 없음: {src_path}")
        else:
            raise ValueError(f"알 수 없는 이미지 URL 형식: {image_url[:100]}")

        # 1:1 이미지를 9:16 프레임으로 합성 (타이틀 포함)
        hook_text = thumbnail_config.get("hook_text", person)
        if len(hook_text) > 20:
            hook_text = hook_text[:20] + "..."
        compose_frame(temp_1x1_path, output_path, title_text=hook_text)

        # 임시 파일 삭제
        if os.path.exists(temp_1x1_path):
            os.remove(temp_1x1_path)

        print(f"[SHORTS] 썸네일 생성 완료 (9:16 프레임 합성)")

        return {
            "ok": True,
            "path": output_path,
            "cost": result.get("cost", 0.05),
        }

    except Exception as e:
        print(f"[SHORTS] 썸네일 생성 실패: {e}")
        return {"ok": False, "error": str(e)}


# ============================================================
# 프레임 합성 (1:1 이미지 → 9:16 프레임)
# ============================================================

def compose_frame(
    image_path: str,
    output_path: str,
    title_text: str = None
) -> str:
    """
    1:1 이미지를 9:16 프레임 중앙에 배치

    레이아웃:
    ┌─────────────────┐
    │   타이틀 영역    │  180px (상단)
    ├─────────────────┤
    │                 │
    │   1:1 이미지     │  720px (중앙)
    │                 │
    ├─────────────────┤
    │   자막 영역      │  380px (하단)
    └─────────────────┘

    Args:
        image_path: 1:1 이미지 경로
        output_path: 출력 경로
        title_text: 상단 타이틀 (선택)

    Returns:
        출력 파일 경로
    """
    from PIL import Image as PILImage, ImageDraw, ImageFont

    try:
        # 배경 생성 (720x1280, 거의 검정)
        bg_color = FRAME_LAYOUT["background_color"]
        # hex to RGB
        bg_rgb = tuple(int(bg_color.lstrip('#')[i:i+2], 16) for i in (0, 2, 4))
        background = PILImage.new('RGB', (VIDEO_WIDTH, VIDEO_HEIGHT), bg_rgb)

        # 1:1 이미지 로드 및 리사이즈
        img = PILImage.open(image_path)
        img_size = FRAME_LAYOUT["image_size"]  # 720
        img = img.resize((img_size, img_size), PILImage.Resampling.LANCZOS)

        # 이미지를 중앙에 배치 (y = title_height)
        title_height = FRAME_LAYOUT["title_height"]  # 180
        x = (VIDEO_WIDTH - img_size) // 2  # 0 (720-720)/2
        y = title_height

        background.paste(img, (x, y))

        # 타이틀 추가 (선택)
        if title_text:
            draw = ImageDraw.Draw(background)
            try:
                font = ImageFont.truetype(
                    "/usr/share/fonts/truetype/nanum/NanumGothicBold.ttf",
                    SHORTS_TITLE_STYLE["font_size"]
                )
            except:
                font = ImageFont.load_default()

            # 텍스트 중앙 정렬
            bbox = draw.textbbox((0, 0), title_text, font=font)
            text_width = bbox[2] - bbox[0]
            text_x = (VIDEO_WIDTH - text_width) // 2
            text_y = FRAME_LAYOUT["title_y"]

            # 외곽선 효과
            outline_color = SHORTS_TITLE_STYLE["outline_color"]
            for dx, dy in [(-2,-2), (-2,2), (2,-2), (2,2), (-2,0), (2,0), (0,-2), (0,2)]:
                draw.text((text_x+dx, text_y+dy), title_text, font=font, fill=outline_color)

            # 메인 텍스트
            draw.text((text_x, text_y), title_text, font=font, fill=SHORTS_TITLE_STYLE["font_color"])

        # 저장
        background.save(output_path, 'JPEG', quality=90)
        return output_path

    except Exception as e:
        print(f"[SHORTS] 프레임 합성 실패: {e}")
        # 실패 시 원본 이미지 복사
        import shutil
        shutil.copy(image_path, output_path)
        return output_path


# ============================================================
# 자막 생성 (ASS 형식) - 문장 단위 한 줄씩 + 상단 타이틀 고정
# ============================================================

def generate_ass_subtitles(
    scenes: List[Dict[str, Any]],
    total_duration: float,
    output_path: str,
    issue_type: str = "default",
    title_text: str = None,
    sentence_timings: List[Dict[str, Any]] = None
) -> str:
    """
    문장 단위로 한 줄씩 표시하는 ASS 자막 생성
    + 상단 타이틀은 전체 영상 동안 고정 표시
    + sentence_timings가 있으면 정확한 TTS 싱크 적용

    Args:
        scenes: 씬 정보 (narration 포함)
        total_duration: 총 영상 길이 (초)
        output_path: ASS 파일 저장 경로
        issue_type: 이슈 타입 (강조 색상 결정)
        title_text: 상단 고정 타이틀 (선택)

    Returns:
        ASS 파일 경로
    """
    import re

    # 스타일 설정
    sub_style = SHORTS_SUBTITLE_STYLE
    title_style = SHORTS_TITLE_STYLE
    font_name = sub_style.get("font_name", "NanumGothicBold")
    font_size = sub_style.get("font_size", 58)
    outline_width = sub_style.get("outline_width", 4)
    shadow_offset = sub_style.get("shadow_offset", 3)

    # ★ 새로운 스타일 설정 (중앙 배치, 배경 박스)
    alignment = sub_style.get("alignment", 5)  # 5=중앙, 2=하단, 8=상단
    margin_v = sub_style.get("margin_v", 0)    # 중앙이면 0
    margin_h = sub_style.get("margin_horizontal", 40)
    border_style = sub_style.get("border_style", 4)  # 4=배경박스+테두리, 1=테두리만
    is_bold = -1 if sub_style.get("bold", True) else 0

    # 타이틀 설정 (상단 고정)
    title_font_size = title_style.get("font_size", 64)
    title_margin_top = FRAME_LAYOUT.get("title_y", 160)

    # BGR 형식으로 변환 (ASS 형식: &HAABBGGRR)
    def hex_to_ass_color(hex_color, alpha=0):
        hex_color = hex_color.lstrip("#")
        r = hex_color[0:2]
        g = hex_color[2:4]
        b = hex_color[4:6]
        return f"&H{alpha:02X}{b}{g}{r}"

    primary_color = hex_to_ass_color(sub_style.get("font_color", "#FFFFFF"))
    outline_color = hex_to_ass_color(sub_style.get("outline_color", "#000000"))
    title_color = hex_to_ass_color(title_style.get("font_color", "#FFFF00"))
    title_outline = hex_to_ass_color(title_style.get("outline_color", "#000000"))

    # ★ 배경 박스 색상 (반투명)
    bg_opacity = sub_style.get("background_opacity", 0.6)
    bg_alpha = int((1 - bg_opacity) * 255)  # ASS는 투명도가 반대
    back_color = hex_to_ass_color(sub_style.get("background_color", "#000000"), bg_alpha)

    # ASS 헤더 - 두 가지 스타일 정의
    # ★ 1. Title: 상단 고정 (Alignment=8: 상단 중앙)
    # ★ 2. Subtitle: 중앙 배치 (Alignment=5: 화면 정중앙)
    #    - BorderStyle=4: 배경 박스 + 테두리 (가독성 최고)
    #    - Bold=-1: 굵은 글씨
    ass_content = f"""[Script Info]
Title: Shorts Subtitles
ScriptType: v4.00+
PlayResX: {VIDEO_WIDTH}
PlayResY: {VIDEO_HEIGHT}
WrapStyle: 0

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Title,{font_name},{title_font_size},{title_color},&H000000FF,{title_outline},&H80000000,1,0,0,0,100,100,0,0,1,5,2,8,40,40,{title_margin_top},1
Style: Subtitle,{font_name},{font_size},{primary_color},&H000000FF,{outline_color},{back_color},{is_bold},0,0,0,100,100,0,0,{border_style},{outline_width},{shadow_offset},{alignment},{margin_h},{margin_h},{margin_v},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

    # 시간 포맷 함수
    def format_time(seconds):
        h = int(seconds // 3600)
        m = int((seconds % 3600) // 60)
        s = int(seconds % 60)
        cs = int((seconds % 1) * 100)
        return f"{h}:{m:02d}:{s:02d}.{cs:02d}"

    # 1) 상단 타이틀 - 전체 영상 동안 고정 표시
    if title_text:
        # 타이틀이 너무 길면 자르기 (이미 run_video_generation에서 처리됨)
        if len(title_text) > TITLE_MAX_LENGTH:
            title_text = title_text[:TITLE_MAX_LENGTH]
        ass_content += f"Dialogue: 1,{format_time(0)},{format_time(total_duration)},Title,,0,0,0,,{{\\fad(300,300)}}{title_text}\n"

    # 2) sentence_timings이 있으면 정확한 TTS 싱크 사용
    if sentence_timings:
        # TTS에서 생성된 정확한 타이밍 사용
        for timing in sentence_timings:
            text = timing.get("text", "")
            start_time = timing.get("start", 0)
            end_time = timing.get("end", 0)

            if not text or end_time <= start_time:
                continue

            # 페이드 효과 (빠른 전환감)
            fade_effect = "{\\fad(50,50)}"

            # 자막 추가 (한 줄로만 표시)
            ass_content += f"Dialogue: 0,{format_time(start_time)},{format_time(end_time)},Subtitle,,0,0,0,,{fade_effect}{text}\n"

        # 파일 저장
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(ass_content)

        print(f"[SHORTS] ASS 자막 생성: {len(sentence_timings)}개 문장 (TTS 싱크), 타이틀={'있음' if title_text else '없음'}")
        return output_path

    # 3) sentence_timings 없으면 글자 수 비율로 fallback
    all_sentences = []
    for scene in scenes:
        narration = scene.get("narration", "")
        if not narration:
            continue
        # 문장 분리 (. ! ? 기준, 한국어 마침표도 포함)
        sentences = re.split(r'(?<=[.!?。])\s*', narration.strip())
        for sent in sentences:
            sent = sent.strip()
            if sent and len(sent) > 1:  # 빈 문장 제외
                all_sentences.append(sent)

    if not all_sentences:
        # 문장 분리 실패 시 씬 단위로 fallback
        for scene in scenes:
            narration = scene.get("narration", "").strip()
            if narration:
                all_sentences.append(narration)

    total_chars = sum(len(s) for s in all_sentences)
    if total_chars == 0:
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(ass_content)
        return output_path

    # 각 문장의 시작/끝 시간 계산 (글자 수 비율)
    current_time = 0.0
    for sentence in all_sentences:
        char_count = len(sentence)
        # 글자 수 비율로 duration 계산
        duration = (char_count / total_chars) * total_duration
        # 최소 0.5초, 최대 5초 제한
        duration = max(0.5, min(5.0, duration))

        start_time = current_time
        end_time = current_time + duration

        # 마지막 문장이 영상 끝을 넘지 않도록
        if end_time > total_duration:
            end_time = total_duration

        # 페이드 효과 (빠른 전환감)
        fade_effect = "{\\fad(50,50)}"

        # 자막 추가 (한 줄로만 표시)
        ass_content += f"Dialogue: 0,{format_time(start_time)},{format_time(end_time)},Subtitle,,0,0,0,,{fade_effect}{sentence}\n"

        current_time = end_time

    # 파일 저장
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(ass_content)

    print(f"[SHORTS] ASS 자막 생성: {len(all_sentences)}개 문장 (글자 비율), 타이틀={'있음' if title_text else '없음'}")
    return output_path


# ============================================================
# 바이럴 자막 생성 (단어별 하이라이팅 + 애니메이션)
# ============================================================

def generate_viral_subtitles(
    sentence_timings: List[Dict[str, Any]],
    total_duration: float,
    output_path: str,
    issue_type: str = "default",
    title_text: str = None,
    preset: str = "default"
) -> str:
    """
    바이럴 스타일 자막 생성 (단어별 하이라이팅)

    특징:
    - 현재 읽는 단어: 노란색 + 확대
    - 이미 읽은 단어: 흰색
    - 안 읽은 단어: 회색 (흐릿하게)
    - 팝인 애니메이션

    Args:
        sentence_timings: TTS에서 생성된 문장별 타이밍 [{text, start, end}, ...]
        total_duration: 총 영상 길이
        output_path: ASS 파일 저장 경로
        issue_type: 이슈 타입 (색상 결정)
        title_text: 상단 타이틀
        preset: 프리셋 (default, news, emotional, shocking)

    Returns:
        ASS 파일 경로
    """
    import re

    viral_style = VIRAL_SUBTITLE_STYLE
    font_config = viral_style.get("font", {})
    word_config = viral_style.get("word_by_word", {})
    current_style = viral_style.get("current_word", {})
    prev_style = viral_style.get("previous_word", {})
    next_style = viral_style.get("next_word", {})
    bg_config = viral_style.get("background", {})
    pos_config = viral_style.get("position", {})
    impact_config = viral_style.get("impact_keywords", {})

    # 이슈별 강조색
    issue_colors = viral_style.get("issue_colors", {})
    highlight_color = issue_colors.get(issue_type, issue_colors.get("default", "#FFFF00"))

    # 폰트 설정
    font_name = font_config.get("name", "NanumSquareRoundEB")
    font_size = font_config.get("size", 62)
    outline_width = font_config.get("outline_width", 5)
    shadow_offset = font_config.get("shadow_offset", 4)

    # 위치
    alignment = pos_config.get("alignment", 5)
    margin_v = pos_config.get("margin_v", 50)

    # BGR 변환 함수
    def hex_to_ass_color(hex_color, alpha=0):
        hex_color = hex_color.lstrip("#")
        r, g, b = hex_color[0:2], hex_color[2:4], hex_color[4:6]
        return f"&H{alpha:02X}{b}{g}{r}"

    # 색상 변환
    current_color = hex_to_ass_color(current_style.get("font_color", highlight_color))
    prev_color = hex_to_ass_color(prev_style.get("font_color", "#FFFFFF"))
    next_color = hex_to_ass_color(next_style.get("font_color", "#888888"))
    outline_color = hex_to_ass_color("#000000")
    title_color = hex_to_ass_color(SHORTS_TITLE_STYLE.get("font_color", "#FFFF00"))

    # 배경색 (반투명)
    bg_opacity = bg_config.get("opacity", 0.7)
    bg_alpha = int((1 - bg_opacity) * 255)
    back_color = hex_to_ass_color(bg_config.get("color", "#000000"), bg_alpha)

    # 임팩트 키워드 목록
    impact_words = set(impact_config.get("words", [])) if impact_config.get("enabled") else set()
    impact_color = hex_to_ass_color(impact_config.get("style", {}).get("font_color", "#FF0000"))

    # ASS 헤더 - 여러 스타일 정의
    ass_content = f"""[Script Info]
Title: Viral Shorts Subtitles
ScriptType: v4.00+
PlayResX: {VIDEO_WIDTH}
PlayResY: {VIDEO_HEIGHT}
WrapStyle: 0

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Title,{font_name},64,{title_color},&H000000FF,{outline_color},&H80000000,-1,0,0,0,100,100,0,0,1,5,2,8,40,40,{FRAME_LAYOUT.get('title_y', 160)},1
Style: Current,{font_name},{font_size},{current_color},&H000000FF,{outline_color},{back_color},-1,0,0,0,115,115,0,0,4,{outline_width},{shadow_offset},{alignment},40,40,{margin_v},1
Style: Previous,{font_name},{font_size},{prev_color},&H000000FF,{outline_color},{back_color},-1,0,0,0,100,100,0,0,4,{outline_width},{shadow_offset},{alignment},40,40,{margin_v},1
Style: Next,{font_name},{font_size},{next_color},&H000000FF,{outline_color},{back_color},-1,0,0,0,100,100,0,0,4,{outline_width-1},{shadow_offset},{alignment},40,40,{margin_v},1
Style: Impact,{font_name},{int(font_size * 1.2)},{impact_color},&H000000FF,{outline_color},{back_color},-1,0,0,0,130,130,0,0,4,{outline_width+1},{shadow_offset},{alignment},40,40,{margin_v},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

    # 시간 포맷 함수
    def format_time(seconds):
        h = int(seconds // 3600)
        m = int((seconds % 3600) // 60)
        s = int(seconds % 60)
        cs = int((seconds % 1) * 100)
        return f"{h}:{m:02d}:{s:02d}.{cs:02d}"

    # 타이틀 추가
    if title_text:
        if len(title_text) > TITLE_MAX_LENGTH:
            title_text = title_text[:TITLE_MAX_LENGTH]
        ass_content += f"Dialogue: 1,{format_time(0)},{format_time(total_duration)},Title,,0,0,0,,{{\\fad(300,300)}}{title_text}\n"

    if not sentence_timings:
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(ass_content)
        return output_path

    # 단어별 타이밍 생성
    words_per_group = word_config.get("words_per_group", 3)

    for timing in sentence_timings:
        text = timing.get("text", "").strip()
        start_time = timing.get("start", 0)
        end_time = timing.get("end", 0)

        if not text or end_time <= start_time:
            continue

        # 단어 분리 (공백 기준)
        words = text.split()
        if not words:
            continue

        # 문장 duration
        sentence_duration = end_time - start_time

        # 각 단어의 대략적인 타이밍 계산 (글자 수 비율)
        total_chars = sum(len(w) for w in words)
        if total_chars == 0:
            continue

        word_timings = []
        current_time = start_time

        for word in words:
            word_duration = (len(word) / total_chars) * sentence_duration
            word_duration = max(0.1, word_duration)  # 최소 0.1초

            word_timings.append({
                "word": word,
                "start": current_time,
                "end": min(current_time + word_duration, end_time),
            })
            current_time += word_duration

        # 단어 그룹별로 자막 생성
        for i in range(0, len(word_timings), words_per_group):
            group = word_timings[i:i + words_per_group]
            if not group:
                continue

            group_start = group[0]["start"]
            group_end = group[-1]["end"]

            # 그룹 내 각 단어별 스타일 적용
            styled_text_parts = []

            for j, wt in enumerate(group):
                word = wt["word"]
                word_start = wt["start"]
                word_end = wt["end"]

                # 임팩트 키워드 체크
                is_impact = any(kw in word for kw in impact_words)

                # ★ ASS 인라인 스타일로 단어별 색상 변경
                # 현재 그룹의 시작점 기준으로 단어가 "현재" 읽히는 중인지 판단
                # 여기서는 그룹 전체를 "현재"로 처리하고, 색상 변화로 강조

                if is_impact:
                    # 임팩트 키워드: 빨간색 + 크게
                    style_override = f"{{\\c{impact_color}\\fscx130\\fscy130}}"
                else:
                    # 일반 단어: 현재 색상
                    style_override = f"{{\\c{current_color}\\fscx115\\fscy115}}"

                styled_text_parts.append(f"{style_override}{word}{{\\r}}")

            # 조합된 텍스트
            final_text = " ".join(styled_text_parts)

            # 팝인 애니메이션
            pop_config = viral_style.get("pop_animation", {})
            if pop_config.get("enabled"):
                pop_duration = pop_config.get("duration_ms", 100)
                start_scale = int(pop_config.get("start_scale", 0.5) * 100)
                end_scale = 100

                # 팝인 효과: 작게 시작해서 커지면서 나타남
                fade_effect = f"{{\\fad({pop_duration},50)\\t(0,{pop_duration},\\fscx{end_scale}\\fscy{end_scale})}}"
            else:
                fade_effect = "{\\fad(50,50)}"

            # 자막 라인 추가
            ass_content += f"Dialogue: 0,{format_time(group_start)},{format_time(group_end)},Current,,0,0,0,,{fade_effect}{final_text}\n"

    # 파일 저장
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(ass_content)

    word_count = sum(len(t.get("text", "").split()) for t in sentence_timings)
    print(f"[SHORTS] 바이럴 자막 생성: {len(sentence_timings)}개 문장, {word_count}개 단어 (단어별 하이라이팅)")
    return output_path


# ============================================================
# 영상 렌더링 (FFmpeg - Ken Burns + 전환 효과)
# ============================================================

def render_video(
    images: List[Dict[str, Any]],
    audio_path: str,
    scenes: List[Dict[str, Any]],
    issue_type: str,
    output_path: str,
    title_text: str = None,
    sentence_timings: List[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    FFmpeg로 영상 렌더링 (1:1 이미지 → 9:16 프레임 합성 + Ken Burns)

    레이아웃:
    ┌─────────────────┐
    │   타이틀 영역    │  220px (YouTube UI 피함)
    ├─────────────────┤
    │   1:1 이미지     │  720px
    ├─────────────────┤
    │   자막 영역      │  340px
    └─────────────────┘

    Args:
        images: 이미지 경로 목록 (1:1 이미지)
        audio_path: TTS 오디오 경로
        scenes: 씬 정보 (자막용)
        issue_type: 이슈 타입 (효과 설정)
        output_path: 출력 영상 경로
        title_text: 상단 타이틀 (선택)
        sentence_timings: TTS 문장별 타이밍 (정확한 자막 싱크)

    Returns:
        {"ok": True, "path": "...", "duration": 50.5}
    """
    try:
        # 오디오 길이 확인
        audio_duration = get_audio_duration(audio_path)
        scene_count = len(images)
        scene_duration = audio_duration / scene_count

        print(f"[SHORTS] 영상 렌더링: {scene_count}개 씬, 총 {audio_duration:.1f}초")

        # 1) 씬별 클립 생성 (프레임 합성 + Ken Burns 효과)
        clips = []
        composed_frames = []

        for img_info in images:
            scene_num = img_info["scene"]
            img_path = img_info["path"]

            # 1-1) 1:1 이미지를 9:16 프레임으로 합성
            composed_path = img_path.replace(".jpg", "_composed.jpg").replace(".png", "_composed.jpg")
            compose_frame(img_path, composed_path, title_text)
            composed_frames.append(composed_path)

            # 1-2) Ken Burns 효과 패턴
            pattern = SHORTS_KEN_BURNS["scene_patterns"].get(scene_num, "zoom_in")
            zoompan = FFMPEG_ZOOMPAN_PRESETS.get(pattern, FFMPEG_ZOOMPAN_PRESETS["zoom_in"])

            # 강도 조절
            intensity = SHORTS_KEN_BURNS["intensity_by_issue"].get(
                issue_type, SHORTS_KEN_BURNS["intensity_by_issue"]["default"]
            )

            clip_path = img_path.replace(".jpg", "_clip.mp4").replace(".png", "_clip.mp4")

            # FFmpeg 명령어 (이미 9:16 크기이므로 scale 불필요)
            fps = 30
            total_frames = int(scene_duration * fps)

            # Ken Burns는 이미지 영역(중앙)에만 적용하도록 조정
            # 전체 프레임에 적용하면 타이틀/자막 영역도 움직임
            # 간단하게 전체 적용 (미세한 움직임)
            cmd = [
                "ffmpeg", "-y",
                "-loop", "1",
                "-i", composed_path,
                "-vf", f"zoompan=z={zoompan['z']}:x={zoompan['x']}:y={zoompan['y']}:d={total_frames}:s={VIDEO_WIDTH}x{VIDEO_HEIGHT}:fps={fps}",
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

        # 3) 오디오 합성 (임시 파일로)
        audio_merged_path = output_path.replace(".mp4", "_audio.mp4")
        subprocess.run([
            "ffmpeg", "-y",
            "-i", concat_path,
            "-i", audio_path,
            "-c:v", "copy",
            "-c:a", "aac",
            "-b:a", "128k",
            "-shortest",
            audio_merged_path
        ], capture_output=True, timeout=300)

        # 4) ASS 자막 생성 (문장 단위 + 상단 타이틀)
        ass_path = output_path.replace(".mp4", ".ass")

        # ★ 바이럴 자막 스타일 사용 여부 확인
        use_viral_style = VIRAL_SUBTITLE_STYLE.get("enabled", True) and sentence_timings

        if use_viral_style:
            # 바이럴 스타일: 단어별 하이라이팅 + 팝인 애니메이션
            generate_viral_subtitles(
                sentence_timings=sentence_timings,
                total_duration=audio_duration,
                output_path=ass_path,
                issue_type=issue_type,
                title_text=title_text,
            )
        else:
            # 기존 스타일: 문장 단위
            generate_ass_subtitles(
                scenes=scenes,
                total_duration=audio_duration,
                output_path=ass_path,
                issue_type=issue_type,
                title_text=title_text,
                sentence_timings=sentence_timings
            )

        # 5) 자막 burn-in (최종 출력)
        # FFmpeg ass 필터로 자막 합성
        # 경로에 특수문자가 있을 수 있으므로 이스케이프 처리
        ass_path_escaped = ass_path.replace("\\", "/").replace(":", "\\:")

        subtitle_result = subprocess.run([
            "ffmpeg", "-y",
            "-i", audio_merged_path,
            "-vf", f"ass='{ass_path_escaped}'",
            "-c:v", "libx264",
            "-preset", "fast",
            "-crf", "23",
            "-c:a", "copy",
            "-movflags", "+faststart",
            output_path
        ], capture_output=True, timeout=300)

        if subtitle_result.returncode != 0:
            print(f"[SHORTS] 자막 burn-in 실패, 자막 없이 진행: {subtitle_result.stderr.decode()[:200]}")
            # 자막 실패 시 오디오 합성본 사용
            import shutil
            shutil.move(audio_merged_path, output_path)
        else:
            print(f"[SHORTS] 자막 burn-in 완료")

        # 임시 파일 정리
        for clip in clips:
            if os.path.exists(clip):
                os.remove(clip)
        for composed in composed_frames:
            if os.path.exists(composed):
                os.remove(composed)
        if os.path.exists(concat_list_path):
            os.remove(concat_list_path)
        if os.path.exists(concat_path):
            os.remove(concat_path)
        if os.path.exists(audio_merged_path):
            os.remove(audio_merged_path)
        if os.path.exists(ass_path):
            os.remove(ass_path)

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
# BGM 믹싱
# ============================================================

def mix_bgm_with_video(
    video_path: str,
    issue_type: str,
    output_path: str = None
) -> Dict[str, Any]:
    """
    비디오에 BGM 믹싱

    Args:
        video_path: 원본 비디오 경로
        issue_type: 이슈 타입 (BGM 분위기 결정)
        output_path: 출력 경로 (없으면 원본 대체)

    Returns:
        {"ok": True, "path": "..."}
    """
    import glob
    import random

    try:
        # 1) 이슈 타입에 맞는 BGM 분위기 선택
        bgm_mood = SHORTS_BGM_MOODS.get(issue_type, SHORTS_BGM_MOODS.get("default", "dramatic"))
        print(f"[BGM] 분위기 선택: {issue_type} → {bgm_mood}")

        # 2) BGM 파일 찾기
        script_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        bgm_dir = os.path.join(script_dir, "static", "audio", "bgm")

        # 해당 분위기의 BGM 파일 목록
        bgm_files = glob.glob(os.path.join(bgm_dir, f"{bgm_mood}_*.mp3"))

        if not bgm_files:
            # fallback: dramatic
            bgm_files = glob.glob(os.path.join(bgm_dir, "dramatic_*.mp3"))

        if not bgm_files:
            print(f"[BGM] BGM 파일 없음: {bgm_mood}")
            return {"ok": False, "error": "BGM 파일 없음"}

        # 랜덤 선택
        bgm_path = random.choice(bgm_files)
        print(f"[BGM] 선택된 파일: {os.path.basename(bgm_path)}")

        # 3) 비디오 길이 확인
        probe_cmd = ["ffprobe", "-v", "error", "-show_entries", "format=duration",
                     "-of", "default=noprint_wrappers=1:nokey=1", video_path]
        result = subprocess.run(probe_cmd, capture_output=True, text=True, timeout=30)
        video_duration = float(result.stdout.strip())

        # 4) BGM 볼륨 설정
        bgm_volume = SHORTS_BGM_CONFIG.get("volume", 0.15)
        fade_in = SHORTS_BGM_CONFIG.get("fade_in", 1.0)
        fade_out = SHORTS_BGM_CONFIG.get("fade_out", 2.0)

        fade_out_start = max(0, video_duration - fade_out)

        # 5) 출력 경로 설정
        if output_path is None:
            output_path = video_path.replace(".mp4", "_bgm.mp4")

        # 6) FFmpeg 믹싱
        ffmpeg_cmd = [
            "ffmpeg", "-y",
            "-i", video_path,
            "-stream_loop", "-1", "-i", bgm_path,
            "-filter_complex",
            f"[1:a]volume={bgm_volume},afade=t=in:st=0:d={fade_in},afade=t=out:st={fade_out_start}:d={fade_out}[bgm];"
            f"[0:a][bgm]amix=inputs=2:duration=first:dropout_transition=2:normalize=0[aout]",
            "-map", "0:v",
            "-map", "[aout]",
            "-c:v", "copy",
            "-c:a", "aac", "-b:a", "128k",
            "-shortest",
            "-movflags", "+faststart",
            output_path
        ]

        print(f"[BGM] 믹싱 시작...")
        result = subprocess.run(ffmpeg_cmd, stdout=subprocess.DEVNULL,
                               stderr=subprocess.PIPE, timeout=300)

        if result.returncode == 0:
            print(f"[BGM] 믹싱 완료")
            return {"ok": True, "path": output_path}
        else:
            stderr = result.stderr.decode('utf-8', errors='ignore')[:200]
            print(f"[BGM] 믹싱 실패: {stderr}")
            return {"ok": False, "error": stderr}

    except Exception as e:
        print(f"[BGM] 믹싱 오류: {e}")
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
        # 1단계: TTS 생성 (문장별 타이밍 포함 - 자막 싱크용)
        # ============================================================
        print("\n[SHORTS] === 1단계: TTS 생성 (문장별 싱크) ===")

        scenes = script_result.get("scenes", [])

        tts_result = generate_tts_with_timing(
            scenes=scenes,
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
        sentence_timings = tts_result.get("sentence_timings", [])

        # ============================================================
        # 2단계: 이미지 생성 (썸네일은 YouTube 자동 생성 사용)
        # ============================================================
        print("\n[SHORTS] === 2단계: 이미지 생성 ===")

        image_dir = os.path.join(work_dir, "images")

        # 이미지 생성 (4 워커 병렬)
        image_result = generate_images_parallel(
            scenes=scenes,
            output_dir=image_dir,
            max_workers=4
        )

        # 이미지 생성 결과 확인
        if not image_result.get("ok") and len(image_result.get("images", [])) == 0:
            return {
                "ok": False,
                "error": "모든 이미지 생성 실패",
                "stage": "image",
            }

        total_cost += image_result.get("cost", 0)

        # ============================================================
        # 3단계: FFmpeg 영상 렌더링
        # ============================================================
        print("\n[SHORTS] === 3단계: 영상 렌더링 ===")

        video_path = os.path.join(work_dir, "output.mp4")

        # 상단 타이틀 생성 (10~15자 임팩트 키워드)
        # 형식: "인물명 키워드!" (예: "박나래 현재 상황!", "주사이모 검찰조사!")
        keyword = TITLE_KEYWORDS.get(issue_type, TITLE_KEYWORDS.get("default", "속보!"))

        # 인물명이 너무 길면 자르기 (타이틀 전체 15자 이내)
        max_person_len = TITLE_MAX_LENGTH - len(keyword) - 1  # 공백 포함
        if len(person) > max_person_len:
            person_short = person[:max_person_len]
        else:
            person_short = person

        title_text = f"{person_short} {keyword}"

        # 최종 길이 체크
        if len(title_text) > TITLE_MAX_LENGTH:
            title_text = title_text[:TITLE_MAX_LENGTH]

        render_result = render_video(
            images=image_result["images"],
            audio_path=audio_path,
            scenes=scenes,
            issue_type=issue_type,
            output_path=video_path,
            title_text=title_text,
            sentence_timings=sentence_timings  # TTS 싱크용 정확한 타이밍
        )

        if not render_result.get("ok"):
            return {
                "ok": False,
                "error": f"렌더링 실패: {render_result.get('error')}",
                "stage": "render",
            }

        # ============================================================
        # 4단계: BGM 믹싱
        # ============================================================
        print("\n[SHORTS] === 4단계: BGM 믹싱 ===")

        final_video_path = os.path.join(work_dir, "final.mp4")
        bgm_result = mix_bgm_with_video(
            video_path=render_result["path"],
            issue_type=issue_type,
            output_path=final_video_path
        )

        if bgm_result.get("ok"):
            # BGM 믹싱 성공 → 최종 파일 사용
            video_output_path = bgm_result["path"]
            # 원본 삭제
            if os.path.exists(render_result["path"]):
                os.remove(render_result["path"])
        else:
            # BGM 믹싱 실패 → 원본 사용 (BGM 없이)
            print(f"[SHORTS] BGM 믹싱 실패, 원본 사용: {bgm_result.get('error')}")
            video_output_path = render_result["path"]

        # ============================================================
        # 완료
        # ============================================================
        gc.collect()

        result = {
            "ok": True,
            "video_path": video_output_path,
            "thumbnail_path": None,  # YouTube 자동 썸네일 사용
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
    save_to_sheet: bool = True,
    run_id: str = None
) -> Dict[str, Any]:
    """
    연예 뉴스 수집 및 시트 저장

    Args:
        max_items: 수집할 최대 뉴스 수
        save_to_sheet: True면 시트에 저장
        run_id: 수집 슬롯 ID (YYYY-MM-DD_HH 형식, 8시/17시 구분)

    Returns:
        {
            "ok": True,
            "collected": 10,
            "saved": 8,
            "duplicates": 2
        }
    """
    print(f"\n{'='*50}")
    print(f"[SHORTS] 연예 뉴스 수집 시작 (run_id: {run_id})")
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

        # run_id 기본값: YYYY-MM-DD_HH (현재 한국 시간)
        if not run_id:
            from datetime import timezone, timedelta
            kst = timezone(timedelta(hours=9))
            now_kst = datetime.now(kst)
            run_id = now_kst.strftime("%Y-%m-%d_%H")

        saved = 0
        duplicates = 0

        for item in news_items:
            # 중복 체크 (person 필드 사용)
            person = item.get("person", item.get("celebrity", ""))
            if check_duplicate(service, spreadsheet_id, person, item["news_url"]):
                duplicates += 1
                print(f"[SHORTS] 중복 스킵: {person} - {item['news_title'][:30]}...")
                continue

            # run_id 추가
            item["run_id"] = run_id

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


def run_youtube_collection(
    max_items: int = 10,
    categories: List[str] = None,
    hours_ago: int = 48,
    min_engagement: float = 30,
    save_to_sheet: bool = True
) -> Dict[str, Any]:
    """
    YouTube 트렌딩 쇼츠 수집 및 시트 저장

    Args:
        max_items: 수집할 최대 주제 수
        categories: 카테고리 목록 (None이면 ["연예인"])
        hours_ago: 검색 시간 범위
        min_engagement: 최소 참여도 점수
        save_to_sheet: True면 시트에 저장

    Returns:
        {
            "ok": True,
            "collected": 5,
            "saved": 3,
            "topics": [...]
        }
    """
    if not YOUTUBE_SEARCH_AVAILABLE:
        return {
            "ok": False,
            "error": "YouTube 검색 모듈 비활성화 (YOUTUBE_API_KEY 또는 googleapiclient 필요)"
        }

    print(f"\n{'='*50}")
    print(f"[SHORTS] YouTube 트렌딩 수집 시작")
    print(f"{'='*50}\n")

    if categories is None:
        categories = ["연예인"]

    all_topics = []

    try:
        for category in categories:
            print(f"[SHORTS] === {category} 카테고리 검색 ===")

            result = search_shorts_by_category(
                category=category,
                hours_ago=hours_ago,
                max_results=max_items * 3  # 필터링 여유분
            )

            videos = result.get("videos", [])
            topics = result.get("topics", [])

            print(f"[SHORTS] 검색 결과: {len(videos)}개 영상, {len(topics)}개 주제 추출")

            if not topics and videos:
                # 주제 추출 실패 시 상위 영상 직접 사용
                print(f"[SHORTS] 주제 추출 실패, 상위 영상 직접 사용")
                for video in videos[:max_items]:
                    topics.append({
                        "topic": video.get("title", "")[:30],
                        "video_count": 1,
                        "total_views": video.get("view_count", 0),
                        "avg_engagement": video.get("engagement_score", 50),
                        "sample_videos": [video],
                    })

            for topic in topics[:max_items]:
                # 참여도 필터 (0이면 필터 비활성화)
                engagement = topic.get("avg_engagement", 0)
                if min_engagement > 0 and engagement < min_engagement:
                    print(f"  ⏭️ {topic['topic']}: 참여도 {engagement:.1f} < {min_engagement} (스킵)")
                    continue

                # ★ 뉴스 기사 검색 (원본 자료 확보)
                enriched_topic = enrich_topic_with_news(topic)
                if enriched_topic is None:
                    # 뉴스 기사가 없으면 저장하지 않음
                    print(f"  ⏭️ {topic['topic']}: 뉴스 기사 없음 (스킵)")
                    continue

                # 뉴스 형식으로 변환 (뉴스 기사 정보 포함)
                news_format = youtube_to_news_format(enriched_topic)
                news_format["category"] = category
                news_format["source"] = "youtube+news"  # 하이브리드 소스

                # 상위 영상 댓글 수집 (script_hints용)
                if enriched_topic.get("sample_videos"):
                    top_video = enriched_topic["sample_videos"][0]
                    comments = get_video_comments(top_video["video_id"], max_results=20)
                    news_format["script_hints"]["hot_phrases"] = [c.get("text", "")[:50] for c in comments[:5]]

                all_topics.append(news_format)

                print(f"  ✅ {topic['topic']}: {topic['video_count']}개 영상 + {len(enriched_topic.get('news_articles', []))}개 뉴스")

        if not all_topics:
            return {"ok": False, "error": "수집된 트렌딩 주제 없음"}

        if not save_to_sheet:
            return {
                "ok": True,
                "collected": len(all_topics),
                "saved": 0,
                "topics": all_topics
            }

        # 시트에 저장
        service = get_sheets_service()
        spreadsheet_id = get_spreadsheet_id()
        create_shorts_sheet(service, spreadsheet_id)

        saved = 0
        duplicates = 0

        for item in all_topics:
            person = item.get("person", "")
            news_url = item.get("news_url", "")

            # 중복 체크
            if check_duplicate(service, spreadsheet_id, person, news_url):
                duplicates += 1
                print(f"[SHORTS] 중복 스킵: {person}")
                continue

            # 시트에 추가
            append_row(service, spreadsheet_id, item)
            saved += 1
            print(f"[SHORTS] 저장: {person} ({item.get('issue_type', '근황')}) - YouTube 트렌딩")

        print(f"\n[SHORTS] YouTube 수집 완료: {len(all_topics)}개 중 {saved}개 저장, {duplicates}개 중복")

        return {
            "ok": True,
            "collected": len(all_topics),
            "saved": saved,
            "duplicates": duplicates,
            "topics": all_topics
        }

    except Exception as e:
        print(f"[SHORTS] YouTube 수집 실패: {e}")
        import traceback
        traceback.print_exc()
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


# ============================================================
# YouTube 업로드
# ============================================================

def upload_to_youtube(
    video_path: str,
    title: str,
    description: str = "",
    tags: List[str] = None,
    privacy_status: str = "private",
    channel_id: str = None,
    playlist_id: str = None,
) -> Dict[str, Any]:
    """
    YouTube에 쇼츠 영상 업로드

    내부적으로 /api/youtube/upload 엔드포인트를 호출합니다.

    Args:
        video_path: 업로드할 영상 경로
        title: 영상 제목
        description: 영상 설명
        tags: 태그 목록
        privacy_status: 공개 설정 (private/public/unlisted)
        channel_id: YouTube 채널 ID (선택)
        playlist_id: 플레이리스트 ID (선택)

    Returns:
        {
            "ok": True,
            "video_id": "...",
            "video_url": "https://www.youtube.com/watch?v=...",
        }
    """
    import requests as http_requests

    try:
        # API 서버 URL (로컬 또는 배포 환경)
        api_base = os.environ.get("API_BASE_URL", "http://localhost:5003")

        print(f"[SHORTS] YouTube 업로드 시작: {title[:30]}...")

        payload = {
            "videoPath": video_path,
            "title": title,
            "description": description,
            "tags": tags or [],
            "categoryId": "22",  # People & Blogs
            "privacyStatus": privacy_status,
        }

        if channel_id:
            payload["channelId"] = channel_id
        if playlist_id:
            payload["playlistId"] = playlist_id

        response = http_requests.post(
            f"{api_base}/api/youtube/upload",
            json=payload,
            timeout=600  # 10분 타임아웃
        )

        result = response.json()

        if result.get("ok"):
            video_url = result.get("videoUrl", "")
            print(f"[SHORTS] YouTube 업로드 성공: {video_url}")
            return {
                "ok": True,
                "video_id": result.get("videoId"),
                "video_url": video_url,
            }
        else:
            error = result.get("error", "Unknown error")
            print(f"[SHORTS] YouTube 업로드 실패: {error}")
            return {"ok": False, "error": error}

    except Exception as e:
        print(f"[SHORTS] YouTube 업로드 오류: {e}")
        return {"ok": False, "error": str(e)}


# ============================================================
# 바이럴 점수 기반 파이프라인 (자동 최적 뉴스 선택)
# ============================================================

def run_viral_pipeline(
    min_score: float = 40,
    categories: List[str] = None,
    generate_video: bool = True,
    upload_youtube: bool = False,
    privacy_status: str = "private",
    channel_id: str = None,
    save_to_sheet: bool = True,
    source: str = "rss"  # "rss" 또는 "youtube"
) -> Dict[str, Any]:
    """
    바이럴 점수 기반 자동 쇼츠 파이프라인

    흐름:
    1. RSS 또는 YouTube에서 트렌딩 주제 수집
    2. 네이버/다음 댓글 크롤링 → 바이럴 점수 계산
    3. 가장 점수 높은 뉴스 선정
    4. 실제 댓글을 반영한 대본 생성
    5. 비디오 생성
    6. (옵션) YouTube 업로드

    Args:
        min_score: 최소 바이럴 점수 (기본 40)
        categories: 수집할 카테고리 (None이면 전체)
        generate_video: 비디오 생성 여부
        upload_youtube: YouTube 업로드 여부 (기본 False)
        privacy_status: YouTube 공개 설정 (private/public/unlisted)
        channel_id: YouTube 채널 ID (선택)
        save_to_sheet: 시트에 저장 여부
        source: 소스 선택 - "rss" (뉴스 RSS) 또는 "youtube" (YouTube 트렌딩)

    Returns:
        {
            "ok": True,
            "news": {...},
            "viral_score": {...},
            "script_hints": {...},
            "video_path": "...",
            "youtube_url": "...",
            "cost": 0.84
        }
    """
    start_time = datetime.now(timezone.utc)

    print(f"\n{'#'*60}")
    print(f"# 바이럴 기반 SHORTS 파이프라인 시작")
    print(f"# 소스: {source.upper()}, 최소 점수: {min_score}")
    print(f"{'#'*60}\n")

    result = {"ok": False}
    total_cost = 0

    try:
        # ============================================================
        # 1단계: 바이럴 점수 기반 뉴스 선정
        # ============================================================
        print(f"[SHORTS] === 1단계: {'YouTube 트렌딩' if source == 'youtube' else 'RSS 뉴스'} 검색 ===\n")

        best_news = None

        if source == "youtube":
            # YouTube 트렌딩 쇼츠에서 주제 찾기
            if not YOUTUBE_SEARCH_AVAILABLE:
                return {
                    "ok": False,
                    "error": "YouTube 검색 모듈 비활성화 (YOUTUBE_API_KEY 또는 googleapiclient 필요)"
                }

            topic = get_best_shorts_topic(
                categories=categories,
                min_engagement=min_score
            )

            if topic:
                # YouTube 주제를 뉴스 형식으로 변환
                best_news = youtube_to_news_format(topic)
                print(f"[SHORTS] YouTube 트렌딩 주제 발견: {topic.get('topic')}")
        else:
            # 기존 RSS 기반 뉴스 수집
            best_news = get_best_news_for_shorts(
                categories=categories,
                min_score=min_score
            )

        if not best_news:
            print("[SHORTS] 바이럴 점수 기준을 충족하는 뉴스가 없습니다")
            return {
                "ok": False,
                "error": f"바이럴 점수 {min_score}+ 기준 충족 뉴스 없음"
            }

        person = best_news.get("person", "")
        issue_type = best_news.get("issue_type", "근황")
        viral_score = best_news.get("viral_score", {})
        script_hints = best_news.get("script_hints", {})

        print(f"\n[SHORTS] 🔥 선정된 뉴스:")
        print(f"  - 인물: {person}")
        print(f"  - 이슈: {issue_type}")
        print(f"  - 바이럴 점수: {viral_score.get('total_score', 0)} ({viral_score.get('grade', 'N/A')}등급)")
        print(f"  - 논쟁 주제: {script_hints.get('debate_topic', 'N/A')}")
        print(f"  - 핫 표현: {script_hints.get('hot_phrases', [])[:3]}")

        # ============================================================
        # 2단계: 실제 댓글 반영 대본 생성
        # ============================================================
        print("\n[SHORTS] === 2단계: 댓글 기반 대본 생성 ===\n")

        # script_hints가 포함된 news_data로 대본 생성
        script_result = generate_complete_shorts_package(best_news)

        if not script_result.get("ok"):
            return {
                "ok": False,
                "error": f"대본 생성 실패: {script_result.get('error')}",
                "news": best_news,
            }

        total_cost += script_result.get("cost", 0)

        print(f"[SHORTS] 대본 생성 완료: {script_result.get('total_chars', 0)}자")

        # ============================================================
        # 3단계: 시트에 저장 (옵션)
        # ============================================================
        if save_to_sheet:
            try:
                service = get_sheets_service()
                spreadsheet_id = get_spreadsheet_id()
                create_shorts_sheet(service, spreadsheet_id)

                # 바이럴 점수 정보 추가
                best_news["viral_grade"] = viral_score.get("grade", "")
                best_news["viral_total"] = viral_score.get("total_score", 0)

                if not check_duplicate(service, spreadsheet_id, person, best_news.get("news_url", "")):
                    append_row(service, spreadsheet_id, best_news)
                    print(f"[SHORTS] 시트에 저장: {person}")
            except Exception as e:
                print(f"[SHORTS] 시트 저장 실패 (무시): {e}")

        # ============================================================
        # 4단계: 비디오 생성 (옵션)
        # ============================================================
        video_result = None
        if generate_video:
            print("\n[SHORTS] === 3단계: 비디오 생성 ===\n")

            video_result = run_video_generation(
                script_result=script_result,
                person=person,
                issue_type=issue_type
            )

            if video_result.get("ok"):
                total_cost += video_result.get("cost", 0)
                print(f"[SHORTS] 비디오 생성 완료: {video_result.get('duration', 0):.1f}초")
            else:
                print(f"[SHORTS] 비디오 생성 실패: {video_result.get('error')}")

        # ============================================================
        # 5단계: YouTube 업로드 (옵션)
        # ============================================================
        youtube_result = None
        if upload_youtube and video_result and video_result.get("ok"):
            print("\n[SHORTS] === 4단계: YouTube 업로드 ===\n")

            # 제목: 쇼츠 제목 사용
            yt_title = script_result.get("title", f"{person} 이슈")
            if len(yt_title) > 100:
                yt_title = yt_title[:97] + "..."

            # 설명: 해시태그 포함
            hashtags = script_result.get("hashtags", [f"#{person}", "#쇼츠"])
            yt_description = f"{yt_title}\n\n{' '.join(hashtags)}"

            youtube_result = upload_to_youtube(
                video_path=video_result.get("video_path"),
                title=yt_title,
                description=yt_description,
                tags=[person, issue_type, "쇼츠", "연예뉴스"],
                privacy_status=privacy_status,
                channel_id=channel_id,
            )

            if youtube_result.get("ok"):
                print(f"[SHORTS] YouTube 업로드 성공: {youtube_result.get('video_url')}")
            else:
                print(f"[SHORTS] YouTube 업로드 실패: {youtube_result.get('error')}")

        # ============================================================
        # 완료
        # ============================================================
        end_time = datetime.now(timezone.utc)
        duration = (end_time - start_time).total_seconds()

        result = {
            "ok": True,
            "person": person,
            "issue_type": issue_type,
            "news": {
                "title": best_news.get("news_title", ""),
                "url": best_news.get("news_url", ""),
            },
            "viral_score": viral_score,
            "script_hints": script_hints,
            "script": {
                "title": script_result.get("title", ""),
                "total_chars": script_result.get("total_chars", 0),
                "scenes": len(script_result.get("scenes", [])),
            },
            "cost": round(total_cost, 3),
            "duration_seconds": round(duration, 1),
        }

        if video_result and video_result.get("ok"):
            result["video"] = {
                "path": video_result.get("video_path"),
                "duration": video_result.get("duration"),
            }

        if youtube_result and youtube_result.get("ok"):
            result["youtube"] = {
                "video_id": youtube_result.get("video_id"),
                "video_url": youtube_result.get("video_url"),
            }

        print(f"\n{'#'*60}")
        print(f"# 바이럴 파이프라인 완료!")
        print(f"# 인물: {person} ({viral_score.get('grade', 'N/A')}등급)")
        print(f"# 총 비용: ${total_cost:.3f}, 소요시간: {duration:.1f}초")
        print(f"{'#'*60}\n")

        return result

    except Exception as e:
        print(f"[SHORTS] 바이럴 파이프라인 오류: {e}")
        return {
            "ok": False,
            "error": str(e),
            "cost": total_cost,
        }


# CLI 실행
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="쇼츠 파이프라인")
    parser.add_argument("--collect", action="store_true", help="뉴스 수집만 (RSS)")
    parser.add_argument("--youtube-collect", action="store_true", help="YouTube 트렌딩 수집 → 시트 저장")
    parser.add_argument("--generate", action="store_true", help="대본 생성만")
    parser.add_argument("--video", action="store_true", help="비디오까지 생성")
    parser.add_argument("--full", action="store_true", help="전체 파이프라인 (수집+대본+비디오)")
    parser.add_argument("--viral", action="store_true", help="바이럴 점수 기반 자동 파이프라인")
    parser.add_argument("--youtube", action="store_true", help="YouTube 트렌딩 기반 (--viral과 함께 사용)")
    parser.add_argument("--min-score", type=float, default=30, help="최소 참여도/바이럴 점수")
    parser.add_argument("--upload", action="store_true", help="YouTube 업로드 (viral 모드)")
    parser.add_argument("--privacy", type=str, default="private", help="YouTube 공개 설정 (private/public/unlisted)")
    parser.add_argument("--channel-id", type=str, help="YouTube 채널 ID")
    parser.add_argument("--person", type=str, help="특정 인물")
    parser.add_argument("--limit", type=int, default=10, help="수집/처리할 최대 수")
    parser.add_argument("--create-sheet", action="store_true", help="시트 생성만")

    args = parser.parse_args()

    if args.create_sheet:
        service = get_sheets_service()
        spreadsheet_id = get_spreadsheet_id()
        create_shorts_sheet(service, spreadsheet_id, force=True)
        print("시트 생성 완료")
    elif args.viral:
        # 바이럴 점수 기반 자동 파이프라인
        source = "youtube" if args.youtube else "rss"
        result = run_viral_pipeline(
            min_score=args.min_score,
            generate_video=args.video,
            upload_youtube=args.upload,
            privacy_status=args.privacy,
            channel_id=args.channel_id,
            source=source,
        )
        print(f"\n결과: {json.dumps(result, ensure_ascii=False, indent=2)}")
    elif args.youtube_collect:
        # YouTube 트렌딩 수집 → 시트 저장
        result = run_youtube_collection(
            max_items=args.limit,
            min_engagement=args.min_score,
        )
        print(f"\n결과: {json.dumps(result, ensure_ascii=False, indent=2)}")
    elif args.collect:
        result = run_news_collection(max_items=args.limit)
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
