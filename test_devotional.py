"""
묵상 이미지 생성 테스트
"""

from PIL import Image, ImageDraw
from shorts_maker import ShortsMaker

# 1. 간단한 그라데이션 배경 생성
def create_gradient_background(width, height, color1, color2):
    """세로 그라데이션 배경 생성"""
    base = Image.new('RGB', (width, height), color1)
    top = Image.new('RGB', (width, height), color2)
    mask = Image.new('L', (width, height))
    mask_data = []
    for y in range(height):
        mask_data.extend([int(255 * (y / height))] * width)
    mask.putdata(mask_data)
    base.paste(top, (0, 0), mask)
    return base

# 2. 배경 이미지 생성
print("Creating gradient background...")
bg = create_gradient_background(
    1080,
    1920,
    (50, 100, 150),   # 진한 파란색
    (200, 150, 100)   # 따뜻한 오렌지
)
bg.save("output/images/test_bg.jpg", quality=95)
print("✅ Background saved: output/images/test_bg.jpg")

# 3. 묵상 이미지 생성
print("\nCreating devotional image...")
maker = ShortsMaker()

test_message = "주님의 은혜가 오늘도 우리와 함께 하시기를 기도합니다. 평안한 하루 되세요."
test_ref = "시편 23:1"

result = maker.create_devotional_image(
    "output/images/test_bg.jpg",
    test_message,
    "output/images/test_devotional.jpg",
    test_ref
)

if result:
    print(f"✅ Devotional image created: {result}")
else:
    print("❌ Failed to create devotional image")
