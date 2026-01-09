#!/usr/bin/env python3
"""썸네일 텍스트 합성 테스트 (Google Fonts 다운로드 + PIL)"""

import os
import requests
from PIL import Image, ImageDraw, ImageFont

# 폰트 저장 디렉토리
FONT_DIR = "assets/fonts"

# 다운로드할 폰트 목록 (OFL 라이선스 - 상업용 무료)
FONTS = {
    # 제목용 - 굵고 임팩트 있음
    "black_han_sans": "https://github.com/google/fonts/raw/main/ofl/blackhansans/BlackHanSans-Regular.ttf",
    # 본문용 - 깔끔한 고딕 (Bold)
    "noto_sans_kr_bold": "https://github.com/google/fonts/raw/main/ofl/notosanskr/NotoSansKR-Bold.ttf",
    # 본문용 - 깔끔한 고딕 (Regular)
    "noto_sans_kr_regular": "https://github.com/google/fonts/raw/main/ofl/notosanskr/NotoSansKR-Regular.ttf",
}

def download_font(name: str, url: str) -> str:
    """폰트 다운로드"""
    os.makedirs(FONT_DIR, exist_ok=True)
    font_path = os.path.join(FONT_DIR, f"{name}.ttf")

    if os.path.exists(font_path):
        print(f"✅ {name}: 이미 존재")
        return font_path

    print(f"⬇️ {name} 다운로드 중...")
    try:
        response = requests.get(url, timeout=30)
        if response.status_code == 200:
            with open(font_path, "wb") as f:
                f.write(response.content)
            print(f"✅ {name}: 다운로드 완료")
            return font_path
        else:
            print(f"❌ {name}: HTTP {response.status_code}")
    except Exception as e:
        print(f"❌ {name}: {e}")

    return None


def add_text_to_thumbnail(
    image_path: str,
    output_path: str,
    series_name: str = "혈영 이세계편",
    episode: str = "제1화",
    subtitle: str = "이방인",
):
    """썸네일에 텍스트 추가"""

    # 이미지 로드
    img = Image.open(image_path)
    draw = ImageDraw.Draw(img)
    width, height = img.size

    # 폰트 로드
    font_path = os.path.join(FONT_DIR, "black_han_sans.ttf")
    if not os.path.exists(font_path):
        print("❌ 폰트 없음")
        return None

    # 폰트 크기 (이미지 크기에 비례) - 2배로 키움
    title_size = int(height * 0.08)       # 시리즈명 (왼쪽 상단)
    episode_size = int(height * 0.24)     # 제1화 (2배)
    subtitle_size = int(height * 0.12)    # 이방인 (2배)

    try:
        font_title = ImageFont.truetype(font_path, title_size)
        font_episode = ImageFont.truetype(font_path, episode_size)
        font_subtitle = ImageFont.truetype(font_path, subtitle_size)
    except Exception as e:
        print(f"❌ 폰트 로드 실패: {e}")
        return None

    margin = int(width * 0.05)

    def draw_text_with_shadow(text, font, x, y, shadow_offset=4):
        """그림자 효과가 있는 텍스트"""
        # 그림자
        draw.text((x + shadow_offset, y + shadow_offset), text, font=font, fill=(0, 0, 0, 200))
        # 본문
        draw.text((x, y), text, font=font, fill=(255, 255, 255, 255))

    # 시리즈명 - 왼쪽 상단 (구석 아니게)
    title_x = int(width * 0.08)
    title_y = int(height * 0.08)
    draw_text_with_shadow(series_name, font_title, title_x, title_y)

    # 제1화 - 우측 하단
    episode_bbox = draw.textbbox((0, 0), episode, font=font_episode)
    episode_w = episode_bbox[2] - episode_bbox[0]
    episode_h = episode_bbox[3] - episode_bbox[1]
    episode_x = width - episode_w - margin
    episode_y = height - episode_h - subtitle_size - int(height * 0.12)
    draw_text_with_shadow(episode, font_episode, episode_x, episode_y, shadow_offset=6)

    # 이방인 - 제1화 아래
    subtitle_bbox = draw.textbbox((0, 0), subtitle, font=font_subtitle)
    subtitle_w = subtitle_bbox[2] - subtitle_bbox[0]
    subtitle_x = width - subtitle_w - margin
    subtitle_y = episode_y + episode_h + int(height * 0.02)
    draw_text_with_shadow(subtitle, font_subtitle, subtitle_x, subtitle_y)

    # 저장
    img.save(output_path)
    print(f"✅ 썸네일 저장: {output_path}")
    return output_path


def main():
    print("=" * 50)
    print("썸네일 텍스트 합성 테스트")
    print("=" * 50)
    print()

    # 1. 폰트 다운로드
    print("[1] 폰트 다운로드")
    print("-" * 30)
    for name, url in FONTS.items():
        download_font(name, url)
    print()

    # 2. 기존 이미지에 텍스트 합성
    print("[2] 텍스트 합성")
    print("-" * 30)

    input_image = "outputs/isekai/images/test_ep001_thumbnail.png"
    output_image = "outputs/isekai/images/test_ep001_thumbnail_with_text.png"

    if os.path.exists(input_image):
        add_text_to_thumbnail(
            image_path=input_image,
            output_path=output_image,
            series_name="혈영 이세계편",
            episode="제1화",
            subtitle="이방인",
        )
    else:
        print(f"❌ 원본 이미지 없음: {input_image}")
        print("먼저 test_thumbnail.py를 실행하세요")


if __name__ == "__main__":
    main()
