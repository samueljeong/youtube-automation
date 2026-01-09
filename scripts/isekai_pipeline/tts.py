"""
이세계 파이프라인 - TTS 모듈 (ElevenLabs + Gemini TTS + Chirp3)

- ElevenLabs TTS (V2 모델) 기본
- Gemini TTS (스타일 지침 지원) - 감정 표현 강화
- Google Chirp3 HD 폴백
- 씬/감정별 속도 및 스타일 조절 지원
"""

import os
import re
import base64
import subprocess
import tempfile
import time
import requests
from typing import Dict, Any, List, Tuple


# ElevenLabs 설정
DEFAULT_VOICE_ID = "aurnUodFzOtofecLd3T1"  # Jung_Narrative
ELEVENLABS_API_URL = "https://api.elevenlabs.io/v1/text-to-speech"
ELEVENLABS_MODEL = "eleven_multilingual_v2"

# Google Chirp3 HD 폴백 설정
TTS_API_URL = "https://texttospeech.googleapis.com/v1/text:synthesize"

# 감정별 TTS 속도 설정 (0.25 ~ 4.0)
EMOTION_SPEED = {
    "nostalgic": 0.92,
    "sad": 0.88,
    "calm": 0.95,
    "romantic": 0.90,
    "tense": 1.05,
    "fight": 1.10,
    "epic": 1.02,
    "dramatic": 0.95,
    "mysterious": 0.93,
    "hopeful": 0.98,
    "default": 1.0,
}

# 감정별 ElevenLabs 설정 (stability, similarity_boost)
EMOTION_SETTINGS = {
    "nostalgic": {"stability": 0.40, "similarity_boost": 0.80},
    "sad": {"stability": 0.35, "similarity_boost": 0.75},
    "calm": {"stability": 0.55, "similarity_boost": 0.70},
    "romantic": {"stability": 0.40, "similarity_boost": 0.80},
    "tense": {"stability": 0.50, "similarity_boost": 0.85},
    "fight": {"stability": 0.60, "similarity_boost": 0.90},
    "epic": {"stability": 0.55, "similarity_boost": 0.85},
    "dramatic": {"stability": 0.45, "similarity_boost": 0.80},
    "mysterious": {"stability": 0.40, "similarity_boost": 0.75},
    "hopeful": {"stability": 0.50, "similarity_boost": 0.80},
    "default": {"stability": 0.50, "similarity_boost": 0.75},
}

SCENE_MARKER_PATTERN = re.compile(r'\[SCENE:([^:]+):([^:]+):([^\]]+)\]')

# Gemini TTS 설정
GEMINI_TTS_MODEL = "gemini-2.5-flash-preview-tts"
GEMINI_TTS_API_URL = "https://generativelanguage.googleapis.com/v1beta/models"

# Gemini TTS 보이스 (한국어 추천)
GEMINI_VOICES = {
    "default": "Kore",      # 기본 한국어
    "male": "Orus",         # 남성
    "female": "Aoede",      # 여성
    "dramatic": "Charon",   # 드라마틱
    "calm": "Puck",         # 차분
}

# 감정별 스타일 지침 (Gemini TTS용)
EMOTION_STYLE_PROMPTS = {
    "nostalgic": "과거를 회상하는 듯한 따뜻하고 그리운 목소리로, 약간 느리고 감성적으로",
    "sad": "슬프고 침울한 목소리로, 천천히 말하며 감정을 담아서",
    "calm": "차분하고 안정적인 목소리로, 편안하게",
    "romantic": "부드럽고 따뜻한 목소리로, 사랑이 담긴 톤으로",
    "tense": "긴장감 있고 급박한 목소리로, 숨이 가쁜 듯이 빠르게",
    "fight": "격렬하고 힘찬 목소리로, 전투의 긴장감을 담아 빠르고 강하게",
    "epic": "웅장하고 장엄한 목소리로, 영웅서사시를 낭독하듯이",
    "dramatic": "극적이고 감정이 고조된 목소리로, 강약 조절을 살려서",
    "mysterious": "신비롭고 속삭이는 듯한 목소리로, 미스터리한 분위기로",
    "hopeful": "희망적이고 밝은 목소리로, 기대감을 담아서",
    "default": "자연스럽고 명확한 목소리로",
}


