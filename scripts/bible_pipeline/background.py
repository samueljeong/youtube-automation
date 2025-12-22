"""
성경통독 배경 이미지 생성 모듈

Gemini 3 Pro를 사용하여 66권 각각의 배경 이미지 생성
- 구약 (39권): 파란색 계열
- 신약 (27권): 빨간색 계열
"""

import os
import sys
from typing import Dict, Any, Optional, List

# 상위 디렉토리 import를 위한 경로 추가
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from image.gemini import generate_image, GEMINI_PRO


# ============================================================
# 66권 배경 이미지 프롬프트
# ============================================================

# 공통 스타일 지시문 (자막 가독성 최우선)
COMMON_STYLE = """
CRITICAL STYLE REQUIREMENTS:
- EXTREMELY SIMPLE and MINIMAL - this is a TEXT BACKGROUND, not artwork
- Solid or very soft gradient background ONLY
- NO complex patterns, NO detailed imagery, NO distracting elements
- NO text, NO letters, NO words, NO characters
- MUTED, LOW CONTRAST colors - nothing bright or eye-catching
- The CENTER 80% of image must be very plain for text readability
- Only very subtle texture or color variation allowed at edges
- Think of it like a presentation slide background - BORING is GOOD
- White/light colored text will be placed on top - ensure good contrast
- Professional, calming, unobtrusive aesthetic
"""

# 구약 39권 배경 프롬프트 (파란색 계열) - 매우 심플
OLD_TESTAMENT_PROMPTS = {
    # 모세오경 - 진한 네이비 그라데이션
    "창세기": {"color": "deep navy blue (#1a237e) to dark blue (#283593)", "tone": "cosmic, beginning"},
    "출애굽기": {"color": "royal blue (#1565c0) to navy (#0d47a1)", "tone": "journey, liberation"},
    "레위기": {"color": "dark blue (#0d47a1) to medium blue (#1976d2)", "tone": "sacred, holy"},
    "민수기": {"color": "midnight blue (#191970) to slate blue (#4a5568)", "tone": "wilderness"},
    "신명기": {"color": "sapphire blue (#0f52ba) to ocean blue (#006994)", "tone": "covenant"},

    # 역사서 - 청록/틸 그라데이션
    "여호수아": {"color": "teal (#008080) to dark cyan (#006666)", "tone": "conquest"},
    "사사기": {"color": "dark teal (#004d4d) to steel blue (#4682b4)", "tone": "cycles"},
    "룻기": {"color": "soft teal (#4db6ac) to blue gray (#607d8b)", "tone": "harvest, loyalty"},
    "사무엘상": {"color": "royal blue (#4169e1) to purple blue (#5d3fd3)", "tone": "kingdom begins"},
    "사무엘하": {"color": "deep purple blue (#3f51b5) to indigo (#4b0082)", "tone": "reign"},
    "열왕기상": {"color": "temple blue (#2196f3) to deep blue (#1565c0)", "tone": "temple glory"},
    "열왕기하": {"color": "stormy blue (#4a6fa5) to dark slate (#2f4f4f)", "tone": "decline"},
    "역대상": {"color": "ancient blue (#3a5a8c) to gray blue (#536878)", "tone": "genealogy"},
    "역대하": {"color": "blue slate (#6a8caf) to stone blue (#5b7c99)", "tone": "kings"},
    "에스라": {"color": "dawn blue (#87ceeb) to soft blue (#6495ed)", "tone": "return"},
    "느헤미야": {"color": "determined blue (#4169e1) to stone gray (#708090)", "tone": "rebuild"},
    "에스더": {"color": "persian blue (#1c39bb) to royal purple (#7851a9)", "tone": "courage"},

    # 시가서 - 보라/자주 그라데이션
    "욥기": {"color": "deep purple (#4a148c) to midnight (#191970)", "tone": "suffering"},
    "시편": {"color": "worship purple (#7b1fa2) to blue violet (#8a2be2)", "tone": "praise"},
    "잠언": {"color": "wisdom blue (#5c6bc0) to deep indigo (#3949ab)", "tone": "wisdom"},
    "전도서": {"color": "contemplative gray (#546e7a) to slate (#607d8b)", "tone": "meaning"},
    "아가": {"color": "soft mauve (#9c7bb8) to dusty rose (#bc8f8f)", "tone": "love"},

    # 대선지서 - 진한 파란색
    "이사야": {"color": "prophetic blue (#1e3a8a) to messianic (#3b82f6)", "tone": "prophecy"},
    "예레미야": {"color": "tearful blue (#1e40af) to hopeful (#60a5fa)", "tone": "lament"},
    "예레미야애가": {"color": "mourning blue (#1e3a5f) to compassion (#3b5998)", "tone": "mourning"},
    "에스겔": {"color": "vision blue (#0ea5e9) to mystical (#0284c7)", "tone": "visions"},
    "다니엘": {"color": "royal blue (#2563eb) to apocalyptic (#1d4ed8)", "tone": "kingdoms"},

    # 소선지서 - 하늘색/청록 그라데이션
    "호세아": {"color": "forgiving blue (#38bdf8) to teal (#14b8a6)", "tone": "restoration"},
    "요엘": {"color": "spirit blue (#0ea5e9) to flame (#f97316)", "tone": "outpouring"},
    "아모스": {"color": "justice blue (#0369a1) to earth (#78716c)", "tone": "justice"},
    "오바댜": {"color": "judgment blue (#1e40af) to desert (#a8a29e)", "tone": "judgment"},
    "요나": {"color": "ocean blue (#0077be) to sea green (#20b2aa)", "tone": "mercy"},
    "미가": {"color": "humble blue (#6366f1) to soft (#a5b4fc)", "tone": "humility"},
    "나훔": {"color": "righteous blue (#1d4ed8) to gray (#6b7280)", "tone": "justice"},
    "하박국": {"color": "watchful blue (#3b82f6) to dawn (#fcd34d)", "tone": "faith"},
    "스바냐": {"color": "solemn blue (#1e3a8a) to soft (#93c5fd)", "tone": "remnant"},
    "학개": {"color": "building blue (#0284c7) to glory (#fbbf24)", "tone": "rebuild"},
    "스가랴": {"color": "visionary blue (#2563eb) to olive (#84cc16)", "tone": "visions"},
    "말라기": {"color": "final blue (#1e40af) to sunrise (#fb923c)", "tone": "messenger"},
}

