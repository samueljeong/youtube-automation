"""
성경통독 YouTube SEO 최적화 모듈

YouTube 검색 최적화를 위한 제목/설명 생성
"""

from typing import Dict, Any, List

# ============================================================
# SEO 키워드 설정
# ============================================================

# 메인 키워드 (제목에 포함)
MAIN_KEYWORDS = ["성경통독", "성경낭독", "100일"]

# 해시태그 (설명 하단)
HASHTAGS_KO = [
    "100일성경통독", "성경통독", "개역개정", "성경낭독", "성경말씀",
    "기독교", "크리스천", "말씀묵상", "QT", "묵상", "성경듣기",
    "성경오디오", "매일성경", "통독", "성경읽기"
]

HASHTAGS_EN = [
    "Bible", "BibleReading", "Christian", "Scripture", "DailyBible",
    "KoreanBible", "BibleStudy"
]

# 구약/신약 책 목록
OLD_TESTAMENT_BOOKS = [
    "창세기", "출애굽기", "레위기", "민수기", "신명기",
    "여호수아", "사사기", "룻기", "사무엘상", "사무엘하",
    "열왕기상", "열왕기하", "역대상", "역대하", "에스라",
    "느헤미야", "에스더", "욥기", "시편", "잠언",
    "전도서", "아가", "이사야", "예레미야", "예레미야애가",
    "에스겔", "다니엘", "호세아", "요엘", "아모스",
    "오바댜", "요나", "미가", "나훔", "하박국",
    "스바냐", "학개", "스가랴", "말라기"
]


def get_testament(book: str) -> str:
    """구약/신약 구분"""
    return "구약" if book in OLD_TESTAMENT_BOOKS else "신약"


def generate_seo_title(
    day_number: int,
    book: str,
    start_chapter: int,
    end_chapter: int,
    max_length: int = 70
) -> str:
    """
    SEO 최적화된 YouTube 제목 생성

    YouTube 검색 알고리즘을 위한 최적화:
    - 메인 키워드를 앞에 배치
    - 60-70자 이내 권장
    - 숫자와 특수문자 활용
    - 명확한 콘텐츠 설명

    Args:
        day_number: Day 번호 (1-106)
        book: 성경 책 이름 (창세기, 마태복음 등)
        start_chapter: 시작 장
        end_chapter: 끝 장
        max_length: 최대 글자 수

    Returns:
        SEO 최적화된 제목
    """
    # 장 범위 텍스트
    if start_chapter == end_chapter:
        chapter_range = f"{start_chapter}장"
    else:
        chapter_range = f"{start_chapter}-{end_chapter}장"

    # 제목 형식 (검색 최적화)
    # 패턴: [100일 성경통독] Day X | 창세기 1-15장 성경낭독
    title = f"[100일 성경통독] Day {day_number} | {book} {chapter_range} 성경낭독"

    # 길이 체크
    if len(title) > max_length:
        # 축약 버전
        title = f"[성경통독] Day {day_number} | {book} {chapter_range}"

    return title


def generate_seo_description(
    day_number: int,
    book: str,
    start_chapter: int,
    end_chapter: int,
    total_verses: int,
    estimated_minutes: int,
    playlist_url: str = None
) -> str:
    """
    SEO 최적화된 YouTube 설명 생성

    YouTube SEO 요소:
    - 첫 2-3문장에 주요 키워드 포함 (검색 결과 미리보기)
    - 타임스탬프 (챕터 구분)
    - CTA (좋아요, 구독, 알림)
    - 해시태그 (최대 15개 권장)

    Args:
        day_number: Day 번호
        book: 성경 책 이름
        start_chapter: 시작 장
        end_chapter: 끝 장
        total_verses: 총 절 수
        estimated_minutes: 예상 재생 시간 (분)
        playlist_url: 재생목록 URL (선택)

    Returns:
        SEO 최적화된 설명
    """
    testament = get_testament(book)

    # 장 범위 텍스트
    if start_chapter == end_chapter:
        range_text = f"{book} {start_chapter}장"
    else:
        range_text = f"{book} {start_chapter}장~{end_chapter}장"

    # 해시태그 생성 (책 이름 + 구약/신약 포함)
    book_hashtag = f"#{book.replace(' ', '')}"
    testament_hashtag = f"#{testament}성경"
    all_hashtags = [book_hashtag, testament_hashtag] + [f"#{tag}" for tag in HASHTAGS_KO[:10]] + [f"#{tag}" for tag in HASHTAGS_EN[:5]]
    hashtag_line = " ".join(all_hashtags)

    # 설명 생성
    description = f"""📖 100일 성경통독 Day {day_number} - {range_text} | 개역개정 성경낭독

🙏 100일 만에 성경 66권을 완독하는 성경통독 프로젝트입니다.
차분한 목소리로 매일 약 20분씩 성경 말씀을 들으며 하나님과 동행하세요.

━━━━━━━━━━━━━━━━━━━━━━
📌 오늘의 말씀 정보
━━━━━━━━━━━━━━━━━━━━━━
• 📅 Day {day_number} / 106일
• 📚 범위: {range_text}
• 📖 분류: {testament}성경
• ⏱️ 재생시간: 약 {estimated_minutes}분
• 📝 총 {total_verses}절

━━━━━━━━━━━━━━━━━━━━━━
⏰ 추천 청취 시간
━━━━━━━━━━━━━━━━━━━━━━
• 🌅 아침 기도 시간 - 하루를 말씀으로 시작
• 🚗 출퇴근 시간 - 이동 중 말씀 묵상
• 🌙 취침 전 - 말씀과 함께 하루 마무리

━━━━━━━━━━━━━━━━━━━━━━
💝 구독과 좋아요 부탁드립니다!
━━━━━━━━━━━━━━━━━━━━━━
✅ 이 영상이 도움이 되셨다면 '좋아요'를 눌러주세요
✅ '구독'하시면 매일 새로운 말씀을 받아보실 수 있습니다
✅ '알림 설정🔔'을 해두시면 업로드 알림을 받으실 수 있습니다

"""

    # 재생목록 URL 추가
    if playlist_url:
        description += f"""━━━━━━━━━━━━━━━━━━━━━━
📚 전체 재생목록
━━━━━━━━━━━━━━━━━━━━━━
100일 성경통독 전체: {playlist_url}

"""

    # 해시태그 추가
    description += f"""━━━━━━━━━━━━━━━━━━━━━━

{hashtag_line}
"""

    return description


