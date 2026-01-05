"""
혈영 이세계편 파이프라인 메인 오케스트레이터

전체 흐름:
1. PLANNER: 에피소드 기획서 생성
2. WRITER: 대본 생성 (25,000자)
3. 병렬 실행:
   - ARTIST: 이미지 프롬프트
   - NARRATOR: TTS 설정
   - SUBTITLE: 자막 스타일
   - EDITOR: BGM/SFX 설정
   - METADATA: YouTube 메타데이터
4. REVIEWER: 품질 검수
5. Workers: 실제 생성 (TTS, 이미지, 영상)
6. YouTube 업로드 (옵션)
"""

import os
import sys
import json
import argparse
from datetime import datetime
from typing import Dict, Any, Optional, List
from concurrent.futures import ThreadPoolExecutor, as_completed

# 프로젝트 루트 추가
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from .config import (
    SERIES_INFO,
    PART_STRUCTURE,
    SCRIPT_CONFIG,
    OUTPUT_BASE,
    SHEET_NAME,
    TTS_CONFIG,
)
from .agents import (
    run_planner,
    run_writer,
    run_artist,
    run_narrator,
    run_subtitle,
    run_editor,
    run_metadata,
    run_reviewer,
)


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


def get_part_for_episode(episode: int) -> Dict[str, Any]:
    """에피소드 번호로 부 정보 조회"""
    for part_num, part_data in PART_STRUCTURE.items():
        start, end = part_data["episodes"]
        if start <= episode <= end:
            return {"part": part_num, **part_data}
    return {"part": 1, "title": "이방인"}


