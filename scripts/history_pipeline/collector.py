"""
한국사 자료 수집 모듈

수집 소스:
- Google Custom Search API (학술/전문 자료)
- 국립중앙박물관 API (선택)
- 한국학중앙연구원 (선택)

뉴스가 아닌 전문 자료 중심
"""

import os
import re
import time
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional, Set
from urllib.parse import quote_plus

from .config import (
    ERAS,
    ERA_KEYWORDS,
    SOURCE_TYPES,
    get_era_sheet_name,
)
from .utils import (
    normalize_text,
    compute_hash,
    detect_keywords,
    passes_era_filter,
    format_keywords_for_sheet,
    get_kst_now,
)


def collect_materials(
    era: str,
    max_results: int = 30,
    existing_hashes: Optional[Set[str]] = None
) -> tuple:
    """
    시대별 자료 수집

    Args:
        era: 시대 키 (예: "GOJOSEON")
        max_results: 수집할 최대 자료 수
        existing_hashes: 중복 방지용 기존 해시 집합

    Returns:
        (raw_rows, items) 튜플
        - raw_rows: RAW 시트용 행 데이터
        - items: 원본 아이템 딕셔너리 리스트
    """
    if existing_hashes is None:
        existing_hashes = set()

    era_info = ERAS.get(era)
    if not era_info:
        print(f"[HISTORY] 알 수 없는 시대: {era}")
        return [], []

    era_name = era_info.get("name", era)
    keywords = ERA_KEYWORDS.get(era, {})
    primary_keywords = keywords.get("primary", [])

    print(f"[HISTORY] === 자료 수집 시작: {era_name} ===")

    all_items = []
    all_rows = []

    # 1) Google Custom Search로 수집
    search_items = _search_google_custom(
        era_name,
        primary_keywords[:5],  # 상위 5개 키워드만 사용
        max_results
    )
    all_items.extend(search_items)

    # 2) 위키백과/나무위키 등 백과사전 수집 (선택)
    # encyclopedia_items = _search_encyclopedia(era_name, primary_keywords)
    # all_items.extend(encyclopedia_items)

    # 3) 중복 제거 및 필터링
    now = get_kst_now().isoformat()
    new_count = 0
    duplicate_count = 0

    for item in all_items:
        title = normalize_text(item.get("title", ""))
        url = item.get("url", "")
        content = normalize_text(item.get("content", ""))

        if not title or not url:
            continue

        # 해시 계산
        item_hash = compute_hash(title, url)

        # 중복 체크
        if item_hash in existing_hashes:
            duplicate_count += 1
            continue

        # 시대 필터 통과 여부
        if not passes_era_filter(title, content, era):
            continue

        # 키워드 감지
        detected = detect_keywords(f"{title} {content}", era)

        # RAW 행 생성
        raw_row = [
            now,                                    # collected_at
            era,                                    # era
            item.get("source_type", "long_form"),   # source_type
            item.get("source_name", ""),            # source_name
            title[:200],                            # title (최대 200자)
            url,                                    # url
            content[:500],                          # content_summary (최대 500자)
            format_keywords_for_sheet(detected),    # keywords
            item_hash,                              # hash
        ]

        all_rows.append(raw_row)
        existing_hashes.add(item_hash)
        item["hash"] = item_hash
        new_count += 1

    print(f"[HISTORY] 수집 완료: 신규 {new_count}개, 중복 제외 {duplicate_count}개")

    return all_rows, all_items


