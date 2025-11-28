"""
Thumbnail Prompt Builder for Step4
Step1 결과를 기반으로 시니어 타겟 썸네일 텍스트 및 이미지 프롬프트 자동 생성

Usage:
    from step4_thumbnail import generate_thumbnail_plan

    step1_output = {...}  # Step1 결과
    thumbnail_plan = generate_thumbnail_plan(step1_output)

    # 결과:
    # thumbnail_plan["text"]["main"] → 썸네일 대표 텍스트
    # thumbnail_plan["image_prompt"]["base_prompt_en"] → DALL-E 기본 프롬프트
    # thumbnail_plan["image_prompt"]["variants"] → 3가지 변형 프롬프트
"""

import os
import json
from pathlib import Path
from typing import Dict, Any, List, Optional

RULES_PATH = Path(__file__).parent / "thumbnail_prompt_rules_v2.txt"


def load_rules() -> str:
    """규칙 파일 로드"""
    if RULES_PATH.exists():
        return RULES_PATH.read_text(encoding="utf-8")
    else:
        raise FileNotFoundError(f"Rules file not found: {RULES_PATH}")


def build_thumbnail_prompt_input(step1_output: Dict[str, Any]) -> Dict[str, Any]:
    """
    Step1 결과에서 썸네일 생성에 필요한 핵심 정보만 추출

    Args:
        step1_output: Step1 결과 전체

    Returns:
        GPT에 전달할 정제된 입력
    """
    meta = step1_output.get("meta", {})
    titles = step1_output.get("titles", {})
    scenes = step1_output.get("scene_ideas") or step1_output.get("scenes") or []
    top_scenes = step1_output.get("top_scenes") or []
    highlight = step1_output.get("highlight_preview") or {}

    # 핵심 장면 정보 추출 (처음 5개만)
    scene_summaries = []
    for scene in scenes[:5]:
        scene_summaries.append({
            "id": scene.get("id"),
            "title": scene.get("title", ""),
            "location": scene.get("location", ""),
            "time_reference": scene.get("time_reference", ""),
            "emotional_tone": scene.get("emotional_tone", ""),
            "visual_description": scene.get("visual_description", ""),
        })

    return {
        "meta": {
            "one_line_concept": meta.get("one_line_concept", ""),
            "core_emotion": meta.get("core_emotion", "nostalgic, warm"),
            "target_length_minutes": meta.get("target_length_minutes", 10),
        },
        "titles": {
            "main_title": titles.get("main_title") or titles.get("main_title_candidate", ""),
            "alternatives": titles.get("title_alternatives", []),
        },
        "scene_ideas": scene_summaries,
        "top_scenes": top_scenes,
        "highlight_preview": {
            "narration": highlight.get("narration", ""),
            "related_scene_id": highlight.get("related_scene_id", ""),
        },
        "category": step1_output.get("category", "category1"),
    }


def generate_thumbnail_plan(step1_output: Dict[str, Any]) -> Dict[str, Any]:
    """
    GPT-4o-mini를 사용하여 Step1 결과 기반 썸네일 플랜 생성

    Args:
        step1_output: Step1 대본 생성 결과

    Returns:
        썸네일 플랜 JSON:
        {
            "thumbnail_plan": {...},
            "text": {"main": "...", "alternatives": [...]},
            "image_prompt": {"base_prompt_en": "...", "variants": [...]}
        }
    """
    api_key = os.getenv("OPENAI_API_KEY")

    print("[Thumbnail] Generating thumbnail plan from Step1 output...")

    if not api_key:
        print("[WARNING] OPENAI_API_KEY not set. Using rule-based fallback.")
        return _generate_rule_based_plan(step1_output)

    try:
        from openai import OpenAI

        client = OpenAI(api_key=api_key)
        system_prompt = load_rules()
        user_input = build_thumbnail_prompt_input(step1_output)

        print("[GPT-MINI] Calling GPT-4o-mini for thumbnail plan...")

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": json.dumps(user_input, ensure_ascii=False)}
            ],
            max_tokens=2048,
            temperature=0.7
        )

        response_text = response.choices[0].message.content
        print(f"[GPT-MINI] Response received ({len(response_text)} chars)")

        result = _parse_json_response(response_text)
        return _validate_and_fix(result, step1_output)

    except ImportError:
        print("[ERROR] openai package not installed. Using rule-based fallback.")
        return _generate_rule_based_plan(step1_output)
    except Exception as e:
        print(f"[ERROR] API call failed: {e}")
        print("[FALLBACK] Using rule-based plan.")
        return _generate_rule_based_plan(step1_output)


