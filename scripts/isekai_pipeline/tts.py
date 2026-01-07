"""
이세계 파이프라인 - TTS 모듈 (Chirp3 HD - API Key 방식)

- Google Cloud TTS Chirp3 HD (고품질 한국어)
- GOOGLE_API_KEY 또는 GOOGLE_CLOUD_API_KEY 환경변수 사용
- REST API 방식 (서비스 계정 불필요)
"""

import os
import re
import json
import base64
import subprocess
import tempfile
import time
import requests
from typing import Dict, Any, List, Tuple


# TTS 설정
DEFAULT_VOICE = "ko-KR-Chirp3-HD-Charon"  # Chirp3 HD 남성
TTS_API_URL = "https://texttospeech.googleapis.com/v1/text:synthesize"


def split_into_sentences(text: str) -> List[str]:
    """텍스트를 문장 단위로 분할"""
    sentences = re.split(r'(?<=[.!?])\s+', text.strip())
    return [s.strip() for s in sentences if s.strip()]


def get_audio_duration(audio_path: str) -> float:
    """오디오 파일의 재생 시간(초) 반환"""
    # mutagen 사용 (ffprobe 불필요)
    try:
        from mutagen.mp3 import MP3
        audio = MP3(audio_path)
        return audio.info.length
    except Exception:
        pass

    # fallback: ffprobe
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

    # 방법 1: pydub 사용 (권장)
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

    # 방법 2: ffmpeg concat
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

    # 방법 3: 단순 바이너리 병합 (fallback)
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


def generate_chirp3_tts_chunk(text: str, voice_name: str, api_key: str) -> Dict[str, Any]:
    """Google Cloud TTS REST API로 Chirp3 HD 청크 생성"""
    url = f"{TTS_API_URL}?key={api_key}"

    # 언어 코드 추출 (ko-KR-Chirp3-HD-Charon → ko-KR)
    lang_code = "-".join(voice_name.split("-")[:2])

    payload = {
        "input": {"text": text},
        "voice": {
            "languageCode": lang_code,
            "name": voice_name
        },
        "audioConfig": {
            "audioEncoding": "MP3",
            "sampleRateHertz": 24000
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


def generate_tts(
    episode_id: str,
    script: str,
    output_dir: str,
    voice: str = "Charon",
    speed: float = 1.0,
) -> Dict[str, Any]:
    """
    대본에 대해 TTS 생성 (Chirp3 HD REST API)

    Args:
        episode_id: 에피소드 ID (예: "ep001")
        script: 대본 텍스트
        output_dir: 출력 디렉토리
        voice: 음성 (Charon, Kore, Puck, Fenrir, Aoede)
        speed: 속도 (현재 미사용)

    Returns:
        {"ok": True, "audio_path": "...", "srt_path": "...", "duration": 900.5}
    """
    api_key = os.environ.get('GOOGLE_API_KEY') or os.environ.get('GOOGLE_CLOUD_API_KEY')
    if not api_key:
        return {"ok": False, "error": "GOOGLE_API_KEY 환경변수가 필요합니다"}

    os.makedirs(output_dir, exist_ok=True)

    # 음성 이름 생성 (Charon → ko-KR-Chirp3-HD-Charon)
    voice_short = voice.split(":")[-1] if ":" in voice else voice
    valid_voices = ["Kore", "Charon", "Puck", "Fenrir", "Aoede", "Orus", "Leda", "Zephyr"]
    if voice_short not in valid_voices:
        voice_short = "Charon"

    voice_name = f"ko-KR-Chirp3-HD-{voice_short}"
    print(f"[ISEKAI-TTS] 음성: {voice_name}")

    # 문장 분할
    sentences = split_into_sentences(script)
    print(f"[ISEKAI-TTS] {len(sentences)}개 문장 처리 중...")

    # 청크 병합 (5000바이트 ≈ 1400자)
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

    print(f"[ISEKAI-TTS] {len(chunks)}개 청크로 병합")

    audio_paths = []
    timeline = []
    current_time = 0.0
    failed_count = 0

    with tempfile.TemporaryDirectory() as temp_dir:
        for i, (chunk, chunk_sentences) in enumerate(chunks):
            if not chunk:
                continue

            # TTS 생성 (재시도 포함)
            result = None
            for retry in range(3):
                result = generate_chirp3_tts_chunk(chunk, voice_name, api_key)
                if result.get("ok"):
                    break
                time.sleep(1)

            if not result.get("ok"):
                print(f"[ISEKAI-TTS] 청크 {i+1} 실패: {result.get('error')}")
                failed_count += 1
                if failed_count >= 3:
                    return {"ok": False, "error": f"TTS 연속 실패: {result.get('error')}"}
                continue

            # MP3 저장
            mp3_path = os.path.join(temp_dir, f"chunk_{i:04d}.mp3")
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

            if (i + 1) % 3 == 0 or i == len(chunks) - 1:
                print(f"[ISEKAI-TTS] {i+1}/{len(chunks)} 완료 ({current_time:.1f}초)")

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
        print(f"[ISEKAI-TTS] 완료: {total_duration:.1f}초, {len(timeline)}개 자막")

        return {
            "ok": True,
            "audio_path": audio_output,
            "srt_path": srt_output,
            "duration": total_duration,
            "timeline": timeline,
        }


if __name__ == "__main__":
    print("isekai_pipeline/tts.py - Chirp3 HD (API Key)")
