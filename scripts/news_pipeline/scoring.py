"""
후보 점수화 및 선정
"""

from datetime import datetime, timezone, timedelta

from .rss import deduplicate_items
from .utils import (
    get_kst_now,
    get_weekday_angle,
    guess_category,
    calculate_relevance_score,
    calculate_recency_score,
    passes_channel_filter,
)


def score_and_select_candidates(items: list, channel: str, top_k: int = 5) -> list:
    """
    채널별 점수화 + TOP K 후보 선정 (규칙 기반)

    Args:
        items: 기사 리스트
        channel: 채널 키 (ECON, POLICY, SOCIETY, WORLD)
        top_k: 선정할 후보 수

    Returns:
        CANDIDATES 시트용 행 데이터 리스트
    """
    now = get_kst_now()
    run_id = now.strftime("%Y-%m-%d")
    weekday_angle = get_weekday_angle()

    # 중복 제거
    unique_items = deduplicate_items(items)

    # 채널 필터링 + 점수화
    scored = []
    filtered_count = 0

    for item in unique_items:
        if not passes_channel_filter(item["title"], item["summary"], channel):
            filtered_count += 1
            continue

        category = guess_category(item["title"], item["summary"])
        relevance = calculate_relevance_score(item["title"], item["summary"], channel)
        recency = calculate_recency_score(item["published_at"], now)
        total = relevance * 2 + recency

        scored.append({
            "total": total,
            "relevance": relevance,
            "recency": recency,
            "category": category,
            "item": item,
        })

    print(f"[NEWS] 채널 필터({channel}): {filtered_count}개 제외, {len(scored)}개 통과")

    # 점수순 정렬
    scored.sort(key=lambda x: x["total"], reverse=True)
    top = scored[:top_k]

    # CANDIDATES 행 생성
    candidate_rows = []
    for rank, s in enumerate(top, start=1):
        item = s["item"]
        angle = f"내 돈·내 생활에 어떤 영향인가? ({weekday_angle})"
        why = f"관련도({s['relevance']})/신선도({s['recency']}) 기반 상위 후보. '{s['category']}'로 분류."

        candidate_rows.append([
            run_id,
            rank,
            s["category"],
            angle,
            s["total"],
            s["recency"],
            s["relevance"],
            "",  # score_uniqueness (MVP 미사용)
            item["title"],
            item["link"],
            item["published_at"],
            why,
        ])

    print(f"[NEWS] TOP {len(candidate_rows)} 후보 선정 완료 (채널: {channel})")
    return candidate_rows
