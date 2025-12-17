"""
뉴스 자동화 파이프라인 MVP

목표: Google News RSS → 후보 선정 → OPUS 입력 생성
- LLM 최소화: 후보 선정은 규칙 기반, TOP 1만 LLM
- Google Sheets = 큐 (RAW_FEED / CANDIDATES / OPUS_INPUT)
- MVP: 키워드 + 신선도 + 중복도 (TF-IDF ❌)

사용법:
    from scripts.news_pipeline import run_news_pipeline
    result = run_news_pipeline(sheet_id, service)
"""

import os
import re
import hashlib
from datetime import datetime, timezone
from urllib.parse import quote_plus

# feedparser, dateutil은 requirements.txt에 추가 필요
try:
    import feedparser
except ImportError:
    feedparser = None

try:
    from dateutil import parser as dtparser
except ImportError:
    dtparser = None


# ============================================================
# 설정: Google News RSS 피드 (쿼리 기반)
# ============================================================

def google_news_rss_url(query: str) -> str:
    """Google News RSS 검색 URL 생성 (한국어)"""
    q = quote_plus(query)
    return f"https://news.google.com/rss/search?q={q}&hl=ko&gl=KR&ceid=KR:ko"


# 피드 설정: (피드명, 검색쿼리)
NEWS_FEEDS = [
    ("economy_daily", "기준금리 OR 대출 OR 예금 OR 물가 OR 환율 OR 부동산"),
    ("policy_life", "세금 OR 연금 OR 건강보험료 OR 전기요금 OR 가스요금 OR 복지"),
    ("society_life", "고용 OR 실업 OR 집값 OR 전세 OR 의료 OR 교육비"),
    ("global_macro", "미국 금리 OR 달러 OR 유가 OR 반도체 수출 OR 중국 경기"),
]


# 카테고리별 키워드 (규칙 기반 분류용)
CATEGORY_KEYWORDS = {
    "경제": ["금리", "대출", "예금", "물가", "환율", "부동산", "전세", "주식", "채권", "달러", "유가", "수출", "경기"],
    "정책": ["세금", "연금", "건강보험", "보험료", "복지", "규제", "지원금", "보조금", "요금", "전기요금", "가스요금"],
    "사회": ["고용", "실업", "임금", "의료", "교육", "사기", "전세사기", "물가", "집값"],
    "국제": ["미국", "연준", "중국", "일본", "유럽", "전쟁", "유가", "달러", "환율", "수출"],
}


# ============================================================
# 유틸리티 함수
# ============================================================

def normalize_text(text: str) -> str:
    """텍스트 정규화 (공백 정리)"""
    return re.sub(r"\s+", " ", (text or "").strip())


def compute_hash(title: str, link: str) -> str:
    """제목+링크로 해시 생성 (중복 방지)"""
    s = f"{title}|{link}".encode("utf-8")
    return hashlib.sha256(s).hexdigest()[:16]


def guess_category(title: str, summary: str) -> str:
    """규칙 기반 카테고리 분류"""
    text = f"{title} {summary}"
    best_cat, best_score = "경제", 0

    for cat, keywords in CATEGORY_KEYWORDS.items():
        score = sum(1 for k in keywords if k in text)
        if score > best_score:
            best_cat, best_score = cat, score

    return best_cat


def calculate_relevance_score(title: str, summary: str, category: str) -> int:
    """관련도 점수 계산 (제목에 있으면 가중치)"""
    text = f"{title} {summary}"
    keywords = CATEGORY_KEYWORDS.get(category, [])
    score = 0

    for k in keywords:
        if k in text:
            score += 2 if k in title else 1

    return score


def calculate_recency_score(published_at: str, now: datetime) -> int:
    """신선도 점수 계산 (최근일수록 높음)"""
    if not published_at or not dtparser:
        return 2  # 날짜 없으면 기본값

    try:
        dt = dtparser.parse(published_at)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        hours = (now - dt).total_seconds() / 3600
        # 60시간 이내면 점수 부여 (10점 만점)
        return max(0, 10 - int(hours / 6))
    except Exception:
        return 2


# ============================================================
# 메인 파이프라인 함수들
# ============================================================

