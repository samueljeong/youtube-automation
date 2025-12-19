#!/usr/bin/env python3
"""
통합 시트 생성 스크립트

NEWS, HISTORY, MYSTERY 3개의 통합 시트를 생성합니다.
- 행 1: 채널ID 설정
- 행 2: 헤더 (수집 데이터 + 영상 자동화)

실행: python scripts/create_unified_sheets.py
"""

import os
import sys
import json

# 프로젝트 루트 추가
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from google.oauth2 import service_account
from googleapiclient.discovery import build


# ============================================================
# 시트 설정
# ============================================================

UNIFIED_SHEETS = {
    "NEWS": {
        "channel_id": "",  # 나중에 설정
        "description": "뉴스 채널 - 수집부터 영상 업로드까지",
        # 수집 영역 헤더
        "collect_headers": [
            "run_id",           # 실행 날짜
            "selected_rank",    # 순위 (1, 2, 3)
            "category",         # 카테고리 (경제/정책/사회/국제)
            "issue_one_line",   # 이슈 한 줄 요약
            "core_points",      # 핵심포인트 (LLM 생성)
            "brief",            # 대본 지시문
            "thumbnail_copy",   # 썸네일 문구 추천
            "opus_prompt_pack", # Opus 프롬프트
        ],
    },
    "HISTORY": {
        "channel_id": "",  # 나중에 설정
        "description": "역사 채널 - 수집부터 영상 업로드까지",
        # 수집 영역 헤더
        "collect_headers": [
            "era",              # 시대
            "episode_slot",     # 슬롯 번호
            "structure_role",   # 형성기/제도기/변동기/유산기/연결기
            "core_question",    # 핵심 질문
            "facts",            # 관찰 가능한 사실
            "human_choices",    # 인간의 선택 가능 지점
            "impact_candidates",# 구조 변화 후보
            "source_url",       # 출처 URL
            "opus_prompt_pack", # Opus 프롬프트
            "thumbnail_copy",   # 썸네일 문구 추천
        ],
    },
    "MYSTERY": {
        "channel_id": "",  # 나중에 설정
        "description": "미스테리 채널 - 수집부터 영상 업로드까지",
        # 수집 영역 헤더
        "collect_headers": [
            "episode",          # 에피소드 번호
            "category",         # 카테고리 (실종/사망/장소/사건/현상)
            "title_en",         # 영문 제목
            "title_ko",         # 한글 제목
            "wiki_url",         # 위키백과 URL
            "summary",          # 사건 요약
            "full_content",     # 전체 내용 (Opus용)
            "opus_prompt",      # Opus 프롬프트
            "thumbnail_copy",   # 썸네일 문구 추천
        ],
    },
}

# 영상 자동화 공통 헤더 (모든 시트에 추가)
VIDEO_AUTOMATION_HEADERS = [
    "상태",             # 대기/처리중/완료/실패
    "대본",             # 영상 대본 (★ 핵심)
    "제목(GPT생성)",    # GPT가 생성한 제목
    "제목(입력)",       # 사용자 입력 제목 (GPT 대신 사용)
    "썸네일문구(입력)", # 사용자 입력 썸네일 문구
    "공개설정",         # public/private/unlisted
    "예약시간",         # YouTube 예약 공개 시간
    "플레이리스트ID",   # YouTube 플레이리스트 ID
    "음성",             # TTS 음성 설정
    "영상URL",          # 업로드된 YouTube URL
    "쇼츠URL",          # 쇼츠 URL
    "제목2",            # 대안 제목 (CTR 자동화용)
    "제목3",            # 대안 제목 (CTR 자동화용)
    "비용",             # 생성 비용
    "에러메시지",       # 실패 시 에러
    "작업시간",         # 파이프라인 실행 시간
]


def get_sheets_service():
    """Google Sheets API 서비스 객체 반환"""
    creds_json = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON")
    if not creds_json:
        raise ValueError("GOOGLE_SERVICE_ACCOUNT_JSON 환경변수가 설정되지 않았습니다")

    creds_data = json.loads(creds_json)
    creds = service_account.Credentials.from_service_account_info(
        creds_data,
        scopes=["https://www.googleapis.com/auth/spreadsheets"]
    )
    return build("sheets", "v4", credentials=creds)