def parse_scenes(script: str) -> List[Dict[str, Any]]:
    """대본에서 씬 마커를 파싱하여 씬 목록 반환"""
    scenes = []
    parts = SCENE_MARKER_PATTERN.split(script)

    if len(parts) == 1:
        return [{"name": "default", "emotion": "default", "bgm": "calm", "text": script.strip()}]

    if parts[0].strip():
        scenes.append({
            "name": "intro",
            "emotion": "default",
            "bgm": "calm",
            "text": parts[0].strip()
        })

    i = 1
    while i + 3 <= len(parts):
        scene_name = parts[i].strip()
        emotion = parts[i + 1].strip().lower()
        bgm = parts[i + 2].strip().lower()
        text = parts[i + 3].strip() if i + 3 < len(parts) else ""

        if text:
            scenes.append({
                "name": scene_name,
                "emotion": emotion,
                "bgm": bgm,
                "text": text
            })
        i += 4

    return scenes


def split_into_sentences(text: str) -> List[str]:
    """텍스트를 문장 단위로 분할"""
    sentences = re.split(r'(?<=[.!?])\s+', text.strip())
    return [s.strip() for s in sentences if s.strip()]


def get_audio_duration(audio_path: str) -> float:
    """오디오 파일의 재생 시간(초) 반환"""
    try:
        from mutagen.mp3 import MP3
        audio = MP3(audio_path)
        return audio.info.length
    except Exception:
        pass

    try:
        result = subprocess.run(
            ['ffprobe', '-v', 'error', '-show_entries', 'format=duration',
             '-of', 'default=noprint_wrappers=1:nokey=1', audio_path],
            capture_output=True, text=True, timeout=30
        )
        return float(result.stdout.strip()) if result.stdout.strip() else 0.0
    except Exception:
        return 0.0


def merge_audio_files(audio_paths: List[str], output_path: str) -> bool:
    """여러 오디오 파일을 하나로 합침"""
    if not audio_paths:
        return False

    if len(audio_paths) == 1:
        import shutil
        shutil.copy(audio_paths[0], output_path)
        return True

    try:
        from pydub import AudioSegment
        combined = AudioSegment.empty()
        for path in audio_paths:
            audio = AudioSegment.from_mp3(path)
            combined += audio
        combined.export(output_path, format="mp3", bitrate="128k")
        return os.path.exists(output_path)
    except Exception:
        pass

    try:
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            for path in audio_paths:
                f.write(f"file '{path}'\n")
            list_path = f.name

        subprocess.run(
            ['ffmpeg', '-y', '-f', 'concat', '-safe', '0', '-i', list_path,
             '-c:a', 'libmp3lame', '-b:a', '128k', output_path],
            capture_output=True, timeout=300
        )
        os.unlink(list_path)
        return os.path.exists(output_path)
    except Exception:
        pass

    try:
        with open(output_path, 'wb') as outfile:
            for path in audio_paths:
                with open(path, 'rb') as infile:
                    outfile.write(infile.read())
        return os.path.exists(output_path)
    except Exception:
        return False


def generate_srt(timeline: List[Tuple[float, float, str]], output_path: str):
    """타임라인으로 SRT 파일 생성"""
    def format_time(seconds: float) -> str:
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        millis = int((seconds % 1) * 1000)
        return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"

    with open(output_path, 'w', encoding='utf-8') as f:
        for i, (start, end, text) in enumerate(timeline, 1):
            f.write(f"{i}\n")
            f.write(f"{format_time(start)} --> {format_time(end)}\n")
            f.write(f"{text}\n\n")


