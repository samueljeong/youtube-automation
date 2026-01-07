"""
한국사 파이프라인 - TTS 모듈 (Google Cloud TTS)

- 단일 음성 나레이션 (역사 다큐멘터리용)
- 문장 단위 자막 생성
- 독립 실행 가능 (외부 의존성 없음)
"""

import os
import re
import base64
import requests
import tempfile
import subprocess
from typing import Dict, Any, List, Tuple


# TTS 설정
DEFAULT_VOICE = "ko-KR-Neural2-C"  # 차분한 남성 목소리
DEFAULT_SPEED = 0.95


def split_into_sentences(text: str) -> List[str]:
    """텍스트를 문장 단위로 분할"""
    # 문장 끝 패턴: .!? 뒤에 공백이나 줄바꿈
    sentences = re.split(r'(?<=[.!?])\s+', text.strip())
    # 빈 문장 제거
    return [s.strip() for s in sentences if s.strip()]


def generate_tts_chunk(
    text: str,
    voice: str = DEFAULT_VOICE,
    speed: float = DEFAULT_SPEED,
) -> Dict[str, Any]:
    """단일 텍스트에 대해 TTS 생성"""
    api_key = os.environ.get("GOOGLE_CLOUD_API_KEY", "")
    if not api_key:
        return {"ok": False, "error": "GOOGLE_CLOUD_API_KEY 환경변수가 설정되지 않았습니다."}

    url = f"https://texttospeech.googleapis.com/v1/text:synthesize?key={api_key}"

    payload = {
        "input": {"text": text},
        "voice": {
            "languageCode": "ko-KR",
            "name": voice,
        },
        "audioConfig": {
            "audioEncoding": "MP3",
            "speakingRate": speed,
        }
    }

    try:
        response = requests.post(url, json=payload, timeout=60)
        if response.status_code == 200:
            result = response.json()
            audio_content = base64.b64decode(result.get("audioContent", ""))
            return {"ok": True, "audio_data": audio_content}
        else:
            return {"ok": False, "error": f"TTS API 오류: {response.status_code} - {response.text[:200]}"}
    except Exception as e:
        return {"ok": False, "error": str(e)}


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
    speed: float = DEFAULT_SPEED,
) -> Dict[str, Any]:
    """
    대본에 대해 TTS 생성 (문장별로 처리)

    Args:
        episode_id: 에피소드 ID (예: "ep019")
        script: 대본 텍스트
        output_dir: 출력 디렉토리
        voice: 음성 (기본: ko-KR-Neural2-C)
        speed: 속도 (기본: 0.95)

    Returns:
        {
            "ok": True,
            "audio_path": "outputs/history/audio/ep019.mp3",
            "srt_path": "outputs/history/subtitles/ep019.srt",
            "duration": 900.5,
            "timeline": [(0, 3.5, "문장1"), ...]
        }
    """
    os.makedirs(output_dir, exist_ok=True)

    # 문장 분할
    sentences = split_into_sentences(script)
    print(f"[HISTORY-TTS] {len(sentences)}개 문장 처리 중...")

    audio_paths = []
    timeline = []
    current_time = 0.0

    with tempfile.TemporaryDirectory() as temp_dir:
        for i, sentence in enumerate(sentences):
            if not sentence:
                continue

            # TTS 생성
            result = generate_tts_chunk(sentence, voice, speed)
            if not result.get("ok"):
                print(f"[HISTORY-TTS] 문장 {i+1} 실패: {result.get('error')}")
                continue

            # 임시 파일 저장
            chunk_path = os.path.join(temp_dir, f"chunk_{i:04d}.mp3")
            with open(chunk_path, 'wb') as f:
                f.write(result["audio_data"])

            # 길이 확인
            duration = get_audio_duration(chunk_path)
            if duration > 0:
                audio_paths.append(chunk_path)
                timeline.append((current_time, current_time + duration, sentence))
                current_time += duration

            # 진행률 표시
            if (i + 1) % 10 == 0:
                print(f"[HISTORY-TTS] {i+1}/{len(sentences)} 완료 ({current_time:.1f}초)")

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
    # 테스트
    print("history_pipeline/tts.py 로드 완료")
