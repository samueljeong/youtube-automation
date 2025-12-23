#!/usr/bin/env python3
"""
성경통독 자막 스타일 테스트
- 창세기 1장 1-10절만으로 짧은 테스트 영상 생성
"""

import os
import sys
import json

# 프로젝트 루트를 path에 추가
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from scripts.bible_pipeline.run import BiblePipeline, Verse, Chapter, Episode
from scripts.bible_pipeline.renderer import generate_ass_subtitle, create_bible_background
from scripts.bible_pipeline.background import get_background_path, generate_book_background


def create_test_episode(pipeline: BiblePipeline, book: str, chapter: int, start_verse: int, end_verse: int) -> Episode:
    """특정 절 범위만으로 테스트 에피소드 생성"""

    # 장 데이터 가져오기
    ch = pipeline.get_chapter(book, chapter)
    if not ch:
        raise ValueError(f"장을 찾을 수 없습니다: {book} {chapter}장")

    # 특정 절 범위만 필터링
    filtered_verses = [v for v in ch.verses if start_verse <= v.verse <= end_verse]

    if not filtered_verses:
        raise ValueError(f"절을 찾을 수 없습니다: {book} {chapter}장 {start_verse}-{end_verse}절")

    # 새 Chapter 객체 생성
    test_chapter = Chapter(
        book=book,
        chapter=chapter,
        verses=filtered_verses
    )

    # Episode 생성
    episode = Episode(
        episode_id="TEST001",
        book=book,
        start_chapter=chapter,
        end_chapter=chapter,
        chapters=[test_chapter],
        day_number=0
    )

    return episode


def generate_test_video():
    """테스트 영상 생성"""

    print("=" * 60)
    print("  성경통독 자막 스타일 테스트")
    print("  창세기 1장 1-10절")
    print("=" * 60)

    # 1. 파이프라인 초기화
    print("\n[1/5] 파이프라인 초기화...")
    pipeline = BiblePipeline()

    # 2. 테스트 에피소드 생성 (창세기 1장 1-10절)
    print("\n[2/5] 테스트 에피소드 생성...")
    episode = create_test_episode(pipeline, "창세기", 1, 1, 10)

    print(f"  - 책: {episode.book}")
    print(f"  - 장: {episode.start_chapter}장")
    print(f"  - 절 수: {len(episode.subtitles)}개")
    print(f"  - 글자 수: {episode.total_chars}자")
    print(f"  - 예상 시간: {episode.estimated_minutes:.1f}분")

    # 자막 내용 미리보기
    print("\n[자막 미리보기]")
    for sub in episode.subtitles:
        print(f"  {sub['book']} {sub['chapter']}장 {sub['verse']}절: {sub['text'][:30]}...")

    # 3. 출력 디렉토리 생성
    output_dir = "/tmp/bible_test"
    os.makedirs(output_dir, exist_ok=True)

    # 4. TTS 생성 (간단한 가짜 durations 사용 - 실제로는 TTS API 필요)
    print("\n[3/5] 테스트용 duration 생성...")

    # 각 절당 대략 3-5초로 가정 (글자 수 기반)
    verse_durations = []
    for sub in episode.subtitles:
        # 한국어 TTS: 약 910자/분 = 15.2자/초
        # 실제로는 TTS 결과에서 정확한 duration을 받아야 함
        char_count = sub['char_count']
        duration = max(2.0, char_count / 15.0)  # 최소 2초
        verse_durations.append(duration)
        print(f"  - {sub['verse']}절: {char_count}자 → {duration:.1f}초")

    total_duration = sum(verse_durations)
    print(f"  - 총 예상 길이: {total_duration:.1f}초")

    # 5. ASS 자막 생성
    print("\n[4/5] ASS 자막 파일 생성...")
    subtitle_path = os.path.join(output_dir, "test_genesis_1_1-10.ass")
    generate_ass_subtitle(
        subtitles=episode.subtitles,
        verse_durations=verse_durations,
        output_path=subtitle_path
    )
    print(f"  - 저장: {subtitle_path}")

    # 6. 배경 이미지 확인/생성
    print("\n[5/5] 배경 이미지 확인...")
    background_path = get_background_path(episode.book)
    if not background_path:
        print(f"  - 배경 이미지 생성 중: {episode.book}")
        result = generate_book_background(episode.book)
        if result.get("ok"):
            background_path = result.get("image_path")
            print(f"  - 생성 완료: {background_path}")
        else:
            print(f"  - 생성 실패: {result.get('error')}")
            # Pillow로 직접 생성
            print("  - Pillow로 직접 생성...")
            bg_img = create_bible_background(episode.book)
            background_path = os.path.join(output_dir, "test_background.png")
            bg_img.save(background_path)
            print(f"  - 저장: {background_path}")
    else:
        print(f"  - 기존 이미지 사용: {background_path}")

    # ASS 파일 내용 출력
    print("\n" + "=" * 60)
    print("  생성된 ASS 자막 파일")
    print("=" * 60)
    with open(subtitle_path, 'r', encoding='utf-8') as f:
        print(f.read())

    print("\n" + "=" * 60)
    print("  테스트 완료!")
    print("=" * 60)
    print(f"\n파일 위치:")
    print(f"  - ASS 자막: {subtitle_path}")
    print(f"  - 배경 이미지: {background_path}")
    print(f"\nFFmpeg로 테스트 영상 생성:")
    print(f"  ffmpeg -y -loop 1 -i {background_path} \\")
    print(f"    -f lavfi -i anullsrc=r=44100:cl=stereo -t {total_duration:.1f} \\")
    print(f"    -vf \"ass={subtitle_path}\" \\")
    print(f"    -c:v libx264 -tune stillimage -c:a aac -shortest \\")
    print(f"    -t {total_duration:.1f} {output_dir}/test_output.mp4")


if __name__ == "__main__":
    generate_test_video()
