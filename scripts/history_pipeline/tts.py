"""
한국사 파이프라인 - TTS 모듈 (Google Cloud TTS - Chirp3 HD)

- Google Cloud TTS API: 고품질 한국어 음성
- Chirp3 HD: 최신 고품질 음성 모델
- 문장 단위 자막 생성
- 독립 실행 가능
- GOOGLE_CLOUD_API_KEY 필요
"""

import os
import re
import json
import base64
import tempfile
import subprocess
import time
import requests
from typing import Dict, Any, List, Tuple


# TTS 설정 (Google Cloud TTS - Chirp3 HD)
DEFAULT_VOICE = "ko-KR-Chirp3-HD-Charon"  # 남성, 깊고 신뢰감 있는 톤
TTS_API_URL = "https://texttospeech.googleapis.com/v1/text:synthesize"


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
        duration = float(result.stdout.strip()) if result.stdout.strip() else 0.0
        if duration > 0:
            return duration
    except Exception:
        pass

    # ffprobe 실패 시 파일 크기로 추정 (MP3 128kbps 기준: 1초당 약 16KB)
    try:
        file_size = os.path.getsize(audio_path)
        if file_size > 0:
            return file_size / 16000.0  # 128kbps MP3 기준
    except Exception:
        pass

    return 0.0


def _strip_id3_tags(data: bytes) -> bytes:
    """MP3 데이터에서 ID3 태그 제거 (순수 오디오 프레임만 추출)"""
    start = 0
    # ID3v2 태그 건너뛰기 (파일 시작 부분)
    if data[:3] == b'ID3':
        # ID3v2 헤더: 10바이트, 크기는 syncsafe integer
        if len(data) >= 10:
            size = ((data[6] & 0x7f) << 21) | ((data[7] & 0x7f) << 14) | \
                   ((data[8] & 0x7f) << 7) | (data[9] & 0x7f)
            start = 10 + size

    # ID3v1 태그 제거 (파일 끝 128바이트)
    end = len(data)
    if len(data) >= 128 and data[-128:-125] == b'TAG':
        end = len(data) - 128

    return data[start:end]


def merge_audio_files(audio_paths: List[str], output_path: str) -> bool:
    """여러 오디오 파일을 하나로 합침 (ffmpeg 또는 순수 Python)"""
    if not audio_paths:
        return False

    if len(audio_paths) == 1:
        import shutil
        shutil.copy(audio_paths[0], output_path)
        return True

    # 방법 1: ffmpeg 사용 (있으면)
    try:
        # ffmpeg 존재 확인
        result = subprocess.run(['which', 'ffmpeg'], capture_output=True, timeout=5)
        if result.returncode == 0:
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

    # 방법 2: 순수 Python으로 MP3 바이너리 병합 (ffmpeg 없을 때)
    try:
        print("[HISTORY-TTS] ffmpeg 없음, 순수 Python으로 MP3 병합...")
        with open(output_path, 'wb') as out_f:
            for i, path in enumerate(audio_paths):
                with open(path, 'rb') as in_f:
                    data = in_f.read()
                    # 첫 번째 파일은 ID3v2 태그 유지, 나머지는 제거
                    if i > 0:
                        data = _strip_id3_tags(data)
                    else:
                        # 첫 파일도 ID3v1 태그만 제거 (끝부분)
                        if len(data) >= 128 and data[-128:-125] == b'TAG':
                            data = data[:-128]
                    out_f.write(data)

        if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
            print(f"[HISTORY-TTS] MP3 병합 완료: {os.path.getsize(output_path)} bytes")
            return True
    except Exception as e:
        print(f"[HISTORY-TTS] MP3 병합 실패: {e}")

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


