"""
이미지 생성 모듈
Gemini API를 사용한 씬 이미지 및 썸네일 생성

핵심 기능:
- Gemini 3 Pro: 씬 이미지 및 썸네일 생성 (고품질)
- 16:9/9:16 비율 자동 크롭/리사이즈
- Base64 → 파일 저장 및 압축
- 영상 길이별 이미지 개수 자동 결정
"""

from .gemini import (
    generate_image,
    generate_image_base64,
    generate_thumbnail_image,
    GEMINI_FLASH,
    GEMINI_PRO,
)


# 영상 길이별 이미지 개수 설정 (2025-12-20 업데이트)
# 장면 전환을 더 자주 하여 시청자 이탈 방지
IMAGE_COUNT_CONFIG = {
    "rules": {
        "~8min": 10,
        "8~10min": 13,
        "10~15min": 14,
        "15~20min": 18,
        "20~25min": 20,
        "25~30min": 25,
    },
    "chars_per_minute": 910,  # 한국어 TTS 기준 (15분=13,650자, 20분=18,200자)
}


def get_image_count_by_script(script_length: int) -> tuple:
    """
    대본 길이에 따른 이미지 개수 결정

    Args:
        script_length: 대본 글자 수

    Returns:
        (이미지 개수, 예상 분량(분))
    """
    chars_per_min = IMAGE_COUNT_CONFIG["chars_per_minute"]
    estimated_minutes = script_length / chars_per_min

    if estimated_minutes <= 8:
        image_count = 10
    elif estimated_minutes <= 10:
        image_count = 13
    elif estimated_minutes <= 15:
        image_count = 14
    elif estimated_minutes <= 20:
        image_count = 18
    elif estimated_minutes <= 25:
        image_count = 20
    else:
        image_count = 25  # 25~30분

    return image_count, estimated_minutes


__all__ = [
    "generate_image",
    "generate_image_base64",
    "generate_thumbnail_image",
    "get_image_count_by_script",
    "IMAGE_COUNT_CONFIG",
    "GEMINI_FLASH",
    "GEMINI_PRO",
]
