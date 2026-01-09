"""
미스테리 자동화 파이프라인 메인 실행

- 해외 미스테리: 영어 위키백과
- 한국 미스테리: 나무위키 (2025-12-22 추가)

워크플로우:
1. 현재 '준비' 상태 개수 확인
2. 부족하면 다음 미스테리 추가
3. 자료 수집 (위키백과/나무위키)
4. Opus 프롬프트 생성 → 시트 저장

사용법:
    # 해외 미스테리
    from scripts.mystery_pipeline import run_mystery_pipeline
    result = run_mystery_pipeline(sheet_id, service)

    # 한국 미스테리 ★
    from scripts.mystery_pipeline import run_kr_mystery_pipeline
    result = run_kr_mystery_pipeline(sheet_id, service)

API:
    POST /api/mystery/run-pipeline           # 해외
    POST /api/mystery/run-kr-pipeline        # 한국 ★
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
    UNIFIED_MYSTERY_SHEET,
    MYSTERY_OPUS_FIELDS,
    # 한국 미스테리 설정
    KR_MYSTERY_CATEGORIES,
    FEATURED_KR_MYSTERIES,
    KR_MYSTERY_OPUS_PROMPT_TEMPLATE,
)
from .collector import (
    collect_mystery_article,
    get_next_mystery,
    list_available_mysteries,
    # 한국 미스테리 수집
    collect_kr_mystery_article,
    get_next_kr_mystery,
    list_available_kr_mysteries,
    get_kr_category_name,
    get_namu_url,
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
        pending_count = sum(1 for row in values if row and row[0] == "준비")

        print(f"[MYSTERY] 현재 준비: {pending_count}개")
        return pending_count

    except Exception as e:
        print(f"[MYSTERY] 준비 개수 조회 오류: {e}")
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


class SheetsSaveError(Exception):
    """Google Sheets 저장 실패 예외"""
    pass


def append_to_unified_sheet(
    service,
    sheet_id: str,
    opus_row: List[Any],
    field_names: List[str]
) -> bool:
    """
    통합 시트(MYSTERY)에 데이터 추가 (헤더 매핑 적용)

    통합 시트 구조:
    - 행 1: 채널ID | UCxxx
    - 행 2: 헤더
    - 행 3~: 데이터

    Args:
        service: Google Sheets API 서비스 객체
        sheet_id: 스프레드시트 ID
        opus_row: 추가할 데이터 행 (단일 행)
        field_names: opus_row의 각 열에 해당하는 필드 이름

    Returns:
        성공 여부
    """
    try:
        # 1) 시트 헤더(행 2) 읽기
        result = service.spreadsheets().values().get(
            spreadsheetId=sheet_id,
            range=f"'{UNIFIED_MYSTERY_SHEET}'!A2:Z2"
        ).execute()
        header_rows = result.get('values', [])

        if not header_rows:
            raise SheetsSaveError(f"시트 '{UNIFIED_MYSTERY_SHEET}'의 헤더가 없습니다")

        headers = header_rows[0]
        header_idx = {h: i for i, h in enumerate(headers)}

        # 2) 데이터를 헤더에 맞게 변환
        new_row = [''] * len(headers)
        for i, field in enumerate(field_names):
            if i < len(opus_row) and field in header_idx:
                new_row[header_idx[field]] = opus_row[i]

        # 3) 행 3부터 append
        body = {"values": [new_row]}
        result = service.spreadsheets().values().append(
            spreadsheetId=sheet_id,
            range=f"'{UNIFIED_MYSTERY_SHEET}'!A3",
            valueInputOption="RAW",
            insertDataOption="INSERT_ROWS",
            body=body
        ).execute()

        updated_rows = result.get("updates", {}).get("updatedRows", 0)
        print(f"[MYSTERY] 통합 시트 '{UNIFIED_MYSTERY_SHEET}'에 {updated_rows}개 행 추가 완료")
        return True

    except Exception as e:
        print(f"[MYSTERY] 통합 시트 '{UNIFIED_MYSTERY_SHEET}' 저장 실패: {e}")
        raise SheetsSaveError(f"통합 시트 저장 실패 ({UNIFIED_MYSTERY_SHEET}): {e}")


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


def generate_thumbnail_copy(mystery_data: Dict[str, Any]) -> str:
    """썸네일 문구 생성"""
    title_ko = mystery_data.get("title_ko", mystery_data.get("title_en", ""))
    hook = mystery_data.get("hook", "")
    category_name = MYSTERY_CATEGORIES.get(
        mystery_data.get("category", ""),
        {}
    ).get("name", "미스테리")

    return f"""[썸네일 문구 추천]

