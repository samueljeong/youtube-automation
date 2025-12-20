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
 anchors 10개 이상, historical_background 3개 이상, places 3개 이상, does_not_claim 5개 이상)

⚠️ meta는 생성하지 마세요. 시스템이 자동 주입합니다.

```json
{
  "passage_overview": {
    "one_paragraph_summary": "본문의 전체 흐름을 2-3문장으로 요약",
    "flow_tags": ["어둠→빛", "압제→해방", "전쟁→평화", "왕권→정의·공의"]
  },

  "historical_background": [
    {
      "id": "H1",
      "topic": "★ 구체 명사 필수 (예: 아하스 시대의 아람-에브라임 동맹 위기)",
      "what_happened": "당시 무슨 일이 있었는가 (구체적 사건/상황)",
      "why_it_matters_for_this_text": "이 본문 이해에 왜 중요한가"
    },
    {
      "id": "H2",
      "topic": "★ 구체 명사 필수 (예: 앗수르의 갈릴리 정복과 deportation)",
      "what_happened": "",
      "why_it_matters_for_this_text": ""
    },
    {
      "id": "H3",
      "topic": "★ 구체 명사 필수 (예: 심판-구원 교차 구조의 문학적 배경)",
      "what_happened": "",
      "why_it_matters_for_this_text": ""
    }
  ],

  "geography_people": {
    "places": [
      {
        "id": "G1",
        "name": "★ 구체 지명 (예: 스불론/납달리)",
        "where_in_bible_context": "성경적 맥락에서 이 장소의 위치",
        "significance_in_this_passage": "이 본문에서 이 장소가 중요한 이유"
      },
      {
        "id": "G2",
        "name": "★ 구체 지명 (예: 요단 저편)",
        "where_in_bible_context": "",
        "significance_in_this_passage": ""
      },
      {
        "id": "G3",
        "name": "★ 구체 지명 (예: 이방의 갈릴리)",
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
    "immediate_before": "바로 앞 단락/구절의 내용 (예: 사8장 마지막 단락의 어둠/저주)",
    "immediate_after": "★ 바로 다음 단락의 구체적 내용 (예: 사9:8~의 심판/책망 단락). '책 전체 요약'이 아님!",
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
      "meaning_in_context": "★ 이 본문 맥락에서의 의미 - 의미 범위 전체 포함! (예: shalom은 '전쟁 종식'뿐 아니라 '온전함/회복/안정/질서'까지 포괄)",
      "usage_note": "용례/사용 주의사항 (설교 적용 금지)"
    }
  ],

  "guardrails": {
    "clearly_affirms": [
      { "id": "C1", "claim": "본문이 명확히 말하는 것 1 (앵커 기반)", "anchor_ids": ["A1"] },
      { "id": "C2", "claim": "본문이 명확히 말하는 것 2 (앵커 기반)", "anchor_ids": ["A2", "A3"] },
      { "id": "C3", "claim": "", "anchor_ids": [] },
      { "id": "C4", "claim": "", "anchor_ids": [] },
      { "id": "C5", "claim": "", "anchor_ids": [] }
    ],
    "does_not_claim": [
      { "id": "D1", "claim": "★ 본문 경계만 기술: 본문은 [X]를 즉시/자동 보장한다고 말하지 않는다", "reason": "본문 텍스트에 해당 표현이 없음", "avoid_in_step2_3": true },
      { "id": "D2", "claim": "★ 본문은 구체적 시기/정치 체제/국경선 확정을 제공하지 않는다", "reason": "", "avoid_in_step2_3": true },
      { "id": "D3", "claim": "★ 본문은 [특정 이미지]를 [특정 시간표]로 확정하지 않는다", "reason": "", "avoid_in_step2_3": true },
      { "id": "D4", "claim": "★ 본문은 [X]가 모든 개인에게 동일하게 적용된다고 단정하지 않는다", "reason": "", "avoid_in_step2_3": true },
      { "id": "D5", "claim": "", "reason": "", "avoid_in_step2_3": true }
    ],
    "common_misreads": [
      { "id": "M1", "misread": "흔히 하는 잘못된 해석 1", "why_wrong": "왜 틀렸는지 (본문 텍스트 기준)", "correct_boundary": "★ 경계만 표시! (예: '시간표/국경/정권 형태를 확정하지 않음')" },
      { "id": "M2", "misread": "", "why_wrong": "", "correct_boundary": "★ 신학 해석이 아닌 '본문이 제공하는 범위'만 기술" },
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
- places: 최소 3개 (G1~G3+) ★ 3개 필수
- clearly_affirms: 최소 5개 (C1~C5+)
- does_not_claim: 최소 5개 (D1~D5+)
- common_misreads: 최소 3개 (M1~M3+)
- key_terms: 최대 6개 (T1~T6)

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
3) 각 sub는 반드시 아래 4요소를 포함한다:
   - passage_anchors: Step1의 A* 2개 이상
   - supporting_verses: 정확히 2개(성경구절 표기만, 본문 인용문 금지)
   - background_support: Step1의 H/G/P 중 1개 이상
   - guardrail_refs: D* 또는 M* 중 1개 이상(해당 sub에서 주의할 경계 표시)
4) supporting_verses는 "Step1 본문"과 논리적으로 연결되는 보충구절로 선택하되,
   - 정확히 2개만
   - 중복 최소화(가능하면 sub끼리 동일 구절 반복 피하기)

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
    "constraints": ["시사/뉴스/통계 금지", "예화/적용 문장 금지", "본문 흐름(U1→U2→U3)만 예고"]
  },

  "section_1": {
    "unit_id": "U1",
    "range": "1-2절",
    "background_support": ["H*", "G*"],
    "sub_1": {
      "title": "<구조적 소제목>",
      "passage_anchors": ["A*", "A*"],
      "supporting_verses": ["<보충구절1>", "<보충구절2>"],
      "guardrail_refs": ["D*", "M*"]
    },
    "sub_2": {
      "title": "<구조적 소제목>",
      "passage_anchors": ["A*", "A*"],
      "supporting_verses": ["<보충구절1>", "<보충구절2>"],
      "guardrail_refs": ["D*", "M*"]
    }
  },

  "section_2": {
    "unit_id": "U2",
    "range": "3-5절",
    "background_support": ["H*"],
    "sub_1": {
      "title": "<구조적 소제목>",
      "passage_anchors": ["A*", "A*"],
      "supporting_verses": ["<보충구절1>", "<보충구절2>"],
      "guardrail_refs": ["D*", "M*"]
    },
    "sub_2": {
      "title": "<구조적 소제목>",
      "passage_anchors": ["A*", "A*"],
      "supporting_verses": ["<보충구절1>", "<보충구절2>"],
      "guardrail_refs": ["D*", "M*"]
    }
  },

  "section_3": {
    "unit_id": "U3",
    "range": "6-7절",
    "background_support": ["H*"],
    "sub_1": {
      "title": "<구조적 소제목>",
      "passage_anchors": ["A*", "A*"],
      "supporting_verses": ["<보충구절1>", "<보충구절2>"],
      "guardrail_refs": ["D*", "M*"]
    },
    "sub_2": {
      "title": "<구조적 소제목>",
      "passage_anchors": ["A*", "A*"],
      "supporting_verses": ["<보충구절1>", "<보충구절2>"],
      "guardrail_refs": ["D*", "M*"]
    }
  },

  "ending": {
    "summary_points": ["<요약1>", "<요약2>", "<요약3>"],
    "decision_questions": ["<질문1>", "<질문2>"],
    "prayer_points": ["<기도1>", "<기도2>"],
    "guardrail_refs": ["D*", "D*"]
  },

  "self_check": [
    { "check": "all_anchor_ids_exist_in_step1", "pass": true, "notes": "사용된 A* ID가 모두 Step1에 존재하는지" },
    { "check": "all_anchors_in_correct_unit_range", "pass": true, "notes": "각 section의 A*가 해당 절 범위 안에 있는지" },
    { "check": "all_guardrail_ids_exist_in_step1", "pass": true, "notes": "사용된 D*, M* ID가 모두 Step1에 존재하는지" },
    { "check": "all_background_ids_exist_in_step1", "pass": true, "notes": "사용된 H*, G*, P* ID가 모두 Step1에 존재하는지" },
    { "check": "each_sub_has_2plus_anchors", "pass": true, "notes": "" },
    { "check": "each_sub_has_exactly_2_supporting_verses", "pass": true, "notes": "" },
    { "check": "each_section_has_background_support", "pass": true, "notes": "" },
    { "check": "flow_follows_U1_U2_U3", "pass": true, "notes": "" },
    { "check": "does_not_claim_respected", "pass": true, "notes": "" },
    { "check": "no_sermon_paragraphs_or_applications", "pass": true, "notes": "" }
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

    return f"""[STEP2 요청: 구조 전용 출력]

아래 Step1 결과(신규 ID 스키마)를 기반으로,
설교 스타일/예화/적용 없이 "구조 전용 STEP2 JSON"을 출력하세요.

[기본 입력]
- reference: {reference}
- title(선택): {title_line}
- time_map_percent(고정): intro 10, s1 27, s2 27, s3 27, ending 9

[필수 규칙]
1) U1(1-2절)→section_1, U2(3-5절)→section_2, U3(6-7절)→section_3 고정
2) 각 sub는:
   - passage_anchors: A* 2개 이상(반드시 Step1에 있는 A*만)
   - supporting_verses: 정확히 2개(구절 표기만)
   - background_support: H/G/P 중 1개 이상(반드시 Step1에 있는 ID만)
   - guardrail_refs: D* 또는 M* 중 1개 이상(반드시 Step1에 있는 ID만)
3) Step2에서는 시사/뉴스/통계/논쟁 정보 사용 금지
4) Step2에서는 예화/적용/설교 문단 작성 금지(구조/근거만)

[Step1 결과(JSON)]
{step1_json}

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


def build_step3_prompt_from_json(json_guide, meta_data, step1_result, step2_result, style_id: str = None):
    """
    신규 ID 스키마(anchors/H*/G*/D*) 기반 Step3(원고) 프롬프트 템플릿.
    - Step2(outline)를 1순위 단일 진실(Single Source of Truth)로 사용
    - Step1은 anchors/guardrails/background 근거 제공자
    - 출력 끝에 self_check JSON을 별도 블록으로 강제(파싱 가능)
    """
    # 메타 기본값
    reference = meta_data.get("reference") or meta_data.get("bible_range") or meta_data.get("scripture") or ""
    title = meta_data.get("title") or meta_data.get("sermon_title") or ""
    target = meta_data.get("target") or meta_data.get("audience") or ""
    service_type = meta_data.get("service_type") or meta_data.get("worship_type") or ""
    duration_min = meta_data.get("duration_min") or meta_data.get("duration") or ""
    special_notes = meta_data.get("special_notes") or meta_data.get("notes") or ""

    # 스타일 가이드 텍스트 (json_guide에서 추출)
    style_guide_text = ""
    if json_guide and isinstance(json_guide, dict):
        style_guide_text = (
            json_guide.get("step3_style_guide", "")
            or json_guide.get("style_guide", "")
            or ""
        )

    # Step1 최소화 (근거용 - 토큰 절약)
    step1_min = _minimize_step1_for_step3(step1_result or {})

    # Step2는 설계서이므로 가급적 전체 전달
    step2_outline = step2_result or {}

    # Step3 프롬프트 템플릿
    user_prompt = f"""\
당신은 설교 STEP3(원고 작성) 담당자입니다.
아래 입력(JSON)을 근거로 설교 원고를 작성하세요.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
[작성 설정]
- 본문: {reference}
- 설교 제목(사용자/Step2 우선): {title}
- 예배/집회 유형: {service_type}
- 대상: {target}
- 목표 분량(분): {duration_min}
- 특별 참고: {special_notes}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
[우선순위(중요)]
1) STEP2(outline JSON) = 단일 진실(Single Source of Truth)
   - 대지/소대지 구조, passage_anchors(anchor_id), supporting_verses(정확히 2개), 배경 참조(background_support)를 그대로 따른다.
2) STEP1(research JSON) = 근거 데이터
   - anchors(A*), guardrails(D* 포함), 역사/지리(H*/G*)는 "근거"로만 사용한다.
3) 위 둘과 충돌하는 내용은 작성 금지.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
[절대 규칙]
- 각 소대지는 STEP2에 지정된 passage_anchors(anchor_id) 2개 이상을 반드시 '내용 근거'로 반영한다.
- 각 소대지는 STEP2에 지정된 supporting_verses 2개를 그대로 인용한다(추가/변경 금지).
- STEP1 guardrails.does_not_claim(D*)에 해당하는 주장/해석은 금지한다(위반 시 스스로 수정).
- 시사 뉴스/통계/부동산/정치 등 변동·논쟁 정보는 사용하지 않는다(사용자가 명시했을 때만 예외).
- 설교문은 한국어로만 작성한다.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
[가독성 필수 지침]
- 한 문장은 최대 2줄
- 핵심은 짧게 끊어 쓰기
- 단락 사이 줄바꿈
- 성경 인용 형식(필수): 아래처럼 '본문 표기 줄' 다음에 '구절 내용'을 쓴다.

(줄바꿈)
요3:16
하나님이 세상을 이처럼 사랑하사...
(줄바꿈)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
[원고 출력 구조(필수)]
1) 제목
2) 서론
3) 1대지
   - 1-1, 1-2 (각 소대지: 근거→인용→짧은 적용→연결문장)
4) 2대지
   - 2-1, 2-2
5) 3대지(클라이맥스)
   - 3-1, 3-2
6) 결론
   - 요약 3문장(대지별 1문장)
   - 결단 질문 2개
   - 기도 제목 2개
   - 축복 문장 1개

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
[스타일 가이드(있으면 표현에만 적용)]
{style_guide_text}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
[입력 데이터: STEP2(outline)]
{_j(step2_outline)}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
[입력 데이터: STEP1(research, minimized)]
{_j(step1_min)}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
[출력 끝에 self_check JSON을 반드시 추가]
원고 맨 끝에 아래 구분자를 붙이고, 그 아래에 JSON만 출력하세요.

===SELF_CHECK_JSON===
{{
  "anchors_used": true,
  "supporting_verses_exactly_two_each_subpoint": true,
  "does_not_claim_violations": [],
  "no_current_affairs_used": true,
  "duration_respected": true,
  "readability_rules_followed": true
}}
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

    # section별 허용 절 범위 정의
    section_verse_ranges = {
        "section_1": (1, 2),  # 1-2절
        "section_2": (3, 5),  # 3-5절
        "section_3": (6, 7),  # 6-7절
    }

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

            # supporting_verses 검증 (정확히 2개)
            sup_verses = sub.get("supporting_verses") or []
            if len(sup_verses) != 2:
                errors.append(f"{section_key}.{sub_key}: supporting_verses가 정확히 2개 필요 (현재 {len(sup_verses)}개)")

            # background_support 검증
            bg_support = sub.get("background_support") or sub.get("background_ids") or []
            if len(bg_support) < 1:
                errors.append(f"{section_key}.{sub_key}: background_support가 1개 이상 필요 (현재 {len(bg_support)}개)")
            else:
                for b in bg_support:
                    b_str = str(b)
                    # Step1 존재 검증
                    if step1_result:
                        if b_str.startswith("H") and b_str not in valid_h_ids:
                            errors.append(f"{section_key}.{sub_key}: '{b}'가 Step1에 없음")
                        elif b_str.startswith("G") and b_str not in valid_g_ids:
                            errors.append(f"{section_key}.{sub_key}: '{b}'가 Step1에 없음")
                        elif b_str.startswith("P") and b_str not in valid_p_ids:
                            errors.append(f"{section_key}.{sub_key}: '{b}'가 Step1에 없음")
                        elif not any(b_str.startswith(p) for p in ("H", "G", "P")):
                            warnings.append(f"{section_key}.{sub_key}: '{b}'는 H*/G*/P* 형식이 아님")

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
