"""
성경통독 파이프라인 설정

- 개역개정 성경 기반
- TTS/영상 설정
- Google Sheets 연동
"""

import os
from typing import Dict, List, Any


# ============================================================
# TTS 설정
# ============================================================

# TTS 음성 (성경 낭독에 어울리는 차분한 목소리)
BIBLE_TTS_VOICE = "chirp3:Charon"

# 말하기 속도 (성경 낭독은 천천히)
BIBLE_TTS_SPEAKING_RATE = 0.9


# ============================================================
# 영상 설정
# ============================================================

# 영상 길이 (분)
BIBLE_VIDEO_LENGTH_MINUTES = 20

# 한국어 TTS 기준: 910자/분
BIBLE_CHARS_PER_MINUTE = 910

# 목표 글자 수 (20분 기준 약 18,200자)
BIBLE_TARGET_CHARS = BIBLE_VIDEO_LENGTH_MINUTES * BIBLE_CHARS_PER_MINUTE


# ============================================================
# 성경 데이터 설정
# ============================================================

# 성경 JSON 파일 경로
BIBLE_JSON_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
    "korean_bible_gae.json"
)

# 성경 66권 목록 (구약 39권 + 신약 27권)
BIBLE_BOOKS: List[Dict[str, Any]] = [
    # ===== 구약 (39권) =====
    # 모세오경 (5권)
    {"id": 1, "name": "창세기", "name_en": "Genesis", "chapters": 50, "testament": "구약"},
    {"id": 2, "name": "출애굽기", "name_en": "Exodus", "chapters": 40, "testament": "구약"},
    {"id": 3, "name": "레위기", "name_en": "Leviticus", "chapters": 27, "testament": "구약"},
    {"id": 4, "name": "민수기", "name_en": "Numbers", "chapters": 36, "testament": "구약"},
    {"id": 5, "name": "신명기", "name_en": "Deuteronomy", "chapters": 34, "testament": "구약"},
    # 역사서 (12권)
    {"id": 6, "name": "여호수아", "name_en": "Joshua", "chapters": 24, "testament": "구약"},
    {"id": 7, "name": "사사기", "name_en": "Judges", "chapters": 21, "testament": "구약"},
    {"id": 8, "name": "룻기", "name_en": "Ruth", "chapters": 4, "testament": "구약"},
    {"id": 9, "name": "사무엘상", "name_en": "1 Samuel", "chapters": 31, "testament": "구약"},
    {"id": 10, "name": "사무엘하", "name_en": "2 Samuel", "chapters": 24, "testament": "구약"},
    {"id": 11, "name": "열왕기상", "name_en": "1 Kings", "chapters": 22, "testament": "구약"},
    {"id": 12, "name": "열왕기하", "name_en": "2 Kings", "chapters": 25, "testament": "구약"},
    {"id": 13, "name": "역대상", "name_en": "1 Chronicles", "chapters": 29, "testament": "구약"},
    {"id": 14, "name": "역대하", "name_en": "2 Chronicles", "chapters": 36, "testament": "구약"},
    {"id": 15, "name": "에스라", "name_en": "Ezra", "chapters": 10, "testament": "구약"},
    {"id": 16, "name": "느헤미야", "name_en": "Nehemiah", "chapters": 13, "testament": "구약"},
    {"id": 17, "name": "에스더", "name_en": "Esther", "chapters": 10, "testament": "구약"},
    # 시가서 (5권)
    {"id": 18, "name": "욥기", "name_en": "Job", "chapters": 42, "testament": "구약"},
    {"id": 19, "name": "시편", "name_en": "Psalms", "chapters": 150, "testament": "구약"},
    {"id": 20, "name": "잠언", "name_en": "Proverbs", "chapters": 31, "testament": "구약"},
    {"id": 21, "name": "전도서", "name_en": "Ecclesiastes", "chapters": 12, "testament": "구약"},
    {"id": 22, "name": "아가", "name_en": "Song of Solomon", "chapters": 8, "testament": "구약"},
    # 대선지서 (5권)
    {"id": 23, "name": "이사야", "name_en": "Isaiah", "chapters": 66, "testament": "구약"},
    {"id": 24, "name": "예레미야", "name_en": "Jeremiah", "chapters": 52, "testament": "구약"},
    {"id": 25, "name": "예레미야애가", "name_en": "Lamentations", "chapters": 5, "testament": "구약"},
    {"id": 26, "name": "에스겔", "name_en": "Ezekiel", "chapters": 48, "testament": "구약"},
    {"id": 27, "name": "다니엘", "name_en": "Daniel", "chapters": 12, "testament": "구약"},
    # 소선지서 (12권)
    {"id": 28, "name": "호세아", "name_en": "Hosea", "chapters": 14, "testament": "구약"},
    {"id": 29, "name": "요엘", "name_en": "Joel", "chapters": 3, "testament": "구약"},
    {"id": 30, "name": "아모스", "name_en": "Amos", "chapters": 9, "testament": "구약"},
    {"id": 31, "name": "오바댜", "name_en": "Obadiah", "chapters": 1, "testament": "구약"},
    {"id": 32, "name": "요나", "name_en": "Jonah", "chapters": 4, "testament": "구약"},
    {"id": 33, "name": "미가", "name_en": "Micah", "chapters": 7, "testament": "구약"},
    {"id": 34, "name": "나훔", "name_en": "Nahum", "chapters": 3, "testament": "구약"},
    {"id": 35, "name": "하박국", "name_en": "Habakkuk", "chapters": 3, "testament": "구약"},
    {"id": 36, "name": "스바냐", "name_en": "Zephaniah", "chapters": 3, "testament": "구약"},
    {"id": 37, "name": "학개", "name_en": "Haggai", "chapters": 2, "testament": "구약"},
    {"id": 38, "name": "스가랴", "name_en": "Zechariah", "chapters": 14, "testament": "구약"},
    {"id": 39, "name": "말라기", "name_en": "Malachi", "chapters": 4, "testament": "구약"},

    # ===== 신약 (27권) =====
    # 복음서 (4권)
    {"id": 40, "name": "마태복음", "name_en": "Matthew", "chapters": 28, "testament": "신약"},
    {"id": 41, "name": "마가복음", "name_en": "Mark", "chapters": 16, "testament": "신약"},
    {"id": 42, "name": "누가복음", "name_en": "Luke", "chapters": 24, "testament": "신약"},
    {"id": 43, "name": "요한복음", "name_en": "John", "chapters": 21, "testament": "신약"},
    # 역사서 (1권)
    {"id": 44, "name": "사도행전", "name_en": "Acts", "chapters": 28, "testament": "신약"},
    # 바울서신 (13권)
    {"id": 45, "name": "로마서", "name_en": "Romans", "chapters": 16, "testament": "신약"},
    {"id": 46, "name": "고린도전서", "name_en": "1 Corinthians", "chapters": 16, "testament": "신약"},
    {"id": 47, "name": "고린도후서", "name_en": "2 Corinthians", "chapters": 13, "testament": "신약"},
    {"id": 48, "name": "갈라디아서", "name_en": "Galatians", "chapters": 6, "testament": "신약"},
    {"id": 49, "name": "에베소서", "name_en": "Ephesians", "chapters": 6, "testament": "신약"},
    {"id": 50, "name": "빌립보서", "name_en": "Philippians", "chapters": 4, "testament": "신약"},
    {"id": 51, "name": "골로새서", "name_en": "Colossians", "chapters": 4, "testament": "신약"},
    {"id": 52, "name": "데살로니가전서", "name_en": "1 Thessalonians", "chapters": 5, "testament": "신약"},
    {"id": 53, "name": "데살로니가후서", "name_en": "2 Thessalonians", "chapters": 3, "testament": "신약"},
    {"id": 54, "name": "디모데전서", "name_en": "1 Timothy", "chapters": 6, "testament": "신약"},
    {"id": 55, "name": "디모데후서", "name_en": "2 Timothy", "chapters": 4, "testament": "신약"},
    {"id": 56, "name": "디도서", "name_en": "Titus", "chapters": 3, "testament": "신약"},
    {"id": 57, "name": "빌레몬서", "name_en": "Philemon", "chapters": 1, "testament": "신약"},
    # 일반서신 (8권)
    {"id": 58, "name": "히브리서", "name_en": "Hebrews", "chapters": 13, "testament": "신약"},
    {"id": 59, "name": "야고보서", "name_en": "James", "chapters": 5, "testament": "신약"},
    {"id": 60, "name": "베드로전서", "name_en": "1 Peter", "chapters": 5, "testament": "신약"},
    {"id": 61, "name": "베드로후서", "name_en": "2 Peter", "chapters": 3, "testament": "신약"},
    {"id": 62, "name": "요한일서", "name_en": "1 John", "chapters": 5, "testament": "신약"},
    {"id": 63, "name": "요한이서", "name_en": "2 John", "chapters": 1, "testament": "신약"},
    {"id": 64, "name": "요한삼서", "name_en": "3 John", "chapters": 1, "testament": "신약"},
    {"id": 65, "name": "유다서", "name_en": "Jude", "chapters": 1, "testament": "신약"},
    # 예언서 (1권)
    {"id": 66, "name": "요한계시록", "name_en": "Revelation", "chapters": 22, "testament": "신약"},
]


