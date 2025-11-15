"""
전체 기능 통합 테스트

모든 새로운 기능을 테스트합니다:
- 다양한 폰트 스타일
- 배경 라이브러리
- 애니메이션 효과
- 테마 시스템
"""

from font_manager import FontManager
from background_library import BackgroundLibrary
from animation_effects import AnimationEffects
from video_themes import VideoThemes
from shorts_maker import ShortsMaker
from datetime import datetime

print("="*60)
print("🎬 전체 기능 통합 테스트")
print("="*60)

# 1. 폰트 관리자
print("\n[1/5] 폰트 관리자 테스트...")
font_mgr = FontManager()
font_style = font_mgr.get_random_style()
fonts = font_mgr.get_font_style(font_style)
print(f"   선택된 폰트 스타일: {font_style}")
print(f"   제목 폰트: {fonts['title'] and 'OK' or 'None'}")
print(f"   본문 폰트: {fonts['message'] and 'OK' or 'None'}")

# 2. 배경 라이브러리
print("\n[2/5] 배경 라이브러리 테스트...")
bg_lib = BackgroundLibrary()
bg_styles = ["gradient", "radial", "blurred"]
for bg_style in bg_styles:
    img = bg_lib.create_random_background(1080, 1920, bg_style)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = f"output/backgrounds/test_{bg_style}_{timestamp}.jpg"
    bg_lib.save_background(img, path)
    print(f"   {bg_style}: {path}")

# 3. 애니메이션 효과
print("\n[3/5] 애니메이션 효과 테스트...")
anim = AnimationEffects()
total_frames = 240
test_frames = [0, 30, 120, 210, 240]
for frame in test_frames:
    alpha = anim.fade_in_out(frame, total_frames, 30)
    print(f"   Frame {frame:3d}: Alpha = {alpha:.2f}")

# 4. 비디오 테마
print("\n[4/5] 비디오 테마 테스트...")
theme_name = VideoThemes.get_random_theme("morning")
theme = VideoThemes.get_theme(theme_name)
print(f"   선택된 테마: {theme_name} - {theme['name']}")
print(f"   색상: {theme['color1']} → {theme['color2']}")

# 5. 통합 테스트 - 비디오 생성
print("\n[5/5] 통합 비디오 생성 테스트...")
print("   배경 생성 중...")

# 배경 이미지 생성
timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
bg_img = bg_lib.create_gradient_background(
    1080, 1920,
    theme['color1'],
    theme['color2'],
    direction="vertical"
)
bg_path = f"output/images/integrated_bg_{timestamp}.jpg"
bg_lib.save_background(bg_img, bg_path)

# 비디오 생성
print("   비디오 생성 중...")
maker = ShortsMaker()
test_message = "모든 새로운 기능이 통합되었습니다. 다양한 폰트, 배경, 애니메이션을 즐겨보세요!"
video_path = f"output/videos/integrated_test_{timestamp}.mp4"

result = maker.create_devotional_video(
    bg_path,
    test_message,
    video_path,
    bible_ref=None,
    duration=10
)

if result:
    import os
    file_size = os.path.getsize(result) / 1024
    print(f"   ✅ 비디오 생성 성공!")
    print(f"   파일: {result}")
    print(f"   크기: {file_size:.1f} KB")
else:
    print("   ❌ 비디오 생성 실패")

print("\n" + "="*60)
print("✅ 전체 기능 테스트 완료!")
print("="*60)

print("\n📊 테스트 결과 요약:")
print(f"  ✓ 폰트 스타일: {font_style}")
print(f"  ✓ 배경 스타일: {len(bg_styles)}개 테스트")
print(f"  ✓ 애니메이션: {len(test_frames)}개 프레임 테스트")
print(f"  ✓ 테마: {theme_name}")
print(f"  ✓ 비디오: {result and '생성 완료' or '실패'}")
