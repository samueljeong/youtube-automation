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

    def generate_all_bible_episodes(self) -> List[Episode]:
        """
        성경 66권 전체를 약 100개 에피소드로 분할 (깔끔한 책 경계 유지)

        원칙:
        1. 긴 책 (15분 이상 분량): 책 내에서만 분할, 다른 책과 절대 합치지 않음
        2. 짧은 책 (15분 미만 분량): 연속된 짧은 책들끼리만 병합
        3. 에피소드당 목표: 15~25분 (너무 짧거나 길지 않게)

        Returns:
            Episode 목록 (약 100개)
        """
        # 임계값 설정
        MIN_EPISODE_CHARS = int(BIBLE_CHARS_PER_MINUTE * 12)  # 12분 = 10,920자
        TARGET_EPISODE_CHARS = int(BIBLE_CHARS_PER_MINUTE * 18)  # 18분 = 16,380자
        MAX_EPISODE_CHARS = int(BIBLE_CHARS_PER_MINUTE * 22)  # 22분 = 20,020자
        MIN_MERGE_THRESHOLD = int(BIBLE_CHARS_PER_MINUTE * 8)  # 8분 미만만 병합

        # 1단계: 각 책의 총 글자 수 계산
        book_stats = []
        total_bible_chars = 0

        for book_info in BIBLE_BOOKS:
            book_name = book_info["name"]
            book = self.get_book(book_name)
            if not book:
                continue

            book_chars = 0
            chapter_chars = []  # [(chapter_num, chars), ...]

            for ch in book.get("chapters", []):
                ch_num = ch.get("chapter")
                ch_chars = sum(len(v.get("text", "")) for v in ch.get("verses", []))
                chapter_chars.append((ch_num, ch_chars))
                book_chars += ch_chars

            book_stats.append({
                "name": book_name,
                "total_chars": book_chars,
                "chapter_chars": chapter_chars,
                "is_long": book_chars >= MIN_EPISODE_CHARS,  # 15분 이상이면 "긴 책"
                "testament": book_info["testament"]
            })
            total_bible_chars += book_chars

        print(f"[BIBLE] 총 글자 수: {total_bible_chars:,}자")
        print(f"[BIBLE] 긴 책: {sum(1 for b in book_stats if b['is_long'])}권")
        print(f"[BIBLE] 짧은 책: {sum(1 for b in book_stats if not b['is_long'])}권")

        all_episodes = []
        day_number = 1

        # 짧은 책들을 모으기 위한 버퍼
        short_book_buffer: List[Chapter] = []
        short_book_buffer_chars = 0
        short_book_buffer_names = []

        def flush_short_book_buffer():
            """짧은 책 버퍼를 에피소드로 생성"""
            nonlocal day_number, short_book_buffer, short_book_buffer_chars, short_book_buffer_names

            if not short_book_buffer:
                return

            first_book = short_book_buffer[0].book
            first_ch = short_book_buffer[0].chapter
            last_ch = short_book_buffer[-1].chapter

            episode = Episode(
                episode_id=f"EP{day_number:03d}",
                book=first_book,
                start_chapter=first_ch,
                end_chapter=last_ch,
                chapters=short_book_buffer[:],
                day_number=day_number,
                books_in_episode=short_book_buffer_names[:] if len(short_book_buffer_names) > 1 else None
            )
            all_episodes.append(episode)

            # 로그
            if len(short_book_buffer_names) == 1:
                range_str = f"{first_book} 전체"
            else:
                range_str = f"{short_book_buffer_names[0]} ~ {short_book_buffer_names[-1]}"

            print(f"[BIBLE] Day {day_number:3d}: {range_str} "
                  f"({short_book_buffer_chars:,}자, {short_book_buffer_chars/BIBLE_CHARS_PER_MINUTE:.1f}분) [병합]")

            day_number += 1
            short_book_buffer = []
            short_book_buffer_chars = 0
            short_book_buffer_names = []

        # 2단계: 책별로 처리
        for book_stat in book_stats:
            book_name = book_stat["name"]
            book_chars = book_stat["total_chars"]
            chapter_chars = book_stat["chapter_chars"]
            is_long = book_stat["is_long"]

            if is_long:
                # ===== 긴 책 처리 =====
                # 짧은 책 버퍼가 MIN_EPISODE_CHARS 이상이면 먼저 flush
                # 그 미만이면 이 책의 첫 에피소드에 포함
                include_short_buffer_in_first = False
                if short_book_buffer_chars >= MIN_EPISODE_CHARS:
                    flush_short_book_buffer()
                elif short_book_buffer:
                    include_short_buffer_in_first = True  # 첫 에피소드에 포함할 예정

                # 책 내에서 에피소드 분할
                current_episode_chapters: List[Chapter] = []
                current_episode_chars = 0
                start_chapter = 1
                is_first_episode_of_book = True  # 이 책의 첫 에피소드 여부

                # 남은 장들의 총 글자 수 미리 계산 (마지막 병합 결정용)
                remaining_chars_from_idx = {}
                total_remaining = 0
                for i in range(len(chapter_chars) - 1, -1, -1):
                    total_remaining += chapter_chars[i][1]
                    remaining_chars_from_idx[i] = total_remaining

                for idx, (ch_num, ch_chars) in enumerate(chapter_chars):
                    chapter = self.get_chapter(book_name, ch_num)
                    if not chapter:
                        continue

                    # 첫 에피소드에 짧은 책 버퍼 포함 시 총 글자 수 계산
                    effective_chars = current_episode_chars
                    if include_short_buffer_in_first and is_first_episode_of_book:
                        effective_chars += short_book_buffer_chars

                    # 이 장을 추가하면 목표 초과하는지 확인
                    if effective_chars + ch_chars > MAX_EPISODE_CHARS and effective_chars >= MIN_EPISODE_CHARS:
                        # 남은 장들이 MIN_MERGE_THRESHOLD 미만이면 현재 에피소드에 모두 포함
                        remaining_after_this = remaining_chars_from_idx.get(idx, 0)
                        if remaining_after_this < MIN_MERGE_THRESHOLD:
                            # 남은 장들 모두 현재 에피소드에 추가
                            for remaining_idx in range(idx, len(chapter_chars)):
                                remaining_ch_num, _ = chapter_chars[remaining_idx]
                                remaining_chapter = self.get_chapter(book_name, remaining_ch_num)
                                if remaining_chapter:
                                    current_episode_chapters.append(remaining_chapter)
                                    current_episode_chars += remaining_chapter.total_chars
                            # 에피소드 생성 후 루프 종료
                            break

                        # 현재까지를 에피소드로 생성
                        # 이 책의 첫 에피소드이고 짧은 책 버퍼가 있으면 포함
                        if include_short_buffer_in_first and is_first_episode_of_book:
                            # 짧은 책 버퍼 + 현재 장들로 첫 에피소드
                            merged_chapters = short_book_buffer + current_episode_chapters
                            merged_chars = short_book_buffer_chars + current_episode_chars
                            first_book = short_book_buffer[0].book

                            episode = Episode(
                                episode_id=f"EP{day_number:03d}",
                                book=first_book,
                                start_chapter=short_book_buffer[0].chapter,
                                end_chapter=current_episode_chapters[-1].chapter,
                                chapters=merged_chapters,
                                day_number=day_number,
                                books_in_episode=short_book_buffer_names + [book_name]
                            )
                            all_episodes.append(episode)

                            range_str = f"{short_book_buffer_names[0]} ~ {book_name} {current_episode_chapters[-1].chapter}장"
                            print(f"[BIBLE] Day {day_number:3d}: {range_str} "
                                  f"({merged_chars:,}자, {merged_chars/BIBLE_CHARS_PER_MINUTE:.1f}분) [+짧은책]")

                            # 버퍼 비우기
                            short_book_buffer = []
                            short_book_buffer_chars = 0
                            short_book_buffer_names = []
                            include_short_buffer_in_first = False
                        else:
                            episode = Episode(
                                episode_id=f"EP{day_number:03d}",
                                book=book_name,
                                start_chapter=start_chapter,
                                end_chapter=current_episode_chapters[-1].chapter,
                                chapters=current_episode_chapters[:],
                                day_number=day_number
                            )
                            all_episodes.append(episode)

                            range_str = f"{book_name} {start_chapter}-{current_episode_chapters[-1].chapter}장"
                            print(f"[BIBLE] Day {day_number:3d}: {range_str} "
                                  f"({current_episode_chars:,}자, {current_episode_chars/BIBLE_CHARS_PER_MINUTE:.1f}분)")

                        is_first_episode_of_book = False  # 첫 에피소드 생성 완료

                        day_number += 1
                        current_episode_chapters = []
                        current_episode_chars = 0
                        start_chapter = ch_num

                    # 현재 장 추가
                    current_episode_chapters.append(chapter)
                    current_episode_chars += ch_chars

                # 책의 마지막 남은 장들 처리
                if current_episode_chapters:
                    # 마지막 에피소드가 MIN_MERGE_THRESHOLD 미만이고 이전 에피소드가 같은 책이면 병합
                    if (current_episode_chars < MIN_MERGE_THRESHOLD and
                        all_episodes and all_episodes[-1].book == book_name):
                        # 이전 에피소드와 병합
                        last_ep = all_episodes[-1]
                        merged_chapters = last_ep.chapters + current_episode_chapters
                        merged_chars = sum(ch.total_chars for ch in merged_chapters)

                        all_episodes[-1] = Episode(
                            episode_id=last_ep.episode_id,
                            book=book_name,
                            start_chapter=last_ep.start_chapter,
                            end_chapter=current_episode_chapters[-1].chapter,
                            chapters=merged_chapters,
                            day_number=last_ep.day_number
                        )

                        range_str = f"{book_name} {last_ep.start_chapter}-{current_episode_chapters[-1].chapter}장"
                        print(f"[BIBLE] Day {last_ep.day_number:3d}: {range_str} "
                              f"({merged_chars:,}자, {merged_chars/BIBLE_CHARS_PER_MINUTE:.1f}분) [병합]")
                    elif include_short_buffer_in_first and is_first_episode_of_book:
                        # 첫 에피소드에 짧은 책 버퍼 포함 (책 전체가 하나의 에피소드인 경우)
                        merged_chapters = short_book_buffer + current_episode_chapters
                        merged_chars = short_book_buffer_chars + current_episode_chars
                        first_book = short_book_buffer[0].book

                        episode = Episode(
                            episode_id=f"EP{day_number:03d}",
                            book=first_book,
                            start_chapter=short_book_buffer[0].chapter,
                            end_chapter=current_episode_chapters[-1].chapter,
                            chapters=merged_chapters,
                            day_number=day_number,
                            books_in_episode=short_book_buffer_names + [book_name]
                        )
                        all_episodes.append(episode)

                        range_str = f"{short_book_buffer_names[0]} ~ {book_name} {current_episode_chapters[-1].chapter}장"
                        print(f"[BIBLE] Day {day_number:3d}: {range_str} "
                              f"({merged_chars:,}자, {merged_chars/BIBLE_CHARS_PER_MINUTE:.1f}분) [+짧은책]")

                        # 버퍼 비우기
                        short_book_buffer = []
                        short_book_buffer_chars = 0
                        short_book_buffer_names = []
                        day_number += 1
                    else:
                        # 새 에피소드 생성
                        episode = Episode(
                            episode_id=f"EP{day_number:03d}",
                            book=book_name,
                            start_chapter=start_chapter,
                            end_chapter=current_episode_chapters[-1].chapter,
                            chapters=current_episode_chapters[:],
                            day_number=day_number
                        )
                        all_episodes.append(episode)

                        if start_chapter == current_episode_chapters[-1].chapter:
                            range_str = f"{book_name} {start_chapter}장"
                        else:
                            range_str = f"{book_name} {start_chapter}-{current_episode_chapters[-1].chapter}장"
                        print(f"[BIBLE] Day {day_number:3d}: {range_str} "
                              f"({current_episode_chars:,}자, {current_episode_chars/BIBLE_CHARS_PER_MINUTE:.1f}분)")

                        day_number += 1

            else:
                # ===== 짧은 책: 버퍼에 추가 =====
                book_chapters = []
                for ch_num, _ in chapter_chars:
                    chapter = self.get_chapter(book_name, ch_num)
                    if chapter:
                        book_chapters.append(chapter)

                # 버퍼에 추가하면 목표 초과하는지 확인
                if short_book_buffer_chars + book_chars > MAX_EPISODE_CHARS and short_book_buffer_chars >= MIN_EPISODE_CHARS:
                    # 현재 버퍼를 에피소드로 생성
                    flush_short_book_buffer()

                # 버퍼에 추가
                short_book_buffer.extend(book_chapters)
                short_book_buffer_chars += book_chars
                if book_name not in short_book_buffer_names:
                    short_book_buffer_names.append(book_name)

                # 버퍼가 목표에 도달하면 flush
                if short_book_buffer_chars >= TARGET_EPISODE_CHARS:
                    flush_short_book_buffer()

        # 마지막 남은 짧은 책 버퍼 처리
        flush_short_book_buffer()

        print(f"\n[BIBLE] ===== 총 {len(all_episodes)}개 에피소드 생성 완료 =====")

        # 통계 출력
        total_chars = sum(ep.total_chars for ep in all_episodes)
        total_minutes = sum(ep.estimated_minutes for ep in all_episodes)
        avg_minutes = total_minutes / len(all_episodes) if all_episodes else 0

        print(f"[BIBLE] 총 글자 수: {total_chars:,}자")
        print(f"[BIBLE] 총 예상 시간: {total_minutes:.0f}분 ({total_minutes/60:.1f}시간)")
        print(f"[BIBLE] 평균 에피소드 길이: {avg_minutes:.1f}분")

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
