"""
sermon_modules/utils.py
유틸리티 함수들
"""

import re
import json

# 모델별 가격 (USD per 1M tokens)
MODEL_PRICING = {
    'gpt-4o': {'input': 2.50, 'output': 10.00},
    'gpt-4o-mini': {'input': 0.15, 'output': 0.60},
    'gpt-4.1': {'input': 2.00, 'output': 8.00},
    'gpt-4.1-mini': {'input': 0.40, 'output': 1.60},
    'gpt-4.1-nano': {'input': 0.10, 'output': 0.40},
    'gpt-4-turbo': {'input': 10.00, 'output': 30.00},
    'gpt-5': {'input': 5.00, 'output': 15.00},
    'o3': {'input': 10.00, 'output': 40.00},
    'o3-mini': {'input': 1.10, 'output': 4.40},
    'o4-mini': {'input': 1.10, 'output': 4.40},
    'claude-sonnet-4-20250514': {'input': 3.00, 'output': 15.00},
}


def calculate_cost(model_name, input_tokens, output_tokens):
    """모델과 토큰 수로 비용 계산 (USD)"""
    pricing = MODEL_PRICING.get(model_name, MODEL_PRICING['gpt-4o'])
    input_cost = (input_tokens / 1_000_000) * pricing['input']
    output_cost = (output_tokens / 1_000_000) * pricing['output']
    return input_cost + output_cost


def format_json_result(json_data, indent=0):
    """JSON 데이터를 보기 좋은 텍스트 형식으로 변환 (재귀적 처리)"""
    result = []
    indent_str = "  " * indent

    for key, value in json_data.items():
        key_display = key.replace('_', ' ').title()

        if isinstance(value, list):
            result.append(f"{indent_str}【 {key_display} 】")
            for item in value:
                if isinstance(item, dict):
                    for sub_line in format_json_result(item, indent + 1).split('\n'):
                        if sub_line.strip():
                            result.append(f"  {indent_str}{sub_line}")
                else:
                    result.append(f"{indent_str}  - {item}")
            if indent == 0:
                result.append("")
        elif isinstance(value, dict):
            result.append(f"{indent_str}【 {key_display} 】")
            for sub_key, sub_value in value.items():
                sub_key_display = sub_key.replace('_', ' ')
                if isinstance(sub_value, dict):
                    result.append(f"{indent_str}  {sub_key_display}:")
                    for nested_line in format_json_result(sub_value, indent + 2).split('\n'):
                        if nested_line.strip() and not nested_line.strip().startswith('【'):
                            result.append(f"  {nested_line}")
                elif isinstance(sub_value, list):
                    result.append(f"{indent_str}  {sub_key_display}:")
                    for item in sub_value:
                        result.append(f"{indent_str}    - {item}")
                else:
                    result.append(f"{indent_str}  {sub_key_display}: {sub_value}")
            if indent == 0:
                result.append("")
        else:
            result.append(f"{indent_str}【 {key_display} 】")
            result.append(f"{indent_str}{str(value)}")
            if indent == 0:
                result.append("")

    return "\n".join(result).strip()


def remove_markdown(text):
    """마크다운 기호 제거"""
    text = re.sub(r'^#+\s+', '', text, flags=re.MULTILINE)
    text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)
    text = re.sub(r'__(.+?)__', r'\1', text)
    text = re.sub(r'\*(.+?)\*', r'\1', text)
    text = re.sub(r'_(.+?)_', r'\1', text)
    text = re.sub(r'^\s*[-*+]\s+', '', text, flags=re.MULTILINE)
    text = re.sub(r'```[\s\S]*?```', '', text)
    text = re.sub(r'`(.+?)`', r'\1', text)
    return text.strip()


def is_json_guide(guide_text):
    """guide가 JSON 형식인지 확인"""
    if not guide_text or not isinstance(guide_text, str):
        return False
    stripped = guide_text.strip()
    return stripped.startswith('{') and stripped.endswith('}')


def parse_json_guide(guide_text):
    """JSON guide를 파싱하여 딕셔너리로 반환"""
    try:
        return json.loads(guide_text)
    except json.JSONDecodeError as e:
        print(f"[JSON Parse Error] {e}")
        return None