# ============================================================
# Google Sheets 설정
# ============================================================

# 시트 이름
BIBLE_SHEET_NAME = "BIBLE"

# 시트 헤더
BIBLE_SHEET_HEADERS = [
    "에피소드",         # 예: EP001
    "책",              # 예: 창세기
    "시작장",           # 예: 1
    "끝장",             # 예: 15
    "예상시간(분)",     # 예: 19.8
    "글자수",           # 예: 18041
    "상태",             # 대기/처리중/완료/실패
    "제목",             # 영상 제목 (자동 생성 또는 수동 입력)
    "음성",             # TTS 음성 (기본: chirp3:Charon)
    "공개설정",         # public/private/unlisted
    "예약시간",         # YouTube 예약 공개 시간
    "플레이리스트ID",   # YouTube 플레이리스트 ID
    "영상URL",          # 업로드된 YouTube URL
    "에러메시지",       # 실패 시 에러 메시지
    "작업시간",         # 처리 소요 시간
    "생성일",           # 행 생성 날짜
]


# ============================================================
# 화면 레이아웃 설정
# ============================================================

# 자막 스타일 (절 번호 포함)
SUBTITLE_STYLE = {
    "font_size": 48,
    "font_color": "#FFFFFF",
    "background_color": "#000000",
    "background_opacity": 0.7,
    "position": "bottom",  # bottom, center
    "verse_number_color": "#FFD700",  # 절 번호 색상 (골드)
}

