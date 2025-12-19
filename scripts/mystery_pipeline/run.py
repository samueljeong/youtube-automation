"""
해외 미스테리 자동화 파이프라인 메인 실행

워크플로우:
1. 현재 PENDING 개수 확인
2. 부족하면 다음 미스테리 추가
3. 위키백과에서 자료 수집
4. Opus 프롬프트 생성 → 시트 저장

사용법:
    from scripts.mystery_pipeline import run_mystery_pipeline
    result = run_mystery_pipeline(sheet_id, service)

API:
    POST /api/mystery/run-pipeline
"""

import os
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional, List

from .config import (
    MYSTERY_SHEET_NAME,
    MYSTERY_SHEET_HEADERS,
    MYSTERY_OPUS_PROMPT_TEMPLATE,
    MYSTERY_CATEGORIES,
    FEATURED_MYSTERIES,
    PENDING_TARGET_COUNT,
    MYSTERY_TTS_VOICE,
    MYSTERY_VIDEO_LENGTH_MINUTES,
)
from .collector import (
    collect_mystery_article,
    get_next_mystery,
    list_available_mysteries,
)


def get_kst_now() -> datetime:
    """현재 KST 시간 반환"""
    return datetime.now(timezone(timedelta(hours=9)))


def ensure_mystery_sheet(service, sheet_id: str) -> bool:
    """
    MYSTERY_OPUS_INPUT 시트 존재 확인 및 생성

    Args:
        service: Google Sheets API 서비스
        sheet_id: 스프레드시트 ID

    Returns:
        성공 여부
    """
    try:
        # 시트 목록 가져오기
        spreadsheet = service.spreadsheets().get(spreadsheetId=sheet_id).execute()
        sheets = spreadsheet.get("sheets", [])
        sheet_names = [s.get("properties", {}).get("title", "") for s in sheets]

        if MYSTERY_SHEET_NAME in sheet_names:
            print(f"[MYSTERY] 시트 '{MYSTERY_SHEET_NAME}' 존재 확인")
            return True

        # 시트 생성
        print(f"[MYSTERY] 시트 '{MYSTERY_SHEET_NAME}' 생성 중...")

        requests_body = {
            "requests": [
                {
                    "addSheet": {
                        "properties": {
                            "title": MYSTERY_SHEET_NAME,
                        }
                    }
                }
            ]
        }

        service.spreadsheets().batchUpdate(
            spreadsheetId=sheet_id,
            body=requests_body
        ).execute()

        # 헤더 추가
        service.spreadsheets().values().update(
            spreadsheetId=sheet_id,
            range=f"{MYSTERY_SHEET_NAME}!A1",
            valueInputOption="RAW",
            body={"values": [MYSTERY_SHEET_HEADERS]}
        ).execute()

        print(f"[MYSTERY] 시트 '{MYSTERY_SHEET_NAME}' 생성 완료")
        return True

    except Exception as e:
        print(f"[MYSTERY] 시트 생성 오류: {e}")
        return False


def get_used_titles(service, sheet_id: str) -> List[str]:
    """
    이미 사용한 미스테리 제목 목록 가져오기

    Args:
        service: Google Sheets API 서비스
        sheet_id: 스프레드시트 ID

    Returns:
        사용한 title_en 리스트
    """
    try:
        result = service.spreadsheets().values().get(
            spreadsheetId=sheet_id,
            range=f"{MYSTERY_SHEET_NAME}!D:D"  # title_en 열
        ).execute()

        values = result.get("values", [])

        # 헤더 제외
        if values and values[0] and values[0][0] == "title_en":
            values = values[1:]

        used = [row[0] for row in values if row]
        print(f"[MYSTERY] 이미 사용한 미스테리: {len(used)}개")
        return used

    except Exception as e:
        print(f"[MYSTERY] 사용 목록 조회 오류: {e}")
        return []