def run_pipeline(
    episode: int,
    prev_summary: Optional[str] = None,
    generate_assets: bool = True,
    generate_video: bool = False,
    upload_youtube: bool = False,
    privacy_status: str = "private",
    max_retries: int = 1,
) -> Dict[str, Any]:
    """
    이세계 파이프라인 전체 실행

    Args:
        episode: 에피소드 번호 (1~60)
        prev_summary: 이전 에피소드 요약 (연속성)
        generate_assets: TTS/이미지 생성 여부
        generate_video: 영상 렌더링 여부
        upload_youtube: YouTube 업로드 여부
        privacy_status: YouTube 공개 설정
        max_retries: REVIEWER 반려 시 재시도 횟수

    Returns:
        {
            "ok": True,
            "episode": 1,
            "title": "이방인",
            "brief": {...},
            "script": "...",
            "char_count": 25000,
            "image_prompt": {...},
            "review": {...},
            "video_path": "...",
            "youtube_url": "...",
            "cost": 0.50
        }
    """
    print(f"\n{'='*60}")
    print(f"[ISEKAI] {SERIES_INFO['title']} 제{episode}화 파이프라인 시작")
    print(f"{'='*60}\n")

    # 디렉토리 생성
    ensure_directories()

    part_info = get_part_for_episode(episode)
    total_cost = 0.0
    retry_count = 0

    result = {
        "ok": True,
        "episode": episode,
        "part": part_info.get("part", 1),
        "part_title": part_info.get("title", ""),
        "series": SERIES_INFO["title"],
    }

    while retry_count <= max_retries:
        # ========================================
        # Phase 1: PLANNER
        # ========================================
        print(f"[PHASE 1] PLANNER 실행... (시도 {retry_count + 1}/{max_retries + 1})")

        planner_result = run_planner(episode, prev_summary)
        if not planner_result.get("ok"):
            return {"ok": False, "error": f"PLANNER 실패: {planner_result.get('error')}"}

        brief = planner_result
        title = brief.get("title", f"제{episode}화")
        total_cost += 0.05  # Opus 호출 비용 추정

        print(f"[PHASE 1] 기획 완료: {title}")
        print(f"[PHASE 1] 씬 수: {len(brief.get('scenes', []))}개")

        # Brief 저장
        brief_path = os.path.join(BRIEF_DIR, f"ep{episode:03d}_brief.json")
        with open(brief_path, "w", encoding="utf-8") as f:
            json.dump(brief, f, ensure_ascii=False, indent=2)

        result["brief"] = brief
        result["title"] = title

        # ========================================
        # Phase 2: WRITER
        # ========================================
        print(f"\n[PHASE 2] WRITER 실행...")

        writer_result = run_writer(brief)
        if not writer_result.get("ok"):
            return {"ok": False, "error": f"WRITER 실패: {writer_result.get('error')}"}

        script = writer_result.get("script", "")
        char_count = writer_result.get("char_count", len(script))
        total_cost += 0.20  # 긴 대본 생성 비용

        print(f"[PHASE 2] 대본 완료: {char_count:,}자")

        # 대본 저장
        script_path = os.path.join(SCRIPT_DIR, f"ep{episode:03d}_{title}.txt")
        with open(script_path, "w", encoding="utf-8") as f:
            f.write(script)

        result["script"] = script
        result["char_count"] = char_count
        result["script_path"] = script_path

        # ========================================
        # Phase 3: 병렬 에이전트 실행
        # ========================================
        print(f"\n[PHASE 3] 병렬 에이전트 실행 (ARTIST, NARRATOR, SUBTITLE, EDITOR, METADATA)...")

        # 등장 캐릭터 추출
        characters = []
        for scene in brief.get("scenes", []):
            characters.extend(scene.get("characters", []))
        characters = list(set(characters))

        # 병렬 실행
        parallel_results = {}
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = {
                executor.submit(run_artist, episode, title, script, characters): "ARTIST",
                executor.submit(run_narrator, episode, script): "NARRATOR",
                executor.submit(run_subtitle, episode, script): "SUBTITLE",
                executor.submit(run_editor, episode, brief, script): "EDITOR",
                executor.submit(run_metadata, episode, title, brief.get("summary", "")): "METADATA",
            }

            for future in as_completed(futures):
                agent_name = futures[future]
                try:
                    agent_result = future.result()
                    parallel_results[agent_name] = agent_result
                    status = "OK" if agent_result.get("ok") else "FAIL"
                    print(f"[PHASE 3] {agent_name}: {status}")
                    total_cost += 0.03  # 에이전트당 비용
                except Exception as e:
                    print(f"[PHASE 3] {agent_name}: ERROR - {e}")
                    parallel_results[agent_name] = {"ok": False, "error": str(e)}

        result["image"] = parallel_results.get("ARTIST", {})
        result["tts_config"] = parallel_results.get("NARRATOR", {})
        result["subtitle_config"] = parallel_results.get("SUBTITLE", {})
        result["edit_config"] = parallel_results.get("EDITOR", {})
        result["metadata"] = parallel_results.get("METADATA", {})

        # ========================================
        # Phase 4: REVIEWER
        # ========================================
        print(f"\n[PHASE 4] REVIEWER 실행...")

        reviewer_result = run_reviewer(
            episode=episode,
            brief=brief,
            script=script,
            image=parallel_results.get("ARTIST", {}),
            tts=parallel_results.get("NARRATOR", {}),
            subtitle=parallel_results.get("SUBTITLE", {}),
            edit=parallel_results.get("EDITOR", {}),
            metadata=parallel_results.get("METADATA", {}),
        )
        total_cost += 0.05

        result["review"] = reviewer_result

        if reviewer_result.get("status") == "approved":
            print(f"[PHASE 4] REVIEWER: 승인")
            break
        else:
            issues = reviewer_result.get("overall_issues", [])
            print(f"[PHASE 4] REVIEWER: 반려 - {issues}")

            if retry_count < max_retries:
                print(f"[PHASE 4] 재시도 진행...")
                retry_count += 1
                continue
            else:
                print(f"[PHASE 4] 최대 재시도 도달, 현재 결과로 진행")
                break

    # ========================================
    # Phase 5: Workers (실제 생성)
    # ========================================
    if generate_assets:
        print(f"\n[PHASE 5] Workers 실행 (TTS, 이미지 생성)...")

        # TTS 생성
        tts_result = _generate_tts(episode, script)
        if tts_result.get("ok"):
            result["audio_path"] = tts_result.get("audio_path")
            result["srt_path"] = tts_result.get("srt_path")
            result["audio_duration"] = tts_result.get("duration")
            print(f"[PHASE 5] TTS 완료: {tts_result.get('duration', 0):.1f}초")
        else:
            print(f"[PHASE 5] TTS 실패: {tts_result.get('error')}")

        # 이미지 생성
        image_prompt = result.get("image", {}).get("main_image", {}).get("prompt", "")
        if image_prompt:
            image_result = _generate_image(episode, image_prompt)
            if image_result.get("ok"):
                result["image_path"] = image_result.get("image_path")
                print(f"[PHASE 5] 이미지 생성 완료")
            else:
                print(f"[PHASE 5] 이미지 생성 실패: {image_result.get('error')}")

    # ========================================
    # Phase 6: 영상 렌더링 (옵션)
    # ========================================
    if generate_video:
        print(f"\n[PHASE 6] 영상 렌더링...")
        # TODO: FFmpeg 렌더링 구현
        print(f"[PHASE 6] 영상 렌더링은 아직 구현되지 않았습니다.")
        result["video_path"] = None

    # ========================================
    # Phase 7: YouTube 업로드 (옵션)
    # ========================================
    if upload_youtube:
        print(f"\n[PHASE 7] YouTube 업로드...")
        # TODO: YouTube 업로드 구현
        print(f"[PHASE 7] YouTube 업로드는 아직 구현되지 않았습니다.")
        result["youtube_url"] = None

    # ========================================
    # 결과 정리
    # ========================================
    result["cost"] = round(total_cost, 4)

    print(f"\n{'='*60}")
    print(f"[ISEKAI] 파이프라인 완료!")
    print(f"{'='*60}")
    print(f"  에피소드: 제{episode}화 - {title}")
    print(f"  대본: {char_count:,}자")
    if result.get("audio_duration"):
        duration = result["audio_duration"]
        print(f"  오디오: {duration:.1f}초 ({duration/60:.1f}분)")
    print(f"  비용: ${total_cost:.4f}")
    print(f"{'='*60}\n")

    return result


