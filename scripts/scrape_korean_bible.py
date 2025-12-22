#!/usr/bin/env python3
"""
개역개정 성경 스크래핑 스크립트
출처: holybible.or.kr

사용법:
    python scrape_korean_bible.py

출력:
    korean_bible_gae.json - 개역개정 성경 전체 (66권)
"""

import json
import re
import time
import urllib.request
from pathlib import Path

# 성경 책 정보 (66권)
BOOKS = [
    # 구약 39권
    {"id": 1, "name": "창세기", "abbr": "창", "chapters": 50},
    {"id": 2, "name": "출애굽기", "abbr": "출", "chapters": 40},
    {"id": 3, "name": "레위기", "abbr": "레", "chapters": 27},
    {"id": 4, "name": "민수기", "abbr": "민", "chapters": 36},
    {"id": 5, "name": "신명기", "abbr": "신", "chapters": 34},
    {"id": 6, "name": "여호수아", "abbr": "수", "chapters": 24},
    {"id": 7, "name": "사사기", "abbr": "삿", "chapters": 21},
    {"id": 8, "name": "룻기", "abbr": "룻", "chapters": 4},
    {"id": 9, "name": "사무엘상", "abbr": "삼상", "chapters": 31},
    {"id": 10, "name": "사무엘하", "abbr": "삼하", "chapters": 24},
    {"id": 11, "name": "열왕기상", "abbr": "왕상", "chapters": 22},
    {"id": 12, "name": "열왕기하", "abbr": "왕하", "chapters": 25},
    {"id": 13, "name": "역대상", "abbr": "대상", "chapters": 29},
    {"id": 14, "name": "역대하", "abbr": "대하", "chapters": 36},
    {"id": 15, "name": "에스라", "abbr": "스", "chapters": 10},
    {"id": 16, "name": "느헤미야", "abbr": "느", "chapters": 13},
    {"id": 17, "name": "에스더", "abbr": "에", "chapters": 10},
    {"id": 18, "name": "욥기", "abbr": "욥", "chapters": 42},
    {"id": 19, "name": "시편", "abbr": "시", "chapters": 150},
    {"id": 20, "name": "잠언", "abbr": "잠", "chapters": 31},
    {"id": 21, "name": "전도서", "abbr": "전", "chapters": 12},
    {"id": 22, "name": "아가", "abbr": "아", "chapters": 8},
    {"id": 23, "name": "이사야", "abbr": "사", "chapters": 66},
    {"id": 24, "name": "예레미야", "abbr": "렘", "chapters": 52},
    {"id": 25, "name": "예레미야애가", "abbr": "애", "chapters": 5},
    {"id": 26, "name": "에스겔", "abbr": "겔", "chapters": 48},
    {"id": 27, "name": "다니엘", "abbr": "단", "chapters": 12},
    {"id": 28, "name": "호세아", "abbr": "호", "chapters": 14},
    {"id": 29, "name": "요엘", "abbr": "욜", "chapters": 3},
    {"id": 30, "name": "아모스", "abbr": "암", "chapters": 9},
    {"id": 31, "name": "오바댜", "abbr": "옵", "chapters": 1},
    {"id": 32, "name": "요나", "abbr": "욘", "chapters": 4},
    {"id": 33, "name": "미가", "abbr": "미", "chapters": 7},
    {"id": 34, "name": "나훔", "abbr": "나", "chapters": 3},
    {"id": 35, "name": "하박국", "abbr": "합", "chapters": 3},
    {"id": 36, "name": "스바냐", "abbr": "습", "chapters": 3},
    {"id": 37, "name": "학개", "abbr": "학", "chapters": 2},
    {"id": 38, "name": "스가랴", "abbr": "슥", "chapters": 14},
    {"id": 39, "name": "말라기", "abbr": "말", "chapters": 4},
    # 신약 27권
    {"id": 40, "name": "마태복음", "abbr": "마", "chapters": 28},
    {"id": 41, "name": "마가복음", "abbr": "막", "chapters": 16},
    {"id": 42, "name": "누가복음", "abbr": "눅", "chapters": 24},
    {"id": 43, "name": "요한복음", "abbr": "요", "chapters": 21},
    {"id": 44, "name": "사도행전", "abbr": "행", "chapters": 28},
    {"id": 45, "name": "로마서", "abbr": "롬", "chapters": 16},
    {"id": 46, "name": "고린도전서", "abbr": "고전", "chapters": 16},
    {"id": 47, "name": "고린도후서", "abbr": "고후", "chapters": 13},
    {"id": 48, "name": "갈라디아서", "abbr": "갈", "chapters": 6},
    {"id": 49, "name": "에베소서", "abbr": "엡", "chapters": 6},
    {"id": 50, "name": "빌립보서", "abbr": "빌", "chapters": 4},
    {"id": 51, "name": "골로새서", "abbr": "골", "chapters": 4},
    {"id": 52, "name": "데살로니가전서", "abbr": "살전", "chapters": 5},
    {"id": 53, "name": "데살로니가후서", "abbr": "살후", "chapters": 3},
    {"id": 54, "name": "디모데전서", "abbr": "딤전", "chapters": 6},
    {"id": 55, "name": "디모데후서", "abbr": "딤후", "chapters": 4},
    {"id": 56, "name": "디도서", "abbr": "딛", "chapters": 3},
    {"id": 57, "name": "빌레몬서", "abbr": "몬", "chapters": 1},
    {"id": 58, "name": "히브리서", "abbr": "히", "chapters": 13},
    {"id": 59, "name": "야고보서", "abbr": "약", "chapters": 5},
    {"id": 60, "name": "베드로전서", "abbr": "벧전", "chapters": 5},
    {"id": 61, "name": "베드로후서", "abbr": "벧후", "chapters": 3},
    {"id": 62, "name": "요한일서", "abbr": "요일", "chapters": 5},
    {"id": 63, "name": "요한이서", "abbr": "요이", "chapters": 1},
    {"id": 64, "name": "요한삼서", "abbr": "요삼", "chapters": 1},
    {"id": 65, "name": "유다서", "abbr": "유", "chapters": 1},
    {"id": 66, "name": "요한계시록", "abbr": "계", "chapters": 22},
]

