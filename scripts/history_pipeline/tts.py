"""
한국사 파이프라인 - TTS 모듈 (Chirp 3 HD)

- Chirp 3 HD: 고품질 한국어 음성 (기본)
- 문장 단위 자막 생성
- 독립 실행 가능
"""

import os
import re
import json
import tempfile
import subprocess
from typing import Dict, Any, List, Tuple


# TTS 설정
DEFAULT_VOICE = "chirp3:Charon"  # Chirp 3 HD 남성 (깊고 신뢰감)
DEFAULT_SPEED = 1.0


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


def generate_chirp3_chunk(
    text: str,
    voice_name: str = "ko-KR-Chirp3-HD-Charon",
    language_code: str = "ko-KR",
) -> Dict[str, Any]:
    """Chirp 3 HD TTS로 단일 청크 생성"""
    try:
        from google.cloud import texttospeech
        from google.oauth2 import service_account

        # 서비스 계정 인증
        service_account_json = os.environ.get('GOOGLE_SERVICE_ACCOUNT_JSON')
        if not service_account_json:
            return {"ok": False, "error": "GOOGLE_SERVICE_ACCOUNT_JSON 환경변수가 필요합니다"}

        try:
            service_account_info = json.loads(service_account_json)
        except json.JSONDecodeError as e:
            return {"ok": False, "error": f"서비스 계정 JSON 파싱 실패: {e}"}

        credentials = service_account.Credentials.from_service_account_info(
            service_account_info,
            scopes=["https://www.googleapis.com/auth/cloud-platform"]
        )

        client = texttospeech.TextToSpeechClient(credentials=credentials)

        voice = texttospeech.VoiceSelectionParams(
            language_code=language_code,
            name=voice_name,
        )

        audio_config = texttospeech.AudioConfig(
            audio_encoding=texttospeech.AudioEncoding.MP3
        )

        input_text = texttospeech.SynthesisInput(text=text)
        response = client.synthesize_speech(
            input=input_text,
            voice=voice,
            audio_config=audio_config,
        )

        return {"ok": True, "audio_data": response.audio_content}

    except Exception as e:
        return {"ok": False, "error": str(e)}


def parse_voice(voice: str) -> tuple:
    """음성 설정 파싱 → (voice_name, language_code)"""
    if voice.startswith("chirp3:"):
        # chirp3:Charon → ko-KR-Chirp3-HD-Charon
        voice_short = voice.split(":")[1]
        return f"ko-KR-Chirp3-HD-{voice_short}", "ko-KR"
    elif voice.startswith("ko-KR-"):
        return voice, "ko-KR"
    else:
        # 기본값
        return "ko-KR-Chirp3-HD-Charon", "ko-KR"


def generate_tts(
    episode_id: str,
    script: str,
    output_dir: str,
    voice: str = DEFAULT_VOICE,
    speed: float = DEFAULT_SPEED,
) -> Dict[str, Any]:
    """
    대본에 대해 TTS 생성 (Chirp 3 HD 사용)

    Args:
        episode_id: 에피소드 ID (예: "ep019")
        script: 대본 텍스트
        output_dir: 출력 디렉토리
        voice: 음성 (기본: chirp3:Charon)
        speed: 속도 (현재 미사용)

    Returns:
        {"ok": True, "audio_path": "...", "srt_path": "...", "duration": 900.5}
    """
    os.makedirs(output_dir, exist_ok=True)

    # 음성 설정 파싱
    voice_name, language_code = parse_voice(voice)
    print(f"[HISTORY-TTS] 음성: {voice_name}")

    # 문장 분할
    sentences = split_into_sentences(script)
    print(f"[HISTORY-TTS] {len(sentences)}개 문장 처리 중...")

    # 청크 병합 (5000바이트 제한 대응)
    MAX_CHARS = 1400
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
            result = generate_chirp3_chunk(chunk, voice_name, language_code)
            if not result.get("ok"):
                print(f"[HISTORY-TTS] 청크 {i+1} 실패: {result.get('error')}")
                failed_count += 1
                if failed_count >= 3:
                    return {"ok": False, "error": f"TTS 생성 연속 실패: {result.get('error')}"}
                continue

            # 임시 파일 저장
            chunk_path = os.path.join(temp_dir, f"chunk_{i:04d}.mp3")
            with open(chunk_path, 'wb') as f:
                f.write(result["audio_data"])

            # 길이 확인
            duration = get_audio_duration(chunk_path)
            if duration > 0:
                audio_paths.append(chunk_path)
                timeline.append((current_time, current_time + duration, chunk))
                current_time += duration
                failed_count = 0  # 성공하면 실패 카운트 리셋

            # 진행률 표시
            if (i + 1) % 5 == 0 or i == len(chunks) - 1:
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
    print(f"기본 음성: {DEFAULT_VOICE}")
