# 드라마 앱 문제 코드 - Opus 4.5 분석용

## 🚨 발생 중인 문제

### 1. TTS 음성 생성 오류
```
오류: Google TTS API 오류 (400): {
  "error": {
    "code": 400,
    "message": "Either `input.text` or `input.ssml` is longer than the limit of 5000 bytes.
                This limit is different from quotas. To fix, reduce the byte length of the
                characters in this request, or consider using the Long Audio API:
                https://cloud.google.com/text-to-speech/docs/create-audio-text-long-audio-synthesis.",
    "status": "INVALID_ARGUMENT"
  }
}
```

### 2. 한국인 인물 이미지 생성 문제
- 한국 할머니/할아버지 생성 시 외국인 사진이 나옴
- 씬 2, 3, 4에서 모두 동일한 문제 발생

---

## 📝 관련 코드 (drama_server.py)

### 1. TTS 생성 함수 (라인 2913-3160)

```python
@app.route('/api/drama/generate-tts', methods=['POST'])
def api_generate_tts():
    """TTS 음성 생성 - Google Cloud TTS (기본) 또는 네이버 클로바"""
    try:
        import requests
        import base64

        data = request.get_json()
        if not data:
            return jsonify({"ok": False, "error": "No data received"}), 400

        text = data.get("text", "")
        speaker = data.get("speaker", "ko-KR-Wavenet-A")
        speed = data.get("speed", 1.0)
        pitch = data.get("pitch", 0)
        volume = data.get("volume", 0)
        tts_provider = data.get("ttsProvider", "google")

        if not text:
            return jsonify({"ok": False, "error": "텍스트가 없습니다."}), 400

        char_count = len(text)

        # Google Cloud TTS
        if tts_provider == "google":
            google_api_key = os.getenv("GOOGLE_CLOUD_API_KEY", "")

            if not google_api_key:
                return jsonify({"ok": False, "error": "Google Cloud API 키가 설정되지 않았습니다."}), 200

            print(f"[TTS] Google TTS 생성 시작 - 음성: {speaker}, 텍스트 길이: {char_count}자")

            # 감정 표현 키워드
            emotional_keywords = [
                "눈물이", "눈시울", "손이 떨", "목이 메", "가슴이 먹먹",
                "슬", "아프", "고통", "절망", "두려", "감사", "정말", "진심으로", "간절히"
            ]

            def apply_emotion_ssml(text_chunk, base_rate):
                """감정 표현이 있는 문장에 SSML 속도 조절 적용"""
                import re
                import html

                def escape_for_ssml(text):
                    return html.escape(text, quote=False)

                sentences = re.split(r'([.!?。！？])', text_chunk)
                merged = []
                i = 0
                while i < len(sentences):
                    if i + 1 < len(sentences) and sentences[i+1] in '.!?。！？':
                        merged.append(sentences[i] + sentences[i+1])
                        i += 2
                    else:
                        if sentences[i].strip():
                            merged.append(sentences[i])
                        i += 1

                result_parts = []
                has_emotion = False

                for sentence in merged:
                    sentence = sentence.strip()
                    if not sentence:
                        continue

                    is_emotional = any(kw in sentence for kw in emotional_keywords)

                    if is_emotional:
                        has_emotion = True
                        emotion_rate = max(0.25, base_rate * 0.9)
                        escaped_sentence = escape_for_ssml(sentence)
                        result_parts.append(f'<break time="300ms"/><prosody rate="{emotion_rate:.2f}">{escaped_sentence}</prosody><break time="200ms"/>')
                    else:
                        result_parts.append(escape_for_ssml(sentence))

                if has_emotion:
                    ssml_text = f'<speak>{" ".join(result_parts)}</speak>'
                    return ssml_text, True
                else:
                    return text_chunk, False

            # Google Cloud TTS는 최대 5000바이트 제한
            # 한글은 UTF-8에서 3바이트이므로 안전하게 3500바이트(약 1166자) 이하로 유지
            # SSML 태그 오버헤드(최대 1500바이트)를 고려하여 여유있게 설정
            max_bytes = 3500
            text_chunks = []

            def get_byte_length(s):
                return len(s.encode('utf-8'))

            def split_text_by_bytes(text, max_bytes):
                """텍스트를 바이트 제한에 맞게 분할"""
                chunks = []
                import re
                sentences = re.split(r'([.!?。！？])', text)
                merged_sentences = []
                i = 0
                while i < len(sentences):
                    if i + 1 < len(sentences) and sentences[i+1] in '.!?。！？':
                        merged_sentences.append(sentences[i] + sentences[i+1])
                        i += 2
                    else:
                        if sentences[i].strip():
                            merged_sentences.append(sentences[i])
                        i += 1

                current_chunk = ""
                for sentence in merged_sentences:
                    sentence = sentence.strip()
                    if not sentence:
                        continue

                    if get_byte_length(sentence) > max_bytes:
                        if current_chunk:
                            chunks.append(current_chunk.strip())
                            current_chunk = ""
                        sub_parts = re.split(r'([,，、\s])', sentence)
                        sub_chunk = ""
                        for part in sub_parts:
                            if get_byte_length(sub_chunk + part) < max_bytes:
                                sub_chunk += part
                            else:
                                if sub_chunk:
                                    chunks.append(sub_chunk.strip())
                                sub_chunk = part
                        if sub_chunk:
                            current_chunk = sub_chunk
                    elif get_byte_length(current_chunk + " " + sentence) < max_bytes:
                        current_chunk = (current_chunk + " " + sentence).strip()
                    else:
                        if current_chunk:
                            chunks.append(current_chunk.strip())
                        current_chunk = sentence

                if current_chunk:
                    chunks.append(current_chunk.strip())

                return chunks if chunks else [text[:1500]]

            text_chunks = split_text_by_bytes(text, max_bytes)
            print(f"[TTS] 텍스트를 {len(text_chunks)}개 청크로 분할 (바이트 제한: {max_bytes})")

            audio_data_list = []
            url = f"https://texttospeech.googleapis.com/v1/text:synthesize?key={google_api_key}"

            # 속도 변환
            if isinstance(speed, (int, float)):
                if speed == 0:
                    google_speed = 1.0
                else:
                    google_speed = 1.0 + (speed * 0.1)
                    google_speed = max(0.25, min(4.0, google_speed))
            else:
                google_speed = 1.0

            google_pitch = pitch * 4 if isinstance(pitch, (int, float)) else 0

            emotion_chunk_count = 0
            for chunk in text_chunks:
                processed_chunk, is_ssml = apply_emotion_ssml(chunk, google_speed)

                if is_ssml:
                    emotion_chunk_count += 1
                    payload = {
                        "input": {"ssml": processed_chunk},
                        "voice": {
                            "languageCode": "ko-KR",
                            "name": speaker
                        },
                        "audioConfig": {
                            "audioEncoding": "MP3",
                            "speakingRate": google_speed,
                            "pitch": google_pitch
                        }
                    }
                else:
                    payload = {
                        "input": {"text": chunk},
                        "voice": {
                            "languageCode": "ko-KR",
                            "name": speaker
                        },
                        "audioConfig": {
                            "audioEncoding": "MP3",
                            "speakingRate": google_speed,
                            "pitch": google_pitch
                        }
                    }

                response = requests.post(url, json=payload, timeout=90)

                if response.status_code == 200:
                    result = response.json()
                    audio_content = base64.b64decode(result.get("audioContent", ""))
                    audio_data_list.append(audio_content)
                else:
                    error_text = response.text
                    print(f"[TTS][ERROR] Google API 응답: {response.status_code} - {error_text}")
                    return jsonify({"ok": False, "error": f"Google TTS API 오류 ({response.status_code}): {error_text}"}), 200

            combined_audio = b''.join(audio_data_list)
            audio_base64 = base64.b64encode(combined_audio).decode('utf-8')
            audio_url = f"data:audio/mp3;base64,{audio_base64}"

            cost_per_char = 0.0054 if "Wavenet" in speaker else 0.0216
            cost_krw = int(char_count * cost_per_char)

            return jsonify({
                "ok": True,
                "audioUrl": audio_url,
                "charCount": char_count,
                "cost": cost_krw,
                "provider": "google",
                "emotionChunks": emotion_chunk_count,
                "totalChunks": len(text_chunks)
            })
```

