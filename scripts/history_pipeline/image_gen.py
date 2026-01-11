"""
한국사 파이프라인 - 이미지 생성 모듈

- OpenRouter API (Gemini) 사용
- 씬 배경 이미지 생성
- 썸네일 이미지 생성
- PIL 오버레이 (회차 배지)
"""

import os
import sys
import shutil
from typing import Dict, Any, List, Optional
from PIL import Image, ImageDraw, ImageFont

# image 모듈 import
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
from image.gemini import generate_image as gemini_generate_image, generate_thumbnail_image as gemini_generate_thumbnail, GEMINI_FLASH, GEMINI_PRO

# 기본 디렉토리
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))

# 폰트 경로 (우선순위)
FONT_PATHS = [
    os.path.join(BASE_DIR, "fonts", "NanumSquareRoundB.ttf"),
    os.path.join(BASE_DIR, "fonts", "NanumGothicBold.ttf"),
    os.path.join(BASE_DIR, "static", "fonts", "NotoSansKR-Bold.ttf"),
    "/usr/share/fonts/truetype/nanum/NanumSquareRoundB.ttf",
    "/usr/share/fonts/truetype/nanum/NanumGothicBold.ttf",
]


def _get_font(size: int) -> ImageFont.FreeTypeFont:
    """한글 폰트 로드"""
    for font_path in FONT_PATHS:
        if os.path.exists(font_path):
            try:
                return ImageFont.truetype(font_path, size)
            except Exception:
                continue
    return ImageFont.load_default()


def add_episode_badge(
    image_path: str,
    episode_number: int,
    series_name: str = "한국사",
    position: str = "top-left",
    output_path: str = None,
) -> Dict[str, Any]:
    """
    썸네일에 회차 배지 추가 (예: "한국사 18화")

    Args:
        image_path: 원본 이미지 경로
        episode_number: 에피소드 번호
        series_name: 시리즈 이름 (기본: "한국사")
        position: 배지 위치 ("top-left", "top-right", "bottom-left", "bottom-right")
        output_path: 저장 경로 (없으면 원본 덮어쓰기)

    Returns:
        {"ok": True, "image_path": str}
    """
    try:
        # 이미지 열기
        img = Image.open(image_path)
        if img.mode != "RGBA":
            img = img.convert("RGBA")

        draw = ImageDraw.Draw(img)

        # 배지 텍스트
        badge_text = f"{series_name} {episode_number}화"

        # 폰트 크기 (이미지 너비 기준) - 40% 더 크게
        font_size = int(img.width * 0.056)  # 5.6% of width (기존 4% * 1.4)
        font = _get_font(font_size)

        # 텍스트 크기 측정
        bbox = draw.textbbox((0, 0), badge_text, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]

        # 패딩
        padding_x = int(font_size * 0.6)
        padding_y = int(font_size * 0.3)

        # 배지 크기
        badge_width = text_width + padding_x * 2
        badge_height = text_height + padding_y * 2

        # 위치 계산 - 더 안쪽으로
        margin = int(img.width * 0.04)  # 4% margin (기존 2%에서 증가)
        if position == "top-left":
            badge_x = margin
            badge_y = margin
        elif position == "top-right":
            badge_x = img.width - badge_width - margin
            badge_y = margin
        elif position == "bottom-left":
            badge_x = margin
            badge_y = img.height - badge_height - margin
        elif position == "bottom-right":
            badge_x = img.width - badge_width - margin
            badge_y = img.height - badge_height - margin
        else:
            badge_x = margin
            badge_y = margin

        # 배지 배경 (반투명 검정 + 라운드)
        badge_bg = Image.new("RGBA", (badge_width, badge_height), (0, 0, 0, 0))
        badge_draw = ImageDraw.Draw(badge_bg)

        # 라운드 사각형 배경
        corner_radius = int(badge_height * 0.3)
        badge_draw.rounded_rectangle(
            [(0, 0), (badge_width, badge_height)],
            radius=corner_radius,
            fill=(0, 0, 0, 200),  # 반투명 검정
        )

        # 배지 합성
        img.paste(badge_bg, (badge_x, badge_y), badge_bg)

        # 텍스트 그리기 (흰색)
        text_x = badge_x + padding_x
        text_y = badge_y + padding_y

        # 텍스트 아웃라인 (가독성)
        outline_color = (0, 0, 0, 255)
        for dx in [-1, 0, 1]:
            for dy in [-1, 0, 1]:
                if dx != 0 or dy != 0:
                    draw.text((text_x + dx, text_y + dy), badge_text, font=font, fill=outline_color)

        # 메인 텍스트 (흰색)
        draw.text((text_x, text_y), badge_text, font=font, fill=(255, 255, 255, 255))

        # 저장
        save_path = output_path or image_path

        # PNG로 저장 (RGBA 유지)
        if save_path.lower().endswith(".png"):
            img.save(save_path, "PNG")
        else:
            # JPG인 경우 RGB로 변환
            img = img.convert("RGB")
            img.save(save_path, "JPEG", quality=95)

        print(f"[HISTORY-IMAGE] 배지 추가: {badge_text} → {save_path}")
        return {"ok": True, "image_path": save_path}

    except Exception as e:
        return {"ok": False, "error": f"배지 추가 실패: {str(e)}"}


