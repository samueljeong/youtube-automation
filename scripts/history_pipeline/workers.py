"""
한국사 파이프라인 - Workers (실행 API)

## 역할 분리

창작 작업 (Claude가 대화에서 직접 수행):
- 자료 조사 및 검증
- 에피소드 기획 (구조, 흐름)
- 대본 작성 (12,000~15,000자)
- 이미지 프롬프트 생성
- YouTube 메타데이터 (제목, 설명, 태그)
- 썸네일 문구 설계
- 품질 검수

실행 작업 (이 모듈에서 API 호출):
- TTS 생성 → Gemini/Google TTS
- 이미지 생성 → Gemini Imagen
- 영상 렌더링 → FFmpeg
- YouTube 업로드 → YouTube API
"""

import os
import json
import requests
from typing import Dict, Any, Optional, List
from datetime import datetime


# =====================================================
# 프로젝트 경로
# =====================================================

_workers_dir = os.path.dirname(os.path.abspath(__file__))
_project_root = os.path.dirname(os.path.dirname(_workers_dir))

# 출력 디렉토리
OUTPUT_BASE = os.path.join(_project_root, "outputs", "history")
AUDIO_DIR = os.path.join(OUTPUT_BASE, "audio")
SUBTITLE_DIR = os.path.join(OUTPUT_BASE, "subtitles")
VIDEO_DIR = os.path.join(OUTPUT_BASE, "videos")
SCRIPT_DIR = os.path.join(OUTPUT_BASE, "scripts")
IMAGE_DIR = os.path.join(OUTPUT_BASE, "images")
BRIEF_DIR = os.path.join(OUTPUT_BASE, "briefs")


# =====================================================
# TTS 설정
# =====================================================

TTS_CONFIG = {
    "voice": "chirp3:Charon",  # 차분하고 신뢰감 있는 남성 목소리
    "speed": 0.95,
    "language": "ko-KR",
}


# =====================================================
# 이미지 설정
# =====================================================

IMAGE_STYLE = {
    "style": "historical_illustration",
    "aspect_ratio": "16:9",
    "quality": "masterpiece, high detail, historically accurate",
    "base_prompt": (
        "Historical illustration, Korean history, "
        "traditional Korean art style mixed with modern illustration, "
        "dramatic lighting, detailed background, "
        "16:9 aspect ratio, masterpiece quality"
    ),
    "negative_prompt": (
        "text, letters, words, writing, watermark, signature, "
        "anime style, cartoon, chibi, modern elements, "
        "low quality, blurry, deformed, "
        "inaccurate historical details"
    ),
}


def ensure_directories():
    """출력 디렉토리 생성"""
    for d in [AUDIO_DIR, SUBTITLE_DIR, VIDEO_DIR, SCRIPT_DIR, IMAGE_DIR, BRIEF_DIR]:
        os.makedirs(d, exist_ok=True)


# =====================================================
# TTS Worker
# =====================================================

def generate_tts(
    episode_id: str,
    script: str,
    voice: str = None,
    speed: float = None,
) -> Dict[str, Any]:
    """
    TTS 생성 (Gemini/Google TTS)

    Args:
        episode_id: 에피소드 ID (예: "ep001_광개토왕")
        script: 대본 텍스트 (12,000~15,000자)
        voice: 음성 (기본: TTS_CONFIG)
        speed: 속도 (기본: TTS_CONFIG)

    Returns:
        {
            "ok": True,
            "audio_path": "outputs/history/audio/ep001_광개토왕.mp3",
            "srt_path": "outputs/history/subtitles/ep001_광개토왕.srt",
            "duration": 900.5  # 약 15분
        }
    """
    ensure_directories()

    voice = voice or TTS_CONFIG.get("voice", "chirp3:Charon")
    speed = speed or TTS_CONFIG.get("speed", 0.95)

    try:
        # wuxia_pipeline의 TTS 모듈 재사용
        from scripts.wuxia_pipeline.multi_voice_tts import (
            generate_multi_voice_tts_simple,
            generate_srt_from_timeline,
        )

        tts_result = generate_multi_voice_tts_simple(
            text=script,
            output_dir=AUDIO_DIR,
            episode_id=episode_id,
            voice=voice,
            speed=speed,
        )

        if tts_result.get("ok"):
            # SRT 생성
            srt_path = os.path.join(SUBTITLE_DIR, f"{episode_id}.srt")
            if tts_result.get("timeline"):
                generate_srt_from_timeline(tts_result["timeline"], srt_path)
                tts_result["srt_path"] = srt_path

            tts_result["audio_path"] = tts_result.get("merged_audio")

        return tts_result

    except ImportError:
        return {"ok": False, "error": "TTS 모듈 없음 (wuxia_pipeline 필요)"}
    except Exception as e:
        return {"ok": False, "error": str(e)}


# =====================================================
# Image Worker
# =====================================================