# 신약 27권 배경 프롬프트 (빨간색 계열) - 매우 심플
NEW_TESTAMENT_PROMPTS = {
    # 복음서 - 진한 빨강 그라데이션
    "마태복음": {"color": "deep crimson (#b71c1c) to dark red (#c62828)", "tone": "king"},
    "마가복음": {"color": "action red (#d32f2f) to maroon (#800000)", "tone": "servant"},
    "누가복음": {"color": "compassionate red (#e53935) to warm (#ef5350)", "tone": "savior"},
    "요한복음": {"color": "divine red (#c62828) to light (#ef9a9a)", "tone": "word"},

    # 역사서
    "사도행전": {"color": "fire red (#ff5722) to orange (#e64a19)", "tone": "spirit"},

    # 바울서신 - 빨강/주황 그라데이션
    "로마서": {"color": "doctrinal red (#bf360c) to rust (#d84315)", "tone": "righteousness"},
    "고린도전서": {"color": "love red (#c62828) to coral (#ff8a65)", "tone": "love, unity"},
    "고린도후서": {"color": "comfort red (#e64a19) to warm (#ffab91)", "tone": "comfort"},
    "갈라디아서": {"color": "freedom red (#ff5722) to gold (#ffc107)", "tone": "freedom"},
    "에베소서": {"color": "heavenly red (#d32f2f) to purple (#9c27b0)", "tone": "church"},
    "빌립보서": {"color": "joyful red (#e91e63) to pink (#f48fb1)", "tone": "joy"},
    "골로새서": {"color": "supreme red (#c62828) to cosmic (#3f51b5)", "tone": "supremacy"},
    "데살로니가전서": {"color": "hopeful red (#ef5350) to sky (#90caf9)", "tone": "return"},
    "데살로니가후서": {"color": "enduring red (#d32f2f) to gray (#78909c)", "tone": "endurance"},
    "디모데전서": {"color": "pastoral red (#e53935) to earth (#8d6e63)", "tone": "pastoral"},
    "디모데후서": {"color": "final red (#c62828) to gold (#ffd54f)", "tone": "crown"},
    "디도서": {"color": "teaching red (#d84315) to sea (#4dd0e1)", "tone": "doctrine"},
    "빌레몬서": {"color": "reconciling red (#ef5350) to warm brown (#a1887f)", "tone": "brotherhood"},

    # 일반서신 - 분홍/자주색 그라데이션
    "히브리서": {"color": "superior red (#880e4f) to gold (#ffca28)", "tone": "better"},
    "야고보서": {"color": "practical red (#ad1457) to earth (#795548)", "tone": "works"},
    "베드로전서": {"color": "hopeful red (#c2185b) to silver (#b0bec5)", "tone": "suffering hope"},
    "베드로후서": {"color": "warning red (#d81b60) to storm (#546e7a)", "tone": "warning"},
    "요한일서": {"color": "love red (#e91e63) to light (#fff9c4)", "tone": "love, light"},
    "요한이서": {"color": "truth red (#ec407a) to pure (#f5f5f5)", "tone": "truth"},
    "요한삼서": {"color": "hospitality red (#f06292) to warm (#ffe0b2)", "tone": "hospitality"},
    "유다서": {"color": "contending red (#ad1457) to dark (#37474f)", "tone": "contend"},

    # 예언서
    "요한계시록": {"color": "glorious red (#b71c1c) to gold (#ffd700)", "tone": "throne, victory"},
}


