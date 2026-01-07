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
IMAGEN_MODEL = "imagen-3.0-generate-001"


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


def _generate_image_via_gemini(
    prompt: str,
    output_path: str = None,
    style: str = "realistic",
    aspect_ratio: str = "16:9",
) -> Dict[str, Any]:
    """로컬 Gemini API로 이미지 생성"""
    api_key = os.environ.get("GOOGLE_API_KEY", "")
    if not api_key:
        return {"ok": False, "error": "GOOGLE_API_KEY 없음"}

    url = f"https://generativelanguage.googleapis.com/v1beta/models/{IMAGEN_MODEL}:predict?key={api_key}"

    # 스타일 힌트 추가
    style_hints = {
        "realistic": "photorealistic, highly detailed, 8k resolution",
        "illustration": "digital illustration, artistic, detailed",
        "cinematic": "cinematic lighting, dramatic atmosphere, film quality",
        "historical": "historical illustration, traditional art style, detailed",
    }
    style_suffix = style_hints.get(style, style_hints["realistic"])
    enhanced_prompt = f"{prompt}, {style_suffix}"

    # Imagen 3.0 predict API 형식
    payload = {
        "instances": [{"prompt": enhanced_prompt}],
        "parameters": {
            "sampleCount": 1,
            "aspectRatio": aspect_ratio,
        }
    }

    try:
        response = requests.post(url, json=payload, timeout=120)

        if response.status_code == 200:
            result = response.json()
            # Imagen 3.0 응답 형식
            predictions = result.get("predictions", [])
            if predictions:
                image_b64 = predictions[0].get("bytesBase64Encoded", "")
                if not image_b64:
                    return {"ok": False, "error": "이미지 데이터 없음 (빈 응답)"}
                image_data = base64.b64decode(image_b64)

                if output_path:
                    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
                    with open(output_path, "wb") as f:
                        f.write(image_data)
                    print(f"[HISTORY-IMAGE] 저장: {output_path}")
                    return {"ok": True, "image_path": output_path, "image_data": image_data}
                else:
                    return {"ok": True, "image_data": image_data}
            else:
                return {"ok": False, "error": "이미지 생성 결과 없음"}
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
    use_render: bool = True,  # 기본: Render API 사용
) -> Dict[str, Any]:
    """
    이미지 생성 (Render API 우선, 실패 시 Gemini 직접 호출)

    Args:
        prompt: 이미지 프롬프트 (영문 권장)
        output_path: 저장 경로 (없으면 base64 반환)
        style: 스타일 힌트 (realistic, illustration, cinematic, historical)
        aspect_ratio: 비율 (16:9, 1:1, 9:16)
        use_render: Render API 사용 여부 (기본: True)

    Returns:
        {"ok": True, "image_path": "...", "image_data": bytes}
    """
    # 1. Render API 시도 (기본)
    if use_render:
        result = _generate_image_via_render(prompt, output_path, style, aspect_ratio)
        if result.get("ok"):
            return result
        print(f"[HISTORY-IMAGE] Render API 실패, Gemini 직접 호출 시도...")

    # 2. Gemini API 직접 호출 (fallback)
    result = _generate_image_via_gemini(prompt, output_path, style, aspect_ratio)
    if result.get("ok"):
        return result
    else:
        print(f"[HISTORY-IMAGE] Gemini 직접 호출 실패: {result.get('error')}")

    # 3. 둘 다 실패
    return {"ok": False, "error": "이미지 생성 실패 (Render/Gemini 모두 실패)"}


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