def generate_chapter_timestamps(
    chapters: List[Dict[str, Any]],
    verse_durations: List[float]
) -> str:
    """
    YouTube 타임스탬프 생성 (챕터별)

    YouTube는 설명에 타임스탬프가 있으면 자동으로 챕터로 인식합니다.
    형식: 0:00 시작
          5:23 창세기 2장
          10:45 창세기 3장

    Args:
        chapters: Episode.chapters 리스트
        verse_durations: 각 절의 재생 시간

    Returns:
        타임스탬프 문자열
    """
    timestamps = []
    current_time = 0.0
    verse_idx = 0

    for chapter in chapters:
        # 이 챕터 시작 시간
        chapter_start = current_time
        minutes = int(chapter_start // 60)
        seconds = int(chapter_start % 60)

        timestamps.append(f"{minutes}:{seconds:02d} {chapter['book']} {chapter['chapter']}장")

        # 이 챕터의 절 수만큼 시간 더하기
        for _ in chapter.get('verses', []):
            if verse_idx < len(verse_durations):
                current_time += verse_durations[verse_idx]
                verse_idx += 1

    return "\n".join(timestamps)


def validate_seo_title(title: str) -> Dict[str, Any]:
    """
    제목 SEO 검증

    Returns:
        {
            "valid": bool,
            "length": int,
            "warnings": List[str],
            "suggestions": List[str]
        }
    """
    warnings = []
    suggestions = []

    # 길이 체크
    if len(title) > 70:
        warnings.append(f"제목이 너무 깁니다 ({len(title)}자). 60-70자 권장.")
    elif len(title) < 30:
        warnings.append(f"제목이 너무 짧습니다 ({len(title)}자). 30자 이상 권장.")

    # 키워드 체크
    has_main_keyword = any(kw in title for kw in ["성경통독", "성경낭독", "성경"])
    if not has_main_keyword:
        suggestions.append("'성경통독' 또는 '성경낭독' 키워드 추가 권장")

    # 숫자 체크 (Day 번호)
    if "Day" not in title and "일차" not in title and "DAY" not in title:
        suggestions.append("Day 번호 추가 권장 (예: Day 1)")

    return {
        "valid": len(warnings) == 0,
        "length": len(title),
        "warnings": warnings,
        "suggestions": suggestions
    }


def validate_seo_description(description: str) -> Dict[str, Any]:
    """
    설명 SEO 검증

    Returns:
        {
            "valid": bool,
            "length": int,
            "warnings": List[str],
            "suggestions": List[str]
        }
    """
    warnings = []
    suggestions = []

    # 길이 체크
    if len(description) < 200:
        warnings.append(f"설명이 너무 짧습니다 ({len(description)}자). 200자 이상 권장.")
    elif len(description) > 5000:
        warnings.append(f"설명이 너무 깁니다 ({len(description)}자). 5000자 이하 권장.")

    # 해시태그 체크
    hashtag_count = description.count("#")
    if hashtag_count < 5:
        suggestions.append(f"해시태그가 적습니다 ({hashtag_count}개). 10-15개 권장.")
    elif hashtag_count > 30:
        warnings.append(f"해시태그가 너무 많습니다 ({hashtag_count}개). 15개 이하 권장.")

    # CTA 체크
    if "구독" not in description and "좋아요" not in description:
        suggestions.append("구독/좋아요 CTA 추가 권장")

    return {
        "valid": len(warnings) == 0,
        "length": len(description),
        "hashtag_count": description.count("#"),
        "warnings": warnings,
        "suggestions": suggestions
    }
