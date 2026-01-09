"""
공통 유틸리티 모듈

중복 코드 제거를 위해 생성됨:
- OpenAI 클라이언트
- GPT-5.1 응답 처리
- JSON 파싱 헬퍼
"""

import os
import re
import json
from typing import Any, Dict


# GPT-5.1 비용 (USD per 1K tokens)
GPT51_COSTS = {
    "input": 0.01,   # $0.01 per 1K input tokens
    "output": 0.03,  # $0.03 per 1K output tokens
}


def get_openai_client():
    """
    OpenAI 클라이언트 반환

    Returns:
        OpenAI: 초기화된 OpenAI 클라이언트

    Raises:
        ValueError: OPENAI_API_KEY 환경변수가 없는 경우
    """
    from openai import OpenAI
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY 환경변수가 설정되지 않았습니다")
    return OpenAI(api_key=api_key)


def extract_gpt51_response(response) -> str:
    """
    GPT-5.1 Responses API 응답에서 텍스트 추출

    GPT-5.1은 기존 Chat Completions API와 다른 형식을 사용:
    - output_text 속성 (단순 텍스트)
    - output 배열 (복잡한 응답)

    Args:
        response: GPT-5.1 Responses API 응답 객체

    Returns:
        str: 추출된 텍스트
    """
    # 1차: output_text 속성 확인 (단순 응답)
    if getattr(response, "output_text", None):
        return response.output_text.strip()

    # 2차: output 배열에서 텍스트 추출 (복잡한 응답)
    text_chunks = []
    for item in getattr(response, "output", []) or []:
        for content in getattr(item, "content", []) or []:
            if getattr(content, "type", "") == "text":
                text_chunks.append(getattr(content, "text", ""))

    return "\n".join(text_chunks).strip()


def repair_json(text: str) -> str:
    """
    불완전한 JSON 수정 시도

    GPT-5.1이 반환하는 JSON에서 흔히 발생하는 문제:
    - 마크다운 코드 블록 (```json ... ```)
    - 후행 콤마 (trailing comma)
    - 누락된 콤마

    Args:
        text: 수정할 JSON 문자열

    Returns:
        str: 수정된 JSON 문자열
    """
    # 1) 마크다운 코드 블록 제거
    if "```" in text:
        match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', text)
        if match:
            text = match.group(1)
        else:
            # 시작만 있고 끝이 없는 경우
            text = re.sub(r'^```(?:json)?\s*', '', text)
            text = re.sub(r'\s*```$', '', text)

    # 2) 후행 콤마 제거 (배열/객체 끝의 콤마)
    text = re.sub(r',\s*([}\]])', r'\1', text)

    # 3) 줄바꿈 후 따옴표가 오는데 콤마가 없는 경우 수정
    # "value"\n"key" → "value",\n"key"
    text = re.sub(r'"\s*\n\s*"(?=[a-zA-Z_가-힣])', '",\n"', text)

    # 4) 객체/배열 끝 후 콤마 없이 다음 요소가 오는 경우
    # }\n{ → },\n{
    text = re.sub(r'}\s*\n\s*{', '},\n{', text)
    # ]\n[ → ],\n[
    text = re.sub(r']\s*\n\s*\[', '],\n[', text)

    return text.strip()


def safe_json_parse(text: str) -> Dict[str, Any]:
    """
    안전한 JSON 파싱 (수정 시도 포함)

    1차: 직접 파싱 시도
    2차: repair_json으로 수정 후 파싱

    Args:
        text: 파싱할 JSON 문자열

    Returns:
        Dict: 파싱된 JSON 객체

    Raises:
        json.JSONDecodeError: 파싱 실패 시
    """
    # 1차 시도: 직접 파싱
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # 2차 시도: 수정 후 파싱
    repaired = repair_json(text)
    return json.loads(repaired)


def calculate_gpt51_cost(input_tokens: int, output_tokens: int) -> float:
    """
    GPT-5.1 비용 계산

    Args:
        input_tokens: 입력 토큰 수
        output_tokens: 출력 토큰 수

    Returns:
        float: USD 비용
    """
    return (input_tokens * GPT51_COSTS["input"] + output_tokens * GPT51_COSTS["output"]) / 1000


def estimate_tokens(text: str) -> int:
    """
    토큰 수 추정 (간단한 휴리스틱)

    한국어: 약 2자당 1토큰
    영어: 약 4자당 1토큰

    Args:
        text: 토큰 수를 추정할 텍스트

    Returns:
        int: 추정 토큰 수
    """
    # 간단한 휴리스틱: 전체 길이의 절반
    return len(text) // 2
