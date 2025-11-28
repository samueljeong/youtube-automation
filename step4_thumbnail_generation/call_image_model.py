"""
Call Image Model for Step 4
DALL-E 3를 사용하여 썸네일 이미지 생성
"""

import os
import json
import base64
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime


def generate_thumbnail_image(
    prompt: str,
    output_dir: str = "output/thumbnails",
    filename_prefix: str = "thumbnail"
) -> Dict[str, Any]:
    """
    DALL-E 3를 사용하여 썸네일 이미지 생성

    Args:
        prompt: 이미지 생성용 영어 프롬프트
        output_dir: 이미지 저장 디렉토리
        filename_prefix: 파일명 접두사

    Returns:
        생성 결과 (image_url, local_path, status 등)
    """
    api_key = os.getenv("OPENAI_API_KEY")

    print(f"[Step4-Image] Generating thumbnail image...")
    print(f"[Step4-Image] Prompt: {prompt[:100]}...")

    if not api_key:
        print("[WARNING] OPENAI_API_KEY not set. Returning mock result.")
        return _generate_mock_result(prompt, output_dir, filename_prefix)

    try:
        from openai import OpenAI

        client = OpenAI(api_key=api_key)

        print("[DALL-E] Calling DALL-E 3 for thumbnail generation...")

        # DALL-E 3 호출 - 1792x1024 (YouTube 썸네일 비율에 가까움)
        response = client.images.generate(
            model="dall-e-3",
            prompt=prompt,
            size="1792x1024",
            quality="standard",
            n=1
        )

        image_url = response.data[0].url
        revised_prompt = response.data[0].revised_prompt

        print(f"[DALL-E] Image generated successfully")
        print(f"[DALL-E] Revised prompt: {revised_prompt[:100]}...")

        # 이미지 다운로드 및 저장
        local_path = _download_and_save_image(
            image_url, output_dir, filename_prefix
        )

        return {
            "status": "success",
            "image_url": image_url,
            "local_path": local_path,
            "revised_prompt": revised_prompt,
            "model": "dall-e-3",
            "size": "1792x1024"
        }

    except ImportError:
        print("[ERROR] openai package not installed. Returning mock result.")
        return _generate_mock_result(prompt, output_dir, filename_prefix)
    except Exception as e:
        print(f"[ERROR] Image generation failed: {e}")
        return {
            "status": "error",
            "error": str(e),
            "image_url": None,
            "local_path": None
        }


def _download_and_save_image(
    image_url: str,
    output_dir: str,
    filename_prefix: str
) -> Optional[str]:
    """Download image from URL and save locally"""
    try:
        import urllib.request

        # Create output directory
        Path(output_dir).mkdir(parents=True, exist_ok=True)

        # Generate filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{filename_prefix}_{timestamp}.png"
        local_path = os.path.join(output_dir, filename)

        # Download image
        urllib.request.urlretrieve(image_url, local_path)
        print(f"[DALL-E] Image saved to: {local_path}")

        return local_path

    except Exception as e:
        print(f"[WARNING] Failed to download image: {e}")
        return None


def _generate_mock_result(
    prompt: str,
    output_dir: str,
    filename_prefix: str
) -> Dict[str, Any]:
    """Generate mock result when API is not available"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    mock_path = f"{output_dir}/{filename_prefix}_{timestamp}_mock.png"

    return {
        "status": "mock",
        "image_url": None,
        "local_path": mock_path,
        "revised_prompt": prompt,
        "model": "mock",
        "size": "1792x1024",
        "message": "OPENAI_API_KEY not set. Image generation skipped."
    }


def run_thumbnail_generation(step1_output: Dict[str, Any]) -> Dict[str, Any]:
    """
    전체 썸네일 생성 프로세스 실행

    Args:
        step1_output: Step1 대본 생성 결과

    Returns:
        썸네일 생성 결과 (프롬프트 + 이미지 정보)
    """
    from .build_thumbnail_prompt import generate_thumbnail_prompt

    titles = step1_output.get("titles", {})
    title = titles.get("main_title", "Untitled")

    print(f"\n[Step4-Thumbnail] Starting thumbnail generation for: {title}")

    # 1. 프롬프트 생성
    prompt_data = generate_thumbnail_prompt(step1_output)

    # 2. 이미지 생성
    # 파일명을 제목에서 추출 (특수문자 제거)
    safe_title = "".join(c if c.isalnum() or c in "_ " else "_" for c in title)
    safe_title = safe_title.replace(" ", "_")[:30]

    image_result = generate_thumbnail_image(
        prompt=prompt_data["thumbnail_prompt"],
        output_dir="output/thumbnails",
        filename_prefix=safe_title
    )

    # 3. 결과 통합
    result = {
        "step": "step4_thumbnail",
        "title": title,
        "category": step1_output.get("category", "category1"),
        "thumbnail_prompt": prompt_data["thumbnail_prompt"],
        "thumbnail_text": prompt_data["thumbnail_text"],
        "thumbnail_style": prompt_data.get("thumbnail_style", "vintage Korean realism"),
        "color_mood": prompt_data.get("color_mood", "warm sepia"),
        "image_generation": image_result
    }

    print(f"[Step4-Thumbnail] Thumbnail generation completed")
    return result


if __name__ == "__main__":
    mock_step1 = {
        "category": "category1",
        "titles": {"main_title": "그 시절, 우리 마을의 작은 구멍가게"},
        "scenes": [
            {
                "id": "scene1",
                "visual_description": "1970년대 시골 마을의 작은 구멍가게 앞 풍경",
                "emotion": "nostalgia"
            }
        ]
    }

    result = run_thumbnail_generation(mock_step1)
    print(json.dumps(result, ensure_ascii=False, indent=2))
