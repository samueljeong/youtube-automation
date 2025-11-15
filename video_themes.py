"""
비디오 테마/스타일 정의

다양한 색상, 폰트, 레이아웃 스타일을 제공합니다.
"""

from typing import Dict, Tuple


class VideoThemes:
    """비디오 테마 컬렉션"""

    # 색상 테마 (배경 그라데이션)
    THEMES = {
        "morning_blue": {
            "name": "아침 파란색",
            "color1": (50, 100, 150),    # 진한 파란색
            "color2": (200, 150, 100),   # 따뜻한 오렌지
            "text_color": (255, 255, 255),
            "title_color": (255, 255, 255),
            "ref_color": (255, 255, 200),
        },
        "evening_purple": {
            "name": "저녁 보라색",
            "color1": (30, 30, 80),      # 어두운 파란색
            "color2": (100, 50, 100),    # 보라색
            "text_color": (255, 255, 255),
            "title_color": (255, 255, 255),
            "ref_color": (255, 200, 255),
        },
        "peaceful_green": {
            "name": "평화로운 녹색",
            "color1": (40, 80, 60),      # 진한 녹색
            "color2": (150, 200, 150),   # 연한 녹색
            "text_color": (255, 255, 255),
            "title_color": (255, 255, 255),
            "ref_color": (255, 255, 200),
        },
        "warm_orange": {
            "name": "따뜻한 주황색",
            "color1": (100, 60, 40),     # 진한 주황색
            "color2": (220, 150, 100),   # 연한 주황색
            "text_color": (255, 255, 255),
            "title_color": (255, 255, 255),
            "ref_color": (255, 255, 200),
        },
        "calm_grey": {
            "name": "차분한 회색",
            "color1": (60, 60, 70),      # 진한 회색
            "color2": (140, 140, 150),   # 연한 회색
            "text_color": (255, 255, 255),
            "title_color": (255, 255, 255),
            "ref_color": (255, 255, 200),
        },
        "sunset_pink": {
            "name": "석양 핑크",
            "color1": (80, 50, 90),      # 진한 보라-핑크
            "color2": (220, 150, 180),   # 연한 핑크
            "text_color": (255, 255, 255),
            "title_color": (255, 255, 255),
            "ref_color": (255, 255, 200),
        },
        "ocean_blue": {
            "name": "바다 파란색",
            "color1": (20, 50, 80),      # 깊은 바다색
            "color2": (100, 150, 200),   # 하늘색
            "text_color": (255, 255, 255),
            "title_color": (255, 255, 255),
            "ref_color": (200, 255, 255),
        },
        "forest_green": {
            "name": "숲 녹색",
            "color1": (30, 60, 40),      # 진한 숲색
            "color2": (120, 180, 140),   # 연한 녹색
            "text_color": (255, 255, 255),
            "title_color": (255, 255, 255),
            "ref_color": (255, 255, 200),
        },
    }

    # 레이아웃 스타일
    LAYOUTS = {
        "centered": {
            "name": "중앙 정렬",
            "title_y": 150,
            "message_align": "center",
            "ref_y_offset": -200,
        },
        "top": {
            "name": "상단 배치",
            "title_y": 100,
            "message_align": "center",
            "ref_y_offset": -150,
        },
        "bottom": {
            "name": "하단 배치",
            "title_y": 200,
            "message_align": "center",
            "ref_y_offset": -250,
        },
    }

    # 폰트 크기 프리셋
    FONT_SIZES = {
        "small": {
            "title": 60,
            "message": 45,
            "ref": 35,
        },
        "medium": {
            "title": 80,
            "message": 60,
            "ref": 45,
        },
        "large": {
            "title": 100,
            "message": 75,
            "ref": 55,
        },
    }

    @classmethod
    def get_theme(cls, theme_name: str) -> Dict:
        """테마 가져오기"""
        return cls.THEMES.get(theme_name, cls.THEMES["morning_blue"])

    @classmethod
    def get_layout(cls, layout_name: str) -> Dict:
        """레이아웃 가져오기"""
        return cls.LAYOUTS.get(layout_name, cls.LAYOUTS["centered"])

    @classmethod
    def get_font_sizes(cls, size_name: str) -> Dict:
        """폰트 크기 가져오기"""
        return cls.FONT_SIZES.get(size_name, cls.FONT_SIZES["medium"])

    @classmethod
    def get_random_theme(cls, time_of_day: str = None) -> str:
        """랜덤 테마 이름 반환"""
        import random

        if time_of_day == "morning":
            morning_themes = ["morning_blue", "peaceful_green", "warm_orange", "ocean_blue"]
            return random.choice(morning_themes)
        elif time_of_day == "evening":
            evening_themes = ["evening_purple", "calm_grey", "sunset_pink", "forest_green"]
            return random.choice(evening_themes)
        else:
            return random.choice(list(cls.THEMES.keys()))

    @classmethod
    def list_themes(cls):
        """사용 가능한 테마 목록 출력"""
        print("\n사용 가능한 테마:")
        for key, theme in cls.THEMES.items():
            print(f"  - {key}: {theme['name']}")
            print(f"    색상: {theme['color1']} → {theme['color2']}")


# 테스트용 코드
if __name__ == "__main__":
    VideoThemes.list_themes()

    print("\n랜덤 아침 테마:")
    print(VideoThemes.get_random_theme("morning"))

    print("\n랜덤 저녁 테마:")
    print(VideoThemes.get_random_theme("evening"))