def ingest_rss_feeds(max_per_feed: int = 30) -> tuple[list, list]:
    """
    RSS 피드에서 기사 수집

    반환: (raw_rows, items)
        - raw_rows: RAW_FEED 시트에 저장할 행들
        - items: 후속 처리용 기사 딕셔너리 리스트
    """
    if not feedparser:
        print("[NEWS] feedparser 모듈이 설치되지 않음")
        return [], []

    now = datetime.now(timezone.utc)
    raw_rows = []
    items = []

    for feed_name, query in NEWS_FEEDS:
        url = google_news_rss_url(query)
        print(f"[NEWS] 피드 수집 중: {feed_name}")

        try:
            d = feedparser.parse(url)
            entries = d.entries[:max_per_feed]
            print(f"[NEWS] {feed_name}: {len(entries)}개 기사 발견")

            for e in entries:
                title = normalize_text(getattr(e, "title", ""))
                link = getattr(e, "link", "")
                summary = normalize_text(getattr(e, "summary", ""))
                published = getattr(e, "published", None) or getattr(e, "updated", None)

                # 날짜 파싱
                published_at = ""
                if published and dtparser:
                    try:
                        published_at = dtparser.parse(published).astimezone(timezone.utc).isoformat()
                    except Exception:
                        pass

                h = compute_hash(title, link)

                # 주요 키워드 추출 (간단 버전)
                hit_keywords = []
                for kw in ["금리", "대출", "연금", "세금", "건보", "부동산", "환율", "물가"]:
                    if kw in (title + summary):
                        hit_keywords.append(kw)
                kw_hit = "|".join(hit_keywords)

                # RAW_FEED 행
                raw_rows.append([
                    now.isoformat(),  # ingested_at
                    "google_news_rss",  # source
                    feed_name,
                    title,
                    link,
                    published_at,
                    summary,
                    kw_hit,
                    h  # hash
                ])

                items.append({
                    "title": title,
                    "link": link,
                    "summary": summary,
                    "published_at": published_at,
                    "hash": h,
                    "feed_name": feed_name,
                })

        except Exception as e:
            print(f"[NEWS] {feed_name} 수집 실패: {e}")

    print(f"[NEWS] 총 {len(items)}개 기사 수집 완료")
    return raw_rows, items


def deduplicate_items(items: list) -> list:
    """해시 기반 중복 제거"""
    seen = set()
    unique = []

    for item in items:
        if item["hash"] not in seen:
            seen.add(item["hash"])
            unique.append(item)

    print(f"[NEWS] 중복 제거: {len(items)} → {len(unique)}개")
    return unique


def score_and_select_candidates(items: list, top_k: int = 5) -> list:
    """
    점수화 + TOP K 후보 선정 (규칙 기반, LLM ❌)

    반환: CANDIDATES 시트에 저장할 행들
    """
    now = datetime.now(timezone.utc)
    run_id = now.astimezone().strftime("%Y-%m-%d")

    # 중복 제거
    unique_items = deduplicate_items(items)

    # 점수화
    scored = []
    for item in unique_items:
        category = guess_category(item["title"], item["summary"])
        relevance = calculate_relevance_score(item["title"], item["summary"], category)
        recency = calculate_recency_score(item["published_at"], now)
        total = relevance * 2 + recency

        scored.append({
            "total": total,
            "relevance": relevance,
            "recency": recency,
            "category": category,
            "item": item,
        })

    # 점수순 정렬
    scored.sort(key=lambda x: x["total"], reverse=True)
    top = scored[:top_k]

    # CANDIDATES 행 생성
    candidate_rows = []
    for rank, s in enumerate(top, start=1):
        item = s["item"]
        angle = "내 돈·내 생활에 어떤 영향인가?"
        why = f"관련도({s['relevance']})/신선도({s['recency']}) 기반 상위 후보. '{s['category']}'로 분류."

        candidate_rows.append([
            run_id,           # run_id
            rank,             # rank
            s["category"],    # category
            angle,            # angle
            s["total"],       # score_total
            s["recency"],     # score_recency
            s["relevance"],   # score_relevance
            "",               # score_uniqueness (MVP에서 미사용)
            item["title"],    # title
            item["link"],     # link
            item["published_at"],  # published_at
            why,              # why_selected
        ])

    print(f"[NEWS] TOP {len(candidate_rows)} 후보 선정 완료")
    return candidate_rows