def generate_tts_chunk(
    text: str,
    voice_name: str = DEFAULT_VOICE,
) -> Dict[str, Any]:
    """Google Cloud TTS API로 단일 청크 생성 (Chirp3 HD)"""
    api_key = os.environ.get('GOOGLE_CLOUD_API_KEY')
    if not api_key:
        return {"ok": False, "error": "GOOGLE_CLOUD_API_KEY 환경변수가 필요합니다"}

    url = f"{TTS_API_URL}?key={api_key}"

    # voice_name 처리: 접두사 제거 (gemini:Charon → ko-KR-Chirp3-HD-Charon)
    if ":" in voice_name:
        voice_suffix = voice_name.split(":")[-1]
        voice_name = f"ko-KR-Chirp3-HD-{voice_suffix}"
    elif not voice_name.startswith("ko-KR"):
        voice_name = f"ko-KR-Chirp3-HD-{voice_name}"

    payload = {
        "input": {"text": text},
        "voice": {"languageCode": "ko-KR", "name": voice_name},
        "audioConfig": {"audioEncoding": "MP3", "sampleRateHertz": 24000}
    }

    try:
        response = requests.post(url, json=payload, timeout=120)

        if response.status_code == 200:
            result = response.json()
            audio_b64 = result.get("audioContent", "")
            if audio_b64:
                audio_data = base64.b64decode(audio_b64)
                return {"ok": True, "audio_data": audio_data, "format": "mp3"}
            return {"ok": False, "error": "오디오 데이터 없음"}
        else:
            error_msg = response.text[:200] if response.text else f"HTTP {response.status_code}"
            return {"ok": False, "error": f"Google Cloud TTS API 오류: {error_msg}"}

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
    대본에 대해 TTS 생성 (Google Cloud TTS - Chirp3 HD 사용)

    Args:
        episode_id: 에피소드 ID (예: "ep019")
        script: 대본 텍스트
        output_dir: 출력 디렉토리
        voice: 음성 (ko-KR-Chirp3-HD-Charon 등)
        speed: 속도 (현재 미사용)

    Returns:
        {"ok": True, "audio_path": "...", "srt_path": "...", "duration": 900.5}
    """
    os.makedirs(output_dir, exist_ok=True)

    # 음성 이름 처리 (chirp3:Charon → ko-KR-Chirp3-HD-Charon)
    voice_name = voice
    print(f"[HISTORY-TTS] 음성: Google Cloud TTS Chirp3 HD - {voice_name}")

    # 문장 분할
    sentences = split_into_sentences(script)
    print(f"[HISTORY-TTS] {len(sentences)}개 문장 처리 중...")

    # 청크 병합 (API 제한 대응) - 문장 목록도 함께 저장
    MAX_CHARS = 1000
    chunks = []  # [(chunk_text, [sentences_in_chunk]), ...]
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
    timeline = []  # [(start, end, sentence), ...] - 문장 단위
    current_time = 0.0
    failed_count = 0

    with tempfile.TemporaryDirectory() as temp_dir:
        for i, (chunk, chunk_sentences) in enumerate(chunks):
            if not chunk:
                continue

            # TTS 생성 (타임아웃 시 재시도)
            result = None
            for retry in range(3):
                result = generate_tts_chunk(chunk, voice_name)
                if result.get("ok"):
                    break
                error_msg = result.get('error', '')
                if 'timeout' in error_msg.lower() or 'timed out' in error_msg.lower():
                    print(f"[HISTORY-TTS] 청크 {i+1} 타임아웃, 재시도 {retry+1}/3...")
                    time.sleep(2)  # 잠시 대기 후 재시도
                else:
                    break  # 타임아웃이 아니면 재시도 안함

            if not result.get("ok"):
                print(f"[HISTORY-TTS] 청크 {i+1} 실패: {result.get('error')}")
                failed_count += 1
                if failed_count >= 3:
                    return {"ok": False, "error": f"TTS 생성 연속 실패: {result.get('error')}"}
                continue

            # Google Cloud TTS는 직접 MP3 반환
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

                # 문장별 타이밍 계산 (글자 수 비례)
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
        }


if __name__ == "__main__":
    print("history_pipeline/tts.py 로드 완료")
    print(f"기본 음성: Google Cloud TTS Chirp3 HD - {DEFAULT_VOICE}")
