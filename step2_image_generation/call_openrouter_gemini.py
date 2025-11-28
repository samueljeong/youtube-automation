"""
OpenRouter + Gemini 2.5 for Step 2
이미지 프롬프트 생성 (GPT-4o-mini 대체)

Usage:
    export OPENROUTER_API_KEY="sk-or-..."
    python3 call_openrouter_gemini.py
"""

import os
import json
from pathlib import Path
from typing import Dict, Any, List, Optional
import requests


# OpenRouter API 설정
OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"
GEMINI_MODEL = "google/gemini-2.5-flash-preview"  # 또는 gemini-2.5-pro-preview


def load_system_prompt() -> str:
    """Load system prompt from step2_prompt.txt"""
    prompt_path = Path(__file__).parent / "step2_prompt.txt"
    if prompt_path.exists():
        return prompt_path.read_text(encoding="utf-8")
    else:
        # 기본 프롬프트
        return """You are an image prompt generator for nostalgic Korean content.
Convert Korean visual descriptions to detailed English image prompts.
Focus on 1970s-80s Korean rural/urban scenes with warm, nostalgic atmosphere.
Output JSON format: {"scenes_for_image": [{"scene_id": "...", "image_prompt": "...", "style": "..."}]}"""


def call_gemini_via_openrouter(
    messages: List[Dict[str, str]],
    model: str = GEMINI_MODEL,
    max_tokens: int = 4096,
    temperature: float = 0.7
) -> Optional[str]:
    """
    OpenRouter를 통해 Gemini 2.5 호출

    Args:
        messages: 대화 메시지 리스트
        model: 사용할 모델 ID
        max_tokens: 최대 토큰 수
        temperature: 생성 온도

    Returns:
        응답 텍스트 또는 None
    """
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        print("[ERROR] OPENROUTER_API_KEY not set")
        return None

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://drama-pipeline.local",  # 선택사항
        "X-Title": "Drama Content Pipeline"  # 선택사항
    }

    payload = {
        "model": model,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature
    }

    try:
        print(f"[OPENROUTER] Calling {model}...")
        response = requests.post(
            OPENROUTER_API_URL,
            headers=headers,
            json=payload,
            timeout=60
        )
        response.raise_for_status()

        result = response.json()
        content = result.get("choices", [{}])[0].get("message", {}).get("content", "")
        print(f"[OPENROUTER] Response received ({len(content)} chars)")
        return content

    except requests.exceptions.Timeout:
        print("[ERROR] OpenRouter API timeout")
        return None
    except requests.exceptions.RequestException as e:
        print(f"[ERROR] OpenRouter API error: {e}")
        return None


def generate_image_prompts_gemini(step1_output: Dict[str, Any]) -> Dict[str, Any]:
    """
    OpenRouter + Gemini 2.5를 사용하여 이미지 프롬프트 생성

    Args:
        step1_output: Step1 스크립트 생성 결과

    Returns:
        Step2 출력 (scenes_for_image 포함)
    """
    api_key = os.getenv("OPENROUTER_API_KEY")
    scenes = step1_output.get("scenes", [])

    print(f"[Step2-Gemini] Processing {len(scenes)} scenes for image prompts")

    if not api_key:
        print("[WARNING] OPENROUTER_API_KEY not set. Using rule-based conversion.")
        return _generate_rule_based_prompts(step1_output)

    system_prompt = load_system_prompt()

    input_for_gemini = {
        "scenes": [
            {
                "id": scene.get("id"),
                "visual_description": scene.get("visual_description", ""),
                "emotion": scene.get("emotion", "nostalgic")
            }
            for scene in scenes
        ]
    }

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": json.dumps(input_for_gemini, ensure_ascii=False)}
    ]

    response_text = call_gemini_via_openrouter(messages)

    if not response_text:
        print("[FALLBACK] Using rule-based conversion.")
        return _generate_rule_based_prompts(step1_output)

    try:
        result = _parse_json_response(response_text)
        return _ensure_pipeline_compatibility(result, step1_output)
    except Exception as e:
        print(f"[ERROR] Failed to parse Gemini response: {e}")
        return _generate_rule_based_prompts(step1_output)


def _parse_json_response(response_text: str) -> Dict[str, Any]:
    """Extract and parse JSON from response text"""
    text = response_text.strip()

    # Remove markdown code blocks
    if text.startswith("```json"):
        text = text[7:]
    elif text.startswith("```"):
        text = text[3:]

    if text.endswith("```"):
        text = text[:-3]

    text = text.strip()

    return json.loads(text)


