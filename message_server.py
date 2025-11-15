import os
from flask import Flask, render_template, request, jsonify, send_file
from openai import OpenAI
from datetime import datetime
import traceback

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
                    "content": f"[{time_label} 지침]\n{guide}\n\n[날짜]\n{month}월 {day}일\n\n[본문]\n{bible_ref}\n\n{bible_text}\n\n위 내용을 바탕으로 {time_label} 묵상 메시지를 작성해주세요."
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

Format EXACTLY like this:

### Image Prompt 1
[detailed English prompt]

### Image Prompt 2
[detailed English prompt]

### Image Prompt 3
[detailed English prompt]

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


# ===== 비디오 생성 API =====
@app.route("/api/message/create-video", methods=["POST"])
def api_create_video():
    """묵상 메시지 비디오 생성 (전체 워크플로우)"""
    try:
        from image_fetcher import ImageFetcher
        from shorts_maker import ShortsMaker

        data = request.get_json()
        if not data:
            return jsonify({"ok": False, "error": "No data received"}), 400

        message = data.get("message", "")
        bible_ref = data.get("bible_ref", "")
        duration = data.get("duration", 10)  # 기본 10초

        if not message:
            return jsonify({"ok": False, "error": "Message is required"}), 400

        print(f"[CREATE_VIDEO] Starting video creation...")

        # 타임스탬프로 고유 파일명 생성
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # 1. 이미지 다운로드
        print("[CREATE_VIDEO] Step 1: Downloading image...")
        fetcher = ImageFetcher()
        image_path = f"output/images/devotional_{timestamp}.jpg"

        result_image = fetcher.get_image_for_message(message, image_path)
        if not result_image:
            return jsonify({"ok": False, "error": "Failed to download image"}), 500

        # 2. 비디오 생성
        print("[CREATE_VIDEO] Step 2: Creating video...")
        maker = ShortsMaker()
        video_path = f"output/videos/devotional_{timestamp}.mp4"

        result_video = maker.create_devotional_video(
            result_image,
            message,
            video_path,
            bible_ref,
            duration
        )

        if not result_video:
            return jsonify({"ok": False, "error": "Failed to create video"}), 500

        print(f"[CREATE_VIDEO] Success! Video: {result_video}")

        return jsonify({
            "ok": True,
            "video_path": result_video,
            "image_path": result_image,
            "message": "Video created successfully"
        })

    except Exception as e:
        print(f"[CREATE_VIDEO][ERROR] {str(e)}")
        traceback.print_exc()
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/message/download-video/<filename>", methods=["GET"])
def api_download_video(filename):
    """생성된 비디오 다운로드"""
    try:
        video_path = f"output/videos/{filename}"
        if not os.path.exists(video_path):
            return jsonify({"ok": False, "error": "File not found"}), 404

        return send_file(
            video_path,
            as_attachment=True,
            download_name=filename,
            mimetype='video/mp4'
        )
    except Exception as e:
        print(f"[DOWNLOAD_VIDEO][ERROR] {str(e)}")
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/message/create-image", methods=["POST"])
def api_create_image():
    """묵상 메시지 이미지 생성 (비디오 없이 이미지만)"""
    try:
        from image_fetcher import ImageFetcher
        from shorts_maker import ShortsMaker

        data = request.get_json()
        if not data:
            return jsonify({"ok": False, "error": "No data received"}), 400

        message = data.get("message", "")
        bible_ref = data.get("bible_ref", "")

        if not message:
            return jsonify({"ok": False, "error": "Message is required"}), 400

        print(f"[CREATE_IMAGE] Starting image creation...")

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # 1. 배경 이미지 다운로드
        fetcher = ImageFetcher()
        bg_image_path = f"output/images/bg_{timestamp}.jpg"
        result_bg = fetcher.get_image_for_message(message, bg_image_path)

        if not result_bg:
            return jsonify({"ok": False, "error": "Failed to download background image"}), 500

        # 2. 묵상 이미지 생성
        maker = ShortsMaker()
        final_image_path = f"output/images/devotional_{timestamp}.jpg"
        result_image = maker.create_devotional_image(
            result_bg,
            message,
            final_image_path,
            bible_ref
        )

        if not result_image:
            return jsonify({"ok": False, "error": "Failed to create image"}), 500

        print(f"[CREATE_IMAGE] Success! Image: {result_image}")

        return jsonify({
            "ok": True,
            "image_path": result_image,
            "message": "Image created successfully"
        })

    except Exception as e:
        print(f"[CREATE_IMAGE][ERROR] {str(e)}")
        traceback.print_exc()
        return jsonify({"ok": False, "error": str(e)}), 500


# ===== Render 배포를 위한 설정 =====
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5058))
    # Render 배포용: host="0.0.0.0", debug=False
    app.run(host="0.0.0.0", port=port, debug=False)