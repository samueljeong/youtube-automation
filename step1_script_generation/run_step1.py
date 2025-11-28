"""
Step 1 Runner
대본 생성 Step1 실행 모듈
"""

from typing import Dict, Any
from .call_sonnet import generate_script
# from .validate_step1 import validate_output  # TODO: 검증 함수 구현 필요


def run(step1_input: Dict[str, Any]) -> Dict[str, Any]:
    """
    Step1 대본 생성 실행

    Args:
        step1_input: Step1 입력 JSON

    Returns:
        Step1 출력 JSON (대본 데이터)
    """
    print(f"[Step1] Category: {step1_input.get('category')}")
    print(f"[Step1] Mode: {step1_input.get('mode')}")
    print(f"[Step1] Length: {step1_input.get('length_minutes')} minutes")

    # Claude Sonnet 4.5로 대본 생성
    result = generate_script(step1_input)

    # 출력 검증
    # validate_output(result)

    return result


if __name__ == "__main__":
    import json

    # 테스트 입력
    test_input = {
        "step": "step1_script_generation",
        "mode": "test",
        "category": "category1",
        "length_minutes": 1
    }

    result = run(test_input)
    print(json.dumps(result, ensure_ascii=False, indent=2))
