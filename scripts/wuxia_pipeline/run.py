"""
무협 파이프라인 메인 오케스트레이터

전체 흐름:
1. 에피소드 대본 생성 (Claude Opus 4.5)
2. 대본 → 음성 세그먼트 파싱
3. 다중 음성 TTS 생성
4. SRT 자막 생성
5. 영상 렌더링 (FFmpeg)
6. YouTube 업로드 (옵션)
"""

import os
import sys
import json
import argparse
from typing import Dict, Any, Optional

# 프로젝트 루트 추가
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from .config import SERIES_INFO, EPISODE_TEMPLATES, SCRIPT_CONFIG
from .script_generator import generate_episode_script, generate_youtube_metadata
from .multi_voice_tts import (
    parse_script_to_segments,
    generate_multi_voice_tts,
    generate_srt_from_timeline,
)


# 출력 디렉토리
OUTPUT_BASE = "outputs/wuxia"
AUDIO_DIR = os.path.join(OUTPUT_BASE, "audio")
SUBTITLE_DIR = os.path.join(OUTPUT_BASE, "subtitles")
VIDEO_DIR = os.path.join(OUTPUT_BASE, "videos")
SCRIPT_DIR = os.path.join(OUTPUT_BASE, "scripts")


def run_pipeline(
    episode: int,
    generate_video: bool = True,
    upload_youtube: bool = False,
    privacy_status: str = "private",
) -> Dict[str, Any]:
    """
    무협 파이프라인 전체 실행

    Args:
        episode: 에피소드 번호
        generate_video: 영상 생성 여부
        upload_youtube: YouTube 업로드 여부
        privacy_status: YouTube 공개 설정 (private/unlisted/public)

    Returns:
        {
            "ok": True,
            "episode": 1,
            "title": "운명의 시작",
            "script_path": "...",
            "audio_path": "...",
            "srt_path": "...",
            "video_path": "...",
            "youtube_url": "...",
            "cost": 0.25
        }
    """
    print(f"\n{'='*60}")
    print(f"[WUXIA] {SERIES_INFO['title']} 제{episode}화 파이프라인 시작")
    print(f"{'='*60}\n")

    # 디렉토리 생성
    for d in [AUDIO_DIR, SUBTITLE_DIR, VIDEO_DIR, SCRIPT_DIR]:
        os.makedirs(d, exist_ok=True)

    total_cost = 0.0
    result = {
        "ok": True,
        "episode": episode,
        "series": SERIES_INFO['title'],
    }

    # ========================================
    # Step 1: 대본 생성
    # ========================================
    print("[STEP 1] 대본 생성...")

    # 이전/다음 에피소드 정보
    prev_template = EPISODE_TEMPLATES.get(episode - 1)
    next_template = EPISODE_TEMPLATES.get(episode + 1)

    prev_summary = prev_template.get("summary") if prev_template else None
    next_preview = next_template.get("summary") if next_template else None

    script_result = generate_episode_script(
        episode=episode,
        prev_episode_summary=prev_summary,
        next_episode_preview=next_preview,
    )

    if not script_result.get("ok"):
        return {"ok": False, "error": f"대본 생성 실패: {script_result.get('error')}"}

    script = script_result["script"]
    title = script_result["title"]
    total_cost += script_result.get("cost", 0)

    # 대본 저장
    script_path = os.path.join(SCRIPT_DIR, f"ep{episode:03d}_{title}.txt")
    with open(script_path, "w", encoding="utf-8") as f:
        f.write(script)

    result["title"] = title
    result["script_path"] = script_path
    result["char_count"] = script_result["char_count"]

    print(f"[STEP 1] 대본 생성 완료: {script_result['char_count']:,}자")

    # ========================================
    # Step 2: 음성 세그먼트 파싱
    # ========================================
    print("\n[STEP 2] 대본 파싱...")

    segments = parse_script_to_segments(script)
    print(f"[STEP 2] 파싱 완료: {len(segments)}개 세그먼트")

    # 캐릭터별 통계
    char_stats = {}
    for seg in segments:
        char_stats[seg.tag] = char_stats.get(seg.tag, 0) + 1

    print(f"[STEP 2] 캐릭터 분포: {char_stats}")

    # ========================================
    # Step 3: 다중 음성 TTS 생성
    # ========================================
    print("\n[STEP 3] 다중 음성 TTS 생성...")

    episode_id = f"ep{episode:03d}"
    tts_result = generate_multi_voice_tts(
        segments=segments,
        output_dir=AUDIO_DIR,
        episode_id=episode_id,
    )

    if not tts_result.get("ok"):
        return {"ok": False, "error": f"TTS 생성 실패: {tts_result.get('error')}"}

    result["audio_path"] = tts_result["merged_audio"]
    result["total_duration"] = tts_result["total_duration"]

    print(f"[STEP 3] TTS 완료: {tts_result['total_duration']:.1f}초")

    # ========================================
    # Step 4: SRT 자막 생성
    # ========================================
    print("\n[STEP 4] SRT 자막 생성...")

    srt_path = os.path.join(SUBTITLE_DIR, f"{episode_id}.srt")
    generate_srt_from_timeline(tts_result["timeline"], srt_path)

    result["srt_path"] = srt_path
    print(f"[STEP 4] 자막 완료: {len(tts_result['timeline'])}개 항목")

    # ========================================
    # Step 5: YouTube 메타데이터 생성
    # ========================================
    print("\n[STEP 5] YouTube 메타데이터 생성...")

    metadata_result = generate_youtube_metadata(script, episode, title)
    if metadata_result.get("ok"):
        result["youtube_title"] = metadata_result.get("title")
        result["youtube_description"] = metadata_result.get("description")
        result["thumbnail_text"] = f"{metadata_result.get('thumbnail_line1', '')}\n{metadata_result.get('thumbnail_line2', '')}"
        print(f"[STEP 5] 메타데이터 완료: {result['youtube_title']}")
    else:
        # 기본값 사용
        result["youtube_title"] = f"[{SERIES_INFO['title']}] {title} | 제{episode}화"
        result["youtube_description"] = script_result.get("summary", "")
        print("[STEP 5] 메타데이터 생성 실패, 기본값 사용")

    # ========================================
    # Step 6: 영상 렌더링 (옵션)
    # ========================================
    if generate_video:
        print("\n[STEP 6] 영상 렌더링...")
        # TODO: 이미지 생성 + FFmpeg 렌더링
        # 현재는 TTS + SRT만 생성
        print("[STEP 6] 영상 렌더링은 아직 구현되지 않았습니다.")
        result["video_path"] = None

    # ========================================
    # Step 7: YouTube 업로드 (옵션)
    # ========================================
    if upload_youtube:
        print("\n[STEP 7] YouTube 업로드...")
        # TODO: YouTube 업로드 구현
        print("[STEP 7] YouTube 업로드는 아직 구현되지 않았습니다.")
        result["youtube_url"] = None

    # ========================================
    # 결과 정리
    # ========================================
    result["cost"] = round(total_cost, 4)

    print(f"\n{'='*60}")
    print(f"[WUXIA] 파이프라인 완료!")
    print(f"{'='*60}")
    print(f"  에피소드: 제{episode}화 - {title}")
    print(f"  대본: {result['char_count']:,}자")
    print(f"  오디오: {result['total_duration']:.1f}초 ({result['total_duration']/60:.1f}분)")
    print(f"  비용: ${total_cost:.4f}")
    print(f"{'='*60}\n")

    return result


def main():
    parser = argparse.ArgumentParser(description=f"{SERIES_INFO['title']} 무협 파이프라인")
    parser.add_argument("--episode", "-e", type=int, default=1, help="에피소드 번호")
    parser.add_argument("--video", "-v", action="store_true", help="영상 생성")
    parser.add_argument("--upload", "-u", action="store_true", help="YouTube 업로드")
    parser.add_argument("--privacy", choices=["private", "unlisted", "public"], default="private")

    args = parser.parse_args()

    result = run_pipeline(
        episode=args.episode,
        generate_video=args.video,
        upload_youtube=args.upload,
        privacy_status=args.privacy,
    )

    print("\n=== 결과 ===")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
