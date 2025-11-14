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

@app.route("/")
def home():
    return render_template("sermon.html")

@app.route("/sermon")
def sermon():
    return render_template("sermon.html")

@app.route("/health")
def health():
    return jsonify({"ok": True})

# ===== 처리 단계 실행 API =====
@app.route("/api/sermon/process", methods=["POST"])
def api_process_step():
    """단일 처리 단계 실행"""
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
        
        # 시스템 메시지 구성
        system_content = """You are an assistant helping to create sermon materials in Korean.

CRITICAL FORMATTING RULES:
- DO NOT use markdown symbols (#, *, **, ###, etc.)
- DO NOT use bullet points with -, *, or +
- Write in plain text only
- Use simple line breaks and spacing for structure
- Use numbers (1, 2, 3) for lists if needed, but no symbols"""
        
        # 총괄 지침이 있으면 추가
        if master_guide:
            system_content += f"\n\n【 카테고리 총괄 지침 】\n{master_guide}\n\n"
            system_content += f"【 현재 단계 】\n- 단계명: {step_name}\n\n"
            system_content += "위 총괄 지침을 반드시 참고하여, 현재 단계의 역할과 비중에 맞게 작성하세요."
        
        # 사용자 메시지 구성
        user_content = f"[성경구절]\n{reference}\n\n"
        
        # 제목이 있으면 추가
        if title:
            user_content += f"[설교 제목]\n{title}\n\n"
            user_content += "위 제목을 염두에 두고 모든 내용을 작성해주세요.\n\n"
        
        if text:
            user_content += f"[성경 본문]\n{text}\n\n"
        
        # 이전 단계 결과 추가
        if previous_results:
            user_content += "[이전 단계 결과]\n"
            for prev_id, prev_data in previous_results.items():
                user_content += f"\n### {prev_data['name']}\n{prev_data['result']}\n"
            user_content += "\n"
        
        # 현재 단계 지침 추가
        if guide:
            user_content += f"[{step_name} 단계 지침]\n{guide}\n\n"
        
        user_content += f"위 내용을 바탕으로 '{step_name}' 단계를 작성해주세요."
        
        if title:
            user_content += f"\n\n제목 '{title}'을 고려하여 작성하세요."
        
        # GPT 호출
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


# ===== Render 배포를 위한 설정 =====
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5058))
    app.run(host="0.0.0.0", port=port, debug=False)
