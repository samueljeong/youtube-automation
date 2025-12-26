"""
sermon_modules/prompt.py
프롬프트 빌더 함수들

스타일별 분기 지원:
- three_points (3대지): 전통적인 3포인트 설교
- topical (주제설교): 주제 중심 설교
- expository (강해설교): 본문 해설 중심 설교
"""

import json
import re
from .utils import is_json_guide, parse_json_guide
from .styles import get_style, get_available_styles, READABILITY_GUIDE


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


# ═══════════════════════════════════════════════════════════════
# 스타일별 프롬프트 함수들
# ═══════════════════════════════════════════════════════════════

def get_step2_prompt_for_style(style_id: str, step1_result: dict = None, context_data: dict = None) -> str:
    """
    스타일별 Step2 구조 설계 프롬프트 반환

    Args:
        style_id: 스타일 ID (three_points, topical, expository)
        step1_result: Step1 분석 결과
        context_data: 시대 컨텍스트 데이터

    Returns:
        스타일에 맞는 Step2 구조 설계 프롬프트
    """
    style = get_style(style_id)
    return style.build_step2_prompt(step1_result=step1_result, context_data=context_data)


def get_step3_prompt_for_style(style_id: str, step2_result: dict = None, duration: str = "20분") -> str:
    """
    스타일별 Step3/Step4 설교문 작성 프롬프트 반환

    Args:
        style_id: 스타일 ID (three_points, topical, expository)
        step2_result: Step2 구조 설계 결과
        duration: 설교 분량

    Returns:
        스타일에 맞는 Step3 작성 프롬프트 (가독성 가이드 포함)
    """
    style = get_style(style_id)
    return style.build_step3_prompt(step2_result=step2_result, duration=duration)


def get_style_structure_template(style_id: str) -> dict:
    """
    스타일별 구조 템플릿 반환 (Step2 출력용)

    Args:
        style_id: 스타일 ID

    Returns:
        해당 스타일의 JSON 구조 템플릿
    """
    style = get_style(style_id)
    return style.get_structure_template()


def get_style_checklist(style_id: str) -> list:
    """
    스타일별 체크리스트 반환 (Step3용)

    Args:
        style_id: 스타일 ID

    Returns:
        해당 스타일의 체크리스트 항목 리스트
    """
    style = get_style(style_id)
    return style.get_step3_checklist()


def get_style_illustration_guide(style_id: str) -> str:
    """
    스타일별 예화 배치 가이드 반환

    Args:
        style_id: 스타일 ID

    Returns:
        해당 스타일의 예화 배치 가이드
    """
    style = get_style(style_id)
    return style.get_illustration_guide()


def build_prompt_from_json(json_guide, step_type="step1"):
    """JSON 지침을 기반으로 시스템 프롬프트 생성"""

    # Step1인 경우: 본문 연구 전용 프롬프트 사용
    if step_type == "step1":
        return build_step1_research_prompt()

    # Step2인 경우: 구조 설계 전용 프롬프트 사용
    if step_type == "step2":
        return build_step2_design_prompt()

    # Step3 이상: 기존 로직 사용
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


def get_style_step1_config(style_id):
    """
    스타일별 Step1 분석 설정 반환 (2025-12-26 통합)

    | 스타일 | anchors | key_terms | cross_refs | 강조점 |
    |--------|---------|-----------|------------|--------|
    | 3대지 | 5개 | 4개 | 2개 | 본문 구조 + 주제 연결 |
    | 강해설교 | 10개+ | 6개 | 2개 | 본문 상세 |

    ※ 주제설교는 3대지에 통합됨 (2025-12-26)
    """
    style_configs = {
        'three_point': {
            'anchors_min': 5,
            'key_terms_max': 4,
            'cross_refs_min': 2,  # 주제설교 기능 통합
            'emphasis': '본문 구조',
            'emphasis_instruction': '본문의 구조와 흐름을 중심으로 분석하세요. 대지(포인트)로 나눌 수 있는 자연스러운 구조 단위를 파악하고, 같은 주제를 다루는 다른 성경 구절도 2개 이상 제시하세요.'
        },
        'expository': {
            'anchors_min': 10,
            'key_terms_max': 6,
            'cross_refs_min': 2,
            'emphasis': '본문 상세',
            'emphasis_instruction': '본문의 세부 내용을 철저히 분석하세요. 역사적 배경, 원어 의미, 문맥적 흐름을 깊이 있게 연구하세요.'
        }
    }

    # 스타일 이름으로도 매칭 (ID가 없을 경우)
    # ※ 주제/주제설교 → three_point로 통합 (2025-12-26)
    style_name_mapping = {
        '3대지': 'three_point',
        '대지': 'three_point',
        '주제': 'three_point',      # 통합
        '주제설교': 'three_point',  # 통합
        '강해': 'expository',
        '강해설교': 'expository'
    }

    # style_id로 먼저 찾고, 없으면 이름 매핑으로 찾음
    config = style_configs.get(style_id)

    # topical → three_point 자동 매핑 (하위 호환)
    if style_id == 'topical':
        config = style_configs['three_point']

    if not config:
        for name_part, mapped_id in style_name_mapping.items():
            if name_part in (style_id or ''):
                config = style_configs.get(mapped_id)
                break

    # 기본값 (3대지 기준)
    if not config:
        config = style_configs['three_point']

    return config


