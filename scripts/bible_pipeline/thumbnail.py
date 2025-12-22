"""
성경통독 썸네일 생성 모듈

Gemini 3 Pro를 사용하여 텍스트가 포함된 고품질 썸네일 생성

형식:
  - 상단: "100일 성경통독 Day X"
  - 중앙/하단: "창세기1장~15장" (범위 텍스트)
  - 스타일: 성경/영적인 분위기

사용법:
    from scripts.bible_pipeline.thumbnail import generate_episode_thumbnail

    result = generate_episode_thumbnail(episode)
    # {"ok": True, "image_path": "...", "image_url": "..."}
"""

import os
import sys
import base64
from typing import Dict, Any, Optional

# 상위 디렉토리 import
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from .config import BIBLE_BOOKS


# ============================================================
# 썸네일 설정
# ============================================================

# 썸네일 크기 (YouTube 권장)
THUMBNAIL_WIDTH = 1280
THUMBNAIL_HEIGHT = 720

# 구약/신약 색상 테마
TESTAMENT_THEMES = {
    "구약": {
        "color_scheme": "deep blue and gold",
        "atmosphere": "ancient scrolls, Hebrew scriptures, starry night sky",
        "accent": "gold accents, ancient temple",
    },
    "신약": {
        "color_scheme": "warm crimson and white",
        "atmosphere": "sunrise, cross silhouette, peaceful light",
        "accent": "dove, olive branch, gentle rays",
    }
}


def get_testament(book_name: str) -> str:
    """책 이름으로 구약/신약 구분"""
    for book in BIBLE_BOOKS:
        if book["name"] == book_name:
            return book["testament"]
    return "구약"  # 기본값


def generate_episode_thumbnail(
    episode,
    output_dir: Optional[str] = None,
    force_regenerate: bool = False,
    use_gemini: bool = True
) -> Dict[str, Any]:
    """
    에피소드 썸네일 생성 (Gemini 3 Pro)

    Args:
        episode: Episode 객체
        output_dir: 저장 디렉토리 (기본: static/images/bible_thumbnails)
        force_regenerate: True면 기존 이미지 재생성
        use_gemini: True면 Gemini 3 Pro 사용, False면 PIL 폴백

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

    # 텍스트 준비
    title_text = f"100일 성경통독 Day {episode.day_number}"
    range_text = episode.range_text

    # 구약/신약 테마
    testament = get_testament(episode.book)
    theme = TESTAMENT_THEMES.get(testament, TESTAMENT_THEMES["구약"])

    if use_gemini:
        result = _generate_with_gemini(
            title_text=title_text,
            range_text=range_text,
            theme=theme,
            testament=testament,
            filepath=filepath,
            day_number=episode.day_number
        )
        if result.get("ok"):
            return result
        # Gemini 실패 시 PIL 폴백
        print(f"[THUMB] Gemini 실패, PIL 폴백: {result.get('error')}")

    # PIL 폴백
    return _generate_with_pil(episode, filepath, filename)


def _generate_with_gemini(
    title_text: str,
    range_text: str,
    theme: dict,
    testament: str,
    filepath: str,
    day_number: int
) -> Dict[str, Any]:
    """Gemini 3 Pro로 썸네일 생성"""
    try:
        # drama_server의 generate_image_base64 함수 import
        from drama_server import generate_image_base64, GEMINI_PRO

        # 프롬프트 구성
        prompt = f"""Create a YouTube thumbnail image for a Korean Bible reading channel.

REQUIRED TEXT (MUST appear clearly, large and readable):
- Main title: "{title_text}" (WHITE text with BLACK outline, top area)
- Subtitle: "{range_text}" (WHITE text with BLACK outline, center-bottom)

VISUAL STYLE:
- Color scheme: {theme['color_scheme']}
- Atmosphere: {theme['atmosphere']}
- Accents: {theme['accent']}
- {'Old Testament' if testament == '구약' else 'New Testament'} theme

