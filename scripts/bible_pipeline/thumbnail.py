"""
성경통독 썸네일 생성 모듈

형식:
  - 상단: "100일 성경통독 Day X"
  - 중앙: "창세기1장~15장" (범위 텍스트)
  - 배경: 책별 Gemini 생성 이미지

사용법:
    from scripts.bible_pipeline.thumbnail import generate_episode_thumbnail

    result = generate_episode_thumbnail(episode)
    # {"ok": True, "image_path": "...", "image_url": "..."}
"""

import os
import sys
from typing import Dict, Any, Optional
from PIL import Image, ImageDraw, ImageFont

# 상위 디렉토리 import
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from .background import get_background_path, generate_book_background


# ============================================================
# 썸네일 설정
# ============================================================

# 썸네일 크기 (YouTube 권장)
THUMBNAIL_WIDTH = 1280
THUMBNAIL_HEIGHT = 720

# 폰트 경로 (NanumSquareRound)
FONT_PATHS = [
    '/usr/share/fonts/truetype/nanum/NanumSquareRoundB.ttf',
    '/usr/share/fonts/truetype/nanum/NanumGothicBold.ttf',
    '/usr/share/fonts/truetype/nanum/NanumBarunGothicBold.ttf',
    os.path.join(os.path.dirname(__file__), '..', '..', 'static', 'fonts', 'NanumSquareRoundB.ttf'),
]

# 텍스트 스타일
TEXT_STYLE = {
    'title_font_size': 60,      # "100일 성경통독 Day X"
    'range_font_size': 80,      # "창세기1장~15장"
    'title_color': (255, 255, 255),      # 흰색
    'range_color': (255, 255, 255),      # 흰색
    'shadow_color': (0, 0, 0),           # 그림자
    'shadow_offset': 3,
}


def _get_font(size: int) -> ImageFont.FreeTypeFont:
    """폰트 로드"""
    for font_path in FONT_PATHS:
        if os.path.exists(font_path):
            try:
                return ImageFont.truetype(font_path, size)
            except Exception:
                continue

    # 폴백: 기본 폰트
    print("[THUMB] 경고: 한글 폰트를 찾을 수 없어 기본 폰트 사용")
    return ImageFont.load_default()


def _draw_text_with_shadow(
    draw: ImageDraw.ImageDraw,
    position: tuple,
    text: str,
    font: ImageFont.FreeTypeFont,
    fill: tuple,
    shadow_color: tuple = (0, 0, 0),
    shadow_offset: int = 3
):
    """그림자가 있는 텍스트 그리기"""
    x, y = position

    # 그림자 (4방향)
    for dx in [-shadow_offset, shadow_offset]:
        for dy in [-shadow_offset, shadow_offset]:
            draw.text((x + dx, y + dy), text, font=font, fill=shadow_color)

    # 메인 텍스트
    draw.text(position, text, font=font, fill=fill)


def generate_episode_thumbnail(
    episode,
    output_dir: Optional[str] = None,
    force_regenerate: bool = False
) -> Dict[str, Any]:
    """
    에피소드 썸네일 생성

    Args:
        episode: Episode 객체
        output_dir: 저장 디렉토리 (기본: static/images/bible_thumbnails)
        force_regenerate: True면 기존 이미지 재생성

    Returns:
        {"ok": True, "image_path": str, "image_url": str} 또는
        {"ok": False, "error": str}
    """
    # 기본 저장 경로
    if output_dir is None:
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        output_dir = os.path.join(base_dir, 'static', 'images', 'bible_thumbnails')

    os.makedirs(output_dir, exist_ok=True)

    # 파일명 생성
    filename = f"day_{episode.day_number:03d}.jpg"
    filepath = os.path.join(output_dir, filename)

    # 이미 존재하는지 확인
    if os.path.exists(filepath) and not force_regenerate:
        print(f"[THUMB] Day {episode.day_number} 썸네일 이미 존재: {filepath}")
        return {
            "ok": True,
            "image_path": filepath,
            "image_url": f"/static/images/bible_thumbnails/{filename}",
            "cached": True
        }

    # 배경 이미지 가져오기
    # 여러 책이 포함된 경우 첫 번째 책 사용
    book_name = episode.book
    background_path = get_background_path(book_name)

    if not background_path:
        # 배경 이미지가 없으면 생성
        print(f"[THUMB] {book_name} 배경 이미지 생성 중...")
        result = generate_book_background(book_name)
        if not result.get("ok"):
            return {"ok": False, "error": f"배경 이미지 생성 실패: {result.get('error')}"}
        background_path = result.get("image_path")

    # 배경 이미지 로드 및 리사이즈
    try:
        bg_image = Image.open(background_path)
        bg_image = bg_image.resize((THUMBNAIL_WIDTH, THUMBNAIL_HEIGHT), Image.Resampling.LANCZOS)
        bg_image = bg_image.convert('RGB')
    except Exception as e:
        # 배경 로드 실패 시 그라데이션 생성
        print(f"[THUMB] 배경 로드 실패, 기본 그라데이션 사용: {e}")
        bg_image = _create_gradient_background()

    # 텍스트 오버레이
    draw = ImageDraw.Draw(bg_image)

    # 폰트 로드
    title_font = _get_font(TEXT_STYLE['title_font_size'])
    range_font = _get_font(TEXT_STYLE['range_font_size'])

    # 상단 제목: "100일 성경통독 Day X"
    title_text = f"100일 성경통독 Day {episode.day_number}"

    # 중앙 범위: "창세기1장~15장"
    range_text = episode.range_text

    # 텍스트 위치 계산 (중앙 정렬)
    # 상단 제목
    title_bbox = draw.textbbox((0, 0), title_text, font=title_font)
    title_width = title_bbox[2] - title_bbox[0]
    title_x = (THUMBNAIL_WIDTH - title_width) // 2
    title_y = 80  # 상단에서 80px

    # 중앙 범위
    range_bbox = draw.textbbox((0, 0), range_text, font=range_font)
    range_width = range_bbox[2] - range_bbox[0]
    range_x = (THUMBNAIL_WIDTH - range_width) // 2
    range_y = (THUMBNAIL_HEIGHT - (range_bbox[3] - range_bbox[1])) // 2  # 정중앙

    # 텍스트 그리기 (그림자 포함)
    _draw_text_with_shadow(
        draw, (title_x, title_y), title_text, title_font,
        TEXT_STYLE['title_color'], TEXT_STYLE['shadow_color'], TEXT_STYLE['shadow_offset']
    )

    _draw_text_with_shadow(
        draw, (range_x, range_y), range_text, range_font,
        TEXT_STYLE['range_color'], TEXT_STYLE['shadow_color'], TEXT_STYLE['shadow_offset']
    )

    # 저장
    bg_image.save(filepath, 'JPEG', quality=90)
    print(f"[THUMB] Day {episode.day_number} 썸네일 생성 완료: {filepath}")

    return {
        "ok": True,
        "image_path": filepath,
        "image_url": f"/static/images/bible_thumbnails/{filename}",
        "cached": False
    }


