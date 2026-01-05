"""
TTS 모듈
- 태그 기반 스크립트 파싱
- 단일 나레이션 음성 TTS (자막 싱크 안정성)
- 문장 단위 자막 생성
"""

import os
import re
import uuid
import tempfile
import subprocess
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass

from .config import (
    VOICE_MAP,
    DEFAULT_VOICE,
    MAIN_CHARACTER_TAGS,
    EXTRA_TAGS,
    SCRIPT_CONFIG,
    CHARACTER_SPEAKING_RATE,
)


@dataclass
class VoiceSegment:
    """음성 세그먼트 정보"""
    index: int
    tag: str              # 태그 (나레이션, 무영, 노인 등)
    text: str             # 대사 또는 나레이션
    voice: str            # TTS 음성 ID
    is_main_char: bool    # 주인공 여부 (나레이터 소개 필요)
    speaking_rate: float = 0.9  # 음성 속도 (캐릭터별)
    audio_path: Optional[str] = None
    duration: float = 0.0


def parse_script_to_segments(script: str) -> List[VoiceSegment]:
    """
    태그 기반 스크립트를 음성 세그먼트로 파싱

    입력 형식:
        [나레이션] 어느 날, 무영은 산길을 걷고 있었다.
        [무영] "누구냐!"
        [노인] "젊은이, 그리 겁먹지 마라."
        [남자] 이봐, 거기 서!

    Returns:
        List[VoiceSegment]: 파싱된 세그먼트 목록
    """
    segments = []

    # 태그 패턴: [태그] 내용
    pattern = r'\[([^\]]+)\]\s*(.+?)(?=\[[^\]]+\]|$)'

    matches = re.findall(pattern, script, re.DOTALL)

    for idx, (tag, text) in enumerate(matches):
        tag = tag.strip()
        text = text.strip()

        if not text:
            continue

        # 음성 결정
        voice = get_voice_for_tag(tag)

        # 주인공 여부 확인
        is_main_char = tag in MAIN_CHARACTER_TAGS

        # 캐릭터별 음성 속도 (기본 0.9)
        speaking_rate = CHARACTER_SPEAKING_RATE.get(tag, SCRIPT_CONFIG.get("speaking_rate", 0.9))

        segments.append(VoiceSegment(
            index=idx,
            tag=tag,
            text=text,
            voice=voice,
            is_main_char=is_main_char,
            speaking_rate=speaking_rate
        ))

    return segments


def get_voice_for_tag(tag: str) -> str:
    """태그에 맞는 음성 반환"""
    # 정확히 매칭되는 태그
    if tag in VOICE_MAP:
        return VOICE_MAP[tag]

    # 숫자가 붙은 엑스트라 (남자1, 여자2 등)
    base_tag = re.sub(r'\d+$', '', tag)
    if base_tag in VOICE_MAP:
        return VOICE_MAP[base_tag]

    # 기본 음성
    return DEFAULT_VOICE


