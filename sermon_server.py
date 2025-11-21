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
    # GPT-5 긴 처리 시간을 위한 타임아웃 설정 (10분)
    return OpenAI(api_key=key, timeout=600.0)

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
    단계별 기본 system prompt 반환
    사용자의 guide를 최우선으로 따르도록 설계
    """
    step_lower = step_name.lower()

    # 제목 추천 단계
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

    # 모든 다른 단계 - 기본 역할만 명시
    else:
        return f"""당신은 설교 '초안 자료'만 준비하는 역할입니다.

현재 단계: {step_name}

기본 역할:
- 반드시 한국어로만 응답하세요
- 완성된 설교 문단이 아닌, 자료와 구조만 제공
- 사용자가 제공하는 세부 지침을 최우선으로 따름
- 지침이 없는 경우에만 일반적인 설교 자료 형식 사용

⚠️ 중요: 사용자의 세부 지침이 제공되면 그것을 절대적으로 우선하여 따라야 합니다."""

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
        step_type = data.get("stepType", "step1")
        reference = data.get("reference", "")
        title = data.get("title", "")
        text = data.get("text", "")
        guide = data.get("guide", "")
        master_guide = data.get("masterGuide", "")
        previous_results = data.get("previousResults", {})

        # stepType 기반 모델 선택
        if step_type == "step1":
            model_name = "gpt-5"
            use_temperature = False
        else:  # step2
            model_name = "gpt-4o-mini"
            use_temperature = True

        print(f"[PROCESS] {category} - {step_name} (Step: {step_type}, 모델: {model_name})")

        # 시스템 메시지 구성 (단계별 최적화)
        system_content = get_system_prompt_for_step(step_name)

        # 총괄 지침이 있으면 추가
        if master_guide:
            system_content += f"\n\n【 카테고리 총괄 지침 】\n{master_guide}\n\n"
            system_content += f"【 현재 단계 역할 】\n{step_name}\n\n"
            system_content += "위 총괄 지침을 참고하여, 현재 단계의 역할과 비중에 맞게 '자료만' 작성하세요."

        # ★ 중요: 단계별 세부 지침을 시스템 프롬프트에 포함 (최우선 지침)
        if guide:
            system_content += f"\n\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            system_content += f"【 최우선 지침: {step_name} 단계 세부 지침 】\n"
            system_content += f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            system_content += guide
            system_content += f"\n\n위 지침을 절대적으로 우선하여 따라야 합니다."
            system_content += f"\n이 지침이 기본 역할과 충돌하면, 이 지침을 따르세요."

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
            user_content += f"위 성경 본문({reference})에 적합한 설교 제목을 정확히 3개만 제안해주세요.\n"
            user_content += "각 제목은 한 줄로, 번호나 기호 없이 작성하세요."
        else:
            user_content += f"위 내용을 바탕으로 '{step_name}' 단계를 작성해주세요.\n"

        if title and '제목' not in step_name:
            user_content += f"\n제목 '{title}'을 고려하여 작성하세요."

        # GPT 호출 (모델 동적 선택)
        # JSON 형식 강제하지 않음 - guide에 따라 자유롭게 출력
        if use_temperature:
            completion = client.chat.completions.create(
                model=model_name,
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
            )
        else:
            completion = client.chat.completions.create(
                model=model_name,
                messages=[
                    {
                        "role": "system",
                        "content": system_content
                    },
                    {
                        "role": "user",
                        "content": user_content
                    }
                ]
            )

        result = completion.choices[0].message.content.strip()

        # 제목 추천 단계는 JSON 파싱하지 않고 그대로 반환
        if '제목' in step_name:
            result = remove_markdown(result)
            return jsonify({"ok": True, "result": result})

        # JSON 파싱 시도 (선택적)
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

            print(f"[PROCESS][SUCCESS] JSON 형식으로 응답받아 포맷팅 완료")
            return jsonify({"ok": True, "result": formatted_result})

        except json.JSONDecodeError as je:
            # JSON 파싱 실패 시 원본 텍스트를 반환 (정상 처리)
            # guide에서 텍스트 형식을 요구했을 수 있으므로 오류가 아님
            print(f"[PROCESS][INFO] 텍스트 형식으로 응답받음 (JSON 아님)")
            result = remove_markdown(result)
            return jsonify({"ok": True, "result": result})
        
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
        completed_step_names = data.get("completedStepNames", [])

        print(f"[GPT-PRO] 처리 시작 - 스타일: {style_name}")

        # 제목 생성 여부 확인
        has_title = bool(title and title.strip())

        # GPT-5.1 시스템 프롬프트 (스타일 동적 적용)
        system_content = (
            "당신은 GPT-5.1 기반의 한국어 설교 전문가입니다."
            " 자료는 참고용으로만 활용하고 문장은 처음부터 새로 구성하며,"
            " 묵직하고 명료한 어조로 신학적 통찰과 실제적 적용을 균형 있게 제시하세요."
            " 마크다운 기호 대신 순수 텍스트만 사용합니다."
        )

        # 제목이 없으면 GPT가 생성하도록 지시
        if not has_title:
            system_content += (
                "\n\n⚠️ 제목 생성: 설교문 맨 앞에 '설교 제목: (제목 내용)' 형식으로 적절한 제목을 먼저 생성하세요."
                "\n그 다음 빈 줄을 넣고 바로 설교 내용(서론, 본론, 결론)을 시작하세요. 본문 성경구절은 출력하지 마세요."
            )
        else:
            system_content += "\n\n⚠️ 중요: 설교 제목과 본문 성경구절은 다시 출력하지 마세요. 바로 설교 내용(서론, 본론, 결론)부터 시작하세요."

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
                "6. 가독성을 위해 각 단계 사이에 빈 줄을 넣으세요.\n"
                "7. 마크다운, 불릿 기호 대신 순수 텍스트 단락을 사용하고, 중복되는 문장은 피하세요."
            )
        elif is_three_point:
            # 3대지 설교 스타일
            user_content += (
                "1. 3대지 구조로 설교문을 작성하세요:\n"
                "   - 서론: 본문 배경과 주요 메시지 소개 (넘버링 없이 '서론'이라고만)\n"
                "   - 본론: 1대지, 2대지, 3대지 (각 대지는 '1.', '2.', '3.' 형식으로 넘버링)\n"
                "   - 결론: 실천과 적용 (넘버링 없이 '결론'이라고만)\n"
                "2. 각 대지 형식:\n"
                "   - 대지 제목: '1. 하나님의 말씀을 다시 붙들라' 형식으로 작성\n"
                "   - 소대지 2개를 포함하여 주제를 전개\n"
                "   - 관련 성경구절 2개를 인용구 형태로 제시\n"
                "   - 역사적 배경과 오늘의 적용을 연결\n"
                "3. 결론에서는 이번 주 실천 사항과 기도 제목을 제시하세요.\n"
                "4. 가독성을 위해 각 섹션(서론, 대지, 결론) 사이에 빈 줄을 넣으세요.\n"
                "5. 마크다운, 불릿 기호 대신 순수 텍스트 단락을 사용하고, 중복되는 문장은 피하세요."
            )
        else:
            # 기본 설교 스타일 - 처리 단계 구조 따르기
            user_content += "1. 제공된 설교 스타일에 맞춰 설교문을 작성하세요.\n"

            # 완료된 처리 단계 정보 활용
            if completed_step_names and len(completed_step_names) > 0:
                steps_list = "', '".join(completed_step_names)
                user_content += (
                    f"2. 위 초안 자료는 '{steps_list}' 단계로 구성되어 있습니다.\n"
                    "   이 단계들의 분석 내용과 구조를 반영하여 설교문을 전개하세요.\n"
                )
            else:
                user_content += "2. 초안 자료의 분석 내용과 구조를 반영하여 설교문을 전개하세요.\n"

            user_content += (
                "3. 핵심 메시지를 전개하고, 관련 성경구절을 적절히 인용하세요.\n"
                "4. 역사적 배경, 신학적 통찰, 실제 적용을 균형 있게 제시하세요.\n"
                "5. 결론 부분에서는 실천 사항과 기도 제목을 제시하세요.\n"
                "6. 가독성을 위해 각 섹션 사이에 빈 줄을 넣으세요.\n"
                "7. 마크다운, 불릿 기호 대신 순수 텍스트 단락을 사용하고, 중복되는 문장은 피하세요."
            )

        # 공통 지침 추가
        user_content += "\n\n⚠️ 중요: 충분히 길고 상세하며 풍성한 내용으로 작성해주세요 (최대 16000 토큰)."

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
            max_output_tokens=16000  # 더 긴 설교문을 위해 토큰 증가
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

        # 마크다운 제거
        result = remove_markdown(result)

        # 결과 앞에 제목과 본문 추가
        final_result = ""

        # 제목 처리
        if has_title:
            # 사용자가 입력한 제목 사용
            final_result += f"설교 제목: {title}\n\n"
            # 본문 추가
            if reference:
                final_result += f"본문: {reference}\n\n"
            # GPT 결과 (제목 없이)
            final_result += result
        else:
            # GPT가 생성한 제목 포함된 결과 그대로 사용
            # 본문만 추가
            if reference:
                # GPT 결과 앞에 본문 삽입
                final_result += f"본문: {reference}\n\n"
            final_result += result

        print(f"[GPT-PRO] 완료")

        return jsonify({"ok": True, "result": final_result})

    except Exception as e:
        print(f"[GPT-PRO][ERROR] {str(e)}")
        return jsonify({"ok": False, "error": str(e)}), 200


@app.route("/api/sermon/qa", methods=["POST"])
def api_sermon_qa():
    """설교 준비 Q&A - 처리 단계 결과와 본문을 기반으로 질문에 답변"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"ok": False, "error": "No data received"}), 400

        question = data.get("question", "")
        reference = data.get("reference", "")
        step_results = data.get("stepResults", {})

        if not question:
            return jsonify({"ok": False, "error": "질문이 비어있습니다"}), 400

        print(f"[Q&A] 질문: {question}")

        # 시스템 메시지: Q&A 역할 정의
        system_content = """당신은 설교 준비를 돕는 성경 연구 도우미입니다.

당신의 역할:
- 사용자가 현재 준비 중인 성경 본문과 관련된 질문에 답변합니다
- 제공된 처리 단계 결과(배경 지식, 본문 분석, 개요 등)를 참고하여 답변합니다
- 질문이 모호한 경우, 현재 맥락(성경 본문, 처리 단계)을 기준으로 이해하고 답변합니다
- 간단하고 명확하게 답변하되, 필요시 성경적 배경이나 신학적 설명을 추가합니다

답변 원칙:
- 친절하고 이해하기 쉬운 톤으로 작성
- 불확실한 경우 "정확하지 않을 수 있습니다"라고 명시
- 필요시 관련 성경 구절이나 역사적 배경 언급"""

        # 사용자 메시지: 컨텍스트 + 질문
        user_content = ""

        # 성경 본문 정보
        if reference:
            user_content += f"【 현재 준비 중인 성경 본문 】\n{reference}\n\n"

        # 처리 단계 결과들
        if step_results:
            user_content += "【 처리 단계 결과 】\n"
            for step_id, step_data in step_results.items():
                step_name = step_data.get("name", "")
                step_result = step_data.get("result", "")
                if step_result:
                    user_content += f"\n### {step_name}\n{step_result}\n"
            user_content += "\n"

        # 사용자 질문
        user_content += f"【 사용자 질문 】\n{question}\n\n"
        user_content += "위 맥락을 참고하여 질문에 답변해주세요."

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
            temperature=0.7
        )

        answer = completion.choices[0].message.content

        print(f"[Q&A] 답변 완료")

        return jsonify({"ok": True, "answer": answer})

    except Exception as e:
        print(f"[Q&A][ERROR] {str(e)}")
        return jsonify({"ok": False, "error": str(e)}), 200


# ===== Render 배포를 위한 설정 =====
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5058))
    app.run(host="0.0.0.0", port=port, debug=False)
