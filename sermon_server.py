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
    key = (os.getenv("OPENAI_API_KEY") or "").strip()
    masked = f"{key[:3]}***{key[-3:]}" if len(key) >= 7 else "(none)"
    return jsonify({
        "ok": True,
        "key_present": bool(key),
        "key_masked": masked,
    })

@app.route("/api/sermon/analyze", methods=["POST"])
def api_sermon_analyze():
    data = request.json or {}
    guide = data.get("guide", "")
    bible_text = data.get("text", "")
    ref = data.get("reference", "")  # ← "reference"로 수정!
    category = data.get("category", "")

    print(f"[ANALYZE] ref={ref}, category={category}, text_len={len(bible_text)}, guide_len={len(guide)}")

    try:
        # 본문이 있으면 포함, 없으면 제외
        content = f"[지침]\n{guide}\n\n[카테고리]\n{category}\n\n[본문]\n{ref}"
        if bible_text:
            content += f"\n\n[본문 내용]\n{bible_text}"

        completion = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": "You help a Korean pastor analyze Bible passages. Always apply user's guide first."
                },
                {
                    "role": "user",
                    "content": content
                }
            ],
            temperature=0.7,
        )

        result_text = (completion.choices[0].message.content or "").strip()
        print(f"[ANALYZE] result length: {len(result_text)}")

        return jsonify({"ok": True, "result": result_text})

    except Exception as e:
        err_text = str(e)
        print(f"[ANALYZE][ERROR] {err_text}")
        return jsonify({"ok": False, "error": err_text}), 200

@app.route("/api/sermon/prompt", methods=["POST"])
def api_sermon_prompt():
    try:
        data = request.get_json()
        if not data:
            return jsonify({"ok": False, "error": "No JSON data received"}), 400
        
        guide = data.get("guide", "")
        ref = data.get("reference", "")
        category = data.get("category", "")
        bible_text = data.get("text", "")
        analysis = data.get("analysis", "")
        promptType = data.get("promptType", "기본")

        print(f"[PROMPT] ref={ref}, category={category}, promptType={promptType}")

        if not ref:
            return jsonify({"ok": False, "error": "성경 구절이 필요합니다."}), 400

        # 프롬프트 생성을 위한 메타-프롬프트 구성
        content = f"""당신은 설교문 작성 프롬프트 전문가입니다.

아래 정보를 바탕으로, **다른 GPT 모델(예: ChatGPT Plus, Claude)에게 직접 입력할 수 있는 완성된 설교문 작성 프롬프트**를 만들어주세요.

---

📌 **설교 정보**
- 성경 구절: {ref}
- 카테고리: {category}
- 설교 유형: {promptType}
"""

        if bible_text:
            content += f"\n- 본문 내용:\n{bible_text}\n"
        
        if analysis:
            content += f"""
📊 **본문 분석 결과**
{analysis}

⚠️ **중요**: 위의 본문 분석 결과를 프롬프트에 반드시 포함시켜, GPT가 이 분석을 바탕으로 설교문을 작성하도록 해주세요.
"""
        
        if guide:
            content += f"""
📘 **설교 제작 매뉴얼 (필수 준수)**
{guide}

⚠️ **중요**: 위 매뉴얼의 모든 지침(대상, 시간, 포맷, 톤, 구조 등)을 프롬프트에 명확히 포함시켜주세요.
"""
        
        content += """

---

✅ **출력 형식**

아래와 같은 형식으로 **완성된 프롬프트**를 작성해주세요:
```
[GPT에게 입력할 프롬프트 시작]

당신은 한국 교회의 설교문 작성 전문가입니다.

[설교 정보와 매뉴얼을 통합하여 명확한 지시사항 작성]
[본문 분석 결과를 포함]
[기대하는 설교문의 구조와 톤 명시]
[구체적인 작성 지침]

[GPT에게 입력할 프롬프트 끝]
```

**주의사항**:
1. 프롬프트는 복사-붙여넣기만 하면 바로 사용 가능해야 합니다
2. 설교문을 직접 작성하지 말고, "설교문을 작성하라"는 지시문을 만드세요
3. 매뉴얼의 모든 세부사항이 프롬프트에 포함되어야 합니다
4. 본문 분석 내용을 프롬프트에 통합하세요
"""

        completion = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system", 
                    "content": "You are an expert at creating sermon writing prompts for other AI models. You create clear, detailed prompts that other GPTs can use to write excellent sermons. You NEVER write the sermon itself - you only create the prompt."
                },
                {"role": "user", "content": content}
            ],
            temperature=0.7,
        )
        
        result = completion.choices[0].message.content
        print(f"[PROMPT] Success! Created prompt for other GPT models")
        return jsonify({"ok": True, "result": result})
        
    except Exception as e:
        err_text = str(e)
        print(f"[PROMPT][ERROR] {err_text}")
        return jsonify({"ok": False, "error": err_text}), 200
        
if __name__ == "__main__":
    import os
    app.run(host="127.0.0.1", port=int(os.environ.get("PORT", 5057)), debug=True)