def _parse_json_response(response_text: str) -> Dict[str, Any]:
    """응답에서 JSON 추출 및 파싱"""
    text = response_text.strip()

    # 마크다운 코드 블록 제거
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


def _validate_and_fix(result: Dict[str, Any], step1_output: Dict[str, Any]) -> Dict[str, Any]:
    """결과 검증 및 누락 필드 보완"""
    # text 필드 검증
    if "text" not in result:
        result["text"] = {
            "main": "그때 그 시절",
            "alternatives": [],
            "rules_used": []
        }

    if "main" not in result["text"]:
        titles = step1_output.get("titles", {})
        main_title = titles.get("main_title", "")
        # 제목에서 짧은 핵심 추출
        result["text"]["main"] = _extract_short_text(main_title)

    # image_prompt 필드 검증
    if "image_prompt" not in result:
        result["image_prompt"] = _generate_fallback_prompts(step1_output)

    if "base_prompt_en" not in result["image_prompt"]:
        result["image_prompt"]["base_prompt_en"] = (
            "1970s Korean village scene, nostalgic warm atmosphere, "
            "soft film grain, cinematic wide shot, no text, no logo"
        )

    if "variants" not in result["image_prompt"]:
        result["image_prompt"]["variants"] = []

    # thumbnail_plan 필드 검증
    if "thumbnail_plan" not in result:
        meta = step1_output.get("meta", {})
        titles = step1_output.get("titles", {})
        result["thumbnail_plan"] = {
            "base_title": titles.get("main_title", ""),
            "one_line_concept": meta.get("one_line_concept", ""),
            "core_emotion": meta.get("core_emotion", "nostalgic")
        }

    return result


def _extract_short_text(title: str) -> str:
    """긴 제목에서 짧은 썸네일 텍스트 추출"""
    if not title:
        return "그때 그 시절"

    # 쉼표로 분리해서 첫 부분 사용
    if "," in title:
        title = title.split(",")[0].strip()

    # 8글자 이하면 그대로
    if len(title) <= 8:
        return title

    # 조사 기준으로 분리
    for particle in ["의", "에서", "에", "와", "과", "을", "를", "은", "는"]:
        if particle in title:
            parts = title.split(particle)
            if parts[0] and len(parts[0]) <= 8:
                return parts[0].strip()

    # 그래도 길면 앞 8글자
    return title[:8]


def _generate_fallback_prompts(step1_output: Dict[str, Any]) -> Dict[str, Any]:
    """규칙 기반 폴백 프롬프트 생성"""
    scenes = step1_output.get("scenes") or step1_output.get("scene_ideas") or []

    # 장소/시대 키워드 추출
    locations = []
    for scene in scenes[:3]:
        loc = scene.get("location", "")
        if loc:
            locations.append(loc)

    # 기본 프롬프트 구성
    base_elements = [
        "1970s Korean village",
        "nostalgic warm atmosphere",
        "soft golden hour lighting",
        "film grain texture",
        "cinematic composition",
        "16:9 aspect ratio",
        "highly detailed",
        "no text, no logo, no UI"
    ]

    base_prompt = ", ".join(base_elements)

    return {
        "base_prompt_en": base_prompt,
        "variants": [
            {
                "focus": "store_front",
                "prompt_en": f"Close view of old Korean general store, warm yellow shop lights, {base_prompt}"
            },
            {
                "focus": "alley_mood",
                "prompt_en": f"Narrow alley in 1970s Korean village at dusk, faint coal briquette smoke, {base_prompt}"
            },
            {
                "focus": "wide_scene",
                "prompt_en": f"Wide shot of small Korean rural village, winter evening, {base_prompt}"
            }
        ],
        "style_tags": ["nostalgic", "1970s Korea", "warm light", "no text"]
    }


