# step4_thumbnail_generation/run_step4.py

from typing import Dict, Any

from .build_thumbnail_prompt import generate_thumbnail_prompt
from .generate_multiple_thumbnails import generate_multiple_thumbnails
from .select_best_thumbnail import select_best_thumbnail


def run_step4(step1_output: Dict[str, Any], count: int = 3) -> Dict[str, Any]:
    """
    Step4: 썸네일 프롬프트 생성 + 썸네일 N종 생성 + 자동 선택

    :param step1_output: Step1 결과(JSON dict)
    :param count: 생성할 썸네일 개수 (기본 3개)
    :return: {
        "thumbnail_prompt": str,
        "thumbnail_text": str,
        "candidates": [{ "index": int, "url": str }, ...],
        "selected": { "index": int, "url": str },
    }
    """
    titles = step1_output.get("titles", {})
    title = titles.get("main_title", "Untitled")
    category = step1_output.get("category", "category1")

    print(f"\n[Step4] Starting thumbnail pipeline for: {title}")
    print(f"[Step4] Will generate {count} candidates")

    # 1) 썸네일 프롬프트 및 텍스트 생성
    print("[Step4] Generating thumbnail prompt...")
    prompt_data = generate_thumbnail_prompt(step1_output)

    thumbnail_prompt = prompt_data.get("thumbnail_prompt", "")
    thumbnail_text = prompt_data.get("thumbnail_text", "")

    print(f"[Step4] Thumbnail text: {thumbnail_text}")

    # 파일명 접두사 생성 (특수문자 제거)
    safe_title = "".join(c if c.isalnum() or c in "_ " else "_" for c in title)
    safe_title = safe_title.replace(" ", "_")[:30]

    # 2) 썸네일 N종 생성
    candidates = generate_multiple_thumbnails(
        thumbnail_prompt=thumbnail_prompt,
        count=count,
        output_dir="output/thumbnails",
        filename_prefix=safe_title
    )

    # 3) 자동 선택
    selected = select_best_thumbnail(candidates)

    # 4) 최종 결과 반환
    result: Dict[str, Any] = {
        "step": "step4_thumbnail",
        "title": title,
        "category": category,
        "thumbnail_prompt": thumbnail_prompt,
        "thumbnail_text": thumbnail_text,
        "thumbnail_style": prompt_data.get("thumbnail_style", "vintage Korean realism"),
        "color_mood": prompt_data.get("color_mood", "warm sepia"),
        "candidates": candidates,
        "selected": selected,
        "candidate_count": len(candidates)
    }

    print(f"[Step4] Pipeline completed - {len(candidates)} candidates, selected index: {selected.get('index')}")
    return result


if __name__ == "__main__":
    import json

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

    result = run_step4(mock_step1, count=3)
    print(json.dumps(result, ensure_ascii=False, indent=2))