def _generate_tts(episode: int, script: str) -> Dict[str, Any]:
    """TTS 생성 (Worker)"""
    try:
        # 기존 TTS 모듈 사용
        from scripts.wuxia_pipeline.multi_voice_tts import (
            generate_multi_voice_tts_simple,
            generate_srt_from_timeline,
        )

        episode_id = f"ep{episode:03d}"
        tts_result = generate_multi_voice_tts_simple(
            text=script,
            output_dir=AUDIO_DIR,
            episode_id=episode_id,
            voice=TTS_CONFIG["voice"],
            speed=TTS_CONFIG["speed"],
        )

        if tts_result.get("ok"):
            # SRT 생성
            srt_path = os.path.join(SUBTITLE_DIR, f"{episode_id}.srt")
            if tts_result.get("timeline"):
                generate_srt_from_timeline(tts_result["timeline"], srt_path)
                tts_result["srt_path"] = srt_path

        return tts_result

    except ImportError:
        # wuxia_pipeline 없으면 스킵
        return {"ok": False, "error": "TTS 모듈 없음 (wuxia_pipeline 필요)"}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def _generate_image(episode: int, prompt: str) -> Dict[str, Any]:
    """이미지 생성 (Worker)"""
    try:
        # Gemini 이미지 생성 API 호출
        import requests

        api_url = os.getenv("IMAGE_API_URL", "http://localhost:5059/api/ai-tools/image-generate")

        response = requests.post(
            api_url,
            json={
                "prompt": prompt,
                "style": "realistic",
                "ratio": "16:9",
            },
            timeout=120,
        )

        if response.status_code == 200:
            data = response.json()
            if data.get("success"):
                # 이미지 저장
                image_url = data.get("image_url")
                image_path = os.path.join(IMAGE_DIR, f"ep{episode:03d}_main.png")

                # 이미지 다운로드
                img_response = requests.get(image_url, timeout=60)
                if img_response.status_code == 200:
                    with open(image_path, "wb") as f:
                        f.write(img_response.content)
                    return {"ok": True, "image_path": image_path}

        return {"ok": False, "error": "이미지 생성 실패"}

    except Exception as e:
        return {"ok": False, "error": str(e)}