def generate_elevenlabs_tts_chunk(
    text: str,
    voice_id: str,
    api_key: str,
    stability: float = 0.5,
    similarity_boost: float = 0.75,
) -> Dict[str, Any]:
    """ElevenLabs TTS API로 청크 생성"""
    url = f"{ELEVENLABS_API_URL}/{voice_id}"

    headers = {
        "Accept": "audio/mpeg",
        "Content-Type": "application/json",
        "xi-api-key": api_key
    }

    payload = {
        "text": text,
        "model_id": ELEVENLABS_MODEL,
        "voice_settings": {
            "stability": stability,
            "similarity_boost": similarity_boost,
        }
    }

    try:
        response = requests.post(url, json=payload, headers=headers, timeout=120)

        if response.status_code == 200:
            return {"ok": True, "audio_data": response.content}
        else:
            error_msg = response.text[:300] if response.text else f"HTTP {response.status_code}"
            return {"ok": False, "error": f"ElevenLabs API 오류: {error_msg}"}

    except Exception as e:
        return {"ok": False, "error": str(e)}


def generate_chirp3_tts_chunk(
    text: str,
    voice_name: str,
    api_key: str,
    speaking_rate: float = 1.0
) -> Dict[str, Any]:
    """Google Cloud TTS REST API로 Chirp3 HD 청크 생성 (폴백용)"""
    url = f"{TTS_API_URL}?key={api_key}"
    lang_code = "-".join(voice_name.split("-")[:2])
    speaking_rate = max(0.25, min(4.0, speaking_rate))

    payload = {
        "input": {"text": text},
        "voice": {
            "languageCode": lang_code,
            "name": voice_name
        },
        "audioConfig": {
            "audioEncoding": "MP3",
            "sampleRateHertz": 24000,
            "speakingRate": speaking_rate,
        }
    }

    try:
        response = requests.post(url, json=payload, timeout=60)

        if response.status_code == 200:
            result = response.json()
            audio_content = result.get("audioContent", "")
            if audio_content:
                audio_data = base64.b64decode(audio_content)
                return {"ok": True, "audio_data": audio_data}
            return {"ok": False, "error": "오디오 데이터 없음"}
        else:
            error_msg = response.text[:300] if response.text else f"HTTP {response.status_code}"
            return {"ok": False, "error": f"TTS API 오류: {error_msg}"}

    except Exception as e:
        return {"ok": False, "error": str(e)}


def generate_gemini_tts_chunk(
    text: str,
    style_prompt: str,
    voice_name: str,
    api_key: str,
) -> Dict[str, Any]:
    """
    Gemini TTS API로 스타일 지침이 적용된 청크 생성

    Args:
        text: TTS로 변환할 텍스트
        style_prompt: 스타일 지침 (예: "긴장감 있고 급박한 목소리로")
        voice_name: Gemini 보이스 이름 (Kore, Orus, Puck 등)
        api_key: Google API 키

    Returns:
        {"ok": True, "audio_data": bytes} 또는 {"ok": False, "error": str}
    """
    url = f"{GEMINI_TTS_API_URL}/{GEMINI_TTS_MODEL}:generateContent?key={api_key}"

    # 스타일 지침 + 텍스트 결합
    content = f"{style_prompt}: {text}"

    payload = {
        "contents": [{"parts": [{"text": content}]}],
        "generationConfig": {
            "responseModalities": ["AUDIO"],
            "speechConfig": {
                "voiceConfig": {
                    "prebuiltVoiceConfig": {
                        "voiceName": voice_name
                    }
                }
            }
        }
    }

    headers = {"Content-Type": "application/json"}

    try:
        response = requests.post(url, json=payload, headers=headers, timeout=120)

        if response.status_code == 200:
            result = response.json()

            # 응답에서 오디오 데이터 추출
            candidates = result.get("candidates", [])
            if candidates:
                content_parts = candidates[0].get("content", {}).get("parts", [])
                for part in content_parts:
                    if "inlineData" in part:
                        audio_b64 = part["inlineData"].get("data", "")
                        if audio_b64:
                            audio_data = base64.b64decode(audio_b64)
                            return {"ok": True, "audio_data": audio_data, "format": "wav"}

            return {"ok": False, "error": "응답에 오디오 데이터 없음"}
        else:
            error_msg = response.text[:500] if response.text else f"HTTP {response.status_code}"
            return {"ok": False, "error": f"Gemini TTS API 오류: {error_msg}"}

    except Exception as e:
        return {"ok": False, "error": str(e)}