# 배경 설정
BACKGROUND_STYLE = {
    "type": "image",  # image, video, gradient
    "default_image": "static/images/bible_background.jpg",
    "gradient_colors": ["#1a1a2e", "#16213e"],  # 어두운 블루 그라데이션
}

# 장 표시 스타일 (예: "창세기 1장")
CHAPTER_TITLE_STYLE = {
    "font_size": 64,
    "font_color": "#FFD700",
    "duration": 3,  # 초
    "position": "center",
}


# ============================================================
# 유틸리티 함수
# ============================================================

def get_book_by_id(book_id: int) -> Dict[str, Any]:
    """책 ID로 책 정보 조회"""
    for book in BIBLE_BOOKS:
        if book["id"] == book_id:
            return book
    return None


def get_book_by_name(name: str) -> Dict[str, Any]:
    """책 이름으로 책 정보 조회"""
    for book in BIBLE_BOOKS:
        if book["name"] == name:
            return book
    return None


def calculate_episode_range(target_chars: int = BIBLE_TARGET_CHARS) -> Dict[str, Any]:
    """
    목표 글자 수에 맞는 에피소드 범위 계산

    Returns:
        {
            "book": "창세기",
            "start_chapter": 1,
            "end_chapter": 15,
            "total_chars": 18041,
            "estimated_minutes": 19.8
        }
    """
    # 이 함수는 run.py에서 성경 JSON을 로드한 후 구현
    pass
