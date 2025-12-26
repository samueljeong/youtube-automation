"""
sermon_config.py
설교 모듈 공통 설정

★ 이 파일이 설교 관련 공통 규칙의 단일 소스입니다.
- 분량 규칙 (CHARS_PER_MIN)
- 기타 공통 설정

Step3, Step4 모두 이 파일을 참조합니다.
"""

import re


# ==========================================
# 분량 설정
# ==========================================
# 2025-12-26 변경: 30분 = 13,000자 기준
# 이전: 900자/분 → 변경: 433자/분
CHARS_PER_MIN = 433  # 분당 글자 수 (공백 포함)


def get_duration_char_count(duration_str: str) -> dict:
    """
    분량(분)을 글자 수로 변환.

    Returns:
        dict: {
            "minutes": 분,
            "min_chars": 최소 글자 수,
            "max_chars": 최대 글자 수,
            "target_chars": 목표 글자 수,
            "chars_per_min": 분당 글자 수
        }
    """
    # 숫자 추출
    if isinstance(duration_str, (int, float)):
        minutes = int(duration_str)
    elif isinstance(duration_str, str):
        match = re.search(r'(\d+)', duration_str)
        minutes = int(match.group(1)) if match else 20
    else:
        minutes = 20

    # 글자 수 계산 (±10% 여유)
    target_chars = minutes * CHARS_PER_MIN
    min_chars = int(target_chars * 0.9)
    max_chars = int(target_chars * 1.1)

    return {
        "minutes": minutes,
        "min_chars": min_chars,
        "max_chars": max_chars,
        "target_chars": target_chars,
        "chars_per_min": CHARS_PER_MIN
    }
