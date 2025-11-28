# step4_thumbnail_generation/generate_multiple_thumbnails.py

from typing import List, Dict, Any
from .call_image_model import generate_thumbnail_image


def generate_multiple_thumbnails(
    thumbnail_prompt: str,
    count: int = 3,
    output_dir: str = "output/thumbnails",
    filename_prefix: str = "thumbnail"
) -> List[Dict[str, Any]]:
    """
    동일한 프롬프트로 썸네일 이미지를 여러 장 생성한다.
    현재 구현은 같은 프롬프트로 count 번 호출하여,
    서로 다른 이미지를 생성하는 것을 전제로 한다.
    (이미지 모델은 호출마다 샘플링이 다르다고 가정)

    :param thumbnail_prompt: 이미지 생성용 영문 프롬프트
    :param count: 생성할 썸네일 개수 (기본 3개)
    :param output_dir: 이미지 저장 디렉토리
    :param filename_prefix: 파일명 접두사
    :return: [{ "index": 0, "url": "...", "local_path": "...", "status": "..." }, ...] 형태의 리스트
    """
    candidates: List[Dict[str, Any]] = []

    print(f"[Step4-Multi] Generating {count} thumbnail candidates...")

    for i in range(count):
        print(f"[Step4-Multi] Generating candidate {i + 1}/{count}...")

        result = generate_thumbnail_image(
            prompt=thumbnail_prompt,
            output_dir=output_dir,
            filename_prefix=f"{filename_prefix}_candidate_{i}"
        )

        # 결과에서 URL 추출 (실제 URL 또는 local_path)
        url = result.get("image_url") or result.get("local_path") or ""

        candidates.append({
            "index": i,
            "url": url,
            "local_path": result.get("local_path", ""),
            "status": result.get("status", "unknown"),
            "model": result.get("model", "unknown")
        })

    print(f"[Step4-Multi] Generated {len(candidates)} candidates")
    return candidates