def convert_pcm_to_mp3(pcm_data: bytes, output_path: str, sample_rate: int = 24000) -> bool:
    """
    Raw PCM 데이터를 MP3 파일로 변환
    Gemini TTS는 WAV 헤더 없는 raw PCM (24kHz, 16-bit, mono)을 반환함
    """
    pcm_path = None
    try:
        with tempfile.NamedTemporaryFile(suffix='.pcm', delete=False) as pcm_file:
            pcm_file.write(pcm_data)
            pcm_path = pcm_file.name

        print(f"[PCM→MP3] PCM 크기: {len(pcm_data)} bytes, 파일: {pcm_path}")

        # raw PCM → MP3 변환 (16-bit signed little-endian, mono)
        result = subprocess.run(
            ['ffmpeg', '-y',
             '-f', 's16le',           # 16-bit signed little-endian
             '-ar', str(sample_rate), # sample rate
             '-ac', '1',              # mono
             '-i', pcm_path,
             '-codec:a', 'libmp3lame',
             '-b:a', '128k',
             output_path],
            capture_output=True, timeout=60, text=True
        )

        if pcm_path and os.path.exists(pcm_path):
            os.unlink(pcm_path)

        if result.returncode != 0:
            print(f"[PCM→MP3] ffmpeg 실패: {result.stderr}")
            return False

        return os.path.exists(output_path)
    except Exception as e:
        print(f"[PCM→MP3] 예외 발생: {e}")
        if pcm_path and os.path.exists(pcm_path):
            os.unlink(pcm_path)
        return False


def convert_wav_to_mp3(wav_data: bytes, output_path: str) -> bool:
    """WAV 또는 PCM 데이터를 MP3 파일로 변환"""
    # WAV 헤더 확인 (RIFF로 시작)
    if wav_data[:4] == b'RIFF':
        # 표준 WAV 파일
        try:
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as wav_file:
                wav_file.write(wav_data)
                wav_path = wav_file.name

            result = subprocess.run(
                ['ffmpeg', '-y', '-i', wav_path, '-codec:a', 'libmp3lame', '-b:a', '128k', output_path],
                capture_output=True, timeout=60
            )

            os.unlink(wav_path)
            return os.path.exists(output_path)
        except Exception:
            return False
    else:
        # Raw PCM 데이터 (Gemini TTS)
        return convert_pcm_to_mp3(wav_data, output_path)


