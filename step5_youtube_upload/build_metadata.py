"""
Build Metadata for Step 5
YouTube 업로드용 메타데이터 생성
"""

from typing import Dict, Any, List


# 카테고리별 기본 태그
DEFAULT_TAGS_BY_CATEGORY = {
    "category1": ["향수", "추억", "옛날이야기", "시니어", "감성", "라디오", "힐링"],
    "category2": ["명언", "인생", "지혜", "동기부여", "시니어", "라디오", "마음"],
}

# YouTube 카테고리 ID (Entertainment = 24)
DEFAULT_YOUTUBE_CATEGORY_ID = "24"


def build_metadata(step5_input: Dict[str, Any]) -> Dict[str, Any]:
    """
    Step5 입력을 받아 YouTube 업로드용 메타데이터를 구성

    Args:
        step5_input: Step5 입력 JSON (step5_youtube_upload 포맷)

    Returns:
        YouTube API 업로드용 메타데이터 딕셔너리
    """
    title = step5_input.get("title", "제목 없음")
    description_seed = step5_input.get("description_seed", "")
    tags_seed = step5_input.get("tags_seed", [])
    category = step5_input.get("category", "category1")

    # 설명 생성
    description = _build_description(title, description_seed, category)

    # 태그 생성
    tags = _build_tags(tags_seed, category)

    return {
        "title": title,
        "description": description,
        "tags": tags,
        "categoryId": DEFAULT_YOUTUBE_CATEGORY_ID
    }


def _build_description(title: str, description_seed: str, category: str) -> str:
    """
    YouTube 영상 설명 생성

    Args:
        title: 영상 제목
        description_seed: 설명 시드 텍스트
        category: 콘텐츠 카테고리

    Returns:
        완성된 설명 문자열
    """
    # 카테고리별 채널 컨셉
    channel_concepts = {
        "category1": "어르신들의 추억과 삶의 이야기를 담은 향수 콘텐츠 채널입니다.",
        "category2": "인생의 지혜와 명언을 나누는 시니어 라디오 채널입니다.",
    }
    channel_concept = channel_concepts.get(category, "시니어를 위한 감성 콘텐츠 채널입니다.")

    # 설명 템플릿 구성
    description_parts = [
        f"📺 {title}",
        "",
        description_seed if description_seed else "오늘도 함께해 주셔서 감사합니다.",
        "",
        f"🏠 {channel_concept}",
        "",
        "❤️ 영상이 마음에 드셨다면 구독과 좋아요 부탁드립니다.",
        "🔔 알림 설정하시면 새 영상을 놓치지 않으실 수 있습니다.",
        "",
        "#시니어 #감성 #라디오 #힐링"
    ]

    return "\n".join(description_parts)


def _build_tags(tags_seed: List[str], category: str) -> List[str]:
    """
    YouTube 영상 태그 생성

    Args:
        tags_seed: 태그 시드 목록
        category: 콘텐츠 카테고리

    Returns:
        완성된 태그 리스트
    """
    # 기본 태그 가져오기
    default_tags = DEFAULT_TAGS_BY_CATEGORY.get(category, ["시니어", "라디오"])

    # 시드 태그 + 기본 태그 결합 (중복 제거)
    all_tags = list(tags_seed) + default_tags
    unique_tags = list(dict.fromkeys(all_tags))  # 순서 유지하면서 중복 제거

    # YouTube 태그 제한 (최대 500자, 개별 태그 최대 30자)
    final_tags = []
    total_length = 0
    for tag in unique_tags:
        tag = tag.strip()
        if len(tag) > 30:
            tag = tag[:30]
        if total_length + len(tag) + 1 <= 500:  # +1 for comma
            final_tags.append(tag)
            total_length += len(tag) + 1
        else:
            break

    return final_tags


if __name__ == "__main__":
    import json

    # 테스트
    test_input = {
        "step": "step5_youtube_upload",
        "category": "category1",
        "title": "그 시절, 우리 마을의 작은 구멍가게",
        "description_seed": "1970년대 시골 마을, 작은 구멍가게에서 피어난 따뜻한 이야기입니다.",
        "tags_seed": ["구멍가게", "70년대", "시골", "추억"],
        "video_filename": "output/video.mp4",
        "upload_mode": "scheduled"
    }

    metadata = build_metadata(test_input)
    print("=== Generated Metadata ===")
    print(json.dumps(metadata, ensure_ascii=False, indent=2))
