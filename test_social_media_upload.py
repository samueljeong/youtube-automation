"""
소셜 미디어 업로드 테스트

Instagram과 TikTok 업로드 기능을 테스트합니다.
"""

import os
import sys
from devotional_scheduler import DevotionalScheduler
from social_media_uploader import SocialMediaUploader


def test_video_generation():
    """비디오 생성 테스트"""
    print("="*60)
    print("1️⃣  비디오 생성 테스트")
    print("="*60)

    scheduler = DevotionalScheduler()

    # 비디오 생성 (업로드 없이)
    print("\n테스트 비디오 생성 중...")
    video_path = scheduler.create_daily_video(
        time_of_day="morning",
        use_tts=False,  # TTS 건너뛰기 (빠른 테스트)
        use_theme=True,
        upload_to_social=False  # 아직 업로드 안 함
    )

    if video_path and os.path.exists(video_path):
        print(f"\n✅ 비디오 생성 성공!")
        print(f"   경로: {video_path}")
        print(f"   크기: {os.path.getsize(video_path) / 1024:.1f} KB")
        return video_path
    else:
        print("\n❌ 비디오 생성 실패")
        return None


def test_social_media_credentials():
    """소셜 미디어 자격증명 확인"""
    print("\n" + "="*60)
    print("2️⃣  소셜 미디어 자격증명 확인")
    print("="*60)

    credentials = {
        "Instagram": {
            "username": os.getenv("INSTAGRAM_USERNAME"),
            "password": os.getenv("INSTAGRAM_PASSWORD")
        },
        "TikTok": {
            "username": os.getenv("TIKTOK_USERNAME"),
            "password": os.getenv("TIKTOK_PASSWORD")
        }
    }

    available_platforms = []

    for platform, creds in credentials.items():
        has_username = bool(creds["username"])
        has_password = bool(creds["password"])
        is_configured = has_username and has_password

        status = "✅ 설정됨" if is_configured else "❌ 미설정"
        print(f"\n{platform}:")
        print(f"  사용자명: {status if has_username else '❌ 미설정'}")
        print(f"  비밀번호: {status if has_password else '❌ 미설정'}")

        if is_configured:
            available_platforms.append(platform.lower())

    if available_platforms:
        print(f"\n✅ 사용 가능한 플랫폼: {', '.join(available_platforms)}")
    else:
        print("\n⚠️  설정된 플랫폼이 없습니다.")
        print("\n환경변수를 설정하세요:")
        print("  export INSTAGRAM_USERNAME=your_username")
        print("  export INSTAGRAM_PASSWORD=your_password")
        print("  export TIKTOK_USERNAME=your_username")
        print("  export TIKTOK_PASSWORD=your_password")

    return available_platforms


def test_upload_to_platforms(video_path, platforms=None):
    """플랫폼별 업로드 테스트"""
    print("\n" + "="*60)
    print("3️⃣  플랫폼 업로드 테스트")
    print("="*60)

    if not video_path or not os.path.exists(video_path):
        print("❌ 업로드할 비디오가 없습니다.")
        return False

    uploader = SocialMediaUploader()
    available = uploader.get_available_platforms()

    if not available:
        print("❌ 설정된 플랫폼이 없어서 업로드를 건너뜁니다.")
        return False

    print(f"\n사용 가능한 플랫폼: {', '.join(available)}")

    # 업로드할 플랫폼 선택
    upload_platforms = platforms if platforms else available

    print(f"업로드할 플랫폼: {', '.join(upload_platforms)}\n")

    # 캡션 생성
    caption = "오늘의 묵상 메시지 🙏\n\n자동화 테스트 중입니다."

    # 업로드 실행
    print("업로드 시작...")
    print("⚠️  브라우저가 열립니다. 수동 개입이 필요할 수 있습니다.\n")

    results = uploader.upload_to_all(
        video_path,
        caption=caption,
        platforms=upload_platforms,
        headless=False  # 테스트시 브라우저 표시
    )

    # 결과 출력
    print("\n" + "="*60)
    print("📊 업로드 결과:")
    print("="*60)

    success_count = 0
    for platform, success in results.items():
        status = "✅ 성공" if success else "❌ 실패"
        print(f"  {platform}: {status}")
        if success:
            success_count += 1

    print("="*60)

    if success_count == len(results):
        print(f"\n🎉 모든 플랫폼 업로드 성공! ({success_count}/{len(results)})")
        return True
    elif success_count > 0:
        print(f"\n⚠️  일부 플랫폼 업로드 성공 ({success_count}/{len(results)})")
        return True
    else:
        print(f"\n❌ 모든 플랫폼 업로드 실패")
        return False


def test_integrated_workflow():
    """통합 워크플로우 테스트 (생성 + 업로드)"""
    print("\n" + "="*60)
    print("4️⃣  통합 워크플로우 테스트 (생성 + 업로드)")
    print("="*60)

    scheduler = DevotionalScheduler()

    # 사용 가능한 플랫폼 확인
    if scheduler.social_media_uploader:
        available = scheduler.social_media_uploader.get_available_platforms()
        if available:
            print(f"\n사용 가능한 플랫폼: {', '.join(available)}")
            print("비디오 생성 및 자동 업로드 시작...\n")

            # 비디오 생성 + 자동 업로드
            video_path = scheduler.create_daily_video(
                time_of_day="evening",
                use_tts=False,  # TTS 건너뛰기
                use_theme=True,
                upload_to_social=True,  # 자동 업로드 활성화
                platforms=available  # 모든 플랫폼
            )

            if video_path:
                print("\n✅ 통합 워크플로우 성공!")
                return True
            else:
                print("\n❌ 통합 워크플로우 실패")
                return False
        else:
            print("\n⚠️  설정된 플랫폼이 없어서 통합 테스트를 건너뜁니다.")
            return False
    else:
        print("\n⚠️  소셜 미디어 업로더가 초기화되지 않았습니다.")
        return False


def main():
    """메인 테스트 함수"""
    print("\n" + "="*60)
    print("🧪 소셜 미디어 업로드 통합 테스트")
    print("="*60)

    # 테스트 모드 선택
    if len(sys.argv) > 1:
        mode = sys.argv[1]
    else:
        print("\n테스트 모드를 선택하세요:")
        print("  1. 전체 테스트 (생성 + 자격증명 확인 + 업로드)")
        print("  2. 비디오 생성만")
        print("  3. 자격증명 확인만")
        print("  4. 업로드만 (기존 비디오 사용)")
        print("  5. 통합 워크플로우 (생성 + 자동 업로드)")
        mode = input("\n선택 (1-5): ").strip()

    if mode == "1":
        # 전체 테스트
        video_path = test_video_generation()
        available_platforms = test_social_media_credentials()

        if video_path and available_platforms:
            test_upload_to_platforms(video_path, available_platforms)
        else:
            print("\n⚠️  업로드 테스트를 건너뜁니다.")

    elif mode == "2":
        # 비디오 생성만
        test_video_generation()

    elif mode == "3":
        # 자격증명 확인만
        test_social_media_credentials()

    elif mode == "4":
        # 업로드만
        print("\n업로드할 비디오 경로를 입력하세요:")
        print("(예: output/videos/devotional_20241115_0900.mp4)")
        video_path = input("경로: ").strip()

        if os.path.exists(video_path):
            test_upload_to_platforms(video_path)
        else:
            print(f"❌ 비디오를 찾을 수 없습니다: {video_path}")

    elif mode == "5":
        # 통합 워크플로우
        test_integrated_workflow()

    else:
        print("❌ 잘못된 선택입니다.")


if __name__ == "__main__":
    main()
