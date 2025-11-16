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
    return render_template("message.html")

@app.route("/message")
def message():
    return render_template("message.html")

@app.route("/health")
def health():
    return jsonify({"ok": True})

# ===== HTML에서 호출하는 통합 메시지 생성 API =====
@app.route("/api/message/generate", methods=["POST"])
def api_generate_message():
    """오전/저녁 메시지 생성 (HTML에서 호출)"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"ok": False, "error": "No data received"}), 400
        
        month = data.get("month", "")
        day = data.get("day", "")
        day_of_week = data.get("day_of_week", "")
        bible_ref = data.get("bible_ref", "")
        bible_text = data.get("bible_text", "")
        time_of_day = data.get("time_of_day", "morning")  # morning 또는 evening
        guide = data.get("guide", "")

        print(f"[GENERATE] {time_of_day} - {bible_ref}")

        # 시스템 메시지
        if time_of_day == "morning":
            system_msg = "You help create morning devotional messages in Korean."
            time_label = "오전"
        else:
            system_msg = "You help create evening devotional messages in Korean."
            time_label = "저녁"

        # 날짜 문자열 구성
        date_str = f"{month}월 {day}일"
        if day_of_week:
            date_str += f" {day_of_week}요일"

        # GPT 호출
        completion = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": system_msg
                },
                {
                    "role": "user",
                    "content": f"[{time_label} 지침]\n{guide}\n\n[날짜]\n{date_str}\n\n[본문]\n{bible_ref}\n\n{bible_text}\n\n위 내용을 바탕으로 {time_label} 묵상 메시지를 작성해주세요."
                }
            ],
            temperature=0.7,
        )
        
        result = completion.choices[0].message.content.strip()
        return jsonify({"ok": True, "message": result})
        
    except Exception as e:
        print(f"[GENERATE][ERROR] {str(e)}")
        return jsonify({"ok": False, "error": str(e)}), 200


# ===== 이미지 프롬프트 생성 API (s 추가!) =====
@app.route("/api/message/image-prompts", methods=["POST"])
def api_image_prompts():
    """이미지 프롬프트 생성 (HTML에서 호출)"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"ok": False, "error": "No data received"}), 400
        
        message = data.get("message", "")
        time_of_day = data.get("time_of_day", "morning")
        guide = data.get("guide", "")
        
        print(f"[IMAGE_PROMPTS] {time_of_day}")
        
        # GPT 호출
        completion = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": "You create image and music generation prompts IN ENGLISH. Always respond in English."
                },
                {
                    "role": "user",
                    "content": f"""[Guidelines]
{guide}

[Message]
{message}

Create 3 image prompts and 1 music prompt in English.

IMPORTANT: The 3 image prompts MUST be in the SAME VISUAL STYLE (same art style, same color palette, same mood).
They should look like they belong to the same series or collection.
Only the subject or scene should vary slightly, but the overall style must be consistent.

Format EXACTLY like this:

### Image Prompt 1
[detailed English prompt with consistent style]

### Image Prompt 2
[detailed English prompt with the SAME style as prompt 1]

### Image Prompt 3
[detailed English prompt with the SAME style as prompts 1 and 2]

### Music Prompt
[detailed English prompt]"""
                }
            ],
            temperature=0.7,
        )
        
        result = completion.choices[0].message.content.strip()
        
        # 결과를 파싱하여 각각 분리
        lines = result.split('\n')
        image1 = ""
        image2 = ""
        image3 = ""
        music = ""
        
        current_section = None
        current_content = []
        
        for line in lines:
            line = line.strip()
            if "### Image Prompt 1" in line or "Image Prompt 1" in line:
                if current_section:
                    content = '\n'.join(current_content).strip()
                    if current_section == 1:
                        image1 = content
                    elif current_section == 2:
                        image2 = content
                    elif current_section == 3:
                        image3 = content
                    elif current_section == 4:
                        music = content
                current_section = 1
                current_content = []
            elif "### Image Prompt 2" in line or "Image Prompt 2" in line:
                if current_section:
                    content = '\n'.join(current_content).strip()
                    if current_section == 1:
                        image1 = content
                current_section = 2
                current_content = []
            elif "### Image Prompt 3" in line or "Image Prompt 3" in line:
                if current_section:
                    content = '\n'.join(current_content).strip()
                    if current_section == 1:
                        image1 = content
                    elif current_section == 2:
                        image2 = content
                current_section = 3
                current_content = []
            elif "### Music Prompt" in line or "Music Prompt" in line:
                if current_section:
                    content = '\n'.join(current_content).strip()
                    if current_section == 1:
                        image1 = content
                    elif current_section == 2:
                        image2 = content
                    elif current_section == 3:
                        image3 = content
                current_section = 4
                current_content = []
            elif line and not line.startswith('#'):
                current_content.append(line)
        
        # 마지막 섹션 처리
        if current_section:
            content = '\n'.join(current_content).strip()
            if current_section == 1:
                image1 = content
            elif current_section == 2:
                image2 = content
            elif current_section == 3:
                image3 = content
            elif current_section == 4:
                music = content
        
        return jsonify({
            "ok": True,
            "image1": image1,
            "image2": image2,
            "image3": image3,
            "music": music
        })
        
    except Exception as e:
        print(f"[IMAGE_PROMPTS][ERROR] {str(e)}")
        return jsonify({"ok": False, "error": str(e)}), 200


# ===== 번역 API =====
@app.route("/api/message/translate", methods=["POST"])
def api_translate():
    """번역 (HTML에서 호출)"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"ok": False, "error": "No data received"}), 400
        
        text = data.get("text", "")
        target_lang = data.get("target_lang", "en")
        guide = data.get("guide", "")
        
        lang_name = "영어" if target_lang == "en" else "일본어"
        print(f"[TRANSLATE] to {lang_name}")
        
        completion = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": f"You translate Korean text to {lang_name}."
                },
                {
                    "role": "user",
                    "content": f"[번역 지침]\n{guide}\n\n[텍스트]\n{text}\n\n위를 {lang_name}로 번역해주세요."
                }
            ],
            temperature=0.3,
        )
        
        result = completion.choices[0].message.content.strip()
        return jsonify({"ok": True, "translation": result})
        
    except Exception as e:
        print(f"[TRANSLATE][ERROR] {str(e)}")
        return jsonify({"ok": False, "error": str(e)}), 200


# ===== Render 배포를 위한 설정 =====
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5058))
    # Render 배포용: host="0.0.0.0", debug=False
    app.run(host="0.0.0.0", port=port, debug=False)