1. {title_ko}
2. {hook}
3. {category_name} - 진실은 무엇인가"""


def append_mystery_row(
    service,
    sheet_id: str,
    mystery_data: Dict[str, Any],
    episode: int,
) -> bool:
    """
    미스테리 데이터를 통합 시트(MYSTERY)에 추가

    Args:
        service: Google Sheets API 서비스
        sheet_id: 스프레드시트 ID
        mystery_data: 수집된 미스테리 데이터
        episode: 에피소드 번호

    Returns:
        성공 여부
    """
    try:
        # Opus 프롬프트 생성
        opus_prompt = generate_opus_prompt(mystery_data)

        # 썸네일 문구 생성
        thumbnail_copy = generate_thumbnail_copy(mystery_data)

        # 통합 시트용 행 데이터 (MYSTERY_OPUS_FIELDS 순서와 일치)
        opus_row = [
            str(episode),                              # [0] episode
            mystery_data.get("category", ""),          # [1] category
            mystery_data.get("title_en", ""),          # [2] title_en
            mystery_data.get("title_ko", ""),          # [3] title_ko
            mystery_data.get("url", ""),               # [4] wiki_url
            mystery_data.get("summary", ""),           # [5] summary (서론만)
            "",                                        # [6] full_content (Opus가 직접 수집)
            opus_prompt[:30000],                       # [7] opus_prompt (시트 셀 한계)
            thumbnail_copy,                            # [8] thumbnail_copy
            "준비",                                    # [9] status
        ]

        # 통합 시트에 저장
        append_to_unified_sheet(
            service,
            sheet_id,
            opus_row,
            MYSTERY_OPUS_FIELDS
        )

        print(f"[MYSTERY] 에피소드 {episode} → '{UNIFIED_MYSTERY_SHEET}' 시트 저장 완료: {mystery_data.get('title_ko', mystery_data.get('title_en'))}")
        return True

    except Exception as e:
        print(f"[MYSTERY] 통합 시트 저장 오류: {e}")
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

        print(f"[MYSTERY] 현재 준비: {pending_count}개, 사용 가능: {len(available)}개")

        # 2) 준비 충분하면 종료 (force가 아닌 경우)
        if not force and pending_count >= PENDING_TARGET_COUNT:
            print(f"[MYSTERY] 준비 {PENDING_TARGET_COUNT}개 이상, 추가 불필요")
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
        print(f"[MYSTERY] 준비: {result['pending_before']} → {result['pending_after']}")
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


# ============================================================
# 한국 미스테리 파이프라인 (나무위키 기반)
# ============================================================


def get_used_kr_titles(service, sheet_id: str) -> List[str]:
    """
    이미 사용한 한국 미스테리 제목 목록 가져오기

    Args:
        service: Google Sheets API 서비스
        sheet_id: 스프레드시트 ID

    Returns:
        사용한 title_ko 리스트
    """
    try:
        result = service.spreadsheets().values().get(
            spreadsheetId=sheet_id,
            range=f"'{UNIFIED_MYSTERY_SHEET}'!A2:Z"  # 헤더 제외하고 전체
        ).execute()

        header_result = service.spreadsheets().values().get(
            spreadsheetId=sheet_id,
            range=f"'{UNIFIED_MYSTERY_SHEET}'!A2:Z2"
        ).execute()

        headers = header_result.get("values", [[]])[0]
        rows = result.get("values", [])

        # 헤더에서 title_ko 열 인덱스 찾기
        title_ko_idx = None
        for i, h in enumerate(headers):
            if h == "title_ko":
                title_ko_idx = i
                break

        if title_ko_idx is None:
            print(f"[KR_MYSTERY] title_ko 열을 찾을 수 없습니다")
            return []

        # title_ko 값 추출 (헤더 제외)
        used = []
        for row in rows[1:]:  # 헤더 행 제외
            if len(row) > title_ko_idx and row[title_ko_idx]:
                used.append(row[title_ko_idx])

        print(f"[KR_MYSTERY] 이미 사용한 한국 미스테리: {len(used)}개")
        return used

    except Exception as e:
        print(f"[KR_MYSTERY] 사용 목록 조회 오류: {e}")
        return []


def count_kr_pending(service, sheet_id: str) -> int:
    """
    한국 미스테리 PENDING 상태 개수 확인 (통합 시트에서)

    Args:
        service: Google Sheets API 서비스
        sheet_id: 스프레드시트 ID

    Returns:
        PENDING 개수
    """
    try:
        # 헤더 가져오기
        header_result = service.spreadsheets().values().get(
            spreadsheetId=sheet_id,
            range=f"'{UNIFIED_MYSTERY_SHEET}'!A2:Z2"
        ).execute()
        headers = header_result.get("values", [[]])[0]

        # 상태 열 인덱스 찾기
        status_idx = None
        for i, h in enumerate(headers):
            if h == "상태":
                status_idx = i
                break

        if status_idx is None:
            print(f"[KR_MYSTERY] 상태 열을 찾을 수 없습니다")
            return 0

        # 상태 열 가져오기
        col_letter = chr(ord('A') + status_idx)
        result = service.spreadsheets().values().get(
            spreadsheetId=sheet_id,
            range=f"'{UNIFIED_MYSTERY_SHEET}'!{col_letter}:{col_letter}"
        ).execute()

        values = result.get("values", [])
        # 헤더 2개 제외 (행1=채널ID, 행2=헤더)
        pending_count = sum(1 for row in values[2:] if row and row[0] in ["준비", "대기"])

        print(f"[KR_MYSTERY] 현재 준비: {pending_count}개")
        return pending_count

    except Exception as e:
        print(f"[KR_MYSTERY] 준비 개수 조회 오류: {e}")
        return 0


def get_next_kr_episode_number(service, sheet_id: str) -> int:
    """
    다음 한국 미스테리 에피소드 번호 가져오기

    Args:
        service: Google Sheets API 서비스
        sheet_id: 스프레드시트 ID

    Returns:
        다음 에피소드 번호
    """
    try:
        # 헤더 가져오기
        header_result = service.spreadsheets().values().get(
            spreadsheetId=sheet_id,
            range=f"'{UNIFIED_MYSTERY_SHEET}'!A2:Z2"
        ).execute()
        headers = header_result.get("values", [[]])[0]

        # episode 열 인덱스 찾기
        ep_idx = None
        for i, h in enumerate(headers):
            if h == "episode":
                ep_idx = i
                break

        if ep_idx is None:
            print(f"[KR_MYSTERY] episode 열을 찾을 수 없습니다")
            return 1

        # episode 열 가져오기
        col_letter = chr(ord('A') + ep_idx)
        result = service.spreadsheets().values().get(
            spreadsheetId=sheet_id,
            range=f"'{UNIFIED_MYSTERY_SHEET}'!{col_letter}:{col_letter}"
        ).execute()

        values = result.get("values", [])

        # 숫자만 추출 (행1, 행2 제외)
        episodes = []
        for row in values[2:]:
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
        print(f"[KR_MYSTERY] 에피소드 번호 조회 오류: {e}")
        return 1


def generate_kr_opus_prompt(mystery_data: Dict[str, Any]) -> str:
    """
    한국 미스테리용 Opus 프롬프트 생성

    Args:
        mystery_data: 미스테리 기본 정보

    Returns:
        Opus 프롬프트 문자열
    """
    category_name = get_kr_category_name(mystery_data.get("category", ""))

    prompt = KR_MYSTERY_OPUS_PROMPT_TEMPLATE.format(
        title_ko=mystery_data.get("title_ko", ""),
        category=category_name,
        year=mystery_data.get("year", "알 수 없음"),
        hook=mystery_data.get("hook", ""),
        namu_url=mystery_data.get("url", ""),
        solved="해결됨" if mystery_data.get("solved") else "미해결",
        movie=mystery_data.get("movie", "없음"),
    )

    return prompt


def generate_kr_thumbnail_copy(mystery_data: Dict[str, Any]) -> str:
    """한국 미스테리 썸네일 문구 생성"""
    title_ko = mystery_data.get("title_ko", "")
    hook = mystery_data.get("hook", "")
    category_name = get_kr_category_name(mystery_data.get("category", ""))
    year = mystery_data.get("year", "")

    lines = [f"[한국 미스테리 썸네일 문구 추천]", ""]

    # 연도 있으면 포함
    if year:
        lines.append(f"1. {year}년, {title_ko}")
    else:
        lines.append(f"1. {title_ko}")

    lines.append(f"2. {hook}")
    lines.append(f"3. {category_name} - 아직 밝혀지지 않은 진실")

    # 영화화된 경우 추가
    if mystery_data.get("movie"):
        lines.append(f"4. 영화 '{mystery_data['movie']}'의 실제 사건")

    return "\n".join(lines)


def append_kr_mystery_row(
    service,
    sheet_id: str,
    mystery_data: Dict[str, Any],
    episode: int,
) -> bool:
    """
    한국 미스테리 데이터를 통합 시트(MYSTERY)에 추가

    Args:
        service: Google Sheets API 서비스
        sheet_id: 스프레드시트 ID
        mystery_data: 수집된 미스테리 데이터
        episode: 에피소드 번호

    Returns:
        성공 여부
    """
    try:
        # Opus 프롬프트 생성
        opus_prompt = generate_kr_opus_prompt(mystery_data)

        # 썸네일 문구 생성
        thumbnail_copy = generate_kr_thumbnail_copy(mystery_data)

        # 통합 시트용 행 데이터 (MYSTERY_OPUS_FIELDS 순서와 일치)
        opus_row = [
            str(episode),                              # [0] episode
            mystery_data.get("category", ""),          # [1] category
            "",                                        # [2] title_en (한국 미스테리는 없음)
            mystery_data.get("title_ko", ""),          # [3] title_ko
            mystery_data.get("url", ""),               # [4] wiki_url (나무위키 URL)
            mystery_data.get("summary", ""),           # [5] summary
            "",                                        # [6] full_content (Opus가 직접 수집)
            opus_prompt[:30000],                       # [7] opus_prompt (시트 셀 한계)
            thumbnail_copy,                            # [8] thumbnail_copy
            "준비",                                    # [9] status
        ]

        # 통합 시트에 저장
        append_to_unified_sheet(
            service,
            sheet_id,
            opus_row,
            MYSTERY_OPUS_FIELDS
        )

        print(f"[KR_MYSTERY] 에피소드 {episode} → '{UNIFIED_MYSTERY_SHEET}' 시트 저장 완료: {mystery_data.get('title_ko')}")
        return True

    except Exception as e:
        print(f"[KR_MYSTERY] 통합 시트 저장 오류: {e}")
        return False


def run_kr_mystery_pipeline(
    sheet_id: str,
    service,
    force: bool = False,
    max_add: int = 3,
    category: Optional[str] = None,
) -> Dict[str, Any]:
    """
    한국 미스테리 파이프라인 실행 (나무위키 기반)

    PENDING이 부족하면 자동으로 다음 한국 미스테리 추가

    Args:
        sheet_id: Google Sheets ID
        service: Google Sheets API 서비스 객체
        force: 강제 실행 (PENDING 충분해도 추가)
        max_add: 한 번에 추가할 최대 개수
        category: 특정 카테고리만 처리 (None이면 전체)

    Returns:
        실행 결과 딕셔너리
    """
    result = {
        "success": False,
        "type": "korean",
        "pending_before": 0,
        "pending_after": 0,
        "episodes_added": 0,
        "added_mysteries": [],
        "available_count": 0,
        "error": None,
    }

    try:
        print(f"[KR_MYSTERY] ========================================")
        print(f"[KR_MYSTERY] 한국 미스테리 파이프라인 시작")
        if category:
            print(f"[KR_MYSTERY] 카테고리 필터: {category}")
        print(f"[KR_MYSTERY] ========================================")

        # 1) 현재 상태 확인
        pending_count = count_kr_pending(service, sheet_id)
        result["pending_before"] = pending_count

        used_titles = get_used_kr_titles(service, sheet_id)
        available = list_available_kr_mysteries(used_titles, category)
        result["available_count"] = len(available)

        print(f"[KR_MYSTERY] 현재 준비: {pending_count}개, 사용 가능: {len(available)}개")

        # 2) 준비 충분하면 종료 (force가 아닌 경우)
        if not force and pending_count >= PENDING_TARGET_COUNT:
            print(f"[KR_MYSTERY] 준비 {PENDING_TARGET_COUNT}개 이상, 추가 불필요")
            result["success"] = True
            result["pending_after"] = pending_count
            return result

        # 3) 추가할 개수 계산
        need_count = PENDING_TARGET_COUNT - pending_count
        add_count = min(need_count, max_add, len(available))

        if add_count <= 0:
            if len(available) == 0:
                print(f"[KR_MYSTERY] 사용 가능한 한국 미스테리가 없습니다")
                result["error"] = "사용 가능한 한국 미스테리 없음"
            else:
                print(f"[KR_MYSTERY] 추가할 필요 없음")
                result["success"] = True

            result["pending_after"] = pending_count
            return result

        print(f"[KR_MYSTERY] {add_count}개 추가 예정")

        # 4) 에피소드 추가
        next_episode = get_next_kr_episode_number(service, sheet_id)

        for i in range(add_count):
            # 다음 미스테리 가져오기
            mystery = get_next_kr_mystery(used_titles, category)

            if not mystery:
                print(f"[KR_MYSTERY] 더 이상 가져올 미스테리가 없습니다")
                break

            # 시트에 추가
            if append_kr_mystery_row(service, sheet_id, mystery, next_episode):
                result["episodes_added"] += 1
                result["added_mysteries"].append({
                    "episode": next_episode,
                    "title_ko": mystery.get("title_ko"),
                    "category": mystery.get("category"),
                    "namu_url": mystery.get("url"),
                })
                used_titles.append(mystery.get("title_ko"))
                next_episode += 1

        # 5) 결과 정리
        result["pending_after"] = count_kr_pending(service, sheet_id)
        result["success"] = True

        print(f"[KR_MYSTERY] ========================================")
        print(f"[KR_MYSTERY] 완료: {result['episodes_added']}개 추가")
        print(f"[KR_MYSTERY] 준비: {result['pending_before']} → {result['pending_after']}")
        print(f"[KR_MYSTERY] ========================================")

    except Exception as e:
        result["error"] = str(e)
        print(f"[KR_MYSTERY] 파이프라인 오류: {e}")
        import traceback
        traceback.print_exc()

    return result


def test_collect_kr_mystery(title_ko: str = "개구리 소년 실종 사건") -> Dict[str, Any]:
    """
    테스트용: 단일 한국 미스테리 수집

    Args:
        title_ko: 한국 미스테리 제목

    Returns:
        수집 결과
    """
    print(f"[KR_MYSTERY] 테스트 수집: {title_ko}")

    # FEATURED_KR_MYSTERIES에서 정보 찾기
    mystery_info = None
    for m in FEATURED_KR_MYSTERIES:
        if m["title_ko"] == title_ko:
            mystery_info = m
            break

    if not mystery_info:
        return {
            "success": False,
            "error": f"'{title_ko}'를 목록에서 찾을 수 없습니다",
        }

    result = collect_kr_mystery_article(
        namu_title=mystery_info["namu_title"],
        title_ko=mystery_info["title_ko"],
        category=mystery_info.get("category"),
    )

    if result["success"]:
        result["year"] = mystery_info.get("year", "")
        result["hook"] = mystery_info.get("hook", "")
        result["movie"] = mystery_info.get("movie", "")
        result["solved"] = mystery_info.get("solved", False)

        # Opus 프롬프트도 생성
        result["opus_prompt"] = generate_kr_opus_prompt(result)

    return result