def build_step1_research_prompt(style_id=None):
    """
    Step1 전용: 본문 연구 프롬프트 (앵커 ID 포함 JSON)

    핵심 원칙:
    - Step1은 '풍성한 본문 연구 소재' 제공
    - 모든 항목에 고유 ID 부여 (H1, G1, P1, U1, A1, T1, C1, D1, M1)
    - Step2에서 ID를 필수 참조하도록 연결
    - 구조/문맥/역사 배경이 Strong's보다 우선

    스타일별 설정 (2025-12-23):
    - 3대지: anchors 5개, key_terms 3개, cross_refs 0개 (본문 구조 중심)
    - 강해설교: anchors 10개+, key_terms 6개, cross_refs 2개 (본문 상세)
    - 주제설교: anchors 3개, key_terms 2개, cross_refs 5개+ (주제 연결)
    """
    # 스타일별 설정 가져오기
    config = get_style_step1_config(style_id)
    anchors_min = config['anchors_min']
    key_terms_max = config['key_terms_max']
    cross_refs_min = config['cross_refs_min']
    emphasis = config['emphasis']
    emphasis_instruction = config['emphasis_instruction']

    # cross_references 섹션 (주제설교용)
    cross_refs_section = ""
    if cross_refs_min > 0:
        cross_refs_section = f'''
  "cross_references": [
    {{
      "ref_id": "X1",
      "reference": "관련 성경 구절 (예: 요 14:27)",
      "text_summary": "해당 구절의 핵심 내용 요약",
      "connection_to_main_passage": "본문과의 연결점/공통 주제"
    }},
    {{
      "ref_id": "X2",
      "reference": "",
      "text_summary": "",
      "connection_to_main_passage": ""
    }}
  ],
'''
        cross_refs_instruction = f'''
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
【 ★ 주제설교 특별 지침: Cross References (관련 성경 구절) 】
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

주제설교는 하나의 본문에서 출발하되, 같은 주제를 다루는 다른 성경 구절들을
연결하여 풍성한 메시지를 전달합니다.

★ cross_references는 최소 {cross_refs_min}개 이상 제시하세요.
- 구약/신약을 균형 있게 포함
- 본문과 직접적으로 연결되는 구절 우선
- 각 구절이 주제에 어떻게 기여하는지 명확히 설명
'''
    else:
        cross_refs_instruction = ""

    return f'''당신은 설교 준비의 STEP1(본문 연구) 담당자입니다.
지금 단계는 Step2/Step3에서 사용할 '풍성한 본문 연구 소재'를 준비합니다.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
【 ★★★ 스타일별 분석 설정: {emphasis} ★★★ 】
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

{emphasis_instruction}

- anchors (핵심 앵커): {anchors_min}개 이상
- key_terms (핵심 단어): 최대 {key_terms_max}개
- cross_references (관련 구절): {cross_refs_min}개 이상
{cross_refs_instruction}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
【 Step1의 역할 】
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

✅ Step1에서 해야 할 것:
- 본문의 역사적/신학적 배경 분석
- 핵심 메시지(앵커)와 흐름 파악
- 적용 방향 힌트 제시 (예: "현대 직장인의 불안과 연결 가능")
- 피해야 할 오해/오류 정리 (가드레일)

⚠️ Step1에서 하지 않을 것:
- 완성된 설교 문단 작성 (그건 Step3의 역할)
- 근거 없는 역사/뉴스/통계 생성

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
【 우선순위 】
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1) 본문 구조/흐름/이미지/전환점을 먼저 분석
2) 역사·정치·지리 배경은 "본문 이해에 필요한 것만" 정리
3) Strong's/주석은 보조 참고로만 사용(단어 분석은 최대 {key_terms_max}개로 제한)
4) 반드시 가드레일(말하는 것/말하지 않는 것/오독)을 포함

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
【 ID 규칙 (필수) 】
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

- historical_background: H1, H2, H3…
- geography places: G1, G2, G3…
- people_groups: P1, P2, P3…
- structure units: U1, U2, U3…
- anchors: A1, A2, A3… (최소 {anchors_min}개)
- key_terms: T1, T2, T3… (최대 {key_terms_max}개)
- cross_references: X1, X2, X3… (최소 {cross_refs_min}개) ← 주제설교용
- guardrails clearly_affirms: C1, C2, C3…
- guardrails does_not_claim: D1, D2, D3…
- guardrails common_misreads: M1, M2, M3…

★ 모든 ID는 고유해야 하며, STEP2에서 필수 참조됩니다.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
【 ⚠️ Anchor 절-문구 정합성 규칙 (필수) 】
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

★ anchor_phrase는 반드시 range에 명시된 절의 실제 내용과 일치해야 합니다!

✅ 올바른 예시:
- A3 range:"사9:3", anchor_phrase:"즐거움을 더하셨으니... 주 앞에서 즐거워함" (3절 내용)
- A4 range:"사9:4", anchor_phrase:"그 멍에와 어깨의 채찍... 미디안의 날" (4절 내용)

❌ 잘못된 예시:
- A4 range:"사9:4", anchor_phrase:"전리품을 나눌 때처럼" ← 이건 3절 내용!

★ 중요 절에는 복수 Anchor 가능 (A6, A6b 형식):
- 예: 사9:6의 "한 아기가... 정사를 메었고" → A6
- 예: 사9:6의 "기묘자/모사/전능하신 하나님/영존하시는 아버지/평강의 왕" → A6b
- 메시아 칭호, 핵심 선언 등은 별도 Anchor로 분리해야 Step2/3에서 깊이 있게 다룰 수 있음

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
【 Strong's 사용 제한 규칙 (필수) 】
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

- key_terms는 최대 6개만 선정한다(본문 흐름에 결정적인 단어만).
- key_terms에는 설교 적용 문장 금지. 오직 "본문 맥락에서의 의미/기능"만.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
【 주석(commentary) 사용 규칙 (권장) 】
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

- 주석은 "가능한 해석 방향"을 소개할 수 있으나, STEP1에서는 단정 금지
- "일부 주석은 A로 본다" 같은 범위 표시만 허용

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
【 출력 형식 】
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

반드시 아래 JSON 스키마 그대로만 출력하십시오(추가 텍스트 금지).
(스키마 내 모든 배열은 최소 개수를 충족해야 함:
 anchors {anchors_min}개 이상, historical_background 3개 이상, places 3개 이상, does_not_claim 5개 이상)

⚠️ meta는 생성하지 마세요. 시스템이 자동 주입합니다.

```json
{{
  "passage_overview": {{
    "one_paragraph_summary": "본문의 전체 흐름을 2-3문장으로 요약",
    "flow_tags": ["어둠→빛", "압제→해방", "전쟁→평화", "왕권→정의·공의"]
  }},

  "historical_background": [
    {{
      "id": "H1",
      "topic": "★ 구체 명사 필수 (예: 아하스 시대의 아람-에브라임 동맹 위기)",
      "what_happened": "당시 무슨 일이 있었는가 (구체적 사건/상황)",
      "why_it_matters_for_this_text": "이 본문 이해에 왜 중요한가"
    }},
    {{
      "id": "H2",
      "topic": "★ 구체 명사 필수 (예: 앗수르의 갈릴리 정복과 deportation)",
      "what_happened": "",
      "why_it_matters_for_this_text": ""
    }},
    {{
      "id": "H3",
      "topic": "★ 구체 명사 필수 (예: 심판-구원 교차 구조의 문학적 배경)",
      "what_happened": "",
      "why_it_matters_for_this_text": ""
    }}
  ],

  "geography_people": {{
    "places": [
      {{
        "id": "G1",
        "name": "★ 구체 지명 (예: 스불론/납달리)",
        "where_in_bible_context": "성경적 맥락에서 이 장소의 위치",
        "significance_in_this_passage": "이 본문에서 이 장소가 중요한 이유"
      }},
      {{
        "id": "G2",
        "name": "★ 구체 지명 (예: 요단 저편)",
        "where_in_bible_context": "",
        "significance_in_this_passage": ""
      }},
      {{
        "id": "G3",
        "name": "★ 구체 지명 (예: 이방의 갈릴리)",
        "where_in_bible_context": "",
        "significance_in_this_passage": ""
      }}
    ],
    "people_groups": [
      {{
        "id": "P1",
        "name": "인물/집단명",
        "role_in_text": "본문에서의 역할",
        "notes": "관련 배경 정보"
      }}
    ]
  }},

  "context_links": {{
    "immediate_before": "바로 앞 단락/구절의 내용 (예: 사8장 마지막 단락의 어둠/저주)",
    "immediate_after": "★ 바로 다음 단락의 구체적 내용 (예: 사9:8~의 심판/책망 단락). '책 전체 요약'이 아님!",
    "book_level_context": "해당 책 전체에서 이 본문의 위치와 역할"
  }},

  "structure_outline": [
    {{
      "unit_id": "U1",
      "range": "1-2절",
      "function": "도입/배경 설정",
      "turning_point": "있다면 기술 (예: 그러나, 그러므로)",
      "key_images": ["핵심 이미지/표현 1", "핵심 이미지/표현 2"]
    }},
    {{
      "unit_id": "U2",
      "range": "3-5절",
      "function": "핵심 사건/메시지",
      "turning_point": "",
      "key_images": []
    }},
    {{
      "unit_id": "U3",
      "range": "6-7절",
      "function": "결론/귀결/클라이맥스",
      "turning_point": "",
      "key_images": []
    }}
  ],

  "anchors": [
    {{
      "anchor_id": "A1",
      "range": "절 범위 (예: 사9:1)",
      "anchor_phrase": "핵심 구절/표현 (예: 전에는… 이제는…)",
      "text_observation": "텍스트에서 직접 관찰되는 것",
      "function_in_flow": "이 앵커가 본문 흐름에서 하는 역할",
      "interpretation_boundary": "이 앵커에서 확대 해석의 한계/오해 주의"
    }},
    {{
      "anchor_id": "A2",
      "range": "",
      "anchor_phrase": "",
      "text_observation": "",
      "function_in_flow": "",
      "interpretation_boundary": ""
    }}
  ],

  "key_terms": [
    {{
      "term_id": "T1",
      "surface": "한글 표기",
      "lemma": "히브리어/헬라어 원형",
      "translit": "음역",
      "strongs": "Strong's 번호 (예: H215)",
      "lexical_meaning": "사전적 의미",
      "meaning_in_context": "★ 이 본문 맥락에서의 의미 - 의미 범위 전체 포함! (예: shalom은 '전쟁 종식'뿐 아니라 '온전함/회복/안정/질서'까지 포괄)",
      "usage_note": "용례/사용 주의사항 (설교 적용 금지)"
    }}
  ],
{cross_refs_section}
  "guardrails": {{
    "clearly_affirms": [
      {{ "id": "C1", "claim": "본문이 명확히 말하는 것 1 (앵커 기반)", "anchor_ids": ["A1"] }},
      {{ "id": "C2", "claim": "본문이 명확히 말하는 것 2 (앵커 기반)", "anchor_ids": ["A2", "A3"] }},
      {{ "id": "C3", "claim": "", "anchor_ids": [] }},
      {{ "id": "C4", "claim": "", "anchor_ids": [] }},
      {{ "id": "C5", "claim": "", "anchor_ids": [] }}
    ],
    "does_not_claim": [
      {{ "id": "D1", "claim": "★ 본문 경계만 기술: 본문은 [X]를 즉시/자동 보장한다고 말하지 않는다", "reason": "본문 텍스트에 해당 표현이 없음", "avoid_in_step2_3": true }},
      {{ "id": "D2", "claim": "★ 본문은 구체적 시기/정치 체제/국경선 확정을 제공하지 않는다", "reason": "", "avoid_in_step2_3": true }},
      {{ "id": "D3", "claim": "★ 본문은 [특정 이미지]를 [특정 시간표]로 확정하지 않는다", "reason": "", "avoid_in_step2_3": true }},
      {{ "id": "D4", "claim": "★ 본문은 [X]가 모든 개인에게 동일하게 적용된다고 단정하지 않는다", "reason": "", "avoid_in_step2_3": true }},
      {{ "id": "D5", "claim": "", "reason": "", "avoid_in_step2_3": true }}
    ],
    "common_misreads": [
      {{ "id": "M1", "misread": "흔히 하는 잘못된 해석 1", "why_wrong": "왜 틀렸는지 (본문 텍스트 기준)", "correct_boundary": "★ 경계만 표시! (예: '시간표/국경/정권 형태를 확정하지 않음')" }},
      {{ "id": "M2", "misread": "", "why_wrong": "", "correct_boundary": "★ 신학 해석이 아닌 '본문이 제공하는 범위'만 기술" }},
      {{ "id": "M3", "misread": "", "why_wrong": "", "correct_boundary": "" }}
    ]
  }},

  "step2_transfer": {{
    "big_idea_candidates": [
      "STEP2에서 big_idea로 발전시킬 수 있는 핵심 메시지 후보 1",
      "핵심 메시지 후보 2"
    ],
    "primary_anchor_ids": ["A1", "A2", "A3"],
    "required_background_ids": ["H1", "G1"],
    "constraints_for_step2": [
      "STEP2에서는 시사/뉴스/통계 사용 금지(구조만 설계)",
      "각 소대지는 anchors 2개 이상을 반드시 참조",
      "does_not_claim(D*) 위반 금지"
    ]
  }}
}}
```

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
【 최소 개수 요구사항 (스타일별) 】
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

- anchors: 최소 {anchors_min}개
- key_terms: 최대 {key_terms_max}개
- cross_references: 최소 {cross_refs_min}개 (주제설교용)
- historical_background: 최소 3개 (H1~H3+)
- places: 최소 3개 (G1~G3+)
- clearly_affirms: 최소 5개 (C1~C5+)
- does_not_claim: 최소 5개 (D1~D5+)
- common_misreads: 최소 3개 (M1~M3+)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
【 ⚠️ Placeholder 금지 규칙 (필수) 】
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

다음과 같은 포괄어/placeholder는 사용 금지:
- "역사적 배경 주제" → ❌ 금지
- "정치적 배경" → ❌ 금지 (구체 명사로 대체: "아하스 시대 아람-에브라임 동맹 위기")
- "장소명" → ❌ 금지 (구체 지명으로 대체: "스불론", "이방의 갈릴리")

★ topic, name 필드는 반드시 구체적인 고유명사/사건명으로 채우세요.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
【 ⚠️ Guardrails does_not_claim 작성 규칙 (필수) 】
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

does_not_claim은 '신학 해석/결론'이 아니라 '본문이 말하지 않는 범위'만 기술:

✅ 올바른 예시:
- "본문은 '평화'를 모든 개인이 즉시 체감하는 심리 상태로 자동 보장한다고 말하지 않는다"
- "본문은 구체적인 시기/정치 체제/국경선 확정을 제공하지 않는다"
- "본문은 '전쟁 도구의 불사름'을 모든 전쟁의 종결 시간표로 확정하지 않는다"

❌ 금지된 예시 (신학 해석):
- "평화는 선택적 반응과 연결된다" ← 이건 해석/신학 결론, STEP1에서 금지

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
【 ⚠️ Guardrails common_misreads(M*) 작성 규칙 (필수) 】
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

common_misreads의 correct_boundary는 '경계 표현'만 사용:

✅ 올바른 예시 (경계 표현):
- "정치적 요소를 배제한다고 단정하지 말고, 본문이 제공하는 범위를 넘지 않게"
- "시간표/국경/정권 형태를 확정하지 않음"
- "영적/정치적 구원 중 하나만 선택하라고 요구하지 않음"

❌ 금지된 예시 (신학 해석/결론):
- "정치적 맥락보다는 영적 구원을 강조" ← 이건 STEP1치고 해석이 강함, 금지

⚠️ 중요: 반드시 위 JSON 스키마 그대로만 출력하세요. 추가 텍스트 금지.
⚠️ 설교 톤, 적용, 권면, 예화는 절대 금지입니다. 객관적 관찰만 하세요.
⚠️ 모든 ID는 STEP2에서 필수 참조됩니다. ID를 빠뜨리지 마세요.
'''