def generate_opus_input(candidate_rows: list, llm_enabled: bool = False) -> list:
    """
    OPUS 입력 생성 (TOP 1만 LLM 사용)

    Args:
        candidate_rows: CANDIDATES 행들
        llm_enabled: LLM 사용 여부

    반환: OPUS_INPUT 시트에 저장할 행들
    """
    if not candidate_rows:
        return []

    # TOP 1만 처리
    top1 = candidate_rows[0]
    run_id = top1[0]
    category = top1[2]
    title = top1[8]
    link = top1[9]

    # 요약 정보 (CANDIDATES에는 없으므로 title로 대체)
    summary = ""

    if llm_enabled:
        core_points, brief, shorts, thumb = _llm_make_opus_input(category, title, summary, link)
    else:
        # LLM 없이 기본 템플릿
        core_points = f"""[수동 작성 필요]
이슈: {title}
카테고리: {category}
링크: {link}

핵심포인트 8개를 직접 작성하세요."""

        brief = """2~3분 대본 작성 지침:
- 속보 요약 ❌
- 맥락 + 파장 중심 정리 ⭕
- 50대 이상 시청자 대상
- "내 돈/내 생활" 관점"""

        shorts = ""
        thumb = ""

    opus_row = [[
        run_id,
        1,  # selected_rank
        category,
        title[:40],  # issue_one_line
        core_points,
        brief,
        shorts,
        thumb,
        "NEW",  # status
        "",  # opus_script (사람이 작성)
    ]]

    print(f"[NEWS] OPUS_INPUT 생성 완료: {title[:30]}...")
    return opus_row


def _llm_make_opus_input(category: str, title: str, summary: str, link: str) -> tuple:
    """
    LLM으로 핵심포인트 생성 (TOP 1만, 저비용 모델)

    반환: (core_points, brief, shorts, thumb)
    """
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        print("[NEWS] OPENAI_API_KEY 환경변수 없음, LLM 스킵")
        return "", "", "", ""

    try:
        from openai import OpenAI
        client = OpenAI(api_key=api_key)

        prompt = f"""너는 '속보가 아니라 정리' 뉴스 채널의 기획자다.
목표: 2~3분 분량(대본 1,800~2,400자 정도)으로, 50대 이상 시청자가 '내 돈/내 생활' 관점에서 이해하도록 정리한다.

카테고리: {category}
이슈 제목: {title}
요약(있으면): {summary}
링크: {link}

출력 형식:
1) 핵심포인트 8개 (불릿)
2) Opus에 붙여넣을 대본 지시문(서론/본론/전망/마무리 구조, '정리' 중심, 과장 금지)
3) 쇼츠→롱폼 유도 문구 5개('다음 파장' 예고형)
4) 썸네일 문구 3안(사건명 X / 시청자 상태 O)"""

        model = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")

        # Responses API 사용 (gpt-5.1 호환)
        if "gpt-5" in model:
            response = client.responses.create(
                model=model,
                input=[
                    {"role": "system", "content": [{"type": "input_text", "text": "뉴스 채널 기획자 역할"}]},
                    {"role": "user", "content": [{"type": "input_text", "text": prompt}]}
                ],
                temperature=0.7
            )
            if getattr(response, "output_text", None):
                text = response.output_text.strip()
            else:
                text_chunks = []
                for item in getattr(response, "output", []) or []:
                    for content in getattr(item, "content", []) or []:
                        if getattr(content, "type", "") == "text":
                            text_chunks.append(getattr(content, "text", ""))
                text = "\n".join(text_chunks).strip()
        else:
            # 일반 Chat Completions API
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": "뉴스 채널 기획자 역할"},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7
            )
            text = response.choices[0].message.content.strip()

        # MVP: 파싱 없이 전체 텍스트 반환
        core_points = text
        brief = "위 핵심포인트 기반으로 2~3분 대본 작성. 속보 요약 금지, 맥락+파장 중심 정리."
        shorts = ""
        thumb = ""

        print(f"[NEWS] LLM 핵심포인트 생성 완료 (모델: {model})")
        return core_points, brief, shorts, thumb

    except Exception as e:
        print(f"[NEWS] LLM 호출 실패: {e}")
        return "", "", "", ""


# ============================================================
# 메인 파이프라인 (통합)
# ============================================================

