"""
소셜 미디어 멀티 플랫폼 업로더

Instagram과 TikTok에 동시 업로드를 지원합니다.
"""

import os
from typing import Dict, List, Optional
from instagram_uploader import InstagramUploader
from tiktok_uploader import TikTokUploader


class SocialMediaUploader:
    """멀티 플랫폼 소셜 미디어 업로더"""

    def __init__(self):
        """
        환경변수에서 자격증명을 로드합니다:
        - INSTAGRAM_USERNAME, INSTAGRAM_PASSWORD
        - TIKTOK_USERNAME, TIKTOK_PASSWORD
        """
        self.instagram = None
        self.tiktok = None

        # Instagram 초기화
        try:
            if os.getenv("INSTAGRAM_USERNAME") and os.getenv("INSTAGRAM_PASSWORD"):
                self.instagram = InstagramUploader()
                print("[SocialMedia] Instagram uploader initialized")
            else:
                print("[SocialMedia] Instagram credentials not found - skipping")
        except Exception as e:
            print(f"[SocialMedia] Instagram initialization failed: {e}")

        # TikTok 초기화
        try:
            if os.getenv("TIKTOK_USERNAME") and os.getenv("TIKTOK_PASSWORD"):
                self.tiktok = TikTokUploader()
                print("[SocialMedia] TikTok uploader initialized")
            else:
                print("[SocialMedia] TikTok credentials not found - skipping")
        except Exception as e:
            print(f"[SocialMedia] TikTok initialization failed: {e}")

    def upload_to_all(
        self,
        video_path: str,
        caption: str = "",
        platforms: Optional[List[str]] = None,
        headless: bool = True
    ) -> Dict[str, bool]:
        """
        여러 플랫폼에 동시 업로드

        Args:
            video_path: 업로드할 비디오 파일 경로
            caption: 캡션 텍스트
            platforms: 업로드할 플랫폼 리스트 (None = 모두)
                      예: ["instagram", "tiktok"]
            headless: 헤드리스 모드 (True = UI 없음)

        Returns:
            플랫폼별 성공 여부 딕셔너리
            예: {"instagram": True, "tiktok": False}
        """
        if not os.path.exists(video_path):
            print(f"[SocialMedia] Video file not found: {video_path}")
            return {}

        # 기본값: 모든 플랫폼
        if platforms is None:
            platforms = []
            if self.instagram:
                platforms.append("instagram")
            if self.tiktok:
                platforms.append("tiktok")

        results = {}

        # Instagram 업로드
        if "instagram" in platforms:
            if self.instagram:
                print("\n" + "="*60)
                print("📸 Instagram 업로드 시작...")
                print("="*60)
                try:
                    # Instagram 해시태그 최적화
                    instagram_caption = self._format_caption_for_instagram(caption)
                    result = self.instagram.upload_reel(
                        video_path,
                        caption=instagram_caption,
                        headless=headless
                    )
                    results["instagram"] = result
                    if result:
                        print("✅ Instagram 업로드 성공!")
                    else:
                        print("❌ Instagram 업로드 실패")
                except Exception as e:
                    print(f"❌ Instagram 업로드 에러: {e}")
                    results["instagram"] = False
            else:
                print("⚠️  Instagram 자격증명 없음 - 건너뜀")
                results["instagram"] = False

        # TikTok 업로드
        if "tiktok" in platforms:
            if self.tiktok:
                print("\n" + "="*60)
                print("🎵 TikTok 업로드 시작...")
                print("="*60)
                try:
                    # TikTok 해시태그 최적화
                    tiktok_caption = self._format_caption_for_tiktok(caption)
                    result = self.tiktok.upload_video(
                        video_path,
                        caption=tiktok_caption,
                        headless=headless
                    )
                    results["tiktok"] = result
                    if result:
                        print("✅ TikTok 업로드 성공!")
                    else:
                        print("❌ TikTok 업로드 실패")
                except Exception as e:
                    print(f"❌ TikTok 업로드 에러: {e}")
                    results["tiktok"] = False
            else:
                print("⚠️  TikTok 자격증명 없음 - 건너뜀")
                results["tiktok"] = False

        return results

    def upload_to_instagram(
        self,
        video_path: str,
        caption: str = "",
        headless: bool = True
    ) -> bool:
        """Instagram에만 업로드"""
        if not self.instagram:
            print("[SocialMedia] Instagram not initialized")
            return False

        instagram_caption = self._format_caption_for_instagram(caption)
        return self.instagram.upload_reel(video_path, caption=instagram_caption, headless=headless)

    def upload_to_tiktok(
        self,
        video_path: str,
        caption: str = "",
        headless: bool = True
    ) -> bool:
        """TikTok에만 업로드"""
        if not self.tiktok:
            print("[SocialMedia] TikTok not initialized")
            return False

        tiktok_caption = self._format_caption_for_tiktok(caption)
        return self.tiktok.upload_video(video_path, caption=tiktok_caption, headless=headless)

    def _format_caption_for_instagram(self, caption: str) -> str:
        """
        Instagram에 최적화된 캡션 포맷

        Args:
            caption: 원본 캡션

        Returns:
            Instagram용 캡션
        """
        # Instagram 해시태그 추가
        instagram_tags = [
            "#묵상", "#기도", "#말씀", "#devotional", "#prayer",
            "#faith", "#blessed", "#godisgood", "#dailydevotion",
            "#reels", "#instareels", "#korea"
        ]

        formatted_caption = caption

        # 해시태그가 없으면 추가
        if "#" not in formatted_caption:
            formatted_caption += "\n\n" + " ".join(instagram_tags)

        return formatted_caption

    def _format_caption_for_tiktok(self, caption: str) -> str:
        """
        TikTok에 최적화된 캡션 포맷

        Args:
            caption: 원본 캡션

        Returns:
            TikTok용 캡션
        """
        # TikTok 해시태그 추가
        tiktok_tags = [
            "#묵상", "#기도", "#말씀", "#devotional", "#prayer",
            "#faith", "#fyp", "#foryou", "#viral", "#blessed",
            "#korea", "#christian"
        ]

        formatted_caption = caption

        # 해시태그가 없으면 추가
        if "#" not in formatted_caption:
            formatted_caption += "\n\n" + " ".join(tiktok_tags)

        return formatted_caption

    def get_available_platforms(self) -> List[str]:
        """사용 가능한 플랫폼 리스트 반환"""
        platforms = []
        if self.instagram:
            platforms.append("instagram")
        if self.tiktok:
            platforms.append("tiktok")
        return platforms

    def is_platform_available(self, platform: str) -> bool:
        """특정 플랫폼이 사용 가능한지 확인"""
        if platform == "instagram":
            return self.instagram is not None
        elif platform == "tiktok":
            return self.tiktok is not None
        return False