LAYOUT:
- 16:9 landscape aspect ratio
- Text on LEFT side (30-40% of width)
- Religious/spiritual imagery on RIGHT side
- Clean, modern Korean church aesthetic
- NO photorealistic style - use illustration/webtoon style

CRITICAL:
- Text MUST be in Korean as shown above
- Text MUST be clearly readable with thick outlines
- Colors should be {theme['color_scheme']} themed
"""

        print(f"[THUMB] Gemini 3 Pro 생성 중: Day {day_number}")

        result = generate_image_base64(prompt=prompt, model=GEMINI_PRO)

        if not result.get("ok"):
            return {"ok": False, "error": result.get("error", "Gemini 이미지 생성 실패")}

        # base64 데이터 저장
        base64_data = result.get("base64")
        if not base64_data:
            return {"ok": False, "error": "base64 데이터 없음"}

        image_data = base64.b64decode(base64_data)

        with open(filepath, 'wb') as f:
            f.write(image_data)

        print(f"[THUMB] Gemini 3 Pro 썸네일 생성 완료: {filepath}")

        return {
            "ok": True,
            "image_path": filepath,
            "image_url": f"/static/images/bible_thumbnails/day_{day_number:03d}.jpg",
            "cached": False,
            "method": "gemini"
        }

    except ImportError as e:
        return {"ok": False, "error": f"drama_server import 실패: {e}"}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def _generate_with_pil(episode, filepath: str, filename: str) -> Dict[str, Any]:
    """PIL로 썸네일 생성 (폴백)"""
    try:
        from PIL import Image, ImageDraw, ImageFont
        from .background import get_background_path, generate_book_background

        # 배경 이미지
        background_path = get_background_path(episode.book)
        if not background_path:
            result = generate_book_background(episode.book)
            if result.get("ok"):
                background_path = result.get("image_path")

        # 배경 로드
        if background_path and os.path.exists(background_path):
            bg_image = Image.open(background_path)
            bg_image = bg_image.resize((THUMBNAIL_WIDTH, THUMBNAIL_HEIGHT), Image.Resampling.LANCZOS)
            bg_image = bg_image.convert('RGB')
        else:
            bg_image = _create_gradient_background(get_testament(episode.book))

        draw = ImageDraw.Draw(bg_image)

        # 폰트
        title_font = _get_font(60)
        range_font = _get_font(80)

        # 텍스트
        title_text = f"100일 성경통독 Day {episode.day_number}"
        range_text = episode.range_text

        # 중앙 정렬
        title_bbox = draw.textbbox((0, 0), title_text, font=title_font)
        title_x = (THUMBNAIL_WIDTH - (title_bbox[2] - title_bbox[0])) // 2
        title_y = 80

        range_bbox = draw.textbbox((0, 0), range_text, font=range_font)
        range_x = (THUMBNAIL_WIDTH - (range_bbox[2] - range_bbox[0])) // 2
        range_y = (THUMBNAIL_HEIGHT - (range_bbox[3] - range_bbox[1])) // 2

        # 그림자 + 텍스트
        _draw_text_with_shadow(draw, (title_x, title_y), title_text, title_font, (255, 255, 255))
        _draw_text_with_shadow(draw, (range_x, range_y), range_text, range_font, (255, 255, 255))

        bg_image.save(filepath, 'JPEG', quality=90)
        print(f"[THUMB] PIL 썸네일 생성 완료: {filepath}")

        return {
            "ok": True,
            "image_path": filepath,
            "image_url": f"/static/images/bible_thumbnails/{filename}",
            "cached": False,
            "method": "pil"
        }

    except Exception as e:
        return {"ok": False, "error": f"PIL 폴백 실패: {e}"}


def _get_font(size: int):
    """폰트 로드"""
    from PIL import ImageFont

    font_paths = [
        '/usr/share/fonts/truetype/nanum/NanumSquareRoundB.ttf',
        '/usr/share/fonts/truetype/nanum/NanumGothicBold.ttf',
        '/usr/share/fonts/truetype/nanum/NanumBarunGothicBold.ttf',
    ]

    for font_path in font_paths:
        if os.path.exists(font_path):
            try:
                return ImageFont.truetype(font_path, size)
            except:
                continue

    return ImageFont.load_default()


def _draw_text_with_shadow(draw, position, text, font, fill, shadow_color=(0, 0, 0), offset=3):
    """그림자 텍스트"""
    x, y = position
    for dx in [-offset, offset]:
        for dy in [-offset, offset]:
            draw.text((x + dx, y + dy), text, font=font, fill=shadow_color)
    draw.text(position, text, font=font, fill=fill)


def _create_gradient_background(testament: str = "구약"):
    """그라데이션 배경 생성"""
    from PIL import Image

    img = Image.new('RGB', (THUMBNAIL_WIDTH, THUMBNAIL_HEIGHT))

    if testament == "신약":
        # 붉은색 계열
        start_color = (80, 30, 40)
        end_color = (40, 20, 60)
    else:
        # 파란색 계열
        start_color = (26, 35, 126)
        end_color = (16, 33, 62)

    for y in range(THUMBNAIL_HEIGHT):
        ratio = y / THUMBNAIL_HEIGHT
        r = int(start_color[0] + (end_color[0] - start_color[0]) * ratio)
        g = int(start_color[1] + (end_color[1] - start_color[1]) * ratio)
        b = int(start_color[2] + (end_color[2] - start_color[2]) * ratio)
        for x in range(THUMBNAIL_WIDTH):
            img.putpixel((x, y), (r, g, b))

    return img


def generate_all_thumbnails(
    episodes: list,
    force_regenerate: bool = False,
    use_gemini: bool = True
) -> Dict[str, Any]:
    """
    모든 에피소드 썸네일 생성

    Args:
        episodes: Episode 객체 목록
        force_regenerate: True면 모두 재생성
        use_gemini: True면 Gemini 3 Pro 사용

    Returns:
        {"ok": True, "generated": int, "cached": int, "failed": int}
    """
    generated = 0
    cached = 0
    failed = 0

    print(f"[THUMB] 총 {len(episodes)}개 썸네일 생성 시작 (Gemini: {use_gemini})...")

    for i, episode in enumerate(episodes, 1):
        print(f"[THUMB] [{i}/{len(episodes)}] Day {episode.day_number}")

        result = generate_episode_thumbnail(
            episode,
            force_regenerate=force_regenerate,
            use_gemini=use_gemini
        )

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
    parser.add_argument("--pil", action="store_true", help="PIL만 사용 (Gemini 비활성화)")

    args = parser.parse_args()

    pipeline = BiblePipeline()
    use_gemini = not args.pil

    if args.day:
        episode = pipeline.get_episode_by_day(args.day)
        if episode:
            result = generate_episode_thumbnail(
                episode,
                force_regenerate=args.force,
                use_gemini=use_gemini
            )
            print(result)
        else:
            print(f"Day {args.day} 에피소드를 찾을 수 없습니다.")

    elif args.all:
        episodes = pipeline.generate_all_bible_episodes()
        result = generate_all_thumbnails(
            episodes,
            force_regenerate=args.force,
            use_gemini=use_gemini
        )

    elif args.range:
        start, end = map(int, args.range.split('-'))
        episodes = pipeline.generate_all_bible_episodes()
        selected = [ep for ep in episodes if start <= ep.day_number <= end]
        result = generate_all_thumbnails(
            selected,
            force_regenerate=args.force,
            use_gemini=use_gemini
        )

    else:
        # 테스트: Day 1, 50, 106 생성
        print("테스트 모드: Day 1, 50, 106 생성")
        episodes = pipeline.generate_all_bible_episodes()
        for day in [1, 50, 106]:
            ep = next((e for e in episodes if e.day_number == day), None)
            if ep:
                result = generate_episode_thumbnail(
                    ep,
                    force_regenerate=args.force,
                    use_gemini=use_gemini
                )
                print(f"Day {day}: {result}")
