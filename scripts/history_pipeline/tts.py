"""
한국사 파이프라인 - TTS 모듈 (Gemini TTS)

- Gemini TTS: 고품질 한국어 음성
- 문장 단위 자막 생성
- 독립 실행 가능
- GOOGLE_API_KEY만 필요 (서비스 계정 불필요)
"""

import os
import re
import json
import base64
import tempfile
import subprocess
import requests
from typing import Dict, Any, List, Tuple


# TTS 설정
DEFAULT_VOICE = "Charon"  # 남성, 깊고 신뢰감
DEFAULT_MODEL = "gemini-2.5-flash-preview-tts"


def split_into_sentences(text: str) -> List[str]:
    """텍스트를 문장 단위로 분할"""
    sentences = re.split(r'(?<=[.!?])\s+', text.strip())
    return [s.strip() for s in sentences if s.strip()]


def get_audio_duration(audio_path: str) -> float:
    """오디오 파일의 재생 시간(초) 반환"""
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


def generate_gemini_chunk(
    text: str,
    voice_name: str = "Charon",
    model: str = DEFAULT_MODEL,
) -> Dict[str, Any]:
    """Gemini TTS로 단일 청크 생성"""
    api_key = os.environ.get('GOOGLE_API_KEY')
    if not api_key:
        return {"ok": False, "error": "GOOGLE_API_KEY 환경변수가 필요합니다"}

    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"

    payload = {
        "contents": [{
            "parts": [{"text": text}]
        }],
        "generationConfig": {
            "response_modalities": ["AUDIO"],
            "speech_config": {
                "voice_config": {
                    "prebuilt_voice_config": {
                        "voice_name": voice_name
                    }
                }
            }
        }
    }

    try:
        response = requests.post(url, json=payload, timeout=120)

        if response.status_code == 200:
            result = response.json()

            # 오디오 데이터 추출
            candidates = result.get("candidates", [])
            if candidates:
                parts = candidates[0].get("content", {}).get("parts", [])
                for part in parts:
                    if "inlineData" in part:
                        audio_b64 = part["inlineData"].get("data", "")
                        if audio_b64:
                            audio_data = base64.b64decode(audio_b64)
                            return {"ok": True, "audio_data": audio_data}

            return {"ok": False, "error": "오디오 데이터 없음"}
        else:
            error_msg = response.text[:200] if response.text else f"HTTP {response.status_code}"
            return {"ok": False, "error": f"Gemini API 오류: {error_msg}"}

    except Exception as e:
        return {"ok": False, "error": str(e)}


def detect_audio_format(data: bytes) -> str:
    """오디오 데이터의 형식 감지"""
    if data[:4] == b'RIFF' and data[8:12] == b'WAVE':
        return 'wav'
    elif data[:4] == b'OggS':
        return 'ogg'
    elif data[:3] == b'ID3' or data[:2] == b'\xff\xfb':
        return 'mp3'
    elif data[:4] == b'fLaC':
        return 'flac'
    else:
        return 'raw'  # 알 수 없으면 raw PCM으로 가정


def convert_to_mp3(input_path: str, output_path: str, audio_format: str = 'auto') -> bool:
    """오디오를 MP3로 변환

    Args:
        input_path: 입력 파일 경로
        output_path: 출력 MP3 경로
        audio_format: 'auto', 'wav', 'raw', 'ogg' 등
    """
    try:
        # 형식 자동 감지
        if audio_format == 'auto':
            with open(input_path, 'rb') as f:
                header = f.read(12)
            audio_format = detect_audio_format(header)

        if audio_format == 'raw':
            # Gemini TTS: raw PCM (24kHz, 16-bit signed little-endian, mono)
            cmd = [
                'ffmpeg', '-y',
                '-f', 's16le',      # 16-bit signed little-endian
                '-ar', '24000',     # 24kHz sample rate
                '-ac', '1',         # mono
                '-i', input_path,
                '-c:a', 'libmp3lame', '-b:a', '128k',
                output_path
            ]
        else:
            # WAV, OGG 등 컨테이너 형식은 ffmpeg가 자동 감지
            cmd = ['ffmpeg', '-y', '-i', input_path, '-c:a', 'libmp3lame', '-b:a', '128k', output_path]

        result = subprocess.run(cmd, capture_output=True, timeout=60)

        if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
            return True

        # 실패 시 에러 출력
        if result.stderr:
            print(f"[FFmpeg 에러] {result.stderr.decode()[:200]}")
        return False
    except Exception as e:
        print(f"[변환 예외] {e}")
        return False


def generate_tts(
    episode_id: str,
    script: str,
    output_dir: str,
    voice: str = DEFAULT_VOICE,
    speed: float = 1.0,
) -> Dict[str, Any]:
    """
    대본에 대해 TTS 생성 (Gemini TTS 사용)

    Args:
        episode_id: 에피소드 ID (예: "ep019")
        script: 대본 텍스트
        output_dir: 출력 디렉토리
        voice: 음성 (Charon, Kore, Puck, Fenrir, Aoede)
        speed: 속도 (현재 미사용)

    Returns:
        {"ok": True, "audio_path": "...", "srt_path": "...", "duration": 900.5}
    """
    os.makedirs(output_dir, exist_ok=True)

    # 음성 이름 파싱 (gemini:Charon → Charon, chirp3:Charon → Charon)
    voice_name = voice.split(":")[-1] if ":" in voice else voice
    print(f"[HISTORY-TTS] 음성: Gemini TTS - {voice_name}")

    # 문장 분할
    sentences = split_into_sentences(script)
    print(f"[HISTORY-TTS] {len(sentences)}개 문장 처리 중...")

    # 청크 병합 (API 제한 대응)
    MAX_CHARS = 2000
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

    print(f"[HISTORY-TTS] {len(chunks)}개 청크로 병합")

    audio_paths = []
    timeline = []
    current_time = 0.0
    failed_count = 0

    with tempfile.TemporaryDirectory() as temp_dir:
        for i, chunk in enumerate(chunks):
            if not chunk:
                continue

            # TTS 생성
            result = generate_gemini_chunk(chunk, voice_name)
            if not result.get("ok"):
                print(f"[HISTORY-TTS] 청크 {i+1} 실패: {result.get('error')}")
                failed_count += 1
                if failed_count >= 3:
                    return {"ok": False, "error": f"TTS 생성 연속 실패: {result.get('error')}"}
                continue

            # 임시 파일 저장 (Gemini는 wav/pcm 반환)
            raw_path = os.path.join(temp_dir, f"chunk_{i:04d}.raw")
            mp3_path = os.path.join(temp_dir, f"chunk_{i:04d}.mp3")

            with open(raw_path, 'wb') as f:
                f.write(result["audio_data"])

            # 형식 확인 (첫 청크만)
            if i == 0:
                detected = detect_audio_format(result["audio_data"][:12])
                print(f"[HISTORY-TTS] 오디오 형식: {detected}, 크기: {len(result['audio_data'])} bytes")

            # MP3로 변환 (형식 자동 감지)
            if not convert_to_mp3(raw_path, mp3_path, audio_format='auto'):
                print(f"[HISTORY-TTS] 청크 {i+1} 변환 실패")
                continue

            # 길이 확인
            duration = get_audio_duration(mp3_path)
            if duration > 0:
                audio_paths.append(mp3_path)
                timeline.append((current_time, current_time + duration, chunk))
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
        }


if __name__ == "__main__":
    print("history_pipeline/tts.py 로드 완료")
    print(f"기본 음성: Gemini TTS - {DEFAULT_VOICE}")
