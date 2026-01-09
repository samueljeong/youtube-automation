"""
미스테리 자료 수집 모듈

- 해외 미스테리: 영어 위키백과 API
- 한국 미스테리: 나무위키 (2025-12-22 추가)
"""

import re
import html
import time
import hashlib
import requests
from typing import Dict, Any, Optional, List
from urllib.parse import quote, quote_plus

from .config import (
    FEATURED_MYSTERIES,
    MYSTERY_CATEGORIES,
    FEATURED_KR_MYSTERIES,
    KR_MYSTERY_CATEGORIES,
)


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


# ============================================================
# 한국 미스테리 수집 (나무위키 기반)
# ============================================================

NAMU_USER_AGENT = "MysteryPipelineBot/1.0 (https://drama-s2ns.onrender.com) Python/3.9"


def compute_kr_hash(title_ko: str) -> str:
    """한국 미스테리 중복 방지용 해시 생성"""
    s = title_ko.encode("utf-8")
    return hashlib.sha256(s).hexdigest()[:16]


def get_namu_url(namu_title: str) -> str:
    """나무위키 URL 생성"""
    encoded = quote(namu_title, safe="")
    return f"https://namu.wiki/w/{encoded}"


def get_namu_info(namu_title: str) -> Optional[Dict[str, Any]]:
    """
    나무위키 문서 존재 확인 (Opus가 직접 URL에서 읽음)

    나무위키는 공식 API가 없으므로 URL만 생성하고
    Opus가 직접 페이지를 읽도록 함

    Args:
        namu_title: 나무위키 문서 제목

    Returns:
        문서 기본 정보 딕셔너리 또는 None
    """
    try:
        url = get_namu_url(namu_title)

        # HEAD 요청으로 문서 존재 확인 (본문 다운로드 X)
        headers = {
            "User-Agent": NAMU_USER_AGENT,
        }

        response = requests.head(url, headers=headers, timeout=10, allow_redirects=True)

        if response.status_code == 200:
            print(f"[KR_MYSTERY] 나무위키 문서 확인: {namu_title}")
            return {
                "title": namu_title,
                "url": url,
                "exists": True,
            }
        else:
            print(f"[KR_MYSTERY] 나무위키 문서 없음: {namu_title} (HTTP {response.status_code})")
            return None

    except Exception as e:
        print(f"[KR_MYSTERY] 나무위키 확인 오류 ({namu_title}): {e}")
        # 오류 시에도 URL은 반환 (Opus가 직접 확인)
        return {
            "title": namu_title,
            "url": get_namu_url(namu_title),
            "exists": None,  # 확인 불가
        }


def collect_kr_mystery_article(
    namu_title: str,
    title_ko: str = None,
    category: str = None,
) -> Dict[str, Any]:
    """
    한국 미스테리 사건 기본 정보 수집 (Opus가 직접 URL에서 읽음)

    Args:
        namu_title: 나무위키 문서 제목
        title_ko: 표시용 한국어 제목 (없으면 namu_title 사용)
        category: 카테고리 키

    Returns:
        기본 정보 딕셔너리
    """
    result = {
        "success": False,
        "namu_title": namu_title,
        "title_ko": title_ko or namu_title,
        "category": category or "",
        "url": get_namu_url(namu_title),
        "hash": compute_kr_hash(title_ko or namu_title),
        "error": None,
    }

    try:
        # 나무위키 문서 존재 확인
        namu_data = get_namu_info(namu_title)

        if namu_data:
            result["success"] = True
            result["url"] = namu_data["url"]
            print(f"[KR_MYSTERY] 기본 정보 수집 완료: {title_ko or namu_title}")
            print(f"[KR_MYSTERY] → Opus가 직접 URL에서 전체 내용을 읽습니다")
        else:
            result["error"] = "나무위키에서 문서를 찾을 수 없습니다"
            # URL은 그대로 유지 (Opus가 직접 확인할 수 있도록)

    except Exception as e:
        result["error"] = str(e)
        print(f"[KR_MYSTERY] 정보 수집 오류 ({namu_title}): {e}")

    return result


def get_next_kr_mystery(
    used_titles: List[str] = None,
    category: str = None,
) -> Optional[Dict[str, Any]]:
    """
    다음 한국 미스테리 사건 가져오기 (사용하지 않은 것 중에서)

    Args:
        used_titles: 이미 사용한 title_ko 리스트
        category: 특정 카테고리만 (없으면 전체)

    Returns:
        미스테리 정보 딕셔너리
    """
    used_titles = used_titles or []

    for mystery in FEATURED_KR_MYSTERIES:
        title_ko = mystery.get("title_ko", mystery.get("namu_title", ""))

        # 이미 사용한 것은 스킵
        if title_ko in used_titles:
            continue

        # namu_title로도 중복 체크
        if mystery.get("namu_title") in used_titles:
            continue

        # 카테고리 필터
        if category and mystery.get("category") != category:
            continue

        # 나무위키에서 정보 수집
        collected = collect_kr_mystery_article(
            namu_title=mystery.get("namu_title", title_ko),
            title_ko=title_ko,
            category=mystery.get("category"),
        )

        if collected["success"] or collected["url"]:
            # 추가 정보 병합
            collected["year"] = mystery.get("year", "")
            collected["hook"] = mystery.get("hook", "")
            collected["movie"] = mystery.get("movie", "")
            collected["solved"] = mystery.get("solved", False)
            return collected

        # 실패해도 URL이 있으면 반환 (Opus가 직접 확인)
        if collected.get("url"):
            collected["year"] = mystery.get("year", "")
            collected["hook"] = mystery.get("hook", "")
            return collected

        # 대기 후 다음으로
        time.sleep(0.3)

    print(f"[KR_MYSTERY] 사용 가능한 한국 미스테리가 없습니다")
    return None


def list_available_kr_mysteries(
    used_titles: List[str] = None,
    category: str = None
) -> List[Dict[str, Any]]:
    """
    사용 가능한 한국 미스테리 목록 반환 (간략 정보만)

    Args:
        used_titles: 이미 사용한 title_ko 리스트
        category: 특정 카테고리만 필터 (None이면 전체)

    Returns:
        사용 가능한 미스테리 목록
    """
    used_titles = used_titles or []
    available = []

    for mystery in FEATURED_KR_MYSTERIES:
        title_ko = mystery.get("title_ko", mystery.get("namu_title", ""))
        namu_title = mystery.get("namu_title", "")
        mystery_category = mystery.get("category", "")

        # 중복 체크
        if title_ko in used_titles or namu_title in used_titles:
            continue

        # 카테고리 필터
        if category and mystery_category != category:
            continue

        available.append({
            "namu_title": namu_title,
            "title_ko": title_ko,
            "category": mystery_category,
            "year": mystery.get("year", ""),
            "hook": mystery.get("hook", ""),
            "movie": mystery.get("movie", ""),
            "solved": mystery.get("solved", False),
        })

    return available


def get_kr_category_name(category_key: str) -> str:
    """카테고리 키를 한글 이름으로 변환"""
    cat_info = KR_MYSTERY_CATEGORIES.get(category_key, {})
    return cat_info.get("name", category_key)
