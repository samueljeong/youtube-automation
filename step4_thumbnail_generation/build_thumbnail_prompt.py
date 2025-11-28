"""
Build Thumbnail Prompt for Step 4
GPT-4o-mini를 사용하여 썸네일 프롬프트 생성
"""

import os
import json
from pathlib import Path
from typing import Dict, Any


def load_system_prompt() -> str:
    """Load system prompt from thumbnail_prompt_rules.txt"""
    prompt_path = Path(__file__).parent / "thumbnail_prompt_rules.txt"
    if prompt_path.exists():
        return prompt_path.read_text(encoding="utf-8")
    else:
        raise FileNotFoundError(f"System prompt not found: {prompt_path}")


def generate_thumbnail_prompt(step1_output: Dict[str, Any]) -> Dict[str, Any]:
    """
    GPT-4o-mini를 사용하여 썸네일 프롬프트 생성

    Args:
        step1_output: Step1 대본 생성 결과

    Returns:
        썸네일 프롬프트 데이터 (thumbnail_prompt, thumbnail_text 등)
    """
    api_key = os.getenv("OPENAI_API_KEY")
    titles = step1_output.get("titles", {})
    title = titles.get("main_title", "Untitled")
    category = step1_output.get("category", "category1")
    scenes = step1_output.get("scenes", [])

    print(f"[Step4-Thumbnail] Generating thumbnail prompt for: {title}")

    if not api_key:
        print("[WARNING] OPENAI_API_KEY not set. Using rule-based generation.")
        return _generate_rule_based_prompt(step1_output)

    try:
        from openai import OpenAI

        client = OpenAI(api_key=api_key)
        system_prompt = load_system_prompt()

        print("[GPT-MINI] Calling GPT-4o-mini for thumbnail prompt...")

        input_for_gpt = {
            "title": title,
            "category": category,
            "scenes": [
                {
                    "id": scene.get("id"),
                    "visual_description": scene.get("visual_description", ""),
                    "emotion": scene.get("emotion", "nostalgic")
                }
                for scene in scenes[:2]  # 처음 2개 씬만 참고
            ]
        }

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": json.dumps(input_for_gpt, ensure_ascii=False)}
            ],
            max_tokens=1024,
            temperature=0.7
        )

        response_text = response.choices[0].message.content
        print(f"[GPT-MINI] Response received ({len(response_text)} chars)")

        result = _parse_json_response(response_text)
        return _ensure_output_structure(result, step1_output)

    except ImportError:
        print("[ERROR] openai package not installed. Using rule-based generation.")
        return _generate_rule_based_prompt(step1_output)
    except Exception as e:
        print(f"[ERROR] API call failed: {e}")
        print("[FALLBACK] Using rule-based generation.")
        return _generate_rule_based_prompt(step1_output)


def _parse_json_response(response_text: str) -> Dict[str, Any]:
    """Extract and parse JSON from response text"""
    text = response_text.strip()

    if text.startswith("```json"):
        text = text[7:]
    elif text.startswith("```"):
        text = text[3:]

    if text.endswith("```"):
        text = text[:-3]

    text = text.strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        print(f"[ERROR] JSON parsing failed: {e}")
        print(f"[DEBUG] Response text: {text[:500]}...")
        raise


def _ensure_output_structure(result: Dict[str, Any], step1_output: Dict[str, Any]) -> Dict[str, Any]:
    """Ensure output has all required fields"""
    titles = step1_output.get("titles", {})
    title = titles.get("main_title", "Untitled")

    if "thumbnail_prompt" not in result:
        result["thumbnail_prompt"] = _generate_default_prompt(title)

    if "thumbnail_text" not in result:
        result["thumbnail_text"] = _extract_short_text(title)

    if "thumbnail_style" not in result:
        result["thumbnail_style"] = "vintage Korean realism"

    if "color_mood" not in result:
        result["color_mood"] = "warm sepia with golden highlights"

    result["title"] = title
    result["category"] = step1_output.get("category", "category1")

    return result


def _generate_rule_based_prompt(step1_output: Dict[str, Any]) -> Dict[str, Any]:
    """Generate thumbnail prompt using rule-based approach (fallback)"""
    titles = step1_output.get("titles", {})
    title = titles.get("main_title", "Untitled")
    category = step1_output.get("category", "category1")
    scenes = step1_output.get("scenes", [])

    # Extract keywords from title and scenes
    visual_hints = []
    for scene in scenes[:2]:
        desc = scene.get("visual_description", "")
        if desc:
            visual_hints.append(desc)

    # Generate prompt based on category
    if category == "category1":  # 향수 콘텐츠
        base_prompt = "A nostalgic 1970s Korean village scene"
        style = "vintage Korean realism"
        mood = "warm sepia with golden highlights"
    else:  # category2 - 명언 라디오
        base_prompt = "A peaceful Korean study room with old books"
        style = "calm contemplative"
        mood = "soft muted tones with warm accents"

    # Build full prompt
    prompt_parts = [
        base_prompt,
        "soft warm lighting streaming through",
        "gentle film grain texture",
        "nostalgic Kodak Portra color palette",
        "wide shot with shallow depth of field",
        "vintage Korean atmosphere",
        "no text or logos"
    ]

    # Add visual hints from scenes
    keyword_map = {
        "구멍가게": "small general store with glass candy jars",
        "골목": "narrow traditional alley",
        "시골": "rural Korean countryside",
        "버스": "old Korean bus stop",
        "연탄": "coal briquettes stacked by doorstep",
        "겨울": "winter scene with frost",
        "학교": "old Korean school building"
    }

    for hint in visual_hints:
        for kor, eng in keyword_map.items():
            if kor in hint:
                prompt_parts.insert(1, eng)
                break

    thumbnail_prompt = ", ".join(prompt_parts)

    # Generate short text
    thumbnail_text = _extract_short_text(title)

    return {
        "thumbnail_prompt": thumbnail_prompt,
        "thumbnail_text": thumbnail_text,
        "thumbnail_style": style,
        "color_mood": mood,
        "title": title,
        "category": category
    }


def _generate_default_prompt(title: str) -> str:
    """Generate default thumbnail prompt"""
    return f"A nostalgic 1970s Korean scene, warm sunlight, soft film grain, vintage Kodak color palette, wide shot, gentle atmosphere, no text"


def _extract_short_text(title: str) -> str:
    """Extract short text (7-12 chars) from title"""
    # Remove common suffixes
    text = title.replace("이야기", "").replace("의 추억", "").strip()

    # Try to extract meaningful part
    if "," in text:
        parts = text.split(",")
        text = parts[0].strip()

    # Truncate if too long
    if len(text) > 12:
        text = text[:12]

    # Ensure minimum length
    if len(text) < 7:
        text = title[:10] if len(title) >= 10 else title

    return text


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

    result = generate_thumbnail_prompt(mock_step1)
    print(json.dumps(result, ensure_ascii=False, indent=2))
