"""
해외 미스테리 자료 수집 모듈

영어 위키백과에서 미스테리 사건 정보 수집
- Wikipedia API 사용 (무료, 제한 없음)
- 전체 본문 추출
- 한국어 번역은 Opus가 담당
"""

import re
import html
import time
import requests
from typing import Dict, Any, Optional, List
from urllib.parse import quote_plus

from .config import FEATURED_MYSTERIES, MYSTERY_CATEGORIES


# Wikipedia API 기본 설정
WIKI_API_BASE = "https://en.wikipedia.org/w/api.php"
WIKI_USER_AGENT = "MysteryPipelineBot/1.0 (https://drama-s2ns.onrender.com; contact@example.com) Python/3.9"


def search_wikipedia_en(keyword: str, max_results: int = 5) -> List[Dict[str, Any]]:
    """
    영어 위키백과 검색

    Args:
        keyword: 검색어
        max_results: 최대 결과 수

    Returns:
        검색 결과 리스트
    """
    items = []

    try:
        params = {
            "action": "query",
            "list": "search",
            "srsearch": keyword,
            "srlimit": max_results,
            "format": "json",
            "utf8": 1,
        }

        headers = {
            "User-Agent": WIKI_USER_AGENT,
            "Accept": "application/json",
        }

        response = requests.get(WIKI_API_BASE, params=params, headers=headers, timeout=15)

        if response.status_code != 200:
            print(f"[MYSTERY] Wikipedia 검색 실패: {response.status_code}")
            return items

        data = response.json()
        search_results = data.get("query", {}).get("search", [])

        for result in search_results:
            title = result.get("title", "")
            snippet = result.get("snippet", "")

            # HTML 태그 제거
            snippet = re.sub(r'<[^>]+>', '', snippet)
            snippet = html.unescape(snippet)

            items.append({
                "title": title,
                "snippet": snippet,
                "url": f"https://en.wikipedia.org/wiki/{quote_plus(title.replace(' ', '_'))}",
            })

        print(f"[MYSTERY] Wikipedia 검색 '{keyword}': {len(items)}개 결과")

    except Exception as e:
        print(f"[MYSTERY] Wikipedia 검색 오류 ({keyword}): {e}")

    return items


def get_wikipedia_info(title: str) -> Optional[Dict[str, Any]]:
    """
    위키백과 문서 기본 정보만 가져오기 (Opus가 직접 URL을 열어서 읽음)

    Args:
        title: 문서 제목 (예: "Dyatlov_Pass_incident")

    Returns:
        문서 기본 정보 딕셔너리 또는 None
    """
    try:
        headers = {
            "User-Agent": WIKI_USER_AGENT,
            "Accept": "application/json",
        }

        print(f"[MYSTERY] Wikipedia 문서 정보 확인 중: {title}")

        # 문서 존재 여부 및 기본 정보만 확인
        params = {
            "action": "query",
            "titles": title.replace("_", " "),
            "prop": "info|extracts",
            "exintro": True,  # 서론만 (간단한 요약용)
            "explaintext": True,
            "inprop": "url",
            "format": "json",
            "utf8": 1,
        }

        response = requests.get(WIKI_API_BASE, params=params, headers=headers, timeout=15)

        if response.status_code != 200:
            print(f"[MYSTERY] Wikipedia 정보 확인 실패: {response.status_code}")
            return None

        data = response.json()
        pages = data.get("query", {}).get("pages", {})

        for page_id, page_data in pages.items():
            if page_id == "-1":
                print(f"[MYSTERY] 문서를 찾을 수 없음: {title}")
                return None

            extract = page_data.get("extract", "")
            full_url = page_data.get("fullurl", f"https://en.wikipedia.org/wiki/{title}")

            # 서론만 요약으로 사용 (Opus가 URL에서 직접 전체 내용을 읽음)
            summary = extract.strip()[:1000] if extract else ""

            print(f"[MYSTERY] 문서 정보 확인 성공: {title}")
            print(f"[MYSTERY] → Opus가 직접 URL에서 읽을 예정: {full_url}")

            return {
                "title": page_data.get("title", title),
                "url": full_url,
                "summary": summary,  # 서론만 (참고용)
            }

        return None

    except Exception as e:
        print(f"[MYSTERY] Wikipedia 정보 확인 오류 ({title}): {e}")
        return None