def _create_gradient_background() -> Image.Image:
    """기본 그라데이션 배경 생성 (폴백용)"""
    img = Image.new('RGB', (THUMBNAIL_WIDTH, THUMBNAIL_HEIGHT))

    for y in range(THUMBNAIL_HEIGHT):
        r = int(26 + (40 - 26) * (y / THUMBNAIL_HEIGHT))
        g = int(35 + (60 - 35) * (y / THUMBNAIL_HEIGHT))
        b = int(126 + (90 - 126) * (y / THUMBNAIL_HEIGHT))

        for x in range(THUMBNAIL_WIDTH):
            img.putpixel((x, y), (r, g, b))

    return img


def generate_all_thumbnails(
    episodes: list,
    force_regenerate: bool = False
) -> Dict[str, Any]:
    """
    모든 에피소드 썸네일 생성

    Args:
        episodes: Episode 객체 목록
        force_regenerate: True면 모두 재생성

    Returns:
        {"ok": True, "generated": int, "cached": int, "failed": int}
    """
    generated = 0
    cached = 0
    failed = 0

    print(f"[THUMB] 총 {len(episodes)}개 썸네일 생성 시작...")

    for i, episode in enumerate(episodes, 1):
        print(f"[THUMB] [{i}/{len(episodes)}] Day {episode.day_number}")

        result = generate_episode_thumbnail(episode, force_regenerate=force_regenerate)

        if result.get("ok"):
            if result.get("cached"):
                cached += 1
            else:
                generated += 1
        else:
            print(f"[THUMB] 실패: {result.get('error')}")
            failed += 1

    print(f"\n[THUMB] 완료!")
    print(f"  - 생성: {generated}개")
    print(f"  - 캐시: {cached}개")
    print(f"  - 실패: {failed}개")

    return {
        "ok": failed == 0,
        "generated": generated,
        "cached": cached,
        "failed": failed
    }


# ============================================================
# CLI
# ============================================================

if __name__ == "__main__":
    import argparse
    from .run import BiblePipeline

    parser = argparse.ArgumentParser(description="성경통독 썸네일 생성")
    parser.add_argument("--day", type=int, help="특정 Day 썸네일만 생성")
    parser.add_argument("--all", action="store_true", help="전체 106개 생성")
    parser.add_argument("--force", action="store_true", help="기존 이미지 재생성")
    parser.add_argument("--range", type=str, help="범위 지정 (예: 1-10)")

    args = parser.parse_args()

    pipeline = BiblePipeline()

    if args.day:
        episode = pipeline.get_episode_by_day(args.day)
        if episode:
            result = generate_episode_thumbnail(episode, force_regenerate=args.force)
            print(result)
        else:
            print(f"Day {args.day} 에피소드를 찾을 수 없습니다.")

    elif args.all:
        episodes = pipeline.generate_all_bible_episodes()
        result = generate_all_thumbnails(episodes, force_regenerate=args.force)

    elif args.range:
        start, end = map(int, args.range.split('-'))
        episodes = pipeline.generate_all_bible_episodes()
        selected = [ep for ep in episodes if start <= ep.day_number <= end]
        result = generate_all_thumbnails(selected, force_regenerate=args.force)

    else:
        # 테스트: Day 1, 50, 106 생성
        print("테스트 모드: Day 1, 50, 106 생성")
        episodes = pipeline.generate_all_bible_episodes()
        for day in [1, 50, 106]:
            ep = next((e for e in episodes if e.day_number == day), None)
            if ep:
                result = generate_episode_thumbnail(ep, force_regenerate=args.force)
                print(f"Day {day}: {result}")
