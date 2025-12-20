"""
sermon_modules/prompt.py
프롬프트 빌더 함수들

스타일별 분기 지원:
- three_points (3대지): 전통적인 3포인트 설교
- topical (주제설교): 주제 중심 설교
- expository (강해설교): 본문 해설 중심 설교
"""

import json
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


def build_step1_research_prompt():
    """
    Step1 전용: 본문 연구 프롬프트 (앵커 ID 포함 JSON)

    핵심 원칙:
    - Step1은 '객관적 본문 연구'만 수행
    - 모든 항목에 고유 ID 부여 (H1, G1, P1, U1, A1, T1, C1, D1, M1)
    - Step2에서 ID를 필수 참조하도록 연결
    - 적용/권면/예화/청중호소/설교 톤 금지
    - 구조/문맥/역사 배경이 Strong's보다 우선
    """
    return '''당신은 설교 준비의 STEP1(본문 연구) 담당자입니다.
지금 단계는 '객관적 본문 연구 데이터'만 생성합니다.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
【 ★★★ 절대 금지 ★★★ 】
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

- 설교 원고 문단 작성 금지
- 적용/권면/결단/예화 금지
- "오늘 우리는 ~해야 합니다" 같은 설교 톤 금지
- 본문 밖의 주장/단정 추가 금지(근거 없는 역사/뉴스/통계 생성 금지)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
【 우선순위 】
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1) 본문 구조/흐름/이미지/전환점을 먼저 분석
2) 역사·정치·지리 배경은 "본문 이해에 필요한 것만" 정리
3) Strong's/주석은 보조 참고로만 사용(단어 분석은 최대 4~6개로 제한)
4) 반드시 가드레일(말하는 것/말하지 않는 것/오독)을 포함

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
【 ID 규칙 (필수) 】
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

- historical_background: H1, H2, H3…
- geography places: G1, G2, G3…
- people_groups: P1, P2, P3…
- structure units: U1, U2, U3…
- anchors: A1, A2, A3… (최소 10개)
- key_terms: T1, T2, T3…
- guardrails clearly_affirms: C1, C2, C3…
- guardrails does_not_claim: D1, D2, D3…
- guardrails common_misreads: M1, M2, M3…

★ 모든 ID는 고유해야 하며, STEP2에서 필수 참조됩니다.

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
 anchors 10개 이상, historical_background 3개 이상, places 2개 이상, does_not_claim 5개 이상)

```json
{
  "meta": {
    "step": "STEP1",
    "reference": "",
    "target_audience": "",
    "service_type": "",
    "duration_min": 0,
    "special_notes": ""
  },

  "passage_overview": {
    "one_paragraph_summary": "본문의 전체 흐름을 2-3문장으로 요약",
    "flow_tags": ["어둠→빛", "압제→해방", "전쟁→평화", "왕권→정의·공의"]
  },

  "historical_background": [
    {
      "id": "H1",
      "topic": "역사적 배경 주제",
      "what_happened": "당시 무슨 일이 있었는가",
      "why_it_matters_for_this_text": "이 본문 이해에 왜 중요한가"
    },
    {
      "id": "H2",
      "topic": "정치적 배경",
      "what_happened": "",
      "why_it_matters_for_this_text": ""
    },
    {
      "id": "H3",
      "topic": "사회/종교적 배경",
      "what_happened": "",
      "why_it_matters_for_this_text": ""
    }
  ],

  "geography_people": {
    "places": [
      {
        "id": "G1",
        "name": "장소명",
        "where_in_bible_context": "성경적 맥락에서 이 장소의 위치",
        "significance_in_this_passage": "이 본문에서 이 장소가 중요한 이유"
      },
      {
        "id": "G2",
        "name": "",
        "where_in_bible_context": "",
        "significance_in_this_passage": ""
      }
    ],
    "people_groups": [
      {
        "id": "P1",
        "name": "인물/집단명",
        "role_in_text": "본문에서의 역할",
        "notes": "관련 배경 정보"
      }
    ]
  },

  "context_links": {
    "immediate_before": "바로 앞 구절/장의 내용과 연결",
    "immediate_after": "바로 뒤 구절/장의 내용과 연결",
    "book_level_context": "해당 책 전체에서 이 본문의 위치와 역할"
  },

  "structure_outline": [
    {
      "unit_id": "U1",
      "range": "1-2절",
      "function": "도입/배경 설정",
      "turning_point": "있다면 기술 (예: 그러나, 그러므로)",
      "key_images": ["핵심 이미지/표현 1", "핵심 이미지/표현 2"]
    },
    {
      "unit_id": "U2",
      "range": "3-5절",
      "function": "핵심 사건/메시지",
      "turning_point": "",
      "key_images": []
    },
    {
      "unit_id": "U3",
      "range": "6-7절",
      "function": "결론/귀결/클라이맥스",
      "turning_point": "",
      "key_images": []
    }
  ],

  "anchors": [
    {
      "anchor_id": "A1",
      "range": "절 범위 (예: 사9:1)",
      "anchor_phrase": "핵심 구절/표현 (예: 전에는… 이제는…)",
      "text_observation": "텍스트에서 직접 관찰되는 것",
      "function_in_flow": "이 앵커가 본문 흐름에서 하는 역할",
      "interpretation_boundary": "이 앵커에서 확대 해석의 한계/오해 주의"
    },
    {
      "anchor_id": "A2",
      "range": "",
      "anchor_phrase": "",
      "text_observation": "",
      "function_in_flow": "",
      "interpretation_boundary": ""
    }
  ],

  "key_terms": [
    {
      "term_id": "T1",
      "surface": "한글 표기",
      "lemma": "히브리어/헬라어 원형",
      "translit": "음역",
      "strongs": "Strong's 번호 (예: H215)",
      "lexical_meaning": "사전적 의미",
      "meaning_in_context": "이 본문 맥락에서의 의미",
      "usage_note": "용례/사용 주의사항 (설교 적용 금지)"
    }
  ],

  "guardrails": {
    "clearly_affirms": [
      { "id": "C1", "claim": "본문이 명확히 말하는 것 1", "anchor_ids": ["A1"] },
      { "id": "C2", "claim": "본문이 명확히 말하는 것 2", "anchor_ids": ["A2", "A3"] },
      { "id": "C3", "claim": "", "anchor_ids": [] },
      { "id": "C4", "claim": "", "anchor_ids": [] },
      { "id": "C5", "claim": "", "anchor_ids": [] }
    ],
    "does_not_claim": [
      { "id": "D1", "claim": "본문이 말하지 않는 것 1", "reason": "왜 이것을 주장할 수 없는지", "avoid_in_step2_3": true },
      { "id": "D2", "claim": "", "reason": "", "avoid_in_step2_3": true },
      { "id": "D3", "claim": "", "reason": "", "avoid_in_step2_3": true },
      { "id": "D4", "claim": "", "reason": "", "avoid_in_step2_3": true },
      { "id": "D5", "claim": "", "reason": "", "avoid_in_step2_3": true }
    ],
    "common_misreads": [
      { "id": "M1", "misread": "흔히 하는 잘못된 해석 1", "why_wrong": "왜 틀렸는지", "correct_boundary": "올바른 해석의 경계" },
      { "id": "M2", "misread": "", "why_wrong": "", "correct_boundary": "" },
      { "id": "M3", "misread": "", "why_wrong": "", "correct_boundary": "" }
    ]
  },

  "step2_transfer": {
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
  }
}
```

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
【 최소 개수 요구사항 】
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

- anchors: 최소 10개 (A1~A10+)
- historical_background: 최소 3개 (H1~H3+)
- places: 최소 2개 (G1~G2+)
- clearly_affirms: 최소 5개 (C1~C5+)
- does_not_claim: 최소 5개 (D1~D5+)
- common_misreads: 최소 3개 (M1~M3+)
- key_terms: 최대 6개 (T1~T6)

⚠️ 중요: 반드시 위 JSON 스키마 그대로만 출력하세요. 추가 텍스트 금지.
⚠️ 설교 톤, 적용, 권면, 예화는 절대 금지입니다. 객관적 관찰만 하세요.
⚠️ 모든 ID는 STEP2에서 필수 참조됩니다. ID를 빠뜨리지 마세요.
'''


