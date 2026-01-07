"""
혈영 이세계편 파이프라인 - 실행 모듈

## 역할 분리

창작 작업 (Claude가 대화에서 직접 수행):
- 기획 (씬 구조, 클리프행어)
- 대본 작성 (12,000~15,000자)
- 이미지 프롬프트 생성
- TTS 연출 지시
- 자막 스타일 설계
- BGM/SFX 설정
- YouTube 메타데이터
- 품질 검수

실행 작업 (이 모듈에서 API 호출):
- TTS 생성 → Gemini/Google TTS
- 이미지 생성 → Gemini Imagen
- 영상 렌더링 → FFmpeg
- YouTube 업로드 → YouTube API
"""

import os
import sys
import json
import argparse
from typing import Dict, Any, Optional, List

# 프로젝트 루트 추가
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from .config import SERIES_INFO, PART_STRUCTURE
from .workers import (
    generate_tts,
    generate_image,
    render_video,
    upload_youtube,
    save_script,
    save_brief,
    save_metadata,
    ensure_directories,
    AUDIO_DIR,
    VIDEO_DIR,
    IMAGE_DIR,
)
from .sheets import sync_episode_from_files
from .reviewers import auto_review_script


def get_part_for_episode(episode: int) -> Dict[str, Any]:
    """에피소드 번호로 부 정보 조회"""
    for part_num, part_data in PART_STRUCTURE.items():
        start, end = part_data["episodes"]
        if start <= episode <= end:
            return {"part": part_num, **part_data}
    return {"part": 1, "title": "이방인"}