def generate_multi_voice_tts(
    segments: List[VoiceSegment],
    output_dir: str,
    episode_id: str = None
) -> Dict[str, Any]:
    """
    다중 음성 TTS 생성

    Args:
        segments: 파싱된 세그먼트 목록
        output_dir: 출력 디렉토리
        episode_id: 에피소드 ID (파일명용)

    Returns:
        {
            "ok": True,
            "segments": [...],  # duration 포함된 세그먼트
            "merged_audio": "path/to/merged.mp3",
            "total_duration": 123.45,
            "timeline": [...]  # SRT용 타임라인
        }
    """
    # 임포트는 여기서 (drama_server와의 의존성)
    import sys
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

    from drama_server import (
        is_chirp3_voice,
        is_gemini_voice,
        parse_chirp3_voice,
        parse_gemini_voice,
        generate_chirp3_tts,
        generate_gemini_tts,
    )

    if not episode_id:
        episode_id = str(uuid.uuid4())[:8]

    os.makedirs(output_dir, exist_ok=True)

    audio_files = []
    timeline = []
    current_time = 0.0

    print(f"[MULTI-TTS] 시작: {len(segments)}개 세그먼트", flush=True)

    for seg in segments:
        print(f"[MULTI-TTS] [{seg.tag}] {seg.voice} - {len(seg.text)}자", flush=True)

        # TTS 생성
        audio_data = None
        used_voice = seg.voice  # 실제 사용된 음성 추적

        if is_chirp3_voice(seg.voice):
            # Chirp3 TTS
            chirp3_config = parse_chirp3_voice(seg.voice)
            result = generate_chirp3_tts(
                text=seg.text,
                voice_name=chirp3_config['voice']
            )
            if result.get("ok"):
                audio_data = result['audio_data']
            else:
                # ★ Chirp3 실패 시 Google Cloud TTS 폴백
                print(f"[MULTI-TTS] Chirp3 실패, Google Cloud TTS 폴백: [{seg.tag}]", flush=True)
                fallback_voice = "ko-KR-Neural2-C" if seg.tag in ["나레이션", "노인", "남자"] else "ko-KR-Neural2-A"
                result = generate_google_cloud_tts(seg.text, fallback_voice, seg.speaking_rate)
                if result.get("ok"):
                    audio_data = result['audio_data']
                    used_voice = fallback_voice

        elif is_gemini_voice(seg.voice):
            # Gemini TTS
            gemini_config = parse_gemini_voice(seg.voice)
            result = generate_gemini_tts(
                text=seg.text,
                voice_name=gemini_config['voice'],
                model=gemini_config['model']
            )
            if result.get("ok"):
                audio_data = result['audio_data']
            else:
                # ★ Gemini 실패 시 Google Cloud TTS 폴백
                print(f"[MULTI-TTS] Gemini 실패, Google Cloud TTS 폴백: [{seg.tag}]", flush=True)
                fallback_voice = "ko-KR-Neural2-C" if seg.tag in ["나레이션", "노인", "남자"] else "ko-KR-Neural2-A"
                result = generate_google_cloud_tts(seg.text, fallback_voice, seg.speaking_rate)
                if result.get("ok"):
                    audio_data = result['audio_data']
                    used_voice = fallback_voice

        else:
            # Google Cloud TTS (Neural2) - 기본
            result = generate_google_cloud_tts(seg.text, seg.voice, seg.speaking_rate)
            if result.get("ok"):
                audio_data = result['audio_data']

        if not audio_data:
            print(f"[MULTI-TTS] ❌ TTS 실패: [{seg.tag}]", flush=True)
            continue

        # 파일 저장
        audio_path = os.path.join(output_dir, f"{episode_id}_seg_{seg.index:03d}.mp3")
        with open(audio_path, 'wb') as f:
            f.write(audio_data)

        # Duration 측정
        duration = get_audio_duration(audio_path)

        seg.audio_path = audio_path
        seg.duration = duration

        # 타임라인 추가
        timeline.append({
            "index": seg.index,
            "tag": seg.tag,
            "text": seg.text,
            "start_sec": current_time,
            "end_sec": current_time + duration,
            "voice": used_voice  # 실제 사용된 음성
        })

        audio_files.append(audio_path)
        current_time += duration

        print(f"[MULTI-TTS] ✓ [{seg.tag}] {duration:.2f}초", flush=True)

    if not audio_files:
        return {"ok": False, "error": "TTS 생성 실패"}

    # FFmpeg로 병합
    merged_path = os.path.join(output_dir, f"{episode_id}_full.mp3")
    merge_result = merge_audio_files(audio_files, merged_path)

    if not merge_result:
        return {"ok": False, "error": "오디오 병합 실패"}

    total_duration = sum(seg.duration for seg in segments if seg.duration > 0)

    print(f"[MULTI-TTS] 완료: {len(audio_files)}개 세그먼트, 총 {total_duration:.1f}초", flush=True)

    return {
        "ok": True,
        "segments": segments,
        "merged_audio": merged_path,
        "total_duration": total_duration,
        "timeline": timeline
    }