def _generate_rule_based_plan(step1_output: Dict[str, Any]) -> Dict[str, Any]:
    """API 없이 규칙 기반으로 썸네일 플랜 생성"""
    meta = step1_output.get("meta", {})
    titles = step1_output.get("titles", {})
    main_title = titles.get("main_title") or titles.get("main_title_candidate", "")

    # 텍스트 생성
    main_text = _extract_short_text(main_title)

    # 대안 텍스트 생성
    alternatives = []
    one_line = meta.get("one_line_concept", "")
    if one_line:
        # one_line_concept에서 핵심 단어 추출
        keywords = ["시절", "골목", "마을", "동네", "겨울", "추억"]
        for kw in keywords:
            if kw in one_line:
                alternatives.append(f"그때 그 {kw}")
                break

    if not alternatives:
        alternatives = ["그때 그 시절", "옛날 이야기", "추억의 골목"]

    return {
        "thumbnail_plan": {
            "base_title": main_title,
            "one_line_concept": meta.get("one_line_concept", ""),
            "core_emotion": meta.get("core_emotion", "nostalgic")
        },
        "text": {
            "main": main_text,
            "alternatives": alternatives[:4],
            "rules_used": [
                "4~8글자 한국어",
                "시니어 친화적 단어",
                "rule-based fallback"
            ]
        },
        "image_prompt": _generate_fallback_prompts(step1_output)
    }


def get_thumbnail_prompts_for_generation(
    thumbnail_plan: Dict[str, Any],
    num_variants: int = 3
) -> List[str]:
    """
    썸네일 플랜에서 이미지 생성용 프롬프트 목록 추출

    Args:
        thumbnail_plan: generate_thumbnail_plan() 결과
        num_variants: 반환할 프롬프트 수

    Returns:
        프롬프트 문자열 리스트
    """
    prompts = []
    image_prompt = thumbnail_plan.get("image_prompt", {})

    # 베이스 프롬프트 추가
    base = image_prompt.get("base_prompt_en", "")
    if base:
        prompts.append(base)

    # 변형 프롬프트 추가
    variants = image_prompt.get("variants", [])
    for variant in variants[:num_variants - 1]:
        prompt = variant.get("prompt_en", "")
        if prompt:
            prompts.append(prompt)

    return prompts[:num_variants]


if __name__ == "__main__":
    # 테스트용 Step1 샘플
    mock_step1 = {
        "category": "category1",
        "meta": {
            "one_line_concept": "연탄 냄새 나던 골목 끝, 작은 구멍가게에 대한 추억",
            "core_emotion": "nostalgia_warm",
            "target_length_minutes": 10
        },
        "titles": {
            "main_title": "그 시절, 우리 마을의 구멍가게"
        },
        "scenes": [
            {
                "id": "scene1",
                "title": "겨울밤 골목",
                "location": "1970년대 서울 변두리 골목",
                "emotional_tone": "nostalgic, warm"
            }
        ],
        "highlight_preview": {
            "narration": "그때 그 구멍가게 할머니의 따뜻한 손길이 생각납니다."
        }
    }

    # 규칙 기반 테스트 (API 없이)
    print("=== Rule-based Test ===")
    result = _generate_rule_based_plan(mock_step1)
    print(json.dumps(result, ensure_ascii=False, indent=2))

    # API 테스트 (OPENAI_API_KEY 있을 때)
    if os.getenv("OPENAI_API_KEY"):
        print("\n=== API Test ===")
        result = generate_thumbnail_plan(mock_step1)
        print(json.dumps(result, ensure_ascii=False, indent=2))