def build_step2_design_prompt():
    """
    Step2 전용: 구조 설계 프롬프트 (Step1 ID 필수 참조)

    핵심 원칙:
    - Step2는 '구조/근거'만 설계
    - Step1의 앵커 ID(A1, A2...), 배경 ID(H1, G1...)를 필수 참조
    - does_not_claim(D*) 위반 시 FAIL
    - 예화/적용/시사이슈는 Step3로 이동
    """
    return '''당신은 설교 '구조 설계(OUTLINE)'만 준비하는 역할입니다.
현재 단계: STEP 2 — 구조 설계

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
【 ★★★ STEP2 최우선 핵심 원칙 ★★★ 】
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1. STEP2는 '구조/근거'만 설계합니다.
   - 완성 문단, 길게 쓰는 예화, 적용 설교문은 작성하지 않습니다.

2. STEP2는 반드시 STEP1의 ID를 필수 참조합니다.
   - 각 소대지의 anchor_ids 필드에 STEP1의 A1, A2... ID를 2개 이상 명시
   - 각 대지의 background_ids 필드에 STEP1의 H1, G1... ID를 명시
   - STEP1에 없는 역사적 주장/시사 수치/뉴스 사실을 새로 만들지 마십시오.

3. does_not_claim(D*) 위반 금지
   - STEP1의 guardrails.does_not_claim에 있는 D1, D2... 항목을 위반하면 FAIL

4. 예화/적용/시사이슈는 STEP3에서 작성합니다.
   - STEP2에서는 intro_question(도입 질문) 한 문장만 제시합니다.

5. 청중/분량/예배 유형은 사용자의 입력값이 최우선입니다.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
【 ID 참조 규칙 (필수) 】
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

★ 각 소대지는 STEP1의 anchors에서 2개 이상의 ID를 참조해야 합니다.
★ 각 대지는 STEP1의 historical_background 또는 geography에서 1개 이상의 ID를 참조해야 합니다.
★ guardrails.clearly_affirms(C*)에 근거해야 하며, does_not_claim(D*)를 위반하면 FAIL입니다.

예시:
- anchor_ids: ["A1", "A3"] ← STEP1에서 A1, A3 앵커를 근거로 사용
- background_ids: ["H1", "G2"] ← STEP1에서 H1 배경, G2 지리를 근거로 사용

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
【 출력 형식 】
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

반드시 아래 JSON 형식으로만 응답하세요. 다른 텍스트 없이 순수 JSON만 출력하세요.

```json
{
  "style": "three_points",
  "style_name": "3대지",
  "title": "설교 제목",
  "big_idea": "이 설교의 핵심 한 문장 (STEP1의 step2_transfer.big_idea_candidates 기반)",
  "intro_question": "도입 질문 1개 (시사이슈 금지)",
  "time_map_percent": {"intro": 10, "p1": 27, "p2": 27, "p3": 27, "ending": 9},

  "대지_1": {
    "title": "첫 번째 대지 제목",
    "background_ids": ["H1", "G1"],
    "sub_1": {
      "title": "1-1 소제목",
      "anchor_ids": ["A1", "A2"],
      "anchor_phrases": ["앵커 구절/표현 1 (A1에서)", "앵커 구절/표현 2 (A2에서)"],
      "supporting_verses": ["보충 성경구절 1 (장:절)", "보충 성경구절 2 (장:절)"],
      "one_sentence_explanation": "한 문장 설명"
    },
    "sub_2": {
      "title": "1-2 소제목",
      "anchor_ids": ["A3", "A4"],
      "anchor_phrases": ["앵커 구절/표현 1", "앵커 구절/표현 2"],
      "supporting_verses": ["보충 성경구절 1", "보충 성경구절 2"],
      "one_sentence_explanation": "한 문장 설명"
    }
  },

  "대지_2": {
    "title": "두 번째 대지 제목",
    "background_ids": ["H2"],
    "sub_1": {
      "title": "2-1 소제목",
      "anchor_ids": ["A5", "A6"],
      "anchor_phrases": ["", ""],
      "supporting_verses": ["", ""],
      "one_sentence_explanation": ""
    },
    "sub_2": {
      "title": "2-2 소제목",
      "anchor_ids": ["A7", "A8"],
      "anchor_phrases": ["", ""],
      "supporting_verses": ["", ""],
      "one_sentence_explanation": ""
    }
  },

  "대지_3": {
    "title": "세 번째 대지 제목 (클라이맥스)",
    "background_ids": ["H3", "G2"],
    "sub_1": {
      "title": "3-1 소제목",
      "anchor_ids": ["A9", "A10"],
      "anchor_phrases": ["", ""],
      "supporting_verses": ["", ""],
      "one_sentence_explanation": ""
    },
    "sub_2": {
      "title": "3-2 소제목",
      "anchor_ids": ["A1", "A10"],
      "anchor_phrases": ["", ""],
      "supporting_verses": ["", ""],
      "one_sentence_explanation": ""
    }
  },

  "ending": {
    "summary_points": ["대지1 핵심 요약", "대지2 핵심 요약", "대지3 핵심 요약"],
    "affirms_used": ["C1", "C2", "C3"],
    "decision_questions": ["결단 질문 1", "결단 질문 2"],
    "prayer_points": ["기도 포인트 1", "기도 포인트 2"]
  },

  "self_check": [
    {"check": "각 소대지 anchor_ids 2개 이상", "pass": true},
    {"check": "각 소대지 supporting_verses 2개", "pass": true},
    {"check": "각 대지 background_ids 1개 이상", "pass": true},
    {"check": "대지 흐름이 본문 전개를 따름", "pass": true},
    {"check": "does_not_claim(D*) 위반 없음", "pass": true},
    {"check": "시사 뉴스/수치/논쟁적 정보 미사용", "pass": true}
  ]
}
```

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
【 각 필드 상세 지침 】
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

▶ big_idea (필수)
  - STEP1의 step2_transfer.big_idea_candidates를 기반으로 설교 전체를 관통하는 핵심 한 문장
  - 이 문장이 3개 대지를 연결하는 축이 됨

▶ intro_question (필수)
  - 오늘 말씀과 연결되는 질문 1개
  - ⚠️ 시사이슈/뉴스/생활이야기는 STEP3에서 작성 (여기서 금지)

▶ 대지별 title (필수)
  - STEP1의 step2_transfer.primary_anchor_ids에 있는 앵커들을 기반으로 작성
  - 본문 흐름(전개)을 따르는 논리적 연결

▶ background_ids (각 대지 1개 이상 필수)
  - STEP1의 historical_background(H*) 또는 geography(G*)에서 참조
  - 이 대지가 어떤 배경 정보에 기반하는지 명시

▶ anchor_ids (각 소대지 2개 필수)
  - STEP1의 anchors(A1, A2...)에서 해당 소대지에 맞는 앵커 ID 선택
  - 2개 미만이면 FAIL

▶ anchor_phrases (각 소대지 2개 필수)
  - anchor_ids에 대응하는 실제 구절/표현
  - STEP1의 anchors[].anchor_phrase 값을 가져옴

▶ supporting_verses (각 소대지 2개 필수)
  - 본문 외 보충 성경구절 (장:절 형식)
  - 반드시 2개씩 채워야 함 (1개만 채우면 FAIL)

▶ one_sentence_explanation (필수)
  - 해당 소대지가 말하는 핵심을 한 문장으로
  - 적용/예화가 아닌 '관찰/주장' 수준

▶ affirms_used (필수)
  - STEP1의 guardrails.clearly_affirms에서 사용한 C* ID 목록
  - 이 설교가 어떤 "확실히 말하는 것"에 근거하는지 명시

▶ self_check (필수)
  - 출력 마지막에 반드시 포함
  - 모든 항목이 true여야 PASS

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
【 ⚠️ STEP2에서 절대 금지 】
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1. 시사 뉴스/수치/부동산/정치 같은 논쟁적·변동 정보 사용 금지
2. 예화 힌트 (illustration_hint) 작성 금지 → STEP3에서 작성
3. 적용 문장 (application) 작성 금지 → STEP3에서 작성
4. 아이스브레이킹 생활 이야기 작성 금지 → STEP3에서 작성
5. STEP1에 없는 역사적 주장/배경을 새로 만들어 넣기 금지
6. does_not_claim(D*)에 있는 주장을 포함하기 금지 → 위반 시 FAIL

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
【 대지 연결 원칙 】
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1. 1대지 → 2대지 → 3대지가 본문 흐름(structure_outline U1→U2→U3)을 따라 논리적으로 연결
2. 점진적 심화 또는 순차적 전개 권장
3. 3대지는 클라이맥스로 가장 강력한 메시지

⚠️ 중요: 반드시 위 JSON 형식으로만 응답하세요.
⚠️ 예화/적용/시사이슈는 STEP3에서 작성합니다. STEP2에서는 구조만 설계하세요.
⚠️ STEP1의 ID를 반드시 참조하세요. ID 없이 작성하면 FAIL입니다.
'''


