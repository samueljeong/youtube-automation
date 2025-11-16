import os
import re
import json
from flask import Flask, render_template, request, jsonify
from openai import OpenAI

app = Flask(__name__)

def get_client():
    key = (os.getenv("OPENAI_API_KEY") or "").strip()
    if not key:
        raise RuntimeError("OPENAI_API_KEY가 비어 있습니다.")
    return OpenAI(api_key=key)

client = get_client()

def format_json_result(json_data, indent=0):
    """JSON 데이터를 보기 좋은 텍스트 형식으로 변환 (재귀적 처리)"""
    result = []
    indent_str = "  " * indent

    # JSON의 각 키-값 쌍을 보기 좋게 포맷팅
    for key, value in json_data.items():
        # 키를 한국어로 변환 (필요시)
        key_display = key.replace('_', ' ').title()

        # 값이 리스트인 경우
        if isinstance(value, list):
            result.append(f"{indent_str}【 {key_display} 】")
            for item in value:
                if isinstance(item, dict):
                    # 리스트 안의 딕셔너리 재귀 처리
                    for sub_line in format_json_result(item, indent + 1).split('\n'):
                        if sub_line.strip():
                            result.append(f"  {indent_str}{sub_line}")
                else:
                    result.append(f"{indent_str}  - {item}")
            if indent == 0:
                result.append("")
        # 값이 딕셔너리인 경우 (재귀 처리)
        elif isinstance(value, dict):
            result.append(f"{indent_str}【 {key_display} 】")
            # 중첩 딕셔너리를 재귀적으로 처리
            for sub_key, sub_value in value.items():
                sub_key_display = sub_key.replace('_', ' ')
                if isinstance(sub_value, dict):
                    # 더 깊은 중첩 딕셔너리
                    result.append(f"{indent_str}  {sub_key_display}:")
                    for nested_line in format_json_result(sub_value, indent + 2).split('\n'):
                        if nested_line.strip() and not nested_line.strip().startswith('【'):
                            result.append(f"  {nested_line}")
                        elif nested_line.strip().startswith('【'):
                            # 섹션 헤더는 건너뛰기
                            pass
                elif isinstance(sub_value, list):
                    result.append(f"{indent_str}  {sub_key_display}:")
                    for item in sub_value:
                        result.append(f"{indent_str}    - {item}")
                else:
                    result.append(f"{indent_str}  {sub_key_display}: {sub_value}")
            if indent == 0:
                result.append("")
        # 값이 문자열 또는 기타인 경우
        else:
            result.append(f"{indent_str}【 {key_display} 】")
            result.append(f"{indent_str}{str(value)}")
            if indent == 0:
                result.append("")

    return "\n".join(result).strip()

def remove_markdown(text):
    """마크다운 기호 제거 (#, *, -, **, ###, 등)"""
    # 헤더 제거 (##, ###, #### 등)
    text = re.sub(r'^#+\s+', '', text, flags=re.MULTILINE)

    # 볼드 제거 (**, __)
    text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)
    text = re.sub(r'__(.+?)__', r'\1', text)

    # 이탤릭 제거 (*, _)
    text = re.sub(r'\*(.+?)\*', r'\1', text)
    text = re.sub(r'_(.+?)_', r'\1', text)

    # 리스트 마커 제거 (-, *, +)
    text = re.sub(r'^\s*[-*+]\s+', '', text, flags=re.MULTILINE)

    # 코드 블록 제거 (```)
    text = re.sub(r'```[\s\S]*?```', '', text)

    # 인라인 코드 제거 (`)
    text = re.sub(r'`(.+?)`', r'\1', text)

    return text.strip()

