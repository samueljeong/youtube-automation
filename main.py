#!/usr/bin/env python3
"""
Drama Content Pipeline - Main Controller
Step1 → Step2 → Step3 → Step4 → Step5 자동 실행 파이프라인

Usage:
    python3 main.py --mode test --category category1
    python3 main.py --mode prod --category category2
"""

import argparse
import json
import os
import sys
from datetime import datetime
from typing import Dict, Any, Optional

# Step 모듈 import
from step1_script_generation import run_step1
from step2_image_generation import image_prompt_builder, call_gpt_mini
from step3_tts_and_subtitles import tts_script_builder, call_tts_engine
from step4_thumbnail_generation import call_image_model as thumbnail_generator
from step4_video_assembly import video_builder
from step5_youtube_upload import schedule_upload


# 경로 설정
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUTS_DIR = os.path.join(BASE_DIR, "outputs")


def load_json(path: str) -> Dict[str, Any]:
    """
    JSON 파일 안전하게 로드

    Args:
        path: JSON 파일 경로

    Returns:
        파싱된 딕셔너리

    Raises:
        FileNotFoundError: 파일이 없는 경우
        json.JSONDecodeError: JSON 파싱 실패
    """
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path: str, data: Dict[str, Any]) -> None:
    """
    JSON 파일 저장 (indent=2, ensure_ascii=False)

    Args:
        path: 저장할 파일 경로
        data: 저장할 딕셔너리
    """
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"  📄 Saved: {path}")


def run_step(
    step_name: str,
    run_func: callable,
    input_data: Dict[str, Any],
    output_path: str
) -> Dict[str, Any]:
    """
    Step 실행 공통 함수

    Args:
        step_name: Step 이름 (로깅용)
        run_func: 실행할 함수
        input_data: 입력 데이터
        output_path: 출력 JSON 저장 경로

    Returns:
        Step 출력 딕셔너리

    Raises:
        Exception: Step 실행 중 오류 발생 시
    """
    print(f"\n{'='*60}")
    print(f"🚀 Starting {step_name}...")
    print(f"{'='*60}")

    try:
        output_data = run_func(input_data)
        save_json(output_path, output_data)
        print(f"✅ {step_name} completed successfully")
        return output_data
    except Exception as e:
        print(f"❌ {step_name} failed: {str(e)}")
        raise


def create_step1_input(mode: str, category: str) -> Dict[str, Any]:
    """
    Step1 입력 JSON 자동 생성

    Args:
        mode: 실행 모드 ("test" or "prod")
        category: 콘텐츠 카테고리

    Returns:
        Step1 입력 딕셔너리
    """
    if mode == "test":
        return {
            "step": "step1_script_generation",
            "mode": "test",
            "category": category,
            "difficulty": "broad",
            "target": {
                "age_group": "60-70",
                "keywords": ["향수", "추억"]
            },
            "length_minutes": 1,
            "style": {
                "tone": "nostalgic",
                "pacing": "slow"
            },
            "characters": {
                "max_count": 1,
                "speaker": "solo"
            },
            "language": "ko",
            "force_scene_count": 4
        }
    else:
        # Production mode
        return {
            "step": "step1_script_generation",
            "mode": "production",
            "category": category,
            "difficulty": "balanced",
            "target": {
                "age_group": "60-70",
                "keywords": ["향수", "추억", "인생"]
            },
            "length_minutes": 10,
            "style": {
                "tone": "auto",
                "pacing": "moderate"
            },
            "characters": {
                "max_count": 2,
                "speaker": "solo"
            },
            "language": "ko"
        }