def count_pending(service, sheet_id: str) -> int:
    """
    PENDING 상태 개수 확인

    Args:
        service: Google Sheets API 서비스
        sheet_id: 스프레드시트 ID

    Returns:
        PENDING 개수
    """
    try:
        result = service.spreadsheets().values().get(
            spreadsheetId=sheet_id,
            range=f"{MYSTERY_SHEET_NAME}!J:J"  # status 열
        ).execute()

        values = result.get("values", [])
        pending_count = sum(1 for row in values if row and row[0] == "PENDING")

        print(f"[MYSTERY] 현재 PENDING: {pending_count}개")
        return pending_count

    except Exception as e:
        print(f"[MYSTERY] PENDING 개수 조회 오류: {e}")
        return 0


def get_next_episode_number(service, sheet_id: str) -> int:
    """
    다음 에피소드 번호 가져오기

    Args:
        service: Google Sheets API 서비스
        sheet_id: 스프레드시트 ID

    Returns:
        다음 에피소드 번호
    """
    try:
        result = service.spreadsheets().values().get(
            spreadsheetId=sheet_id,
            range=f"{MYSTERY_SHEET_NAME}!B:B"  # episode 열
        ).execute()

        values = result.get("values", [])

        # 숫자만 추출
        episodes = []
        for row in values:
            if row:
                try:
                    ep = int(row[0])
                    episodes.append(ep)
                except ValueError:
                    pass

        if episodes:
            return max(episodes) + 1
        return 1

    except Exception as e:
        print(f"[MYSTERY] 에피소드 번호 조회 오류: {e}")
        return 1


def generate_opus_prompt(mystery_data: Dict[str, Any]) -> str:
    """
    Opus 프롬프트 생성 (Opus가 URL에서 직접 자료 수집)

    Args:
        mystery_data: 미스테리 기본 정보

    Returns:
        Opus 프롬프트 문자열
    """
    category_name = MYSTERY_CATEGORIES.get(
        mystery_data.get("category", ""),
        {}
    ).get("name", mystery_data.get("category", ""))

    prompt = MYSTERY_OPUS_PROMPT_TEMPLATE.format(
        title_ko=mystery_data.get("title_ko", mystery_data.get("title_en", "")),
        title_en=mystery_data.get("title_en", ""),
        category=category_name,
        year=mystery_data.get("year", "알 수 없음"),
        country=mystery_data.get("country", "알 수 없음"),
        hook=mystery_data.get("hook", ""),
        wiki_url=mystery_data.get("url", ""),
    )

    return prompt


def append_mystery_row(
    service,
    sheet_id: str,
    mystery_data: Dict[str, Any],
    episode: int,
) -> bool:
    """
    미스테리 데이터를 시트에 추가

    Args:
        service: Google Sheets API 서비스
        sheet_id: 스프레드시트 ID
        mystery_data: 수집된 미스테리 데이터
        episode: 에피소드 번호

    Returns:
        성공 여부
    """
    try:
        now = get_kst_now()
        run_id = now.strftime("%Y-%m-%d")

        # Opus 프롬프트 생성
        opus_prompt = generate_opus_prompt(mystery_data)

        row = [
            run_id,                                    # run_id
            str(episode),                              # episode
            mystery_data.get("category", ""),          # category
            mystery_data.get("title_en", ""),          # title_en
            mystery_data.get("title_ko", ""),          # title_ko
            mystery_data.get("url", ""),               # wiki_url
            mystery_data.get("summary", ""),           # summary (서론만)
            "",                                        # full_content (Opus가 직접 수집)
            opus_prompt[:30000],                       # opus_prompt (시트 셀 한계)
            "PENDING",                                 # status
            now.isoformat(),                           # created_at
        ]

        service.spreadsheets().values().append(
            spreadsheetId=sheet_id,
            range=f"{MYSTERY_SHEET_NAME}!A:K",
            valueInputOption="RAW",
            insertDataOption="INSERT_ROWS",
            body={"values": [row]}
        ).execute()

        print(f"[MYSTERY] 에피소드 {episode} 추가 완료: {mystery_data.get('title_ko', mystery_data.get('title_en'))}")
        return True

    except Exception as e:
        print(f"[MYSTERY] 행 추가 오류: {e}")
        return False


