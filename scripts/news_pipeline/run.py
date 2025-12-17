"""
뉴스 자동화 파이프라인 (A안: 채널별 탭 분리)

구조:
- RAW_FEED: 공용 (모든 채널이 공유)
- CANDIDATES_{CHANNEL}: 채널별 후보
- OPUS_INPUT_{CHANNEL}: 채널별 대본 입력

현재 활성 채널: ECON (경제)
확장 예정: POLICY, SOCIETY, WORLD

사용법:
    from scripts.news_pipeline import run_news_pipeline
    result = run_news_pipeline(sheet_id, service, channel="ECON")
"""

import os

from .config import CHANNELS
from .utils import get_tab_name
from .rss import ingest_rss_feeds
from .scoring import score_and_select_candidates
from .opus import generate_opus_input
from .sheets import append_rows, SheetsSaveError, cleanup_old_rows


def run_news_pipeline(
    sheet_id: str,
    service,
    channel: str = "ECON",
    max_per_feed: int = 30,
    top_k: int = 5,
    llm_enabled: bool = False,
    llm_min_score: int = 0
) -> dict:
    """
    뉴스 파이프라인 전체 실행 (채널별)

    Args:
        sheet_id: Google Sheets ID
        service: Google Sheets API 서비스 객체
        channel: 채널 키 (ECON, POLICY, SOCIETY, WORLD)
        max_per_feed: 피드당 최대 기사 수
        top_k: 선정할 후보 수
        llm_enabled: LLM 사용 여부
        llm_min_score: LLM 호출 최소 점수

    Returns:
        실행 결과 딕셔너리
    """
    result = {
        "success": False,
        "channel": channel,
        "raw_count": 0,
        "candidate_count": 0,
        "opus_generated": False,
        "sheets_saved": [],  # 성공적으로 저장된 시트 목록
        "cleaned_rows": 0,   # 정리된 오래된 행 수
        "error": None,
    }

    # 채널 유효성 검사
    if channel not in CHANNELS:
        result["error"] = f"알 수 없는 채널: {channel}. 유효 채널: {list(CHANNELS.keys())}"
        return result

    if not CHANNELS[channel].get("active", False):
        result["error"] = f"비활성 채널: {channel}"
        return result

    try:
        # 0) 오래된 데이터 정리 (7일 기준)
        if service and sheet_id:
            print(f"[NEWS] === 0단계: 오래된 데이터 정리 ===")
            cleaned = cleanup_old_rows(service, sheet_id, "RAW_FEED", days=7)
            result["cleaned_rows"] = cleaned

        # 1) RSS 수집 (공용)
        print(f"[NEWS] === 1단계: RSS 수집 (채널: {channel}) ===")
        raw_rows, items = ingest_rss_feeds(max_per_feed)
        result["raw_count"] = len(raw_rows)

        if not raw_rows:
            result["error"] = "RSS 수집 결과 없음"
            return result

        # RAW_FEED에 저장
        if service and sheet_id:
            try:
                append_rows(service, sheet_id, "RAW_FEED!A1", raw_rows)
                result["sheets_saved"].append("RAW_FEED")
                print(f"[NEWS] RAW_FEED에 {len(raw_rows)}개 행 저장 완료")
            except SheetsSaveError as e:
                result["error"] = f"RAW_FEED 저장 실패: {e}"
                print(f"[NEWS] RAW_FEED 저장 실패: {e}")
                return result

        # 2) 채널별 후보 선정
        print(f"[NEWS] === 2단계: 후보 선정 ({channel}) ===")
        candidate_rows = score_and_select_candidates(items, channel, top_k)
        result["candidate_count"] = len(candidate_rows)

        if not candidate_rows:
            result["error"] = f"채널 {channel}에 적합한 후보 없음"
            return result

        # CANDIDATES_{CHANNEL}에 저장
        candidates_tab = get_tab_name("CANDIDATES", channel)
        if service and sheet_id:
            try:
                append_rows(service, sheet_id, f"{candidates_tab}!A1", candidate_rows)
                result["sheets_saved"].append(candidates_tab)
                print(f"[NEWS] {candidates_tab}에 {len(candidate_rows)}개 행 저장 완료")
            except SheetsSaveError as e:
                result["error"] = f"{candidates_tab} 저장 실패: {e}"
                print(f"[NEWS] {candidates_tab} 저장 실패: {e}")
                return result

        # 3) OPUS 입력 생성
        print(f"[NEWS] === 3단계: OPUS 입력 생성 ({channel}) ===")
        opus_rows = generate_opus_input(candidate_rows, channel, llm_enabled, llm_min_score)

        if opus_rows:
            result["opus_generated"] = True
            opus_tab = get_tab_name("OPUS_INPUT", channel)
            if service and sheet_id:
                try:
                    append_rows(service, sheet_id, f"{opus_tab}!A1", opus_rows)
                    result["sheets_saved"].append(opus_tab)
                    print(f"[NEWS] {opus_tab}에 저장 완료")
                except SheetsSaveError as e:
                    result["error"] = f"{opus_tab} 저장 실패: {e}"
                    print(f"[NEWS] {opus_tab} 저장 실패: {e}")
                    return result

        result["success"] = True
        print(f"[NEWS] === 파이프라인 완료 ({channel}) ===")

    except Exception as e:
        result["error"] = str(e)
        print(f"[NEWS] 파이프라인 오류: {e}")
        import traceback
        traceback.print_exc()

    return result


# ============================================================
# CLI 실행 (테스트용)
# ============================================================

if __name__ == "__main__":
    import json
    from google.oauth2 import service_account
    from googleapiclient.discovery import build

    sheet_id = os.environ.get("NEWS_SHEET_ID") or os.environ.get("SHEET_ID")
    service_account_json = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON")
    llm_enabled = os.environ.get("LLM_ENABLED", "0") == "1"
    channel = os.environ.get("NEWS_CHANNEL", "ECON")

    if not sheet_id:
        print("ERROR: NEWS_SHEET_ID 또는 SHEET_ID 환경변수 필요")
        exit(1)

    if not service_account_json:
        print("ERROR: GOOGLE_SERVICE_ACCOUNT_JSON 환경변수 필요")
        exit(1)

    creds_info = json.loads(service_account_json)
    creds = service_account.Credentials.from_service_account_info(
        creds_info,
        scopes=["https://www.googleapis.com/auth/spreadsheets"]
    )
    service = build("sheets", "v4", credentials=creds)

    result = run_news_pipeline(
        sheet_id=sheet_id,
        service=service,
        channel=channel,
        max_per_feed=int(os.environ.get("MAX_PER_FEED", "30")),
        top_k=int(os.environ.get("TOP_K", "5")),
        llm_enabled=llm_enabled
    )

    print(f"\n결과: {json.dumps(result, ensure_ascii=False, indent=2)}")