def generate_tts(
    episode_id: str,
    script: str,
    output_dir: str,
    voice: str = "Jung_Narrative",
    speed: float = 1.0,
    provider: str = "auto",  # "elevenlabs", "gemini", "chirp3", "auto"
) -> Dict[str, Any]:
    """
    대본에 대해 TTS 생성

    Args:
        episode_id: 에피소드 ID (예: "EP001")
        script: 대본 텍스트 (SCENE 마커 포함 가능)
        output_dir: 출력 디렉토리
        voice: 보이스 설정
        speed: 속도 배율
        provider: TTS 제공자
            - "elevenlabs": ElevenLabs (기본)
            - "gemini": Gemini TTS (스타일 지침 지원)
            - "chirp3": Google Chirp3 HD
            - "auto": 환경변수에 따라 자동 선택

    Returns:
        {"ok": True, "audio_path": str, ...} 또는 {"ok": False, "error": str}
    """
    elevenlabs_api_key = os.environ.get('ELEVENLABS_API_KEY')
    google_api_key = os.environ.get('GOOGLE_API_KEY') or os.environ.get('GOOGLE_CLOUD_API_KEY')

    # provider 결정
    if provider == "auto":
        if elevenlabs_api_key:
            provider = "elevenlabs"
        elif google_api_key:
            provider = "gemini"  # gemini 우선 (스타일 지침 지원)
        else:
            return {"ok": False, "error": "ELEVENLABS_API_KEY 또는 GOOGLE_API_KEY 환경변수가 필요합니다"}
    elif provider == "gemini" and not google_api_key:
        return {"ok": False, "error": "Gemini TTS를 사용하려면 GOOGLE_API_KEY가 필요합니다"}
    elif provider == "elevenlabs" and not elevenlabs_api_key:
        return {"ok": False, "error": "ElevenLabs TTS를 사용하려면 ELEVENLABS_API_KEY가 필요합니다"}
    elif provider == "chirp3" and not google_api_key:
        return {"ok": False, "error": "Chirp3 TTS를 사용하려면 GOOGLE_API_KEY가 필요합니다"}

    os.makedirs(output_dir, exist_ok=True)

    # 보이스 설정
    if provider == "elevenlabs":
        voice_id = voice if len(voice) > 15 else DEFAULT_VOICE_ID
        print(f"[ISEKAI-TTS] ElevenLabs 사용: {voice_id}")
    elif provider == "gemini":
        # Gemini 보이스 선택
        gemini_voice = GEMINI_VOICES.get(voice, voice)
        if gemini_voice not in ["Zephyr", "Puck", "Charon", "Kore", "Fenrir", "Leda", "Orus", "Aoede"]:
            gemini_voice = "Kore"  # 기본값
        print(f"[ISEKAI-TTS] Gemini TTS 사용: {gemini_voice} (스타일 지침 활성화)")
    else:  # chirp3
        voice_short = voice.split(":")[-1] if ":" in voice else voice
        valid_voices = ["Kore", "Charon", "Puck", "Fenrir", "Aoede", "Orus", "Leda", "Zephyr"]
        if voice_short not in valid_voices:
            voice_short = "Charon"
        voice_name = f"ko-KR-Chirp3-HD-{voice_short}"
        print(f"[ISEKAI-TTS] Google Chirp3 사용: {voice_name}")

    scenes = parse_scenes(script)
    print(f"[ISEKAI-TTS] {len(scenes)}개 씬 감지")
    for scene in scenes:
        emotion_speed = EMOTION_SPEED.get(scene["emotion"], 1.0)
        print(f"  - {scene['name']}: 감정={scene['emotion']}, BGM={scene['bgm']}, 속도={emotion_speed}")

    audio_paths = []
    timeline = []
    scene_timeline = []
    current_time = 0.0
    failed_count = 0
    chunk_index = 0

    with tempfile.TemporaryDirectory() as temp_dir:
        for scene in scenes:
            scene_start = current_time
            scene_text = scene["text"]
            emotion = scene["emotion"]
            bgm = scene["bgm"]

            emotion_speed = EMOTION_SPEED.get(emotion, 1.0) * speed
            emotion_setting = EMOTION_SETTINGS.get(emotion, EMOTION_SETTINGS["default"])
            print(f"[ISEKAI-TTS] 씬 '{scene['name']}' 처리 중 (감정: {emotion})")

            sentences = split_into_sentences(scene_text)

            # provider별 청크 크기 설정
            if provider == "elevenlabs":
                MAX_CHARS = 4500
            elif provider == "gemini":
                MAX_CHARS = 3500  # Gemini는 스타일 프롬프트 포함하므로 여유 필요
            else:  # chirp3
                MAX_CHARS = 1400

            chunks = []
            current_chunk = ""
            current_sentences = []

            for sentence in sentences:
                if len(current_chunk) + len(sentence) + 1 <= MAX_CHARS:
                    current_chunk += " " + sentence if current_chunk else sentence
                    current_sentences.append(sentence)
                else:
                    if current_chunk:
                        chunks.append((current_chunk.strip(), list(current_sentences)))
                    current_chunk = sentence
                    current_sentences = [sentence]

            if current_chunk:
                chunks.append((current_chunk.strip(), list(current_sentences)))

            # Gemini용 스타일 지침 가져오기
            style_prompt = EMOTION_STYLE_PROMPTS.get(emotion, EMOTION_STYLE_PROMPTS["default"])

            for chunk, chunk_sentences in chunks:
                if not chunk:
                    continue

                result = None
                for retry in range(3):
                    if provider == "elevenlabs":
                        result = generate_elevenlabs_tts_chunk(
                            chunk, voice_id, elevenlabs_api_key,
                            stability=emotion_setting["stability"],
                            similarity_boost=emotion_setting["similarity_boost"]
                        )
                    elif provider == "gemini":
                        result = generate_gemini_tts_chunk(
                            chunk, style_prompt, gemini_voice, google_api_key
                        )
                    else:  # chirp3
                        result = generate_chirp3_tts_chunk(
                            chunk, voice_name, google_api_key,
                            speaking_rate=emotion_speed
                        )
                    if result.get("ok"):
                        break
                    time.sleep(1 if provider == "elevenlabs" else 0.5)

                if not result.get("ok"):
                    print(f"[ISEKAI-TTS] 청크 {chunk_index+1} 실패: {result.get('error')}")
                    failed_count += 1
                    if failed_count >= 3:
                        return {"ok": False, "error": f"TTS 연속 실패: {result.get('error')}"}
                    continue

                # Gemini는 WAV로 반환하므로 MP3 변환 필요
                mp3_path = os.path.join(temp_dir, f"chunk_{chunk_index:04d}.mp3")
                if result.get("format") == "wav":
                    if not convert_wav_to_mp3(result["audio_data"], mp3_path):
                        print(f"[ISEKAI-TTS] WAV→MP3 변환 실패")
                        continue
                else:
                    with open(mp3_path, 'wb') as f:
                        f.write(result["audio_data"])

                duration = get_audio_duration(mp3_path)
                if duration > 0:
                    audio_paths.append(mp3_path)

                    total_chars = sum(len(s) for s in chunk_sentences)
                    chunk_start = current_time

                    for sentence in chunk_sentences:
                        sentence_ratio = len(sentence) / total_chars if total_chars > 0 else 1
                        sentence_duration = duration * sentence_ratio
                        timeline.append((chunk_start, chunk_start + sentence_duration, sentence))
                        chunk_start += sentence_duration

                    current_time += duration
                    failed_count = 0

                chunk_index += 1

            scene_timeline.append({
                "name": scene["name"],
                "emotion": emotion,
                "bgm": bgm,
                "start": scene_start,
                "end": current_time,
            })

        if not audio_paths:
            return {"ok": False, "error": "TTS 생성 실패"}

        audio_output = os.path.join(output_dir, f"{episode_id}.mp3")
        if not merge_audio_files(audio_paths, audio_output):
            return {"ok": False, "error": "오디오 병합 실패"}

        srt_dir = os.path.join(os.path.dirname(output_dir), "subtitles")
        os.makedirs(srt_dir, exist_ok=True)
        srt_output = os.path.join(srt_dir, f"{episode_id}.srt")
        generate_srt(timeline, srt_output)

        total_duration = get_audio_duration(audio_output)

        tts_type_names = {
            "elevenlabs": "ElevenLabs",
            "gemini": "Gemini TTS",
            "chirp3": "Google Chirp3"
        }
        tts_type = tts_type_names.get(provider, provider)
        print(f"[ISEKAI-TTS] 완료 ({tts_type}): {total_duration:.1f}초, {len(timeline)}개 자막")
        print(f"[ISEKAI-TTS] 씬 타임라인:")
        for st in scene_timeline:
            print(f"  - {st['name']}: {st['start']:.1f}s ~ {st['end']:.1f}s (BGM: {st['bgm']})")

        return {
            "ok": True,
            "audio_path": audio_output,
            "srt_path": srt_output,
            "duration": total_duration,
            "timeline": timeline,
            "scene_timeline": scene_timeline,
            "provider": provider,
        }


