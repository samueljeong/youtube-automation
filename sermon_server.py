import os
import re
from flask import Flask, render_template, request, jsonify
from openai import OpenAI

app = Flask(__name__)

def get_client():
    key = (os.getenv("OPENAI_API_KEY") or "").strip()
    if not key:
        raise RuntimeError("OPENAI_API_KEY가 비어 있습니다.")
    return OpenAI(api_key=key)

client = get_client()

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
아브라함의 신앙 결단"""
    
    # 본문 분석 / 연구 단계
    elif '분석' in step_name or '연구' in step_name or '배경' in step_name:
        return f"""당신은 gpt-4o-mini로서 설교 '초안 자료'만 준비하는 역할입니다.

현재 단계: {step_name}

CRITICAL RULES:
1. 객관적인 성경 연구 자료만 제공하세요
2. 다음 항목들을 포함하세요:
   - 시대적/지리적/문화적 배경
   - 핵심 단어 분석
   - 본문 구조 분석
   - 관련 성경구절 (Cross-reference)
   - 신학적 주제
3. 설교문 형식으로 작성하지 마세요
4. 감동적인 표현이나 적용 내용 금지
5. 마크다운 기호 사용 금지
6. 순수한 연구 자료만 제공"""
    
    # 개요 / 구조 단계
    elif '개요' in step_name or '구조' in step_name or 'outline' in step_lower:
        return f"""당신은 gpt-4o-mini로서 설교 '개요'만 작성하는 역할입니다.

현재 단계: {step_name}

CRITICAL RULES:
1. 설교의 뼈대만 제시하세요:
   - Big Idea (한 문장으로 핵심 메시지)
   - 서론 포인트 (키워드만)
   - 1대지 주제 문장
   - 1대지 소대지 (키워드만)
   - 2대지 주제 문장
   - 2대지 소대지 (키워드만)
   - 3대지 주제 문장
   - 3대지 소대지 (키워드만)
   - 결론 방향 (키워드만)
2. 문단 형태의 설교문은 절대 작성하지 마세요
3. 구조와 주제 문장만 제시하세요
4. 마크다운 기호 사용 금지"""
    
    # 설교문 작성이 의심되는 단계 (경고)
    elif any(word in step_name for word in ['서론', '본론', '결론', '적용', '설교문']):
        return f"""당신은 gpt-4o-mini로서 설교 '자료'만 준비하는 역할입니다.

⚠️ 중요: 완성된 설교 문단은 작성하지 마세요!

현재 단계: {step_name}

CRITICAL RULES:
1. 이 단계는 GPT-5.1에서 최종 작성될 부분입니다
2. 당신은 자료와 포인트만 제공하세요:
   - 핵심 메시지 (한 문장)
   - 주요 포인트 (키워드 나열)
   - 사용할 성경 구절 리스트
   - 강조할 내용 (키워드만)
3. 자연스러운 설교 문장 작성 금지
4. 감동적인 표현 금지
5. 마크다운 기호 사용 금지"""
    
    # 기타 단계
    else:
        return f"""당신은 gpt-4o-mini로서 설교 '초안 자료'만 준비하는 역할입니다.

현재 단계: {step_name}

CRITICAL RULES:
1. 자료와 정보만 제공하세요
2. 완성된 설교문은 작성하지 마세요
3. 객관적 내용만 제시하세요
4. 마크다운 기호 사용 금지"""

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
        
        # 현재 단계 지침 추가
        if guide:
            user_content += f"[{step_name} 단계 세부 지침]\n{guide}\n\n"
        
        # 제목 추천 단계 특별 처리
        if '제목' in step_name:
            user_content += f"위 성경 본문({reference})에 적합한 설교 제목을 정확히 3개만 제안해주세요.\n"
            user_content += "각 제목은 한 줄로, 번호나 기호 없이 작성하세요."
        else:
            user_content += f"위 내용을 바탕으로 '{step_name}' 단계를 작성해주세요.\n"
            user_content += "⚠️ 중요: 완성된 설교 문단이 아닌, 자료와 구조만 제공하세요."
        
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
        )
        
        result = completion.choices[0].message.content.strip()
        
        # 마크다운 기호 제거
        result = remove_markdown(result)
        
        return jsonify({"ok": True, "result": result})
        
    except Exception as e:
        print(f"[PROCESS][ERROR] {str(e)}")
        return jsonify({"ok": False, "error": str(e)}), 200


# ===== GPT PRO 처리 API (gpt-4o) =====
@app.route("/api/sermon/gpt-pro", methods=["POST"])
def api_gpt_pro():
    """GPT-5.1 (gpt-4o) 완성본 작성"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"ok": False, "error": "No data received"}), 400
        
        reference = data.get("reference", "")
        title = data.get("title", "")
        draft_content = data.get("draftContent", "")
        
        print(f"[GPT-PRO] 처리 시작")
        
        # GPT-5.1 시스템 프롬프트
        system_content = """당신은 gpt-4o로서 설교문 작성 전문가입니다.

당신의 역할:
1. gpt-4o-mini가 작성한 '초안 자료'를 참고하여 완성도 높은 설교문을 작성합니다
2. mini의 문장을 그대로 복사하지 말고, 자연스럽고 감동적인 설교문으로 재작성합니다
3. 청중과 소통하는 듯한 따뜻하고 진실된 어조로 작성합니다

작성 원칙:
- 초안의 구조와 핵심 메시지는 유지하되, 표현은 완전히 새롭게
- 적절한 예화와 실생활 적용을 추가
- 청중의 마음을 움직이는 감동적인 메시지
- 명확한 서론-본론-결론 구조
- 한국 교회 문화에 맞는 자연스러운 표현

중요: mini의 개요와 자료를 참고하되, 당신만의 언어로 처음부터 새로 작성하세요."""

        # 사용자 메시지 구성
        user_content = f"""다음은 gpt-4o-mini가 작성한 설교 초안 자료입니다.
이 자료를 참고하여 완성도 높은 설교문을 작성해주세요.

{draft_content}

====================================

위 초안 자료를 바탕으로, 청중의 마음을 움직이는 완성도 높은 설교문을 작성해주세요.
- 서론에서 청중의 관심을 끌고
- 본론에서 명확한 메시지를 전달하며
- 결론에서 실천 가능한 적용점을 제시해주세요.

초안의 구조는 따르되, 표현은 당신만의 언어로 완전히 새롭게 작성하세요."""

        # GPT 호출 (gpt-4o = GPT-5.1)
        completion = client.chat.completions.create(
            model="gpt-4o",
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
            temperature=0.8,
            max_tokens=4000
        )
        
        result = completion.choices[0].message.content.strip()
        
        print(f"[GPT-PRO] 완료")
        
        return jsonify({"ok": True, "result": result})
        
    except Exception as e:
        print(f"[GPT-PRO][ERROR] {str(e)}")
        return jsonify({"ok": False, "error": str(e)}), 200


# ===== Render 배포를 위한 설정 =====
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5058))
    app.run(host="0.0.0.0", port=port, debug=False)