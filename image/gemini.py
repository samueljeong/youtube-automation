"""
Gemini 이미지 생성 모듈
OpenRouter API를 통한 Gemini 이미지 생성

지원 모델:
- gemini-2.5-flash: 씬 이미지 생성 (빠르고 저렴)
- gemini-3-pro: 썸네일 생성 (고품질)
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
DEFAULT_TIMEOUT = 120
MAX_RETRIES = 3
INITIAL_RETRY_DELAY = 5

# 모델 상수
GEMINI_FLASH = "google/gemini-2.5-flash-image-preview"  # 씬 이미지용
GEMINI_PRO = "google/gemini-3-pro-image-preview"        # 썸네일용 (고품질)

# 모델별 비용 (USD)
MODEL_COSTS = {
    GEMINI_FLASH: 0.039,
    GEMINI_PRO: 0.05,
}


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
    elif size == "1024x1024" or "1:1" in size or size == "720x720":
        # 1:1 정사각형 - 크롭 없음
        instruction = (
            "Generate a 1:1 SQUARE image. The width and height must be equal. "
            "Target dimensions: 1024x1024 pixels. DO NOT generate rectangular images."
        )
        return instruction, 1024, 1024
    else:
        instruction = (
            "CRITICAL: You MUST generate the image in EXACT 16:9 WIDESCREEN LANDSCAPE aspect ratio. "
            "Target dimensions: 1920x1080 or 1280x720 pixels. MANDATORY for YouTube."
        )
        return instruction, 1280, 720


def _call_openrouter_api(prompt: str, api_key: str, model: str = GEMINI_FLASH) -> Dict[str, Any]:
    """OpenRouter API 호출 (재시도 로직 포함)"""
    # API 키 검증 로깅
    if not api_key:
        print("[GEMINI][ERROR] API 키가 비어있습니다!")
        return {"ok": False, "error": "OPENROUTER_API_KEY가 설정되지 않았습니다"}

    key_preview = f"{api_key[:8]}...{api_key[-4:]}" if len(api_key) > 12 else "***"
    print(f"[GEMINI][DEBUG] API 호출 시작 - 모델: {model}, 키: {key_preview}, 프롬프트 길이: {len(prompt)}자")

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://drama-generator.app",
        "X-Title": "Drama Image Generator"
    }

    payload = {
        "model": model,
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
            print(f"[GEMINI][DEBUG] API 요청 시도 {attempt + 1}/{MAX_RETRIES}...")
            response = requests.post(
                OPENROUTER_API_URL,
                headers=headers,
                json=payload,
                timeout=DEFAULT_TIMEOUT
            )

            print(f"[GEMINI][DEBUG] 응답 상태: {response.status_code}")

            if response.status_code == 200:
                data = response.json()
                # 응답 구조 로깅
                choices = data.get("choices", [])
                if choices:
                    msg = choices[0].get("message", {})
                    content = msg.get("content", [])
                    images = msg.get("images", [])
                    print(f"[GEMINI][DEBUG] 응답 구조 - choices: {len(choices)}, content 타입: {type(content).__name__}, images: {len(images)}")
                else:
                    print(f"[GEMINI][DEBUG] 응답에 choices 없음 - 키: {list(data.keys())[:5]}")
                return {"ok": True, "data": data}
            elif response.status_code in [429, 502, 503, 504] or "quota" in response.text.lower():
                last_error = response.text
                error_type = "서버 오류" if response.status_code >= 500 else "quota/rate limit"
                print(f"[GEMINI][RETRY] {error_type} ({response.status_code}) (시도 {attempt + 1}/{MAX_RETRIES})")
                print(f"[GEMINI][DEBUG] 오류 응답: {response.text[:300]}")
                time.sleep(retry_delay)
                retry_delay *= 2
                continue
            else:
                print(f"[GEMINI][ERROR] API 오류 ({response.status_code}): {response.text[:500]}")
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
        print("[GEMINI][DEBUG] _extract: choices 없음")
        return None

    message = choices[0].get("message", {})

    # 1. images 배열 확인
    images = message.get("images", [])
    if images:
        print(f"[GEMINI][DEBUG] _extract: images 배열 발견 - 개수: {len(images)}")
        for i, img in enumerate(images):
            print(f"[GEMINI][DEBUG] _extract: images[{i}] 타입: {type(img).__name__}")
            if isinstance(img, str):
                print(f"[GEMINI][DEBUG] _extract: images[{i}] 문자열 길이: {len(img)}, 시작: {img[:50] if len(img) > 50 else img}")
                if img.startswith("data:"):
                    return img.split(",", 1)[1] if "," in img else img
                # base64 문자열로 간주
                if len(img) > 100:  # base64는 보통 매우 김
                    print(f"[GEMINI][DEBUG] _extract: images[{i}]를 base64로 반환")
                    return img
            elif isinstance(img, dict):
                print(f"[GEMINI][DEBUG] _extract: images[{i}] dict 키: {list(img.keys())}")

                # OpenRouter 형식: {"type": "image_url", "image_url": {"url": "data:..."}, "index": 0}
                if "image_url" in img:
                    image_url_obj = img["image_url"]
                    if isinstance(image_url_obj, dict) and "url" in image_url_obj:
                        url = image_url_obj["url"]
                        print(f"[GEMINI][DEBUG] _extract: images[{i}][image_url][url] 발견, 길이: {len(url)}")
                        if url.startswith("data:"):
                            return url.split(",", 1)[1] if "," in url else url
                        return url
                    elif isinstance(image_url_obj, str):
                        print(f"[GEMINI][DEBUG] _extract: images[{i}][image_url] 문자열, 길이: {len(image_url_obj)}")
                        if image_url_obj.startswith("data:"):
                            return image_url_obj.split(",", 1)[1] if "," in image_url_obj else image_url_obj
                        return image_url_obj

                # 기존 형식 지원
                for key in ["data", "b64_json", "url", "base64"]:
                    if key in img:
                        val = img[key]
                        if isinstance(val, str):
                            print(f"[GEMINI][DEBUG] _extract: images[{i}][{key}] 발견, 길이: {len(val)}")
                            if val.startswith("data:"):
                                return val.split(",", 1)[1] if "," in val else val
                            return val

    # 2. content 배열 확인
    content = message.get("content", [])
    if isinstance(content, list):
        print(f"[GEMINI][DEBUG] _extract: content 리스트 - 개수: {len(content)}")
        for item in content:
            if not isinstance(item, dict):
                continue

            item_type = item.get("type", "")
            print(f"[GEMINI][DEBUG] _extract: content item 타입: {item_type}, 키: {list(item.keys())}")

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

    print(f"[GEMINI][DEBUG] _extract: 이미지 추출 실패 - message 키: {list(message.keys())}")
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
        print(f"[GEMINI] 저장 완료: {filepath} ({final_size/1024:.1f}KB)")

        # 실제 파일 경로 반환 (기존: 항상 /static/images/ 반환하던 버그 수정)
        return filepath

    except Exception as e:
        print(f"[GEMINI][ERROR] 이미지 처리 실패: {e}")
        return None


def generate_image(
    prompt: str,
    size: str = "1280x720",
    output_dir: Optional[str] = None,
    model: str = GEMINI_FLASH,
    add_aspect_instruction: bool = True
) -> Dict[str, Any]:
    """
    Gemini를 사용하여 이미지 생성

    Args:
        prompt: 이미지 생성 프롬프트
        size: 이미지 크기 (예: "1280x720", "720x1280")
        output_dir: 이미지 저장 디렉토리 (기본: static/images)
        model: 사용할 모델 (GEMINI_FLASH 또는 GEMINI_PRO)
        add_aspect_instruction: 비율 지시문 자동 추가 여부

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
    if add_aspect_instruction:
        enhanced_prompt = f"{aspect_instruction}\n\n{prompt}"
    else:
        enhanced_prompt = prompt

    model_name = "Pro" if "pro" in model.lower() else "Flash"
    print(f"[GEMINI-{model_name}] 이미지 생성 시작 - 크기: {size}")

    # API 호출
    result = _call_openrouter_api(enhanced_prompt, api_key, model)
    if not result.get("ok"):
        return result

    # 이미지 추출
    base64_data = _extract_image_from_response(result["data"])
    if not base64_data:
        # 디버그: API 응답 구조 로깅
        choices = result["data"].get("choices", [])
        if choices:
            message = choices[0].get("message", {})
            content = message.get("content", [])
            print(f"[GEMINI][DEBUG] 이미지 추출 실패 - content 타입: {type(content)}, 길이: {len(content) if isinstance(content, list) else 'N/A'}")
            if isinstance(content, list) and content:
                print(f"[GEMINI][DEBUG] 첫 번째 content: {str(content[0])[:200]}")
            elif isinstance(content, str):
                print(f"[GEMINI][DEBUG] content (text): {content[:200]}")
        else:
            print(f"[GEMINI][DEBUG] choices 없음 - 응답: {str(result['data'])[:300]}")
        return {"ok": False, "error": "Gemini에서 이미지를 생성하지 못했습니다. (응답에 이미지 없음)"}

    # 이미지 처리 및 저장
    if output_dir is None:
        output_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'static', 'images')

    prefix = "thumbnail" if model == GEMINI_PRO else "gemini"
    image_url = _process_and_save_image(
        base64_data, target_width, target_height, output_dir, prefix
    )

    if not image_url:
        # 저장 실패 시 base64 URL 반환
        image_url = f"data:image/png;base64,{base64_data}"

    # 모델별 비용
    cost = MODEL_COSTS.get(model, 0.039)
    print(f"[GEMINI-{model_name}] 완료 - 비용: ${cost}")

    return {
        "ok": True,
        "image_url": image_url,
        "cost": cost,
        "provider": "gemini",
        "model": model_name.lower()
    }


