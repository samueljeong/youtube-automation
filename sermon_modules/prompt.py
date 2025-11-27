"""
sermon_modules/prompt.py
프롬프트 빌더 함수들
"""

import json
from .utils import is_json_guide, parse_json_guide


def get_system_prompt_for_step(step_name):
    """단계별 기본 system prompt 반환"""
    if '제목' in step_name:
        return """당신은 설교 '제목 후보'만 제안하는 역할입니다.

CRITICAL RULES:
1. 반드시 한국어로만 응답하세요
2. 정확히 3개의 제목만 제시하세요
3. 각 제목은 한 줄로 작성하세요
4. 번호, 기호, 마크다운 사용 금지
5. 제목만 작성하고 설명 추가 금지

출력 형식 예시:
하나님의 약속을 믿는 믿음
약속의 땅을 향한 여정
아브라함의 신앙 결단"""
    else:
        return f"""당신은 설교 '초안 자료'만 준비하는 역할입니다.

현재 단계: {step_name}

기본 역할:
- 반드시 한국어로만 응답하세요
- 완성된 설교 문단이 아닌, 자료와 구조만 제공
- 사용자가 제공하는 세부 지침을 최우선으로 따름
- 지침이 없는 경우에만 일반적인 설교 자료 형식 사용

⚠️ 중요: 사용자의 세부 지침이 제공되면 그것을 절대적으로 우선하여 따라야 합니다."""


def build_prompt_from_json(json_guide, step_type="step1"):
    """JSON 지침을 기반으로 시스템 프롬프트 생성"""
    role = json_guide.get("role", "설교 자료 작성자")
    principle = json_guide.get("principle", "")
    output_format = json_guide.get("output_format", {})

    prompt = f"""당신은 '{role}'입니다.

【 핵심 원칙 】
{principle}

【 출력 형식 】
반드시 아래 JSON 형식으로만 응답하세요. 다른 텍스트 없이 순수 JSON만 출력하세요.

```json
{{
"""

    fields = []
    for key, value in output_format.items():
        label = value.get("label", key) if isinstance(value, dict) else key
        description = value.get("description", "") if isinstance(value, dict) else ""
        fields.append(f'  "{key}": "/* {label}: {description} */"')

    prompt += ",\n".join(fields)
    prompt += "\n}\n```\n"

    prompt += "\n【 각 필드 상세 지침 】\n"
    for key, value in output_format.items():
        if isinstance(value, dict):
            label = value.get("label", key)
            description = value.get("description", "")
            purpose = value.get("purpose", "")
            items = value.get("items", [])

            prompt += f"\n▶ {key} ({label})\n"
            if description:
                prompt += f"  - 설명: {description}\n"
            if purpose:
                prompt += f"  - 목적: {purpose}\n"
            if items:
                prompt += f"  - 포함 항목: {', '.join(items)}\n"

            for sub_key in ["per_verse", "per_term", "sub_items", "format"]:
                if sub_key in value:
                    sub_value = value[sub_key]
                    if isinstance(sub_value, dict):
                        prompt += f"  - {sub_key}:\n"
                        for sk, sv in sub_value.items():
                            if isinstance(sv, dict):
                                prompt += f"    • {sk}: {sv.get('description', sv)}\n"
                            else:
                                prompt += f"    • {sk}: {sv}\n"
                    elif isinstance(sub_value, list):
                        prompt += f"  - {sub_key}: {', '.join(str(x) for x in sub_value)}\n"

    prompt += "\n⚠️ 중요: 반드시 위 JSON 형식으로만 응답하세요."
    return prompt