def create_unified_sheet(service, spreadsheet_id: str, sheet_name: str, config: dict) -> bool:
    """
    통합 시트 생성

    Args:
        service: Google Sheets API 서비스
        spreadsheet_id: 스프레드시트 ID
        sheet_name: 시트 이름 (NEWS, HISTORY, MYSTERY)
        config: 시트 설정 (collect_headers, channel_id 등)

    Returns:
        True: 성공, False: 이미 존재
    """
    try:
        # 1) 기존 시트 목록 확인
        spreadsheet = service.spreadsheets().get(
            spreadsheetId=spreadsheet_id
        ).execute()

        existing_sheets = [
            sheet['properties']['title']
            for sheet in spreadsheet.get('sheets', [])
        ]

        if sheet_name in existing_sheets:
            print(f"[UNIFIED] 시트 '{sheet_name}' 이미 존재 - 건너뜀")
            return False

        # 2) 시트 생성
        requests = [{
            "addSheet": {
                "properties": {
                    "title": sheet_name,
                }
            }
        }]

        service.spreadsheets().batchUpdate(
            spreadsheetId=spreadsheet_id,
            body={"requests": requests}
        ).execute()

        print(f"[UNIFIED] 시트 '{sheet_name}' 생성 완료")

        # 3) 행 1: 채널ID 설정
        channel_id = config.get("channel_id", "")
        row1 = ["채널ID", channel_id]

        # 4) 행 2: 헤더 (수집 + 영상 자동화)
        collect_headers = config.get("collect_headers", [])
        row2 = collect_headers + VIDEO_AUTOMATION_HEADERS

        # 5) 시트에 쓰기
        service.spreadsheets().values().update(
            spreadsheetId=spreadsheet_id,
            range=f"{sheet_name}!A1",
            valueInputOption="RAW",
            body={"values": [row1, row2]}
        ).execute()

        print(f"[UNIFIED] 시트 '{sheet_name}' 헤더 설정 완료 ({len(row2)}개 열)")
        print(f"          - 수집 영역: {len(collect_headers)}개")
        print(f"          - 영상 자동화: {len(VIDEO_AUTOMATION_HEADERS)}개")

        return True

    except Exception as e:
        print(f"[UNIFIED] 시트 '{sheet_name}' 생성 실패: {e}")
        raise


def main():
    """메인 함수"""
    # 환경변수 확인
    spreadsheet_id = os.environ.get("AUTOMATION_SHEET_ID") or os.environ.get("NEWS_SHEET_ID")
    if not spreadsheet_id:
        print("[ERROR] AUTOMATION_SHEET_ID 또는 NEWS_SHEET_ID 환경변수를 설정하세요")
        sys.exit(1)

    print(f"[UNIFIED] 스프레드시트 ID: {spreadsheet_id}")
    print(f"[UNIFIED] 생성할 시트: {', '.join(UNIFIED_SHEETS.keys())}")
    print()

    # Google Sheets 서비스 생성
    try:
        service = get_sheets_service()
    except Exception as e:
        print(f"[ERROR] Google Sheets 인증 실패: {e}")
        sys.exit(1)

    # 각 시트 생성
    created_count = 0
    for sheet_name, config in UNIFIED_SHEETS.items():
        print(f"\n[UNIFIED] === {sheet_name} 시트 생성 ===")
        try:
            if create_unified_sheet(service, spreadsheet_id, sheet_name, config):
                created_count += 1
        except Exception as e:
            print(f"[ERROR] {sheet_name} 시트 생성 실패: {e}")

    print(f"\n[UNIFIED] 완료! {created_count}개 시트 생성됨")

    # 결과 출력
    print("\n" + "=" * 50)
    print("생성된 시트 구조:")
    print("=" * 50)
    for sheet_name, config in UNIFIED_SHEETS.items():
        collect_headers = config.get("collect_headers", [])
        total_headers = collect_headers + VIDEO_AUTOMATION_HEADERS
        print(f"\n[{sheet_name}]")
        print(f"  행 1: 채널ID | (채널 ID 입력)")
        print(f"  행 2: 헤더 ({len(total_headers)}개 열)")
        print(f"        - 수집: {', '.join(collect_headers[:3])}...")
        print(f"        - 영상: 상태, 대본, 제목(GPT생성)...")


if __name__ == "__main__":
    main()
