"""
Channel Router for Step 5
카테고리 기반 YouTube 채널 라우팅
"""

from typing import Optional


# 카테고리별 채널 ID 매핑
# TODO: 실제 채널 ID로 교체 필요
CATEGORY_CHANNEL_MAP = {
    "category1": "CHANNEL_ID_PLACEHOLDER_NOSTALGIA",   # 향수 콘텐츠 채널
    "category2": "CHANNEL_ID_PLACEHOLDER_QUOTES",      # 명언 라디오 채널
}

# 기본 채널 (매핑에 없는 경우 사용)
DEFAULT_CHANNEL_ID = "CHANNEL_ID_PLACEHOLDER_DEFAULT"


def get_channel_id(category: str, fallback_to_default: bool = True) -> str:
    """
    카테고리 값을 기반으로 업로드할 YouTube 채널 ID를 반환

    Args:
        category: 콘텐츠 카테고리 (예: "category1", "category2")
        fallback_to_default: 매핑에 없을 때 기본 채널 사용 여부

    Returns:
        YouTube 채널 ID

    Raises:
        ValueError: fallback_to_default=False이고 매핑에 없는 경우
    """
    channel_id = CATEGORY_CHANNEL_MAP.get(category)

    if channel_id:
        return channel_id

    if fallback_to_default:
        print(f"[ROUTER] Category '{category}' not found, using default channel")
        return DEFAULT_CHANNEL_ID

    raise ValueError(f"Unknown category: {category}. Available: {list(CATEGORY_CHANNEL_MAP.keys())}")


def get_channel_name(category: str) -> str:
    """
    카테고리에 해당하는 채널 이름 반환 (로깅/디버그용)

    Args:
        category: 콘텐츠 카테고리

    Returns:
        채널 이름 문자열
    """
    channel_names = {
        "category1": "향수 콘텐츠 채널",
        "category2": "명언 라디오 채널",
    }
    return channel_names.get(category, "기본 채널")


def list_available_channels() -> dict:
    """
    사용 가능한 모든 채널 목록 반환

    Returns:
        카테고리-채널ID 매핑 딕셔너리
    """
    return CATEGORY_CHANNEL_MAP.copy()


if __name__ == "__main__":
    # 테스트
    print("=== Channel Router Test ===")
    print(f"category1 -> {get_channel_id('category1')}")
    print(f"category2 -> {get_channel_id('category2')}")
    print(f"unknown -> {get_channel_id('unknown')}")
    print(f"\nAvailable channels: {list_available_channels()}")