def build_step2_design_prompt():
    """
    Step2 시스템 프롬프트: 구조 전용(Structure-Only) 모드

    핵심 원칙:
    - Step2는 '구조/근거'만 설계 (mode = structure_only)
    - Step1의 ID(U*, A*, H*, G*, P*, D*, M*, C*)를 필수 참조
    - 본문 유닛 매핑: U1→section_1, U2→section_2, U3→section_3
    - 예화/적용/설교문 생성 금지
    """
    return '''당신은 "설교 구조 설계 엔진(Structure-Only)"입니다.

목표:
- Step1 결과(신규 ID 스키마: U*, A*, H*, G*, P*, D*, M*, C*)를 입력으로 받아,
- Step3에서 어떤 설교 스타일이 오더라도 흔들리지 않는 "본문 흐름 기반 구조(JSON)"만 설계합니다.

절대 금지:
- 완성 설교문 작성 금지(문단/서술형 설교 금지)
- 예화/간증/적용 문장 생성 금지(힌트/키워드 수준도 금지)
- 시사/뉴스/통계/논쟁적 주장 사용 금지
- Step1에 없는 ID 사용 금지 (A*, D*, M*, H*, G*, P* 모두 Step1에 실제 존재해야 함)
- Step1 Guardrails의 does_not_claim(D*)를 위반하는 진술/구조 만들기 금지

핵심 원칙:
1) Step2는 "구조만" 출력한다. (mode = structure_only)
2) 본문 유닛 매핑을 반드시 지킨다:
   - U1(1-2절) → section_1
   - U2(3-5절) → section_2
   - U3(6-7절) → section_3
3) 각 sub는 반드시 아래 5요소를 포함한다:
   - anchor_ids: Step1의 A* 2개 이상
   - outline_blocks: Anchor와 Supporting Verse의 배치 순서 (아래 참고)
   - supporting_verses (outline_blocks 안에서 정확히 2개)
   - guardrail_refs: D* 중 1개 이상
   - misread_refs: M* 중 1개 이상 (해당 sub에서 주의할 경계)
4) outline_blocks 패턴 (★ 중요):
   - supporting_verses는 "sub 마지막에 몰아서" 쓰지 말고, outline_blocks 배열 안에 필요한 위치에 배치한다.
   - 권장 패턴: anchor → supporting → anchor → supporting
   - 예시:
     [
       { "type": "anchor", "id": "A1", "note": "앵커 설명" },
       { "type": "supporting_verse", "ref": "시편 23:4", "note": "보충구절 연결 이유" },
       { "type": "anchor", "id": "A2", "note": "앵커 설명" },
       { "type": "supporting_verse", "ref": "요한복음 1:5", "note": "보충구절 연결 이유" }
     ]

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
【 ★★★ Unit-Anchor 범위 매칭 규칙 (필수) ★★★ 】
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

각 section은 해당 Unit의 절 범위에 속하는 Anchor만 사용할 수 있습니다!

✅ 올바른 매핑:
- section_1 (U1, 1-2절) → A1, A2만 사용 가능
- section_2 (U2, 3-5절) → A3, A4, A5만 사용 가능
- section_3 (U3, 6-7절) → A6, A7, A8, A9, A10, A11 등 6-7절 Anchor만 사용 가능

❌ 절대 금지 (범위 침범):
- section_1에서 A3, A4 사용 ← 3-4절은 U2 영역!
- section_2에서 A6 사용 ← 6절은 U3 영역!
- section_3에서 A12 사용 ← Step1에 없는 ID!

★ Anchor의 range 필드를 확인하고, 해당 절이 section의 unit_id 범위 안에 있는지 반드시 검증하세요.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
【 ★★★ Step1 ID 존재 검증 규칙 (필수) ★★★ 】
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Step2에서 참조하는 모든 ID는 Step1에 실제로 존재해야 합니다!

예를 들어 Step1에 다음이 있다면:
- anchors: A1~A10 (또는 A11까지)
- does_not_claim: D1~D5
- common_misreads: M1~M3
- historical_background: H1~H3
- places: G1~G3

Step2에서 사용 가능한 ID:
✅ A1, A2, ..., A10 (Step1에 있음)
✅ D1, D2, D3, D4, D5 (Step1에 있음)
✅ M1, M2, M3 (Step1에 있음)
✅ H1, H2, H3 (Step1에 있음)
✅ G1, G2, G3 (Step1에 있음)

❌ A12 (Step1에 없음)
❌ D6, D7, D8 (Step1에 없음)
❌ M4, M5, M6 (Step1에 없음)

출력 형식(필수):
- 반드시 "아래 JSON 스키마" 그대로만 출력한다.
- JSON 외의 어떤 텍스트/설명/마크다운도 출력하지 않는다.

필수 JSON 스키마:
```json
{
  "step": "STEP2",
  "mode": "structure_only",
  "reference": "<성경구절>",
  "title": "<설교 제목(사용자 제공 또는 후보)>",
  "big_idea_candidate": "<한 문장>",
  "time_map_percent": { "intro": 10, "s1": 27, "s2": 27, "s3": 27, "ending": 9 },

  "intro": {
    "intro_question": "<한 문장 질문>",
    "flow_preview_only": ["U1(1-2절): 어둠→빛", "U2(3-5절): 압제→해방", "U3(6-7절): 왕권→정의"],
    "constraints": ["시사/뉴스/통계 금지", "예화/적용 문장 금지", "본문 흐름(U1→U2→U3)만 예고"]
  },

  "section_1": {
    "unit_id": "U1",
    "range": "1-2절",
    "background_support": ["H1", "G1"],
    "sub_1": {
      "title": "<구조적 소제목>",
      "anchor_ids": ["A1", "A2"],
      "outline_blocks": [
        { "type": "anchor", "id": "A1", "note": "앵커 설명" },
        { "type": "supporting_verse", "ref": "시편 23:4", "note": "보충구절 연결 이유" },
        { "type": "anchor", "id": "A2", "note": "앵커 설명" },
        { "type": "supporting_verse", "ref": "요한복음 1:5", "note": "보충구절 연결 이유" }
      ],
      "guardrail_refs": ["D1"],
      "misread_refs": ["M1"]
    },
    "sub_2": {
      "title": "<구조적 소제목>",
      "anchor_ids": ["A1", "A2"],
      "outline_blocks": [],
      "guardrail_refs": ["D2"],
      "misread_refs": ["M2"]
    }
  },

  "section_2": {
    "unit_id": "U2",
    "range": "3-5절",
    "background_support": ["H2"],
    "sub_1": {
      "title": "<구조적 소제목>",
      "anchor_ids": ["A3", "A4"],
      "outline_blocks": [],
      "guardrail_refs": ["D1"],
      "misread_refs": ["M1"]
    },
    "sub_2": {
      "title": "<구조적 소제목>",
      "anchor_ids": ["A4", "A5"],
      "outline_blocks": [],
      "guardrail_refs": ["D3"],
      "misread_refs": ["M3"]
    }
  },

  "section_3": {
    "unit_id": "U3",
    "range": "6-7절",
    "background_support": ["H3"],
    "sub_1": {
      "title": "<구조적 소제목>",
      "anchor_ids": ["A6", "A7"],
      "outline_blocks": [],
      "guardrail_refs": ["D5"],
      "misread_refs": ["M2"]
    },
    "sub_2": {
      "title": "<구조적 소제목>",
      "anchor_ids": ["A9", "A10"],
      "outline_blocks": [],
      "guardrail_refs": ["D2"],
      "misread_refs": ["M2"]
    }
  },

  "ending": {
    "summary_points": ["<요약1>", "<요약2>", "<요약3>"],
    "decision_questions": ["<질문1>", "<질문2>"],
    "prayer_points": ["<기도1>", "<기도2>"],
    "guardrail_refs": ["D*", "D*"]
  },

  "self_check": [
    { "check": "all_anchor_ids_exist_in_step1", "pass": true, "notes": "" },
    { "check": "anchors_within_unit_range", "pass": true, "notes": "" },
    { "check": "each_sub_has_2plus_anchors", "pass": true, "notes": "" },
    { "check": "each_sub_has_exactly_2_supporting_verses", "pass": true, "notes": "" },
    { "check": "each_section_has_background_support", "pass": true, "notes": "" },
    { "check": "misread_ids_exist_in_step1_only", "pass": true, "notes": "M1~M3만 사용" },
    { "check": "does_not_claim_ids_exist_in_step1_only", "pass": true, "notes": "D1~D5만 사용" },
    { "check": "no_sermon_paragraphs_or_applications", "pass": true, "notes": "" },
    { "check": "no_news_stats_examples", "pass": true, "notes": "" }
  ]
}
```

검증 규칙 (self_check pass=false 조건):
1. all_anchor_ids_exist_in_step1: Step1에 없는 A* ID 사용 시 pass=false (예: A12가 없는데 사용)
2. all_anchors_in_correct_unit_range: Anchor가 해당 section의 절 범위를 벗어나면 pass=false
   - section_1에서 A3 사용 → pass=false (A3는 3절, section_1은 1-2절)
   - section_2에서 A6 사용 → pass=false (A6은 6절, section_2는 3-5절)
3. all_guardrail_ids_exist_in_step1: Step1에 없는 D*, M* 사용 시 pass=false (예: M4, D6 등)
4. all_background_ids_exist_in_step1: Step1에 없는 H*, G*, P* 사용 시 pass=false
5. each_sub_has_2plus_anchors: 각 sub의 passage_anchors가 2개 미만이면 pass=false
6. each_sub_has_exactly_2_supporting_verses: supporting_verses가 2개가 아니면 pass=false
7. does_not_claim_respected: D* 위반 소지가 있으면 pass=false

반드시 한국어로만, JSON만 출력하세요.
'''


def build_step2_user_prompt(reference: str, step1_result: dict, title: str = "") -> str:
    """
    Step2 유저 프롬프트: Step1 결과를 기반으로 구조 전용 STEP2 JSON 요청

    Args:
        reference: 성경구절 (예: "사9:1-7")
        step1_result: Step1 분석 결과 (dict 또는 JSON 문자열)
        title: 설교 제목 (선택, 없으면 Step1 big_idea 후보 기반)

    Returns:
        Step2 유저 프롬프트 문자열
    """
    # Step1 결과를 JSON 문자열로 변환
    if isinstance(step1_result, dict):
        step1_json = json.dumps(step1_result, ensure_ascii=False, indent=2)
    else:
        step1_json = str(step1_result)

    title_line = title if title else "(없음 - Step1 big idea 후보 기반으로 생성)"

    return f"""[STEP2 입력]

Reference: {reference}
Mode: structure_only
Title candidate: {title_line}

Time map percent:
- intro: 10
- s1: 27
- s2: 27
- s3: 27
- ending: 9

[Step1 Result JSON]
{step1_json}

[작성 지시]
1) Step1의 Structure Outline(Unit U1→U2→U3)을 그대로 사용해 Section_1~3을 구성하세요.
2) 각 sub는 anchor_ids 2개 이상 + outline_blocks(supporting_verses 정확히 2개 포함)를 포함하세요.
3) outline_blocks 안에서 supporting_verses는 "필요한 위치"에 배치하세요.
   (anchor → supporting → anchor → supporting 패턴 권장)
4) guardrail_refs는 D1~D5 중에서, misread_refs는 M1~M3 중에서만 참조하세요.
   (Step1에 존재하는 ID만 사용!)
5) 예화/적용/설교문 문장/시사/뉴스/통계는 절대 쓰지 마세요.
6) 출력은 JSON 1개만 (설명 텍스트 금지).

[Unit-Anchor 범위 규칙]
- section_1(U1, 1-2절) → A1, A2만 사용 가능
- section_2(U2, 3-5절) → A3, A4, A5만 사용 가능
- section_3(U3, 6-7절) → A6~A11 등 6-7절 Anchor만 사용 가능
- 범위 밖 Anchor 사용 금지!

[출력]
- System Prompt에 정의된 STEP2 JSON 스키마 그대로 출력
- JSON 이외의 텍스트 출력 금지
"""


# ═══════════════════════════════════════════════════════════════
# Step3 헬퍼 함수들
# ═══════════════════════════════════════════════════════════════

def _j(obj) -> str:
    """Pretty JSON for prompt embedding (Korean-safe)."""
    return json.dumps(obj, ensure_ascii=False, indent=2)


def _minimize_step1_for_step3(step1: dict) -> dict:
    """
    Step3에서 꼭 필요한 Step1 정보만 추려서 토큰 절약 + 강제 근거 구조 유지.
    (신규 ID 스키마 기준)
    """
    if not step1:
        return {}

    # 신규 스키마 기준 필드들만 선택
    keep = {
        "meta": step1.get("meta", {}),
        "passage_overview": step1.get("passage_overview", {}),
        "structure_outline": step1.get("structure_outline", []),
        "anchors": step1.get("anchors", []),
        "historical_background": step1.get("historical_background", []),
        "geography_people": step1.get("geography_people", {}),
        "context_links": step1.get("context_links", {}),
        "guardrails": step1.get("guardrails", {}),
        "step2_transfer": step1.get("step2_transfer", {}),
        "key_terms": step1.get("key_terms", []),  # 선택(있으면)
    }

    # anchors가 너무 길면(예: 20개 이상) 핵심만 줄이되, ID는 남기기
    anchors = keep.get("anchors") or []
    if len(anchors) > 20:
        keep["anchors"] = anchors[:20]

    # does_not_claim는 Step3에서 중요하니 최대한 유지(너무 길면 상위 12개)
    guard = keep.get("guardrails") or {}
    dnc = guard.get("does_not_claim") or []
    if len(dnc) > 12:
        guard["does_not_claim"] = dnc[:12]
        keep["guardrails"] = guard

    return keep


