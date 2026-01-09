#!/usr/bin/env python3
"""
Gemini TTS 테스트 스크립트

사용법:
    python scripts/isekai_pipeline/test_gemini_tts.py

환경변수:
    GOOGLE_API_KEY: Google API 키
"""

import os
import sys

# 프로젝트 루트를 path에 추가
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from scripts.isekai_pipeline.tts import (
    generate_gemini_tts_chunk,
    convert_wav_to_mp3,
    EMOTION_STYLE_PROMPTS,
    GEMINI_VOICES,
)


def test_gemini_tts():
    """Gemini TTS 단일 청크 테스트"""
    api_key = os.environ.get('GOOGLE_API_KEY')
    if not api_key:
        print("❌ GOOGLE_API_KEY 환경변수가 필요합니다")
        return False

    # 테스트 텍스트 (이세계 1화 일부)
    test_cases = [
        {
            "emotion": "fight",
            "text": "검이 부딪쳤다. 화광이 튀었다. 내공이 폭발했다. 천지가 뒤흔들렸다.",
            "voice": "Orus"  # 남성
        },
        {
            "emotion": "epic",
            "text": "그리고 공간이 갈라졌다. 두 절대강자의 충돌이 만들어낸 결과. 차원의 균열.",
            "voice": "Kore"  # 기본
        },
        {
            "emotion": "calm",
            "text": "눈을 떴을 때, 처음 본 것은 푸른 하늘이었다. 낯선 하늘. 낯선 공기. 여기가 어디지?",
            "voice": "Kore"
        },
    ]

    output_dir = "outputs/isekai/EP001/audio/gemini_test"
    os.makedirs(output_dir, exist_ok=True)

    success_count = 0

    for i, case in enumerate(test_cases):
        emotion = case["emotion"]
        text = case["text"]
        voice = case["voice"]
        style_prompt = EMOTION_STYLE_PROMPTS.get(emotion, EMOTION_STYLE_PROMPTS["default"])

        print(f"\n[테스트 {i+1}] 감정: {emotion}, 보이스: {voice}")
        print(f"  스타일: {style_prompt}")
        print(f"  텍스트: {text[:50]}...")

        result = generate_gemini_tts_chunk(text, style_prompt, voice, api_key)

        if result.get("ok"):
            output_path = os.path.join(output_dir, f"test_{emotion}_{voice}.mp3")

            if result.get("format") == "wav":
                if convert_wav_to_mp3(result["audio_data"], output_path):
                    file_size = os.path.getsize(output_path) / 1024
                    print(f"  ✅ 성공: {output_path} ({file_size:.1f}KB)")
                    success_count += 1
                else:
                    print(f"  ❌ WAV→MP3 변환 실패")
            else:
                with open(output_path, 'wb') as f:
                    f.write(result["audio_data"])
                file_size = os.path.getsize(output_path) / 1024
                print(f"  ✅ 성공: {output_path} ({file_size:.1f}KB)")
                success_count += 1
        else:
            print(f"  ❌ 실패: {result.get('error')}")

    print(f"\n=============================")
    print(f"결과: {success_count}/{len(test_cases)} 성공")
    print(f"출력 디렉토리: {output_dir}")

    return success_count == len(test_cases)


if __name__ == "__main__":
    success = test_gemini_tts()
    sys.exit(0 if success else 1)