def execute_episode(
    episode: int,
    title: str,
    script: str,
    image_prompt: str,
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
        episode: 에피소드 번호
        title: 에피소드 제목
        script: 대본 (12,000~15,000자)
        image_prompt: 이미지 프롬프트 (영문)
        metadata: YouTube 메타데이터 (title, description, tags)
        brief: 기획서 (선택)
        bgm_mood: BGM 분위기
        generate_video: 영상 렌더링 여부
        upload: YouTube 업로드 여부
        privacy_status: 공개 설정

    Returns:
        {
            "ok": True,
            "episode": 1,
            "title": "...",
            "script_path": "...",
            "audio_path": "...",
            "image_path": "...",
            "video_path": "...",
            "youtube_url": "..."
        }
    """
    print(f"\n{'='*60}")
    print(f"[ISEKAI] 제{episode}화 '{title}' 실행 시작")
    print(f"{'='*60}\n")

    ensure_directories()

    result = {
        "ok": True,
        "episode": episode,
        "title": title,
        "part": get_part_for_episode(episode),
    }

    # ========================================
    # Step 1: 파일 저장 (대본, 기획서, 메타데이터)
    # ========================================
    print("[STEP 1] 파일 저장...")

    script_path = save_script(episode, title, script)
    result["script_path"] = script_path
    result["char_count"] = len(script)
    print(f"  - 대본 저장: {script_path} ({len(script):,}자)")

    if brief:
        brief_path = save_brief(episode, brief)
        result["brief_path"] = brief_path
        print(f"  - 기획서 저장: {brief_path}")

    if metadata:
        meta_path = save_metadata(episode, metadata)
        result["metadata_path"] = meta_path
        print(f"  - 메타데이터 저장: {meta_path}")

    # ========================================
    # Step 1.5: 대본 자동 리뷰
    # ========================================
    print("\n[STEP 1.5] 대본 자동 리뷰...")

    try:
        episode_str = f"EP{episode:03d}"
        review_result = auto_review_script(script, episode_str, save_results=True)
        result["review"] = {
            "form_score": review_result.get("form_score", 0),
            "form_verdict": review_result.get("form_verdict", "N/A"),
            "needs_manual_review": review_result.get("needs_manual_review", True),
        }
        print(f"  - FORM 점수: {result['review']['form_score']}점 ({result['review']['form_verdict']})")
        if result['review']['needs_manual_review']:
            print("  - ⚠️  VOICE/FEEL 체크리스트 검토 필요")
    except Exception as e:
        print(f"  - 리뷰 실패: {e}")
        result["review_error"] = str(e)

    # ========================================
    # Step 2: TTS 생성
    # ========================================
    print("\n[STEP 2] TTS 생성...")

    tts_result = generate_tts(episode, script)
    if tts_result.get("ok"):
        result["audio_path"] = tts_result.get("audio_path")
        result["srt_path"] = tts_result.get("srt_path")
        result["duration"] = tts_result.get("duration", 0)
        print(f"  - 오디오: {result['audio_path']}")
        print(f"  - 자막: {result.get('srt_path')}")
        print(f"  - 길이: {result['duration']:.1f}초 ({result['duration']/60:.1f}분)")
    else:
        print(f"  - TTS 실패: {tts_result.get('error')}")
        result["tts_error"] = tts_result.get("error")

    # ========================================
    # Step 3: 이미지 생성
    # ========================================
    print("\n[STEP 3] 이미지 생성...")

    if image_prompt:
        image_result = generate_image(episode, image_prompt)
        if image_result.get("ok"):
            result["image_path"] = image_result.get("image_path")
            print(f"  - 이미지: {result['image_path']}")
        else:
            print(f"  - 이미지 실패: {image_result.get('error')}")
            result["image_error"] = image_result.get("error")
    else:
        print("  - 이미지 프롬프트 없음, 스킵")

    # ========================================
    # Step 4: 영상 렌더링 (옵션)
    # ========================================
    if generate_video and result.get("audio_path") and result.get("image_path"):
        print("\n[STEP 4] 영상 렌더링...")

        video_result = render_video(
            episode=episode,
            audio_path=result["audio_path"],
            image_path=result["image_path"],
            srt_path=result.get("srt_path"),
            bgm_mood=bgm_mood,
        )
        if video_result.get("ok"):
            result["video_path"] = video_result.get("video_path")
            print(f"  - 영상: {result['video_path']}")
        else:
            print(f"  - 렌더링 실패: {video_result.get('error')}")
            result["video_error"] = video_result.get("error")
    elif generate_video:
        print("\n[STEP 4] 영상 렌더링 스킵 (오디오 또는 이미지 없음)")

    # ========================================
    # Step 5: YouTube 업로드 (옵션)
    # ========================================
    if upload and result.get("video_path"):
        print("\n[STEP 5] YouTube 업로드...")

        yt_title = metadata.get("youtube", {}).get("title", f"[{SERIES_INFO['title']}] 제{episode}화")
        yt_desc = metadata.get("youtube", {}).get("description", "")
        yt_tags = metadata.get("youtube", {}).get("tags", [])

        upload_result = upload_youtube(
            video_path=result["video_path"],
            title=yt_title,
            description=yt_desc,
            tags=yt_tags,
            thumbnail_path=result.get("image_path"),
            privacy_status=privacy_status,
        )
        if upload_result.get("ok"):
            result["youtube_url"] = upload_result.get("video_url")
            result["youtube_id"] = upload_result.get("video_id")
            print(f"  - URL: {result['youtube_url']}")
        else:
            print(f"  - 업로드 실패: {upload_result.get('error')}")
            result["upload_error"] = upload_result.get("error")
    elif upload:
        print("\n[STEP 5] YouTube 업로드 스킵 (영상 없음)")

    # ========================================
    # Step 6: Google Sheets 자동 동기화
    # ========================================
    print("\n[STEP 6] Google Sheets 동기화...")

    try:
        sync_result = sync_episode_from_files(episode)
        if sync_result.get("ok"):
            result["sheet_status"] = sync_result.get("status")
            result["sheet_row"] = sync_result.get("row_index")
            print(f"  - 시트 상태: {sync_result.get('status')}")
            print(f"  - 시트 행: {sync_result.get('row_index')}")
        else:
            print(f"  - 동기화 실패: {sync_result.get('error')}")
            result["sheet_error"] = sync_result.get("error")
    except Exception as e:
        print(f"  - 동기화 예외: {e}")
        result["sheet_error"] = str(e)

    # ========================================
    # 결과 정리
    # ========================================
    print(f"\n{'='*60}")
    print(f"[ISEKAI] 제{episode}화 '{title}' 실행 완료!")
    print(f"{'='*60}")
    print(f"  대본: {result['char_count']:,}자")
    if result.get("review"):
        print(f"  리뷰: FORM {result['review']['form_score']}점 ({result['review']['form_verdict']})")
    if result.get("duration"):
        print(f"  오디오: {result['duration']:.1f}초 ({result['duration']/60:.1f}분)")
    if result.get("video_path"):
        print(f"  영상: {result['video_path']}")
    if result.get("youtube_url"):
        print(f"  YouTube: {result['youtube_url']}")
    if result.get("sheet_status"):
        print(f"  시트 상태: {result['sheet_status']} (행 {result.get('sheet_row', '?')})")
    print(f"{'='*60}\n")

    return result


def execute_from_json(json_path: str, **kwargs) -> Dict[str, Any]:
    """
    JSON 파일에서 창작물 로드 후 실행

    Claude가 생성한 결과물을 JSON으로 저장한 경우 사용

    Args:
        json_path: JSON 파일 경로
        **kwargs: execute_episode에 전달할 추가 인자

    Returns:
        execute_episode 결과
    """
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    return execute_episode(
        episode=data.get("episode", 1),
        title=data.get("title", ""),
        script=data.get("script", ""),
        image_prompt=data.get("image_prompt", ""),
        metadata=data.get("metadata", {}),
        brief=data.get("brief"),
        bgm_mood=data.get("bgm_mood", "calm"),
        **kwargs,
    )


def main():
    parser = argparse.ArgumentParser(
        description=f"{SERIES_INFO['title']} 파이프라인 실행"
    )
    parser.add_argument(
        "--json", "-j",
        type=str,
        help="창작물 JSON 파일 경로"
    )
    parser.add_argument(
        "--video", "-v",
        action="store_true",
        help="영상 렌더링"
    )
    parser.add_argument(
        "--upload", "-u",
        action="store_true",
        help="YouTube 업로드"
    )
    parser.add_argument(
        "--privacy",
        choices=["private", "unlisted", "public"],
        default="private",
        help="YouTube 공개 설정"
    )

    args = parser.parse_args()

    if args.json:
        result = execute_from_json(
            args.json,
            generate_video=args.video,
            upload=args.upload,
            privacy_status=args.privacy,
        )
    else:
        print("사용법:")
        print("  1. Claude가 대화에서 창작물 생성")
        print("  2. 결과를 JSON 파일로 저장")
        print("  3. python -m scripts.isekai_pipeline.run --json episode.json")
        print("")
        print("또는 Python에서 직접 호출:")
        print("  from scripts.isekai_pipeline import execute_episode")
        print("  execute_episode(episode=1, title='...', script='...', ...)")
        return

    print("\n=== 결과 ===")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
