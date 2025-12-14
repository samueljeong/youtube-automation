"""
Gemini 이미지 생성 모듈
OpenRouter API를 통한 Gemini 2.5 Flash 이미지 생성
"""

import os
import json
import time
import base64
from datetime import datetime
from io import BytesIO
from typing import Optional, Tuple, Dict, Any

import requests
from PIL import Image as PILImage


# 상수
OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"
GEMINI_MODEL = "google/gemini-2.5-flash-image-preview"
DEFAULT_TIMEOUT = 90
MAX_RETRIES = 3
INITIAL_RETRY_DELAY = 5


def _get_aspect_instruction(size: str) -> Tuple[str, int, int]:
    """사이즈에 따른 비율 지시문과 타겟 크기 반환"""
    if size == "1792x1024" or "16:9" in size or size == "1280x720":
        instruction = (
            "CRITICAL: You MUST generate the image in EXACT 16:9 WIDESCREEN LANDSCAPE aspect ratio. "
            "The width MUST be 1.78 times the height. Target dimensions: 1920x1080 pixels or 1280x720 pixels. "
            "This is MANDATORY for YouTube video format. DO NOT generate square or portrait images."
        )
        return instruction, 1280, 720
    elif size == "1024x1792" or "9:16" in size or size == "720x1280":
        instruction = (
            "CRITICAL: You MUST generate the image in EXACT 9:16 VERTICAL PORTRAIT aspect ratio. "
            "The height MUST be 1.78 times the width. Target dimensions: 1080x1920 pixels or 720x1280 pixels. "
            "This is MANDATORY for YouTube Shorts format. DO NOT generate square or landscape images."
        )
        return instruction, 720, 1280
    else:
        instruction = (
            "CRITICAL: You MUST generate the image in EXACT 16:9 WIDESCREEN LANDSCAPE aspect ratio. "
            "Target dimensions: 1920x1080 or 1280x720 pixels. MANDATORY for YouTube."
        )
        return instruction, 1280, 720


def _call_openrouter_api(prompt: str, api_key: str) -> Dict[str, Any]:
    """OpenRouter API 호출 (재시도 로직 포함)"""
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://drama-generator.app",
        "X-Title": "Drama Image Generator"
    }

    payload = {
        "model": GEMINI_MODEL,
        "modalities": ["text", "image"],
        "messages": [
            {
                "role": "user",
                "content": [{"type": "text", "text": prompt}]
            }
        ]
    }

    retry_delay = INITIAL_RETRY_DELAY
    last_error = None

    for attempt in range(MAX_RETRIES):
        try:
            response = requests.post(
                OPENROUTER_API_URL,
                headers=headers,
                json=payload,
                timeout=DEFAULT_TIMEOUT
            )

            if response.status_code == 200:
                return {"ok": True, "data": response.json()}
            elif response.status_code in [429, 502, 503, 504] or "quota" in response.text.lower():
                last_error = response.text
                error_type = "서버 오류" if response.status_code >= 500 else "quota/rate limit"
                print(f"[GEMINI][RETRY] {error_type} ({response.status_code}) (시도 {attempt + 1}/{MAX_RETRIES})")
                time.sleep(retry_delay)
                retry_delay *= 2
                continue
            else:
                return {"ok": False, "error": f"API 오류 ({response.status_code}): {response.text[:200]}"}

        except requests.exceptions.Timeout:
            last_error = "요청 시간 초과"
            print(f"[GEMINI][RETRY] 타임아웃 (시도 {attempt + 1}/{MAX_RETRIES})")
            time.sleep(retry_delay)
            continue
        except Exception as e:
            last_error = str(e)
            print(f"[GEMINI][RETRY] 오류: {e} (시도 {attempt + 1}/{MAX_RETRIES})")
            time.sleep(retry_delay)
            continue

    return {"ok": False, "error": f"API 호출 실패 (재시도 {MAX_RETRIES}회): {last_error}"}


def _extract_image_from_response(result: Dict[str, Any]) -> Optional[str]:
    """API 응답에서 base64 이미지 데이터 추출"""
    choices = result.get("choices", [])
    if not choices:
        return None

    message = choices[0].get("message", {})

    # 1. images 배열 확인
    images = message.get("images", [])
    for img in images:
        if isinstance(img, str):
            if img.startswith("data:"):
                return img.split(",", 1)[1] if "," in img else img
            return img
        elif isinstance(img, dict):
            for key in ["data", "b64_json", "url"]:
                if key in img:
                    val = img[key]
                    if isinstance(val, str):
                        if val.startswith("data:"):
                            return val.split(",", 1)[1] if "," in val else val
                        return val

    # 2. content 배열 확인
    content = message.get("content", [])
    if isinstance(content, list):
        for item in content:
            if not isinstance(item, dict):
                continue

            item_type = item.get("type", "")

            if item_type == "image_url":
                url = item.get("image_url", {}).get("url", "")
                if url.startswith("data:"):
                    return url.split(",", 1)[1] if "," in url else url
            elif item_type == "image":
                image_data = item.get("image", {})
                if isinstance(image_data, dict):
                    return image_data.get("data") or image_data.get("base64")
                elif isinstance(image_data, str):
                    return image_data
            elif "inline_data" in item:
                return item.get("inline_data", {}).get("data")
            elif "source" in item:
                source = item.get("source", {})
                if source.get("type") == "base64":
                    return source.get("data")

    return None