def generate_google_cloud_tts(text: str, voice: str, speaking_rate: float = 0.9) -> Dict[str, Any]:
    """Google Cloud TTS (Neural2) 생성"""
    import requests
    import base64

    api_key = os.getenv("GOOGLE_CLOUD_API_KEY", "")
    if not api_key:
        return {"ok": False, "error": "GOOGLE_CLOUD_API_KEY 없음"}

    url = f"https://texttospeech.googleapis.com/v1/text:synthesize?key={api_key}"

    payload = {
        "input": {"text": text},
        "voice": {
            "languageCode": "ko-KR",
            "name": voice if voice.startswith("ko-KR") else "ko-KR-Neural2-C"
        },
        "audioConfig": {
            "audioEncoding": "MP3",
            "speakingRate": speaking_rate
        }
    }

    try:
        response = requests.post(url, json=payload, timeout=60)
        if response.status_code == 200:
            result = response.json()
            audio_content = base64.b64decode(result.get("audioContent", ""))
            return {"ok": True, "audio_data": audio_content}
        else:
            return {"ok": False, "error": f"API 오류: {response.status_code}"}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def get_audio_duration(audio_path: str) -> float:
    """ffprobe로 오디오 길이 측정"""
    if not os.path.exists(audio_path):
        return 0.0

    try:
        cmd = [
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            audio_path
        ]
        out = subprocess.check_output(cmd, stderr=subprocess.DEVNULL).decode().strip()
        return float(out)
    except Exception:
        # 파일 크기 기반 추정 (MP3 128kbps 기준)
        try:
            return os.path.getsize(audio_path) / 16000
        except:
            return 0.0


def merge_audio_files(files: List[str], output_path: str) -> bool:
    """FFmpeg로 오디오 파일 병합"""
    if not files:
        return False

    if len(files) == 1:
        import shutil
        shutil.copy(files[0], output_path)
        return True

    try:
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            for path in files:
                f.write(f"file '{os.path.abspath(path)}'\n")
            list_file = f.name

        cmd = [
            "ffmpeg", "-y",
            "-f", "concat", "-safe", "0",
            "-i", list_file,
            "-c", "copy",
            output_path
        ]

        subprocess.run(cmd, check=True, capture_output=True)
        os.unlink(list_file)

        print(f"[MULTI-TTS] 병합 완료: {len(files)}개 → {output_path}", flush=True)
        return True

    except Exception as e:
        print(f"[MULTI-TTS] 병합 오류: {e}", flush=True)
        return False


def generate_srt_from_timeline(timeline: List[Dict], srt_path: str) -> bool:
    """타임라인에서 SRT 자막 생성"""
    os.makedirs(os.path.dirname(srt_path), exist_ok=True)

    with open(srt_path, "w", encoding="utf-8") as f:
        for i, entry in enumerate(timeline, 1):
            start = sec_to_srt_time(entry['start_sec'])
            end = sec_to_srt_time(entry['end_sec'])
            text = entry['text']

            # 대사에 캐릭터 표시 (옵션)
            if entry['tag'] != "나레이션":
                text = f"[{entry['tag']}] {text}"

            f.write(f"{i}\n")
            f.write(f"{start} --> {end}\n")
            f.write(f"{text}\n\n")

    print(f"[SRT] 생성 완료: {len(timeline)}개 항목 → {srt_path}", flush=True)
    return True


