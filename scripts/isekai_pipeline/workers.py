"""
혈영 이세계편 - Workers (실행 API)

창작 작업은 Claude가 대화에서 직접 수행.
이 모듈은 실행만 담당:
- TTS 생성 (Gemini TTS)
- 이미지 생성 (Gemini Imagen)
- 영상 렌더링 (FFmpeg)
- YouTube 업로드

사용법:
    from scripts.isekai_pipeline.workers import execute_episode

    result = execute_episode(
        episode=1,
        title="이방인",
        script="대본...",
        image_prompt="무림 검객이 이세계 숲에서...",
        metadata={"title": "...", "description": "...", "tags": [...]},
        generate_video=True,
        upload=False,
    )
"""

import os
import json
import requests
from typing import Dict, Any, Optional, List
from datetime import datetime

from .config import (
    OUTPUT_BASE,
    TTS_CONFIG,
    IMAGE_STYLE,
)

# 자체 모듈 사용
from .tts import generate_tts as _generate_tts, generate_srt
from .renderer import render_video as _render_video


# 출력 디렉토리
AUDIO_DIR = os.path.join(OUTPUT_BASE, "audio")
SUBTITLE_DIR = os.path.join(OUTPUT_BASE, "subtitles")
VIDEO_DIR = os.path.join(OUTPUT_BASE, "videos")
SCRIPT_DIR = os.path.join(OUTPUT_BASE, "scripts")
IMAGE_DIR = os.path.join(OUTPUT_BASE, "images")
BRIEF_DIR = os.path.join(OUTPUT_BASE, "briefs")


def ensure_directories():
    """출력 디렉토리 생성"""
    for d in [AUDIO_DIR, SUBTITLE_DIR, VIDEO_DIR, SCRIPT_DIR, IMAGE_DIR, BRIEF_DIR]:
        os.makedirs(d, exist_ok=True)


# =====================================================
# TTS Worker
# =====================================================

def generate_tts(
    episode: int,
    script: str,
    voice: str = None,
    speed: float = None,
) -> Dict[str, Any]:
    """
    TTS 생성 (Gemini TTS)

    Args:
        episode: 에피소드 번호
        script: 대본 텍스트
        voice: 음성 (기본: config의 TTS_CONFIG)
        speed: 속도 (기본: config의 TTS_CONFIG)

    Returns:
        {
            "ok": True,
            "audio_path": "outputs/isekai/audio/ep001.mp3",
            "srt_path": "outputs/isekai/subtitles/ep001.srt",
            "duration": 900.5
        }
    """
    ensure_directories()

    voice = voice or TTS_CONFIG.get("voice", "Charon")
    episode_id = f"ep{episode:03d}"

    try:
        # 자체 TTS 모듈 사용
        audio_path = os.path.join(AUDIO_DIR, f"{episode_id}.mp3")
        srt_path = os.path.join(SUBTITLE_DIR, f"{episode_id}.srt")

        result = _generate_tts(
            text=script,
            output_path=audio_path,
            voice=voice,
            srt_output_path=srt_path,
        )

        if result.get("ok"):
            result["audio_path"] = audio_path
            result["srt_path"] = srt_path

        return result

    except Exception as e:
        return {"ok": False, "error": str(e)}


# =====================================================
# Image Worker
# =====================================================

def generate_image(
    episode: int,
    prompt: str,
    scene_index: int = 0,
    negative_prompt: str = None,
    style: str = "realistic",
    ratio: str = "16:9",
) -> Dict[str, Any]:
    """
    이미지 생성 (Gemini Imagen)

    Args:
        episode: 에피소드 번호
        prompt: 이미지 프롬프트 (영문)
        scene_index: 씬 인덱스 (0 = 메인/썸네일)
        negative_prompt: 제외할 요소
        style: 스타일 (realistic, artistic, etc.)
        ratio: 비율 (16:9, 1:1, 9:16)

    Returns:
        {
            "ok": True,
            "image_path": "outputs/isekai/images/ep001_scene_01.png"
        }
    """
    ensure_directories()

    try:
        api_url = os.getenv(
            "IMAGE_API_URL",
            "http://localhost:5059/api/ai-tools/image-generate"
        )

        # 기본 negative prompt 추가
        full_negative = IMAGE_STYLE.get("negative_prompt", "")
        if negative_prompt:
            full_negative = f"{full_negative}, {negative_prompt}"

        # 이세계 스타일 추가
        base_prompt = IMAGE_STYLE.get("base_prompt", "")
        full_prompt = f"{base_prompt}, {prompt}" if base_prompt else prompt

        response = requests.post(
            api_url,
            json={
                "prompt": full_prompt,
                "negative_prompt": full_negative,
                "style": style,
                "ratio": ratio,
            },
            timeout=120,
        )

        if response.status_code == 200:
            data = response.json()
            if data.get("success"):
                image_url = data.get("image_url")

                # 파일명 생성
                if scene_index == 0:
                    filename = f"ep{episode:03d}_thumbnail.png"
                else:
                    filename = f"ep{episode:03d}_scene_{scene_index:02d}.png"

                image_path = os.path.join(IMAGE_DIR, filename)

                # 이미지 다운로드
                img_response = requests.get(image_url, timeout=60)
                if img_response.status_code == 200:
                    with open(image_path, "wb") as f:
                        f.write(img_response.content)
                    return {"ok": True, "image_path": image_path}

        return {"ok": False, "error": "이미지 생성 실패"}

    except Exception as e:
        return {"ok": False, "error": str(e)}


