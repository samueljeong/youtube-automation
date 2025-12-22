"""
성경통독 파이프라인 메인 실행 모듈

핵심 기능:
1. 성경 JSON 로드 및 파싱
2. 에피소드 범위 계산 (20분 분량 기준)
3. TTS용 텍스트 생성 (절 번호 제외, 말씀만)
4. 자막용 텍스트 생성 (절 번호 포함)
5. Google Sheets 연동

사용법:
    from scripts.bible_pipeline.run import BiblePipeline

    pipeline = BiblePipeline()

    # 특정 범위의 에피소드 데이터 생성
    episode = pipeline.create_episode("창세기", 1, 15)

    # TTS용 텍스트
    tts_text = episode["tts_text"]

    # 자막용 텍스트 (절별)
    subtitles = episode["subtitles"]
"""

import json
import os
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass

from .config import (
    BIBLE_JSON_PATH,
    BIBLE_BOOKS,
    BIBLE_TTS_VOICE,
    BIBLE_TTS_SPEAKING_RATE,
    BIBLE_TARGET_CHARS,
    BIBLE_CHARS_PER_MINUTE,
    BIBLE_VIDEO_LENGTH_MINUTES,
    get_book_by_name,
)


@dataclass
class Verse:
    """성경 절 데이터"""
    book: str           # 책 이름 (예: 창세기)
    chapter: int        # 장 번호
    verse: int          # 절 번호
    text: str           # 말씀 내용

    @property
    def reference(self) -> str:
        """참조 문자열 (예: 창세기 1:1)"""
        return f"{self.book} {self.chapter}:{self.verse}"

    @property
    def tts_text(self) -> str:
        """TTS용 텍스트 (말씀만)"""
        return self.text

    @property
    def subtitle_text(self) -> str:
        """자막용 텍스트 (절 번호 포함)"""
        return f"({self.verse}) {self.text}"


@dataclass
class Chapter:
    """성경 장 데이터"""
    book: str           # 책 이름
    chapter: int        # 장 번호
    verses: List[Verse] # 절 목록

    @property
    def total_chars(self) -> int:
        """총 글자 수 (TTS 기준)"""
        return sum(len(v.text) for v in self.verses)

    @property
    def estimated_minutes(self) -> float:
        """예상 시간 (분)"""
        return self.total_chars / BIBLE_CHARS_PER_MINUTE

    @property
    def title(self) -> str:
        """장 제목 (예: 창세기 1장)"""
        return f"{self.book} {self.chapter}장"