def get_background_prompt(book_name: str) -> str:
    """
    책 이름에 맞는 배경 이미지 생성 프롬프트 반환

    Args:
        book_name: 성경 책 이름 (예: 창세기)

    Returns:
        Gemini 프롬프트 문자열
    """
    # 구약/신약 확인
    if book_name in OLD_TESTAMENT_PROMPTS:
        book_info = OLD_TESTAMENT_PROMPTS[book_name]
        testament = "Old Testament"
    elif book_name in NEW_TESTAMENT_PROMPTS:
        book_info = NEW_TESTAMENT_PROMPTS[book_name]
        testament = "New Testament"
    else:
        # 기본 프롬프트
        return f"""
Create an EXTREMELY SIMPLE, plain gradient background image for Bible reading video.
{COMMON_STYLE}
Color: soft blue gradient
Style: Like a PowerPoint slide background - PLAIN and BORING
"""

    prompt = f"""
Create an EXTREMELY SIMPLE and PLAIN gradient background image.

PURPOSE: Background for "{book_name}" ({testament}) Bible reading video with Korean text overlay.

COLOR GRADIENT: {book_info['color']}
MOOD: {book_info['tone']}

{COMMON_STYLE}

CRITICAL INSTRUCTIONS:
1. This is JUST a background - make it VERY SIMPLE
2. Use ONLY soft gradient colors - no patterns, no shapes, no imagery
3. The center 80% must be PLAIN for white text readability
4. Think PowerPoint slide background - BORING is PERFECT
5. Maximum 2-3 colors blending softly
6. Very subtle texture or grain is OK at edges only
7. Must have good contrast for white text overlay

DO NOT include:
- Any symbols, icons, or imagery
- Complex patterns or textures
- Bright or distracting colors
- Any text or letters
"""

    return prompt