def generate_images_batch(
    episode: int,
    prompts: List[Dict[str, str]],
) -> Dict[str, Any]:
    """
    여러 이미지 일괄 생성

    Args:
        episode: 에피소드 번호
        prompts: [{"prompt": "...", "scene_index": 1}, ...]

    Returns:
        {
            "ok": True,
            "images": [{"scene_index": 1, "path": "..."}, ...],
            "failed": []
        }
    """
    results = {"ok": True, "images": [], "failed": []}

    for item in prompts:
        prompt = item.get("prompt", "")
        scene_index = item.get("scene_index", 0)

        result = generate_image(
            episode=episode,
            prompt=prompt,
            scene_index=scene_index,
        )

        if result.get("ok"):
            results["images"].append({
                "scene_index": scene_index,
                "path": result["image_path"],
            })
        else:
            results["failed"].append({
                "scene_index": scene_index,
                "error": result.get("error"),
            })

    if results["failed"]:
        results["ok"] = len(results["images"]) > 0

    return results


# =====================================================
# Video Worker
# =====================================================

def render_video(
    episode: int,
    audio_path: str,
    image_path: str,
    srt_path: str = None,
    bgm_mood: str = "calm",
) -> Dict[str, Any]:
    """
    영상 렌더링 (FFmpeg)

    Args:
        episode: 에피소드 번호
        audio_path: TTS 오디오 파일 경로
        image_path: 배경 이미지 경로
        srt_path: 자막 파일 경로 (선택)
        bgm_mood: BGM 분위기

    Returns:
        {
            "ok": True,
            "video_path": "outputs/isekai/videos/ep001.mp4",
            "duration": 900.5
        }
    """
    ensure_directories()

    try:
        episode_id = f"ep{episode:03d}"
        video_path = os.path.join(VIDEO_DIR, f"{episode_id}.mp4")

        # 자체 렌더러 사용
        result = _render_video(
            audio_path=audio_path,
            image_path=image_path,
            output_path=video_path,
            srt_path=srt_path,
        )

        return result

    except Exception as e:
        return {"ok": False, "error": str(e)}


# =====================================================
# YouTube Worker
# =====================================================

def upload_youtube(
    video_path: str,
    title: str,
    description: str,
    tags: List[str] = None,
    thumbnail_path: str = None,
    privacy_status: str = "private",
    playlist_id: str = None,
    scheduled_time: str = None,
) -> Dict[str, Any]:
    """
    YouTube 업로드

    Args:
        video_path: 영상 파일 경로
        title: 영상 제목
        description: 영상 설명
        tags: 태그 목록
        thumbnail_path: 썸네일 이미지 경로
        privacy_status: 공개 설정 (private/unlisted/public)
        playlist_id: 플레이리스트 ID
        scheduled_time: 예약 공개 시간 (ISO 8601)

    Returns:
        {
            "ok": True,
            "video_id": "abc123",
            "video_url": "https://youtube.com/watch?v=abc123"
        }
    """
    try:
        from drama_server import upload_to_youtube

        result = upload_to_youtube(
            video_path=video_path,
            title=title,
            description=description,
            tags=tags or [],
            thumbnail_path=thumbnail_path,
            privacy_status=privacy_status,
            playlist_id=playlist_id,
            scheduled_time=scheduled_time,
        )

        return result

    except ImportError:
        return {"ok": False, "error": "YouTube 모듈 없음 (drama_server 필요)"}
    except Exception as e:
        return {"ok": False, "error": str(e)}


# =====================================================
# 파일 저장 유틸리티
# =====================================================

def save_script(episode: int, title: str, script: str) -> str:
    """대본 파일 저장"""
    ensure_directories()
    script_path = os.path.join(SCRIPT_DIR, f"ep{episode:03d}_{title}.txt")
    with open(script_path, "w", encoding="utf-8") as f:
        f.write(script)
    print(f"[ISEKAI] 대본 저장: {script_path}")
    return script_path


def save_brief(episode: int, brief: Dict[str, Any]) -> str:
    """기획서 파일 저장"""
    ensure_directories()
    brief_path = os.path.join(BRIEF_DIR, f"ep{episode:03d}_brief.json")
    with open(brief_path, "w", encoding="utf-8") as f:
        json.dump(brief, f, ensure_ascii=False, indent=2)
    print(f"[ISEKAI] 기획서 저장: {brief_path}")
    return brief_path


def save_metadata(episode: int, metadata: Dict[str, Any]) -> str:
    """메타데이터 파일 저장"""
    ensure_directories()
    meta_path = os.path.join(BRIEF_DIR, f"ep{episode:03d}_metadata.json")
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, ensure_ascii=False, indent=2)
    print(f"[ISEKAI] 메타데이터 저장: {meta_path}")
    return meta_path