def sec_to_srt_time(sec: float) -> str:
    """초를 SRT 타임코드로 변환 (HH:MM:SS,mmm)"""
    h = int(sec // 3600)
    m = int((sec % 3600) // 60)
    s = int(sec % 60)
    ms = int((sec - int(sec)) * 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


# =====================================================
# 단일 음성 TTS (자막 싱크 안정성)
# =====================================================

def generate_single_voice_tts(
    segments: List[VoiceSegment],
    output_dir: str,
    episode_id: str = None,
    voice: str = "chirp3:Charon"
) -> Dict[str, Any]:
    """
    단일 음성으로 전체 대본 TTS 생성 (자막 싱크 안정성)

    - 모든 세그먼트의 텍스트를 합쳐서 1회 TTS 호출
    - 병합 과정 없음 → 프레임 딜레이 문제 해결
    - 자막은 글자 수 비례로 타이밍 계산

    Args:
        segments: 파싱된 세그먼트 목록
        output_dir: 출력 디렉토리
        episode_id: 에피소드 ID
        voice: TTS 음성 (기본: chirp3:Charon)

    Returns:
        {
            "ok": True,
            "merged_audio": "path/to/audio.mp3",
            "total_duration": 123.45,
            "timeline": [...]  # SRT용 타임라인
        }
    """
    import sys
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

    from drama_server import (
        is_chirp3_voice,
        parse_chirp3_voice,
        generate_chirp3_tts,
    )

    if not episode_id:
        episode_id = str(uuid.uuid4())[:8]

    os.makedirs(output_dir, exist_ok=True)

    # 1. 모든 텍스트 합치기 (태그 제거, 텍스트만)
    all_texts = []
    segment_info = []  # 각 세그먼트의 텍스트 길이 저장

    for seg in segments:
        text = seg.text.strip()
        if text:
            all_texts.append(text)
            segment_info.append({
                "tag": seg.tag,
                "text": text,
                "char_count": len(text)
            })

    if not all_texts:
        return {"ok": False, "error": "텍스트가 없습니다"}

    # 전체 텍스트 (문장 사이에 공백 추가)
    full_text = " ".join(all_texts)
    total_chars = sum(info["char_count"] for info in segment_info)

    print(f"[SINGLE-TTS] 시작: {len(segment_info)}개 세그먼트, 총 {total_chars:,}자", flush=True)

    # 2. 단일 TTS 생성
    if is_chirp3_voice(voice):
        chirp3_config = parse_chirp3_voice(voice)
        result = generate_chirp3_tts(
            text=full_text,
            voice_name=chirp3_config['voice']
        )
    else:
        return {"ok": False, "error": f"지원하지 않는 음성: {voice}"}

    if not result.get("ok"):
        return {"ok": False, "error": result.get("error", "TTS 생성 실패")}

    audio_data = result.get("audio_data")
    if not audio_data:
        return {"ok": False, "error": "오디오 데이터 없음"}

    # 3. 오디오 저장
    audio_path = os.path.join(output_dir, f"{episode_id}_full.mp3")
    with open(audio_path, "wb") as f:
        f.write(audio_data)

    # 4. 전체 duration 측정
    total_duration = get_audio_duration(audio_path)
    print(f"[SINGLE-TTS] TTS 완료: {total_duration:.1f}초 ({total_duration/60:.1f}분)", flush=True)

    # 5. 타임라인 생성 (글자 수 비례)
    timeline = []
    current_time = 0.0

    for i, info in enumerate(segment_info):
        # 글자 수 비례로 duration 계산
        ratio = info["char_count"] / total_chars
        duration = total_duration * ratio

        timeline.append({
            "index": i,
            "tag": info["tag"],
            "text": info["text"],
            "start_sec": current_time,
            "end_sec": current_time + duration,
            "voice": voice
        })

        current_time += duration

    print(f"[SINGLE-TTS] 완료: {len(timeline)}개 세그먼트, 총 {total_duration:.1f}초", flush=True)

    return {
        "ok": True,
        "segments": segments,
        "merged_audio": audio_path,
        "total_duration": total_duration,
        "timeline": timeline
    }


# =====================================================
# 테스트 코드
# =====================================================

if __name__ == "__main__":
    # 테스트 스크립트
    test_script = """
[나레이션] 어느 깊은 밤, 산중의 작은 오두막에서 한 젊은이가 잠에서 깨어났다.

[무영] "또... 그 꿈이었어."

[나레이션] 무영이라 불리는 이 청년은 노비 출신이었다. 매일 밤 같은 꿈에 시달렸다.

[노인] "젊은이, 아직 깨어 있었군."

[무영] "어르신! 언제 오셨습니까?"

[노인] "때가 되었다. 네게 전할 것이 있다."

[남자] 이봐! 거기 누구야!

[나레이션] 밖에서 누군가의 외침이 들려왔다.
"""

    print("=== 다중 음성 TTS 테스트 ===")

    # 스크립트 파싱
    segments = parse_script_to_segments(test_script)

    print(f"\n파싱된 세그먼트: {len(segments)}개")
    for seg in segments:
        print(f"  [{seg.tag}] {seg.voice} - {seg.text[:30]}...")

    # TTS 생성 (실제 API 키 필요)
    # result = generate_multi_voice_tts(segments, "outputs/wuxia_test", "test001")
    # print(f"\n결과: {result}")
