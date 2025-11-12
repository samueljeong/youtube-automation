import os
from flask import Flask, render_template, request, jsonify
from openai import OpenAI

app = Flask(__name__)

def get_client():
    key = (os.getenv("OPENAI_API_KEY") or "").strip()
    if not key:
        raise RuntimeError("OPENAI_API_KEY가 비어 있습니다. Render 대시보드 > Environment에 추가하세요.")
    print(f"🔑 OPENAI_API_KEY length={len(key)}, prefix={(key[:6] if len(key)>=6 else key)}")
    return OpenAI(api_key=key)

client = get_client()

@app.route("/")
def home():
    return render_template("message.html")

@app.route("/message")
def message():
    return render_template("message.html")

# 헬스체크
@app.route("/health")
def health():
    key = (os.getenv("OPENAI_API_KEY") or "").strip()
    masked = f"{key[:3]}***{key[-3:]}" if len(key) >= 7 else "(none)"
    return jsonify({
        "ok": True,
        "key_present": bool(key),
        "key_len": len(key),
        "key_masked": masked,
    })

# 오전 메시지 생성
@app.route("/api/message/morning", methods=["POST"])
def api_morning_message():
    data = request.json or {}
    guide = data.get("guide", "")
    bible_text = data.get("text", "")
    ref = data.get("ref", "")
    date = data.get("date", "")

    print("[MORNING] payload =>", {
        "len_guide": len(guide),
        "len_text": len(bible_text),
        "ref": ref,
        "date": date,
    })

    try:
        completion = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": "You help create morning devotional messages in Korean."
                },
                {
                    "role": "user",
                    "content": f"[오전 지침]\n{guide}\n\n[날짜]\n{date}\n\n[본문]\n{ref}\n{bible_text}"
                }
            ],
            temperature=0.7,
        )

        result_text = (completion.choices[0].message.content or "").strip()
        print("[MORNING] result length =>", len(result_text))

        return jsonify({"ok": True, "result": result_text})

    except Exception as e:
        err_text = str(e)
        print("[MORNING][ERROR]", err_text)
        return jsonify({"ok": False, "error": err_text}), 200

# 저녁 메시지 생성
@app.route("/api/message/evening", methods=["POST"])
def api_evening_message():
    data = request.json or {}
    guide = data.get("guide", "")
    bible_text = data.get("text", "")
    ref = data.get("ref", "")
    date = data.get("date", "")

    print("[EVENING] payload =>", {
        "len_guide": len(guide),
        "len_text": len(bible_text),
        "ref": ref,
        "date": date,
    })

    try:
        completion = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": "You help create evening devotional messages in Korean."
                },
                {
                    "role": "user",
                    "content": f"[저녁 지침]\n{guide}\n\n[날짜]\n{date}\n\n[본문]\n{ref}\n{bible_text}"
                }
            ],
            temperature=0.7,
        )

        result_text = (completion.choices[0].message.content or "").strip()
        print("[EVENING] result length =>", len(result_text))

        return jsonify({"ok": True, "result": result_text})

    except Exception as e:
        err_text = str(e)
        print("[EVENING][ERROR]", err_text)
        return jsonify({"ok": False, "error": err_text}), 200

# 번역
@app.route("/api/message/translate", methods=["POST"])
def api_translate():
    data = request.json or {}
    guide = data.get("guide", "")
    text = data.get("text", "")
    lang = data.get("lang", "en")  # en or ja

    lang_name = "영어" if lang == "en" else "일본어"
    print(f"[TRANSLATE] {lang_name} =>", {"len_text": len(text)})

    try:
        completion = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": f"You translate Korean text to {lang_name}."
                },
                {
                    "role": "user",
                    "content": f"[번역 지침]\n{guide}\n\n[번역할 텍스트]\n{text}\n\n위 텍스트를 {lang_name}로 번역해주세요."
                }
            ],
            temperature=0.3,
        )

        result_text = (completion.choices[0].message.content or "").strip()
        print(f"[TRANSLATE] {lang_name} result length =>", len(result_text))

        return jsonify({"ok": True, "result": result_text})

    except Exception as e:
        err_text = str(e)
        print("[TRANSLATE][ERROR]", err_text)
        return jsonify({"ok": False, "error": err_text}), 200

# 이미지 프롬프트 생성
@app.route("/api/message/image-prompt", methods=["POST"])
def api_image_prompt():
    data = request.json or {}
    guide = data.get("guide", "")
    message = data.get("message", "")
    time = data.get("time", "morning")

    time_name = "오전" if time == "morning" else "저녁"
    print(f"[IMAGE_PROMPT] {time_name} =>", {"len_message": len(message)})

    try:
        completion = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": "You create image and music generation prompts IN ENGLISH based on devotional messages. Always respond in English."
                },
                {
                    "role": "user",
                    "content": f"""[Image Prompt Guidelines]
{guide}

[Message]
{message}

Create 3 separate image prompts and 1 music prompt based on the message above. 
Format your response EXACTLY like this:

### Image Prompt 1
[detailed English prompt for first image]

### Image Prompt 2
[detailed English prompt for second image]

### Image Prompt 3
[detailed English prompt for third image]

### Music Prompt
[detailed English prompt for background music]

IMPORTANT: Write ALL prompts in English only."""
                }
            ],
            temperature=0.7,
        )

        result_text = (completion.choices[0].message.content or "").strip()
        print(f"[IMAGE_PROMPT] {time_name} result length =>", len(result_text))

        return jsonify({"ok": True, "result": result_text})

    except Exception as e:
        err_text = str(e)
        print("[IMAGE_PROMPT][ERROR]", err_text)
        return jsonify({"ok": False, "error": err_text}), 200

if __name__ == "__main__":
    import os
    app.run(host="127.0.0.1", port=int(os.environ.get("PORT", 5058)), debug=True)