def build_step3_prompt_from_json(json_guide, meta_data, step1_result, step2_result, style_id: str = None):
    """
    Step3용 프롬프트 생성 - Step1/2 데이터를 충실히 전달

    Args:
        json_guide: JSON 지침
        meta_data: 메타 정보 (duration, worship_type, target, sermon_style 등)
        step1_result: Step1 분석 결과
        step2_result: Step2 구조 설계 결과
        style_id: 설교 스타일 ID (없으면 meta_data에서 추출)

    Returns:
        Step3용 완성된 프롬프트
    """
    duration = meta_data.get("duration", "")
    worship_type = meta_data.get("worship_type", "")
    special_notes = meta_data.get("special_notes", "")
    target = meta_data.get("target", "")

    # 스타일 ID 결정 (파라미터 > meta_data > 기본값)
    if not style_id:
        style_id = meta_data.get("sermon_style", "three_points")

    prompt = ""

    # ========================================
    # 1순위: Step1 핵심 분석 (설교의 기초)
    # ========================================
    prompt += "=" * 60 + "\n"
    prompt += "【 ★★★ 1순위: Step1 본문 분석 (설교의 기초) ★★★ 】\n"
    prompt += "=" * 60 + "\n\n"

    if step1_result and isinstance(step1_result, dict):
        # 핵심 메시지 (가장 중요)
        core_message = step1_result.get("핵심_메시지")
        if core_message:
            prompt += "▶ 핵심 메시지 (이 설교의 중심 진리)\n"
            if isinstance(core_message, str):
                prompt += f"   {core_message}\n\n"
            else:
                prompt += json.dumps(core_message, ensure_ascii=False, indent=2)
                prompt += "\n\n"

        # 본문 개요
        overview = step1_result.get("본문_개요")
        if overview:
            prompt += "▶ 본문 개요\n"
            if isinstance(overview, str):
                prompt += f"   {overview}\n\n"
            else:
                prompt += json.dumps(overview, ensure_ascii=False, indent=2)
                prompt += "\n\n"

        # 구조 분석
        structure = step1_result.get("구조_분석")
        if structure:
            prompt += "▶ 본문 구조 분석\n"
            if isinstance(structure, str):
                prompt += f"   {structure}\n\n"
            else:
                prompt += json.dumps(structure, ensure_ascii=False, indent=2)
                prompt += "\n\n"

        # 핵심 단어 분석 (실제 Step1 출력 키)
        key_terms = step1_result.get("핵심_단어_분석") or step1_result.get("key_terms")
        if key_terms:
            prompt += "▶ 핵심 단어/원어 분석\n"
            if isinstance(key_terms, str):
                prompt += f"   {key_terms}\n\n"
            else:
                prompt += json.dumps(key_terms, ensure_ascii=False, indent=2)
                prompt += "\n\n"

        # 주요 절 해설
        verse_notes = step1_result.get("주요_절_해설")
        if verse_notes:
            prompt += "▶ 주요 절 해설 (설교에서 반드시 다뤄야 할 구절)\n"
            if isinstance(verse_notes, str):
                prompt += f"   {verse_notes}\n\n"
            else:
                prompt += json.dumps(verse_notes, ensure_ascii=False, indent=2)
                prompt += "\n\n"

        # 대지 후보
        point_candidates = step1_result.get("대지_후보")
        if point_candidates:
            prompt += "▶ 대지 후보 (Step2에서 선택된 포인트들의 원천)\n"
            if isinstance(point_candidates, str):
                prompt += f"   {point_candidates}\n\n"
            else:
                prompt += json.dumps(point_candidates, ensure_ascii=False, indent=2)
                prompt += "\n\n"

        # 신학적 주제
        theological = step1_result.get("신학적_주제")
        if theological:
            prompt += "▶ 신학적 주제\n"
            if isinstance(theological, str):
                prompt += f"   {theological}\n\n"
            else:
                prompt += json.dumps(theological, ensure_ascii=False, indent=2)
                prompt += "\n\n"

        # 보충 성경구절 (cross_references 호환)
        cross_refs = step1_result.get("보충_성경구절") or step1_result.get("cross_references")
        if cross_refs:
            prompt += "▶ 보충 성경구절\n"
            if isinstance(cross_refs, str):
                prompt += f"   {cross_refs}\n\n"
            else:
                prompt += json.dumps(cross_refs, ensure_ascii=False, indent=2)
                prompt += "\n\n"
    else:
        prompt += "⚠️ Step1 분석 결과가 없습니다. 본문을 직접 분석하여 작성하세요.\n\n"

    # ========================================
    # 2순위: Step2 설교 구조 (뼈대)
    # ========================================
    prompt += "=" * 60 + "\n"
    prompt += "【 ★★★ 2순위: Step2 설교 구조 (반드시 따를 것) ★★★ 】\n"
    prompt += "=" * 60 + "\n\n"

    if step2_result and isinstance(step2_result, dict):
        # 설교 제목
        sermon_title = step2_result.get("설교_제목")
        if sermon_title:
            prompt += "▶ 설교 제목\n"
            if isinstance(sermon_title, str):
                prompt += f"   {sermon_title}\n\n"
            else:
                prompt += json.dumps(sermon_title, ensure_ascii=False, indent=2)
                prompt += "\n\n"

        # 대지 연결 흐름
        flow = step2_result.get("대지_연결_흐름")
        if flow:
            prompt += "▶ 대지 연결 흐름 (1→2→3대지 논리적 연결)\n"
            if isinstance(flow, str):
                prompt += f"   {flow}\n\n"
            else:
                prompt += json.dumps(flow, ensure_ascii=False, indent=2)
                prompt += "\n\n"

        # 서론 방향
        intro = step2_result.get("서론_방향")
        if intro:
            prompt += "▶ 서론 방향\n"
            if isinstance(intro, str):
                prompt += f"   {intro}\n\n"
            else:
                prompt += json.dumps(intro, ensure_ascii=False, indent=2)
                prompt += "\n\n"

        # 대지 1, 2, 3
        for i in range(1, 4):
            point = step2_result.get(f"대지_{i}")
            if point:
                prompt += f"▶ 대지 {i}\n"
                if isinstance(point, str):
                    prompt += f"   {point}\n\n"
                elif isinstance(point, dict):
                    for key, value in point.items():
                        prompt += f"   • {key}: {value}\n"
                    prompt += "\n"
                else:
                    prompt += json.dumps(point, ensure_ascii=False, indent=2)
                    prompt += "\n\n"

        # 결론 방향
        conclusion = step2_result.get("결론_방향")
        if conclusion:
            prompt += "▶ 결론 방향\n"
            if isinstance(conclusion, str):
                prompt += f"   {conclusion}\n\n"
            else:
                prompt += json.dumps(conclusion, ensure_ascii=False, indent=2)
                prompt += "\n\n"

        # 기존 호환: writing_spec, sermon_outline, detailed_points
        writing_spec = step2_result.get("writing_spec", {})
        if writing_spec:
            prompt += "▶ 작성 규격\n"
            for key, value in writing_spec.items():
                prompt += f"  - {key}: {value}\n"
            prompt += "\n"

        sermon_outline = step2_result.get("sermon_outline")
        if sermon_outline:
            prompt += "▶ 설교 구조 (outline)\n"
            prompt += json.dumps(sermon_outline, ensure_ascii=False, indent=2)
            prompt += "\n\n"

        detailed_points = step2_result.get("detailed_points")
        if detailed_points:
            prompt += "▶ 상세 구조\n"
            prompt += json.dumps(detailed_points, ensure_ascii=False, indent=2)
            prompt += "\n\n"
    else:
        prompt += "⚠️ Step2 구조 결과가 없습니다. 3대지 구조를 직접 설계하여 작성하세요.\n\n"

    # ========================================
    # 3순위: 설정 정보 (분량, 대상, 예배유형)
    # ========================================
    prompt += "=" * 60 + "\n"
    prompt += "【 3순위: 설정 정보 】\n"
    prompt += "=" * 60 + "\n"

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

    if special_notes:
        prompt += f"▶ 특별 참고 사항\n   {special_notes}\n\n"

    # ========================================
    # 스타일별 작성 지침 (있는 경우)
    # ========================================
    if json_guide and isinstance(json_guide, dict):
        prompt += "=" * 60 + "\n"
        prompt += "【 스타일별 작성 지침 】\n"
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

    # ========================================
    # 스타일별 작성 가이드 (신규)
    # ========================================
    prompt += "=" * 60 + "\n"
    prompt += f"【 ★★★ 설교 스타일별 작성 가이드 ({style_id}) ★★★ 】\n"
    prompt += "=" * 60 + "\n\n"

    # 스타일별 작성 가이드 추가
    style_writing_guide = get_step3_prompt_for_style(style_id, step2_result, duration or "20분")
    prompt += style_writing_guide
    prompt += "\n\n"

    # 스타일별 예화 가이드 추가
    style_illustration_guide = get_style_illustration_guide(style_id)
    prompt += style_illustration_guide
    prompt += "\n\n"

    # ========================================
    # 최종 체크리스트 (스타일별 + 공통)
    # ========================================
    prompt += "=" * 60 + "\n"
    prompt += "【 ★★★ 최종 체크리스트 ★★★ 】\n"
    prompt += "=" * 60 + "\n\n"

    # 스타일별 체크리스트
    prompt += "▶ 스타일별 필수 체크:\n"
    style_checklist = get_style_checklist(style_id)
    for item in style_checklist:
        prompt += f"  □ {item}\n"
    prompt += "\n"

    # 공통 체크리스트
    prompt += "▶ 공통 필수 체크:\n"
    prompt += "  □ Step1의 '핵심_메시지'가 설교 전체에 일관되게 흐르는가?\n"
    prompt += "  □ Step1의 '주요_절_해설'과 '핵심_단어_분석'을 적절히 활용했는가?\n"
    if duration:
        prompt += f"  □ 분량이 {duration}에 맞는가?\n"
    if target:
        prompt += f"  □ 대상({target})에 맞는 어조와 예시를 사용했는가?\n"
    if worship_type:
        prompt += f"  □ 예배 유형({worship_type})에 맞는 톤인가?\n"
    prompt += "  □ 마크다운 없이 순수 텍스트로 작성했는가?\n"
    prompt += "  □ 복음과 소망, 하나님의 은혜가 분명하게 드러나는가?\n"
    prompt += "  □ 성경 구절이 가독성 가이드에 맞게 줄바꿈 처리되었는가?\n"

    prompt += "\n⚠️ 중요: Step1과 Step2의 분석 결과를 충실히 반영하여, "
    prompt += "일관성 있고 깊이 있는 설교문을 작성하세요.\n"
    prompt += "⚠️ 특히 가독성 가이드를 반드시 따르세요 (성경 구절 줄바꿈, 짧은 문장).\n"

    return prompt