### 2. 캐릭터 분석 함수 (라인 2368-2452)

```python
@app.route('/api/drama/analyze-characters', methods=['POST'])
def api_analyze_characters():
    """대본을 분석하여 등장인물과 씬 정보 추출"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"ok": False, "error": "No data received"}), 400

        script = data.get("script", "")

        if not script:
            return jsonify({"ok": False, "error": "대본이 없습니다."}), 400

        print(f"[ANALYZE] 등장인물 및 씬 분석 시작")

        system_content = """당신은 드라마 대본을 분석하여 등장인물과 씬 정보를 추출하는 전문가입니다.

대본을 분석하여 다음 정보를 JSON 형식으로 추출해주세요:

1. 등장인물 (characters): 각 인물에 대해
   - name: 인물 이름 (한글)
   - description: 인물 설명 (나이, 성격, 역할 등 - 한글)
   - imagePrompt: DALL-E용 영어 이미지 프롬프트 (외모, 의상, 분위기 묘사)

2. 씬 (scenes): 각 씬에 대해
   - title: 씬 제목 또는 요약 (한글)
   - location: 장소 (한글)
   - description: 씬 설명 (한글)
   - characters: 등장하는 인물들 이름 배열
   - backgroundPrompt: DALL-E용 영어 배경 프롬프트 (장소, 분위기, 조명 묘사)

응답은 반드시 다음 JSON 형식으로:
{
  "characters": [
    {"name": "수진", "description": "28세 여성, 밝고 활발한 성격의 카페 사장", "imagePrompt": "A Korean woman in her late 20s with East Asian features, Korean ethnicity, bright and cheerful expression, casual smart outfit..."},
    ...
  ],
  "scenes": [
    {"title": "첫 만남", "location": "카페", "description": "수진이 처음 민수를 만나는 장면", "characters": ["수진", "민수"], "backgroundPrompt": "A cozy Korean cafe interior, warm afternoon light..."},
    ...
  ]
}

중요:
- imagePrompt와 backgroundPrompt는 반드시 영어로 작성
- 프롬프트는 DALL-E 3에 최적화되도록 상세하게 작성
- 인물 프롬프트는 portrait 스타일에 적합하게 작성
- 한국 드라마 스타일의 시각적 요소 반영
- ⚠️ CRITICAL: 모든 인물의 imagePrompt는 반드시 "Korean" 또는 "Korean ethnicity", "East Asian features"를 명시적으로 포함해야 합니다
- 한국인 할머니/할아버지는 "elderly Korean woman/man with East Asian features" 등으로 명확히 표현"""

        user_content = f"""다음 드라마 대본을 분석해주세요:

{script[:15000]}

⚠️ 중요: 대본에 있는 모든 씬을 빠짐없이 추출해주세요.
등장인물과 씬 정보를 JSON 형식으로 추출해주세요."""

        completion = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_content},
                {"role": "user", "content": user_content}
            ],
            temperature=0.7,
            response_format={"type": "json_object"}
        )

        result = completion.choices[0].message.content.strip()

        import json as json_module
        parsed = json_module.loads(result)

        characters = parsed.get("characters", [])
        scenes = parsed.get("scenes", [])

        print(f"[ANALYZE] 분석 완료 - 인물: {len(characters)}명, 씬: {len(scenes)}개")

        return jsonify({
            "ok": True,
            "characters": characters,
            "scenes": scenes
        })

    except Exception as e:
        print(f"[ANALYZE][ERROR] {str(e)}")
        return jsonify({"ok": False, "error": str(e)}), 200
```