def build_step3_prompt_from_json(json_guide, meta_data, step1_result, step2_result):
    """Step3용 프롬프트 생성"""
    duration = meta_data.get("duration", "")
    worship_type = meta_data.get("worship_type", "")
    special_notes = meta_data.get("special_notes", "")

    prompt = ""

    # 1순위: 홈화면 설정
    prompt += "=" * 60 + "\n"
    prompt += "【 ★★★ 1순위: 홈화면 설정 (최우선) ★★★ 】\n"
    prompt += "=" * 60 + "\n"

    if duration:
        prompt += f"\n🚨 분량: {duration}\n"
        prompt += f"   → 이 설교는 반드시 {duration} 분량으로 작성하세요.\n"

    if worship_type:
        prompt += f"\n🚨 예배/집회 유형: {worship_type}\n"

    if special_notes:
        prompt += f"\n🚨 특별 참고 사항:\n   {special_notes}\n"

    # 기본 정보
    key_labels = {
        "scripture": "성경 본문", "title": "설교 제목", "target": "대상",
        "worship_type": "예배·집회 유형", "duration": "분량",
        "sermon_style": "설교 스타일", "category": "카테고리"
    }
    prompt += "\n▶ 기본 정보\n"
    for key, value in meta_data.items():
        if value and key != "special_notes":
            label = key_labels.get(key, key)
            prompt += f"  - {label}: {value}\n"
    prompt += "\n"

    # 스타일별 지침
    if json_guide and isinstance(json_guide, dict):
        prompt += "=" * 60 + "\n"
        prompt += "【 ★★ 스타일별 작성 지침 ★★ 】\n"
        prompt += "=" * 60 + "\n\n"

        priority_order = json_guide.get("priority_order", {})
        if priority_order:
            prompt += "▶ 우선순위\n"
            for key, value in priority_order.items():
                prompt += f"  {key}: {value}\n"
            prompt += "\n"

        use_from_step1 = json_guide.get("use_from_step1", {})
        if use_from_step1:
            prompt += "▶ Step1 자료 활용법\n"
            for field, config in use_from_step1.items():
                if isinstance(config, dict):
                    instruction = config.get("instruction", "")
                    prompt += f"  • {field}: {instruction}\n"
                else:
                    prompt += f"  • {field}: {config}\n"
            prompt += "\n"

        use_from_step2 = json_guide.get("use_from_step2", {})
        if use_from_step2:
            prompt += "▶ Step2 구조 활용법\n"
            for field, config in use_from_step2.items():
                if isinstance(config, dict):
                    instruction = config.get("instruction", "")
                    prompt += f"  • {field}: {instruction}\n"
                else:
                    prompt += f"  • {field}: {config}\n"
            prompt += "\n"

        writing_rules = json_guide.get("writing_rules", {})
        if writing_rules:
            prompt += "▶ 작성 규칙\n"
            for rule_name, rule_config in writing_rules.items():
                if isinstance(rule_config, dict):
                    label = rule_config.get("label", rule_name)
                    rules = rule_config.get("rules", [])
                    prompt += f"  [{label}]\n"
                    for rule in rules:
                        prompt += f"    - {rule}\n"
            prompt += "\n"

    # Step2 설교 구조
    prompt += "=" * 60 + "\n"
    prompt += "【 ★★ 2순위: Step2 설교 구조 (필수 반영) ★★ 】\n"
    prompt += "=" * 60 + "\n\n"

    if step2_result and isinstance(step2_result, dict):
        writing_spec = step2_result.get("writing_spec", {})
        if writing_spec:
            prompt += "▶ 작성 규격\n"
            for key, value in writing_spec.items():
                prompt += f"  - {key}: {value}\n"
            prompt += "\n"

        sermon_outline = step2_result.get("sermon_outline")
        if sermon_outline:
            prompt += "▶ 설교 구조\n"
            prompt += json.dumps(sermon_outline, ensure_ascii=False, indent=2)
            prompt += "\n\n"

        detailed_points = step2_result.get("detailed_points")
        if detailed_points:
            prompt += "▶ 상세 구조\n"
            prompt += json.dumps(detailed_points, ensure_ascii=False, indent=2)
            prompt += "\n\n"
    else:
        prompt += "(Step2 결과 없음)\n\n"

    # Step1 분석 자료
    prompt += "=" * 60 + "\n"
    prompt += "【 3순위: Step1 분석 자료 (참고 활용) 】\n"
    prompt += "=" * 60 + "\n\n"

    if step1_result and isinstance(step1_result, dict):
        key_terms = step1_result.get("key_terms")
        if key_terms:
            prompt += "▶ 핵심 단어\n"
            prompt += json.dumps(key_terms, ensure_ascii=False, indent=2)
            prompt += "\n\n"

        cross_references = step1_result.get("cross_references")
        if cross_references:
            prompt += "▶ 보충 성경구절\n"
            prompt += json.dumps(cross_references, ensure_ascii=False, indent=2)
            prompt += "\n\n"
    else:
        prompt += "(Step1 결과 없음)\n\n"

    # 최종 지침
    prompt += "=" * 60 + "\n"
    prompt += "【 최종 작성 지침 】\n"
    prompt += "=" * 60 + "\n"
    prompt += "✅ 필수 체크리스트:\n"
    if duration:
        prompt += f"  □ 분량: {duration}\n"
    prompt += "  □ Step2 구조 따름\n"
    prompt += "  □ 마크다운 없이 순수 텍스트\n"

    return prompt