def _generate_image_via_gemini(
    prompt: str,
    output_path: str = None,
    style: str = "realistic",
    aspect_ratio: str = "16:9",
    use_pro: bool = False,
) -> Dict[str, Any]:
    """OpenRouter API로 Gemini 이미지 생성"""
    # 스타일 힌트 추가
    style_hints = {
        "realistic": "photorealistic, highly detailed, 8k resolution",
        "illustration": "digital illustration, artistic, detailed",
        "cinematic": "cinematic lighting, dramatic atmosphere, film quality",
        "historical": "historical illustration, traditional Korean art style, detailed, ink wash painting influence",
    }
    style_suffix = style_hints.get(style, style_hints["realistic"])
    enhanced_prompt = f"{prompt}, {style_suffix}"

    # 비율 → 크기 변환
    size_map = {
        "16:9": "1280x720",
        "1:1": "1024x1024",
        "9:16": "720x1280",
    }
    size = size_map.get(aspect_ratio, "1280x720")

    # 출력 디렉토리 결정
    output_dir = os.path.dirname(output_path) if output_path else None

    # 모델 선택 (Pro는 썸네일용, Flash는 씬 이미지용)
    model = GEMINI_PRO if use_pro else GEMINI_FLASH

    try:
        print(f"[HISTORY-IMAGE] Gemini ({'Pro' if use_pro else 'Flash'}) 호출 중...")
        result = gemini_generate_image(
            prompt=enhanced_prompt,
            size=size,
            output_dir=output_dir,
            model=model
        )

        if result.get("ok"):
            image_url = result.get("image_url", "")

            # gemini.py가 저장한 파일을 원하는 경로로 이동
            if output_path and image_url and not image_url.startswith("data:"):
                if os.path.exists(image_url):
                    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
                    shutil.move(image_url, output_path)
                    print(f"[HISTORY-IMAGE] 저장: {output_path}")
                    return {"ok": True, "image_path": output_path, "cost": result.get("cost", 0)}
                else:
                    return {"ok": True, "image_path": image_url, "cost": result.get("cost", 0)}
            elif output_path and image_url and image_url.startswith("data:"):
                # base64 데이터인 경우 직접 저장
                import base64
                base64_data = image_url.split(",", 1)[1] if "," in image_url else image_url
                image_bytes = base64.b64decode(base64_data)
                os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
                with open(output_path, "wb") as f:
                    f.write(image_bytes)
                print(f"[HISTORY-IMAGE] 저장: {output_path}")
                return {"ok": True, "image_path": output_path, "cost": result.get("cost", 0)}
            else:
                return {"ok": True, "image_url": image_url, "cost": result.get("cost", 0)}
        else:
            return {"ok": False, "error": result.get("error", "Gemini 이미지 생성 실패")}

    except Exception as e:
        return {"ok": False, "error": f"Gemini API 예외: {str(e)}"}


