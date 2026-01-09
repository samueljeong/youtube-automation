#!/usr/bin/env python3
"""씬 이미지 생성 테스트 (Gemini 2.0 Flash)"""

import os
import base64
import requests

# API 설정
API_KEY = os.environ.get('GOOGLE_CLOUD_API_KEY') or os.environ.get('GOOGLE_API_KEY')

# 1화 씬 프롬프트
SCENE_PROMPT = """
Young East Asian man, early 20s, sharp angular features,
intense dark eyes, messy black hair in a loose ponytail,
lean muscular build, wearing tattered dark martial arts clothes,
subtle scars on hands, confused and alert expression,
sitting up on a stone floor, just waking up in an unfamiliar place,
medieval western fantasy stone room interior,
dim morning light streaming through a window,
two moons visible in the purple sky outside,
western fantasy illustration style, epic cinematic lighting,
dramatic composition, book cover quality, masterpiece, highly detailed,
16:9 aspect ratio, no text, no watermark
"""

def generate_scene_image(episode_id: str = "ep001"):
    """Gemini 2.0 Flash로 씬 이미지 생성"""

    if not API_KEY:
        print("❌ API Key가 없습니다")
        return None

    print(f"✅ API Key 확인됨 (길이: {len(API_KEY)})")
    print(f"📍 에피소드: {episode_id}")
    print()

    # Gemini 2.0 Flash 이미지 생성
    url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash-exp:generateContent"

    headers = {
        "Content-Type": "application/json",
        "x-goog-api-key": API_KEY
    }

    payload = {
        "contents": [{
            "parts": [{
                "text": f"Generate an image: {SCENE_PROMPT.strip()}"
            }]
        }],
        "generationConfig": {
            "responseModalities": ["image", "text"]
        }
    }

    print("🖼️ 씬 이미지 생성 중...")

    try:
        response = requests.post(url, headers=headers, json=payload, timeout=120)

        if response.status_code == 200:
            data = response.json()

            candidates = data.get("candidates", [])
            if candidates:
                parts = candidates[0].get("content", {}).get("parts", [])
                for part in parts:
                    if "inlineData" in part:
                        image_data = part["inlineData"].get("data")
                        mime_type = part["inlineData"].get("mimeType", "image/png")

                        if image_data:
                            output_dir = "outputs/isekai/images"
                            os.makedirs(output_dir, exist_ok=True)

                            ext = "png" if "png" in mime_type else "jpg"
                            output_path = os.path.join(output_dir, f"{episode_id}_scene.{ext}")
                            with open(output_path, "wb") as f:
                                f.write(base64.b64decode(image_data))

                            print(f"✅ 성공! 저장됨: {output_path}")
                            return output_path

            print(f"❌ 이미지 데이터 없음")
        else:
            print(f"❌ API 오류 ({response.status_code}): {response.text[:300]}")

    except Exception as e:
        print(f"❌ 예외 발생: {e}")

    return None


if __name__ == "__main__":
    print("=" * 50)
    print("씬 이미지 생성 테스트 (1화)")
    print("=" * 50)
    print()
    generate_scene_image("ep001")