def run_auto_pipeline(max_episodes: int = 1) -> Dict[str, Any]:
    """
    자동 파이프라인 (Cron Job용)

    Google Sheets에서 '준비' 상태 에피소드를 찾아 자동 생성

    Args:
        max_episodes: 한 번에 처리할 최대 에피소드 수

    Returns:
        {
            "success": True,
            "generated": 1,
            "episodes": [...],
            "total_cost": 0.50
        }
    """
    print(f"\n{'='*60}")
    print(f"[ISEKAI] 자동 파이프라인 시작")
    print(f"[ISEKAI] max_episodes: {max_episodes}")
    print(f"{'='*60}\n")

    try:
        from .sheets import get_ready_episodes, update_episode_status, update_episode_with_result
    except ImportError:
        return {"success": False, "error": "sheets 모듈 필요"}

    # 1) '준비' 상태 에피소드 조회
    ready_episodes = get_ready_episodes()

    if not ready_episodes:
        print(f"[ISEKAI] '준비' 상태 에피소드 없음")
        return {
            "success": True,
            "generated": 0,
            "episodes": [],
            "total_cost": 0,
            "message": "생성할 에피소드 없음",
        }

    print(f"[ISEKAI] '준비' 상태 에피소드 {len(ready_episodes)}개 발견")

    # 2) max_episodes 개수만큼 처리
    generated = []
    total_cost = 0.0
    errors = []

    for ep_data in ready_episodes[:max_episodes]:
        row_index = ep_data.get("_row_index")
        episode_id = ep_data.get("episode", "")
        title = ep_data.get("title", "")
        prev_summary = ep_data.get("prev_summary", "")

        # 에피소드 번호 추출 (EP001 → 1)
        try:
            ep_num = int(episode_id.replace("EP", ""))
        except:
            ep_num = 1

        print(f"\n[ISEKAI] === {episode_id}: {title} (행 {row_index}) ===")

        # 상태를 '처리중'으로 변경
        update_episode_status(row_index, status="처리중")

        try:
            # 파이프라인 실행
            result = run_pipeline(
                episode=ep_num,
                prev_summary=prev_summary,
                generate_assets=True,
                generate_video=False,
                upload_youtube=False,
            )

            if result.get("ok"):
                cost = result.get("cost", 0)
                total_cost += cost

                # 시트 업데이트
                update_result = update_episode_with_result(
                    row_index=row_index,
                    script=result.get("script", ""),
                    youtube_title=result.get("metadata", {}).get("youtube", {}).get("title", ""),
                    audio_path=result.get("audio_path"),
                    cost=cost,
                )

                if update_result.get("ok"):
                    generated.append({
                        "episode": episode_id,
                        "title": title,
                        "char_count": result.get("char_count", 0),
                        "cost": cost,
                        "row_index": row_index,
                    })
                    print(f"[ISEKAI] 완료: {episode_id}")
                else:
                    error_msg = update_result.get("error", "시트 업데이트 실패")
                    update_episode_status(row_index, status="실패", error_msg=error_msg)
                    errors.append({"episode": episode_id, "error": error_msg})
            else:
                error_msg = result.get("error", "파이프라인 실패")
                update_episode_status(row_index, status="실패", error_msg=error_msg)
                errors.append({"episode": episode_id, "error": error_msg})

        except Exception as e:
            import traceback
            traceback.print_exc()
            error_msg = str(e)
            print(f"[ISEKAI] 예외 발생: {error_msg}")
            update_episode_status(row_index, status="실패", error_msg=error_msg)
            errors.append({"episode": episode_id, "error": error_msg})

    # 3) 결과 정리
    print(f"\n{'='*60}")
    print(f"[ISEKAI] 자동 파이프라인 완료!")
    print(f"[ISEKAI] 생성: {len(generated)}개, 실패: {len(errors)}개")
    print(f"[ISEKAI] 총 비용: ${total_cost:.4f}")
    print(f"{'='*60}\n")

    return {
        "success": True,
        "generated": len(generated),
        "episodes": generated,
        "errors": errors if errors else None,
        "total_cost": round(total_cost, 4),
    }


