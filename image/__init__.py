"""
이미지 생성 모듈
Gemini API를 사용한 씬 이미지 및 썸네일 생성

핵심 기능:
- Gemini 2.5 Flash를 통한 이미지 생성
- 16:9 비율 자동 크롭/리사이즈
- Base64 → 파일 저장 및 압축
"""

from .gemini import generate_image, generate_thumbnail_image

__all__ = [
    "generate_image",
    "generate_thumbnail_image",
]
