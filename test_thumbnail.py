#!/usr/bin/env python3
"""썸네일 이미지 생성 테스트 (OpenRouter API)"""

import os
import base64
import requests

# API 설정
API_KEY = os.environ.get('OPENROUTER_API_KEY')

# 1화 - 이방인 씬: 무영이 이세계에서 눈을 뜨는 장면
SCENE_PROMPTS = {
    "ep001": {
        "title": "이방인",
        "prompt": """
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
16:9 aspect ratio, no text
"""
    }
}

PROMPT = SCENE_PROMPTS["ep001"]["prompt"]

NEGATIVE_PROMPT = """
text, letters, words, writing, watermark,
anime style, cartoon, chibi,
low quality, blurry, deformed,
modern clothes, contemporary fashion,
asian architecture, eastern style building
"""

def generate_imagen():
    """Google Imagen 3 API로 이미지 생성"""

    if not API_KEY:
        print("❌ API Key가 없습니다")
        return

    print(f"✅ API Key 확인됨 (길이: {len(API_KEY)})")
    print()
    print("프롬프트:")
    print("-" * 40)
    print(PROMPT.strip())
    print("-" * 40)
    print()

    # OpenRouter API 이미지 생성
    url = "https://openrouter.ai/api/v1/chat/completions"

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {API_KEY}"
    }

    payload = {
        "model": "google/gemini-2.5-flash-preview-image-generation",
        "messages": [{
            "role": "user",
            "content": f"Generate an image: {PROMPT.strip()}"
        }],
        "modalities": ["image", "text"],
        "image_config": {
            "aspect_ratio": "16:9"
        }
    }

    print("🖼️ 이미지 생성 중 (OpenRouter - Gemini 2.5 Flash)...")

    try:
        response = requests.post(url, headers=headers, json=payload, timeout=120)

        if response.status_code == 200:
            data = response.json()

            # OpenRouter 응답에서 이미지 추출
            choices = data.get("choices", [])
            if choices:
                message = choices[0].get("message", {})

                # images 배열에서 추출
                images = message.get("images", [])
                if images:
                    image_url = images[0].get("image_url", {}).get("url", "")
                    if image_url.startswith("data:image"):
                        # data:image/png;base64,... 형식
                        header, image_data = image_url.split(",", 1)
                        mime_type = header.split(";")[0].split(":")[1]

                        output_dir = "outputs/isekai/images"
                        os.makedirs(output_dir, exist_ok=True)

                        ext = "png" if "png" in mime_type else "jpg"
                        output_path = os.path.join(output_dir, f"test_ep001_thumbnail.{ext}")
                        with open(output_path, "wb") as f:
                            f.write(base64.b64decode(image_data))

                        print(f"✅ 성공! 저장됨: {output_path}")
                        return output_path

                # content에서 이미지 추출 시도
                content = message.get("content", "")
                if content:
                    print(f"📝 텍스트 응답: {content[:200]}")

            print(f"❌ 이미지 데이터 없음: {data}")
        else:
            print(f"❌ API 오류 ({response.status_code}): {response.text[:500]}")

    except Exception as e:
        print(f"❌ 예외 발생: {e}")

    return None


if __name__ == "__main__":
    print("=" * 50)
    print("썸네일 이미지 생성 테스트")
    print("=" * 50)
    print()
    generate_imagen()