def create_step5_input(
    step1_output: Dict[str, Any],
    step4_output: Dict[str, Any],
    upload_mode: str = "immediate"
) -> Dict[str, Any]:
    """
    Step5 입력 JSON 생성 (Step1, Step4 결과 조합)

    Args:
        step1_output: Step1 출력 데이터
        step4_output: Step4 출력 데이터
        upload_mode: 업로드 모드 ("immediate" or "scheduled")

    Returns:
        Step5 입력 딕셔너리
    """
    # Step1에서 메타데이터 추출
    titles = step1_output.get("titles", {})
    title = titles.get("main_title", "Untitled")

    meta = step1_output.get("meta", {})
    episode_theme = meta.get("episode_theme", "")

    # 태그 추출
    tags_seed = []
    if "highlight_preview" in step1_output:
        tags_seed = step1_output["highlight_preview"].get("hashtags", [])

    return {
        "step": "step5_youtube_upload",
        "category": step1_output.get("category", "category1"),
        "title": title,
        "description_seed": episode_theme,
        "tags_seed": tags_seed,
        "video_filename": step4_output.get("video_filename", ""),
        "upload_mode": upload_mode,
        "preferred_slot": "09:00",
        "timezone": "Asia/Seoul"
    }


def main():
    """메인 파이프라인 실행"""
    # argparse 설정
    parser = argparse.ArgumentParser(
        description="Drama Content Pipeline Controller",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 main.py --mode test --category category1
  python3 main.py --mode prod --category category2 --upload scheduled
        """
    )
    parser.add_argument(
        "--mode",
        choices=["test", "prod"],
        default="test",
        help="실행 모드 (test: 1분/4컷, prod: 전체)"
    )
    parser.add_argument(
        "--category",
        default="category1",
        help="콘텐츠 카테고리 (category1=향수, category2=명언)"
    )
    parser.add_argument(
        "--upload",
        choices=["immediate", "scheduled", "skip"],
        default="skip",
        help="업로드 모드 (skip=업로드 안함)"
    )
    parser.add_argument(
        "--skip-to",
        type=int,
        choices=[1, 2, 3, 4, 5],
        help="특정 Step부터 시작 (이전 output 파일 필요)"
    )

    args = parser.parse_args()

    # 시작 로그
    print("\n" + "="*60)
    print("🎬 Drama Content Pipeline Started")
    print("="*60)
    print(f"  Mode: {args.mode}")
    print(f"  Category: {args.category}")
    print(f"  Upload: {args.upload}")
    print(f"  Time: {datetime.now().isoformat()}")

    # outputs 폴더 생성
    os.makedirs(OUTPUTS_DIR, exist_ok=True)

    try:
        # ============================================================
        # Step 1: Script Generation
        # ============================================================
        step1_input_path = os.path.join(OUTPUTS_DIR, "step1_input.json")
        step1_output_path = os.path.join(OUTPUTS_DIR, "step1_output.json")

        if args.skip_to and args.skip_to > 1:
            print(f"\n⏭️  Skipping to Step {args.skip_to}, loading previous outputs...")
            step1_output = load_json(step1_output_path)
        else:
            step1_input = create_step1_input(args.mode, args.category)
            save_json(step1_input_path, step1_input)

            step1_output = run_step(
                "Step 1: Script Generation",
                run_step1.run,
                step1_input,
                step1_output_path
            )

        # ============================================================
        # Step 2: Image Prompt Generation
        # ============================================================
        step2_output_path = os.path.join(OUTPUTS_DIR, "step2_output.json")

        if args.skip_to and args.skip_to > 2:
            step2_output = load_json(step2_output_path)
        else:
            step2_output = run_step(
                "Step 2: Image Prompt Generation",
                call_gpt_mini.generate_image_prompts,
                step1_output,
                step2_output_path
            )

        # ============================================================
        # Step 3: TTS & Subtitle Generation
        # ============================================================
        step3_output_path = os.path.join(OUTPUTS_DIR, "step3_output.json")

        if args.skip_to and args.skip_to > 3:
            step3_output = load_json(step3_output_path)
        else:
            step3_input = tts_script_builder.build_tts_input(step1_output)
            save_json(os.path.join(OUTPUTS_DIR, "step3_input.json"), step3_input)

            # Step3 실행 (TTS + 자막) - step1_output을 사용하여 원본 narration 접근
            step3_output = run_step(
                "Step 3: TTS & Subtitle Generation",
                call_tts_engine.generate_tts_output,
                step1_output,
                step3_output_path
            )

        # ============================================================
        # Step 3.5: Thumbnail Generation
        # ============================================================
        thumbnail_output_path = os.path.join(OUTPUTS_DIR, "thumbnail_output.json")

        thumbnail_output = run_step(
            "Step 3.5: Thumbnail Generation",
            thumbnail_generator.run_thumbnail_generation,
            step1_output,
            thumbnail_output_path
        )

        # ============================================================
        # Step 4: Video Assembly
        # ============================================================
        step4_output_path = os.path.join(OUTPUTS_DIR, "step4_output.json")

        if args.skip_to and args.skip_to > 4:
            step4_output = load_json(step4_output_path)
        else:
            # Step4 입력 생성 (Step2 이미지 + Step3 오디오 조합)
            step4_input = video_builder.build_step4_input(
                title=step1_output.get("titles", {}).get("main_title", "Untitled"),
                step3_result=step3_output,
                step2_images=step2_output
            )
            save_json(os.path.join(OUTPUTS_DIR, "step4_input.json"), step4_input)

            step4_output = run_step(
                "Step 4: Video Assembly",
                video_builder.build_video,
                step4_input,
                step4_output_path
            )

        # ============================================================
        # Step 5: YouTube Upload
        # ============================================================
        if args.upload == "skip":
            print("\n⏭️  Skipping Step 5 (YouTube Upload)")
            step5_output = {"step": "step5_youtube_upload_result", "status": "skipped"}
        else:
            step5_input_path = os.path.join(OUTPUTS_DIR, "step5_input.json")
            step5_output_path = os.path.join(OUTPUTS_DIR, "step5_output.json")

            step5_input = create_step5_input(
                step1_output,
                step4_output,
                upload_mode=args.upload
            )
            save_json(step5_input_path, step5_input)

            step5_output = run_step(
                "Step 5: YouTube Upload",
                schedule_upload.schedule_or_upload,
                step5_input,
                step5_output_path
            )

        # ============================================================
        # 완료
        # ============================================================
        print("\n" + "="*60)
        print("🎉 Pipeline completed successfully!")
        print("="*60)

        if step5_output.get("url"):
            print(f"📺 Uploaded video URL: {step5_output['url']}")
        elif step5_output.get("status") == "scheduled":
            print(f"📅 Video scheduled for: {step5_output.get('scheduled_time')}")
        elif step5_output.get("status") == "skipped":
            print(f"📁 Video file: {step4_output.get('video_filename')}")

        print(f"\n📂 All outputs saved to: {OUTPUTS_DIR}")

    except Exception as e:
        print("\n" + "="*60)
        print(f"💥 Pipeline failed: {str(e)}")
        print("="*60)
        sys.exit(1)


def _mock_step3_run(step3_input: Dict[str, Any]) -> Dict[str, Any]:
    """
    Step3 임시 mock 함수 (실제 run_step3.run 구현 전까지 사용)
    """
    scenes = step3_input.get("scenes", [])
    audio_files = []
    timeline = []
    current_time = 0.0

    for scene in scenes:
        duration = scene.get("approx_duration_minutes", 0.5) * 60  # 분 → 초
        audio_files.append({
            "scene_id": scene.get("scene_id"),
            "order": scene.get("order"),
            "audio_filename": f"audio/{scene.get('scene_id')}.mp3",
            "subtitle_filename": f"subtitles/{scene.get('scene_id')}.srt",
            "duration_seconds": duration
        })
        timeline.append({
            "scene_id": scene.get("scene_id"),
            "order": scene.get("order"),
            "start_time": current_time,
            "end_time": current_time + duration
        })
        current_time += duration

    return {
        "step": "step3_tts_result",
        "title": step3_input.get("title"),
        "audio_files": audio_files,
        "timeline": timeline
    }


if __name__ == "__main__":
    main()