def run_news_pipeline(
    sheet_id: str,
    service,
    max_per_feed: int = 30,
    top_k: int = 5,
    llm_enabled: bool = False
) -> dict:
    """
    뉴스 파이프라인 전체 실행

    Args:
        sheet_id: Google Sheets ID
        service: Google Sheets API 서비스 객체
        max_per_feed: 피드당 최대 기사 수
        top_k: 선정할 후보 수
        llm_enabled: LLM 사용 여부 (TOP 1만)

    반환: {
        "success": bool,
        "raw_count": int,
        "candidate_count": int,
        "opus_generated": bool,
        "error": str or None
    }
    """
    result = {
        "success": False,
        "raw_count": 0,
        "candidate_count": 0,
        "opus_generated": False,
        "error": None,
    }

    try:
        # 1) RSS 수집
        print("[NEWS] === 1단계: RSS 수집 ===")
        raw_rows, items = ingest_rss_feeds(max_per_feed)
        result["raw_count"] = len(raw_rows)

        if not raw_rows:
            result["error"] = "RSS 수집 결과 없음"
            return result

        # RAW_FEED에 저장
        if service and sheet_id:
            _append_rows(service, sheet_id, "RAW_FEED!A1", raw_rows)
            print(f"[NEWS] RAW_FEED에 {len(raw_rows)}개 행 저장")

        # 2) 후보 선정
        print("[NEWS] === 2단계: 후보 선정 ===")
        candidate_rows = score_and_select_candidates(items, top_k)
        result["candidate_count"] = len(candidate_rows)

        if not candidate_rows:
            result["error"] = "후보 선정 결과 없음"
            return result

        # CANDIDATES에 저장
        if service and sheet_id:
            _append_rows(service, sheet_id, "CANDIDATES!A1", candidate_rows)
            print(f"[NEWS] CANDIDATES에 {len(candidate_rows)}개 행 저장")

        # 3) OPUS 입력 생성 (TOP 1만)
        print("[NEWS] === 3단계: OPUS 입력 생성 ===")
        opus_rows = generate_opus_input(candidate_rows, llm_enabled)

        if opus_rows:
            result["opus_generated"] = True
            if service and sheet_id:
                _append_rows(service, sheet_id, "OPUS_INPUT!A1", opus_rows)
                print(f"[NEWS] OPUS_INPUT에 저장 완료")

        result["success"] = True
        print("[NEWS] === 파이프라인 완료 ===")

    except Exception as e:
        result["error"] = str(e)
        print(f"[NEWS] 파이프라인 오류: {e}")
        import traceback
        traceback.print_exc()

    return result


def _append_rows(service, sheet_id: str, range_a1: str, rows: list) -> bool:
    """Google Sheets에 행 추가 (재시도 로직 포함)"""
    import time as time_module

    body = {"values": rows}
    max_retries = 3

    for attempt in range(max_retries):
        try:
            service.spreadsheets().values().append(
                spreadsheetId=sheet_id,
                range=range_a1,
                valueInputOption="RAW",
                insertDataOption="INSERT_ROWS",
                body=body
            ).execute()
            return True
        except Exception as e:
            error_str = str(e).lower()
            transient_errors = ['500', '502', '503', '504', 'timeout', 'backend error']
            is_transient = any(p in error_str for p in transient_errors)

            if is_transient and attempt < max_retries - 1:
                wait_time = (2 ** attempt) * 2
                print(f"[NEWS] Sheets append 재시도 ({attempt + 1}/{max_retries}), {wait_time}초 대기")
                time_module.sleep(wait_time)
            else:
                print(f"[NEWS] Sheets append 실패: {e}")
                return False

    return False


# ============================================================
# CLI 실행 (테스트용)
# ============================================================

if __name__ == "__main__":
    import json
    from google.oauth2 import service_account
    from googleapiclient.discovery import build

    # 환경변수에서 설정 로드
    sheet_id = os.environ.get("NEWS_SHEET_ID") or os.environ.get("SHEET_ID")
    service_account_json = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON")
    llm_enabled = os.environ.get("LLM_ENABLED", "0") == "1"

    if not sheet_id:
        print("ERROR: NEWS_SHEET_ID 또는 SHEET_ID 환경변수 필요")
        exit(1)

    if not service_account_json:
        print("ERROR: GOOGLE_SERVICE_ACCOUNT_JSON 환경변수 필요")
        exit(1)

    # Google Sheets 서비스 생성
    creds_info = json.loads(service_account_json)
    creds = service_account.Credentials.from_service_account_info(
        creds_info,
        scopes=["https://www.googleapis.com/auth/spreadsheets"]
    )
    service = build("sheets", "v4", credentials=creds)

    # 파이프라인 실행
    result = run_news_pipeline(
        sheet_id=sheet_id,
        service=service,
        max_per_feed=int(os.environ.get("MAX_PER_FEED", "30")),
        top_k=int(os.environ.get("TOP_K", "5")),
        llm_enabled=llm_enabled
    )

    print(f"\n결과: {json.dumps(result, ensure_ascii=False, indent=2)}")
