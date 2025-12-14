"""
Google Cloud TTS API Caller for Step 3
Google Cloud Text-to-Speech API를 사용한 음성 생성

Usage:
    # 방법 1: Google Cloud TTS (고품질, 유료)
    export GOOGLE_APPLICATION_CREDENTIALS="/path/to/service-account.json"

    # 방법 2: gTTS (무료, 간단)
    pip install gtts

Requirements:
    pip install google-cloud-texttospeech  # Google Cloud TTS
    pip install gtts  # 무료 대안
"""

import os
from pathlib import Path
from typing import Optional
from .tts_gender_rules import get_tts_voice_id


# TTS 엔진 선택: "google_cloud" 또는 "gtts"
TTS_ENGINE = os.getenv("TTS_ENGINE", "gtts")


def generate_tts(
    text: str,
    gender: str,
    output_filename: str,
    speaking_rate: float = 0.9,
    pitch: float = 0.0,
    volume_gain_db: float = 0.0
) -> Optional[str]:
    """
    TTS를 사용하여 음성 파일 생성

    Args:
        text: TTS로 변환할 문자열
        gender: 화자 성별 ("male" 또는 "female")
        output_filename: 출력 파일명 (예: audio_scene1.mp3)
        speaking_rate: 읽기 속도 (기본 0.9 - 약간 느리게)
        pitch: 피치 조정 (기본 0.0)
        volume_gain_db: 볼륨 조정 (기본 0.0)

    Returns:
        생성된 파일 경로 또는 None (실패 시)
    """
    if TTS_ENGINE == "google_cloud":
        return _generate_google_cloud_tts(
            text, gender, output_filename, speaking_rate, pitch, volume_gain_db
        )
    else:
        return _generate_gtts(text, output_filename, speaking_rate)


def _generate_google_cloud_tts(
    text: str,
    gender: str,
    output_filename: str,
    speaking_rate: float = 0.9,
    pitch: float = 0.0,
    volume_gain_db: float = 0.0
) -> Optional[str]:
    """Google Cloud TTS API 사용 (고품질)"""
    # 서비스 계정 인증 확인
    credentials_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
    if not credentials_path or not os.path.exists(credentials_path):
        print("[WARNING] GOOGLE_APPLICATION_CREDENTIALS not set or file not found")
        print("[FALLBACK] Using gTTS instead")
        return _generate_gtts(text, output_filename, speaking_rate)

    try:
        from google.cloud import texttospeech

        client = texttospeech.TextToSpeechClient()

        # Voice ID 결정
        voice_id = get_tts_voice_id(gender)

        # 입력 설정
        synthesis_input = texttospeech.SynthesisInput(text=text)

        # 음성 설정
        voice = texttospeech.VoiceSelectionParams(
            language_code="ko-KR",
            name=voice_id
        )

        # 오디오 설정
        audio_config = texttospeech.AudioConfig(
            audio_encoding=texttospeech.AudioEncoding.MP3,
            speaking_rate=speaking_rate,
            pitch=pitch,
            volume_gain_db=volume_gain_db
        )

        print(f"[Google TTS] Generating: {output_filename}")
        print(f"[Google TTS] Voice: {voice_id}, Rate: {speaking_rate}")

        # API 호출
        response = client.synthesize_speech(
            input=synthesis_input,
            voice=voice,
            audio_config=audio_config
        )

        # 출력 디렉토리 생성
        os.makedirs(os.path.dirname(output_filename), exist_ok=True)

        # 파일 저장
        with open(output_filename, "wb") as out:
            out.write(response.audio_content)

        print(f"[Google TTS] Saved: {output_filename}")
        return output_filename

    except ImportError:
        print("[ERROR] google-cloud-texttospeech not installed")
        print("[FALLBACK] Using gTTS instead")
        return _generate_gtts(text, output_filename, speaking_rate)
    except Exception as e:
        print(f"[ERROR] Google Cloud TTS failed: {e}")
        print("[FALLBACK] Using gTTS instead")
        return _generate_gtts(text, output_filename, speaking_rate)


def _generate_gtts(
    text: str,
    output_filename: str,
    speaking_rate: float = 0.9
) -> Optional[str]:
    """gTTS (Google Translate TTS) 사용 - 무료"""
    try:
        from gtts import gTTS

        print(f"[gTTS] Generating: {output_filename}")
        print(f"[gTTS] Text length: {len(text)} chars")

        # 출력 디렉토리 생성
        os.makedirs(os.path.dirname(output_filename), exist_ok=True)

        # gTTS는 speaking_rate를 직접 지원하지 않음
        # slow=True 옵션만 있음
        slow = speaking_rate < 0.85

        tts = gTTS(text=text, lang='ko', slow=slow)
        tts.save(output_filename)

        print(f"[gTTS] Saved: {output_filename}")
        return output_filename

    except ImportError:
        print("[ERROR] gtts not installed. Install with: pip install gtts")
        return None
    except Exception as e:
        print(f"[ERROR] gTTS failed: {e}")
        return None


def get_audio_duration(audio_path: str) -> float:
    """
    오디오 파일의 실제 재생 시간 측정

    Args:
        audio_path: 오디오 파일 경로

    Returns:
        재생 시간(초)
    """
    try:
        from mutagen.mp3 import MP3
        audio = MP3(audio_path)
        return audio.info.length
    except ImportError:
        # mutagen이 없으면 추정치 사용
        return estimate_audio_duration_from_file(audio_path)
    except Exception:
        return 0.0


def estimate_audio_duration_from_file(audio_path: str) -> float:
    """파일 크기 기반 재생 시간 추정 (MP3 128kbps 기준)"""
    try:
        file_size = os.path.getsize(audio_path)
        # MP3 128kbps = 16KB per second
        return file_size / 16000
    except Exception:
        return 0.0


def estimate_audio_duration(text: str, speaking_rate: float = 0.9) -> float:
    """
    문자열 길이를 기준으로 대략적인 재생 시간 추정

    Args:
        text: 문자열
        speaking_rate: 읽기 속도

    Returns:
        예상 재생 시간(초)
    """
    if not text:
        return 0.0

    # 한글 기준 분당 글자 수 추정
    # 기본 속도(1.0)에서 분당 약 150자
    # speaking_rate 0.9면 약간 느려서 분당 약 135자
    char_count = len(text.replace(" ", "").replace("\n", ""))
    chars_per_minute = 150 * speaking_rate

    duration_seconds = (char_count / chars_per_minute) * 60

    return round(duration_seconds, 1)


if __name__ == "__main__":
    # 테스트
    test_text = "안녕하세요. 오늘은 옛날 우리 동네에 있던 작은 이발소 이야기를 들려드릴게요."

    result = generate_tts(test_text, "male", "outputs/test_audio.mp3")
    print(f"Result: {result}")

    duration = estimate_audio_duration(test_text)
    print(f"Estimated duration: {duration} seconds")