def _search_google_custom(
    era_name: str,
    keywords: List[str],
    max_results: int = 30
) -> List[Dict[str, Any]]:
    """
    Google Custom Search API로 자료 검색

    환경변수:
    - GOOGLE_CUSTOM_SEARCH_API_KEY: API 키
    - GOOGLE_CUSTOM_SEARCH_CX: 검색 엔진 ID

    Args:
        era_name: 시대 한글명
        keywords: 검색 키워드 리스트
        max_results: 최대 결과 수

    Returns:
        검색 결과 아이템 리스트
    """
    api_key = os.environ.get("GOOGLE_CUSTOM_SEARCH_API_KEY")
    cx = os.environ.get("GOOGLE_CUSTOM_SEARCH_CX")

    if not api_key or not cx:
        print("[HISTORY] Google Custom Search API 설정 없음, 샘플 데이터 사용")
        return _get_sample_data(era_name, keywords)

    try:
        from googleapiclient.discovery import build
        service = build("customsearch", "v1", developerKey=api_key)
    except ImportError:
        print("[HISTORY] google-api-python-client 없음, 샘플 데이터 사용")
        return _get_sample_data(era_name, keywords)
    except Exception as e:
        print(f"[HISTORY] Custom Search 서비스 생성 실패: {e}")
        return _get_sample_data(era_name, keywords)

    items = []

    # 키워드별 검색
    queries = [
        f"{era_name} 역사",
        f"{era_name} 연구",
        f"{era_name} 유적 발굴",
    ]

    # 주요 키워드 추가
    for kw in keywords[:3]:
        queries.append(f"{kw} 역사적 의의")

    results_per_query = max(1, max_results // len(queries))

    for query in queries:
        try:
            result = service.cse().list(
                q=query,
                cx=cx,
                num=min(10, results_per_query),  # API 제한: 최대 10개
                lr="lang_ko",  # 한국어 결과
            ).execute()

            for item in result.get("items", []):
                source_type = _classify_source(item.get("link", ""))

                items.append({
                    "title": item.get("title", ""),
                    "url": item.get("link", ""),
                    "content": item.get("snippet", ""),
                    "source_type": source_type,
                    "source_name": item.get("displayLink", ""),
                })

            # API 호출 간격
            time.sleep(0.2)

        except Exception as e:
            print(f"[HISTORY] 검색 실패 '{query}': {e}")
            continue

        if len(items) >= max_results:
            break

    print(f"[HISTORY] Google Custom Search: {len(items)}개 결과")
    return items[:max_results]


def _classify_source(url: str) -> str:
    """URL 기반 출처 유형 분류"""

    # 대학 연구
    university_patterns = [
        r'\.ac\.kr',
        r'\.edu',
        r'university',
        r'institute',
        r'한국학중앙연구원',
    ]

    # 박물관/문화재
    museum_patterns = [
        r'museum',
        r'박물관',
        r'문화재청',
        r'cha\.go\.kr',
        r'heritage',
    ]

    # 학술지/논문
    journal_patterns = [
        r'journal',
        r'paper',
        r'dbpia',
        r'riss',
        r'kiss',
        r'scholar',
        r'논문',
    ]

    # 백과사전
    encyclopedia_patterns = [
        r'wikipedia',
        r'나무위키',
        r'namu\.wiki',
        r'encyclopedia',
        r'백과',
    ]

    url_lower = url.lower()

    for pattern in university_patterns:
        if re.search(pattern, url_lower):
            return "university"

    for pattern in museum_patterns:
        if re.search(pattern, url_lower):
            return "museum"

    for pattern in journal_patterns:
        if re.search(pattern, url_lower):
            return "journal"

    for pattern in encyclopedia_patterns:
        if re.search(pattern, url_lower):
            return "encyclopedia"

    return "long_form"


def _get_sample_data(era_name: str, keywords: List[str]) -> List[Dict[str, Any]]:
    """
    API 없을 때 사용할 샘플 데이터 (테스트/개발용)

    실제 운영 시에는 Google Custom Search API 필수
    """
    samples = {
        "고조선": [
            {
                "title": "고조선의 건국과 발전 - 한국학중앙연구원",
                "url": "https://example.com/gojoseon-1",
                "content": "단군왕검이 아사달에 도읍을 정하고 고조선을 건국한 것은 한민족 역사의 시작이다. 비파형동검과 고인돌 문화는 고조선의 청동기 문명을 보여준다.",
                "source_type": "university",
                "source_name": "한국학중앙연구원",
            },
            {
                "title": "위만조선의 멸망과 한사군 설치",
                "url": "https://example.com/gojoseon-2",
                "content": "기원전 108년 한나라의 침략으로 위만조선이 멸망하고 한사군이 설치되었다. 이는 고조선 역사의 종말을 의미하지만, 한민족의 저항은 계속되었다.",
                "source_type": "journal",
                "source_name": "한국고대사학회",
            },
            {
                "title": "8조법 연구: 고조선의 법률 체계",
                "url": "https://example.com/gojoseon-3",
                "content": "8조법은 현재 3개 조항만 전해지지만, 고조선이 법치국가였음을 보여주는 중요한 증거다. 살인자는 사형, 상해는 곡물로 배상하는 등의 내용이 있다.",
                "source_type": "university",
                "source_name": "서울대학교 역사학과",
            },
        ],
    }

    # 해당 시대 샘플이 없으면 기본 샘플 생성
    if era_name not in samples:
        default_samples = []
        for i, kw in enumerate(keywords[:3]):
            default_samples.append({
                "title": f"{era_name} {kw} 연구",
                "url": f"https://example.com/{era_name.lower()}-{i+1}",
                "content": f"{era_name} 시대의 {kw}에 대한 연구 자료입니다. 이 시대의 역사적 중요성을 다룹니다.",
                "source_type": "long_form",
                "source_name": "역사연구소",
            })
        return default_samples

    print(f"[HISTORY] 샘플 데이터 사용: {era_name} ({len(samples[era_name])}개)")
    return samples.get(era_name, [])


def deduplicate_items(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """아이템 리스트 중복 제거 (해시 기준)"""
    seen = set()
    unique = []

    for item in items:
        item_hash = item.get("hash") or compute_hash(
            item.get("title", ""),
            item.get("url", "")
        )

        if item_hash not in seen:
            seen.add(item_hash)
            unique.append(item)

    return unique
