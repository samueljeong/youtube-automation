#!/usr/bin/env python3
"""
19화 발해 영상 생성 스크립트

Mac에서 직접 실행:
  cd ~/Desktop/MY_PAGE/project/server/my_page_v2
  source venv/bin/activate
  python scripts/history_pipeline/generate_ep019.py
"""

import os
import sys

# 프로젝트 루트를 path에 추가
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)

from scripts.history_pipeline.episodes.ep019_balhae_data import (
    EPISODE_INFO,
    SCRIPT,
    IMAGE_PROMPTS,
    METADATA,
    THUMBNAIL,
)
from scripts.history_pipeline.image_gen import generate_scene_images
from scripts.history_pipeline.renderer import render_multi_image_video
from scripts.history_pipeline.tts import generate_tts


def main():
    episode_id = EPISODE_INFO["episode_id"]
    title = EPISODE_INFO["title"]

    print("=" * 60)
    print(f"  19화 발해 영상 생성")
    print("=" * 60)
    print(f"  에피소드: {title}")
    print(f"  대본: {len(SCRIPT):,}자")
    print(f"  이미지: {len(IMAGE_PROMPTS)}컷")
    print("=" * 60)

    # 경로 설정
    audio_path = f"outputs/history/audio/{episode_id}.mp3"
    srt_path = f"outputs/history/subtitles/{episode_id}.srt"
    image_dir = f"outputs/history/images"
    video_path = f"outputs/history/videos/{episode_id}.mp4"

    # 1. TTS 생성/확인
    print(f"\n[1/4] TTS 확인...")
    if os.path.exists(audio_path):
        size_mb = os.path.getsize(audio_path) / (1024 * 1024)
        print(f"✓ TTS 존재: {audio_path} ({size_mb:.1f}MB)")
    else:
        print(f"  TTS 없음, 생성 중...")
        os.makedirs(os.path.dirname(audio_path), exist_ok=True)

        tts_result = generate_tts(
            episode_id=episode_id,
            script=SCRIPT,
            output_dir=os.path.dirname(audio_path),
            voice="Charon",  # Gemini TTS
        )

        if not tts_result.get("ok"):
            print(f"✗ TTS 생성 실패: {tts_result.get('error')}")
            return

        audio_path = tts_result.get("audio_path", audio_path)
        srt_path = tts_result.get("srt_path", srt_path)
        print(f"✓ TTS 생성 완료: {tts_result.get('duration', 0):.1f}초")

    # 2. 이미지 생성 (테스트: 2개만)
    TEST_IMAGE_COUNT = 2  # 테스트용 - 전체는 len(IMAGE_PROMPTS)
    test_prompts = IMAGE_PROMPTS[:TEST_IMAGE_COUNT]
    print(f"\n[2/4] 이미지 생성 중... ({len(test_prompts)}컷 테스트)")

    # 이미 생성된 이미지 확인
    existing_images = []
    for i in range(1, len(test_prompts) + 1):
        img_path = f"{image_dir}/{episode_id}_scene_{i:02d}.png"
        if os.path.exists(img_path):
            existing_images.append(img_path)

    if len(existing_images) == len(test_prompts):
        print(f"✓ 모든 이미지 이미 존재 ({len(existing_images)}개)")
        image_paths = existing_images
    else:
        print(f"  기존 이미지: {len(existing_images)}개, 생성 필요: {len(test_prompts) - len(existing_images)}개")

        img_result = generate_scene_images(
            episode_id=episode_id,
            prompts=test_prompts,
            output_dir=image_dir,
            style="historical",
        )

        if not img_result.get("ok") and not img_result.get("images"):
            print(f"✗ 이미지 생성 실패: {img_result.get('error')}")
            return

        image_paths = [img["path"] for img in img_result.get("images", [])]
        print(f"✓ 이미지 생성 완료: {len(image_paths)}개")

    # 3. 영상 렌더링
    print(f"\n[3/4] 영상 렌더링 중...")
    os.makedirs(os.path.dirname(video_path), exist_ok=True)

    render_result = render_multi_image_video(
        audio_path=audio_path,
        image_paths=sorted(image_paths),  # 순서대로 정렬
        output_path=video_path,
        srt_path=srt_path if os.path.exists(srt_path) else None,
    )

    if not render_result.get("ok"):
        print(f"✗ 렌더링 실패: {render_result.get('error')}")
        return

    print(f"\n{'=' * 60}")
    print(f"  ✓ 영상 생성 완료!")
    print(f"{'=' * 60}")
    print(f"  영상: {render_result.get('video_path')}")
    print(f"  길이: {render_result.get('duration', 0):.1f}초")
    print(f"{'=' * 60}")

    # YouTube 업로드 여부 확인
    upload = input("\nYouTube에 업로드하시겠습니까? (y/n): ").strip().lower()
    if upload == 'y':
        print("\n업로드 기능은 아직 구현 중입니다.")
        print("수동으로 업로드해주세요:")
        print(f"  영상: {video_path}")
        print(f"  제목: {METADATA['title']}")


if __name__ == "__main__":
    main()