def get_system_prompt_for_step(step_name):
    """
    단계별로 최적화된 system prompt 반환
    mini는 개요와 자료만 생성, 설교문 작성 금지
    JSON 형식으로 응답
    """
    step_lower = step_name.lower()

    # 제목 추천 단계
    if '제목' in step_name:
        return """당신은 gpt-4o-mini로서 설교 '제목 후보'만 제안하는 역할입니다.

CRITICAL RULES:
1. 정확히 3개의 제목만 제시하세요
2. 각 제목은 한 줄로 작성하세요
3. 번호, 기호, 마크다운 사용 금지
4. 제목만 작성하고 설명 추가 금지

출력 형식 예시:
하나님의 약속을 믿는 믿음
약속의 땅을 향한 여정
아브라함의 신앙 결단

⚠️ 중요: 사용자가 제공하는 세부 지침이 있다면 위 규칙보다 우선하여 반드시 따르세요."""

    # 본문 분석 / 연구 단계
    elif '분석' in step_name or '연구' in step_name or '배경' in step_name:
        return f"""당신은 gpt-4o-mini로서 설교 '초안 자료'만 준비하는 역할입니다.

현재 단계: {step_name}

CRITICAL RULES:
1. 객관적인 성경 연구 자료만 제공하세요
2. 반드시 JSON 형식으로 응답하세요
3. 설교문 형식으로 작성하지 마세요
4. 감동적인 표현이나 적용 내용 금지
5. 순수한 연구 자료만 제공

응답은 반드시 다음 JSON 형식을 따르세요:
{{
  "background": "시대적/지리적/문화적 배경",
  "context_before": "본문 이전 맥락",
  "context_after": "본문 이후 맥락",
  "characters": "등장인물과 역할",
  "key_words": "핵심 단어 분석",
  "structure": "본문 구조 분석",
  "cross_references": "관련 성경구절",
  "theological_themes": "신학적 주제",
  "summary": "본문 요약"
}}

JSON만 출력하고 추가 설명은 하지 마세요.

⚠️ 중요: 사용자가 제공하는 세부 지침이 있다면 위 규칙보다 우선하여 반드시 따르세요. 지침에서 요구하는 항목, 형식, 내용 깊이를 정확히 반영하세요."""

    # 개요 / 구조 단계
    elif '개요' in step_name or '구조' in step_name or 'outline' in step_lower:
        return f"""당신은 gpt-4o-mini로서 설교 '개요'만 작성하는 역할입니다.

현재 단계: {step_name}

CRITICAL RULES:
1. 설교의 뼈대만 제시하세요
2. 반드시 JSON 형식으로 응답하세요
3. 문단 형태의 설교문은 절대 작성하지 마세요
4. 구조와 주제 문장만 제시하세요

응답은 반드시 다음 JSON 형식을 따르세요:
{{
  "big_idea": "한 문장으로 핵심 메시지",
  "intro_points": ["서론 포인트 1", "서론 포인트 2"],
  "point1": {{
    "title": "1대지 주제 문장",
    "sub_points": ["소대지 1", "소대지 2"]
  }},
  "point2": {{
    "title": "2대지 주제 문장",
    "sub_points": ["소대지 1", "소대지 2"]
  }},
  "point3": {{
    "title": "3대지 주제 문장",
    "sub_points": ["소대지 1", "소대지 2"]
  }},
  "conclusion_direction": "결론 방향 키워드"
}}

JSON만 출력하고 추가 설명은 하지 마세요.

⚠️ 중요: 사용자가 제공하는 세부 지침이 있다면 위 규칙보다 우선하여 반드시 따르세요. 지침에서 요구하는 구조, 항목 수, 형식을 정확히 반영하세요."""

    # 설교문 작성이 의심되는 단계 (경고)
    elif any(word in step_name for word in ['서론', '본론', '결론', '적용', '설교문']):
        return f"""당신은 gpt-4o-mini로서 설교 '자료'만 준비하는 역할입니다.

⚠️ 중요: 완성된 설교 문단은 작성하지 마세요!

현재 단계: {step_name}

CRITICAL RULES:
1. 이 단계는 GPT-5.1에서 최종 작성될 부분입니다
2. 당신은 자료와 포인트만 제공하세요
3. 반드시 JSON 형식으로 응답하세요
4. 자연스러운 설교 문장 작성 금지
5. 감동적인 표현 금지

응답은 반드시 다음 JSON 형식을 따르세요:
{{
  "core_message": "핵심 메시지 (한 문장)",
  "key_points": ["포인트 1", "포인트 2", "포인트 3"],
  "scripture_references": ["구절 1", "구절 2"],
  "emphasis": ["강조할 내용 1", "강조할 내용 2"]
}}

JSON만 출력하고 추가 설명은 하지 마세요.

⚠️ 중요: 사용자가 제공하는 세부 지침이 있다면 위 규칙보다 우선하여 반드시 따르세요. 지침의 요구사항을 정확히 반영하세요."""

    # 기타 단계
    else:
        return f"""당신은 gpt-4o-mini로서 설교 '초안 자료'만 준비하는 역할입니다.

현재 단계: {step_name}

CRITICAL RULES:
1. 자료와 정보만 제공하세요
2. 완성된 설교문은 작성하지 마세요
3. 반드시 JSON 형식으로 응답하세요
4. 객관적 내용만 제시하세요

응답은 반드시 다음 JSON 형식을 따르세요:
{{
  "content": "자료 내용",
  "points": ["포인트 1", "포인트 2"],
  "references": ["참고 사항"]
}}

JSON만 출력하고 추가 설명은 하지 마세요.

⚠️ 중요: 사용자가 제공하는 세부 지침이 있다면 위 규칙보다 우선하여 반드시 따르세요. 지침의 요구사항을 정확히 반영하세요."""

