"""
Actual Image Generation for Step 2
DALL-E 3를 사용하여 실제 이미지 파일 생성

Usage:
    export OPENAI_API_KEY="sk-..."
    python3 generate_images.py
"""

import os
import json
import requests
import base64
from pathlib import Path
from typing import Dict, Any, List, Optional
from urllib.request import urlopen
import ssl


# SSL 인증서 문제 해결 (macOS)
ssl._create_default_https_context = ssl._create_unverified_context


def generate_image_dalle(
    prompt: str,
    output_path: str,
    size: str = "1024x1024",
    quality: str = "standard"
) -> Optional[str]:
    """
    DALL-E 3로 이미지 생성

    Args:
        prompt: 이미지 생성 프롬프트
        output_path: 저장할 파일 경로
        size: 이미지 크기 (1024x1024, 1024x1792, 1792x1024)
        quality: 품질 (standard, hd)

    Returns:
        생성된 파일 경로 또는 None
    """
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("[ERROR] OPENAI_API_KEY not set")
        return None

    try:
        from openai import OpenAI
        client = OpenAI(api_key=api_key)

        print(f"[DALL-E] Generating image...")
        print(f"[DALL-E] Prompt: {prompt[:100]}...")

        response = client.images.generate(
            model="dall-e-3",
            prompt=prompt,
            size=size,
            quality=quality,
            n=1
        )

        image_url = response.data[0].url
        revised_prompt = response.data[0].revised_prompt
        print(f"[DALL-E] Image generated successfully")
        print(f"[DALL-E] Revised prompt: {revised_prompt[:100]}...")

        # 이미지 다운로드
        os.makedirs(os.path.dirname(output_path), exist_ok=True)

        try:
            image_data = urlopen(image_url).read()
            with open(output_path, "wb") as f:
                f.write(image_data)
            print(f"[DALL-E] Saved to: {output_path}")
            return output_path
        except Exception as e:
            print(f"[WARNING] Failed to download image: {e}")
            # URL만 반환
            return image_url

    except ImportError:
        print("[ERROR] openai package not installed")
        return None
    except Exception as e:
        print(f"[ERROR] Image generation failed: {e}")
        return None


def generate_all_scene_images(
    step2_output: Dict[str, Any],
    output_dir: str = "outputs/images"
) -> Dict[str, Any]:
    """
    Step2 출력의 모든 씬에 대해 이미지 생성

    Args:
        step2_output: Step2 출력 (scenes_for_image 포함)
        output_dir: 이미지 저장 디렉토리

    Returns:
        이미지 경로가 추가된 Step2 출력
    """
    scenes = step2_output.get("scenes_for_image", [])
    print(f"\n=== [Image Generation] Generating {len(scenes)} images ===")

    os.makedirs(output_dir, exist_ok=True)

    generated_images = []

    for i, scene in enumerate(scenes):
        scene_id = scene.get("scene_id", f"scene{i+1}")
        prompt = scene.get("image_prompt", "")
        style = scene.get("style", "")

        if not prompt:
            print(f"[WARNING] No prompt for {scene_id}, skipping")
            continue

        # 스타일을 프롬프트에 추가
        full_prompt = f"{prompt}, {style}" if style else prompt

        output_path = os.path.join(output_dir, f"{scene_id}.png")

        print(f"\n[Scene {i+1}/{len(scenes)}] Generating {scene_id}...")
        result = generate_image_dalle(full_prompt, output_path)

        if result:
            scene["image_path"] = result
            generated_images.append({
                "scene_id": scene_id,
                "image_path": result,
                "prompt_used": full_prompt[:200]
            })
        else:
            scene["image_path"] = None
            print(f"[WARNING] Failed to generate image for {scene_id}")

    # 결과 업데이트
    step2_output["generated_images"] = generated_images
    step2_output["images_generated"] = len(generated_images)

    print(f"\n[Image Generation] Complete: {len(generated_images)}/{len(scenes)} images generated")

    return step2_output


def run_step2_with_images(
    step1_output: Dict[str, Any],
    use_gemini: bool = False,
    output_dir: str = "outputs/images"
) -> Dict[str, Any]:
    """
    Step2 전체 실행: 프롬프트 생성 + 이미지 생성

    Args:
        step1_output: Step1 출력
        use_gemini: Gemini 사용 여부 (False면 GPT-4o-mini 사용)
        output_dir: 이미지 저장 디렉토리

    Returns:
        이미지가 포함된 Step2 출력
    """
    # 1. 이미지 프롬프트 생성
    if use_gemini:
        from .call_openrouter_gemini import generate_image_prompts_gemini
        step2_output = generate_image_prompts_gemini(step1_output)
    else:
        from .call_gpt_mini import generate_image_prompts
        step2_output = generate_image_prompts(step1_output)

    # 2. 실제 이미지 생성
    step2_output = generate_all_scene_images(step2_output, output_dir)

    return step2_output


if __name__ == "__main__":
    # 테스트
    mock_step2_output = {
        "step": "step2_images",
        "title": "테스트",
        "scenes_for_image": [
            {
                "scene_id": "scene1",
                "image_prompt": "1970s Korean rural village, small general store with wooden shelves, warm nostalgic atmosphere, soft film grain",
                "style": "warm retro color palette"
            }
        ]
    }

    result = generate_all_scene_images(mock_step2_output, "outputs/test_images")
    print(json.dumps(result, ensure_ascii=False, indent=2))