def run_single_agent(agent_name: str, episode: int, **kwargs) -> Dict[str, Any]:
    """
    단일 에이전트 테스트 실행

    Args:
        agent_name: 에이전트 이름 (PLANNER, WRITER, ARTIST, ...)
        episode: 에피소드 번호
        **kwargs: 에이전트별 추가 인자

    Returns:
        에이전트 결과
    """
    print(f"\n[TEST] {agent_name} 에이전트 테스트 (제{episode}화)")

    agent_map = {
        "PLANNER": lambda: run_planner(episode, kwargs.get("prev_summary")),
        "WRITER": lambda: run_writer(kwargs.get("brief", {})),
        "ARTIST": lambda: run_artist(
            episode,
            kwargs.get("title", "테스트"),
            kwargs.get("script", ""),
            kwargs.get("characters", ["무영"]),
        ),
        "NARRATOR": lambda: run_narrator(episode, kwargs.get("script", "")),
        "SUBTITLE": lambda: run_subtitle(episode, kwargs.get("script", "")),
        "EDITOR": lambda: run_editor(episode, kwargs.get("brief", {}), kwargs.get("script", "")),
        "METADATA": lambda: run_metadata(
            episode,
            kwargs.get("title", "테스트"),
            kwargs.get("summary", ""),
        ),
    }

    if agent_name.upper() not in agent_map:
        return {"ok": False, "error": f"알 수 없는 에이전트: {agent_name}"}

    result = agent_map[agent_name.upper()]()
    print(f"[TEST] 결과: {json.dumps(result, ensure_ascii=False, indent=2)[:500]}...")

    return result


def main():
    parser = argparse.ArgumentParser(description=f"{SERIES_INFO['title']} 파이프라인")
    parser.add_argument("--episode", "-e", type=int, default=1, help="에피소드 번호 (1~60)")
    parser.add_argument("--assets", "-a", action="store_true", help="TTS/이미지 생성")
    parser.add_argument("--video", "-v", action="store_true", help="영상 렌더링")
    parser.add_argument("--upload", "-u", action="store_true", help="YouTube 업로드")
    parser.add_argument("--privacy", choices=["private", "unlisted", "public"], default="private")
    parser.add_argument("--auto", action="store_true", help="자동 파이프라인 (시트 기반)")
    parser.add_argument("--max-episodes", type=int, default=1, help="자동 생성 시 최대 에피소드 수")
    parser.add_argument("--test-agent", type=str, help="단일 에이전트 테스트 (PLANNER, WRITER, ...)")

    args = parser.parse_args()

    if args.test_agent:
        # 단일 에이전트 테스트
        result = run_single_agent(args.test_agent, args.episode)
    elif args.auto:
        # 자동 파이프라인 모드
        result = run_auto_pipeline(max_episodes=args.max_episodes)
    else:
        # 수동 파이프라인 모드
        result = run_pipeline(
            episode=args.episode,
            generate_assets=args.assets,
            generate_video=args.video,
            upload_youtube=args.upload,
            privacy_status=args.privacy,
        )

    print("\n=== 결과 ===")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