def build_step3_system_prompt():
    """
    Step3 시스템 프롬프트: 완성 설교문(강연형/발화 가능한 원고) 작성

    핵심 원칙:
    - Step1(본문 분석) + Step2(구조 설계)를 기반으로 완성 설교문 작성
    - 자연스러운 텍스트 형식으로 출력 (JSON 아님)
    - 청중이 은혜받을 수 있는 설교
    """
    return '''당신은 20년 경력의 설교 전문가입니다.
Step1(본문 분석) + Step2(구조 설계)를 바탕으로, 청중의 마음을 움직이는 "완성 설교문"을 작성합니다.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
【 핵심 목표 】
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
청중이 "이건 내 이야기다"라고 느끼고, 삶의 변화를 결단하게 하는 설교문

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
【 출력 형식 】 - 순수 텍스트만 (JSON/마크다운 금지)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

[서론]
(청중의 관심을 끄는 질문이나 상황 제시)
(본문의 배경을 스토리텔링으로 흥미롭게 설명 - 딱딱한 정보전달 금지)
(본문과의 연결)
(오늘 메시지 예고)

[1대지] (대지 제목)
(본문 해설 + 예화 + 적용이 자연스럽게 어우러진 설교)
(성경구절 인용은 별도 줄에)

[2대지] (대지 제목)
(동일한 방식)

[3대지] (대지 제목)
(클라이맥스, 가장 강력한 메시지)

[결론]
(핵심 요약)
(구체적 적용/결단 촉구)
(축복/기도)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
【 설교 작성 원칙 】
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1. 구조는 Step2를 따르되, 살아있는 설교로
   - Step2의 대지/소대지 구조를 뼈대로 사용
   - 그 위에 예화, 적용, 감동을 입혀 생동감 있게

2. 예화는 구체적으로
   ✗ "어떤 사람이 어려움을 겪었습니다"
   ✓ "30대 직장인 김 과장은 갑작스런 해고 통보 앞에서..."
   - 구체적 인물, 상황, 감정, 갈등, 변화를 담아주세요

3. 적용은 실천 가능하게
   ✗ "믿음을 가집시다"
   ✓ "이번 주 하루 10분, 출근 전 오늘 말씀을 묵상해 보세요"
   - 오늘/이번 주/한 달 단위로 구체적 실천 제시

4. 성경 인용 형식
   본문 흐름 중에 자연스럽게 인용하고, 구절은 별도 줄에:

   예수님은 이렇게 약속하셨습니다.

   요한복음 14:27
   "평안을 너희에게 끼치노니 곧 나의 평안을 너희에게 주노라"

   이 평안은 세상이 주는 것과 다릅니다.

5. 가독성
   - 한 문장은 2줄 이내
   - 핵심은 짧게 끊어서
   - 단락 사이 줄바꿈 적극 사용

6. 배경 설명은 스토리텔링으로
   ✗ "이사야서는 주전 8세기에 기록되었으며, 당시 앗수르의 위협이..."
   ✓ "지금 이 순간, 이스라엘 백성들은 두려움에 떨고 있습니다. 앗수르라는
      거대한 제국이 코앞까지 밀려왔기 때문입니다. 모든 이웃 나라들이
      하나씩 무너지는 것을 보면서, '우리는 살아남을 수 있을까?'
      이것이 당시 모든 사람들의 질문이었습니다."
   - 역사적 배경을 '사실 나열'이 아닌 '장면 묘사'로 전달
   - 청중이 그 시대, 그 장소에 있는 것처럼 느끼게 하라
   - 인물의 감정, 고민, 상황을 생생하게 그려라

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
【 Step1/Step2 활용 방법 】
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

- Step1의 앵커(A*)와 배경(H*, G*)은 설교의 근거로 활용
- Step1의 가드레일(D*, M*)은 피해야 할 오해/오류로 참고
- Step2의 구조(section_1~3)는 대지 순서로 따름
- 단, Step1/Step2에 없는 새로운 통찰도 필요하면 추가 가능

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
【 자기 점검 (설교문 끝에 별도 구분자로) 】
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

설교문 작성 후, 맨 끝에 다음 형식으로 자기 점검을 추가하세요:

---SELF_CHECK---
1. 구조 완성: [예/아니오] - 서론/본론(3대지)/결론 모두 포함
2. 예화 포함: [예/아니오] - 구체적 예화 최소 2개 이상
3. 적용 구체성: [예/아니오] - 실천 가능한 적용 제시
4. 분량 적절: [예/아니오] - 목표 분량에 맞음
---END_CHECK---

반드시 한국어로, 순수 텍스트로만 작성하세요.
'''


# ★ 분량 규칙은 sermon_config.py에서 가져옴 (단일 소스)
from .sermon_config import get_duration_char_count


