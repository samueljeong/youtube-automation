"""
배경 이미지 라이브러리

다양한 배경 스타일을 생성합니다.
"""

import os
from PIL import Image, ImageDraw, ImageFilter
import random
from typing import Tuple, Optional


class BackgroundLibrary:
    """배경 이미지 생성 라이브러리"""

    def __init__(self):
        pass

    def create_gradient_background(
        self,
        width: int,
        height: int,
        color1: Tuple[int, int, int],
        color2: Tuple[int, int, int],
        direction: str = "vertical"
    ) -> Image.Image:
        """
        그라데이션 배경 생성

        Args:
            width: 너비
            height: 높이
            color1: 시작 색상
            color2: 끝 색상
            direction: 방향 (vertical, horizontal, diagonal)

        Returns:
            PIL Image
        """
        base = Image.new('RGB', (width, height), color1)
        top = Image.new('RGB', (width, height), color2)
        mask = Image.new('L', (width, height))

        if direction == "vertical":
            # 세로 그라데이션
            mask_data = []
            for y in range(height):
                mask_data.extend([int(255 * (y / height))] * width)
            mask.putdata(mask_data)
        elif direction == "horizontal":
            # 가로 그라데이션
            mask_data = []
            for y in range(height):
                for x in range(width):
                    mask_data.append(int(255 * (x / width)))
            mask.putdata(mask_data)
        elif direction == "diagonal":
            # 대각선 그라데이션
            mask_data = []
            for y in range(height):
                for x in range(width):
                    mask_data.append(int(255 * ((x + y) / (width + height))))
            mask.putdata(mask_data)

        base.paste(top, (0, 0), mask)
        return base

    def create_radial_gradient(
        self,
        width: int,
        height: int,
        center_color: Tuple[int, int, int],
        edge_color: Tuple[int, int, int]
    ) -> Image.Image:
        """
        방사형 그라데이션 배경 생성

        Args:
            width: 너비
            height: 높이
            center_color: 중앙 색상
            edge_color: 가장자리 색상

        Returns:
            PIL Image
        """
        base = Image.new('RGB', (width, height), edge_color)
        center = Image.new('RGB', (width, height), center_color)
        mask = Image.new('L', (width, height))

        cx, cy = width // 2, height // 2
        max_dist = ((width / 2) ** 2 + (height / 2) ** 2) ** 0.5

        mask_data = []
        for y in range(height):
            for x in range(width):
                dist = ((x - cx) ** 2 + (y - cy) ** 2) ** 0.5
                alpha = int(255 * (1 - min(dist / max_dist, 1)))
                mask_data.append(alpha)

        mask.putdata(mask_data)
        base.paste(center, (0, 0), mask)
        return base

    def create_striped_background(
        self,
        width: int,
        height: int,
        color1: Tuple[int, int, int],
        color2: Tuple[int, int, int],
        stripe_width: int = 100
    ) -> Image.Image:
        """
        줄무늬 배경 생성

        Args:
            width: 너비
            height: 높이
            color1: 첫 번째 색상
            color2: 두 번째 색상
            stripe_width: 줄 너비

        Returns:
            PIL Image
        """
        img = Image.new('RGB', (width, height), color1)
        draw = ImageDraw.Draw(img)

        for y in range(0, height, stripe_width * 2):
            draw.rectangle([(0, y), (width, y + stripe_width)], fill=color2)

        return img

    def create_solid_background(
        self,
        width: int,
        height: int,
        color: Tuple[int, int, int]
    ) -> Image.Image:
        """
        단색 배경 생성

        Args:
            width: 너비
            height: 높이
            color: 색상

        Returns:
            PIL Image
        """
        return Image.new('RGB', (width, height), color)

    def create_blurred_gradient(
        self,
        width: int,
        height: int,
        color1: Tuple[int, int, int],
        color2: Tuple[int, int, int],
        blur_radius: int = 50
    ) -> Image.Image:
        """
        블러 처리된 그라데이션 배경

        Args:
            width: 너비
            height: 높이
            color1: 첫 번째 색상
            color2: 두 번째 색상
            blur_radius: 블러 반경

        Returns:
            PIL Image
        """
        img = self.create_gradient_background(width, height, color1, color2)
        img = img.filter(ImageFilter.GaussianBlur(radius=blur_radius))
        return img

    def create_random_background(
        self,
        width: int,
        height: int,
        style: str = "gradient"
    ) -> Image.Image:
        """
        랜덤 배경 생성

        Args:
            width: 너비
            height: 높이
            style: 스타일 (gradient, radial, striped, solid, blurred)

        Returns:
            PIL Image
        """
        # 랜덤 색상
        colors = [
            ((50, 100, 150), (200, 150, 100)),   # 파란색 → 오렌지
            ((30, 30, 80), (100, 50, 100)),      # 어두운 파란색 → 보라색
            ((40, 80, 60), (150, 200, 150)),     # 녹색 → 연한 녹색
            ((100, 60, 40), (220, 150, 100)),    # 주황색 → 연한 주황색
            ((60, 60, 70), (140, 140, 150)),     # 회색 → 연한 회색
            ((80, 50, 90), (220, 150, 180)),     # 보라-핑크 → 연한 핑크
            ((20, 50, 80), (100, 150, 200)),     # 깊은 바다색 → 하늘색
            ((30, 60, 40), (120, 180, 140)),     # 숲색 → 연한 녹색
        ]

        color1, color2 = random.choice(colors)

        if style == "gradient":
            direction = random.choice(["vertical", "horizontal", "diagonal"])
            return self.create_gradient_background(width, height, color1, color2, direction)
        elif style == "radial":
            return self.create_radial_gradient(width, height, color1, color2)
        elif style == "striped":
            return self.create_striped_background(width, height, color1, color2)
        elif style == "solid":
            return self.create_solid_background(width, height, color1)
        elif style == "blurred":
            return self.create_blurred_gradient(width, height, color1, color2)
        else:
            return self.create_gradient_background(width, height, color1, color2)

    def save_background(
        self,
        img: Image.Image,
        output_path: str
    ) -> Optional[str]:
        """
        배경 이미지 저장

        Args:
            img: PIL Image
            output_path: 저장 경로

        Returns:
            저장된 파일 경로 또는 None
        """
        try:
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            img.save(output_path, quality=95)
            print(f"[BackgroundLibrary] Saved: {output_path}")
            return output_path
        except Exception as e:
            print(f"[BackgroundLibrary] Error saving: {e}")
            return None


# 테스트용 코드
if __name__ == "__main__":
    library = BackgroundLibrary()

    # 다양한 배경 스타일 테스트
    styles = ["gradient", "radial", "striped", "solid", "blurred"]

    for style in styles:
        print(f"Creating {style} background...")
        img = library.create_random_background(1080, 1920, style)
        library.save_background(img, f"output/backgrounds/test_{style}.jpg")

    print("\n✅ All backgrounds created!")
