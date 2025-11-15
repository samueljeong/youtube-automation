"""
쇼츠 영상 제작 모듈
묵상 메시지를 세로형 쇼츠 영상으로 변환합니다.
"""

import os
from typing import Optional
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance
import textwrap


class ShortsMaker:
    """묵상 쇼츠 비디오 제작"""

    def __init__(self, width: int = 1080, height: int = 1920):
        """
        Args:
            width: 비디오 너비 (기본: 1080)
            height: 비디오 높이 (기본: 1920, 세로형)
        """
        self.width = width
        self.height = height

        # 한글 폰트 경로 (시스템에 따라 다름)
        self.font_paths = [
            "/usr/share/fonts/truetype/nanum/NotoSansKR.ttf",  # Google Noto Sans KR
            "/usr/share/fonts/truetype/nanum/NanumGothic.ttf",  # Ubuntu/Debian
            "/usr/share/fonts/nanum/NanumGothic.ttf",
            "/System/Library/Fonts/AppleSDGothicNeo.ttc",  # macOS
            "C:/Windows/Fonts/malgun.ttf",  # Windows
            "/usr/share/fonts/truetype/nanum/NanumBarunGothic.ttf",
        ]

        self.font_path = self._find_korean_font()

    def _find_korean_font(self) -> Optional[str]:
        """시스템에서 한글 폰트 찾기"""
        for path in self.font_paths:
            if os.path.exists(path):
                print(f"[ShortsMaker] Found Korean font: {path}")
                return path

        print("[ShortsMaker] Warning: Korean font not found, using default")
        return None

    def create_devotional_image(
        self,
        background_image_path: str,
        message: str,
        output_path: str,
        bible_ref: str = None
    ) -> Optional[str]:
        """
        묵상 메시지 이미지 생성 (정적 이미지)

        Args:
            background_image_path: 배경 이미지 경로
            message: 묵상 메시지 텍스트
            output_path: 저장할 파일 경로
            bible_ref: 성경 구절 (선택)

        Returns:
            저장된 파일 경로 또는 None
        """
        try:
            # 배경 이미지 로드 및 크기 조정
            bg = Image.open(background_image_path)
            bg = bg.convert('RGB')

            # 세로형으로 크롭/리사이즈
            bg = self._resize_and_crop(bg, self.width, self.height)

            # 어두운 오버레이 추가 (가독성 향상)
            overlay = Image.new('RGBA', bg.size, (0, 0, 0, 120))  # 반투명 검정
            bg = bg.convert('RGBA')
            bg = Image.alpha_composite(bg, overlay)
            bg = bg.convert('RGB')

            # Draw 객체 생성
            draw = ImageDraw.Draw(bg)

            # 폰트 설정
            title_font_size = 80
            message_font_size = 60
            ref_font_size = 45

            if self.font_path:
                try:
                    title_font = ImageFont.truetype(self.font_path, title_font_size)
                    message_font = ImageFont.truetype(self.font_path, message_font_size)
                    ref_font = ImageFont.truetype(self.font_path, ref_font_size)
                except Exception as e:
                    print(f"[ShortsMaker] Font loading error, using default: {e}")
                    # 기본 폰트 (한글 지원 안 될 수 있음)
                    title_font = ImageFont.load_default()
                    message_font = ImageFont.load_default()
                    ref_font = ImageFont.load_default()
            else:
                # 기본 폰트 (한글 지원 안 될 수 있음)
                title_font = ImageFont.load_default()
                message_font = ImageFont.load_default()
                ref_font = ImageFont.load_default()

            # 제목 추가 (상단)
            title = "오늘의 묵상"
            title_bbox = draw.textbbox((0, 0), title, font=title_font)
            title_width = title_bbox[2] - title_bbox[0]
            title_x = (self.width - title_width) // 2
            title_y = 150

            draw.text(
                (title_x, title_y),
                title,
                font=title_font,
                fill=(255, 255, 255),
                stroke_width=2,
                stroke_fill=(0, 0, 0)
            )

            # 메시지 텍스트 줄바꿈 (중앙)
            wrapped_lines = self._wrap_korean_text(message, max_width=20)

            # 텍스트 높이 계산
            line_height = message_font_size + 20
            total_text_height = len(wrapped_lines) * line_height
            start_y = (self.height - total_text_height) // 2

            # 각 줄 그리기
            for i, line in enumerate(wrapped_lines):
                # 텍스트 크기 측정
                bbox = draw.textbbox((0, 0), line, font=message_font)
                text_width = bbox[2] - bbox[0]

                # 중앙 정렬
                x = (self.width - text_width) // 2
                y = start_y + (i * line_height)

                # 그림자 효과
                draw.text(
                    (x + 3, y + 3),
                    line,
                    font=message_font,
                    fill=(0, 0, 0, 180)
                )

                # 메인 텍스트
                draw.text(
                    (x, y),
                    line,
                    font=message_font,
                    fill=(255, 255, 255)
                )

            # 성경 구절 (하단)
            if bible_ref:
                ref_bbox = draw.textbbox((0, 0), bible_ref, font=ref_font)
                ref_width = ref_bbox[2] - ref_bbox[0]
                ref_x = (self.width - ref_width) // 2
                ref_y = self.height - 200

                draw.text(
                    (ref_x, ref_y),
                    bible_ref,
                    font=ref_font,
                    fill=(255, 255, 200),
                    stroke_width=1,
                    stroke_fill=(0, 0, 0)
                )

            # 파일 저장
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            bg.save(output_path, quality=95)

            print(f"[ShortsMaker] Image created: {output_path}")
            return output_path

        except Exception as e:
            print(f"[ShortsMaker] Error creating image: {e}")
            import traceback
            traceback.print_exc()
            return None

    def create_devotional_video(
        self,
        background_image_path: str,
        message: str,
        output_path: str,
        bible_ref: str = None,
        duration: int = 10
    ) -> Optional[str]:
        """
        묵상 메시지 비디오 생성 (MoviePy 사용)

        Args:
            background_image_path: 배경 이미지 경로
            message: 묵상 메시지
            output_path: 저장할 비디오 경로
            bible_ref: 성경 구절
            duration: 비디오 길이 (초)

        Returns:
            저장된 파일 경로 또는 None
        """
        try:
            from moviepy.editor import (
                ImageClip,
                TextClip,
                CompositeVideoClip,
                concatenate_videoclips
            )
            from moviepy.video.fx.all import fadein, fadeout

            # 임시 이미지 생성
            temp_image = output_path.replace('.mp4', '_temp.jpg')
            self.create_devotional_image(
                background_image_path,
                message,
                temp_image,
                bible_ref
            )

            if not os.path.exists(temp_image):
                print("[ShortsMaker] Failed to create temp image")
                return None

            # 이미지 클립 생성
            clip = ImageClip(temp_image, duration=duration)

            # 페이드 효과
            clip = clip.fx(fadein, 1).fx(fadeout, 1)

            # 비디오 저장
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            clip.write_videofile(
                output_path,
                fps=24,
                codec='libx264',
                audio=False,
                preset='medium',
                logger=None  # 진행 로그 숨기기
            )

            # 임시 파일 삭제
            if os.path.exists(temp_image):
                os.remove(temp_image)

            print(f"[ShortsMaker] Video created: {output_path}")
            return output_path

        except Exception as e:
            print(f"[ShortsMaker] Error creating video: {e}")
            import traceback
            traceback.print_exc()
            return None

    def _resize_and_crop(self, img: Image.Image, target_width: int, target_height: int) -> Image.Image:
        """이미지를 타겟 크기에 맞게 크롭"""
        img_ratio = img.width / img.height
        target_ratio = target_width / target_height

        if img_ratio > target_ratio:
            # 이미지가 더 넓음 -> 높이 맞추고 좌우 크롭
            new_height = target_height
            new_width = int(new_height * img_ratio)
        else:
            # 이미지가 더 높음 -> 너비 맞추고 상하 크롭
            new_width = target_width
            new_height = int(new_width / img_ratio)

        img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)

        # 중앙 크롭
        left = (new_width - target_width) // 2
        top = (new_height - target_height) // 2
        right = left + target_width
        bottom = top + target_height

        return img.crop((left, top, right, bottom))

    def _wrap_korean_text(self, text: str, max_width: int = 20) -> list:
        """한글 텍스트 줄바꿈"""
        words = text.split()
        lines = []
        current_line = ""

        for word in words:
            test_line = current_line + " " + word if current_line else word

            if len(test_line) <= max_width:
                current_line = test_line
            else:
                if current_line:
                    lines.append(current_line)
                current_line = word

        if current_line:
            lines.append(current_line)

        return lines


# 테스트용 코드
if __name__ == "__main__":
    maker = ShortsMaker()

    # 테스트 메시지
    test_message = "주님의 은혜가 오늘도 우리와 함께 하시기를 기도합니다. 평안한 하루 되세요."
    test_ref = "시편 23:1"

    # 테스트용 배경 이미지가 있다면
    if os.path.exists("output/test_image.jpg"):
        print("Testing image creation...")
        result = maker.create_devotional_image(
            "output/test_image.jpg",
            test_message,
            "output/test_devotional.jpg",
            test_ref
        )
        if result:
            print(f"✅ Image success: {result}")

        print("\nTesting video creation...")
        result = maker.create_devotional_video(
            "output/test_image.jpg",
            test_message,
            "output/test_devotional.mp4",
            test_ref,
            duration=10
        )
        if result:
            print(f"✅ Video success: {result}")
    else:
        print("⚠️ Test image not found. Run image_fetcher.py first.")