def build_step3_prompt_from_json(
    json_guide,
    meta_data,
    step1_result,
    step2_result,
    style_id: str = None,
    style_name: str = None,
    writing_style: dict = None,
    scripture_citation: dict = None,
    step1_extra_info: dict = None,
    step2_extra_info: dict = None
):
    """
    Step3(설교문 완성) 유저 프롬프트 - Step4(외부 GPT용)와 동일한 형식.

    개선사항 (2025-12-22):
    - JSON 형식 → 읽기 쉬운 텍스트 형식
    - Step1 최소화 제거 → 전체 결과 포함
    - 최우선 지침 강조
    - 스타일별 가이드 포함
    - 상세한 체크리스트 추가
    - Strong's 원어 분석, 시대 컨텍스트 포함
    - 구체적인 글자 수 기준 추가 (분당 270자)
    """
    import json
    from datetime import datetime

    # 메타 기본값
    reference = meta_data.get("reference") or meta_data.get("bible_range") or meta_data.get("scripture") or ""
    title = meta_data.get("title") or meta_data.get("sermon_title") or ""
    target = meta_data.get("target") or meta_data.get("audience") or ""
    service_type = meta_data.get("service_type") or meta_data.get("worship_type") or ""
    duration = meta_data.get("duration_min") or meta_data.get("duration") or "20분"
    special_notes = meta_data.get("special_notes") or meta_data.get("notes") or ""
    category = meta_data.get("category") or ""

    # duration이 숫자면 "분" 붙이기
    if isinstance(duration, (int, float)):
        duration = f"{int(duration)}분"
    elif isinstance(duration, str) and duration.isdigit():
        duration = f"{duration}분"

    # 분량→글자 수 변환 (구체적인 기준)
    duration_info = get_duration_char_count(duration)

    today = datetime.now().strftime("%Y-%m-%d")

    # Step1/Step2 결과를 텍스트로 변환
    def json_to_text(data, indent=0):
        """JSON 객체를 읽기 쉬운 텍스트로 변환"""
        if data is None:
            return ""
        if isinstance(data, str):
            return data
        if isinstance(data, dict):
            lines = []
            for key, value in data.items():
                prefix = "  " * indent
                if isinstance(value, (dict, list)):
                    lines.append(f"{prefix}【{key}】")
                    lines.append(json_to_text(value, indent + 1))
                else:
                    lines.append(f"{prefix}- {key}: {value}")
            return "\n".join(lines)
        if isinstance(data, list):
            lines = []
            for i, item in enumerate(data, 1):
                prefix = "  " * indent
                if isinstance(item, dict):
                    lines.append(f"{prefix}{i}.")
                    lines.append(json_to_text(item, indent + 1))
                else:
                    lines.append(f"{prefix}{i}. {item}")
            return "\n".join(lines)
        return str(data)

    # ===== 프롬프트 구성 시작 =====
    draft = ""

    # 헤더
    draft += "=" * 50 + "\n"
    draft += "설교 초안 자료 (설교문 작성용)\n"
    draft += "=" * 50 + "\n\n"

    # 최우선 지침
    draft += "=" * 50 + "\n"
    draft += "【 ★★★ 최우선 지침 ★★★ 】\n"
    draft += "=" * 50 + "\n\n"

    if duration:
        target_chars = duration_info['target_chars']
        min_chars = duration_info['min_chars']
        max_chars = duration_info['max_chars']
        minutes = duration_info['minutes']
        chars_per_min = duration_info['chars_per_min']

        draft += f"[최우선 필수] 분량: {duration} = {target_chars:,}자\n"
        draft += "━" * 48 + "\n"
        draft += f"   최소 글자 수: {min_chars:,}자 (이 미만은 불합격)\n"
        draft += f"   목표 글자 수: {target_chars:,}자\n"
        draft += f"   최대 글자 수: {max_chars:,}자\n"
        draft += "━" * 48 + "\n"
        draft += f"   계산 기준: {minutes}분 × {chars_per_min}자/분 = {target_chars:,}자\n\n"

        draft += "   [분량 맞추기 전략]\n"
        if minutes >= 25:
            draft += f"   - 서론: 약 {round(target_chars * 0.15):,}자 (도입, 성경 배경)\n"
            draft += f"   - 본론: 약 {round(target_chars * 0.65):,}자 (대지별 설명)\n"
            draft += f"   - 결론: 약 {round(target_chars * 0.20):,}자 (요약 + 결단 촉구 + 기도)\n"
        elif minutes >= 15:
            draft += f"   - 서론: 약 {round(target_chars * 0.15):,}자\n"
            draft += f"   - 본론: 약 {round(target_chars * 0.65):,}자 (대지별 설명)\n"
            draft += f"   - 결론: 약 {round(target_chars * 0.20):,}자\n"
        else:
            draft += "   - 짧은 설교이므로 핵심에 집중하되, 구조(서론/본론/결론)는 유지하세요.\n"

        draft += "\n"
        draft += f"   [경고] {min_chars:,}자 미만 작성 시 불합격 처리됩니다.\n"
        draft += f"   반드시 {target_chars:,}자 이상 작성하세요!\n\n"

    if service_type:
        draft += f"[필수] 예배/집회 유형: {service_type}\n"
        draft += f"   → '{service_type}'에 적합한 톤과 내용으로 작성하세요.\n\n"

    if target:
        draft += f"[필수] 대상: {target}\n\n"

    if special_notes:
        draft += f"[필수] 특별 참고사항:\n"
        draft += f"   {special_notes}\n\n"

    draft += "=" * 50 + "\n\n"

    # 안내 문구
    draft += "※ 중요: 이 자료는 gpt-4o-mini가 만든 '초안'입니다.\n"
    draft += "이 자료를 참고하되, 처음부터 새로 작성해주세요.\n"
    draft += "mini가 만든 문장을 그대로 복사하지 말고, 자연스러운 설교문으로 재작성하세요.\n\n"

    draft += "=" * 50 + "\n\n"

    # 기본 정보
    draft += "【 기본 정보 】\n"
    if category:
        draft += f"- 카테고리: {category}\n"
    if style_name:
        draft += f"- 스타일: {style_name}\n"
    if style_id:
        draft += f"- 스타일ID: {style_id}\n"
    draft += f"- 성경구절: {reference}\n"

    # 개역개정 성경 본문 추가 (오타 없는 원문)
    if reference:
        try:
            from sermon_modules.bible import format_verses_for_prompt
            bible_text = format_verses_for_prompt(reference)
            if bible_text and "찾을 수 없습니다" not in bible_text:
                draft += "\n" + "─" * 40 + "\n"
                draft += "【 ★ 개역개정 성경 본문 (정확한 원문) ★ 】\n"
                draft += "─" * 40 + "\n"
                draft += bible_text + "\n"
                draft += "─" * 40 + "\n"
                draft += "※ 위 성경 본문을 그대로 인용하세요. 절대 수정/생략/요약하지 마세요.\n"
                draft += "─" * 40 + "\n\n"
        except Exception as e:
            # 성경 모듈 로드 실패 시 무시 (기존 동작 유지)
            pass

    if title:
        draft += f"- 제목: {title}\n"
    if service_type:
        draft += f"- 예배·집회 유형: {service_type}\n"
    if duration:
        draft += f"- 분량: {duration}\n"
    if target:
        draft += f"- 대상: {target}\n"
    draft += f"- 작성일: {today}\n"

    draft += "\n" + "=" * 50 + "\n\n"

    # Step1 결과 (★ 토큰 절약을 위해 핵심 정보만 추출)
    if step1_result:
        draft += "【 STEP 1 — 성경 연구 및 분석 (핵심 요약) 】\n\n"
        if isinstance(step1_result, dict):
            # 1. 핵심 메시지 (필수)
            if step1_result.get("core_message") or step1_result.get("핵심_메시지"):
                msg = step1_result.get("core_message") or step1_result.get("핵심_메시지")
                draft += f"▶ 핵심 메시지:\n{msg}\n\n"

            # 2. passage_overview (있으면)
            if step1_result.get("passage_overview"):
                overview = step1_result["passage_overview"]
                if isinstance(overview, dict):
                    if overview.get("one_paragraph_summary"):
                        draft += f"▶ 본문 요약:\n{overview['one_paragraph_summary']}\n\n"
                    if overview.get("flow_tags"):
                        tags = overview["flow_tags"]
                        if isinstance(tags, list):
                            draft += f"▶ 흐름 태그: {' → '.join(tags)}\n\n"

            # 3. 주요 절 해설 (상위 3개만)
            if step1_result.get("key_verses") or step1_result.get("주요_절_해설"):
                verses = step1_result.get("key_verses") or step1_result.get("주요_절_해설")
                if isinstance(verses, list) and len(verses) > 3:
                    verses = verses[:3]
                draft += f"▶ 주요 절 해설 (상위 3개):\n{json_to_text(verses)}\n\n"

            # 4. 핵심 단어 분석 (상위 3개만)
            if step1_result.get("key_words") or step1_result.get("핵심_단어_분석") or step1_result.get("key_terms"):
                words = step1_result.get("key_words") or step1_result.get("핵심_단어_분석") or step1_result.get("key_terms")
                if isinstance(words, list) and len(words) > 3:
                    words = words[:3]
                draft += f"▶ 핵심 단어 (상위 3개):\n{json_to_text(words)}\n\n"

            # 5. 역사적 배경 (상위 2개만)
            if step1_result.get("historical_background") or step1_result.get("역사적_배경"):
                bg = step1_result.get("historical_background") or step1_result.get("역사적_배경")
                if isinstance(bg, list) and len(bg) > 2:
                    bg = bg[:2]
                draft += f"▶ 역사적 배경 (상위 2개):\n{json_to_text(bg)}\n\n"

            # 6. anchors (★ 상위 5개만 - 토큰 절약 핵심)
            if step1_result.get("anchors"):
                anchors = step1_result['anchors']
                if isinstance(anchors, list) and len(anchors) > 5:
                    anchors = anchors[:5]
                    draft += f"▶ Anchors 핵심 근거 (상위 5개/{len(step1_result['anchors'])}개):\n"
                else:
                    draft += f"▶ Anchors 핵심 근거:\n"
                draft += f"{json_to_text(anchors)}\n\n"

            # 7. guardrails (★ 핵심만 추출 - does_not_claim 상위 3개)
            if step1_result.get("guardrails"):
                guardrails = step1_result['guardrails']
                if isinstance(guardrails, dict):
                    draft += "▶ Guardrails (주의사항 핵심):\n"
                    # clearly_affirms 상위 3개
                    if guardrails.get("clearly_affirms"):
                        affirms = guardrails["clearly_affirms"]
                        if isinstance(affirms, list) and len(affirms) > 3:
                            affirms = affirms[:3]
                        draft += f"  [본문이 말하는 것] (상위 3개):\n{json_to_text(affirms)}\n"
                    # does_not_claim 상위 3개
                    if guardrails.get("does_not_claim"):
                        claims = guardrails["does_not_claim"]
                        if isinstance(claims, list) and len(claims) > 3:
                            claims = claims[:3]
                        draft += f"  [본문이 말하지 않는 것] (상위 3개):\n{json_to_text(claims)}\n"
                    draft += "\n"
                else:
                    draft += f"▶ Guardrails:\n{json_to_text(guardrails)}\n\n"

            # 8. step2_transfer (있으면 - 핵심 후보)
            if step1_result.get("step2_transfer"):
                transfer = step1_result["step2_transfer"]
                if isinstance(transfer, dict):
                    if transfer.get("big_idea_candidates"):
                        draft += f"▶ Big Idea 후보:\n"
                        for idea in transfer["big_idea_candidates"][:2]:
                            draft += f"  - {idea}\n"
                        draft += "\n"

            # 9. cross_references (★ 2025-12-26 추가: 참조 구절 - 주제설교에 특히 중요)
            if step1_result.get("cross_references"):
                cross_refs = step1_result["cross_references"]
                if isinstance(cross_refs, list) and cross_refs:
                    draft += f"▶ 참조 구절 (Cross References):\n"
                    for ref in cross_refs[:5]:  # 상위 5개
                        if isinstance(ref, dict):
                            ref_id = ref.get("ref_id", "")
                            reference = ref.get("reference", ref.get("ref", ""))
                            reason = ref.get("reason", ref.get("connection", ""))
                            draft += f"  - [{ref_id}] {reference}"
                            if reason:
                                draft += f": {reason[:80]}{'...' if len(str(reason)) > 80 else ''}"
                            draft += "\n"
                        else:
                            draft += f"  - {ref}\n"
                    draft += "\n"

            # 10. context_links (★ 2025-12-26 추가: 앞뒤 문맥 연결)
            if step1_result.get("context_links"):
                ctx_links = step1_result["context_links"]
                if isinstance(ctx_links, dict):
                    draft += f"▶ 문맥 연결 (Context Links):\n"
                    if ctx_links.get("preceding_context") or ctx_links.get("앞_문맥"):
                        preceding = ctx_links.get("preceding_context") or ctx_links.get("앞_문맥")
                        draft += f"  [앞 문맥] {preceding[:150]}{'...' if len(str(preceding)) > 150 else ''}\n"
                    if ctx_links.get("following_context") or ctx_links.get("뒤_문맥"):
                        following = ctx_links.get("following_context") or ctx_links.get("뒤_문맥")
                        draft += f"  [뒤 문맥] {following[:150]}{'...' if len(str(following)) > 150 else ''}\n"
                    if ctx_links.get("book_context") or ctx_links.get("책_전체_맥락"):
                        book_ctx = ctx_links.get("book_context") or ctx_links.get("책_전체_맥락")
                        draft += f"  [책 전체] {book_ctx[:150]}{'...' if len(str(book_ctx)) > 150 else ''}\n"
                    draft += "\n"

            # 11. geography_people (★ 2025-12-26 추가: 지리/인물 정보)
            if step1_result.get("geography_people"):
                geo_people = step1_result["geography_people"]
                if isinstance(geo_people, dict):
                    has_content = False
                    places = geo_people.get("places", [])
                    people = geo_people.get("people_groups", geo_people.get("people", []))

                    if places or people:
                        draft += f"▶ 지리/인물 정보:\n"
                        has_content = True

                    if places and isinstance(places, list):
                        draft += f"  [장소] "
                        place_strs = []
                        for p in places[:3]:  # 상위 3개
                            if isinstance(p, dict):
                                place_strs.append(f"{p.get('place_id', '')}: {p.get('name', p.get('place', ''))}")
                            else:
                                place_strs.append(str(p))
                        draft += ", ".join(place_strs) + "\n"

                    if people and isinstance(people, list):
                        draft += f"  [인물/그룹] "
                        people_strs = []
                        for p in people[:3]:  # 상위 3개
                            if isinstance(p, dict):
                                people_strs.append(f"{p.get('people_id', p.get('group_id', ''))}: {p.get('name', p.get('group', ''))}")
                            else:
                                people_strs.append(str(p))
                        draft += ", ".join(people_strs) + "\n"

                    if has_content:
                        draft += "\n"

        else:
            # 문자열인 경우 길이 제한
            if len(str(step1_result)) > 2000:
                draft += f"{str(step1_result)[:2000]}... (이하 생략)\n\n"
            else:
                draft += f"{step1_result}\n\n"

        # Strong's 원어 분석 (★ 상위 3개만 - 토큰 절약)
        if step1_extra_info and step1_extra_info.get('strongs_analysis'):
            strongs = step1_extra_info['strongs_analysis']
            key_words = strongs.get('key_words', [])
            if key_words:
                draft += "-" * 40 + "\n"
                draft += "【 ★ Strong's 원어 분석 (상위 3개) 】\n"
                draft += "-" * 40 + "\n\n"
                draft += "▶ 핵심 원어 단어:\n"
                for i, word in enumerate(key_words[:3], 1):  # ★ 7개 → 3개
                    lemma = word.get('lemma', '')
                    translit = word.get('translit', '')
                    strongs_num = word.get('strongs', '')
                    definition = word.get('definition', '')
                    draft += f"  {i}. {lemma} ({translit}, {strongs_num})\n"
                    if definition:
                        draft += f"     → 의미: {definition[:100]}{'...' if len(definition) > 100 else ''}\n"  # 200자 → 100자
                    draft += "\n"

        draft += "=" * 50 + "\n\n"

    # Step2 결과 (★ 토큰 절약을 위해 핵심 구조만 추출)
    if step2_result:
        draft += "【 STEP 2 — 설교 구조 및 개요 (핵심 요약) 】\n\n"
        if isinstance(step2_result, dict):
            # 1. 서론 (요약)
            if step2_result.get("introduction") or step2_result.get("서론"):
                intro = step2_result.get("introduction") or step2_result.get("서론")
                if isinstance(intro, dict):
                    # 핵심 필드만 추출
                    intro_summary = {}
                    for key in ['hook', 'bridge', 'thesis', '도입', '연결', '주제문']:
                        if intro.get(key):
                            intro_summary[key] = intro[key]
                    if intro_summary:
                        draft += f"▶ 서론:\n{json_to_text(intro_summary)}\n\n"
                    else:
                        draft += f"▶ 서론:\n{json_to_text(intro)}\n\n"
                else:
                    draft += f"▶ 서론:\n{json_to_text(intro)}\n\n"

            # 2. 본론/대지 (상위 3개 대지만)
            if step2_result.get("main_points") or step2_result.get("본론") or step2_result.get("대지"):
                points = step2_result.get("main_points") or step2_result.get("본론") or step2_result.get("대지")
                if isinstance(points, list) and len(points) > 3:
                    points = points[:3]
                    draft += f"▶ 본론 (대지) - 상위 3개:\n{json_to_text(points)}\n\n"
                else:
                    draft += f"▶ 본론 (대지):\n{json_to_text(points)}\n\n"

            # 3. sections (ID 스키마) - 상위 3개만
            if step2_result.get("sections"):
                sections = step2_result['sections']
                if isinstance(sections, list) and len(sections) > 3:
                    sections = sections[:3]
                    draft += f"▶ 설교 구조 (상위 3개):\n{json_to_text(sections)}\n\n"
                else:
                    draft += f"▶ 설교 구조:\n{json_to_text(sections)}\n\n"

            # 4. 결론 (요약)
            if step2_result.get("conclusion") or step2_result.get("결론"):
                conclusion = step2_result.get("conclusion") or step2_result.get("결론")
                draft += f"▶ 결론:\n{json_to_text(conclusion)}\n\n"

            # 5. 예화 (상위 2개만)
            if step2_result.get("illustrations") or step2_result.get("예화"):
                illust = step2_result.get("illustrations") or step2_result.get("예화")
                if isinstance(illust, list) and len(illust) > 2:
                    illust = illust[:2]
                    draft += f"▶ 예화 (상위 2개):\n{json_to_text(illust)}\n\n"
                else:
                    draft += f"▶ 예화:\n{json_to_text(illust)}\n\n"

        else:
            # 문자열인 경우 길이 제한
            if len(str(step2_result)) > 2000:
                draft += f"{str(step2_result)[:2000]}... (이하 생략)\n\n"
            else:
                draft += f"{step2_result}\n\n"

        # 시대 컨텍스트 (★ 토큰 절약: 카테고리당 1개, 관심사 3개)
        if step2_extra_info and step2_extra_info.get('context_data'):
            context = step2_extra_info['context_data']
            draft += "-" * 40 + "\n"
            draft += "【 ★ 현재 시대 컨텍스트 (요약) 】\n"
            draft += "-" * 40 + "\n\n"
            draft += f"청중 유형: {context.get('audience', '전체')}\n\n"

            # 주요 뉴스 (★ 카테고리당 1개만)
            news = context.get('news', {})
            if news:
                cat_names = {'economy': '경제', 'politics': '정치', 'society': '사회', 'world': '국제', 'culture': '문화'}
                draft += "▶ 주요 시사 이슈 (카테고리당 1개):\n"
                news_count = 0
                for cat, items in news.items():
                    if items and news_count < 3:  # 최대 3개 카테고리만
                        item = items[0]  # ★ 첫 번째만
                        title_text = item.get('title', '')
                        if len(title_text) > 40:
                            title_text = title_text[:40] + '...'
                        draft += f"  - [{cat_names.get(cat, cat)}] {title_text}\n"
                        news_count += 1
                draft += "\n"

            # 청중 관심사 (★ 상위 3개만)
            concerns = context.get('concerns', [])
            if concerns:
                draft += "▶ 청중 관심사 (상위 3개):\n"
                for concern in concerns[:3]:  # ★ 3개만
                    draft += f"  - {concern}\n"
                draft += "\n"

        draft += "=" * 50 + "\n\n"

    # 스타일별 작성 가이드
    if writing_style or scripture_citation:
        draft += "=" * 50 + "\n"
        draft += f"【 ★★★ 스타일별 작성 가이드{' (' + style_name + ')' if style_name else ''} ★★★ 】\n"
        draft += "=" * 50 + "\n\n"

        # 문단/줄바꿈 스타일
        if writing_style and isinstance(writing_style, dict):
            draft += f"▶ {writing_style.get('label', '문단/줄바꿈 스타일')}\n"
            if writing_style.get('core_principle'):
                draft += f"   핵심: {writing_style['core_principle']}\n"
            if writing_style.get('must_do'):
                draft += "   [해야 할 것]\n"
                for item in writing_style['must_do']:
                    draft += f"      - {item}\n"
            if writing_style.get('must_not'):
                draft += "   [하지 말 것]\n"
                for item in writing_style['must_not']:
                    draft += f"      - {item}\n"
            draft += "\n"

        # 성경구절 인용 방식
        if scripture_citation and isinstance(scripture_citation, dict):
            draft += f"▶ {scripture_citation.get('label', '성경구절 인용 방식')}\n"
            if scripture_citation.get('core_principle'):
                draft += f"   핵심: {scripture_citation['core_principle']}\n"
            if scripture_citation.get('must_do'):
                draft += "   [해야 할 것]\n"
                for item in scripture_citation['must_do']:
                    draft += f"      - {item}\n"
            if scripture_citation.get('good_examples'):
                draft += "   [올바른 예시]\n"
                for ex in scripture_citation['good_examples']:
                    draft += f"      {ex}\n"
            draft += "\n"

        draft += "=" * 50 + "\n\n"

    # ★★★ 스타일별 구조 가이드 (2025-12-23 추가) ★★★
    if style_id:
        try:
            from sermon_modules.styles import ThreePointsStyle, ExpositoryStyle, TopicalStyle
            style_classes = {
                'three_points': ThreePointsStyle,
                'three_point': ThreePointsStyle,
                'expository': ExpositoryStyle,
                'topical': TopicalStyle
            }
            style_class = style_classes.get(style_id)
            if style_class:
                style_guide = style_class.get_step3_writing_guide()
                if style_guide:
                    draft += "=" * 50 + "\n"
                    draft += f"【 ★★★ {style_class.name} 스타일 구조 가이드 ★★★ 】\n"
                    draft += "=" * 50 + "\n"
                    draft += style_guide + "\n"
                    draft += "=" * 50 + "\n\n"

                # 체크리스트도 추가
                checklist = style_class.get_step3_checklist()
                if checklist:
                    draft += "【 스타일별 체크리스트 (필수) 】\n"
                    for item in checklist:
                        draft += f"  □ {item}\n"
                    draft += "\n"
        except Exception as e:
            # 스타일 모듈 로드 실패 시 무시
            pass

    # 최종 작성 지침
    draft += "=" * 50 + "\n"
    draft += "【 최종 작성 지침 】\n"
    draft += "=" * 50 + "\n\n"
    draft += "위의 초안 자료를 참고하여, 완성도 높은 설교문을 처음부터 새로 작성해주세요.\n\n"

    draft += "[필수 체크리스트]\n"
    draft += "  □ Step1의 '핵심 메시지'가 설교 전체에 일관되게 흐르는가?\n"
    draft += "  □ Step1의 '주요 절 해설'과 '핵심 단어 분석'을 활용했는가?\n"
    draft += "  □ Step2의 설교 구조(서론, 본론, 결론)를 따랐는가?\n"
    if duration:
        draft += f"  □ 분량이 {duration} ({duration_info['min_chars']:,}~{duration_info['max_chars']:,}자)에 맞는가?\n"
    if target:
        draft += f"  □ 대상({target})에 맞는 어조와 예시를 사용했는가?\n"
    if service_type:
        draft += f"  □ 예배 유형({service_type})에 맞는 톤인가?\n"
    draft += "  □ 성경 구절이 가독성 가이드에 맞게 줄바꿈 처리되었는가?\n"
    draft += "  □ 마크다운 없이 순수 텍스트로 작성했는가?\n"
    draft += "  □ 복음과 소망, 하나님의 은혜가 분명하게 드러나는가?\n\n"

    if duration:
        draft += "\n" + "━" * 48 + "\n"
        draft += "[최종 분량 확인]\n"
        draft += "━" * 48 + "\n"
        draft += f"{duration} 설교 = 최소 {duration_info['min_chars']:,}자 ~ 최대 {duration_info['max_chars']:,}자\n"
        draft += f"목표: {duration_info['target_chars']:,}자\n\n"
        draft += "작성 완료 후 반드시 글자 수를 확인하세요.\n"
        draft += f"{duration_info['min_chars']:,}자 미만이면 다시 작성해야 합니다.\n"
        draft += "━" * 48 + "\n"
    if service_type:
        draft += f"\n[예배 유형] '{service_type}'에 맞는 톤으로 작성하세요.\n"

    # 자기 점검 포맷
    draft += "\n" + "-" * 40 + "\n"
    draft += "설교문 작성 후, 맨 끝에 다음 형식으로 자기 점검을 추가하세요:\n\n"
    draft += "---SELF_CHECK---\n"
    draft += "1. 구조 완성: [예/아니오] - 서론/본론/결론 모두 포함\n"
    draft += "2. 예화 포함: [예/아니오] - 구체적 예화 최소 2개 이상\n"
    draft += "3. 적용 구체성: [예/아니오] - 실천 가능한 적용 제시\n"
    draft += "4. 분량 적절: [예/아니오] - 목표 분량에 맞음\n"
    draft += "---END_CHECK---\n"

    return draft


