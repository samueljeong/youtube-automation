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


# 영상 길이별 이미지 개수 설정
# ~8분: 5컷, 8~10분: 8컷 (장면 전환 자주)
# 10~15분: 11컷, 15분+: 12컷 (10분 이후 장면 전환 느려짐)
IMAGE_COUNT_CONFIG = {
    "rules": {
        "~8min": 5,
        "8~10min": 8,
        "10~15min": 11,
        "15min+": 12,
    },
    "chars_per_minute": 150,  # 한국어 TTS 기준
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
        image_count = 5
    elif estimated_minutes <= 10:
        image_count = 8  # 10분 전까지는 장면 전환 자주
    elif estimated_minutes <= 15:
        image_count = 11  # 10분 이후부터는 장면 전환 느려짐
    else:
        image_count = 12  # 최대 12컷 고정

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
