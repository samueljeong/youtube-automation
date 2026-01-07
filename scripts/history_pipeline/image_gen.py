"""
한국사 파이프라인 - 이미지 생성 모듈

- 로컬 Gemini API 시도 → 실패 시 Render API fallback
- 씬 배경 이미지 생성
- 썸네일 이미지 생성
"""

import os
import base64
import requests
from typing import Dict, Any, List


# Render 서버 URL
RENDER_API_URL = os.environ.get(
    "RENDER_API_URL",
    "https://drama-s2ns.onrender.com"
)

# Gemini 이미지 생성 모델
# - gemini-2.0-flash-exp: 빠르고 저렴, 기본 품질
# - imagen-3.0-generate-002: Imagen 3 (고품질, Vertex AI 필요)
# - gemini-exp-image-generation: Gemini 실험적 이미지 생성 (고품질)
GEMINI_IMAGE_MODEL = "gemini-exp-image-generation"  # Gemini 실험적 이미지 생성 (고품질)


def _generate_image_via_render(
    prompt: str,
    output_path: str = None,
    style: str = "realistic",
    aspect_ratio: str = "16:9",
) -> Dict[str, Any]:
    """Render 서버 API로 이미지 생성"""
    try:
        url = f"{RENDER_API_URL}/api/drama/generate-image"

        payload = {
            "prompt": prompt,
            "style": style,
            "ratio": aspect_ratio,
        }

        print(f"[HISTORY-IMAGE] Render API 호출 중...")
        response = requests.post(url, json=payload, timeout=180)

        if response.status_code == 200:
            result = response.json()

            if result.get("success") or result.get("ok"):
                image_url = result.get("image_url") or result.get("url")

                if image_url:
                    # 이미지 다운로드
                    img_response = requests.get(image_url, timeout=60)
                    if img_response.status_code == 200:
                        image_data = img_response.content

                        if output_path:
                            os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
                            with open(output_path, "wb") as f:
                                f.write(image_data)
                            print(f"[HISTORY-IMAGE] 저장: {output_path}")
                            return {"ok": True, "image_path": output_path, "image_data": image_data}
                        else:
                            return {"ok": True, "image_data": image_data}

            return {"ok": False, "error": f"Render API 응답 오류: {result}"}
        else:
            return {"ok": False, "error": f"Render API 오류: {response.status_code}"}

    except Exception as e:
        return {"ok": False, "error": f"Render API 예외: {str(e)}"}


def _generate_image_via_openrouter(
    prompt: str,
    output_path: str = None,
    style: str = "realistic",
    aspect_ratio: str = "16:9",
) -> Dict[str, Any]:
    """OpenRouter API로 이미지 생성 (DALL-E 3)"""
    api_key = os.environ.get("OPENROUTER_API_KEY", "")
    if not api_key:
        return {"ok": False, "error": "OPENROUTER_API_KEY 없음"}

    url = "https://openrouter.ai/api/v1/images/generations"

    # 스타일 힌트 추가
    style_hints = {
        "realistic": "photorealistic, highly detailed, 8k resolution",
        "illustration": "digital illustration, artistic, detailed",
        "cinematic": "cinematic lighting, dramatic atmosphere, film quality",
        "historical": "historical illustration, traditional art style, detailed",
    }
    style_suffix = style_hints.get(style, style_hints["realistic"])
    enhanced_prompt = f"{prompt}, {style_suffix}"

    # 비율 → 크기 변환
    size_map = {
        "16:9": "1792x1024",
        "1:1": "1024x1024",
        "9:16": "1024x1792",
    }
    size = size_map.get(aspect_ratio, "1792x1024")

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": "openai/dall-e-3",
        "prompt": enhanced_prompt,
        "n": 1,
        "size": size,
        "quality": "standard",
    }

    try:
        print(f"[HISTORY-IMAGE] OpenRouter (DALL-E 3) 호출 중...")
        response = requests.post(url, headers=headers, json=payload, timeout=120)

        if response.status_code == 200:
            result = response.json()
            data = result.get("data", [])
            if data and data[0].get("url"):
                image_url = data[0]["url"]
                # 이미지 다운로드
                img_response = requests.get(image_url, timeout=60)
                if img_response.status_code == 200:
                    image_data = img_response.content
                    if output_path:
                        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
                        with open(output_path, "wb") as f:
                            f.write(image_data)
                        print(f"[HISTORY-IMAGE] 저장: {output_path}")
                        return {"ok": True, "image_path": output_path, "image_data": image_data}
                    else:
                        return {"ok": True, "image_data": image_data}

            return {"ok": False, "error": "OpenRouter 응답에 이미지 URL 없음"}
        else:
            error_body = response.text[:300] if response.text else ""
            return {"ok": False, "error": f"OpenRouter API 오류 {response.status_code}: {error_body}"}

    except Exception as e:
        return {"ok": False, "error": f"OpenRouter API 예외: {str(e)}"}


