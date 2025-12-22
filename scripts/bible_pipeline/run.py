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
            "book": self.book,
            "start_chapter": self.start_chapter,
            "end_chapter": self.end_chapter,
            "title": self.title,
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
    # 테스트: 창세기 에피소드 생성
    pipeline = BiblePipeline()

    # 20분 분량으로 자동 계산
    episode = pipeline.create_episode_auto("창세기", start_chapter=1)

    print("\n" + "=" * 50)
    print(f"에피소드: {episode.title}")
    print(f"글자 수: {episode.total_chars:,}자")
    print(f"예상 시간: {episode.estimated_minutes:.1f}분")
    print(f"장 수: {len(episode.chapters)}개")
    print(f"절 수: {len(episode.subtitles)}개")
    print("=" * 50)

    # TTS 텍스트 샘플 (처음 500자)
    print("\n[TTS 텍스트 샘플]")
    print(episode.tts_text[:500] + "...")

    # 자막 샘플 (처음 5개)
    print("\n[자막 샘플]")
    for sub in episode.subtitles[:5]:
        print(f"  {sub['reference']}: {sub['text'][:30]}...")

    # 창세기 전체 에피소드 분할
    print("\n" + "=" * 50)
    print("[창세기 전체 에피소드 분할]")
    print("=" * 50)
    episodes = pipeline.generate_all_episodes("창세기")
    print(f"\n총 {len(episodes)}개 에피소드로 분할됨")
