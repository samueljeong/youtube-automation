"""
무료 배경음악 다운로드 모듈

무료 로열티 프리 음악을 다운로드합니다.
"""

import os
import requests
from typing import Optional
import random


class MusicFetcher:
    """무료 배경음악 다운로드"""

    def __init__(self):
        # 무료 배경음악 URL 리스트 (로열티 프리)
        # 실제로는 Free Music Archive, Incompetech 등에서 가져올 수 있음
        self.free_music_urls = [
            # 평화로운 피아노 음악
            "https://incompetech.com/music/royalty-free/mp3-royaltyfree/Meditation%20Impromptu%2001.mp3",
            # 부드러운 어쿠스틱
            "https://incompetech.com/music/royalty-free/mp3-royaltyfree/Meditation%20Impromptu%2002.mp3",
            # 조용한 배경음악
            "https://incompetech.com/music/royalty-free/mp3-royaltyfree/Meditation%20Impromptu%2003.mp3",
        ]

        # 카테고리별 음악
        self.music_categories = {
            "peaceful": [
                "https://incompetech.com/music/royalty-free/mp3-royaltyfree/Meditation%20Impromptu%2001.mp3",
            ],
            "morning": [
                "https://incompetech.com/music/royalty-free/mp3-royaltyfree/Meditation%20Impromptu%2002.mp3",
            ],
            "evening": [
                "https://incompetech.com/music/royalty-free/mp3-royaltyfree/Meditation%20Impromptu%2003.mp3",
            ]
        }

    def download_music(self, url: str, save_path: str) -> bool:
        """
        음악 파일 다운로드

        Args:
            url: 음악 파일 URL
            save_path: 저장할 파일 경로

        Returns:
            성공 여부
        """
        try:
            response = requests.get(url, timeout=30, stream=True)
            response.raise_for_status()

            # 디렉토리 생성
            os.makedirs(os.path.dirname(save_path), exist_ok=True)

            # 파일 저장
            with open(save_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)

            print(f"[MusicFetcher] Downloaded: {save_path}")
            return True

        except Exception as e:
            print(f"[MusicFetcher] Download error: {e}")
            return False

    def get_random_music(self, save_path: str, category: str = None) -> Optional[str]:
        """
        랜덤 배경음악 다운로드

        Args:
            save_path: 저장할 파일 경로
            category: 음악 카테고리 (peaceful, morning, evening)

        Returns:
            저장된 파일 경로 또는 None
        """
        if category and category in self.music_categories:
            url = random.choice(self.music_categories[category])
        else:
            url = random.choice(self.free_music_urls)

        if self.download_music(url, save_path):
            return save_path
        return None

    def get_music_for_time(self, save_path: str, time_of_day: str = "morning") -> Optional[str]:
        """
        시간대에 맞는 음악 다운로드

        Args:
            save_path: 저장할 파일 경로
            time_of_day: morning 또는 evening

        Returns:
            저장된 파일 경로 또는 None
        """
        category = "morning" if time_of_day == "morning" else "evening"
        return self.get_random_music(save_path, category)


# 테스트용 코드
if __name__ == "__main__":
    fetcher = MusicFetcher()

    # 테스트: 랜덤 음악 다운로드
    print("Testing music download...")
    result = fetcher.get_random_music("output/music/test_bg_music.mp3")
    if result:
        print(f"✅ Success: {result}")
    else:
        print("❌ Failed")