@app.route("/")
def home():
    return render_template("sermon.html")

@app.route("/sermon")
def sermon():
    return render_template("sermon.html")

@app.route("/health")
def health():
    return jsonify({"ok": True})

# ===== 처리 단계 실행 API (gpt-4o-mini) =====
@app.route("/api/sermon/process", methods=["POST"])
def api_process_step():
    """단일 처리 단계 실행 (gpt-4o-mini 사용)"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"ok": False, "error": "No data received"}), 400
        
        category = data.get("category", "")
        step_id = data.get("stepId", "")
        step_name = data.get("stepName", "")
        reference = data.get("reference", "")
        title = data.get("title", "")
        text = data.get("text", "")
        guide = data.get("guide", "")
        master_guide = data.get("masterGuide", "")
        previous_results = data.get("previousResults", {})
        
        print(f"[PROCESS] {category} - {step_name}")
        
        # 시스템 메시지 구성 (단계별 최적화)
        system_content = get_system_prompt_for_step(step_name)
        
        # 총괄 지침이 있으면 추가
        if master_guide:
            system_content += f"\n\n【 카테고리 총괄 지침 】\n{master_guide}\n\n"
            system_content += f"【 현재 단계 역할 】\n{step_name}\n\n"
            system_content += "위 총괄 지침을 참고하여, 현재 단계의 역할과 비중에 맞게 '자료만' 작성하세요."
        
        # 사용자 메시지 구성
        user_content = f"[성경구절]\n{reference}\n\n"
        
        # 제목이 있으면 추가 (제목 추천 단계가 아닐 때만)
        if title and '제목' not in step_name:
            user_content += f"[설교 제목]\n{title}\n\n"
            user_content += "위 제목을 염두에 두고 모든 내용을 작성해주세요.\n\n"
        
        if text:
            user_content += f"[성경 본문]\n{text}\n\n"
        
        # 이전 단계 결과 추가
        if previous_results:
            user_content += "[이전 단계 결과 (참고용)]\n"
            for prev_id, prev_data in previous_results.items():
                user_content += f"\n### {prev_data['name']}\n{prev_data['result']}\n"
            user_content += "\n"
        
        # 제목 추천 단계 특별 처리
        if '제목' in step_name:
            if guide:
                user_content += f"\n⚠️⚠️⚠️ 중요 지침 ⚠️⚠️⚠️\n"
                user_content += f"아래 지침을 반드시 따라야 합니다:\n"
                user_content += f"{guide}\n"
                user_content += f"{'='*50}\n\n"
            user_content += f"위 성경 본문({reference})에 적합한 설교 제목을 정확히 3개만 제안해주세요.\n"
            user_content += "각 제목은 한 줄로, 번호나 기호 없이 작성하세요."
        else:
            # 현재 단계 지침 강조
            if guide:
                user_content += f"\n⚠️⚠️⚠️ 중요 지침 ⚠️⚠️⚠️\n"
                user_content += f"아래 지침을 기본 규칙보다 우선하여 반드시 따라야 합니다:\n"
                user_content += f"{guide}\n"
                user_content += f"{'='*50}\n\n"

            user_content += f"위 내용을 바탕으로 '{step_name}' 단계를 작성해주세요.\n"
            if not guide:
                user_content += "⚠️ 중요: 완성된 설교 문단이 아닌, 자료와 구조만 제공하세요.\n"

        if title and '제목' not in step_name:
            user_content += f"\n제목 '{title}'을 고려하여 작성하세요."
        
        # GPT 호출 (gpt-4o-mini)
        completion = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": system_content
                },
                {
                    "role": "user",
                    "content": user_content
                }
            ],
            temperature=0.7,
            response_format={"type": "json_object"} if '제목' not in step_name else None,
        )

        result = completion.choices[0].message.content.strip()

        # 제목 추천 단계는 JSON 파싱하지 않고 그대로 반환
        if '제목' in step_name:
            result = remove_markdown(result)
            return jsonify({"ok": True, "result": result})

        # JSON 파싱 시도
        try:
            # JSON 코드 블록 제거 (```json ... ``` 형태)
            cleaned_result = result
            if cleaned_result.startswith('```'):
                # ```json 또는 ``` 로 시작하는 경우
                lines = cleaned_result.split('\n')
                # 첫 줄과 마지막 줄 제거
                if lines[0].startswith('```'):
                    lines = lines[1:]
                if lines and lines[-1].startswith('```'):
                    lines = lines[:-1]
                cleaned_result = '\n'.join(lines).strip()

            # JSON 파싱
            json_data = json.loads(cleaned_result)

            # JSON을 보기 좋은 텍스트로 변환
            formatted_result = format_json_result(json_data)

            print(f"[PROCESS][SUCCESS] JSON 파싱 성공")
            return jsonify({"ok": True, "result": formatted_result})

        except json.JSONDecodeError as je:
            # JSON 파싱 실패 시 원본 텍스트를 마크다운 제거하여 반환
            print(f"[PROCESS][WARNING] JSON 파싱 실패: {str(je)}")
            print(f"[PROCESS][WARNING] 원본 결과: {result[:200]}...")
            result = remove_markdown(result)
            return jsonify({"ok": True, "result": result, "warning": "JSON 형식이 아닌 결과가 반환되었습니다."})
        
    except Exception as e:
        print(f"[PROCESS][ERROR] {str(e)}")
        return jsonify({"ok": False, "error": str(e)}), 200


# ===== GPT PRO 처리 API (gpt-5.1) =====
@app.route("/api/sermon/gpt-pro", methods=["POST"])
def api_gpt_pro():
    """GPT-5.1 완성본 작성"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"ok": False, "error": "No data received"}), 400

        reference = data.get("reference", "")
        title = data.get("title", "")
        series_name = data.get("seriesName", "")
        style_name = data.get("styleName", "")
        category = data.get("category", "")
        draft_content = data.get("draftContent", "")
        style_description = data.get("styleDescription", "")

        print(f"[GPT-PRO] 처리 시작 - 스타일: {style_name}")

        # GPT-5.1 시스템 프롬프트 (스타일 동적 적용)
        system_content = (
            "당신은 GPT-5.1 기반의 한국어 설교 전문가입니다."
            " 자료는 참고용으로만 활용하고 문장은 처음부터 새로 구성하며,"
            " 묵직하고 명료한 어조로 신학적 통찰과 실제적 적용을 균형 있게 제시하세요."
            " 마크다운 기호 대신 순수 텍스트만 사용합니다."
        )

        # 사용자 메시지 구성
        meta_lines = []
        if category:
            meta_lines.append(f"- 카테고리: {category}")
        if style_name:
            meta_lines.append(f"- 설교 스타일: {style_name}")
        if style_description:
            meta_lines.append(f"- 스타일 설명: {style_description}")
        if reference:
            meta_lines.append(f"- 본문 성경구절: {reference}")
        if title:
            meta_lines.append(f"- 설교 제목: {title}")
        if series_name:
            meta_lines.append(f"- 시리즈명: {series_name}")

        meta_section = "\n".join(meta_lines)

        user_content = (
            "아래는 gpt-4o-mini가 정리한 연구·개요 자료입니다."
            " 참고만 하고, 문장은 처음부터 새로 작성해주세요."
        )
        if meta_section:
            user_content += f"\n\n[기본 정보]\n{meta_section}"
        user_content += "\n\n[설교 초안 자료]\n"
        user_content += draft_content

        # 설교 스타일별 요청 사항 결정
        user_content += "\n\n【요청 사항】\n"

        # 하몽서클 관련 스타일인지 확인
        is_harmonic_circle = any(keyword in style_name.lower() for keyword in ['하몽', 'harmonic'])

        # 3대지 관련 스타일인지 확인
        is_three_point = any(keyword in style_name.lower() for keyword in ['3대지', '주제', 'topical', '강해'])

        if is_harmonic_circle:
            # 하몽서클 스타일
            user_content += (
                "1. 하몽서클 5단계(Setup, Conflict, Turning Point, Realization, Call to Action)를 차례대로 구분해 주세요.\n"
                "   - 각 단계 제목은 영어-한국어 병기 형태로 표기합니다 (예: Setup — 서론).\n"
                "2. 각 단계마다 관련 배경 설명과 함께 적용을 제공하고, 반드시 보충 성경구절 2개를 인용구 형태로 제시하세요.\n"
                "3. 역사적 배경, 스토리텔링, 오늘의 적용을 골고루 담아 묵직하고 명확한 메시지를 만드세요.\n"
                "4. 결단(Call to Action) 단계에서는 이번 주 실천과 공동체 기도제목을 명확히 정리하세요.\n"
                "5. 마지막에 짧은 마무리 기도문과 축복 선언을 덧붙이세요.\n"
                "6. 마크다운, 불릿 기호 대신 순수 텍스트 단락과 번호를 사용하고, 중복되는 문장은 피하세요."
            )
        elif is_three_point:
            # 3대지 설교 스타일
            user_content += (
                "1. 3대지 구조로 설교문을 작성하세요:\n"
                "   - 서론: 본문 배경과 주요 메시지 소개\n"
                "   - 1대지, 2대지, 3대지: 각 대지마다 선포형 제목과 2개의 소대지 포함\n"
                "   - 결론: 실천과 적용\n"
                "2. 각 대지마다:\n"
                "   - 명확한 주제 문장으로 시작\n"
                "   - 소대지 2개를 포함하여 주제를 전개\n"
                "   - 관련 성경구절 2개를 인용구 형태로 제시\n"
                "   - 역사적 배경과 오늘의 적용을 연결\n"
                "3. 결론에서는 이번 주 실천 사항과 기도 제목을 제시하세요.\n"
                "4. 마크다운, 불릿 기호 대신 순수 텍스트 단락과 번호를 사용하고, 중복되는 문장은 피하세요."
            )
        else:
            # 기본 설교 스타일
            user_content += (
                "1. 제공된 설교 스타일에 맞춰 설교문을 작성하세요.\n"
                "2. 서론, 본론, 결론 구조를 명확히 하세요.\n"
                "3. 본론에서 핵심 메시지를 전개하고, 관련 성경구절을 인용하세요.\n"
                "4. 역사적 배경, 신학적 통찰, 실제 적용을 균형 있게 제시하세요.\n"
                "5. 결론에서는 실천 사항과 기도 제목을 제시하세요.\n"
                "6. 마크다운, 불릿 기호 대신 순수 텍스트 단락과 번호를 사용하고, 중복되는 문장은 피하세요."
            )

        # 최신 Responses API (gpt-5.1) 호출
        completion = client.responses.create(
            model="gpt-5.1",
            input=[
                {
                    "role": "system",
                    "content": [
                        {
                            "type": "input_text",
                            "text": system_content
                        }
                    ]
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "input_text",
                            "text": user_content
                        }
                    ]
                }
            ],
            temperature=0.8,
            max_output_tokens=8000  # 더 긴 설교문을 위해 토큰 증가
        )

        if getattr(completion, "output_text", None):
            result = completion.output_text.strip()
        else:
            text_chunks = []
            for item in getattr(completion, "output", []) or []:
                for content in getattr(item, "content", []) or []:
                    if getattr(content, "type", "") == "text":
                        text_chunks.append(getattr(content, "text", ""))
            result = "\n".join(text_chunks).strip()

        if not result:
            raise RuntimeError("GPT-5.1 API로부터 결과를 받지 못했습니다.")

        # 결과 앞에 본문과 제목 추가 (제목이 있을 때만)
        final_result = ""

        # 제목 추가 (사용자가 선택한 제목이 있을 때만)
        if title and title.strip():
            final_result += f"설교 제목: {title}\n"

        # 본문 추가
        if reference:
            final_result += f"본문: {reference}\n"

        # 제목이나 본문이 있으면 구분선 추가
        if title or reference:
            final_result += "\n" + "="*50 + "\n\n"

        final_result += result

        print(f"[GPT-PRO] 완료")

        return jsonify({"ok": True, "result": final_result})

    except Exception as e:
        print(f"[GPT-PRO][ERROR] {str(e)}")
        return jsonify({"ok": False, "error": str(e)}), 200


# ===== Render 배포를 위한 설정 =====
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5058))
    app.run(host="0.0.0.0", port=port, debug=False)