def _ensure_pipeline_compatibility(result: Dict[str, Any], step1_output: Dict[str, Any]) -> Dict[str, Any]:
    """Ensure pipeline compatibility by adding required fields"""
    result["step"] = "step2_images"
    result["category"] = step1_output.get("category", "category1")
    result["category_key"] = step1_output.get("category_key", "nostalgia_story")
    result["title"] = step1_output.get("titles", {}).get("main_title", "Untitled")

    if "scenes_for_image" not in result:
        result["scenes_for_image"] = []

    for scene in result.get("scenes_for_image", []):
        if "scene_id" not in scene and "id" in scene:
            scene["scene_id"] = scene.pop("id")
        if "image_prompt" not in scene:
            scene["image_prompt"] = ""
        if "style" not in scene:
            scene["style"] = "warm retro color palette"
        if "is_key_scene" not in scene:
            scene["is_key_scene"] = True

    result["max_cuts"] = len(result.get("scenes_for_image", []))
    return result


def _generate_rule_based_prompts(step1_output: Dict[str, Any]) -> Dict[str, Any]:
    """Generate image prompts using rule-based conversion (fallback)"""
    scenes = step1_output.get("scenes", [])
    titles = step1_output.get("titles", {})

    scenes_for_image: List[Dict[str, Any]] = []

    for scene in scenes[:4]:
        scene_id = scene.get("id", f"scene{len(scenes_for_image) + 1}")
        visual_desc = scene.get("visual_description", "")
        emotion = scene.get("emotion", "nostalgic")

        image_prompt = _convert_to_english_prompt(visual_desc, emotion)
        style = _get_style_tag(emotion)
        seed_hint = f"{scene_id} {emotion} korea 1970s warm tone"

        scenes_for_image.append({
            "scene_id": scene_id,
            "image_prompt": image_prompt,
            "style": style,
            "seed_hint": seed_hint,
            "is_key_scene": True
        })

    return {
        "step": "step2_images",
        "category": step1_output.get("category", "category1"),
        "category_key": step1_output.get("category_key", "nostalgia_story"),
        "title": titles.get("main_title", "Untitled"),
        "scenes_for_image": scenes_for_image,
        "max_cuts": len(scenes_for_image)
    }


def _convert_to_english_prompt(visual_desc: str, emotion: str) -> str:
    """Convert Korean visual_description to English prompt (rule-based)"""
    base_elements = [
        "1970s Korean village scene",
        "warm nostalgic atmosphere",
        "soft film grain",
        "cinematic wide shot"
    ]

    lighting_map = {
        "nostalgia": "soft warm lighting, sunset glow",
        "warmth": "golden-hour light, diffused soft shadows",
        "bittersweet": "cool ambient light mixed with warm highlights",
        "comfort": "warm indoor lighting, gentle shadows"
    }

    lighting = lighting_map.get(emotion, "soft warm lighting")

    keyword_map = {
        "시골": "rural Korean village",
        "마을": "small Korean town",
        "골목": "narrow Korean alley",
        "버스": "old Korean bus",
        "학교": "old Korean school",
        "시장": "traditional Korean market",
        "구멍가게": "old Korean general store",
        "연탄": "coal briquettes stacked near doorsteps",
        "겨울": "winter scene with visible breath in cold air",
        "새벽": "early dawn, quiet streets",
        "저녁": "evening twilight",
        "1970": "1970s Korea",
        "1980": "1980s Korea"
    }

    matched_elements = []
    for kor, eng in keyword_map.items():
        if kor in visual_desc:
            matched_elements.append(eng)

    if matched_elements:
        scene_desc = ", ".join(matched_elements[:3])
    else:
        scene_desc = "nostalgic 1970s Korean neighborhood"

    prompt = f"{scene_desc}, {lighting}, {', '.join(base_elements)}"
    return prompt


def _get_style_tag(emotion: str) -> str:
    """Get style tag based on emotion"""
    style_map = {
        "nostalgia": "soft nostalgic illustration",
        "warmth": "warm retro color palette",
        "bittersweet": "film still aesthetic",
        "comfort": "vintage Korean realism"
    }
    return style_map.get(emotion, "warm retro color palette")


if __name__ == "__main__":
    mock_step1 = {
        "category": "category1",
        "category_key": "nostalgia_story",
        "titles": {"main_title": "그 시절, 우리 마을의 작은 구멍가게"},
        "scenes": [
            {
                "id": "scene1",
                "visual_description": "1970년대 시골 마을의 작은 구멍가게, 나무 진열대에 과자와 음료가 진열되어 있다",
                "emotion": "nostalgia"
            },
            {
                "id": "scene2",
                "visual_description": "겨울 저녁, 연탄 냄새가 나는 골목길",
                "emotion": "warmth"
            }
        ]
    }

    result = generate_image_prompts_gemini(mock_step1)
    print(json.dumps(result, ensure_ascii=False, indent=2))
