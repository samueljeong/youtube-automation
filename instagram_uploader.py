"""
Instagram Reels 업로드 자동화

Playwright를 사용하여 Instagram에 Reels를 업로드합니다.
"""

import os
import time
from typing import Optional
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout


class InstagramUploader:
    """Instagram Reels 업로드 자동화"""

    def __init__(self, username: str = None, password: str = None):
        """
        Args:
            username: Instagram 사용자명 (환경변수 INSTAGRAM_USERNAME 사용 가능)
            password: Instagram 비밀번호 (환경변수 INSTAGRAM_PASSWORD 사용 가능)
        """
        self.username = username or os.getenv("INSTAGRAM_USERNAME")
        self.password = password or os.getenv("INSTAGRAM_PASSWORD")

        if not self.username or not self.password:
            raise ValueError("Instagram credentials not provided. Set INSTAGRAM_USERNAME and INSTAGRAM_PASSWORD")

    def upload_reel(
        self,
        video_path: str,
        caption: str = "",
        headless: bool = True,
        timeout: int = 60000
    ) -> bool:
        """
        Instagram에 Reels 업로드

        Args:
            video_path: 업로드할 비디오 파일 경로
            caption: 캡션 텍스트
            headless: 헤드리스 모드 (True = UI 없음)
            timeout: 타임아웃 (밀리초)

        Returns:
            성공 여부
        """
        if not os.path.exists(video_path):
            print(f"[Instagram] Video file not found: {video_path}")
            return False

        try:
            with sync_playwright() as p:
                print("[Instagram] Launching browser...")
                browser = p.chromium.launch(headless=headless)
                context = browser.new_context(
                    viewport={"width": 1280, "height": 720},
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                )
                page = context.new_page()

                # Instagram 로그인
                print("[Instagram] Logging in...")
                if not self._login(page, timeout):
                    browser.close()
                    return False

                # Reels 업로드 페이지로 이동
                print("[Instagram] Navigating to upload page...")
                time.sleep(2)

                # Create 버튼 클릭
                try:
                    # 새 게시물 만들기 버튼 찾기
                    create_button = page.locator('a[href="#"]').filter(has_text="만들기")
                    if create_button.count() == 0:
                        create_button = page.locator('a[href="#"]').filter(has_text="Create")

                    create_button.first.click(timeout=timeout)
                    time.sleep(2)
                except Exception as e:
                    print(f"[Instagram] Error clicking create button: {e}")
                    browser.close()
                    return False

                # 파일 업로드
                print("[Instagram] Uploading video...")
                try:
                    # 파일 입력 찾기
                    file_input = page.locator('input[type="file"]')
                    file_input.set_input_files(os.path.abspath(video_path))
                    time.sleep(5)  # 업로드 대기
                except Exception as e:
                    print(f"[Instagram] Error uploading file: {e}")
                    browser.close()
                    return False

                # 다음 버튼 클릭 (여러 단계)
                print("[Instagram] Processing upload...")
                for i in range(3):  # 최대 3번 "다음" 클릭
                    try:
                        next_button = page.locator('button').filter(has_text="다음")
                        if next_button.count() == 0:
                            next_button = page.locator('button').filter(has_text="Next")

                        if next_button.count() > 0:
                            next_button.first.click(timeout=timeout)
                            time.sleep(2)
                        else:
                            break
                    except:
                        break

                # 캡션 입력
                if caption:
                    print(f"[Instagram] Adding caption: {caption[:50]}...")
                    try:
                        caption_area = page.locator('textarea[aria-label*="캡션"]')
                        if caption_area.count() == 0:
                            caption_area = page.locator('textarea[aria-label*="caption"]')

                        caption_area.first.fill(caption)
                        time.sleep(1)
                    except Exception as e:
                        print(f"[Instagram] Warning: Could not add caption: {e}")

                # 공유 버튼 클릭
                print("[Instagram] Publishing...")
                try:
                    share_button = page.locator('button').filter(has_text="공유하기")
                    if share_button.count() == 0:
                        share_button = page.locator('button').filter(has_text="Share")

                    share_button.first.click(timeout=timeout)
                    time.sleep(5)  # 업로드 완료 대기
                except Exception as e:
                    print(f"[Instagram] Error publishing: {e}")
                    browser.close()
                    return False

                print("[Instagram] ✅ Upload successful!")
                browser.close()
                return True

        except Exception as e:
            print(f"[Instagram] ❌ Upload failed: {e}")
            return False

    def _login(self, page, timeout: int) -> bool:
        """
        Instagram 로그인

        Args:
            page: Playwright 페이지 객체
            timeout: 타임아웃 (밀리초)

        Returns:
            성공 여부
        """
        try:
            page.goto("https://www.instagram.com/", timeout=timeout)
            time.sleep(3)

            # 쿠키 허용 버튼 클릭 (있는 경우)
            try:
                accept_cookies = page.locator('button').filter(has_text="모든 쿠키 허용")
                if accept_cookies.count() == 0:
                    accept_cookies = page.locator('button').filter(has_text="Accept")

                if accept_cookies.count() > 0:
                    accept_cookies.first.click()
                    time.sleep(1)
            except:
                pass

            # 사용자명 입력
            username_input = page.locator('input[name="username"]')
            username_input.fill(self.username)
            time.sleep(1)

            # 비밀번호 입력
            password_input = page.locator('input[name="password"]')
            password_input.fill(self.password)
            time.sleep(1)

            # 로그인 버튼 클릭
            login_button = page.locator('button[type="submit"]')
            login_button.click()
            time.sleep(5)

            # 로그인 확인
            if "instagram.com" in page.url and "/accounts/login" not in page.url:
                print("[Instagram] Login successful!")

                # "정보 저장" 팝업 처리
                try:
                    not_now = page.locator('button').filter(has_text="나중에 하기")
                    if not_now.count() == 0:
                        not_now = page.locator('button').filter(has_text="Not Now")

                    if not_now.count() > 0:
                        not_now.first.click()
                        time.sleep(1)
                except:
                    pass

                # "알림 켜기" 팝업 처리
                try:
                    not_now = page.locator('button').filter(has_text="나중에 하기")
                    if not_now.count() == 0:
                        not_now = page.locator('button').filter(has_text="Not Now")

                    if not_now.count() > 0:
                        not_now.first.click()
                        time.sleep(1)
                except:
                    pass

                return True
            else:
                print("[Instagram] Login failed - still on login page")
                return False

        except Exception as e:
            print(f"[Instagram] Login error: {e}")
            return False


# 테스트용 코드
if __name__ == "__main__":
    # 환경변수에서 자격증명 로드
    uploader = InstagramUploader()

    # 테스트 비디오 경로
    test_video = "output/videos/integrated_test_20241115_120000.mp4"

    if os.path.exists(test_video):
        caption = "오늘의 묵상 메시지 🙏\n\n#묵상 #기도 #말씀 #devotional #prayer"

        print("=== Instagram Reels Upload Test ===")
        result = uploader.upload_reel(
            test_video,
            caption=caption,
            headless=False  # 테스트시 브라우저 표시
        )

        if result:
            print("✅ Upload test successful!")
        else:
            print("❌ Upload test failed")
    else:
        print(f"❌ Test video not found: {test_video}")
        print("Please run test_all_features.py first to generate a test video")