def run_mystery_pipeline(
    sheet_id: str,
    service,
    force: bool = False,
    max_add: int = 3,
) -> Dict[str, Any]:
    """
    미스테리 파이프라인 실행

    PENDING이 부족하면 자동으로 다음 미스테리 추가

    Args:
        sheet_id: Google Sheets ID
        service: Google Sheets API 서비스 객체
        force: 강제 실행 (PENDING 충분해도 추가)
        max_add: 한 번에 추가할 최대 개수

    Returns:
        실행 결과 딕셔너리
    """
    result = {
        "success": False,
        "pending_before": 0,
        "pending_after": 0,
        "episodes_added": 0,
        "added_mysteries": [],
        "available_count": 0,
        "error": None,
    }

    try:
        print(f"[MYSTERY] ========================================")
        print(f"[MYSTERY] 해외 미스테리 파이프라인 시작")
        print(f"[MYSTERY] ========================================")

        # 0) 시트 준비
        if service and sheet_id:
            ensure_mystery_sheet(service, sheet_id)

        # 1) 현재 상태 확인
        pending_count = count_pending(service, sheet_id)
        result["pending_before"] = pending_count

        used_titles = get_used_titles(service, sheet_id)
        available = list_available_mysteries(used_titles)
        result["available_count"] = len(available)

        print(f"[MYSTERY] 현재 PENDING: {pending_count}개, 사용 가능: {len(available)}개")

        # 2) PENDING 충분하면 종료 (force가 아닌 경우)
        if not force and pending_count >= PENDING_TARGET_COUNT:
            print(f"[MYSTERY] PENDING {PENDING_TARGET_COUNT}개 이상, 추가 불필요")
            result["success"] = True
            result["pending_after"] = pending_count
            return result

        # 3) 추가할 개수 계산
        need_count = PENDING_TARGET_COUNT - pending_count
        add_count = min(need_count, max_add, len(available))

        if add_count <= 0:
            if len(available) == 0:
                print(f"[MYSTERY] 사용 가능한 미스테리가 없습니다")
                result["error"] = "사용 가능한 미스테리 없음"
            else:
                print(f"[MYSTERY] 추가할 필요 없음")
                result["success"] = True

            result["pending_after"] = pending_count
            return result

        print(f"[MYSTERY] {add_count}개 추가 예정")

        # 4) 에피소드 추가
        next_episode = get_next_episode_number(service, sheet_id)

        for i in range(add_count):
            # 다음 미스테리 가져오기
            mystery = get_next_mystery(used_titles)

            if not mystery:
                print(f"[MYSTERY] 더 이상 가져올 미스테리가 없습니다")
                break

            # 시트에 추가
            if append_mystery_row(service, sheet_id, mystery, next_episode):
                result["episodes_added"] += 1
                result["added_mysteries"].append({
                    "episode": next_episode,
                    "title_en": mystery.get("title_en"),
                    "title_ko": mystery.get("title_ko"),
                })
                used_titles.append(mystery.get("title_en"))
                next_episode += 1

        # 5) 결과 정리
        result["pending_after"] = count_pending(service, sheet_id)
        result["success"] = True

        print(f"[MYSTERY] ========================================")
        print(f"[MYSTERY] 완료: {result['episodes_added']}개 추가")
        print(f"[MYSTERY] PENDING: {result['pending_before']} → {result['pending_after']}")
        print(f"[MYSTERY] ========================================")

    except Exception as e:
        result["error"] = str(e)
        print(f"[MYSTERY] 파이프라인 오류: {e}")

    return result


def test_collect_mystery(title: str = "Dyatlov_Pass_incident") -> Dict[str, Any]:
    """
    테스트용: 단일 미스테리 수집

    Args:
        title: 위키백과 문서 제목

    Returns:
        수집 결과
    """
    print(f"[MYSTERY] 테스트 수집: {title}")

    # FEATURED_MYSTERIES에서 정보 찾기
    mystery_info = None
    for m in FEATURED_MYSTERIES:
        if m["title"] == title:
            mystery_info = m
            break

    result = collect_mystery_article(
        title=title,
        title_ko=mystery_info.get("title_ko") if mystery_info else None,
        category=mystery_info.get("category") if mystery_info else None,
    )

    if result["success"] and mystery_info:
        result["year"] = mystery_info.get("year", "")
        result["country"] = mystery_info.get("country", "")
        result["hook"] = mystery_info.get("hook", "")

        # Opus 프롬프트도 생성
        result["opus_prompt"] = generate_opus_prompt(result)

    return result