def generate_book_background(
    book_name: str,
    output_dir: Optional[str] = None,
    force_regenerate: bool = False
) -> Dict[str, Any]:
    """
    특정 책의 배경 이미지 생성

    Args:
        book_name: 성경 책 이름
        output_dir: 저장 디렉토리 (기본: static/images/bible_backgrounds)
        force_regenerate: True면 기존 이미지가 있어도 재생성

    Returns:
        {"ok": True, "image_path": str, "cost": float} 또는
        {"ok": False, "error": str}
    """
    # 기본 저장 경로
    if output_dir is None:
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        output_dir = os.path.join(base_dir, 'static', 'images', 'bible_backgrounds')

    os.makedirs(output_dir, exist_ok=True)

    # 파일명 생성 (예: genesis.jpg, matthew.jpg)
    # 한글 → 영문 매핑
    book_name_en = _get_english_name(book_name)
    filename = f"{book_name_en.lower().replace(' ', '_')}.jpg"
    filepath = os.path.join(output_dir, filename)

    # 이미 존재하는지 확인
    if os.path.exists(filepath) and not force_regenerate:
        print(f"[BIBLE-BG] {book_name} 배경 이미지 이미 존재: {filepath}")
        return {
            "ok": True,
            "image_path": filepath,
            "image_url": f"/static/images/bible_backgrounds/{filename}",
            "cost": 0,
            "cached": True
        }

    # 프롬프트 생성
    prompt = get_background_prompt(book_name)

    print(f"[BIBLE-BG] {book_name} 배경 이미지 생성 중... (Gemini 3 Pro)")

    # Gemini 3 Pro로 이미지 생성
    result = generate_image(
        prompt=prompt,
        size="1920x1080",  # Full HD
        output_dir=output_dir,
        model=GEMINI_PRO,
        add_aspect_instruction=True
    )

    if not result.get("ok"):
        print(f"[BIBLE-BG] {book_name} 생성 실패: {result.get('error')}")
        return result

    # 파일 이름 변경 (gemini_xxx.jpg → book_name.jpg)
    generated_path = result.get("image_url", "").replace("/static/images/bible_backgrounds/", "")
    if generated_path:
        old_path = os.path.join(output_dir, os.path.basename(generated_path.replace("/static/images/", "")))
        if os.path.exists(old_path) and old_path != filepath:
            os.rename(old_path, filepath)

    print(f"[BIBLE-BG] {book_name} 생성 완료: {filepath}")

    return {
        "ok": True,
        "image_path": filepath,
        "image_url": f"/static/images/bible_backgrounds/{filename}",
        "cost": result.get("cost", 0.05),
        "cached": False
    }


def generate_all_backgrounds(
    force_regenerate: bool = False,
    books: Optional[List[str]] = None
) -> Dict[str, Any]:
    """
    모든 책 (또는 지정된 책들)의 배경 이미지 생성

    Args:
        force_regenerate: True면 모두 재생성
        books: 생성할 책 목록 (None이면 66권 전체)

    Returns:
        {
            "ok": True,
            "generated": int,
            "cached": int,
            "failed": int,
            "total_cost": float,
            "results": {...}
        }
    """
    if books is None:
        books = list(OLD_TESTAMENT_PROMPTS.keys()) + list(NEW_TESTAMENT_PROMPTS.keys())

    results = {}
    generated = 0
    cached = 0
    failed = 0
    total_cost = 0

    print(f"[BIBLE-BG] 총 {len(books)}권 배경 이미지 생성 시작...")

    for i, book_name in enumerate(books, 1):
        print(f"\n[BIBLE-BG] [{i}/{len(books)}] {book_name}")

        result = generate_book_background(book_name, force_regenerate=force_regenerate)
        results[book_name] = result

        if result.get("ok"):
            if result.get("cached"):
                cached += 1
            else:
                generated += 1
                total_cost += result.get("cost", 0)
        else:
            failed += 1

    print(f"\n[BIBLE-BG] 완료!")
    print(f"  - 생성: {generated}개")
    print(f"  - 캐시: {cached}개")
    print(f"  - 실패: {failed}개")
    print(f"  - 총 비용: ${total_cost:.2f}")

    return {
        "ok": failed == 0,
        "generated": generated,
        "cached": cached,
        "failed": failed,
        "total_cost": total_cost,
        "results": results
    }