### 3. 이미지 생성 함수 (라인 2556-2909) - 핵심 부분만

```python
@app.route('/api/drama/generate-image', methods=['POST'])
def api_generate_image():
    """이미지 생성 - Gemini (기본) / FLUX.1 Pro / DALL-E 3"""
    try:
        import requests as req

        data = request.get_json()
        prompt = data.get("prompt", "")
        size = data.get("size", "1024x1024")
        image_provider = data.get("imageProvider", "gemini")

        if not prompt:
            return jsonify({"ok": False, "error": "프롬프트가 없습니다."}), 400

        # Gemini 2.5 Flash Image
        if image_provider == "gemini":
            openrouter_api_key = os.getenv("OPENROUTER_API_KEY", "")

            if not openrouter_api_key:
                return jsonify({"ok": False, "error": "OpenRouter API 키가 설정되지 않았습니다."}), 200

            # 프롬프트에 스타일 가이드 추가 및 한국 인종 강조
            if "Korean" in prompt or "korean" in prompt:
                enhanced_prompt = f"Generate a high quality, photorealistic image: {prompt}. IMPORTANT: Ensure the person has authentic Korean/East Asian facial features, Korean ethnicity. Style: cinematic lighting, professional photography, 8k resolution, detailed"
            else:
                enhanced_prompt = f"Generate a high quality, photorealistic image: {prompt}. Style: cinematic lighting, professional photography, 8k resolution, detailed"

            headers = {
                "Authorization": f"Bearer {openrouter_api_key}",
                "Content-Type": "application/json"
            }

            payload = {
                "model": "google/gemini-2.5-flash-image-preview",
                "modalities": ["text", "image"],
                "messages": [
                    {
                        "role": "user",
                        "content": [{"type": "text", "text": enhanced_prompt}]
                    }
                ]
            }

            response = req.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers=headers,
                json=payload,
                timeout=90
            )

            # ... (이미지 URL 추출 로직)

        # FLUX.1 Pro
        elif image_provider == "flux":
            # 프롬프트 강화
            if "Korean" in prompt or "korean" in prompt:
                enhanced_prompt = f"{prompt}, IMPORTANT: authentic Korean/East Asian facial features and ethnicity, high quality, photorealistic"
            else:
                enhanced_prompt = f"{prompt}, high quality, photorealistic"

        # DALL-E 3
        else:
            # 프롬프트 강화
            if "Korean" in prompt or "korean" in prompt:
                enhanced_prompt = f"{prompt}, IMPORTANT: authentic Korean/East Asian facial features and ethnicity, high quality, photorealistic"
            else:
                enhanced_prompt = f"{prompt}, high quality, photorealistic"

            response = client.images.generate(
                model="dall-e-3",
                prompt=enhanced_prompt,
                size=size,
                quality="standard",
                n=1
            )
```

---

## 📌 분석 요청사항

Opus 4.5에게:

1. **TTS 문제**: SSML 태그가 추가될 때 5000바이트를 초과하는 경우가 여전히 발생합니다. `max_bytes = 3500`으로 설정했는데도 문제가 계속됩니다. 완벽하게 해결해주세요.

2. **이미지 생성 문제**: 한국인 캐릭터 프롬프트에 "Korean ethnicity", "East Asian features"를 명시했는데도 여전히 외국인 이미지가 생성됩니다. 더 강력한 방법이 필요합니다.

3. 두 문제 모두 완벽하게 작동하도록 코드를 수정하고, 전체 수정된 함수를 제공해주세요.
