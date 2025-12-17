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
    print(f"[HISTORY] 키워드: {primary_keywords[:3]}")

    all_items = []
    all_rows = []

    # 1) Google Custom Search로 수집
    search_items = _search_google_custom(
        era_name,
        primary_keywords[:5],  # 상위 5개 키워드만 사용
        max_results
    )
    all_items.extend(search_items)
    print(f"[HISTORY] 검색 결과: {len(search_items)}개 아이템")

    # 2) 위키백과/나무위키 등 백과사전 수집 (선택)
    # encyclopedia_items = _search_encyclopedia(era_name, primary_keywords)
    # all_items.extend(encyclopedia_items)

    # 3) 중복 제거 및 필터링
    now = datetime.now(timezone.utc).isoformat()
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
            print(f"[HISTORY] 필터 제외: {title[:30]}...")
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
    import uuid
    # 매 호출마다 고유 ID 생성 (중복 방지)
    unique_id = uuid.uuid4().hex[:8]

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
        "부여/옥저/동예": [
            {
                "title": "부여의 제천행사 영고와 국가 체제",
                "url": "https://example.com/buyeo-1",
                "content": "부여는 12월에 영고라는 제천행사를 열어 하늘에 제사를 지냈다. 5부족 연맹체 형태로 마가, 우가, 저가, 구가가 각각 사출도를 다스렸다.",
                "source_type": "university",
                "source_name": "고려대학교 한국사학과",
            },
            {
                "title": "옥저와 동예의 사회 풍습 연구",
                "url": "https://example.com/buyeo-2",
                "content": "옥저는 민며느리제와 골장제라는 독특한 혼인 및 장례 풍습이 있었다. 동예는 책화라는 경계 침범에 대한 배상 제도가 있었으며 무천 제천행사를 열었다.",
                "source_type": "journal",
                "source_name": "한국고대사학회",
            },
            {
                "title": "삼한의 소도와 천군 - 제정분리의 시작",
                "url": "https://example.com/buyeo-3",
                "content": "삼한 사회에는 소도라는 신성 구역이 있어 천군이 제사를 주관했다. 이는 정치와 종교가 분리되기 시작한 증거로, 고대 국가 형성 과정을 보여준다.",
                "source_type": "university",
                "source_name": "서울대학교 역사학과",
            },
        ],
        "삼국시대": [
            {
                "title": "광개토대왕의 정복 전쟁과 영토 확장",
                "url": "https://example.com/samguk-1",
                "content": "광개토대왕은 백제와 신라를 압박하고 만주 일대까지 영토를 확장했다. 광개토대왕릉비에는 64성 1400촌을 점령했다고 기록되어 있다.",
                "source_type": "museum",
                "source_name": "국립중앙박물관",
            },
            {
                "title": "백제 근초고왕의 전성기와 해상 무역",
                "url": "https://example.com/samguk-2",
                "content": "근초고왕 시대 백제는 황해를 장악하고 중국 및 일본과 활발한 해상 무역을 했다. 칠지도를 일본에 하사한 것은 백제의 국력을 보여주는 증거다.",
                "source_type": "journal",
                "source_name": "백제학회",
            },
            {
                "title": "신라 진흥왕의 한강 유역 점령과 비석",
                "url": "https://example.com/samguk-3",
                "content": "진흥왕은 한강 유역을 점령하고 순수비를 세워 영토 확장을 기념했다. 북한산 순수비, 창녕 순수비 등이 현재까지 전해지고 있다.",
                "source_type": "university",
                "source_name": "경북대학교 사학과",
            },
        ],
        "남북국시대": [
            {
                "title": "발해 대조영의 건국과 해동성국",
                "url": "https://example.com/nambuk-1",
                "content": "대조영은 고구려 유민을 이끌고 698년 발해를 건국했다. 무왕과 문왕 시대에 전성기를 맞아 '해동성국'이라 불렸다.",
                "source_type": "university",
                "source_name": "동북아역사재단",
            },
            {
                "title": "통일신라 9주 5소경 지방 행정 제도",
                "url": "https://example.com/nambuk-2",
                "content": "신문왕은 전국을 9주 5소경으로 나누어 지방 행정 체계를 정비했다. 5소경은 수도 금성의 편중된 위치를 보완하는 부도 역할을 했다.",
                "source_type": "journal",
                "source_name": "신라사학회",
            },
            {
                "title": "장보고와 청해진 - 동아시아 해상 무역",
                "url": "https://example.com/nambuk-3",
                "content": "장보고는 완도에 청해진을 설치하고 동아시아 해상 무역을 장악했다. 당나라와 일본을 연결하는 무역 네트워크를 구축하여 '해상왕'이라 불렸다.",
                "source_type": "museum",
                "source_name": "국립해양박물관",
            },
        ],
        "고려": [
            {
                "title": "왕건의 고려 건국과 후삼국 통일",
                "url": "https://example.com/goryeo-1",
                "content": "왕건은 918년 고려를 건국하고 936년 후삼국을 통일했다. 호족 연합 정책과 결혼 정책으로 세력을 규합하고 훈요십조를 남겼다.",
                "source_type": "university",
                "source_name": "고려대학교 한국사학과",
            },
            {
                "title": "팔만대장경과 고려의 불교 문화",
                "url": "https://example.com/goryeo-2",
                "content": "몽골 침입기에 국난 극복을 기원하며 팔만대장경을 제작했다. 현재 해인사에 보관된 8만여 장의 목판은 유네스코 세계기록유산이다.",
                "source_type": "museum",
                "source_name": "국립중앙박물관",
            },
            {
                "title": "고려청자의 발전과 상감 기법",
                "url": "https://example.com/goryeo-3",
                "content": "고려청자는 12세기에 상감 기법이 개발되면서 전성기를 맞았다. 비색청자의 은은한 색감과 섬세한 문양은 고려 미술의 정수를 보여준다.",
                "source_type": "journal",
                "source_name": "한국미술사학회",
            },
        ],
        "조선 전기": [
            {
                "title": "세종대왕의 훈민정음 창제",
                "url": "https://example.com/joseon-early-1",
                "content": "세종대왕은 1443년 훈민정음을 창제하고 1446년 반포했다. 집현전 학자들과 함께 백성이 쉽게 익힐 수 있는 문자를 만들었다.",
                "source_type": "university",
                "source_name": "서울대학교 국어국문학과",
            },
            {
                "title": "경국대전과 조선의 법치 체계",
                "url": "https://example.com/joseon-early-2",
                "content": "성종 때 완성된 경국대전은 조선의 기본 법전으로 500년간 국가 운영의 근간이 되었다. 이전/호전/예전/병전/형전/공전의 6전 체계로 구성되었다.",
                "source_type": "journal",
                "source_name": "한국법사학회",
            },
            {
                "title": "사림과 훈구의 대립 - 사화의 시대",
                "url": "https://example.com/joseon-early-3",
                "content": "성종 이후 사림세력이 성장하면서 훈구파와 충돌했다. 무오사화, 갑자사화, 기묘사화, 을사사화 등 4대 사화로 많은 사림이 화를 입었다.",
                "source_type": "university",
                "source_name": "한국학중앙연구원",
            },
        ],
        "조선 후기": [
            {
                "title": "임진왜란과 이순신의 해전 승리",
                "url": "https://example.com/joseon-late-1",
                "content": "1592년 왜군이 조선을 침략했다. 이순신은 한산도대첩, 명량해전 등에서 승리하여 제해권을 장악하고 왜군의 보급로를 차단했다.",
                "source_type": "museum",
                "source_name": "현충사",
            },
            {
                "title": "정조의 화성 건설과 개혁 정치",
                "url": "https://example.com/joseon-late-2",
                "content": "정조는 수원화성을 건설하고 규장각을 설치하여 개혁을 추진했다. 탕평책을 이어받아 붕당의 폐해를 극복하고자 했다.",
                "source_type": "university",
                "source_name": "성균관대학교 사학과",
            },
            {
                "title": "실학의 발전과 정약용의 목민심서",
                "url": "https://example.com/joseon-late-3",
                "content": "18-19세기 실학이 발전하면서 현실 개혁을 주장하는 학자들이 등장했다. 정약용은 목민심서를 통해 지방관의 올바른 자세를 제시했다.",
                "source_type": "journal",
                "source_name": "다산학술문화재단",
            },
        ],
        "대한제국": [
            {
                "title": "대한제국 선포와 광무개혁",
                "url": "https://example.com/daehan-1",
                "content": "1897년 고종은 대한제국을 선포하고 황제로 즉위했다. 광무개혁을 통해 근대화를 추진하고 전기, 철도, 전화 등 근대 시설을 도입했다.",
                "source_type": "university",
                "source_name": "고려대학교 한국사학과",
            },
            {
                "title": "을사조약과 헤이그 특사 파견",
                "url": "https://example.com/daehan-2",
                "content": "1905년 을사조약으로 외교권을 상실한 후, 고종은 1907년 헤이그 만국평화회의에 특사를 파견했다. 그러나 열강의 무관심 속에 실패했다.",
                "source_type": "journal",
                "source_name": "독립기념관",
            },
            {
                "title": "안중근 의사의 의거와 독립운동",
                "url": "https://example.com/daehan-3",
                "content": "안중근은 1909년 하얼빈에서 이토 히로부미를 저격했다. 뤼순 감옥에서 동양평화론을 집필하며 동아시아 평화를 호소했다.",
                "source_type": "museum",
                "source_name": "안중근의사기념관",
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

    # 모든 URL에 고유 ID 추가 (중복 방지)
    result = []
    for item in samples.get(era_name, []):
        item_copy = item.copy()
        item_copy["url"] = f"{item['url']}-{unique_id}"
        result.append(item_copy)

    print(f"[HISTORY] 샘플 데이터 사용: {era_name} ({len(result)}개, ID: {unique_id})")
    return result


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
