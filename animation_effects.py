"""
비디오 애니메이션 효과

텍스트와 이미지에 애니메이션 효과를 적용합니다.
"""

import numpy as np
from typing import Tuple


class AnimationEffects:
    """애니메이션 효과 클래스"""

    @staticmethod
    def fade_in(frame_num: int, total_frames: int, fade_duration: int = 30) -> float:
        """
        페이드 인 효과

        Args:
            frame_num: 현재 프레임 번호
            total_frames: 총 프레임 수
            fade_duration: 페이드 지속 프레임 수

        Returns:
            알파값 (0.0 ~ 1.0)
        """
        if frame_num < fade_duration:
            return frame_num / fade_duration
        return 1.0

    @staticmethod
    def fade_out(frame_num: int, total_frames: int, fade_duration: int = 30) -> float:
        """
        페이드 아웃 효과

        Args:
            frame_num: 현재 프레임 번호
            total_frames: 총 프레임 수
            fade_duration: 페이드 지속 프레임 수

        Returns:
            알파값 (0.0 ~ 1.0)
        """
        if frame_num > total_frames - fade_duration:
            return (total_frames - frame_num) / fade_duration
        return 1.0

    @staticmethod
    def fade_in_out(frame_num: int, total_frames: int, fade_duration: int = 30) -> float:
        """
        페이드 인/아웃 효과

        Args:
            frame_num: 현재 프레임 번호
            total_frames: 총 프레임 수
            fade_duration: 페이드 지속 프레임 수

        Returns:
            알파값 (0.0 ~ 1.0)
        """
        fade_in_val = AnimationEffects.fade_in(frame_num, total_frames, fade_duration)
        fade_out_val = AnimationEffects.fade_out(frame_num, total_frames, fade_duration)
        return min(fade_in_val, fade_out_val)

    @staticmethod
    def slide_from_bottom(frame_num: int, total_frames: int, height: int, slide_duration: int = 40) -> int:
        """
        아래에서 위로 슬라이드

        Args:
            frame_num: 현재 프레임 번호
            total_frames: 총 프레임 수
            height: 화면 높이
            slide_duration: 슬라이드 지속 프레임 수

        Returns:
            Y 오프셋
        """
        if frame_num < slide_duration:
            progress = frame_num / slide_duration
            # Ease-out 효과
            progress = 1 - (1 - progress) ** 3
            return int(height * (1 - progress))
        return 0

    @staticmethod
    def slide_from_top(frame_num: int, total_frames: int, height: int, slide_duration: int = 40) -> int:
        """
        위에서 아래로 슬라이드

        Args:
            frame_num: 현재 프레임 번호
            total_frames: 총 프레임 수
            height: 화면 높이
            slide_duration: 슬라이드 지속 프레임 수

        Returns:
            Y 오프셋
        """
        if frame_num < slide_duration:
            progress = frame_num / slide_duration
            progress = 1 - (1 - progress) ** 3
            return -int(height * (1 - progress))
        return 0

    @staticmethod
    def zoom_in(frame_num: int, total_frames: int, zoom_duration: int = 50) -> float:
        """
        확대 효과

        Args:
            frame_num: 현재 프레임 번호
            total_frames: 총 프레임 수
            zoom_duration: 확대 지속 프레임 수

        Returns:
            스케일 (1.0 ~ 1.2)
        """
        if frame_num < zoom_duration:
            progress = frame_num / zoom_duration
            return 1.0 + (0.2 * progress)
        return 1.2

    @staticmethod
    def pulse(frame_num: int, total_frames: int, pulse_speed: float = 0.1) -> float:
        """
        맥박 효과 (크기 변화)

        Args:
            frame_num: 현재 프레임 번호
            total_frames: 총 프레임 수
            pulse_speed: 맥박 속도

        Returns:
            스케일 (0.95 ~ 1.05)
        """
        import math
        return 1.0 + 0.05 * math.sin(frame_num * pulse_speed)

    @staticmethod
    def bounce_in(frame_num: int, total_frames: int, bounce_duration: int = 60) -> Tuple[float, int]:
        """
        바운스 인 효과

        Args:
            frame_num: 현재 프레임 번호
            total_frames: 총 프레임 수
            bounce_duration: 바운스 지속 프레임 수

        Returns:
            (스케일, Y 오프셋)
        """
        if frame_num < bounce_duration:
            import math
            progress = frame_num / bounce_duration
            # Bounce 이징
            if progress < 0.5:
                scale = progress * 2
                y_offset = -int(100 * (1 - progress * 2))
            else:
                scale = 1.0 + 0.1 * math.sin((progress - 0.5) * math.pi * 4)
                y_offset = 0
            return (scale, y_offset)
        return (1.0, 0)

    @staticmethod
    def apply_alpha_blend(img, alpha: float):
        """
        이미지에 알파 블렌딩 적용

        Args:
            img: numpy 배열 이미지
            alpha: 알파값 (0.0 ~ 1.0)

        Returns:
            알파 블렌딩된 이미지
        """
        return (img * alpha).astype(np.uint8)

    @staticmethod
    def get_animation_preset(preset_name: str = "fade"):
        """
        애니메이션 프리셋 가져오기

        Args:
            preset_name: 프리셋 이름 (fade, slide, zoom, pulse, bounce)

        Returns:
            애니메이션 함수 리스트
        """
        presets = {
            "fade": [AnimationEffects.fade_in_out],
            "slide_up": [AnimationEffects.slide_from_bottom, AnimationEffects.fade_in],
            "slide_down": [AnimationEffects.slide_from_top, AnimationEffects.fade_in],
            "zoom": [AnimationEffects.zoom_in, AnimationEffects.fade_in],
            "pulse": [AnimationEffects.pulse],
            "bounce": [AnimationEffects.bounce_in],
        }

        return presets.get(preset_name, presets["fade"])


# 테스트용 코드
if __name__ == "__main__":
    effects = AnimationEffects()

    # 페이드 인/아웃 테스트
    total_frames = 240  # 10초 @ 24fps
    fade_duration = 30  # 약 1.25초

    print("Frame 애니메이션 테스트:")
    for frame in [0, 10, 20, 30, 100, 210, 220, 230, 240]:
        alpha = effects.fade_in_out(frame, total_frames, fade_duration)
        print(f"  Frame {frame:3d}: Alpha = {alpha:.2f}")

    print("\n슬라이드 테스트:")
    for frame in [0, 10, 20, 30, 40, 50]:
        y_offset = effects.slide_from_bottom(frame, total_frames, 1920, 40)
        print(f"  Frame {frame:3d}: Y Offset = {y_offset}")

    print("\n✅ Animation effects ready!")
