"""
후보 점수화 및 선정 모듈
"""

from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any

from .config import (
    DEFAULT_TOP_K,
    get_era_sheet_name,
)
from .utils import (
    get_run_id,
    get_era_display_name,
    calculate_relevance_score,
    calculate_quality_score,
    calculate_freshness_score,
    guess_topic,
    get_source_weight,
)
from .collector import deduplicate_items


def score_and_select_candidates(
    items: List[Dict[str, Any]],
    era: str,
    top_k: int = DEFAULT_TOP_K
) -> List[List[Any]]:
    """
    점수화 + TOP K 후보 선정 (규칙 기반, LLM 사용 안함)

    Args:
        items: 수집된 자료 리스트
        era: 시대 키
        top_k: 선정할 후보 수

    Returns:
        CANDIDATES 시트용 행 데이터 리스트
    """
    now = datetime.now(timezone.utc)
    run_id = get_run_id()
    era_name = get_era_display_name(era)

    # 중복 제거
    unique_items = deduplicate_items(items)
    print(f"[HISTORY] 중복 제거 후: {len(unique_items)}개")

    # 점수화
    scored = []

    for item in unique_items:
        title = item.get("title", "")
        content = item.get("content", "")
        source_type = item.get("source_type", "long_form")
        collected_at = item.get("collected_at", now.isoformat())

        # 관련도 점수
        relevance = calculate_relevance_score(title, content, era)

        # 자료 품질 점수
        quality = calculate_quality_score(source_type)

        # 신선도 점수
        freshness = calculate_freshness_score(collected_at, now)

        # 출처 가중치 적용
        source_weight = get_source_weight(source_type)

        # 총점 계산 (관련도 x2 + 품질 x1.5 + 신선도 x1) x 출처가중치
        total = (relevance * 2 + quality * 1.5 + freshness) * source_weight

        # 주제 분류
        topic = guess_topic(title, content, era)

        scored.append({
            "total": round(total, 2),
            "relevance": relevance,
            "quality": quality,
            "freshness": freshness,
            "topic": topic,
            "item": item,
        })

    # 점수순 정렬
    scored.sort(key=lambda x: x["total"], reverse=True)
    top = scored[:top_k]

    # CANDIDATES 행 생성
    candidate_rows = []

    for rank, s in enumerate(top, start=1):
        item = s["item"]

        why = _generate_why_selected(s, era_name)

        candidate_rows.append([
            run_id,                          # run_id
            rank,                            # rank
            era,                             # era
            s["topic"],                      # topic
            s["total"],                      # score_total
            s["relevance"],                  # score_relevance
            s["quality"],                    # score_quality
            s["freshness"],                  # score_freshness
            item.get("title", "")[:200],     # title
            item.get("url", ""),             # url
            item.get("content", "")[:300],   # summary
            why,                             # why_selected
        ])

    print(f"[HISTORY] TOP {len(candidate_rows)} 후보 선정 완료")
    return candidate_rows


def _generate_why_selected(scored_item: Dict, era_name: str) -> str:
    """선정 근거 문장 생성"""
    topic = scored_item["topic"]
    relevance = scored_item["relevance"]
    quality = scored_item["quality"]
    freshness = scored_item["freshness"]
    source_type = scored_item["item"].get("source_type", "")

    source_name = {
        "university": "대학/연구기관",
        "museum": "박물관/문화재청",
        "journal": "학술지",
        "long_form": "전문 칼럼",
        "encyclopedia": "백과사전",
    }.get(source_type, "일반")

    parts = []

    if relevance >= 10:
        parts.append(f"높은 관련도({relevance})")
    elif relevance >= 5:
        parts.append(f"관련도({relevance})")

    parts.append(f"{source_name} 출처")

    if quality >= 8:
        parts.append("고품질 자료")

    if freshness >= 8:
        parts.append("최신 자료")

    parts.append(f"'{topic}' 분류")

    return f"{era_name}: " + ", ".join(parts)


def filter_by_topic(
    candidate_rows: List[List[Any]],
    topics: List[str]
) -> List[List[Any]]:
    """
    특정 주제로 필터링

    Args:
        candidate_rows: CANDIDATES 행 데이터
        topics: 필터링할 주제 리스트 (예: ["정치", "군사"])

    Returns:
        필터링된 행 데이터
    """
    if not topics:
        return candidate_rows

    filtered = []
    for row in candidate_rows:
        topic = row[3]  # topic 열
        if topic in topics:
            filtered.append(row)

    return filtered


def rerank_by_diversity(
    candidate_rows: List[List[Any]],
    max_per_topic: int = 2
) -> List[List[Any]]:
    """
    주제 다양성을 위한 재정렬

    같은 주제가 너무 많으면 다양한 주제가 선정되도록 조정

    Args:
        candidate_rows: CANDIDATES 행 데이터
        max_per_topic: 주제당 최대 개수

    Returns:
        재정렬된 행 데이터
    """
    topic_counts = {}
    reranked = []
    deferred = []

    for row in candidate_rows:
        topic = row[3]
        current_count = topic_counts.get(topic, 0)

        if current_count < max_per_topic:
            reranked.append(row)
            topic_counts[topic] = current_count + 1
        else:
            deferred.append(row)

    # 나머지 추가
    reranked.extend(deferred)

    # 순위 재부여
    for i, row in enumerate(reranked):
        row[1] = i + 1  # rank 열 업데이트

    return reranked