BASE_URL = "http://www.holybible.or.kr/B_GAE/cgi/bibleftxt.php"


def fetch_chapter(book_id: int, chapter: int, retries: int = 3) -> list[dict]:
    """특정 장의 모든 구절을 가져옵니다."""
    url = f"{BASE_URL}?VR=GAE&VL={book_id}&CN={chapter}&CV=99"

    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7',
                'Referer': 'http://www.holybible.or.kr/',
            })

            with urllib.request.urlopen(req, timeout=30) as response:
                # EUC-KR 인코딩
                data = response.read().decode('euc-kr', errors='ignore')

                verses = []

                # holybible.or.kr HTML 구조:
                # <ol start=001 id="b_001">
                # <li><font class=tk4l>구절내용</font>
                # <li><font class=tk4l>구절내용</font>
                # ...

                # 모든 <ol> 블록 찾기
                ol_blocks = re.findall(r'<ol start=(\d+)[^>]*>(.*?)</td>', data, re.DOTALL)

                for start_num, ol_content in ol_blocks:
                    start_verse = int(start_num)

                    # <li><font class=tk4l>...</font> 패턴으로 각 구절 추출
                    li_matches = re.findall(r'<li><font class=tk4l>(.*?)</font>', ol_content, re.DOTALL)

                    for i, verse_content in enumerate(li_matches):
                        verse_num = start_verse + i

                        # HTML 태그 제거 (사전 링크 등)
                        clean_text = re.sub(r'<[^>]+>', '', verse_content)
                        # 연속 공백 정리
                        clean_text = re.sub(r'\s+', ' ', clean_text).strip()

                        if clean_text:
                            verses.append({
                                "verse": verse_num,
                                "text": clean_text
                            })

                return sorted(verses, key=lambda x: x["verse"])

        except Exception as e:
            print(f"  오류 (시도 {attempt + 1}/{retries}): {e}")
            if attempt < retries - 1:
                time.sleep(2 ** attempt)  # 지수 백오프

    return []


def scrape_bible(output_path: str = "korean_bible_gae.json"):
    """전체 성경을 스크래핑합니다."""
    bible_data = {
        "version": "개역개정",
        "version_code": "GAE",
        "source": "holybible.or.kr",
        "books": []
    }

    total_chapters = sum(book["chapters"] for book in BOOKS)
    completed_chapters = 0

    print(f"개역개정 성경 스크래핑 시작 (총 {len(BOOKS)}권, {total_chapters}장)")
    print("=" * 60)

    for book in BOOKS:
        book_data = {
            "id": book["id"],
            "name": book["name"],
            "abbr": book["abbr"],
            "chapters": []
        }

        print(f"\n[{book['id']:02d}/66] {book['name']} ({book['chapters']}장)")

        for chapter_num in range(1, book["chapters"] + 1):
            verses = fetch_chapter(book["id"], chapter_num)

            book_data["chapters"].append({
                "chapter": chapter_num,
                "verses": verses
            })

            completed_chapters += 1
            progress = (completed_chapters / total_chapters) * 100
            print(f"  {chapter_num}장: {len(verses)}절 ({progress:.1f}%)", end="\r")

            # 서버 부하 방지를 위한 딜레이
            time.sleep(0.5)

        print(f"  완료: {book['chapters']}장")
        bible_data["books"].append(book_data)

        # 중간 저장 (10권마다)
        if book["id"] % 10 == 0:
            temp_path = output_path.replace(".json", f"_temp_{book['id']}.json")
            with open(temp_path, "w", encoding="utf-8") as f:
                json.dump(bible_data, f, ensure_ascii=False, indent=2)
            print(f"  중간 저장: {temp_path}")

    # 최종 저장
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(bible_data, f, ensure_ascii=False, indent=2)

    # 통계
    total_verses = sum(
        len(chapter["verses"])
        for book in bible_data["books"]
        for chapter in book["chapters"]
    )

    print("\n" + "=" * 60)
    print(f"스크래핑 완료!")
    print(f"  - 총 {len(bible_data['books'])}권")
    print(f"  - 총 {total_chapters}장")
    print(f"  - 총 {total_verses}절")
    print(f"  - 저장: {output_path}")

    return bible_data


if __name__ == "__main__":
    output_file = Path(__file__).parent / "korean_bible_gae.json"
    scrape_bible(str(output_file))
