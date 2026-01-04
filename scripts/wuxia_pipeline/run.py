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
from .sheets import (
    get_ready_episodes,
    update_episode_with_script,
    update_episode_status,
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


def run_auto_script_pipeline(max_scripts: int = 1) -> Dict[str, Any]:
    """
    자동 대본 생성 파이프라인 (Cron Job용)

    ★ Google Sheets에서 '준비' 상태 에피소드를 찾아 대본 자동 생성
    ★ 생성 후 상태를 '대기'로 변경 (영상 생성 파이프라인이 자동으로 처리)

    Args:
        max_scripts: 한 번에 생성할 최대 대본 수 (기본 1)

    Returns:
        {
            "success": True,
            "generated": 1,
            "episodes": [...],
            "total_cost": 0.15
        }
    """
    print(f"\n{'='*60}")
    print(f"[WUXIA] 자동 대본 생성 파이프라인 시작")
    print(f"[WUXIA] max_scripts: {max_scripts}")
    print(f"{'='*60}\n")

    # 1) '준비' 상태 에피소드 조회
    ready_episodes = get_ready_episodes()

    if not ready_episodes:
        print("[WUXIA] '준비' 상태 에피소드 없음")
        return {
            "success": True,
            "generated": 0,
            "episodes": [],
            "total_cost": 0,
            "message": "생성할 에피소드 없음"
        }

    print(f"[WUXIA] '준비' 상태 에피소드 {len(ready_episodes)}개 발견")

    # 2) max_scripts 개수만큼 처리
    generated = []
    total_cost = 0.0
    errors = []

    for ep_data in ready_episodes[:max_scripts]:
        row_index = ep_data.get("_row_index")
        episode_id = ep_data.get("episode", "")
        title = ep_data.get("title", "")
        summary = ep_data.get("summary", "")
        characters_str = ep_data.get("characters", "")
        key_events_str = ep_data.get("key_events", "")

        # 에피소드 번호 추출 (EP001 → 1)
        try:
            ep_num = int(episode_id.replace("EP", ""))
        except:
            ep_num = 1

        print(f"\n[WUXIA] === {episode_id}: {title} (행 {row_index}) ===")

        # 상태를 '처리중'으로 변경
        update_episode_status(row_index, status="처리중")

        try:
            # 이전/다음 에피소드 정보
            prev_template = EPISODE_TEMPLATES.get(ep_num - 1)
            next_template = EPISODE_TEMPLATES.get(ep_num + 1)

            prev_summary = prev_template.get("summary") if prev_template else None
            next_preview = next_template.get("summary") if next_template else None

            # 대본 생성 (통합: 대본 + 이미지 프롬프트 + 메타데이터)
            script_result = generate_episode_script(
                episode=ep_num,
                title=title,
                summary=summary,
                key_events=key_events_str.split("\n") if key_events_str else None,
                characters=characters_str.split(", ") if characters_str else None,
                prev_episode_summary=prev_summary,
                next_episode_preview=next_preview,
            )

            if not script_result.get("ok"):
                error_msg = script_result.get("error", "알 수 없는 오류")
                print(f"[WUXIA] ❌ 대본 생성 실패: {error_msg}")
                update_episode_status(row_index, status="실패", error_msg=error_msg)
                errors.append({"episode": episode_id, "error": error_msg})
                continue

            # 결과 추출
            script = script_result.get("script", "")
            char_count = script_result.get("char_count", len(script))
            cost = script_result.get("cost", 0)
            total_cost += cost

            # YouTube 메타데이터
            youtube_data = script_result.get("youtube", {})
            youtube_title = youtube_data.get("title", f"[{SERIES_INFO['title']}] {title}")

            # 썸네일 정보
            thumbnail_data = script_result.get("thumbnail", {})
            thumbnail_text = f"{thumbnail_data.get('text_line1', '')}\n{thumbnail_data.get('text_line2', '')}"

            # 씬 이미지 프롬프트
            scenes = script_result.get("scenes", [])

            print(f"[WUXIA] ✅ 대본 생성 완료: {char_count:,}자, 씬 {len(scenes)}개")
            print(f"[WUXIA] 비용: ${cost:.4f}")

            # 시트 업데이트 (상태 → '대기')
            update_result = update_episode_with_script(
                row_index=row_index,
                script=script,
                youtube_title=youtube_title,
                thumbnail_text=thumbnail_text,
                scenes=scenes,
                cost=cost,
            )

            if update_result.get("ok"):
                generated.append({
                    "episode": episode_id,
                    "title": title,
                    "char_count": char_count,
                    "scenes": len(scenes),
                    "cost": cost,
                    "row_index": row_index,
                })
                print(f"[WUXIA] ✅ 시트 업데이트 완료 → 상태: '대기'")
            else:
                error_msg = update_result.get("error", "시트 업데이트 실패")
                update_episode_status(row_index, status="실패", error_msg=error_msg)
                errors.append({"episode": episode_id, "error": error_msg})

        except Exception as e:
            import traceback
            traceback.print_exc()
            error_msg = str(e)
            print(f"[WUXIA] ❌ 예외 발생: {error_msg}")
            update_episode_status(row_index, status="실패", error_msg=error_msg)
            errors.append({"episode": episode_id, "error": error_msg})

    # 3) 결과 정리
    print(f"\n{'='*60}")
    print(f"[WUXIA] 자동 대본 생성 완료!")
    print(f"[WUXIA] 생성: {len(generated)}개, 실패: {len(errors)}개")
    print(f"[WUXIA] 총 비용: ${total_cost:.4f}")
    print(f"{'='*60}\n")

    return {
        "success": True,
        "generated": len(generated),
        "episodes": generated,
        "errors": errors if errors else None,
        "total_cost": round(total_cost, 4),
    }


def main():
    parser = argparse.ArgumentParser(description=f"{SERIES_INFO['title']} 무협 파이프라인")
    parser.add_argument("--episode", "-e", type=int, default=1, help="에피소드 번호")
    parser.add_argument("--video", "-v", action="store_true", help="영상 생성")
    parser.add_argument("--upload", "-u", action="store_true", help="YouTube 업로드")
    parser.add_argument("--privacy", choices=["private", "unlisted", "public"], default="private")
    parser.add_argument("--auto", action="store_true", help="자동 대본 생성 (시트 기반)")
    parser.add_argument("--max-scripts", type=int, default=1, help="자동 생성 시 최대 대본 수")

    args = parser.parse_args()

    if args.auto:
        # 자동 대본 생성 모드
        result = run_auto_script_pipeline(max_scripts=args.max_scripts)
    else:
        # 수동 파이프라인 모드
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
