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
    주제별 자료 수집

    Args:
        era: 시대 키 (예: "GOJOSEON")
        episode: 에피소드 번호 (1부터 시작)

    Returns:
        수집된 자료 딕셔너리:
        {
            "topic": 주제 정보,
            "materials": [자료 리스트],
            "full_content": 추출된 전체 내용 (Opus용),
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

    # 수집 결과
    materials = []
    full_content_parts = []
    sources = []

    # 1. 참고 링크에서 내용 추출
    reference_links = topic_info.get("reference_links", [])
    for link in reference_links:
        print(f"[HISTORY] 링크 수집 중: {link}")
        content = _fetch_content_from_url(link)
        if content:
            materials.append({
                "url": link,
                "content": content,
                "source_type": _classify_source(link),
            })
            full_content_parts.append(f"[출처: {link}]\n{content}")
            sources.append(link)
        time.sleep(0.5)  # API 호출 간격

    # 2. 키워드로 추가 검색 (한국민족문화대백과)
    keywords = topic_info.get("keywords", [])
    for keyword in keywords[:3]:  # 상위 3개 키워드만
        print(f"[HISTORY] 키워드 검색: {keyword}")
        search_results = _search_encykorea(keyword, max_results=2)
        for result in search_results:
            # 중복 체크
            if result["url"] not in sources:
                materials.append(result)
                if result.get("content"):
                    full_content_parts.append(f"[출처: {result['url']}]\n{result['content']}")
                    sources.append(result["url"])
        time.sleep(0.3)

    # 3. e뮤지엄 검색 (API 키 있을 경우)
    emuseum_results = _search_emuseum(era_name, keywords[:2])
    for result in emuseum_results:
        materials.append(result)
        if result.get("content"):
            full_content_parts.append(f"[출처: 국립중앙박물관]\n{result['content']}")
            sources.append(result.get("url", "국립중앙박물관"))

    # 전체 내용 합치기
    full_content = "\n\n---\n\n".join(full_content_parts)

    print(f"[HISTORY] 수집 완료: {len(materials)}개 자료, {len(full_content)}자")

    return {
        "topic": topic_info,
        "materials": materials,
        "full_content": full_content,
        "sources": sources,
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
    한국민족문화대백과사전에서 내용 추출

    URL 형식: https://encykorea.aks.ac.kr/Article/E0003937
    """
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "text/html,application/xhtml+xml",
        }

        response = requests.get(url, headers=headers, timeout=15)

        if response.status_code != 200:
            print(f"[HISTORY] 대백과사전 응답 실패: {response.status_code}")
            return None

        page_html = response.text

        # 본문 내용 추출 (여러 패턴 시도)
        content_patterns = [
            r'<div class="article-body"[^>]*>(.*?)</div>',
            r'<div class="content"[^>]*>(.*?)</div>',
            r'<article[^>]*>(.*?)</article>',
            r'<div id="article"[^>]*>(.*?)</div>',
        ]

        content = ""
        for pattern in content_patterns:
            matches = re.findall(pattern, page_html, re.DOTALL | re.IGNORECASE)
            if matches:
                # HTML 태그 제거
                raw_content = matches[0]
                content = re.sub(r'<[^>]+>', ' ', raw_content)
                content = re.sub(r'\s+', ' ', content).strip()
                if len(content) > 100:  # 충분한 내용이 있으면
                    break

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
            # 내용 정리 (최대 3000자)
            content = content[:3000]
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

        html = response.text

        # 본문 추출
        content_match = re.search(
            r'<div class="view_cont"[^>]*>(.*?)</div>',
            html,
            re.DOTALL | re.IGNORECASE
        )

        if content_match:
            content = re.sub(r'<[^>]+>', ' ', content_match.group(1))
            content = re.sub(r'\s+', ' ', content).strip()
            return content[:2000]

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

        html = response.text

        # 메타 설명 추출
        meta_match = re.search(
            r'<meta name="description" content="([^"]+)"',
            html,
            re.IGNORECASE
        )

        if meta_match:
            return meta_match.group(1)

        # 본문 첫 부분 추출
        body_match = re.search(r'<body[^>]*>(.*?)</body>', html, re.DOTALL | re.IGNORECASE)
        if body_match:
            text = re.sub(r'<script[^>]*>.*?</script>', '', body_match.group(1), flags=re.DOTALL)
            text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL)
            text = re.sub(r'<[^>]+>', ' ', text)
            text = re.sub(r'\s+', ' ', text).strip()
            return text[:1000] if text else None

        return None

    except Exception as e:
        print(f"[HISTORY] 일반 URL 내용 추출 오류: {e}")
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
    국립중앙박물관 e뮤지엄 API 검색

    환경변수:
    - EMUSEUM_API_KEY: 공공데이터포털 인증키
    """
    api_key = os.environ.get("EMUSEUM_API_KEY")
    if not api_key:
        return []

    items = []

    # 시대 매핑
    era_mapping = {
        "고조선": "청동기",
        "부여/옥저/동예": "원삼국",
        "삼국시대": "삼국",
        "남북국시대": "통일신라",
        "고려": "고려",
        "조선 전기": "조선",
        "조선 후기": "조선",
        "대한제국": "대한제국",
        "일제강점기": "일제강점기",
    }

    search_era = era_mapping.get(era_name, era_name)

    try:
        base_url = "http://www.emuseum.go.kr/openapi/relic/list"

        params = {
            "serviceKey": api_key,
            "pageNo": 1,
            "numOfRows": max_results,
            "mnfctDt": search_era,
            "type": "json"
        }

        response = requests.get(base_url, params=params, timeout=15)

        if response.status_code == 200:
            try:
                data = response.json()
                relics = data.get("response", {}).get("body", {}).get("items", {}).get("item", [])

                if isinstance(relics, dict):
                    relics = [relics]

                for relic in relics:
                    title = relic.get("prdctNmNtnl", "") or relic.get("prdctNmEng", "")
                    if not title:
                        continue

                    content = f"[유물명] {title}\n"
                    content += f"[시대] {relic.get('mnfctDt', '')} 시대\n"
                    content += f"[재질] {relic.get('mtrlNtnl', '')}\n"
                    content += f"[크기] {relic.get('sizeNtnl', '')}\n"
                    content += f"[설명] {relic.get('dscNtnl', '')[:500]}"

                    items.append({
                        "title": title,
                        "url": f"https://www.emuseum.go.kr/relic/{relic.get('relicId', '')}",
                        "content": content.strip(),
                        "source_type": "museum",
                        "source_name": "국립중앙박물관",
                    })

            except ValueError:
                print(f"[HISTORY] e뮤지엄 JSON 파싱 실패")

        if items:
            print(f"[HISTORY] 국립중앙박물관: {len(items)}개 유물 정보 수집")

    except Exception as e:
        print(f"[HISTORY] e뮤지엄 API 오류: {e}")

    return items


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