# ═══════════════════════════════════════════════════════════════
# Step4 프롬프트 빌더 (설교문 검토 및 정제)
# ═══════════════════════════════════════════════════════════════

def build_step4_system_prompt():
    """
    Step4 시스템 프롬프트: 설교문 검토 및 정제

    핵심 원칙:
    - Step3 완성 설교문을 검토하고 정제
    - ID 사용 추적 검증
    - 최종 품질 검증 (분량, 가독성, guardrail 준수 등)
    - JSON 형식으로 출력
    """
    return '''당신은 설교 작성 파이프라인의 STEP4 모델입니다.
STEP4의 목적은 Step3에서 작성된 "완성 설교문"을 검토하고 정제하여 최종 품질을 보장하는 것입니다.

출력 규칙(절대):
1) 출력은 오직 JSON 1개만 응답합니다. (설명 텍스트 금지)
2) Step1/Step2/Step3에 존재하는 ID만 사용합니다.
   - Anchors: A*
   - Background: H*, G*, P*
   - Guardrails: C*, D*
   - Misreads: M*
3) Step3 설교문을 그대로 유지하되, 아래 항목을 검토/정제합니다:
   - 가독성 규칙 준수 여부 (문장 길이, 줄바꿈, 성경 인용 형식)
   - ID 사용 통계 (사용된 ID 목록 및 누락된 ID)
   - Guardrails 위반 여부 (D* 위반, M* 유도)
   - 분량 적절성 (목표 분량 대비)
4) Step1 Guardrails의 does_not_claim(D*)를 위반하는 표현이 있으면 수정합니다.
5) Step1 common_misreads(M*)를 유도하는 표현이 있으면 수정합니다.

검토 항목:
- 구조 정합성: Step2 구조(Section_1~3, sub_1~2)가 설교문에 반영되었는지
- ID 사용 완전성: Step1/Step2의 주요 ID가 설교문에 활용되었는지
- 가독성: 문장 길이, 줄바꿈, 성경 인용 형식
- Guardrail 준수: D* 위반 없음, M* 유도 없음
- 분량: 목표 분량에 맞게 작성되었는지

반드시 아래 스키마로만 출력하세요:

```json
{
  "step": "STEP4",
  "mode": "review_and_refine",
  "reference": "",
  "style_id": "",
  "title": "",
  "meta": {
    "audience": "",
    "service_type": "",
    "duration_min": 0,
    "special_notes": ""
  },

  "review_summary": {
    "total_issues_found": 0,
    "critical_issues": [],
    "minor_issues": [],
    "improvements_made": []
  },

  "id_usage_stats": {
    "anchors_used": [],
    "anchors_unused": [],
    "backgrounds_used": [],
    "backgrounds_unused": [],
    "guardrails_checked": [],
    "misreads_avoided": []
  },

  "sermon": {
    "intro": {
      "rendered_text": "",
      "used_ids": { "anchor_ids": [], "background_ids": [], "guardrail_ids": [], "misread_ids": [] },
      "refinements": []
    },

    "points": [
      {
        "point_no": 1,
        "title": "",
        "range": "",
        "used_ids": { "unit_id": "", "background_ids": [] },

        "subpoints": [
          {
            "sub_no": "1-1",
            "title": "",
            "anchor_ids": [],
            "outline_blocks_used": [],
            "rendered_text": "",
            "used_ids": { "guardrail_ids": [], "misread_ids": [] },
            "refinements": []
          },
          {
            "sub_no": "1-2",
            "title": "",
            "anchor_ids": [],
            "outline_blocks_used": [],
            "rendered_text": "",
            "used_ids": { "guardrail_ids": [], "misread_ids": [] },
            "refinements": []
          }
        ],

        "transition_to_next": {
          "rendered_text": "",
          "refinements": []
        }
      },

      { "point_no": 2, "...": "same structure" },
      { "point_no": 3, "...": "same structure" }
    ],

    "ending": {
      "rendered_text": "",
      "used_ids": { "guardrail_ids": [], "misread_ids": [] },
      "refinements": []
    }
  },

  "self_check": [
    { "check": "json_only", "pass": false, "notes": "" },
    { "check": "uses_only_step1_step2_step3_ids", "pass": false, "notes": "" },
    { "check": "follows_step2_structure_order", "pass": false, "notes": "" },
    { "check": "does_not_claim_respected", "pass": false, "notes": "D* 위반 여부" },
    { "check": "misreads_avoided", "pass": false, "notes": "M* 유도 여부" },
    { "check": "readability_rules_ok", "pass": false, "notes": "문장/단락 줄바꿈" },
    { "check": "scripture_quote_format_ok", "pass": false, "notes": "구절 인용 줄바꿈 형식" },
    { "check": "duration_target_reasonable", "pass": false, "notes": "분량 체감" },
    { "check": "all_critical_anchors_used", "pass": false, "notes": "핵심 Anchor 사용 여부" },
    { "check": "refinements_applied", "pass": false, "notes": "정제 사항 적용 여부" }
  ]
}
```

Self_Check는 반드시 '검증 후' pass 값을 True/False로 채우세요.
refinements 배열에는 각 섹션에서 수정한 내용을 기록하세요.

반드시 한국어로만, JSON만 출력하세요.
'''