# 테스트용 코드
if __name__ == "__main__":
    print("=== 소셜 미디어 멀티 플랫폼 업로더 테스트 ===\n")

    # 업로더 초기화
    uploader = SocialMediaUploader()

    # 사용 가능한 플랫폼 확인
    available = uploader.get_available_platforms()
    print(f"사용 가능한 플랫폼: {available}\n")

    if not available:
        print("❌ 설정된 플랫폼이 없습니다.")
        print("\n환경변수를 설정하세요:")
        print("  - INSTAGRAM_USERNAME, INSTAGRAM_PASSWORD")
        print("  - TIKTOK_USERNAME, TIKTOK_PASSWORD")
    else:
        # 테스트 비디오
        test_video = "output/videos/integrated_test_20241115_120000.mp4"

        if os.path.exists(test_video):
            caption = "오늘의 묵상 메시지 🙏"

            print(f"테스트 비디오: {test_video}")
            print(f"캡션: {caption}\n")

            # 모든 플랫폼에 업로드
            results = uploader.upload_to_all(
                test_video,
                caption=caption,
                headless=False  # 테스트시 브라우저 표시
            )

            # 결과 출력
            print("\n" + "="*60)
            print("📊 업로드 결과:")
            print("="*60)
            for platform, success in results.items():
                status = "✅ 성공" if success else "❌ 실패"
                print(f"  {platform}: {status}")
        else:
            print(f"❌ 테스트 비디오를 찾을 수 없습니다: {test_video}")
            print("test_all_features.py를 먼저 실행하세요.")