def _generate_image_via_gemini(
    prompt: str,
    output_path: str = None,
    style: str = "realistic",
    aspect_ratio: str = "16:9",
) -> Dict[str, Any]:
    """Gemini 2.0 Flash로 이미지 생성 (실험적 기능)"""
    api_key = os.environ.get("GOOGLE_API_KEY", "")
    if not api_key:
        return {"ok": False, "error": "GOOGLE_API_KEY 없음"}

    url = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_IMAGE_MODEL}:generateContent?key={api_key}"

    # 스타일 힌트 추가
    style_hints = {
        "realistic": "photorealistic, highly detailed, 8k resolution",
        "illustration": "digital illustration, artistic, detailed",
        "cinematic": "cinematic lighting, dramatic atmosphere, film quality",
        "historical": "historical illustration, traditional art style, detailed",
    }
    style_suffix = style_hints.get(style, style_hints["realistic"])
    enhanced_prompt = f"Generate an image: {prompt}, {style_suffix}"

    # Gemini 2.0 Flash generateContent API 형식
    payload = {
        "contents": [{
            "parts": [{"text": enhanced_prompt}]
        }],
        "generationConfig": {
            "responseModalities": ["IMAGE", "TEXT"],
        }
    }

    try:
        response = requests.post(url, json=payload, timeout=120)

        if response.status_code == 200:
            result = response.json()
            candidates = result.get("candidates", [])
            if candidates:
                parts = candidates[0].get("content", {}).get("parts", [])
                for part in parts:
                    if "inlineData" in part:
                        mime_type = part["inlineData"].get("mimeType", "")
                        if "image" in mime_type:
                            image_b64 = part["inlineData"].get("data", "")
                            if image_b64:
                                image_data = base64.b64decode(image_b64)

                                if output_path:
                                    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
                                    with open(output_path, "wb") as f:
                                        f.write(image_data)
                                    print(f"[HISTORY-IMAGE] 저장: {output_path}")
                                    return {"ok": True, "image_path": output_path, "image_data": image_data}
                                else:
                                    return {"ok": True, "image_data": image_data}

            return {"ok": False, "error": "이미지 생성 결과 없음 (응답에 이미지 없음)"}
        else:
            error_body = response.text[:300] if response.text else ""
            return {"ok": False, "error": f"Gemini API 오류 {response.status_code}: {error_body}"}

    except Exception as e:
        return {"ok": False, "error": f"Gemini API 예외: {str(e)}"}


def generate_image(
    prompt: str,
    output_path: str = None,
    style: str = "realistic",
    aspect_ratio: str = "16:9",
    use_openrouter: bool = True,  # 기본: OpenRouter 사용
) -> Dict[str, Any]:
    """
    이미지 생성 (OpenRouter 우선, 실패 시 Render → Gemini fallback)

    Args:
        prompt: 이미지 프롬프트 (영문 권장)
        output_path: 저장 경로 (없으면 base64 반환)
        style: 스타일 힌트 (realistic, illustration, cinematic, historical)
        aspect_ratio: 비율 (16:9, 1:1, 9:16)
        use_openrouter: OpenRouter API 사용 여부 (기본: True)

    Returns:
        {"ok": True, "image_path": "...", "image_data": bytes}
    """
    # 1. OpenRouter API 시도 (기본)
    if use_openrouter:
        result = _generate_image_via_openrouter(prompt, output_path, style, aspect_ratio)
        if result.get("ok"):
            return result
        print(f"[HISTORY-IMAGE] OpenRouter 실패: {result.get('error')}, Render API 시도...")

    # 2. Render API 시도 (fallback)
    result = _generate_image_via_render(prompt, output_path, style, aspect_ratio)
    if result.get("ok"):
        return result
    print(f"[HISTORY-IMAGE] Render API 실패, Gemini 직접 호출 시도...")

    # 3. Gemini API 직접 호출 (최후의 fallback)
    result = _generate_image_via_gemini(prompt, output_path, style, aspect_ratio)
    if result.get("ok"):
        return result
    else:
        print(f"[HISTORY-IMAGE] Gemini 직접 호출 실패: {result.get('error')}")

    # 4. 모두 실패
    return {"ok": False, "error": "이미지 생성 실패 (OpenRouter/Render/Gemini 모두 실패)"}


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
    )


if __name__ == "__main__":
    print("history_pipeline/image_gen.py 로드 완료")
    print(f"Render API URL: {RENDER_API_URL}")