def build_step4_prompt_from_json(json_guide, meta_data, step1_result, step2_result, step3_result, style_id: str = None):
    """
    Step4(검토 및 정제) 유저 프롬프트.
    - Step3 결과를 검토하고 정제
    - ID 사용 추적 검증
    - JSON 형식으로 최종 정제된 설교문 출력
    """
    # 메타 기본값
    reference = meta_data.get("reference") or meta_data.get("bible_range") or meta_data.get("scripture") or ""
    title = meta_data.get("title") or meta_data.get("sermon_title") or ""
    target = meta_data.get("target") or meta_data.get("audience") or ""
    service_type = meta_data.get("service_type") or meta_data.get("worship_type") or ""
    duration_min = meta_data.get("duration_min") or meta_data.get("duration") or 20
    special_notes = meta_data.get("special_notes") or meta_data.get("notes") or ""

    # Step1 최소화 (근거용 - 토큰 절약)
    step1_min = _minimize_step1_for_step3(step1_result or {})

    # Step2는 구조 참조용
    step2_outline = step2_result or {}

    # Step3 결과 (검토 대상)
    step3_sermon = step3_result or {}

    # Step4 유저 프롬프트 템플릿
    user_prompt = f"""[STEP4 입력]

Reference: {reference}
Style_Id: {style_id or "three_points"}
Title: {title}

Meta:
- audience: {target}
- service_type: {service_type}
- duration_min: {duration_min}
- special_notes: {special_notes}

[Step1 Result JSON - ID 참조용]
{_j(step1_min)}

[Step2 Result JSON - 구조 참조용]
{_j(step2_outline)}

[Step3 Result JSON - 검토 대상]
{_j(step3_sermon)}

[검토 및 정제 지시]
1) Step3 설교문을 검토하고 아래 항목을 점검하세요:
   - 가독성 규칙 준수 (문장 최대 2줄, 핵심은 짧게, 줄바꿈 적극 사용)
   - 성경 인용 형식 (줄바꿈 후 구절번호, 줄바꿈 후 본문)
   - ID 사용 완전성 (Step1의 주요 Anchor가 모두 활용되었는지)
   - Guardrail 준수 (D* 위반 없음, M* 유도 없음)

2) 문제가 발견되면 수정하고 refinements 배열에 기록하세요.

3) ID 사용 통계를 id_usage_stats에 채우세요:
   - 사용된 Anchor 목록 (anchors_used)
   - 사용되지 않은 Anchor 목록 (anchors_unused)
   - 사용된 Background 목록 (backgrounds_used)
   - 확인한 Guardrail 목록 (guardrails_checked)

4) review_summary에 검토 결과를 요약하세요:
   - 발견된 이슈 수 (total_issues_found)
   - 심각한 이슈 목록 (critical_issues): D* 위반, M* 유도 등
   - 경미한 이슈 목록 (minor_issues): 가독성, 형식 등
   - 적용한 개선 목록 (improvements_made)

5) 출력은 JSON 1개만.
"""

    return user_prompt


# ═══════════════════════════════════════════════════════════════
# Step2 출력 검증 함수
# ═══════════════════════════════════════════════════════════════

def validate_step2_output(step2_result: dict, step1_result: dict = None) -> dict:
    """
    Step2 출력물의 필수 ID 참조를 검증합니다. (section_* 스키마)

    검증 항목:
    1. ID 존재 검증 (step1_result 제공 시):
       - 사용된 A*, D*, M*, H*, G*, P*가 Step1에 실제 존재하는지
    2. Unit-Anchor 범위 매칭:
       - section_1(1-2절)은 1-2절 Anchor만, section_2(3-5절)은 3-5절 Anchor만 사용
    3. 각 sub별:
       - passage_anchors: A* ID 2개 이상
       - supporting_verses: 정확히 2개
       - background_support: H*/G*/P* ID 1개 이상
       - guardrail_refs: D*/M* ID 1개 이상

    Args:
        step2_result: Step2 출력 결과
        step1_result: Step1 결과 (선택, ID 존재 및 범위 검증용)

    Returns:
        {
            "valid": bool,
            "errors": ["에러 메시지 목록"],
            "warnings": ["경고 메시지 목록"]
        }
    """
    if not step2_result or not isinstance(step2_result, dict):
        return {"valid": False, "errors": ["Step2 결과가 비어있음"], "warnings": []}

    errors = []
    warnings = []

    # Step1에서 유효한 ID 목록 추출
    valid_anchor_ids = set()
    anchor_ranges = {}  # anchor_id -> verse number (예: "A1" -> 1, "A3" -> 3)
    valid_d_ids = set()
    valid_m_ids = set()
    valid_h_ids = set()
    valid_g_ids = set()
    valid_p_ids = set()

    if step1_result and isinstance(step1_result, dict):
        # Anchor IDs 및 범위 추출
        for anchor in step1_result.get("anchors", []):
            aid = anchor.get("anchor_id", "")
            if aid:
                valid_anchor_ids.add(aid)
                # range에서 절 번호 추출 (예: "사9:1" -> 1, "1절" -> 1)
                range_str = anchor.get("range", "")
                verse_match = re.search(r"(\d+)", range_str)
                if verse_match:
                    anchor_ranges[aid] = int(verse_match.group(1))

        # Guardrails IDs 추출
        guardrails = step1_result.get("guardrails", {})
        for d in guardrails.get("does_not_claim", []):
            did = d.get("id", "")
            if did:
                valid_d_ids.add(did)
        for m in guardrails.get("common_misreads", []):
            mid = m.get("id", "")
            if mid:
                valid_m_ids.add(mid)

        # Background IDs 추출
        for h in step1_result.get("historical_background", []):
            hid = h.get("id", "")
            if hid:
                valid_h_ids.add(hid)

        geo = step1_result.get("geography_people", {})
        for g in geo.get("places", []):
            gid = g.get("id", "")
            if gid:
                valid_g_ids.add(gid)
        for p in geo.get("people_groups", []):
            pid = p.get("id", "")
            if pid:
                valid_p_ids.add(pid)

    # section별 허용 절 범위 정의 (★ Step1의 structure_outline에서 동적 추출)
    section_verse_ranges = {}
    if step1_result and isinstance(step1_result, dict):
        structure = step1_result.get("structure_outline", [])
        for idx, unit in enumerate(structure):
            if isinstance(unit, dict):
                unit_id = unit.get("unit_id", f"U{idx+1}")
                verse_range = unit.get("verse_range", unit.get("range", ""))
                # "1-2절", "3-5", "6절~7절" 등에서 숫자 추출
                verse_nums = re.findall(r"(\d+)", verse_range)
                if verse_nums:
                    min_v = int(verse_nums[0])
                    max_v = int(verse_nums[-1]) if len(verse_nums) > 1 else min_v
                    section_verse_ranges[f"section_{idx+1}"] = (min_v, max_v)

    # fallback: Step1이 없거나 structure_outline이 없으면 기본값 사용
    if not section_verse_ranges:
        section_verse_ranges = {
            "section_1": (1, 99),  # 제한 없음 (검증 비활성화)
            "section_2": (1, 99),
            "section_3": (1, 99),
        }
        if step1_result:
            warnings.append("structure_outline 없음 - Unit-Anchor 범위 검증 비활성화")

    # section별 검증 (section_1, section_2, section_3)
    for i in range(1, 4):
        section_key = f"section_{i}"
        legacy_key = f"대지_{i}"
        section = step2_result.get(section_key) or step2_result.get(legacy_key, {})

        if not section:
            errors.append(f"{section_key}이(가) 없음")
            continue

        # 해당 section의 허용 절 범위
        min_verse, max_verse = section_verse_ranges.get(section_key, (1, 7))

        # ★ background_support는 section 레벨에서 검증 (sub 레벨이 아님)
        section_bg_support = section.get("background_support") or section.get("background_ids") or []
        if len(section_bg_support) < 1:
            errors.append(f"{section_key}: background_support가 1개 이상 필요 (현재 {len(section_bg_support)}개)")
        else:
            for b in section_bg_support:
                b_str = str(b)
                # Step1 존재 검증
                if step1_result:
                    if b_str.startswith("H") and b_str not in valid_h_ids:
                        errors.append(f"{section_key}: '{b}'가 Step1에 없음")
                    elif b_str.startswith("G") and b_str not in valid_g_ids:
                        errors.append(f"{section_key}: '{b}'가 Step1에 없음")
                    elif b_str.startswith("P") and b_str not in valid_p_ids:
                        errors.append(f"{section_key}: '{b}'가 Step1에 없음")
                    elif not any(b_str.startswith(p) for p in ("H", "G", "P")):
                        warnings.append(f"{section_key}: '{b}'는 H*/G*/P* 형식이 아님")

        # 소대지별 검증 (sub_1, sub_2)
        for sub_i in [1, 2]:
            sub_key = f"sub_{sub_i}"
            sub = section.get(sub_key, {})

            if not sub:
                warnings.append(f"{section_key}.{sub_key}가 없음")
                continue

            # passage_anchors 검증
            anchors = sub.get("passage_anchors") or sub.get("anchor_ids") or []
            if len(anchors) < 2:
                errors.append(f"{section_key}.{sub_key}: passage_anchors가 2개 이상 필요 (현재 {len(anchors)}개)")
            else:
                for a in anchors:
                    a_str = str(a)
                    # A* 형식 검증
                    if not a_str.startswith("A"):
                        warnings.append(f"{section_key}.{sub_key}: '{a}'는 A* 형식이 아님")
                        continue

                    # Step1 존재 검증
                    if step1_result and a_str not in valid_anchor_ids:
                        errors.append(f"{section_key}.{sub_key}: '{a}'가 Step1에 없음")

                    # Unit-Anchor 범위 매칭 검증
                    if step1_result and a_str in anchor_ranges:
                        verse_num = anchor_ranges[a_str]
                        if verse_num < min_verse or verse_num > max_verse:
                            errors.append(
                                f"{section_key}.{sub_key}: '{a}'({verse_num}절)는 "
                                f"{section_key}({min_verse}-{max_verse}절) 범위 밖 - 범위 침범!"
                            )

            # ★ supporting_verses 검증: outline_blocks에서 추출 (정확히 2개)
            outline_blocks = sub.get("outline_blocks") or []
            sup_verses_from_blocks = [
                block for block in outline_blocks
                if isinstance(block, dict) and block.get("type") == "supporting_verse"
            ]
            # fallback: 기존 supporting_verses 필드도 확인
            sup_verses_direct = sub.get("supporting_verses") or []
            sup_verse_count = len(sup_verses_from_blocks) if sup_verses_from_blocks else len(sup_verses_direct)

            if sup_verse_count != 2:
                errors.append(f"{section_key}.{sub_key}: supporting_verses가 정확히 2개 필요 (현재 {sup_verse_count}개)")

            # guardrail_refs 검증
            guardrails = sub.get("guardrail_refs") or []
            if len(guardrails) < 1:
                errors.append(f"{section_key}.{sub_key}: guardrail_refs가 1개 이상 필요 (현재 {len(guardrails)}개)")
            else:
                for g in guardrails:
                    g_str = str(g)
                    # Step1 존재 검증
                    if step1_result:
                        if g_str.startswith("D") and g_str not in valid_d_ids:
                            errors.append(f"{section_key}.{sub_key}: '{g}'가 Step1에 없음 (D1~D5만 존재)")
                        elif g_str.startswith("M") and g_str not in valid_m_ids:
                            errors.append(f"{section_key}.{sub_key}: '{g}'가 Step1에 없음 (M1~M3만 존재)")
                        elif not any(g_str.startswith(p) for p in ("D", "M")):
                            warnings.append(f"{section_key}.{sub_key}: '{g}'는 D*/M* 형식이 아님")

            # misread_refs 검증 (선택적, 경고만)
            misreads = sub.get("misread_refs") or []
            if len(misreads) < 1:
                warnings.append(f"{section_key}.{sub_key}: misread_refs가 비어있음 (M* ID 권장)")

    # ending 검증
    ending = step2_result.get("ending", {})
    if ending:
        affirms = ending.get("affirms_used") or []
        if len(affirms) < 1:
            warnings.append("ending.affirms_used가 비어있음 (C* ID 권장)")

    # self_check 검증
    self_check = step2_result.get("self_check", [])
    if not self_check:
        warnings.append("self_check가 없음")

    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "warnings": warnings
    }