def _get_english_name(korean_name: str) -> str:
    """한글 책 이름을 영문으로 변환"""
    mapping = {
        # 구약
        "창세기": "Genesis", "출애굽기": "Exodus", "레위기": "Leviticus",
        "민수기": "Numbers", "신명기": "Deuteronomy", "여호수아": "Joshua",
        "사사기": "Judges", "룻기": "Ruth", "사무엘상": "1Samuel",
        "사무엘하": "2Samuel", "열왕기상": "1Kings", "열왕기하": "2Kings",
        "역대상": "1Chronicles", "역대하": "2Chronicles", "에스라": "Ezra",
        "느헤미야": "Nehemiah", "에스더": "Esther", "욥기": "Job",
        "시편": "Psalms", "잠언": "Proverbs", "전도서": "Ecclesiastes",
        "아가": "SongOfSolomon", "이사야": "Isaiah", "예레미야": "Jeremiah",
        "예레미야애가": "Lamentations", "에스겔": "Ezekiel", "다니엘": "Daniel",
        "호세아": "Hosea", "요엘": "Joel", "아모스": "Amos",
        "오바댜": "Obadiah", "요나": "Jonah", "미가": "Micah",
        "나훔": "Nahum", "하박국": "Habakkuk", "스바냐": "Zephaniah",
        "학개": "Haggai", "스가랴": "Zechariah", "말라기": "Malachi",
        # 신약
        "마태복음": "Matthew", "마가복음": "Mark", "누가복음": "Luke",
        "요한복음": "John", "사도행전": "Acts", "로마서": "Romans",
        "고린도전서": "1Corinthians", "고린도후서": "2Corinthians",
        "갈라디아서": "Galatians", "에베소서": "Ephesians", "빌립보서": "Philippians",
        "골로새서": "Colossians", "데살로니가전서": "1Thessalonians",
        "데살로니가후서": "2Thessalonians", "디모데전서": "1Timothy",
        "디모데후서": "2Timothy", "디도서": "Titus", "빌레몬서": "Philemon",
        "히브리서": "Hebrews", "야고보서": "James", "베드로전서": "1Peter",
        "베드로후서": "2Peter", "요한일서": "1John", "요한이서": "2John",
        "요한삼서": "3John", "유다서": "Jude", "요한계시록": "Revelation",
    }
    return mapping.get(korean_name, korean_name)


def get_background_path(book_name: str) -> Optional[str]:
    """
    책의 배경 이미지 경로 반환 (이미 생성된 경우)

    Args:
        book_name: 성경 책 이름

    Returns:
        이미지 경로 또는 None
    """
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    book_name_en = _get_english_name(book_name)
    filename = f"{book_name_en.lower().replace(' ', '_')}.jpg"
    filepath = os.path.join(base_dir, 'static', 'images', 'bible_backgrounds', filename)

    if os.path.exists(filepath):
        return filepath
    return None


# ============================================================
# CLI
# ============================================================

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="성경 배경 이미지 생성")
    parser.add_argument("--book", type=str, help="특정 책만 생성 (예: 창세기)")
    parser.add_argument("--all", action="store_true", help="66권 전체 생성")
    parser.add_argument("--force", action="store_true", help="기존 이미지 재생성")
    parser.add_argument("--testament", choices=["old", "new"], help="구약/신약만 생성")

    args = parser.parse_args()

    if args.book:
        result = generate_book_background(args.book, force_regenerate=args.force)
        print(result)
    elif args.all:
        result = generate_all_backgrounds(force_regenerate=args.force)
        print(f"\n총 비용: ${result['total_cost']:.2f}")
    elif args.testament == "old":
        books = list(OLD_TESTAMENT_PROMPTS.keys())
        result = generate_all_backgrounds(force_regenerate=args.force, books=books)
    elif args.testament == "new":
        books = list(NEW_TESTAMENT_PROMPTS.keys())
        result = generate_all_backgrounds(force_regenerate=args.force, books=books)
    else:
        # 테스트: 창세기, 마태복음만 생성
        print("테스트 모드: 창세기, 마태복음 배경 생성")
        for book in ["창세기", "마태복음"]:
            result = generate_book_background(book, force_regenerate=args.force)
            print(f"{book}: {result}")
