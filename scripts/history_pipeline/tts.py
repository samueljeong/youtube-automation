"""
한국사 파이프라인 - TTS 모듈 (ElevenLabs)

- ElevenLabs TTS (multilingual_v2 모델)
- 문장 단위 자막 생성
- 독립 실행 가능
- ELEVENLABS_API_KEY 필요
"""

import os
import re
import tempfile
import subprocess
import time
import requests
from typing import Dict, Any, List, Tuple


# ElevenLabs 설정
DEFAULT_VOICE_ID = "aurnUodFzOtofecLd3T1"  # Jung_Narrative (이세계와 동일)
ELEVENLABS_API_URL = "https://api.elevenlabs.io/v1/text-to-speech"
ELEVENLABS_MODEL = "eleven_multilingual_v2"

# 기본 음성 설정
DEFAULT_STABILITY = 0.50
DEFAULT_SIMILARITY_BOOST = 0.75
DEFAULT_SPEED = 0.95  # 0.7 ~ 1.2 (한국사 다큐용 차분한 톤)


def split_into_sentences(text: str) -> List[str]:
    """텍스트를 문장 단위로 분할"""
    sentences = re.split(r'(?<=[.!?])\s+', text.strip())
    return [s.strip() for s in sentences if s.strip()]


def get_audio_duration(audio_path: str) -> float:
    """오디오 파일의 재생 시간(초) 반환"""
    # mutagen 먼저 시도 (더 정확)
    try:
        from mutagen.mp3 import MP3
        audio = MP3(audio_path)
        return audio.info.length
    except Exception:
        pass

    # ffprobe 시도
    try:
        result = subprocess.run(
            ['ffprobe', '-v', 'error', '-show_entries', 'format=duration',
             '-of', 'default=noprint_wrappers=1:nokey=1', audio_path],
            capture_output=True, text=True, timeout=30
        )
        duration = float(result.stdout.strip()) if result.stdout.strip() else 0.0
        if duration > 0:
            return duration
    except Exception:
        pass

    # 파일 크기로 추정 (MP3 128kbps 기준)
    try:
        file_size = os.path.getsize(audio_path)
        if file_size > 0:
            return file_size / 16000.0
    except Exception:
        pass

    return 0.0


def merge_audio_files(audio_paths: List[str], output_path: str) -> bool:
    """여러 오디오 파일을 하나로 합침"""
    if not audio_paths:
        return False

    if len(audio_paths) == 1:
        import shutil
        shutil.copy(audio_paths[0], output_path)
        return True

    # pydub 먼저 시도
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

    # ffmpeg 시도
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
        if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
            return True
    except Exception:
        pass

    # 순수 Python 바이너리 병합 (폴백)
    try:
        print("[HISTORY-TTS] 순수 Python으로 MP3 병합...")
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
    stability: float = DEFAULT_STABILITY,
    similarity_boost: float = DEFAULT_SIMILARITY_BOOST,
    speed: float = DEFAULT_SPEED,
    with_timestamps: bool = True,
) -> Dict[str, Any]:
    """ElevenLabs TTS API로 청크 생성 (타임스탬프 포함)"""
    url = f"{ELEVENLABS_API_URL}/{voice_id}/with-timestamps"

    headers = {
        "Content-Type": "application/json",
        "xi-api-key": api_key
    }

    # 속도 범위 제한 (0.7 ~ 1.2)
    speed = max(0.7, min(1.2, speed))

    payload = {
        "text": text,
        "model_id": ELEVENLABS_MODEL,
        "voice_settings": {
            "stability": stability,
            "similarity_boost": similarity_boost,
            "speed": speed,
        }
    }

    try:
        response = requests.post(url, json=payload, headers=headers, timeout=120)

        if response.status_code == 200:
            data = response.json()
            # audio_base64와 alignment 정보 반환
            import base64
            audio_data = base64.b64decode(data.get("audio_base64", ""))
            alignment = data.get("alignment", {})
            return {
                "ok": True,
                "audio_data": audio_data,
                "alignment": alignment,  # characters, character_start_times_seconds, character_end_times_seconds
            }
        else:
            error_msg = response.text[:300] if response.text else f"HTTP {response.status_code}"
            return {"ok": False, "error": f"ElevenLabs API 오류: {error_msg}"}

    except Exception as e:
        return {"ok": False, "error": str(e)}


