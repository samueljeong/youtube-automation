"""
TikTok 업로드 자동화

Playwright를 사용하여 TikTok에 동영상을 업로드합니다.
"""

import os
import time
from typing import Optional
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout


class TikTokUploader:
    """TikTok 업로드 자동화"""

    def __init__(self, username: str = None, password: str = None):
        """
        Args:
            username: TikTok 사용자명 또는 이메일 (환경변수 TIKTOK_USERNAME 사용 가능)
            password: TikTok 비밀번호 (환경변수 TIKTOK_PASSWORD 사용 가능)
        """
        self.username = username or os.getenv("TIKTOK_USERNAME")
        self.password = password or os.getenv("TIKTOK_PASSWORD")

        if not self.username or not self.password:
            raise ValueError("TikTok credentials not provided. Set TIKTOK_USERNAME and TIKTOK_PASSWORD")

    def upload_video(
        self,
        video_path: str,
        caption: str = "",
        headless: bool = True,
        timeout: int = 60000
    ) -> bool:
        """
        TikTok에 동영상 업로드

        Args:
            video_path: 업로드할 비디오 파일 경로
            caption: 캡션 텍스트
            headless: 헤드리스 모드 (True = UI 없음)
            timeout: 타임아웃 (밀리초)

        Returns:
            성공 여부
        """
        if not os.path.exists(video_path):
            print(f"[TikTok] Video file not found: {video_path}")
            return False

        try:
            with sync_playwright() as p:
                print("[TikTok] Launching browser...")
                browser = p.chromium.launch(headless=headless)
                context = browser.new_context(
                    viewport={"width": 1280, "height": 720},
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                )
                page = context.new_page()

                # TikTok 로그인
                print("[TikTok] Logging in...")
                if not self._login(page, timeout):
                    browser.close()
                    return False

                # 업로드 페이지로 이동
                print("[TikTok] Navigating to upload page...")
                page.goto("https://www.tiktok.com/upload", timeout=timeout)
                time.sleep(3)

                # 파일 업로드
                print("[TikTok] Uploading video...")
                try:
                    # iframe 내부의 파일 입력 찾기
                    file_input = page.locator('input[type="file"]').first
                    file_input.set_input_files(os.path.abspath(video_path))
                    time.sleep(10)  # 업로드 및 처리 대기
                except Exception as e:
                    print(f"[TikTok] Error uploading file: {e}")
                    browser.close()
                    return False

                # 캡션 입력
                if caption:
                    print(f"[TikTok] Adding caption: {caption[:50]}...")
                    try:
                        # 캡션 입력란 찾기 (여러 가능한 셀렉터 시도)
                        caption_selectors = [
                            'div[contenteditable="true"]',
                            'div[data-text="true"]',
                            'div.public-DraftEditor-content',
                            'div[role="textbox"]'
                        ]

                        caption_found = False
                        for selector in caption_selectors:
                            try:
                                caption_box = page.locator(selector).first
                                if caption_box.count() > 0:
                                    caption_box.click()
                                    caption_box.fill(caption)
                                    caption_found = True
                                    break
                            except:
                                continue

                        if not caption_found:
                            print("[TikTok] Warning: Could not find caption input")

                        time.sleep(2)
                    except Exception as e:
                        print(f"[TikTok] Warning: Could not add caption: {e}")

                # 게시 설정 (공개 범위 등)
                try:
                    # "누구나 볼 수 있음" 옵션이 기본값인지 확인
                    # 필요시 추가 설정 가능
                    pass
                except:
                    pass

                # 게시 버튼 클릭
                print("[TikTok] Publishing...")
                try:
                    # 게시 버튼 찾기 (여러 가능한 텍스트)
                    publish_texts = ["게시", "Post", "게시하기", "Publish"]
                    publish_clicked = False

                    for text in publish_texts:
                        try:
                            publish_button = page.locator(f'button:has-text("{text}")').first
                            if publish_button.count() > 0:
                                publish_button.click(timeout=timeout)
                                publish_clicked = True
                                break
                        except:
                            continue

                    if not publish_clicked:
                        print("[TikTok] Warning: Could not find publish button")
                        browser.close()
                        return False

                    # 업로드 완료 대기
                    time.sleep(10)

                    # 성공 확인 (URL이 업로드 페이지에서 변경되었는지 확인)
                    current_url = page.url
                    if "upload" not in current_url or "upload?state=success" in current_url:
                        print("[TikTok] ✅ Upload successful!")
                        browser.close()
                        return True
                    else:
                        # 추가 대기
                        time.sleep(5)
                        print("[TikTok] ✅ Upload completed!")
                        browser.close()
                        return True

                except Exception as e:
                    print(f"[TikTok] Error publishing: {e}")
                    browser.close()
                    return False

        except Exception as e:
            print(f"[TikTok] ❌ Upload failed: {e}")
            return False

    def _login(self, page, timeout: int) -> bool:
        """
        TikTok 로그인

        Args:
            page: Playwright 페이지 객체
            timeout: 타임아웃 (밀리초)

        Returns:
            성공 여부
        """
        try:
            page.goto("https://www.tiktok.com/login/phone-or-email/email", timeout=timeout)
            time.sleep(3)

            # 쿠키 허용 버튼 클릭 (있는 경우)
            try:
                accept_cookies = page.locator('button').filter(has_text="모두 허용")
                if accept_cookies.count() == 0:
                    accept_cookies = page.locator('button').filter(has_text="Accept all")

                if accept_cookies.count() > 0:
                    accept_cookies.first.click()
                    time.sleep(1)
            except:
                pass

            # 이메일/사용자명 입력
            try:
                # 이메일 입력란 찾기
                email_input = page.locator('input[name="username"]')
                if email_input.count() == 0:
                    email_input = page.locator('input[type="text"]').first

                email_input.fill(self.username)
                time.sleep(1)
            except Exception as e:
                print(f"[TikTok] Error entering username: {e}")
                return False

            # 비밀번호 입력
            try:
                password_input = page.locator('input[type="password"]').first
                password_input.fill(self.password)
                time.sleep(1)
            except Exception as e:
                print(f"[TikTok] Error entering password: {e}")
                return False

            # 로그인 버튼 클릭
            try:
                login_texts = ["로그인", "Log in", "로그인하기"]
                login_clicked = False

                for text in login_texts:
                    try:
                        login_button = page.locator(f'button:has-text("{text}")').first
                        if login_button.count() > 0:
                            login_button.click()
                            login_clicked = True
                            break
                    except:
                        continue

                if not login_clicked:
                    print("[TikTok] Could not find login button")
                    return False

                time.sleep(5)
            except Exception as e:
                print(f"[TikTok] Error clicking login button: {e}")
                return False

            # 로그인 확인
            current_url = page.url
            if "login" not in current_url or "tiktok.com" in current_url:
                print("[TikTok] Login successful!")
                time.sleep(2)
                return True
            else:
                print("[TikTok] Login failed - still on login page")
                return False

        except Exception as e:
            print(f"[TikTok] Login error: {e}")
            return False


# 테스트용 코드
if __name__ == "__main__":
    # 환경변수에서 자격증명 로드
    uploader = TikTokUploader()

    # 테스트 비디오 경로
    test_video = "output/videos/integrated_test_20241115_120000.mp4"

    if os.path.exists(test_video):
        caption = "오늘의 묵상 메시지 🙏 #묵상 #기도 #말씀 #devotional #prayer #faith"

        print("=== TikTok Upload Test ===")
        result = uploader.upload_video(
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