# ═══════════════════════════════════════════════════════════════
# Step1 출력 검증 함수
# ═══════════════════════════════════════════════════════════════

# Placeholder 금지 키워드
STEP1_PLACEHOLDER_KEYWORDS = [
    "역사적 배경 주제", "정치적 배경", "사회/종교적 배경",
    "장소명", "인물/집단명", "핵심 구절/표현",
    "본문이 명확히 말하는 것", "본문이 말하지 않는 것",
    "흔히 하는 잘못된 해석", "구체 명사 필수", "구체 지명"
]


def validate_step1_output(step1_result: dict) -> dict:
    """
    Step1 출력물의 품질을 검증합니다.

    검증 항목:
    - placeholder 키워드 금지
    - 최소 개수 충족 (anchors 10개, places 3개, does_not_claim 5개)
    - historical_background topic이 구체적인지

    Returns:
        {
            "valid": bool,
            "errors": ["에러 메시지 목록"],
            "warnings": ["경고 메시지 목록"]
        }
    """
    if not step1_result or not isinstance(step1_result, dict):
        return {"valid": False, "errors": ["Step1 결과가 비어있음"], "warnings": []}

    errors = []
    warnings = []

    # 1. Historical Background 검증
    hist_bg = step1_result.get("historical_background", [])
    if len(hist_bg) < 3:
        errors.append(f"historical_background가 3개 이상 필요 (현재 {len(hist_bg)}개)")

    for h in hist_bg:
        topic = h.get("topic", "")
        h_id = h.get("id", "?")
        # Placeholder 검사
        for placeholder in STEP1_PLACEHOLDER_KEYWORDS:
            if placeholder in topic:
                errors.append(f"{h_id}.topic에 placeholder 포함: '{topic}' (구체 명사로 대체 필요)")
                break

    # 2. Geography Places 검증
    geo = step1_result.get("geography_people", {})
    places = geo.get("places", [])
    if len(places) < 3:
        errors.append(f"places가 3개 이상 필요 (현재 {len(places)}개)")

    for p in places:
        name = p.get("name", "")
        p_id = p.get("id", "?")
        for placeholder in STEP1_PLACEHOLDER_KEYWORDS:
            if placeholder in name:
                errors.append(f"{p_id}.name에 placeholder 포함: '{name}' (구체 지명으로 대체 필요)")
                break

    # 3. Anchors 검증
    anchors = step1_result.get("anchors", [])
    if len(anchors) < 10:
        errors.append(f"anchors가 10개 이상 필요 (현재 {len(anchors)}개)")

    # 4. Guardrails 검증
    guardrails = step1_result.get("guardrails", {})
    does_not_claim = guardrails.get("does_not_claim", [])
    if len(does_not_claim) < 5:
        errors.append(f"does_not_claim이 5개 이상 필요 (현재 {len(does_not_claim)}개)")

    clearly_affirms = guardrails.get("clearly_affirms", [])
    if len(clearly_affirms) < 5:
        warnings.append(f"clearly_affirms가 5개 이상 권장 (현재 {len(clearly_affirms)}개)")

    common_misreads = guardrails.get("common_misreads", [])
    if len(common_misreads) < 3:
        warnings.append(f"common_misreads가 3개 이상 권장 (현재 {len(common_misreads)}개)")

    # 5. does_not_claim 내용 검증 (신학 해석 금지)
    theology_keywords = ["선택적 반응", "개인의 결단", "믿음으로만", "은혜와 행위"]
    for d in does_not_claim:
        claim = d.get("claim", "")
        d_id = d.get("id", "?")
        for kw in theology_keywords:
            if kw in claim:
                warnings.append(f"{d_id}: 신학 해석 의심 '{kw}' - 본문 경계만 기술 필요")
                break

    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "warnings": warnings
    }


# ═══════════════════════════════════════════════════════════════
# Step3 self_check 파서 및 검증 함수
# ═══════════════════════════════════════════════════════════════

SELF_CHECK_SEPARATOR = "===SELF_CHECK_JSON==="


def parse_step3_self_check(step3_result: str) -> tuple:
    """
    Step3 출력에서 self_check JSON을 분리합니다.

    Returns:
        (sermon_text: str, self_check: dict or None, parse_error: str or None)
    """
    if not step3_result or not isinstance(step3_result, str):
        return (step3_result or "", None, "Step3 결과가 비어있음")

    if SELF_CHECK_SEPARATOR not in step3_result:
        return (step3_result, None, "self_check 구분자 없음")

    parts = step3_result.split(SELF_CHECK_SEPARATOR, 1)
    sermon_text = parts[0].strip()

    if len(parts) < 2 or not parts[1].strip():
        return (sermon_text, None, "self_check JSON이 비어있음")

    json_text = parts[1].strip()

    # JSON 블록 추출 (```json ... ``` 형식 처리)
    if json_text.startswith("```"):
        # 코드 블록 제거
        lines = json_text.split('\n')
        json_lines = []
        in_block = False
        for line in lines:
            if line.strip().startswith("```"):
                in_block = not in_block
                continue
            if in_block or not line.strip().startswith("```"):
                json_lines.append(line)
        json_text = '\n'.join(json_lines).strip()

    # JSON 파싱 시도
    try:
        self_check = json.loads(json_text)
        return (sermon_text, self_check, None)
    except json.JSONDecodeError as e:
        # 중괄호 범위만 추출해서 재시도
        try:
            start = json_text.find('{')
            end = json_text.rfind('}') + 1
            if start >= 0 and end > start:
                self_check = json.loads(json_text[start:end])
                return (sermon_text, self_check, None)
        except:
            pass
        return (sermon_text, None, f"JSON 파싱 실패: {str(e)}")


def validate_step3_self_check(self_check: dict) -> dict:
    """
    Step3 self_check를 검증하여 재시도 필요 여부를 판단합니다.

    Returns:
        {
            "valid": bool,
            "should_retry": bool,
            "errors": ["에러 메시지 목록"],
            "retry_instructions": "재시도 시 추가할 지시문"
        }
    """
    if not self_check or not isinstance(self_check, dict):
        return {
            "valid": False,
            "should_retry": True,
            "errors": ["self_check가 없거나 유효하지 않음"],
            "retry_instructions": "출력 끝에 ===SELF_CHECK_JSON=== 구분자와 함께 self_check JSON을 반드시 포함하세요."
        }

    errors = []
    retry_reasons = []

    # 1. anchors_used 검증
    if not self_check.get("anchors_used", True):
        errors.append("anchor_ids가 사용되지 않음")
        retry_reasons.append("각 소대지에 passage_anchors(A*) 2개 이상을 반드시 반영하세요")

    # 2. supporting_verses 검증
    if not self_check.get("supporting_verses_exactly_two_each_subpoint", True):
        errors.append("supporting_verses가 소대지당 2개가 아님")
        retry_reasons.append("각 소대지에 supporting_verses 정확히 2개를 인용하세요")

    # 3. does_not_claim 위반 검증 (가장 중요)
    violations = self_check.get("does_not_claim_violations", [])
    if violations:
        errors.append(f"does_not_claim(D*) 위반: {violations}")
        retry_reasons.append(f"다음 주장을 제거하세요: {violations}")

    # 4. 시사 뉴스 사용 검증
    if not self_check.get("no_current_affairs_used", True):
        errors.append("시사 뉴스/통계 등 변동 정보 사용됨")
        retry_reasons.append("시사 뉴스, 통계, 부동산, 정치 등 변동·논쟁 정보를 제거하세요")

    # 5. 분량 준수 검증
    if not self_check.get("duration_respected", True):
        errors.append("분량 미준수")
        retry_reasons.append("지정된 분량을 준수하세요")

    # 6. 가독성 규칙 준수 검증
    if not self_check.get("readability_rules_followed", True):
        errors.append("가독성 규칙 미준수")
        retry_reasons.append("한 문장 최대 2줄, 성경 인용 형식을 지키세요")

    should_retry = len(errors) > 0
    retry_instructions = ""
    if retry_reasons:
        retry_instructions = "\n".join([f"- {r}" for r in retry_reasons])

    return {
        "valid": len(errors) == 0,
        "should_retry": should_retry,
        "errors": errors,
        "retry_instructions": retry_instructions
    }


def build_step3_retry_prompt(original_result: str, validation: dict) -> str:
    """
    self_check 검증 실패 시 재시도 프롬프트를 생성합니다.
    """
    return f"""
이전 출력에서 다음 문제가 발견되었습니다:
{chr(10).join(['- ' + e for e in validation.get('errors', [])])}

아래 지시를 반드시 수정하여 다시 작성하세요:
{validation.get('retry_instructions', '')}

중요:
1. 이전 원고의 좋은 부분은 유지하되, 위 문제만 수정하세요.
2. 출력 끝에 ===SELF_CHECK_JSON=== 구분자와 self_check JSON을 반드시 포함하세요.

=== 이전 원고 (수정 기준) ===
{original_result[:3000]}...
"""