def generate_tts(
    episode_id: str,
    script: str,
    output_dir: str,
    voice: str = None,
    speed: float = 1.0,
) -> Dict[str, Any]:
    """
    대본에 대해 TTS 생성 (ElevenLabs 사용)

    Args:
        episode_id: 에피소드 ID (예: "ep019")
        script: 대본 텍스트
        output_dir: 출력 디렉토리
        voice: 음성 ID (없으면 기본값 사용)
        speed: 속도 (현재 미사용, ElevenLabs는 자동 조절)

    Returns:
        {"ok": True, "audio_path": "...", "srt_path": "...", "duration": 900.5}
    """
    api_key = os.environ.get('ELEVENLABS_API_KEY')
    if not api_key:
        return {"ok": False, "error": "ELEVENLABS_API_KEY 환경변수가 필요합니다"}

    os.makedirs(output_dir, exist_ok=True)

    # 음성 ID 설정
    voice_id = voice if voice and len(voice) > 15 else DEFAULT_VOICE_ID
    print(f"[HISTORY-TTS] 음성: ElevenLabs - {voice_id}")

    # 문장 분할
    sentences = split_into_sentences(script)
    print(f"[HISTORY-TTS] {len(sentences)}개 문장 처리 중...")

    # 청크 병합 (API 제한 대응) - 타임아웃 방지를 위해 작게
    MAX_CHARS = 2000
    chunks = []
    current_chunk = ""
    current_sentences = []

    for sentence in sentences:
        if len(current_chunk) + len(sentence) + 1 <= MAX_CHARS:
            current_chunk += " " + sentence if current_chunk else sentence
            current_sentences.append(sentence)
        else:
            if current_chunk:
                chunks.append((current_chunk.strip(), current_sentences))
            current_chunk = sentence
            current_sentences = [sentence]

    if current_chunk:
        chunks.append((current_chunk.strip(), current_sentences))

    print(f"[HISTORY-TTS] {len(chunks)}개 청크로 병합")

    audio_paths = []
    timeline = []
    current_time = 0.0
    failed_count = 0

    with tempfile.TemporaryDirectory() as temp_dir:
        for i, (chunk, chunk_sentences) in enumerate(chunks):
            if not chunk:
                continue

            # TTS 생성 (타임아웃 시 재시도)
            result = None
            for retry in range(3):
                result = generate_elevenlabs_tts_chunk(chunk, voice_id, api_key, speed=speed)
                if result.get("ok"):
                    break
                error_msg = result.get('error', '')
                if 'timeout' in error_msg.lower() or 'timed out' in error_msg.lower():
                    print(f"[HISTORY-TTS] 청크 {i+1} 타임아웃, 재시도 {retry+1}/3...")
                    time.sleep(2)
                else:
                    time.sleep(1)  # ElevenLabs rate limit 대응

            if not result.get("ok"):
                print(f"[HISTORY-TTS] 청크 {i+1} 실패: {result.get('error')}")
                failed_count += 1
                if failed_count >= 3:
                    return {"ok": False, "error": f"TTS 생성 연속 실패: {result.get('error')}"}
                continue

            # ElevenLabs는 직접 MP3 반환
            mp3_path = os.path.join(temp_dir, f"chunk_{i:04d}.mp3")

            with open(mp3_path, 'wb') as f:
                f.write(result["audio_data"])

            # 형식 확인 (첫 청크만)
            if i == 0:
                print(f"[HISTORY-TTS] 오디오 형식: MP3, 크기: {len(result['audio_data'])} bytes")

            # 길이 확인
            duration = get_audio_duration(mp3_path)
            if duration > 0:
                audio_paths.append(mp3_path)

                # 글자 수 비례로 자막 타이밍 계산 (이세계와 동일한 방식)
                total_chars = sum(len(s) for s in chunk_sentences)
                chunk_start = current_time

                for sentence in chunk_sentences:
                    sentence_ratio = len(sentence) / total_chars if total_chars > 0 else 1
                    sentence_duration = duration * sentence_ratio
                    timeline.append((chunk_start, chunk_start + sentence_duration, sentence))
                    chunk_start += sentence_duration

                current_time += duration
                failed_count = 0

            # 진행률 표시
            if (i + 1) % 3 == 0 or i == len(chunks) - 1:
                print(f"[HISTORY-TTS] {i+1}/{len(chunks)} 완료 ({current_time:.1f}초)")

        if not audio_paths:
            return {"ok": False, "error": "TTS 생성 실패 - 오디오 없음"}

        # 오디오 합치기
        audio_output = os.path.join(output_dir, f"{episode_id}.mp3")
        if not merge_audio_files(audio_paths, audio_output):
            return {"ok": False, "error": "오디오 병합 실패"}

        # SRT 생성
        srt_dir = os.path.join(os.path.dirname(output_dir), "subtitles")
        os.makedirs(srt_dir, exist_ok=True)
        srt_output = os.path.join(srt_dir, f"{episode_id}.srt")
        generate_srt(timeline, srt_output)

        total_duration = get_audio_duration(audio_output)
        print(f"[HISTORY-TTS] 완료: {total_duration:.1f}초, {len(timeline)}개 자막")

        return {
            "ok": True,
            "audio_path": audio_output,
            "srt_path": srt_output,
            "duration": total_duration,
            "timeline": timeline,
            "provider": "elevenlabs",
        }


if __name__ == "__main__":
    print("history_pipeline/tts.py 로드 완료")
    print(f"기본 음성: ElevenLabs - {DEFAULT_VOICE_ID}")
