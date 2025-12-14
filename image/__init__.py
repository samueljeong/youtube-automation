"""
이미지 생성 모듈
Gemini API를 사용한 씬 이미지 및 썸네일 생성

핵심 기능:
- Gemini 2.5 Flash: 씬 이미지 생성 (빠르고 저렴)
- Gemini 3 Pro: 썸네일 생성 (고품질)
- 16:9/9:16 비율 자동 크롭/리사이즈
- Base64 → 파일 저장 및 압축
"""

from .gemini import (
    generate_image,
    generate_image_base64,
    generate_thumbnail_image,
    GEMINI_FLASH,
    GEMINI_PRO,
)

__all__ = [
    "generate_image",
    "generate_image_base64",
    "generate_thumbnail_image",
    "GEMINI_FLASH",
    "GEMINI_PRO",
]