# =====================================================
# 에피소드 실행 (통합)
# =====================================================

def execute_episode(
    episode: int,
    title: str,
    script: str,
    image_prompts: List[Dict[str, str]] = None,
    metadata: Dict[str, Any] = None,
    brief: Dict[str, Any] = None,
    bgm_mood: str = "epic",
    generate_video: bool = False,
    upload: bool = False,
    privacy_status: str = "private",
) -> Dict[str, Any]:
    """
    에피소드 실행 (Workers 호출)

    Claude가 대화에서 생성한 창작물을 받아서 실제 파일 생성

    Args:
        episode: 에피소드 번호 (1~60)
        title: 에피소드 제목
        script: 대본 (12,000~15,000자)
        image_prompts: 이미지 프롬프트 목록 [{"prompt": "...", "scene_index": 1}, ...]
        metadata: YouTube 메타데이터 (title, description, tags)
        brief: 기획서 (선택)
        bgm_mood: BGM 분위기 (epic, tense, calm, etc.)
        generate_video: 영상 렌더링 여부
        upload: YouTube 업로드 여부
        privacy_status: 공개 설정

    Returns:
        {
            "ok": True,
            "episode": 1,
            "title": "이방인",
            "script_path": "...",
            "audio_path": "...",
            "image_paths": [...],
            "video_path": "...",
            "youtube_url": "..."
        }
    """
    print(f"\n{'='*60}")
    print(f"[ISEKAI] EP{episode:03d} '{title}' 실행 시작")
    print(f"{'='*60}")

    result = {
        "ok": False,
        "episode": episode,
        "title": title,
    }

    # 1. 대본 저장
    print(f"\n[ISEKAI] 1. 대본 저장...")
    script_path = save_script(episode, title, script)
    result["script_path"] = script_path
    print(f"    ✓ {len(script):,}자 저장 완료")

    # 2. 기획서 저장 (선택)
    if brief:
        print(f"\n[ISEKAI] 2. 기획서 저장...")
        brief_path = save_brief(episode, brief)
        result["brief_path"] = brief_path

    # 3. 메타데이터 저장
    if metadata:
        print(f"\n[ISEKAI] 3. 메타데이터 저장...")
        meta_path = save_metadata(episode, metadata)
        result["metadata_path"] = meta_path

    # 4. TTS 생성
    print(f"\n[ISEKAI] 4. TTS 생성 중...")
    tts_result = generate_tts(episode, script)
    if not tts_result.get("ok"):
        result["error"] = f"TTS 실패: {tts_result.get('error')}"
        print(f"    ✗ TTS 실패: {result['error']}")
        return result

    result["audio_path"] = tts_result.get("audio_path")
    result["srt_path"] = tts_result.get("srt_path")
    result["duration"] = tts_result.get("duration")
    print(f"    ✓ TTS 완료: {result.get('duration', 0):.1f}초")

    # 5. 이미지 생성
    print(f"\n[ISEKAI] 5. 이미지 생성 중...")
    if image_prompts:
        img_result = generate_images_batch(episode, image_prompts)
        result["image_paths"] = [img["path"] for img in img_result.get("images", [])]
        print(f"    ✓ {len(result['image_paths'])}개 이미지 생성")
        if img_result.get("failed"):
            print(f"    ⚠ {len(img_result['failed'])}개 실패")
    else:
        result["image_paths"] = []
        print(f"    - 이미지 프롬프트 없음 (스킵)")

    # 6. 영상 렌더링 (선택)
    if generate_video and result.get("image_paths"):
        print(f"\n[ISEKAI] 6. 영상 렌더링 중...")
        video_result = render_video(
            episode=episode,
            audio_path=result["audio_path"],
            image_path=result["image_paths"][0],  # 첫 번째 이미지 사용
            srt_path=result.get("srt_path"),
            bgm_mood=bgm_mood,
        )
        if video_result.get("ok"):
            result["video_path"] = video_result.get("video_path")
            print(f"    ✓ 영상 생성 완료: {result['video_path']}")
        else:
            print(f"    ✗ 영상 생성 실패: {video_result.get('error')}")

    # 7. YouTube 업로드 (선택)
    if upload and result.get("video_path") and metadata:
        print(f"\n[ISEKAI] 7. YouTube 업로드 중...")
        yt_result = upload_youtube(
            video_path=result["video_path"],
            title=metadata.get("title", f"혈영 이세계편 EP{episode:03d}"),
            description=metadata.get("description", ""),
            tags=metadata.get("tags", []),
            thumbnail_path=result["image_paths"][0] if result.get("image_paths") else None,
            privacy_status=privacy_status,
        )
        if yt_result.get("ok"):
            result["youtube_url"] = yt_result.get("video_url")
            print(f"    ✓ 업로드 완료: {result['youtube_url']}")
        else:
            print(f"    ✗ 업로드 실패: {yt_result.get('error')}")

    result["ok"] = True
    print(f"\n{'='*60}")
    print(f"[ISEKAI] EP{episode:03d} '{title}' 실행 완료")
    print(f"{'='*60}")

    return result
