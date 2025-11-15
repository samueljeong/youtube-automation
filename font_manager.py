"""
폰트 관리 시스템

다양한 한글 폰트를 관리하고 선택합니다.
"""

import os
from typing import Optional, Dict


class FontManager:
    """폰트 관리"""

    # 사용 가능한 폰트 목록
    FONTS = {
        "sans_regular": {
            "name": "고딕체 (보통)",
            "filename": "NotoSansKR-Regular.ttf",
            "style": "modern",
            "weight": "regular",
        },
        "sans_bold": {
            "name": "고딕체 (굵게)",
            "filename": "NotoSansKR-Bold.otf",
            "style": "modern",
            "weight": "bold",
        },
        "serif_regular": {
            "name": "명조체 (보통)",
            "filename": "NotoSerifKR-Regular.ttf",
            "style": "classic",
            "weight": "regular",
        },
    }

    # 스타일별 폰트 조합
    FONT_STYLES = {
        "modern": {
            "title": "sans_bold",
            "message": "sans_regular",
            "ref": "sans_regular",
        },
        "classic": {
            "title": "serif_regular",
            "message": "serif_regular",
            "ref": "sans_regular",
        },
        "mixed": {
            "title": "sans_bold",
            "message": "serif_regular",
            "ref": "sans_regular",
        },
    }

    def __init__(self):
        self.fonts_dir = os.path.join(os.path.dirname(__file__), "fonts")

    def get_font_path(self, font_key: str) -> Optional[str]:
        """
        폰트 경로 가져오기

        Args:
            font_key: 폰트 키 (sans_regular, sans_bold, serif_regular)

        Returns:
            폰트 파일 경로 또는 None
        """
        if font_key not in self.FONTS:
            return None

        font_info = self.FONTS[font_key]
        font_path = os.path.join(self.fonts_dir, font_info["filename"])

        if os.path.exists(font_path):
            return font_path
        else:
            print(f"[FontManager] Font not found: {font_path}")
            return None

    def get_font_style(self, style_name: str = "modern") -> Dict:
        """
        스타일에 맞는 폰트 조합 가져오기

        Args:
            style_name: 스타일 (modern, classic, mixed)

        Returns:
            폰트 경로 딕셔너리
        """
        if style_name not in self.FONT_STYLES:
            style_name = "modern"

        style = self.FONT_STYLES[style_name]

        return {
            "title": self.get_font_path(style["title"]),
            "message": self.get_font_path(style["message"]),
            "ref": self.get_font_path(style["ref"]),
        }

    def get_random_style(self) -> str:
        """랜덤 폰트 스타일 이름 반환"""
        import random
        return random.choice(list(self.FONT_STYLES.keys()))

    @classmethod
    def list_fonts(cls):
        """사용 가능한 폰트 목록 출력"""
        print("\n사용 가능한 폰트:")
        for key, font in cls.FONTS.items():
            print(f"  - {key}: {font['name']}")
            print(f"    파일: {font['filename']}")
            print(f"    스타일: {font['style']}, 굵기: {font['weight']}")

    @classmethod
    def list_styles(cls):
        """사용 가능한 폰트 스타일 목록 출력"""
        print("\n사용 가능한 폰트 스타일:")
        for key, style in cls.FONT_STYLES.items():
            print(f"  - {key}:")
            print(f"    제목: {cls.FONTS[style['title']]['name']}")
            print(f"    본문: {cls.FONTS[style['message']]['name']}")
            print(f"    참조: {cls.FONTS[style['ref']]['name']}")


# 테스트용 코드
if __name__ == "__main__":
    manager = FontManager()

    # 폰트 목록
    FontManager.list_fonts()

    # 스타일 목록
    FontManager.list_styles()

    # 랜덤 스타일
    print(f"\n랜덤 스타일: {manager.get_random_style()}")

    # 스타일별 폰트 경로
    for style_name in FontManager.FONT_STYLES.keys():
        print(f"\n{style_name} 스타일 폰트:")
        fonts = manager.get_font_style(style_name)
        for key, path in fonts.items():
            if path:
                print(f"  {key}: {os.path.basename(path)}")
            else:
                print(f"  {key}: 없음")