def _process_and_save_image(
    base64_data: str,
    target_width: int,
    target_height: int,
    output_dir: str,
    filename_prefix: str = "gemini"
) -> Optional[str]:
    """Base64 이미지를 처리하고 파일로 저장"""
    try:
        # Base64 디코딩
        image_bytes = base64.b64decode(base64_data)
        img = PILImage.open(BytesIO(image_bytes))

        original_size = len(image_bytes)
        print(f"[GEMINI] 원본 이미지: {img.width}x{img.height}, {original_size/1024:.1f}KB")

        # 비율 맞추기 (크롭)
        target_ratio = target_width / target_height
        current_ratio = img.width / img.height

        if abs(current_ratio - target_ratio) > 0.05:
            if current_ratio > target_ratio:
                new_width = int(img.height * target_ratio)
                left = (img.width - new_width) // 2
                img = img.crop((left, 0, left + new_width, img.height))
            else:
                new_height = int(img.width / target_ratio)
                top = (img.height - new_height) // 2
                img = img.crop((0, top, img.width, top + new_height))
            print(f"[GEMINI] 크롭 완료: {img.width}x{img.height}")

        # 리사이즈
        if img.width > target_width or img.height > target_height:
            img = img.resize((target_width, target_height), PILImage.Resampling.LANCZOS)
            print(f"[GEMINI] 리사이즈 완료: {target_width}x{target_height}")

        # RGB 변환
        if img.mode == 'RGBA':
            background = PILImage.new('RGB', img.size, (255, 255, 255))
            background.paste(img, mask=img.split()[3])
            img = background
        elif img.mode != 'RGB':
            img = img.convert('RGB')

        # 파일 저장
        os.makedirs(output_dir, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        filename = f"{filename_prefix}_{timestamp}.jpg"
        filepath = os.path.join(output_dir, filename)

        img.save(filepath, 'JPEG', quality=85, optimize=True)

        final_size = os.path.getsize(filepath)
        print(f"[GEMINI] 저장 완료: {final_size/1024:.1f}KB")

        return f"/static/images/{filename}"

    except Exception as e:
        print(f"[GEMINI][ERROR] 이미지 처리 실패: {e}")
        return None


def generate_image(
    prompt: str,
    size: str = "1280x720",
    output_dir: Optional[str] = None
) -> Dict[str, Any]:
    """
    Gemini를 사용하여 이미지 생성

    Args:
        prompt: 이미지 생성 프롬프트
        size: 이미지 크기 (예: "1280x720", "720x1280")
        output_dir: 이미지 저장 디렉토리 (기본: static/images)

    Returns:
        {"ok": True, "image_url": str, "cost": float} 또는
        {"ok": False, "error": str}
    """
    api_key = os.getenv("OPENROUTER_API_KEY", "")
    if not api_key:
        return {"ok": False, "error": "OPENROUTER_API_KEY 환경변수가 설정되지 않았습니다."}

    if not prompt:
        return {"ok": False, "error": "프롬프트가 없습니다."}

    # 비율 지시문 추가
    aspect_instruction, target_width, target_height = _get_aspect_instruction(size)
    enhanced_prompt = f"{aspect_instruction}\n\n{prompt}"

    print(f"[GEMINI] 이미지 생성 시작 - 크기: {size}")

    # API 호출
    result = _call_openrouter_api(enhanced_prompt, api_key)
    if not result.get("ok"):
        return result

    # 이미지 추출
    base64_data = _extract_image_from_response(result["data"])
    if not base64_data:
        return {"ok": False, "error": "Gemini에서 이미지를 생성하지 못했습니다."}

    # 이미지 처리 및 저장
    if output_dir is None:
        output_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'static', 'images')

    image_url = _process_and_save_image(
        base64_data, target_width, target_height, output_dir, "gemini"
    )

    if not image_url:
        # 저장 실패 시 base64 URL 반환
        image_url = f"data:image/png;base64,{base64_data}"

    # 비용: ~$0.039/장
    cost = 0.039
    print(f"[GEMINI] 완료 - 비용: ${cost}")

    return {
        "ok": True,
        "image_url": image_url,
        "cost": cost,
        "provider": "gemini"
    }


def generate_thumbnail_image(
    prompt: str,
    text_overlay: Optional[Dict[str, str]] = None,
    output_dir: Optional[str] = None
) -> Dict[str, Any]:
    """
    썸네일 이미지 생성 (16:9 고정)

    Args:
        prompt: 이미지 생성 프롬프트
        text_overlay: 텍스트 오버레이 정보 {"main": str, "sub": str}
        output_dir: 이미지 저장 디렉토리

    Returns:
        {"ok": True, "image_url": str, "cost": float} 또는
        {"ok": False, "error": str}
    """
    # 썸네일은 항상 16:9
    return generate_image(prompt, size="1280x720", output_dir=output_dir)
