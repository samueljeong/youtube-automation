"""
이세계 파이프라인 - TTS 모듈 (Chirp3 HD 사용)

- drama_server의 generate_chirp3_tts 함수 사용
- Google Cloud TTS Chirp3 HD (고품질 한국어)
- GOOGLE_SERVICE_ACCOUNT_JSON 환경변수 필요
"""

import os
import re
import subprocess
import tempfile
from typing import Dict, Any, List, Tuple


# TTS 설정
DEFAULT_VOICE = "Charon"  # 남성, 깊고 신뢰감


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


def generate_tts(
    episode_id: str,
    script: str,
    output_dir: str,
    voice: str = DEFAULT_VOICE,
    speed: float = 1.0,
) -> Dict[str, Any]:
    """
    대본에 대해 TTS 생성 (Google Cloud Chirp3 HD 사용)

    Args:
        episode_id: 에피소드 ID (예: "ep001")
        script: 대본 텍스트
        output_dir: 출력 디렉토리
        voice: 음성 (Charon, Kore, Puck, Fenrir, Aoede)
        speed: 속도 (현재 미사용)

    Returns:
        {"ok": True, "audio_path": "...", "srt_path": "...", "duration": 900.5}
    """
    # drama_server에서 Chirp3 TTS 함수 가져오기
    try:
        import sys
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        if project_root not in sys.path:
            sys.path.insert(0, project_root)

        from drama_server import generate_chirp3_tts
    except ImportError as e:
        return {"ok": False, "error": f"drama_server 임포트 실패: {e}"}

    os.makedirs(output_dir, exist_ok=True)

    # 음성 이름 파싱 (chirp3:Charon → Charon)
    voice_short = voice.split(":")[-1] if ":" in voice else voice
    valid_voices = ["Kore", "Charon", "Puck", "Fenrir", "Aoede", "Orus", "Leda", "Zephyr"]
    if voice_short not in valid_voices:
        print(f"[ISEKAI-TTS] 잘못된 음성: {voice_short}, 기본값 Charon 사용")
        voice_short = "Charon"

    chirp3_voice_name = f"ko-KR-Chirp3-HD-{voice_short}"
    print(f"[ISEKAI-TTS] 음성: {chirp3_voice_name}")

    # 문장 분할
    sentences = split_into_sentences(script)
    print(f"[ISEKAI-TTS] {len(sentences)}개 문장 처리 중...")

    # 청크 병합 (API 제한 대응 - 5000바이트 ≈ 1400자)
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

            # TTS 생성 (Chirp3 HD)
            result = generate_chirp3_tts(
                text=chunk,
                voice_name=chirp3_voice_name,
                language_code="ko-KR"
            )

            if not result.get("ok"):
                print(f"[ISEKAI-TTS] 청크 {i+1} 실패: {result.get('error')}")
                failed_count += 1
                if failed_count >= 3:
                    return {"ok": False, "error": f"TTS 생성 연속 실패: {result.get('error')}"}
                continue

            # MP3 파일 저장 (Chirp3는 MP3 반환)
            mp3_path = os.path.join(temp_dir, f"chunk_{i:04d}.mp3")
            with open(mp3_path, 'wb') as f:
                f.write(result["audio_data"])

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
                print(f"[ISEKAI-TTS] {i+1}/{len(chunks)} 완료 ({current_time:.1f}초)")

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
        print(f"[ISEKAI-TTS] 완료: {total_duration:.1f}초, {len(timeline)}개 자막")

        return {
            "ok": True,
            "audio_path": audio_output,
            "srt_path": srt_output,
            "duration": total_duration,
            "timeline": timeline,
        }


if __name__ == "__main__":
    print("isekai_pipeline/tts.py 로드 완료")
    print(f"기본 음성: Chirp3 HD - {DEFAULT_VOICE}")
