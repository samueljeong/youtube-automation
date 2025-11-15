"""
TTS (Text-to-Speech) 생성 모듈

묵상 메시지를 음성으로 변환합니다.
"""

import os
from typing import Optional
from openai import OpenAI


class TTSGenerator:
    """텍스트를 음성으로 변환"""

    def __init__(self):
        self.openai_client = self._get_openai_client()

    def _get_openai_client(self):
        """OpenAI 클라이언트 생성"""
        key = (os.getenv("OPENAI_API_KEY") or "").strip()
        if not key:
            print("[TTSGenerator] Warning: OPENAI_API_KEY not set. OpenAI TTS unavailable.")
            return None
        return OpenAI(api_key=key)

    def generate_openai_tts(self, text: str, output_path: str, voice: str = "alloy") -> Optional[str]:
        """
        OpenAI TTS로 음성 생성 (고품질)

        Args:
            text: 읽을 텍스트
            output_path: 저장할 파일 경로 (.mp3)
            voice: 음성 종류 (alloy, echo, fable, onyx, nova, shimmer)

        Returns:
            저장된 파일 경로 또는 None
        """
        if not self.openai_client:
            print("[TTSGenerator] OpenAI client not available")
            return None

        try:
            print(f"[TTSGenerator] Generating OpenAI TTS...")

            response = self.openai_client.audio.speech.create(
                model="tts-1",  # tts-1 또는 tts-1-hd
                voice=voice,
                input=text
            )

            # 파일 저장
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            response.stream_to_file(output_path)

            print(f"[TTSGenerator] OpenAI TTS created: {output_path}")
            return output_path

        except Exception as e:
            print(f"[TTSGenerator] OpenAI TTS error: {e}")
            import traceback
            traceback.print_exc()
            return None

    def generate_gtts(self, text: str, output_path: str, lang: str = "ko") -> Optional[str]:
        """
        gTTS로 음성 생성 (무료, 저품질)

        Args:
            text: 읽을 텍스트
            output_path: 저장할 파일 경로 (.mp3)
            lang: 언어 코드 (ko, en, zh-CN 등)

        Returns:
            저장된 파일 경로 또는 None
        """
        try:
            from gtts import gTTS

            print(f"[TTSGenerator] Generating gTTS...")

            tts = gTTS(text=text, lang=lang, slow=False)

            # 파일 저장
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            tts.save(output_path)

            print(f"[TTSGenerator] gTTS created: {output_path}")
            return output_path

        except ImportError:
            print("[TTSGenerator] gTTS not installed. Install with: pip install gTTS")
            return None
        except Exception as e:
            print(f"[TTSGenerator] gTTS error: {e}")
            import traceback
            traceback.print_exc()
            return None

    def generate_tts(self, text: str, output_path: str, use_openai: bool = True) -> Optional[str]:
        """
        TTS 음성 생성 (OpenAI 우선, 실패하면 gTTS)

        Args:
            text: 읽을 텍스트
            output_path: 저장할 파일 경로 (.mp3)
            use_openai: OpenAI TTS 사용 여부 (기본: True)

        Returns:
            저장된 파일 경로 또는 None
        """
        # OpenAI TTS 시도 (고품질)
        if use_openai and self.openai_client:
            result = self.generate_openai_tts(text, output_path, voice="nova")  # nova는 여성 목소리
            if result:
                return result
            print("[TTSGenerator] OpenAI TTS failed, trying gTTS...")

        # gTTS 시도 (무료)
        result = self.generate_gtts(text, output_path, lang="ko")
        if result:
            return result

        print("[TTSGenerator] All TTS methods failed")
        return None


# 테스트용 코드
if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()

    generator = TTSGenerator()

    # 테스트 텍스트
    test_text = "오늘 하루도 평안하고 감사한 하루 되세요. 주님의 사랑이 함께 하시기를 기도합니다."

    # 테스트: TTS 생성
    print("Testing TTS generation...")
    result = generator.generate_tts(test_text, "output/audio/test_tts.mp3")
    if result:
        file_size = os.path.getsize(result) / 1024  # KB
        print(f"✅ TTS Success: {result}")
        print(f"   File size: {file_size:.1f} KB")
    else:
        print("❌ TTS Failed")