def collect_mystery_article(
    title: str,
    title_ko: str = None,
    category: str = None,
) -> Dict[str, Any]:
    """
    미스테리 사건 기본 정보 수집 (Opus가 직접 URL에서 읽음)

    Args:
        title: 위키백과 문서 제목 (영문)
        title_ko: 한국어 제목 (있으면)
        category: 카테고리 키

    Returns:
        기본 정보 딕셔너리 (Opus가 URL에서 직접 내용 수집)
    """
    result = {
        "success": False,
        "title_en": title,
        "title_ko": title_ko or "",
        "category": category or "",
        "url": "",
        "summary": "",
        "error": None,
    }

    try:
        # 위키백과 문서 존재 확인 및 기본 정보만 가져오기
        wiki_data = get_wikipedia_info(title)

        if not wiki_data:
            result["error"] = "위키백과에서 문서를 찾을 수 없습니다"
            return result

        result["success"] = True
        result["url"] = wiki_data["url"]
        result["summary"] = wiki_data.get("summary", "")

        print(f"[MYSTERY] 기본 정보 수집 완료: {title}")
        print(f"[MYSTERY] → Opus가 직접 URL에서 전체 내용을 읽습니다")

    except Exception as e:
        result["error"] = str(e)
        print(f"[MYSTERY] 정보 수집 오류 ({title}): {e}")

    return result


def get_featured_mystery(index: int = 0) -> Optional[Dict[str, Any]]:
    """
    추천 미스테리 사건 가져오기 (초기 콘텐츠용)

    Args:
        index: FEATURED_MYSTERIES 인덱스

    Returns:
        미스테리 정보 딕셔너리
    """
    if index < 0 or index >= len(FEATURED_MYSTERIES):
        print(f"[MYSTERY] 인덱스 범위 초과: {index} (전체 {len(FEATURED_MYSTERIES)}개)")
        return None

    mystery = FEATURED_MYSTERIES[index]

    # 위키백과에서 내용 수집
    collected = collect_mystery_article(
        title=mystery["title"],
        title_ko=mystery.get("title_ko"),
        category=mystery.get("category"),
    )

    if collected["success"]:
        # 추가 정보 병합
        collected["year"] = mystery.get("year", "")
        collected["country"] = mystery.get("country", "")
        collected["hook"] = mystery.get("hook", "")

    return collected


def get_next_mystery(
    used_titles: List[str] = None,
    category: str = None,
) -> Optional[Dict[str, Any]]:
    """
    다음 미스테리 사건 가져오기 (사용하지 않은 것 중에서)

    Args:
        used_titles: 이미 사용한 제목 리스트
        category: 특정 카테고리만 (없으면 전체)

    Returns:
        미스테리 정보 딕셔너리
    """
    used_titles = used_titles or []

    for mystery in FEATURED_MYSTERIES:
        # 이미 사용한 것은 스킵
        if mystery["title"] in used_titles:
            continue

        # 카테고리 필터
        if category and mystery.get("category") != category:
            continue

        # 위키백과에서 내용 수집
        collected = collect_mystery_article(
            title=mystery["title"],
            title_ko=mystery.get("title_ko"),
            category=mystery.get("category"),
        )

        if collected["success"]:
            collected["year"] = mystery.get("year", "")
            collected["country"] = mystery.get("country", "")
            collected["hook"] = mystery.get("hook", "")
            return collected

        # 실패하면 다음으로
        time.sleep(0.5)

    print(f"[MYSTERY] 사용 가능한 미스테리가 없습니다")
    return None


def list_available_mysteries(used_titles: List[str] = None) -> List[Dict[str, str]]:
    """
    사용 가능한 미스테리 목록 반환 (간략 정보만)

    Args:
        used_titles: 이미 사용한 제목 리스트

    Returns:
        사용 가능한 미스테리 목록
    """
    used_titles = used_titles or []
    available = []

    for mystery in FEATURED_MYSTERIES:
        if mystery["title"] not in used_titles:
            available.append({
                "title": mystery["title"],
                "title_ko": mystery.get("title_ko", ""),
                "category": mystery.get("category", ""),
                "year": mystery.get("year", ""),
                "hook": mystery.get("hook", ""),
            })

    return available