def generate_image(
    prompt: str,
    output_path: str = None,
    style: str = "realistic",
    aspect_ratio: str = "16:9",
    use_pro: bool = False,
) -> Dict[str, Any]:
    """
    이미지 생성 (OpenRouter Gemini 사용)

    Args:
        prompt: 이미지 프롬프트 (영문 권장)
        output_path: 저장 경로 (없으면 base64 반환)
        style: 스타일 힌트 (realistic, illustration, cinematic, historical)
        aspect_ratio: 비율 (16:9, 1:1, 9:16)
        use_pro: Gemini Pro 모델 사용 (썸네일용)

    Returns:
        {"ok": True, "image_path": "...", "cost": float}
    """
    return _generate_image_via_gemini(prompt, output_path, style, aspect_ratio, use_pro)


def generate_scene_images(
    episode_id: str,
    prompts: List[Dict[str, Any]],
    output_dir: str,
    style: str = "historical",
) -> Dict[str, Any]:
    """
    여러 씬 이미지 일괄 생성

    Args:
        episode_id: 에피소드 ID (예: "ep019")
        prompts: [{"scene_index": 1, "prompt": "..."}, ...]
        output_dir: 출력 디렉토리
        style: 스타일

    Returns:
        {"ok": True, "images": [{"scene_index": 1, "path": "..."}], "failed": [...]}
    """
    os.makedirs(output_dir, exist_ok=True)

    results = {"ok": True, "images": [], "failed": []}

    for i, item in enumerate(prompts):
        scene_index = item.get("scene_index", i + 1)
        prompt = item.get("prompt", "")

        if not prompt:
            continue

        output_path = os.path.join(output_dir, f"{episode_id}_scene_{scene_index:02d}.png")

        print(f"[HISTORY-IMAGE] 씬 {scene_index}/{len(prompts)} 생성 중...")
        result = generate_image(
            prompt=prompt,
            output_path=output_path,
            style=style,
        )

        if result.get("ok"):
            results["images"].append({
                "scene_index": scene_index,
                "path": result["image_path"],
            })
        else:
            results["failed"].append({
                "scene_index": scene_index,
                "error": result.get("error"),
            })

    if results["failed"]:
        results["ok"] = len(results["images"]) > 0  # 부분 성공 허용

    print(f"[HISTORY-IMAGE] 완료: {len(results['images'])}개 성공, {len(results['failed'])}개 실패")
    return results


def generate_thumbnail(
    episode_id: str,
    title: str,
    subtitle: str = "",
    output_dir: str = None,
    background_prompt: str = None,
) -> Dict[str, Any]:
    """
    썸네일 이미지 생성

    Args:
        episode_id: 에피소드 ID
        title: 메인 타이틀
        subtitle: 서브 타이틀
        output_dir: 출력 디렉토리
        background_prompt: 배경 이미지 프롬프트

    Returns:
        {"ok": True, "image_path": "..."}
    """
    if not background_prompt:
        background_prompt = f"Epic historical scene for YouTube thumbnail about {title}, dramatic lighting, cinematic composition"

    output_path = os.path.join(output_dir or ".", f"{episode_id}_thumbnail.png")

    return generate_image(
        prompt=background_prompt,
        output_path=output_path,
        style="cinematic",
        aspect_ratio="16:9",
        use_pro=True,  # 썸네일은 고품질 Pro 모델 사용
    )


if __name__ == "__main__":
    print("history_pipeline/image_gen.py 로드 완료")
    print(f"Gemini 모델: Flash={GEMINI_FLASH}, Pro={GEMINI_PRO}")
