# sermon_server.py
import os
from flask import Flask, render_template, request, jsonify
from openai import OpenAI

app = Flask(__name__)

def get_client():
    key = (os.getenv("OPENAI_API_KEY") or "").strip()
    if not key:
        raise RuntimeError("OPENAI_API_KEY가 비어 있습니다.")
    return OpenAI(api_key=key)

client = get_client()

@app.route("/")
def home():
    return render_template("sermon.html")

@app.route("/sermon")
def sermon():
    return render_template("sermon.html")

@app.route("/health")
def health():
    return jsonify({"ok": True})

# ===== 통합 처리 엔드포인트 =====
@app.route("/api/sermon/process", methods=["POST"])
def api_sermon_process():
    """
    모든 처리 단계를 처리하는 통합 엔드포인트
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({"ok": False, "error": "No JSON data received"}), 400
        
        category = data.get("category", "")
        step_id = data.get("stepId", "")
        reference = data.get("reference", "")
        text = data.get("text", "")
        guide = data.get("guide", "")
        prompt_type = data.get("promptType", None)
        previous_results = data.get("previousResults", {})
        
        print(f"[PROCESS] category={category}, stepId={step_id}, promptType={prompt_type}")
        
        if not reference:
            return jsonify({"ok": False, "error": "성경 구절이 필요합니다."}), 400
        
        # 단계별 처리
        if step_id == "analysis":
            result = process_analysis(reference, text, guide, category, previous_results)
        elif step_id == "prompt":
            result = process_prompt(reference, text, guide, category, prompt_type, previous_results)
        else:
            # 커스텀 단계 (일반 처리)
            result = process_custom_step(step_id, reference, text, guide, category, previous_results)
        
        return jsonify({"ok": True, "result": result})
        
    except Exception as e:
        err_text = str(e)
        print(f"[PROCESS][ERROR] {err_text}")
        return jsonify({"ok": False, "error": err_text}), 200


def process_analysis(reference, text, guide, category, previous_results):
    """본문 분석 처리"""
    content = f"[성경 구절]\n{reference}\n\n[카테고리]\n{category}"
    
    if text:
        content += f"\n\n[본문 내용]\n{text}"
    
    if guide:
        content = f"[사용자 지침]\n{guide}\n\n{content}"
    
    content += "\n\n위 본문을 분석해주세요."
    
    completion = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "system",
                "content": "You help Korean pastors analyze Bible passages."
            },
            {
                "role": "user",
                "content": content
            }
        ],
        temperature=0.7,
    )
    
    return completion.choices[0].message.content.strip()


def process_prompt(reference, text, guide, category, prompt_type, previous_results):
    """설교문 프롬프트 생성 처리"""
    
    # 메타-프롬프트 구성
    content = f"""당신은 설교문 작성 프롬프트 전문가입니다.

아래 정보를 바탕으로, **다른 GPT 모델(예: ChatGPT Plus, Claude)에게 직접 입력할 수 있는 완성된 설교문 작성 프롬프트**를 만들어주세요.

---

📌 **설교 정보**
- 성경 구절: {reference}
- 카테고리: {category}
- 설교 유형: {prompt_type or '기본'}
"""

    if text:
        content += f"\n- 본문 내용:\n{text}\n"
    
    # 이전 단계 결과들 포함
    if previous_results:
        content += "\n📊 **이전 단계 결과**\n"
        for step_id, step_data in previous_results.items():
            content += f"\n[{step_data['name']}]\n{step_data['result']}\n"
        content += "\n⚠️ **중요**: 위의 이전 단계 결과들을 프롬프트에 반드시 포함시켜, GPT가 이를 바탕으로 설교문을 작성하도록 해주세요.\n"
    
    if guide:
        content += f"""
📘 **설교 제작 매뉴얼 (필수 준수)**
{guide}

⚠️ **중요**: 위 매뉴얼의 모든 지침을 프롬프트에 명확히 포함시켜주세요.
"""
    
    content += """

---

✅ **출력 형식**

아래와 같은 형식으로 **완성된 프롬프트**를 작성해주세요:
```
[GPT에게 입력할 프롬프트 시작]

당신은 한국 교회의 설교문 작성 전문가입니다.

[설교 정보와 매뉴얼을 통합하여 명확한 지시사항 작성]
[이전 단계 결과들을 포함]
[기대하는 설교문의 구조와 톤 명시]
[구체적인 작성 지침]

[GPT에게 입력할 프롬프트 끝]
```

**주의사항**:
1. 프롬프트는 복사-붙여넣기만 하면 바로 사용 가능해야 합니다
2. 설교문을 직접 작성하지 말고, "설교문을 작성하라"는 지시문을 만드세요
3. 매뉴얼의 모든 세부사항이 프롬프트에 포함되어야 합니다
4. 이전 단계의 모든 결과를 프롬프트에 통합하세요
"""

    completion = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "system",
                "content": "You are an expert at creating sermon writing prompts for other AI models. You create clear, detailed prompts that other GPTs can use to write excellent sermons. You NEVER write the sermon itself - you only create the prompt."
            },
            {
                "role": "user",
                "content": content
            }
        ],
        temperature=0.7,
    )
    
    return completion.choices[0].message.content.strip()


def process_custom_step(step_id, reference, text, guide, category, previous_results):
    """커스텀 단계 처리 (질문 생성, 토론 주제 등)"""
    
    # 단계 이름을 추론 (실제로는 프론트에서 보내주는 게 좋지만, 여기서는 간단히)
    step_names = {
        "questions": "성경공부 질문",
        "discussion": "토론 주제",
        "application": "실천 과제",
        "prayer": "기도 제목",
        "illustration": "예화",
        "outline": "설교 개요"
    }
    
    step_name = step_names.get(step_id, step_id)
    
    content = f"""[성경 구절]\n{reference}\n\n[카테고리]\n{category}"""
    
    if text:
        content += f"\n\n[본문 내용]\n{text}"
    
    # 이전 단계 결과들 포함
    if previous_results:
        content += "\n\n[이전 단계 결과]\n"
        for prev_step_id, step_data in previous_results.items():
            content += f"\n## {step_data['name']}\n{step_data['result']}\n"
    
    if guide:
        content = f"[사용자 지침]\n{guide}\n\n{content}"
    
    content += f"\n\n위 정보를 바탕으로 {step_name}을(를) 작성해주세요."
    
    completion = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "system",
                "content": f"You are a Korean church ministry expert helping to create {step_name}."
            },
            {
                "role": "user",
                "content": content
            }
        ],
        temperature=0.7,
    )
    
    return completion.choices[0].message.content.strip()


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5057))
    app.run(host="0.0.0.0", port=port, debug=False)