def generate_image(
    episode_id: str,
    prompt: str,
    scene_index: int = 0,
    negative_prompt: str = None,
    style: str = "realistic",
    ratio: str = "16:9",
) -> Dict[str, Any]:
    """
    이미지 생성 (Gemini Imagen)

    Args:
        episode_id: 에피소드 ID
        prompt: 이미지 프롬프트 (영문)
        scene_index: 씬 인덱스 (0 = 메인/썸네일)
        negative_prompt: 제외할 요소
        style: 스타일
        ratio: 비율

    Returns:
        {
            "ok": True,
            "image_path": "outputs/history/images/ep001_광개토왕_scene_01.png"
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

        # 히스토리 기본 스타일 추가
        full_prompt = f"{IMAGE_STYLE.get('base_prompt', '')}, {prompt}"

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
                    filename = f"{episode_id}_thumbnail.png"
                else:
                    filename = f"{episode_id}_scene_{scene_index:02d}.png"

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
    episode_id: str,
    prompts: List[Dict[str, str]],
) -> Dict[str, Any]:
    """
    여러 이미지 일괄 생성

    Args:
        episode_id: 에피소드 ID
        prompts: [{"prompt": "...", "scene_index": 1}, ...]

    Returns:
        {
            "ok": True,
            "images": [
                {"scene_index": 1, "path": "..."},
                {"scene_index": 2, "path": "..."},
            ],
            "failed": []
        }
    """
    results = {"ok": True, "images": [], "failed": []}

    for item in prompts:
        prompt = item.get("prompt", "")
        scene_index = item.get("scene_index", 0)

        result = generate_image(
            episode_id=episode_id,
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
        results["ok"] = len(results["images"]) > 0  # 부분 성공 허용

    return results


# =====================================================
# Video Worker
# =====================================================

def render_video(
    episode_id: str,
    audio_path: str,
    image_paths: List[str],
    srt_path: str = None,
    bgm_mood: str = "calm",
) -> Dict[str, Any]:
    """
    영상 렌더링 (FFmpeg)

    Args:
        episode_id: 에피소드 ID
        audio_path: TTS 오디오 파일 경로
        image_paths: 배경 이미지 경로 목록 (시간순)
        srt_path: 자막 파일 경로 (선택)
        bgm_mood: BGM 분위기

    Returns:
        {
            "ok": True,
            "video_path": "outputs/history/videos/ep001_광개토왕.mp4",
            "duration": 900.5
        }
    """
    ensure_directories()

    try:
        video_path = os.path.join(VIDEO_DIR, f"{episode_id}.mp4")

        # 단일 이미지인 경우 기존 렌더러 사용
        if len(image_paths) == 1:
            from scripts.wuxia_pipeline.renderer import render_episode_video

            result = render_episode_video(
                audio_path=audio_path,
                image_path=image_paths[0],
                srt_path=srt_path,
                output_path=video_path,
                bgm_mood=bgm_mood,
            )
            return result

        # 여러 이미지인 경우 씬별 렌더링 (추후 구현)
        # TODO: 씬별 이미지 전환 렌더링
        # 현재는 첫 번째 이미지만 사용
        from scripts.wuxia_pipeline.renderer import render_episode_video

        result = render_episode_video(
            audio_path=audio_path,
            image_path=image_paths[0],
            srt_path=srt_path,
            output_path=video_path,
            bgm_mood=bgm_mood,
        )
        return result

    except ImportError:
        return {"ok": False, "error": "렌더러 모듈 없음 (wuxia_pipeline 필요)"}
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
        # drama_server의 YouTube 업로드 함수 사용
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

def save_script(episode_id: str, title: str, script: str) -> str:
    """대본 파일 저장"""
    ensure_directories()
    script_path = os.path.join(SCRIPT_DIR, f"{episode_id}_{title}.txt")
    with open(script_path, "w", encoding="utf-8") as f:
        f.write(script)
    print(f"[HISTORY] 대본 저장: {script_path}")
    return script_path


def save_brief(episode_id: str, brief: Dict[str, Any]) -> str:
    """기획서 파일 저장"""
    ensure_directories()
    brief_path = os.path.join(BRIEF_DIR, f"{episode_id}_brief.json")
    with open(brief_path, "w", encoding="utf-8") as f:
        json.dump(brief, f, ensure_ascii=False, indent=2)
    print(f"[HISTORY] 기획서 저장: {brief_path}")
    return brief_path


def save_metadata(episode_id: str, metadata: Dict[str, Any]) -> str:
    """메타데이터 파일 저장"""
    ensure_directories()
    meta_path = os.path.join(BRIEF_DIR, f"{episode_id}_metadata.json")
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, ensure_ascii=False, indent=2)
    print(f"[HISTORY] 메타데이터 저장: {meta_path}")
    return meta_path


# =====================================================
# 에피소드 실행 (통합)
# =====================================================

def execute_episode(
    episode_id: str,
    title: str,
    script: str,
    image_prompts: List[Dict[str, str]],
    metadata: Dict[str, Any],
    brief: Dict[str, Any] = None,
    bgm_mood: str = "calm",
    generate_video: bool = False,
    upload: bool = False,
    privacy_status: str = "private",
) -> Dict[str, Any]:
    """
    에피소드 실행 (Workers 호출)

    Claude가 대화에서 생성한 창작물을 받아서 실제 파일 생성

    Args:
        episode_id: 에피소드 ID (예: "ep001")
        title: 에피소드 제목 (예: "광개토왕의 정복전쟁")
        script: 대본 (12,000~15,000자)
        image_prompts: 이미지 프롬프트 목록
        metadata: YouTube 메타데이터 (title, description, tags)
        brief: 기획서 (선택)
        bgm_mood: BGM 분위기
        generate_video: 영상 렌더링 여부
        upload: YouTube 업로드 여부
        privacy_status: 공개 설정

    Returns:
        {
            "ok": True,
            "episode_id": "ep001",
            "title": "광개토왕의 정복전쟁",
            "script_path": "...",
            "audio_path": "...",
            "image_paths": [...],
            "video_path": "...",
            "youtube_url": "..."
        }
    """
    print(f"\n{'='*60}")
    print(f"[HISTORY] '{title}' ({episode_id}) 실행 시작")
    print(f"{'='*60}")

    result = {
        "ok": False,
        "episode_id": episode_id,
        "title": title,
    }

    # 1. 대본 저장
    print(f"\n[HISTORY] 1. 대본 저장...")
    script_path = save_script(episode_id, title, script)
    result["script_path"] = script_path
    print(f"    ✓ {len(script):,}자 저장 완료")

    # 2. 기획서 저장 (선택)
    if brief:
        print(f"\n[HISTORY] 2. 기획서 저장...")
        brief_path = save_brief(episode_id, brief)
        result["brief_path"] = brief_path

    # 3. 메타데이터 저장
    print(f"\n[HISTORY] 3. 메타데이터 저장...")
    meta_path = save_metadata(episode_id, metadata)
    result["metadata_path"] = meta_path

    # 4. TTS 생성
    print(f"\n[HISTORY] 4. TTS 생성 중...")
    tts_result = generate_tts(episode_id, script)
    if not tts_result.get("ok"):
        result["error"] = f"TTS 실패: {tts_result.get('error')}"
        print(f"    ✗ TTS 실패: {result['error']}")
        return result

    result["audio_path"] = tts_result.get("audio_path")
    result["srt_path"] = tts_result.get("srt_path")
    result["duration"] = tts_result.get("duration")
    print(f"    ✓ TTS 완료: {result.get('duration', 0):.1f}초")

    # 5. 이미지 생성
    print(f"\n[HISTORY] 5. 이미지 생성 중...")
    if image_prompts:
        img_result = generate_images_batch(episode_id, image_prompts)
        result["image_paths"] = [img["path"] for img in img_result.get("images", [])]
        print(f"    ✓ {len(result['image_paths'])}개 이미지 생성")
        if img_result.get("failed"):
            print(f"    ⚠ {len(img_result['failed'])}개 실패")
    else:
        result["image_paths"] = []
        print(f"    - 이미지 프롬프트 없음 (스킵)")

    # 6. 영상 렌더링 (선택)
    if generate_video and result.get("image_paths"):
        print(f"\n[HISTORY] 6. 영상 렌더링 중...")
        video_result = render_video(
            episode_id=episode_id,
            audio_path=result["audio_path"],
            image_paths=result["image_paths"],
            srt_path=result.get("srt_path"),
            bgm_mood=bgm_mood,
        )
        if video_result.get("ok"):
            result["video_path"] = video_result.get("video_path")
            print(f"    ✓ 영상 렌더링 완료")
        else:
            print(f"    ✗ 렌더링 실패: {video_result.get('error')}")

    # 7. YouTube 업로드 (선택)
    if upload and result.get("video_path"):
        print(f"\n[HISTORY] 7. YouTube 업로드 중...")
        yt_result = upload_youtube(
            video_path=result["video_path"],
            title=metadata.get("title", title),
            description=metadata.get("description", ""),
            tags=metadata.get("tags", []),
            thumbnail_path=result["image_paths"][0] if result["image_paths"] else None,
            privacy_status=privacy_status,
            playlist_id=metadata.get("playlist_id"),
            scheduled_time=metadata.get("scheduled_time"),
        )
        if yt_result.get("ok"):
            result["youtube_url"] = yt_result.get("video_url")
            result["youtube_id"] = yt_result.get("video_id")
            print(f"    ✓ 업로드 완료: {result['youtube_url']}")
        else:
            print(f"    ✗ 업로드 실패: {yt_result.get('error')}")

    result["ok"] = True
    print(f"\n{'='*60}")
    print(f"[HISTORY] '{title}' 실행 완료!")
    print(f"{'='*60}\n")

    return result
