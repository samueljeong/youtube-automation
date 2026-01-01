"""
한국사 자료 수집 모듈 (주제 기반)

주제 기반 수집:
- HISTORY_TOPICS에 정의된 주제별로 자료 수집
- 한국민족문화대백과사전, 국립중앙박물관 e뮤지엄 등
- 실제 내용을 추출하여 Opus에게 전달

수집 소스:
- 한국민족문화대백과사전 (encykorea.aks.ac.kr) - 웹 접근
- 국립중앙박물관 e뮤지엄 (API 키 필요)
- 국사편찬위원회 한국사DB (db.history.go.kr)
"""

import os
import re
import time
import html
import requests
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from urllib.parse import quote_plus

from .config import (
    ERAS,
    ERA_ORDER,
    ERA_KEYWORDS,
    HISTORY_TOPICS,
)


def collect_topic_materials(
    era: str,
    episode: int,
) -> Dict[str, Any]:
    """
    주제별 자료 수집 (4개 공신력 있는 소스에서 수집)

    Args:
        era: 시대 키 (예: "GOJOSEON")
        episode: 에피소드 번호 (1부터 시작)

    Returns:
        수집된 자료 딕셔너리:
        {
            "topic": 주제 정보,
            "materials": [자료 리스트],
            "full_content": 추출된 전체 내용 (GPT-5.1용),
            "sources": 출처 목록,
        }
    """
    # 주제 정보 가져오기
    topics = HISTORY_TOPICS.get(era, [])
    if not topics:
        print(f"[HISTORY] 시대 {era}의 주제 목록이 없습니다.")
        return {"error": f"시대 {era}의 주제 목록 없음"}

    # 에피소드 번호로 주제 찾기
    topic_info = None
    for t in topics:
        if t["episode"] == episode:
            topic_info = t
            break

    if not topic_info:
        print(f"[HISTORY] {era} 에피소드 {episode}를 찾을 수 없습니다.")
        return {"error": f"에피소드 {episode} 없음"}

    era_info = ERAS.get(era, {})
    era_name = era_info.get("name", era)

    print(f"[HISTORY] === 자료 수집 시작 ===")
    print(f"[HISTORY] 시대: {era_name}")
    print(f"[HISTORY] 에피소드: {episode}화 - {topic_info['title']}")
    print(f"[HISTORY] 주제: {topic_info['topic']}")

    keywords = topic_info.get("keywords", [])
    print(f"[HISTORY] 키워드: {', '.join(keywords[:5])}")

    # ★ 2025-01 변경: 4개 공신력 있는 소스에서 자료 수집
    # GPT-5.1에 전달하여 대본 자동 생성
    all_materials = []
    all_sources = []

    # 1. 한국민족문화대백과사전 (최우선)
    print(f"[HISTORY] → 한국민족문화대백과사전 검색 중...")
    for keyword in keywords[:5]:
        items = _search_encykorea(keyword, max_results=2)
        for item in items:
            if item not in all_materials:
                all_materials.append(item)
                if item.get("url") and item["url"] not in all_sources:
                    all_sources.append(item["url"])
        time.sleep(0.3)

    # 2. 국사편찬위원회 한국사DB
    print(f"[HISTORY] → 국사편찬위원회 한국사DB 검색 중...")
    for keyword in keywords[:3]:
        items = _search_history_db(keyword, max_results=2)
        for item in items:
            if item not in all_materials:
                all_materials.append(item)
                if item.get("url") and item["url"] not in all_sources:
                    all_sources.append(item["url"])
        time.sleep(0.3)

    # 3. 문화재청 국가문화유산포털
    print(f"[HISTORY] → 문화재청 국가문화유산포털 검색 중...")
    for keyword in keywords[:2]:
        items = _search_heritage(keyword, max_results=2)
        for item in items:
            if item not in all_materials:
                all_materials.append(item)
                if item.get("url") and item["url"] not in all_sources:
                    all_sources.append(item["url"])
        time.sleep(0.3)

    # 4. 국립중앙박물관
    print(f"[HISTORY] → 국립중앙박물관 검색 중...")
    items = _search_emuseum(era_name, keywords[:3], max_results=3)
    for item in items:
        if item not in all_materials:
            all_materials.append(item)
            if item.get("url") and item["url"] not in all_sources:
                all_sources.append(item["url"])

    # full_content 생성 (GPT-5.1에 전달할 자료)
    content_parts = []
    for i, material in enumerate(all_materials, 1):
        source_name = material.get("source_name", "")
        title = material.get("title", "")
        content = material.get("content", "")
        url = material.get("url", "")

        if content:
            content_parts.append(f"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
[자료 {i}] {title}
출처: {source_name}
URL: {url}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{content}
""")

    full_content = "\n".join(content_parts)

    print(f"[HISTORY] === 자료 수집 완료 ===")
    print(f"[HISTORY] 수집된 자료: {len(all_materials)}개")
    print(f"[HISTORY] 총 내용 길이: {len(full_content):,}자")
    print(f"[HISTORY] 출처 수: {len(all_sources)}개")

    return {
        "topic": topic_info,
        "materials": all_materials,
        "full_content": full_content,
        "sources": all_sources,
        "era": era,
        "era_name": era_name,
        "episode": episode,
    }


def _fetch_content_from_url(url: str) -> Optional[str]:
    """
    URL에서 내용 추출

    지원 소스:
    - encykorea.aks.ac.kr: 한국민족문화대백과사전
    - db.history.go.kr: 국사편찬위원회
    """
    try:
        if "encykorea.aks.ac.kr" in url:
            return _fetch_encykorea_content(url)
        elif "db.history.go.kr" in url:
            return _fetch_history_db_content(url)
        else:
            # 일반 URL - 기본 추출 시도
            return _fetch_generic_content(url)
    except Exception as e:
        print(f"[HISTORY] URL 내용 추출 실패 ({url}): {e}")
        return None


def _fetch_encykorea_content(url: str) -> Optional[str]:
    """
    한국민족문화대백과사전에서 내용 추출 (강화 버전)

    URL 형식: https://encykorea.aks.ac.kr/Article/E0003937
    """
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
        }

        response = requests.get(url, headers=headers, timeout=15)

        if response.status_code != 200:
            print(f"[HISTORY] 대백과사전 응답 실패: {response.status_code}")
            return None

        page_html = response.text

        # 본문 내용 추출 (여러 패턴 시도 - 우선순위순)
        content_patterns = [
            # 1. article 태그 전체
            r'<article[^>]*>(.*?)</article>',
            # 2. 본문 div
            r'<div class="article-body"[^>]*>(.*?)</div>',
            r'<div class="content"[^>]*>(.*?)</div>',
            r'<div id="article"[^>]*>(.*?)</div>',
            # 3. section 태그
            r'<section[^>]*>(.*?)</section>',
        ]

        content = ""

        # 모든 p 태그 수집 (가장 많은 내용)
        p_tags = re.findall(r'<p[^>]*>(.*?)</p>', page_html, re.DOTALL | re.IGNORECASE)
        if p_tags:
            all_p_content = ' '.join(p_tags)
            all_p_content = re.sub(r'<[^>]+>', ' ', all_p_content)
            all_p_content = re.sub(r'\s+', ' ', all_p_content).strip()
            if len(all_p_content) > 200:
                content = all_p_content

        # 더 긴 내용 찾기
        for pattern in content_patterns[:-1]:  # 마지막 p 태그 패턴 제외
            matches = re.findall(pattern, page_html, re.DOTALL | re.IGNORECASE)
            if matches:
                for match in matches:
                    # HTML 태그 제거
                    clean = re.sub(r'<[^>]+>', ' ', match)
                    clean = re.sub(r'\s+', ' ', clean).strip()
                    if len(clean) > len(content):
                        content = clean

        # 메타 설명 추출 (백업)
        if len(content) < 100:
            meta_match = re.search(
                r'<meta name="description" content="([^"]+)"',
                page_html,
                re.IGNORECASE
            )
            if meta_match:
                content = meta_match.group(1)

        # 제목 추출
        title_match = re.search(r'<title>([^<]+)</title>', page_html, re.IGNORECASE)
        title = title_match.group(1) if title_match else ""
        title = title.replace(" - 한국민족문화대백과사전", "").strip()

        if content:
            # HTML 엔티티 디코딩 (&#xACE0; → 고)
            content = html.unescape(content)
            title = html.unescape(title)
            # 내용 정리 (최대 5000자로 확대)
            content = content[:5000]
            print(f"[HISTORY] 추출 성공: {title[:30]}... ({len(content)}자)")
            return f"[{title}]\n{content}"

        return None

    except Exception as e:
        print(f"[HISTORY] 대백과사전 내용 추출 오류: {e}")
        return None


def _fetch_history_db_content(url: str) -> Optional[str]:
    """
    국사편찬위원회 한국사데이터베이스에서 내용 추출
    """
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (compatible; HistoryBot/1.0)",
            "Accept": "text/html,application/xhtml+xml",
        }

        response = requests.get(url, headers=headers, timeout=15)

        if response.status_code != 200:
            return None

        page_html = response.text

        # 본문 추출 (여러 패턴 시도)
        content_patterns = [
            r'<div class="view_cont"[^>]*>(.*?)</div>',
            r'<div class="cont_area"[^>]*>(.*?)</div>',
            r'<div id="content"[^>]*>(.*?)</div>',
            r'<article[^>]*>(.*?)</article>',
        ]

        content = ""
        for pattern in content_patterns:
            content_match = re.search(pattern, page_html, re.DOTALL | re.IGNORECASE)
            if content_match:
                extracted = re.sub(r'<[^>]+>', ' ', content_match.group(1))
                extracted = re.sub(r'\s+', ' ', extracted).strip()
                if len(extracted) > len(content):
                    content = extracted

        if content:
            content = html.unescape(content)
            return content[:3000]

        return None

    except Exception as e:
        print(f"[HISTORY] 한국사DB 내용 추출 오류: {e}")
        return None


def _fetch_generic_content(url: str) -> Optional[str]:
    """
    일반 URL에서 내용 추출 (백업용)
    """
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        }

        response = requests.get(url, headers=headers, timeout=10)

        if response.status_code != 200:
            return None

        page_html = response.text

        # 메타 설명 추출
        meta_match = re.search(
            r'<meta name="description" content="([^"]+)"',
            page_html,
            re.IGNORECASE
        )

        if meta_match:
            return html.unescape(meta_match.group(1))

        # 본문 첫 부분 추출
        body_match = re.search(r'<body[^>]*>(.*?)</body>', page_html, re.DOTALL | re.IGNORECASE)
        if body_match:
            text = re.sub(r'<script[^>]*>.*?</script>', '', body_match.group(1), flags=re.DOTALL)
            text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL)
            text = re.sub(r'<[^>]+>', ' ', text)
            text = re.sub(r'\s+', ' ', text).strip()
            text = html.unescape(text)
            return text[:2000] if text else None

        return None

    except Exception as e:
        print(f"[HISTORY] 일반 URL 내용 추출 오류: {e}")
        return None


def _search_wikipedia_ko(keyword: str, max_results: int = 2) -> List[Dict[str, Any]]:
    """
    한국어 위키백과 검색 (User-Agent 수정)
    """
    items = []

    try:
        # 위키백과 API 검색 - 적절한 User-Agent 필수
        search_url = "https://ko.wikipedia.org/w/api.php"
        params = {
            "action": "query",
            "list": "search",
            "srsearch": keyword,
            "srlimit": max_results,
            "format": "json",
            "utf8": 1,
        }

        # 위키백과는 적절한 User-Agent가 필요
        headers = {
            "User-Agent": "HistoryPipelineBot/1.0 (https://drama-s2ns.onrender.com; contact@example.com) Python/3.9",
            "Accept": "application/json",
        }

        response = requests.get(search_url, params=params, headers=headers, timeout=10)

        if response.status_code != 200:
            print(f"[HISTORY] 위키백과 검색 실패: {response.status_code}")
            return items

        data = response.json()
        search_results = data.get("query", {}).get("search", [])

        if not search_results:
            print(f"[HISTORY] 위키백과: '{keyword}' 검색 결과 없음")
            return items

        for result in search_results:
            title = result.get("title", "")
            snippet = result.get("snippet", "")

            # 스니펫에서 HTML 태그 제거
            snippet = re.sub(r'<[^>]+>', '', snippet)
            snippet = html.unescape(snippet)

            # 전체 내용 가져오기
            content = _fetch_wikipedia_content(title)

            items.append({
                "title": title,
                "url": f"https://ko.wikipedia.org/wiki/{quote_plus(title)}",
                "content": content or snippet,
                "source_type": "encyclopedia",
                "source_name": "위키백과",
            })
            print(f"[HISTORY] 위키백과: {title[:30]}... ({len(content or snippet)}자)")

    except Exception as e:
        print(f"[HISTORY] 위키백과 검색 오류 ({keyword}): {e}")

    return items


def _fetch_wikipedia_content(title: str) -> Optional[str]:
    """
    위키백과 문서 내용 가져오기
    """
    try:
        api_url = "https://ko.wikipedia.org/w/api.php"
        params = {
            "action": "query",
            "titles": title,
            "prop": "extracts",
            "exintro": False,
            "explaintext": True,
            "format": "json",
            "utf8": 1,
        }

        headers = {
            "User-Agent": "HistoryPipelineBot/1.0 (https://drama-s2ns.onrender.com; contact@example.com) Python/3.9",
            "Accept": "application/json",
        }

        response = requests.get(api_url, params=params, headers=headers, timeout=10)

        if response.status_code != 200:
            return None

        data = response.json()
        pages = data.get("query", {}).get("pages", {})

        for page_id, page_data in pages.items():
            if page_id == "-1":
                continue
            extract = page_data.get("extract", "")
            if extract:
                return extract[:4000]

        return None

    except Exception as e:
        print(f"[HISTORY] 위키백과 내용 추출 오류: {e}")
        return None


def _search_namu_wiki(keyword: str, max_results: int = 2) -> List[Dict[str, Any]]:
    """
    나무위키 검색 (추가 소스)
    """
    items = []

    try:
        # 나무위키 문서 직접 접근
        encoded_keyword = quote_plus(keyword)
        doc_url = f"https://namu.wiki/w/{encoded_keyword}"

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml",
        }

        response = requests.get(doc_url, headers=headers, timeout=10, allow_redirects=True)

        if response.status_code == 200:
            page_html = response.text

            # 본문 추출
            content_match = re.search(r'<article[^>]*>(.*?)</article>', page_html, re.DOTALL | re.IGNORECASE)
            if content_match:
                content = re.sub(r'<[^>]+>', ' ', content_match.group(1))
                content = re.sub(r'\s+', ' ', content).strip()
                content = html.unescape(content)

                if len(content) > 200:
                    items.append({
                        "title": keyword,
                        "url": doc_url,
                        "content": content[:4000],
                        "source_type": "encyclopedia",
                        "source_name": "나무위키",
                    })
                    print(f"[HISTORY] 나무위키: {keyword[:30]}... ({len(content[:4000])}자)")

    except Exception as e:
        print(f"[HISTORY] 나무위키 검색 오류 ({keyword}): {e}")

    return items


def _search_history_db(keyword: str, max_results: int = 3) -> List[Dict[str, Any]]:
    """
    국사편찬위원회 한국사데이터베이스 검색
    https://db.history.go.kr
    """
    items = []

    try:
        # 한국사DB 통합검색 URL
        search_url = "https://db.history.go.kr/search/searchTotalList.do"
        params = {
            "searchType": "TA",
            "searchWord": keyword,
            "searchMethod": "EXACT",
            "itemCount": max_results,
        }

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "ko-KR,ko;q=0.9",
            "Referer": "https://db.history.go.kr/",
        }

        response = requests.get(search_url, params=params, headers=headers, timeout=15)

        if response.status_code != 200:
            print(f"[HISTORY] 한국사DB 검색 실패: {response.status_code}")
            return items

        page_html = response.text

        # 검색 결과에서 링크 추출 (다양한 패턴 시도)
        patterns = [
            r'href="(https?://db\.history\.go\.kr/[^"]+)"[^>]*>([^<]+)</a>',
            r'href="(/[^"]*item[^"]*)"[^>]*>([^<]+)</a>',
            r'<a[^>]*href="([^"]+)"[^>]*class="[^"]*title[^"]*"[^>]*>([^<]+)</a>',
        ]

        matches = []
        for pattern in patterns:
            found = re.findall(pattern, page_html, re.IGNORECASE)
            if found:
                matches.extend(found)
                break

        for url_path, title in matches[:max_results]:
            if url_path.startswith('/'):
                full_url = f"https://db.history.go.kr{url_path}"
            else:
                full_url = url_path

            title = html.unescape(title.strip())
            if not title or len(title) < 2:
                continue

            # 내용 추출
            content = _fetch_history_db_content(full_url)

            items.append({
                "title": title,
                "url": full_url,
                "content": content or f"[{title}] 국사편찬위원회 한국사데이터베이스 자료",
                "source_type": "archive",
                "source_name": "국사편찬위원회",
            })
            print(f"[HISTORY] 한국사DB: {title[:30]}...")

            time.sleep(0.3)

        if not items:
            print(f"[HISTORY] 한국사DB: '{keyword}' 검색 결과 없음")

    except Exception as e:
        print(f"[HISTORY] 한국사DB 검색 오류 ({keyword}): {e}")

    return items


def _search_heritage(keyword: str, max_results: int = 3) -> List[Dict[str, Any]]:
    """
    문화재청 국가문화유산포털 검색
    https://www.heritage.go.kr
    """
    items = []

    try:
        # 국가문화유산포털 검색 (새 URL)
        search_url = "https://www.heritage.go.kr/heri/cul/culSelectTotalList.do"
        params = {
            "culMainSearchWord": keyword,
            "culSearchWord": keyword,
            "pageUnit": max_results,
            "pageIndex": 1,
        }

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "ko-KR,ko;q=0.9",
            "Referer": "https://www.heritage.go.kr/heri/cul/culSelectTotalList.do",
        }

        response = requests.get(search_url, params=params, headers=headers, timeout=15)

        if response.status_code != 200:
            print(f"[HISTORY] 문화재청 검색 실패: {response.status_code}")
            return items

        page_html = response.text

        # 검색 결과에서 문화재 정보 추출 (다양한 패턴)
        patterns = [
            r'href="(/heri/cul/culSelectDetail\.do[^"]*)"[^>]*>\s*<[^>]*>([^<]+)',
            r'<a[^>]*href="([^"]*culSelectDetail[^"]*)"[^>]*>([^<]+)</a>',
            r'class="[^"]*title[^"]*"[^>]*>\s*<a[^>]*href="([^"]+)"[^>]*>([^<]+)</a>',
        ]

        matches = []
        for pattern in patterns:
            found = re.findall(pattern, page_html, re.IGNORECASE | re.DOTALL)
            if found:
                matches.extend(found)
                break

        for url_path, title in matches[:max_results]:
            if url_path.startswith('/'):
                full_url = f"https://www.heritage.go.kr{url_path}"
            else:
                full_url = url_path

            title = re.sub(r'<[^>]+>', '', title)  # HTML 태그 제거
            title = html.unescape(title.strip())
            if not title or len(title) < 2:
                continue

            # 상세 정보 추출
            content = _fetch_heritage_content(full_url)

            items.append({
                "title": title,
                "url": full_url,
                "content": content or f"[{title}] 국가문화유산포털 문화재 정보",
                "source_type": "heritage",
                "source_name": "문화재청",
            })
            print(f"[HISTORY] 문화재청: {title[:30]}...")

            time.sleep(0.3)

        if not items:
            print(f"[HISTORY] 문화재청: '{keyword}' 검색 결과 없음")

    except Exception as e:
        print(f"[HISTORY] 문화재청 검색 오류 ({keyword}): {e}")

    return items


def _fetch_heritage_content(url: str) -> Optional[str]:
    """
    문화재청 상세 페이지에서 내용 추출
    """
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "text/html,application/xhtml+xml",
        }

        response = requests.get(url, headers=headers, timeout=10)

        if response.status_code != 200:
            return None

        page_html = response.text

        # 문화재 설명 추출
        content_parts = []

        # 기본 정보 테이블
        info_patterns = [
            (r'<th[^>]*>종\s*목</th>\s*<td[^>]*>([^<]+)</td>', "종목"),
            (r'<th[^>]*>명\s*칭</th>\s*<td[^>]*>([^<]+)</td>', "명칭"),
            (r'<th[^>]*>분\s*류</th>\s*<td[^>]*>([^<]+)</td>', "분류"),
            (r'<th[^>]*>수\s*량</th>\s*<td[^>]*>([^<]+)</td>', "수량"),
            (r'<th[^>]*>지정일</th>\s*<td[^>]*>([^<]+)</td>', "지정일"),
            (r'<th[^>]*>소재지</th>\s*<td[^>]*>([^<]+)</td>', "소재지"),
            (r'<th[^>]*>시\s*대</th>\s*<td[^>]*>([^<]+)</td>', "시대"),
        ]

        for pattern, label in info_patterns:
            match = re.search(pattern, page_html, re.IGNORECASE | re.DOTALL)
            if match:
                value = re.sub(r'<[^>]+>', '', match.group(1)).strip()
                value = html.unescape(value)
                if value:
                    content_parts.append(f"[{label}] {value}")

        # 상세 설명
        desc_patterns = [
            r'<div class="cont_desc"[^>]*>(.*?)</div>',
            r'<div class="exp_txt"[^>]*>(.*?)</div>',
            r'<td class="desc"[^>]*>(.*?)</td>',
        ]

        for pattern in desc_patterns:
            match = re.search(pattern, page_html, re.IGNORECASE | re.DOTALL)
            if match:
                desc = re.sub(r'<[^>]+>', ' ', match.group(1))
                desc = re.sub(r'\s+', ' ', desc).strip()
                desc = html.unescape(desc)
                if len(desc) > 100:
                    content_parts.append(f"\n[설명]\n{desc[:2000]}")
                    break

        if content_parts:
            return "\n".join(content_parts)

        return None

    except Exception as e:
        print(f"[HISTORY] 문화재청 내용 추출 오류: {e}")
        return None


def _search_encykorea(keyword: str, max_results: int = 3) -> List[Dict[str, Any]]:
    """
    한국민족문화대백과사전 검색
    """
    items = []

    try:
        # 검색 URL
        search_url = f"https://encykorea.aks.ac.kr/Article/Search/{quote_plus(keyword)}"

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "text/html,application/xhtml+xml",
        }

        response = requests.get(search_url, headers=headers, timeout=10)

        if response.status_code != 200:
            return items

        # 검색 결과에서 링크 추출
        pattern = r'href="(/Article/E\d+)"[^>]*>([^<]+)</a>'
        matches = re.findall(pattern, response.text)

        for url_path, title in matches[:max_results]:
            full_url = f"https://encykorea.aks.ac.kr{url_path}"

            # 각 항목의 내용 추출
            content = _fetch_encykorea_content(full_url)

            items.append({
                "title": title.strip(),
                "url": full_url,
                "content": content or "",
                "source_type": "encyclopedia",
                "source_name": "한국민족문화대백과사전",
            })

            time.sleep(0.3)

    except Exception as e:
        print(f"[HISTORY] 대백과사전 검색 오류 ({keyword}): {e}")

    return items


def _search_emuseum(
    era_name: str,
    keywords: List[str],
    max_results: int = 5
) -> List[Dict[str, Any]]:
    """
    국립중앙박물관 소장품 검색 (museum.go.kr)

    e뮤지엄(emuseum.go.kr)은 500 에러가 발생하여
    국립중앙박물관 본 사이트에서 검색
    """
    items = []

    # 검색 키워드 (시대명 + 키워드)
    search_keywords = [era_name] + keywords[:2] if keywords else [era_name]

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "ko-KR,ko;q=0.9",
        "Referer": "https://www.museum.go.kr/",
    }

    for keyword in search_keywords[:2]:  # 최대 2개 키워드만
        try:
            # 국립중앙박물관 소장품 검색 URL (실제 소장품 검색 페이지)
            search_url = "https://www.museum.go.kr/site/main/relic/search/list"
            params = {
                "searchWord": keyword,
            }

            print(f"[HISTORY] 국립중앙박물관 검색: {keyword}")
            response = requests.get(search_url, params=params, headers=headers, timeout=15)

            if response.status_code != 200:
                print(f"[HISTORY] 국립중앙박물관 검색 실패: HTTP {response.status_code}")
                continue

            page_html = response.text

            # 검색 결과에서 유물 정보 추출
            # 소장품 목록 패턴 (relicId 기반)
            patterns = [
                # 소장품 상세 링크 (relicId 포함)
                r'href="([^"]*relicId=\d+[^"]*)"[^>]*>\s*([^<]+)</a>',
                r'href="(/site/main/relic/search/view\?relicId=\d+)"[^>]*>([^<]+)</a>',
                # 유물 제목 링크
                r'class="[^"]*tit[^"]*"[^>]*>\s*<a[^>]*href="([^"]+)"[^>]*>([^<]+)</a>',
                r'<strong[^>]*>\s*<a[^>]*href="([^"]*relic[^"]*)"[^>]*>([^<]+)</a>',
            ]

            matches = []
            for pattern in patterns:
                found = re.findall(pattern, page_html, re.IGNORECASE | re.DOTALL)
                if found:
                    matches.extend(found)
                    if len(matches) >= max_results:
                        break

            for url_path, title in matches[:max_results]:
                # 중복 제거
                title_clean = re.sub(r'<[^>]+>', '', title)
                title_clean = html.unescape(title_clean.strip())

                if any(item.get("title") == title_clean for item in items):
                    continue

                if not title_clean or len(title_clean) < 2:
                    continue

                # URL 정리
                if url_path.startswith('/'):
                    full_url = f"https://www.museum.go.kr{url_path}"
                elif url_path.startswith('http'):
                    full_url = url_path
                else:
                    full_url = f"https://www.museum.go.kr/MUSEUM/contents/{url_path}"

                # 상세 페이지에서 정보 추출
                content = _fetch_museum_content(full_url, headers)

                items.append({
                    "title": title_clean,
                    "url": full_url,
                    "content": content or f"[{title_clean}] 국립중앙박물관 소장 유물",
                    "source_type": "museum",
                    "source_name": "국립중앙박물관",
                })
                print(f"[HISTORY] 국립중앙박물관: {title_clean[:40]}...")

                if len(items) >= max_results:
                    break

            time.sleep(0.3)

        except Exception as e:
            print(f"[HISTORY] 국립중앙박물관 검색 오류 ({keyword}): {e}")

    if items:
        print(f"[HISTORY] 국립중앙박물관: 총 {len(items)}개 유물 정보 수집")
    else:
        print(f"[HISTORY] 국립중앙박물관: 검색 결과 없음 (시대: {era_name})")

    return items


def _fetch_museum_content(url: str, headers: dict = None) -> Optional[str]:
    """
    국립중앙박물관 상세 페이지에서 유물 정보 추출
    """
    try:
        if not headers:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Accept": "text/html,application/xhtml+xml",
            }

        response = requests.get(url, headers=headers, timeout=10)

        if response.status_code != 200:
            return None

        page_html = response.text
        content_parts = []

        # 유물 기본 정보 추출
        info_patterns = [
            (r'<th[^>]*>명\s*칭</th>\s*<td[^>]*>([^<]+)</td>', "명칭"),
            (r'<th[^>]*>국\s*적[/시대]*</th>\s*<td[^>]*>([^<]+)</td>', "시대"),
            (r'<th[^>]*>재\s*질</th>\s*<td[^>]*>([^<]+)</td>', "재질"),
            (r'<th[^>]*>크\s*기</th>\s*<td[^>]*>([^<]+)</td>', "크기"),
            (r'<th[^>]*>지정구분</th>\s*<td[^>]*>([^<]+)</td>', "지정"),
            (r'<th[^>]*>출토지</th>\s*<td[^>]*>([^<]+)</td>', "출토지"),
            (r'<th[^>]*>소장품번호</th>\s*<td[^>]*>([^<]+)</td>', "소장품번호"),
        ]

        for pattern, label in info_patterns:
            match = re.search(pattern, page_html, re.IGNORECASE | re.DOTALL)
            if match:
                value = re.sub(r'<[^>]+>', '', match.group(1)).strip()
                value = html.unescape(value)
                if value and value != "-" and value.strip():
                    content_parts.append(f"[{label}] {value}")

        # 상세 설명 추출
        desc_patterns = [
            r'<div class="[^"]*desc[^"]*"[^>]*>(.*?)</div>',
            r'<div class="[^"]*cont[^"]*"[^>]*>(.*?)</div>',
            r'<dd class="[^"]*txt[^"]*"[^>]*>(.*?)</dd>',
            r'<p class="[^"]*info[^"]*"[^>]*>(.*?)</p>',
        ]

        for pattern in desc_patterns:
            match = re.search(pattern, page_html, re.IGNORECASE | re.DOTALL)
            if match:
                desc = re.sub(r'<[^>]+>', ' ', match.group(1))
                desc = re.sub(r'\s+', ' ', desc).strip()
                desc = html.unescape(desc)
                if len(desc) > 50:
                    content_parts.append(f"\n[설명]\n{desc[:1500]}")
                    break

        if content_parts:
            return "\n".join(content_parts)

        return None

    except Exception as e:
        print(f"[HISTORY] 국립중앙박물관 상세 추출 오류: {e}")
        return None


def _classify_source(url: str) -> str:
    """URL 기반 출처 유형 분류"""

    url_lower = url.lower()

    if "encykorea" in url_lower:
        return "encyclopedia"
    elif "emuseum" in url_lower or "museum" in url_lower:
        return "museum"
    elif "db.history" in url_lower:
        return "university"
    elif "ac.kr" in url_lower or "edu" in url_lower:
        return "university"
    elif "cha.go.kr" in url_lower:
        return "museum"

    return "long_form"


def get_all_topics_for_era(era: str) -> List[Dict[str, Any]]:
    """
    시대의 모든 주제 목록 반환
    """
    return HISTORY_TOPICS.get(era, [])


def get_topic_count(era: str) -> int:
    """
    시대의 총 에피소드 수 반환
    """
    return len(HISTORY_TOPICS.get(era, []))


def get_total_episode_count() -> int:
    """
    전체 에피소드 수 반환
    """
    total = 0
    for era_topics in HISTORY_TOPICS.values():
        total += len(era_topics)
    return total
