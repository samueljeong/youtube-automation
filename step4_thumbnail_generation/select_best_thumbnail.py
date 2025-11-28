# step4_thumbnail_generation/select_best_thumbnail.py

from typing import List, Dict, Any


def select_best_thumbnail(candidates: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    생성된 썸네일 후보들 중에서 최종 1개를 선택한다.

    현재 구현:
    - 가장 처음 생성된 썸네일(index == 0)을 선택한다.
    - 나중에 CTR 예측 모델이나, 썸네일 평가 로직을 붙일 수 있도록
      이 함수만 교체하면 전체 파이프라인을 건드리지 않도록 설계한다.

    :param candidates: [{ "index": int, "url": str, ... }, ...]
    :return: { "index": int, "url": str }
    """
    if not candidates:
        print("[Step4-Select] No candidates available, returning empty result")
        return {
            "index": -1,
            "url": ""
        }

    # TODO: 향후 더 고급 로직으로 교체 가능
    # 예:
    # - 썸네일별 스타일 메타데이터 분석
    # - AB테스트 결과 반영
    # - CTR 예측 모델 호출
    # - GPT-4V를 사용한 이미지 품질 평가

    # 현재는 성공한 첫 번째 후보 선택
    for candidate in candidates:
        if candidate.get("status") == "success" or candidate.get("url"):
            print(f"[Step4-Select] Selected candidate {candidate['index']}")
            return {
                "index": candidate["index"],
                "url": candidate.get("url", ""),
                "local_path": candidate.get("local_path", "")
            }

    # 모두 실패한 경우 첫 번째 반환
    first = candidates[0]
    print(f"[Step4-Select] Fallback to first candidate (index {first['index']})")
    return {
        "index": first["index"],
        "url": first.get("url", ""),
        "local_path": first.get("local_path", "")
    }