@dataclass
class Episode:
    """성경통독 에피소드 데이터"""
    episode_id: str         # 에피소드 ID (예: EP001)
    book: str               # 책 이름
    start_chapter: int      # 시작 장
    end_chapter: int        # 끝 장
    chapters: List[Chapter] # 장 목록
    day_number: int = 0     # Day 번호 (1~106)
    books_in_episode: List[str] = None  # 여러 책이 포함된 경우

    @property
    def total_chars(self) -> int:
        """총 글자 수"""
        return sum(ch.total_chars for ch in self.chapters)

    @property
    def estimated_minutes(self) -> float:
        """예상 시간 (분)"""
        return self.total_chars / BIBLE_CHARS_PER_MINUTE

    @property
    def title(self) -> str:
        """에피소드 제목"""
        if self.start_chapter == self.end_chapter:
            return f"{self.book} {self.start_chapter}장"
        return f"{self.book} {self.start_chapter}-{self.end_chapter}장"

    @property
    def range_text(self) -> str:
        """범위 텍스트 (예: 창세기1장~15장 또는 룻기~사무엘상8장)"""
        if self.books_in_episode and len(self.books_in_episode) > 1:
            # 여러 책에 걸친 경우
            first_book = self.books_in_episode[0]
            last_book = self.books_in_episode[-1]
            # 첫 책의 첫 장
            first_ch = self.chapters[0].chapter
            # 마지막 책의 마지막 장
            last_ch = self.chapters[-1].chapter
            return f"{first_book}{first_ch}장~{last_book}{last_ch}장"
        else:
            # 단일 책인 경우
            if self.start_chapter == self.end_chapter:
                return f"{self.book}{self.start_chapter}장"
            return f"{self.book}{self.start_chapter}장~{self.end_chapter}장"

    @property
    def thumbnail_title(self) -> str:
        """
        썸네일 제목
        형식: 100일 성경통독 Day X / 창세기1장~15장
        """
        return f"100일 성경통독 Day {self.day_number}\n{self.range_text}"

    @property
    def video_title(self) -> str:
        """
        YouTube 영상 제목
        형식: [100일 성경통독] Day 1 - 창세기 1-15장
        """
        if self.books_in_episode and len(self.books_in_episode) > 1:
            # 여러 책에 걸친 경우
            first_book = self.books_in_episode[0]
            last_book = self.books_in_episode[-1]
            first_ch = self.chapters[0].chapter
            last_ch = self.chapters[-1].chapter
            range_str = f"{first_book} {first_ch}장 ~ {last_book} {last_ch}장"
        else:
            if self.start_chapter == self.end_chapter:
                range_str = f"{self.book} {self.start_chapter}장"
            else:
                range_str = f"{self.book} {self.start_chapter}-{self.end_chapter}장"
        return f"[100일 성경통독] Day {self.day_number} - {range_str}"

    @property
    def tts_text(self) -> str:
        """
        TTS용 텍스트 (전체)
        - 절 번호 제외
        - 장 시작 시 "창세기 1장" 안내 포함
        """
        parts = []
        for chapter in self.chapters:
            # 장 시작 안내
            parts.append(f"{chapter.title}.")
            # 각 절의 말씀
            for verse in chapter.verses:
                parts.append(verse.tts_text)
        return " ".join(parts)

    @property
    def tts_scenes(self) -> List[Dict[str, Any]]:
        """
        TTS 씬 목록 (장 단위로 분할)
        기존 파이프라인의 scenes 구조와 호환
        """
        scenes = []
        for i, chapter in enumerate(self.chapters):
            # 장별로 하나의 씬 생성
            narration_parts = [verse.tts_text for verse in chapter.verses]
            scenes.append({
                "scene": i + 1,
                "chapter": chapter.chapter,
                "chapter_title": chapter.title,
                "narration": " ".join(narration_parts),
                "char_count": chapter.total_chars,
                "verse_count": len(chapter.verses),
            })
        return scenes

    @property
    def subtitles(self) -> List[Dict[str, Any]]:
        """
        자막 목록 (절 단위)
        - 절 번호 포함: (1) 태초에 하나님이...
        """
        subtitles = []
        for chapter in self.chapters:
            for verse in chapter.verses:
                subtitles.append({
                    "book": verse.book,
                    "chapter": verse.chapter,
                    "verse": verse.verse,
                    "text": verse.subtitle_text,
                    "reference": verse.reference,
                    "char_count": len(verse.text),
                })
        return subtitles

    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리 변환 (JSON 직렬화용)"""
        return {
            "episode_id": self.episode_id,
            "day_number": self.day_number,
            "book": self.book,
            "start_chapter": self.start_chapter,
            "end_chapter": self.end_chapter,
            "title": self.title,
            "range_text": self.range_text,
            "thumbnail_title": self.thumbnail_title,
            "video_title": self.video_title,
            "total_chars": self.total_chars,
            "estimated_minutes": round(self.estimated_minutes, 1),
            "chapter_count": len(self.chapters),
            "verse_count": sum(len(ch.verses) for ch in self.chapters),
            "tts_text": self.tts_text,
            "tts_scenes": self.tts_scenes,
            "subtitles": self.subtitles,
        }


class BiblePipeline:
    """성경통독 파이프라인"""

    def __init__(self, bible_json_path: str = BIBLE_JSON_PATH):
        """
        Args:
            bible_json_path: 성경 JSON 파일 경로
        """
        self.bible_json_path = bible_json_path
        self.bible_data = None
        self._load_bible()

    def _load_bible(self):
        """성경 JSON 로드"""
        if not os.path.exists(self.bible_json_path):
            raise FileNotFoundError(f"성경 파일을 찾을 수 없습니다: {self.bible_json_path}")

        with open(self.bible_json_path, 'r', encoding='utf-8') as f:
            self.bible_data = json.load(f)

        print(f"[BIBLE] 로드 완료: {self.bible_data.get('version', 'Unknown')}")
        print(f"[BIBLE] 총 {len(self.bible_data.get('books', []))}권")

    def get_book(self, book_name: str) -> Optional[Dict[str, Any]]:
        """책 이름으로 성경 책 데이터 조회"""
        for book in self.bible_data.get("books", []):
            if book.get("name") == book_name:
                return book
        return None

    def get_chapter(self, book_name: str, chapter_num: int) -> Optional[Chapter]:
        """특정 장 데이터 조회"""
        book = self.get_book(book_name)
        if not book:
            return None

        for ch in book.get("chapters", []):
            if ch.get("chapter") == chapter_num:
                verses = [
                    Verse(
                        book=book_name,
                        chapter=chapter_num,
                        verse=v.get("verse"),
                        text=v.get("text", "")
                    )
                    for v in ch.get("verses", [])
                ]
                return Chapter(book=book_name, chapter=chapter_num, verses=verses)
        return None

    def get_chapters_range(self, book_name: str, start: int, end: int) -> List[Chapter]:
        """특정 범위의 장들 조회"""
        chapters = []
        for chapter_num in range(start, end + 1):
            chapter = self.get_chapter(book_name, chapter_num)
            if chapter:
                chapters.append(chapter)
        return chapters

    def calculate_chapters_for_duration(
        self,
        book_name: str,
        start_chapter: int = 1,
        target_minutes: float = BIBLE_VIDEO_LENGTH_MINUTES
    ) -> Tuple[int, int, int, float]:
        """
        목표 시간에 맞는 장 범위 계산

        Args:
            book_name: 책 이름
            start_chapter: 시작 장
            target_minutes: 목표 시간 (분)

        Returns:
            (start_chapter, end_chapter, total_chars, estimated_minutes)
        """
        target_chars = target_minutes * BIBLE_CHARS_PER_MINUTE
        book = self.get_book(book_name)

        if not book:
            raise ValueError(f"책을 찾을 수 없습니다: {book_name}")

        total_chars = 0
        end_chapter = start_chapter

        for ch in book.get("chapters", []):
            ch_num = ch.get("chapter")
            if ch_num < start_chapter:
                continue

            # 이 장의 글자 수 계산
            ch_chars = sum(len(v.get("text", "")) for v in ch.get("verses", []))

            # 목표 초과 시 이전 장까지
            if total_chars + ch_chars > target_chars:
                break

            total_chars += ch_chars
            end_chapter = ch_num

        estimated_minutes = total_chars / BIBLE_CHARS_PER_MINUTE
        return start_chapter, end_chapter, total_chars, estimated_minutes

    def create_episode(
        self,
        book_name: str,
        start_chapter: int,
        end_chapter: int,
        episode_id: Optional[str] = None
    ) -> Episode:
        """
        에피소드 생성

        Args:
            book_name: 책 이름 (예: 창세기)
            start_chapter: 시작 장
            end_chapter: 끝 장
            episode_id: 에피소드 ID (없으면 자동 생성)

        Returns:
            Episode 객체
        """
        chapters = self.get_chapters_range(book_name, start_chapter, end_chapter)

        if not chapters:
            raise ValueError(f"장을 찾을 수 없습니다: {book_name} {start_chapter}-{end_chapter}장")

        if not episode_id:
            episode_id = f"EP{start_chapter:03d}"

        return Episode(
            episode_id=episode_id,
            book=book_name,
            start_chapter=start_chapter,
            end_chapter=end_chapter,
            chapters=chapters
        )

    def create_episode_auto(
        self,
        book_name: str,
        start_chapter: int = 1,
        target_minutes: float = BIBLE_VIDEO_LENGTH_MINUTES,
        episode_id: Optional[str] = None
    ) -> Episode:
        """
        목표 시간에 맞춰 자동으로 에피소드 생성

        Args:
            book_name: 책 이름
            start_chapter: 시작 장
            target_minutes: 목표 시간 (분)
            episode_id: 에피소드 ID

        Returns:
            Episode 객체
        """
        start, end, chars, minutes = self.calculate_chapters_for_duration(
            book_name, start_chapter, target_minutes
        )

        print(f"[BIBLE] 자동 계산: {book_name} {start}-{end}장")
        print(f"[BIBLE] 글자 수: {chars:,}자, 예상 시간: {minutes:.1f}분")

        return self.create_episode(book_name, start, end, episode_id)

    def generate_all_episodes(
        self,
        book_name: str,
        target_minutes: float = BIBLE_VIDEO_LENGTH_MINUTES
    ) -> List[Episode]:
        """
        책 전체를 에피소드로 분할

        Args:
            book_name: 책 이름
            target_minutes: 에피소드당 목표 시간

        Returns:
            Episode 목록
        """
        book = self.get_book(book_name)
        if not book:
            raise ValueError(f"책을 찾을 수 없습니다: {book_name}")

        total_chapters = len(book.get("chapters", []))
        episodes = []
        current_start = 1
        episode_num = 1

        while current_start <= total_chapters:
            start, end, chars, minutes = self.calculate_chapters_for_duration(
                book_name, current_start, target_minutes
            )

            # 마지막 장까지 도달했으면 종료
            if end < current_start:
                break

            episode = self.create_episode(
                book_name, start, end,
                episode_id=f"EP{episode_num:03d}"
            )
            episodes.append(episode)

            print(f"[BIBLE] EP{episode_num:03d}: {book_name} {start}-{end}장 ({minutes:.1f}분)")

            current_start = end + 1
            episode_num += 1

        return episodes

    def generate_all_bible_episodes(
        self,
        target_episodes: int = 102  # 실제 106개 생성됨
    ) -> List[Episode]:
        """
        성경 66권 전체를 약 106개 에피소드로 분할

        - 장 단위로 분할 (절 단위 X)
        - 총 글자 수를 목표 에피소드 수로 나눠 평균 분량 계산
        - 짧은 책들은 다음 책과 병합
        - Day 1 ~ Day 106 번호 부여

        Args:
            target_episodes: 목표 에피소드 수 (기본 106개)

        Returns:
            Episode 목록 (약 106개)
        """
        # 먼저 전체 글자 수 계산
        total_bible_chars = 0
        for book_info in BIBLE_BOOKS:
            book = self.get_book(book_info["name"])
            if book:
                for ch in book.get("chapters", []):
                    total_bible_chars += sum(len(v.get("text", "")) for v in ch.get("verses", []))

        # 목표 에피소드 수에 맞는 평균 글자 수 계산
        target_chars = total_bible_chars / target_episodes
        target_minutes = target_chars / BIBLE_CHARS_PER_MINUTE

        print(f"[BIBLE] 총 글자 수: {total_bible_chars:,}자")
        print(f"[BIBLE] 목표: {target_episodes}개 에피소드, 에피소드당 {target_chars:,.0f}자 ({target_minutes:.1f}분)")

        # 8분 미만이면 무조건 다음과 병합
        min_standalone_chars = int(BIBLE_CHARS_PER_MINUTE * 8)  # 8분 = 7,280자

        all_episodes = []
        day_number = 1

        # 현재 진행 중인 에피소드 데이터
        pending_chapters: List[Chapter] = []
        pending_chars = 0
        pending_books = []

        def create_episode_from_pending():
            """현재 pending 데이터로 에피소드 생성"""
            nonlocal day_number, pending_chapters, pending_chars, pending_books

            if not pending_chapters:
                return

            # 범위 정보 추출
            first_book = pending_chapters[0].book
            first_ch = pending_chapters[0].chapter
            last_book = pending_chapters[-1].book
            last_ch = pending_chapters[-1].chapter

            episode = Episode(
                episode_id=f"EP{day_number:03d}",
                book=first_book,
                start_chapter=first_ch,
                end_chapter=last_ch,
                chapters=pending_chapters[:],
                day_number=day_number,
                books_in_episode=pending_books[:] if len(pending_books) > 1 else None
            )
            all_episodes.append(episode)

            # 로그 출력
            if len(pending_books) == 1:
                if first_ch == last_ch:
                    range_str = f"{first_book} {first_ch}장"
                else:
                    range_str = f"{first_book} {first_ch}-{last_ch}장"
            else:
                range_str = f"{pending_books[0]}~{pending_books[-1]}"

            print(f"[BIBLE] Day {day_number:3d}: {range_str} "
                  f"({pending_chars:,}자, {pending_chars/BIBLE_CHARS_PER_MINUTE:.1f}분)")

            day_number += 1
            pending_chapters = []
            pending_chars = 0
            pending_books = []

        # 66권 순서대로 처리
        for book_info in BIBLE_BOOKS:
            book_name = book_info["name"]
            book = self.get_book(book_name)

            if not book:
                continue

            total_chapters_in_book = len(book.get("chapters", []))
            current_start = 1

            while current_start <= total_chapters_in_book:
                # 남은 공간 계산
                available_chars = target_chars - pending_chars

                # 목표까지 공간이 거의 없으면 flush
                if available_chars < BIBLE_CHARS_PER_MINUTE * 2 and pending_chars >= min_standalone_chars:
                    create_episode_from_pending()
                    available_chars = target_chars

                # 이 책에서 얼마나 읽을 수 있는지 계산
                start, end, chars, _ = self.calculate_chapters_for_duration(
                    book_name, current_start,
                    available_chars / BIBLE_CHARS_PER_MINUTE
                )

                # 범위가 유효하지 않으면 책 끝까지
                if end < current_start:
                    end = total_chapters_in_book

                chapters_to_add = self.get_chapters_range(book_name, current_start, end)
                chars_to_add = sum(ch.total_chars for ch in chapters_to_add)

                # 현재 책 추가
                if book_name not in pending_books:
                    pending_books.append(book_name)

                # pending에 추가하면 목표 초과하는지 확인
                if pending_chars + chars_to_add <= target_chars * 1.1:  # 10% 여유
                    pending_chapters.extend(chapters_to_add)
                    pending_chars += chars_to_add
                    current_start = end + 1
                else:
                    # 현재 pending이 충분하면 flush 후 새로 시작
                    if pending_chars >= min_standalone_chars:
                        create_episode_from_pending()
                        # 현재 장들로 새 pending 시작
                        pending_chapters = chapters_to_add
                        pending_chars = chars_to_add
                        pending_books = [book_name]
                        current_start = end + 1
                    else:
                        # 짧으면 강제로 추가 후 flush
                        pending_chapters.extend(chapters_to_add)
                        pending_chars += chars_to_add
                        create_episode_from_pending()
                        current_start = end + 1

            # 책이 끝났을 때 pending이 목표의 90% 이상이면 flush
            # (10분 이하 짧은 에피소드 방지)
            if pending_chars >= target_chars * 0.9:
                create_episode_from_pending()

        # 마지막 남은 pending 처리
        # 마지막 에피소드가 너무 짧으면 이전 에피소드와 병합
        if pending_chapters and pending_chars < min_standalone_chars and all_episodes:
            # 이전 에피소드 가져오기
            last_ep = all_episodes[-1]
            merged_chapters = last_ep.chapters + pending_chapters
            merged_books = list(last_ep.books_in_episode or [last_ep.book])
            for book in pending_books:
                if book not in merged_books:
                    merged_books.append(book)

            # 이전 에피소드 업데이트
            all_episodes[-1] = Episode(
                episode_id=last_ep.episode_id,
                book=merged_chapters[0].book,
                start_chapter=merged_chapters[0].chapter,
                end_chapter=merged_chapters[-1].chapter,
                chapters=merged_chapters,
                day_number=last_ep.day_number,
                books_in_episode=merged_books if len(merged_books) > 1 else None
            )
            merged_chars = sum(ch.total_chars for ch in merged_chapters)
            print(f"[BIBLE] Day {last_ep.day_number} 병합됨: "
                  f"({merged_chars:,}자, {merged_chars/BIBLE_CHARS_PER_MINUTE:.1f}분)")
        else:
            create_episode_from_pending()

        print(f"\n[BIBLE] ===== 총 {len(all_episodes)}개 에피소드 생성 완료 =====")
        return all_episodes

    def get_episode_by_day(self, day: int) -> Optional[Episode]:
        """
        Day 번호로 에피소드 조회

        Args:
            day: Day 번호 (1~106)

        Returns:
            해당 Day의 Episode 객체
        """
        all_episodes = self.generate_all_bible_episodes()
        for ep in all_episodes:
            if ep.day_number == day:
                return ep
        return None

    def get_episodes_summary(self) -> List[Dict[str, Any]]:
        """
        106개 에피소드 요약 정보 (Google Sheets용)

        Returns:
            [
                {
                    "day": 1,
                    "episode_id": "EP001",
                    "book": "창세기",
                    "start_chapter": 1,
                    "end_chapter": 15,
                    "range_text": "창세기1장~15장",
                    "video_title": "[100일 성경통독] Day 1 - 창세기 1-15장",
                    "total_chars": 18041,
                    "estimated_minutes": 19.8
                },
                ...
            ]
        """
        episodes = self.generate_all_bible_episodes()
        summary = []

        for ep in episodes:
            summary.append({
                "day": ep.day_number,
                "episode_id": ep.episode_id,
                "book": ep.book,
                "start_chapter": ep.start_chapter,
                "end_chapter": ep.end_chapter,
                "range_text": ep.range_text,
                "video_title": ep.video_title,
                "total_chars": ep.total_chars,
                "estimated_minutes": round(ep.estimated_minutes, 1)
            })

        return summary

    def get_tts_config(self) -> Dict[str, Any]:
        """TTS 설정 반환 (기존 파이프라인 호환)"""
        return {
            "voice": BIBLE_TTS_VOICE,
            "speaking_rate": BIBLE_TTS_SPEAKING_RATE,
        }


# ============================================================
# CLI 테스트
# ============================================================

if __name__ == "__main__":
    import sys

    pipeline = BiblePipeline()

    # 인자 확인
    if len(sys.argv) > 1 and sys.argv[1] == "--all":
        # 전체 106개 에피소드 생성 테스트
        print("=" * 60)
        print("  100일 성경통독 - 106개 에피소드 분할")
        print("=" * 60)

        episodes = pipeline.generate_all_bible_episodes()

        # 요약 통계
        total_chars = sum(ep.total_chars for ep in episodes)
        total_minutes = sum(ep.estimated_minutes for ep in episodes)
        avg_minutes = total_minutes / len(episodes)

        print("\n" + "=" * 60)
        print("  요약 통계")
        print("=" * 60)
        print(f"  총 에피소드: {len(episodes)}개")
        print(f"  총 글자 수: {total_chars:,}자")
        print(f"  총 예상 시간: {total_minutes:.0f}분 ({total_minutes/60:.1f}시간)")
        print(f"  평균 에피소드 길이: {avg_minutes:.1f}분")
        print("=" * 60)

        # 처음 5개, 마지막 5개 에피소드 출력
        print("\n[처음 5개 에피소드]")
        for ep in episodes[:5]:
            print(f"  Day {ep.day_number:3d}: {ep.video_title}")

        print("\n[마지막 5개 에피소드]")
        for ep in episodes[-5:]:
            print(f"  Day {ep.day_number:3d}: {ep.video_title}")

    elif len(sys.argv) > 1 and sys.argv[1].startswith("--day="):
        # 특정 Day 에피소드 상세 정보
        day = int(sys.argv[1].split("=")[1])
        episode = pipeline.get_episode_by_day(day)

        if episode:
            print("=" * 60)
            print(f"  Day {episode.day_number} 상세 정보")
            print("=" * 60)
            print(f"  영상 제목: {episode.video_title}")
            print(f"  썸네일 제목:\n    {episode.thumbnail_title.replace(chr(10), chr(10) + '    ')}")
            print(f"  글자 수: {episode.total_chars:,}자")
            print(f"  예상 시간: {episode.estimated_minutes:.1f}분")
            print(f"  장 수: {len(episode.chapters)}개")
            print(f"  절 수: {len(episode.subtitles)}개")
            print("=" * 60)

            print("\n[TTS 텍스트 샘플 (500자)]")
            print(episode.tts_text[:500] + "...")

            print("\n[자막 샘플 (5개)]")
            for sub in episode.subtitles[:5]:
                print(f"  {sub['reference']}: {sub['text'][:40]}...")
        else:
            print(f"Day {day} 에피소드를 찾을 수 없습니다.")

    else:
        # 기본: 창세기 에피소드 생성 테스트
        episode = pipeline.create_episode_auto("창세기", start_chapter=1)
        episode.day_number = 1  # Day 1 설정

        print("\n" + "=" * 60)
        print(f"  Day {episode.day_number}: {episode.title}")
        print("=" * 60)
        print(f"  영상 제목: {episode.video_title}")
        print(f"  글자 수: {episode.total_chars:,}자")
        print(f"  예상 시간: {episode.estimated_minutes:.1f}분")
        print(f"  장 수: {len(episode.chapters)}개")
        print(f"  절 수: {len(episode.subtitles)}개")
        print("=" * 60)

        print("\n[TTS 텍스트 샘플]")
        print(episode.tts_text[:500] + "...")

        print("\n[자막 샘플]")
        for sub in episode.subtitles[:5]:
            print(f"  {sub['reference']}: {sub['text'][:30]}...")

        print("\n[사용법]")
        print("  python -m scripts.bible_pipeline.run          # 기본 테스트")
        print("  python -m scripts.bible_pipeline.run --all    # 106개 에피소드 생성")
        print("  python -m scripts.bible_pipeline.run --day=1  # Day 1 상세 정보")
