"""
Sermon Pipeline 설정

헤더, 분량 기준, 상태값 등 설정
"""

# Google Sheets 헤더 (행 1)
SERMON_HEADERS = [
    "상태",       # A: 요청/처리중/완료/실패
    "본문",       # B: 성경 본문 (예: "요한복음 3:16")
    "요청사항",   # C: 설교 방향, 분량, 대상 등
    "설교문",     # D: Claude Code가 작성한 설교문
    "피드백",     # E: 수정 요청 시 피드백
    "수정본",     # F: 피드백 반영한 수정본
    "작성일시",   # G: 완료 시간
    "에러메시지", # H: 실패 시 에러
]

# 헤더 인덱스 (0-based)
COL_STATUS = 0       # 상태
COL_SCRIPTURE = 1    # 본문
COL_REQUEST = 2      # 요청사항
COL_SERMON = 3       # 설교문
COL_FEEDBACK = 4     # 피드백
COL_REVISION = 5     # 수정본
COL_DATETIME = 6     # 작성일시
COL_ERROR = 7        # 에러메시지

# 상태값
STATUS_REQUEST = "요청"
STATUS_REVISION_REQUEST = "수정요청"
STATUS_PROCESSING = "처리중"
STATUS_COMPLETE = "완료"
STATUS_FAILED = "실패"

# 분당 글자 수 (한국어 TTS 기준)
CHARS_PER_MINUTE = 250  # 설교는 천천히 말하므로 250자/분

# 예배 종류별 분량 (분)
SERMON_LENGTH_BY_TYPE = {
    "새벽": 10,
    "새벽기도": 10,
    "수요": 20,
    "수요예배": 20,
    "청년": 25,
    "청년부": 25,
    "주일": 30,
    "주일예배": 30,
    "금요": 20,
    "금요철야": 30,
    "특새": 15,       # 특별새벽기도
    "부흥회": 40,
}

# 기본 분량 (매칭되지 않을 때)
DEFAULT_SERMON_LENGTH = 20  # 20분


def get_sermon_length(sheet_name: str, request: str = "") -> int:
    """
    시트 이름과 요청사항에서 설교 분량(분) 결정

    Args:
        sheet_name: 시트 탭 이름 (예: "새벽기도", "청년부")
        request: 요청사항 (예: "15분 분량으로")

    Returns:
        설교 분량 (분)
    """
    # 1. 요청사항에서 분량 추출 (예: "15분", "20분 분량")
    if request:
        import re
        match = re.search(r'(\d+)\s*분', request)
        if match:
            return int(match.group(1))

    # 2. 시트 이름으로 분량 결정
    for key, length in SERMON_LENGTH_BY_TYPE.items():
        if key in sheet_name:
            return length

    # 3. 기본값
    return DEFAULT_SERMON_LENGTH


def get_target_chars(sheet_name: str, request: str = "") -> int:
    """
    목표 글자 수 계산

    Args:
        sheet_name: 시트 탭 이름
        request: 요청사항

    Returns:
        목표 글자 수
    """
    minutes = get_sermon_length(sheet_name, request)
    return minutes * CHARS_PER_MINUTE