def generate_hybrid_tts(
    episode_id: str,
    script: str,
    output_dir: str,
    voice_id: str = None,
) -> Dict[str, Any]:
    """
    하이브리드 TTS 생성 (ElevenLabs 나레이션 + Gemini TTS 대사)

    Args:
        episode_id: 에피소드 ID (예: "EP001")
        script: 원본 대본 텍스트 (태그 없는 순수 텍스트)
        output_dir: 출력 디렉토리
        voice_id: ElevenLabs 보이스 ID (없으면 기본값)

    Returns:
        {"ok": True, "audio_path": str, ...} 또는 {"ok": False, "error": str}
    """
    from scripts.isekai_pipeline.script_parser import (
        parse_script_with_ai,
        get_voice_for_character,
        get_style_for_emotion,
    )

    elevenlabs_api_key = os.environ.get('ELEVENLABS_API_KEY')
    google_api_key = os.environ.get('GOOGLE_API_KEY')

    if not elevenlabs_api_key:
        return {"ok": False, "error": "ELEVENLABS_API_KEY 환경변수가 필요합니다"}
    if not google_api_key:
        return {"ok": False, "error": "GOOGLE_API_KEY 환경변수가 필요합니다"}

    voice_id = voice_id or DEFAULT_VOICE_ID
    os.makedirs(output_dir, exist_ok=True)

    print(f"[HYBRID-TTS] 대본 파싱 중...")
    parse_result = parse_script_with_ai(script, google_api_key)

    if not parse_result.get("ok"):
        return {"ok": False, "error": f"파싱 실패: {parse_result.get('error')}"}

    dialogues = parse_result.get("dialogues", [])
    print(f"[HYBRID-TTS] {len(dialogues)}개 대사 추출됨")

    # 대사 텍스트를 플레이스홀더로 대체한 나레이션 텍스트 생성
    narration_script = script
    dialogue_markers = []

    for i, d in enumerate(dialogues):
        dialogue_text = d["text"]
        marker = f"[DLG_{i:03d}]"
        dialogue_markers.append({
            "marker": marker,
            "text": dialogue_text,
            "speaker": d["speaker"],
            "emotion": d["emotion"],
        })

        # 원본에서 따옴표 포함된 대사를 마커로 대체
        patterns = [
            f'"{dialogue_text}"',
            f"'{dialogue_text}'",
            f'「{dialogue_text}」',
        ]
        for pattern in patterns:
            if pattern in narration_script:
                narration_script = narration_script.replace(pattern, marker, 1)
                break

    print(f"[HYBRID-TTS] 나레이션 TTS 생성 중 (ElevenLabs)...")

    # 나레이션을 문장 단위로 분할
    audio_segments = []
    timeline = []
    current_time = 0.0

    with tempfile.TemporaryDirectory() as temp_dir:
        # 나레이션과 대사 마커를 순서대로 처리
        parts = re.split(r'(\[DLG_\d{3}\])', narration_script)
        segment_index = 0

        for part in parts:
            part = part.strip()
            if not part:
                continue

            # 대사 마커인 경우
            if re.match(r'\[DLG_\d{3}\]', part):
                marker_idx = int(part[5:8])
                d = dialogue_markers[marker_idx]

                print(f"[HYBRID-TTS] 대사 {marker_idx+1}/{len(dialogues)}: [{d['speaker']}:{d['emotion']}]")

                voice = get_voice_for_character(d["speaker"])
                style = get_style_for_emotion(d["emotion"])

                # Gemini TTS로 대사 생성
                result = None
                for retry in range(3):
                    result = generate_gemini_tts_chunk(d["text"], style, voice, google_api_key)
                    if result.get("ok"):
                        break
                    time.sleep(1)

                if result and result.get("ok"):
                    mp3_path = os.path.join(temp_dir, f"segment_{segment_index:04d}_dlg.mp3")
                    if convert_wav_to_mp3(result["audio_data"], mp3_path):
                        duration = get_audio_duration(mp3_path)
                        if duration > 0:
                            audio_segments.append(mp3_path)
                            timeline.append((current_time, current_time + duration, d["text"]))
                            current_time += duration
                            segment_index += 1
                else:
                    print(f"[HYBRID-TTS] 대사 실패: {result.get('error') if result else 'Unknown'}")

            # 나레이션인 경우
            else:
                sentences = split_into_sentences(part)
                MAX_CHARS = 4500
                chunks = []
                current_chunk = ""

                for sentence in sentences:
                    if len(current_chunk) + len(sentence) + 1 <= MAX_CHARS:
                        current_chunk += " " + sentence if current_chunk else sentence
                    else:
                        if current_chunk:
                            chunks.append(current_chunk.strip())
                        current_chunk = sentence
                if current_chunk:
                    chunks.append(current_chunk.strip())

                for chunk in chunks:
                    if not chunk:
                        continue

                    result = None
                    for retry in range(3):
                        result = generate_elevenlabs_tts_chunk(
                            chunk, voice_id, elevenlabs_api_key,
                            stability=0.50, similarity_boost=0.75
                        )
                        if result.get("ok"):
                            break
                        time.sleep(1)

                    if result and result.get("ok"):
                        mp3_path = os.path.join(temp_dir, f"segment_{segment_index:04d}_nar.mp3")
                        with open(mp3_path, 'wb') as f:
                            f.write(result["audio_data"])

                        duration = get_audio_duration(mp3_path)
                        if duration > 0:
                            audio_segments.append(mp3_path)

                            # 문장별 타임라인
                            chunk_sentences = split_into_sentences(chunk)
                            total_chars = sum(len(s) for s in chunk_sentences)
                            chunk_start = current_time

                            for sentence in chunk_sentences:
                                sentence_ratio = len(sentence) / total_chars if total_chars > 0 else 1
                                sentence_duration = duration * sentence_ratio
                                timeline.append((chunk_start, chunk_start + sentence_duration, sentence))
                                chunk_start += sentence_duration

                            current_time += duration
                            segment_index += 1

        if not audio_segments:
            return {"ok": False, "error": "TTS 생성 실패 (세그먼트 없음)"}

        # 오디오 병합
        audio_output = os.path.join(output_dir, f"{episode_id}_hybrid.mp3")
        if not merge_audio_files(audio_segments, audio_output):
            return {"ok": False, "error": "오디오 병합 실패"}

        # SRT 생성
        srt_dir = os.path.join(os.path.dirname(output_dir), "subtitles")
        os.makedirs(srt_dir, exist_ok=True)
        srt_output = os.path.join(srt_dir, f"{episode_id}_hybrid.srt")
        generate_srt(timeline, srt_output)

        total_duration = get_audio_duration(audio_output)

        print(f"[HYBRID-TTS] 완료: {total_duration:.1f}초, {len(timeline)}개 자막")
        print(f"[HYBRID-TTS] 나레이션: ElevenLabs, 대사 {len(dialogues)}개: Gemini TTS")

        return {
            "ok": True,
            "audio_path": audio_output,
            "srt_path": srt_output,
            "duration": total_duration,
            "timeline": timeline,
            "dialogues_count": len(dialogues),
            "provider": "hybrid",
        }


if __name__ == "__main__":
    print("isekai_pipeline/tts.py - ElevenLabs + Gemini TTS + Chirp3 + Hybrid")