def generate_image_base64(
    prompt: str,
    model: str = GEMINI_PRO
) -> Dict[str, Any]:
    """
    Gemini로 이미지 생성 후 base64 데이터만 반환 (저장 없음)

    Args:
        prompt: 이미지 생성 프롬프트
        model: 사용할 모델 (GEMINI_FLASH 또는 GEMINI_PRO)

    Returns:
        {"ok": True, "base64": str, "cost": float} 또는
        {"ok": False, "error": str}
    """
    api_key = os.getenv("OPENROUTER_API_KEY", "")
    if not api_key:
        return {"ok": False, "error": "OPENROUTER_API_KEY 환경변수가 설정되지 않았습니다."}

    if not prompt:
        return {"ok": False, "error": "프롬프트가 없습니다."}

    model_name = "Pro" if "pro" in model.lower() else "Flash"
    print(f"[GEMINI-{model_name}] base64 이미지 생성 시작")

    result = _call_openrouter_api(prompt, api_key, model)
    if not result.get("ok"):
        return result

    base64_data = _extract_image_from_response(result["data"])
    if not base64_data:
        return {"ok": False, "error": "Gemini에서 이미지를 생성하지 못했습니다."}

    cost = MODEL_COSTS.get(model, 0.05)
    print(f"[GEMINI-{model_name}] 완료 - 비용: ${cost}")

    return {
        "ok": True,
        "base64": base64_data,
        "cost": cost,
        "provider": "gemini",
        "model": model_name.lower()
    }


def generate_thumbnail_image(
    prompt: str,
    text_overlay: Optional[Dict[str, str]] = None,
    output_dir: Optional[str] = None,
    use_pro_model: bool = True
) -> Dict[str, Any]:
    """
    썸네일 이미지 생성 (16:9 고정, 고품질)

    Args:
        prompt: 이미지 생성 프롬프트
        text_overlay: 텍스트 오버레이 정보 {"main": str, "sub": str}
        output_dir: 이미지 저장 디렉토리
        use_pro_model: True면 GEMINI_PRO (고품질), False면 GEMINI_FLASH

    Returns:
        {"ok": True, "image_url": str, "cost": float} 또는
        {"ok": False, "error": str}
    """
    model = GEMINI_PRO if use_pro_model else GEMINI_FLASH
    return generate_image(prompt, size="1280x720", output_dir=output_dir, model=model)
