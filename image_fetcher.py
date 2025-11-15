"""
무료 이미지 다운로드 모듈
Unsplash, Pexels, Pixabay 등에서 무료 이미지를 가져옵니다.
"""

import os
import requests
from typing import Optional, List
import random

class ImageFetcher:
    """무료 스톡 이미지 다운로드"""

    def __init__(self):
        # Unsplash API 키 (선택사항 - 없어도 제한적으로 작동)
        self.unsplash_key = os.getenv("UNSPLASH_ACCESS_KEY", "")

        # Pexels API 키 (선택사항)
        self.pexels_key = os.getenv("PEXELS_API_KEY", "")

        # 기본 검색 키워드 (묵상 콘텐츠용)
        self.default_keywords = [
            "peaceful nature",
            "calm sunrise",
            "serene landscape",
            "morning light",
            "peaceful sky",
            "tranquil ocean",
            "quiet forest",
            "soft sunset",
            "gentle mountains",
            "prayer hands"
        ]

    def fetch_unsplash(self, keyword: str = None, width: int = 1080, height: int = 1920) -> Optional[str]:
        """
        Unsplash에서 이미지 URL 가져오기

        Args:
            keyword: 검색 키워드 (None이면 랜덤)
            width: 이미지 너비
            height: 이미지 높이

        Returns:
            이미지 URL 또는 None
        """
        if not keyword:
            keyword = random.choice(self.default_keywords)

        try:
            if self.unsplash_key:
                # API 키가 있으면 검색 API 사용
                url = "https://api.unsplash.com/search/photos"
                headers = {"Authorization": f"Client-ID {self.unsplash_key}"}
                params = {
                    "query": keyword,
                    "per_page": 10,
                    "orientation": "portrait"  # 세로형
                }

                response = requests.get(url, headers=headers, params=params, timeout=10)
                response.raise_for_status()

                data = response.json()
                if data.get("results"):
                    # 랜덤하게 하나 선택
                    photo = random.choice(data["results"])
                    # 원하는 크기로 조정된 URL 반환
                    return f"{photo['urls']['raw']}&w={width}&h={height}&fit=crop"
            else:
                # API 키가 없으면 Unsplash Source 사용 (무료, 키 불필요)
                # 제한: 랜덤 이미지만 가능, 검색 불가
                return f"https://source.unsplash.com/{width}x{height}/?{keyword.replace(' ', ',')}"

        except Exception as e:
            print(f"[Unsplash] Error: {e}")
            return None

    def fetch_pexels(self, keyword: str = None, width: int = 1080, height: int = 1920) -> Optional[str]:
        """
        Pexels에서 이미지 URL 가져오기

        Args:
            keyword: 검색 키워드
            width: 이미지 너비
            height: 이미지 높이

        Returns:
            이미지 URL 또는 None
        """
        if not self.pexels_key:
            print("[Pexels] API key not found")
            return None

        if not keyword:
            keyword = random.choice(self.default_keywords)

        try:
            url = "https://api.pexels.com/v1/search"
            headers = {"Authorization": self.pexels_key}
            params = {
                "query": keyword,
                "per_page": 10,
                "orientation": "portrait"
            }

            response = requests.get(url, headers=headers, params=params, timeout=10)
            response.raise_for_status()

            data = response.json()
            if data.get("photos"):
                photo = random.choice(data["photos"])
                # Pexels는 다양한 크기 제공
                return photo["src"]["large2x"]  # 고화질

        except Exception as e:
            print(f"[Pexels] Error: {e}")
            return None

    def download_image(self, url: str, save_path: str) -> bool:
        """
        이미지 URL을 다운로드하여 파일로 저장

        Args:
            url: 이미지 URL
            save_path: 저장할 파일 경로

        Returns:
            성공 여부
        """
        try:
            response = requests.get(url, timeout=15, stream=True)
            response.raise_for_status()

            # 디렉토리 생성
            os.makedirs(os.path.dirname(save_path), exist_ok=True)

            # 파일 저장
            with open(save_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)

            print(f"[ImageFetcher] Downloaded: {save_path}")
            return True

        except Exception as e:
            print(f"[ImageFetcher] Download error: {e}")
            return False

    def get_random_devotional_image(self, save_path: str) -> Optional[str]:
        """
        묵상용 랜덤 이미지를 다운로드하여 저장

        Args:
            save_path: 저장할 파일 경로

        Returns:
            저장된 파일 경로 또는 None
        """
        # 묵상 관련 키워드 중 랜덤 선택
        keyword = random.choice(self.default_keywords)

        # Unsplash 시도 (우선)
        url = self.fetch_unsplash(keyword)
        if url and self.download_image(url, save_path):
            return save_path

        # Pexels 시도 (백업)
        url = self.fetch_pexels(keyword)
        if url and self.download_image(url, save_path):
            return save_path

        print("[ImageFetcher] Failed to download image")
        return None

    def get_image_for_message(self, message: str, save_path: str) -> Optional[str]:
        """
        묵상 메시지 내용을 분석하여 적합한 이미지 다운로드

        Args:
            message: 묵상 메시지 텍스트
            save_path: 저장할 파일 경로

        Returns:
            저장된 파일 경로 또는 None
        """
        # 메시지에서 키워드 추출 (간단한 규칙 기반)
        keyword = None

        keywords_map = {
            "빛": "morning light",
            "사랑": "love heart",
            "평화": "peaceful nature",
            "소망": "hope sunrise",
            "기쁨": "joy happiness",
            "감사": "gratitude thankful",
            "은혜": "grace beautiful",
            "믿음": "faith prayer",
            "하늘": "sky heaven",
            "바다": "ocean sea",
            "산": "mountains",
            "새벽": "dawn sunrise",
            "저녁": "sunset evening",
            "밤": "night stars"
        }

        # 메시지에서 키워드 찾기
        for korean, english in keywords_map.items():
            if korean in message:
                keyword = english
                break

        # 키워드 없으면 랜덤
        if not keyword:
            return self.get_random_devotional_image(save_path)

        # 키워드로 이미지 다운로드
        url = self.fetch_unsplash(keyword)
        if url and self.download_image(url, save_path):
            return save_path

        # 실패하면 랜덤으로 재시도
        return self.get_random_devotional_image(save_path)


# 테스트용 코드
if __name__ == "__main__":
    fetcher = ImageFetcher()

    # 테스트: 랜덤 묵상 이미지 다운로드
    print("Testing image download...")
    result = fetcher.get_random_devotional_image("output/test_image.jpg")
    if result:
        print(f"✅ Success: {result}")
    else:
        print("❌ Failed")
