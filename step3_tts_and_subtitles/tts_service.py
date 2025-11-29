"""
TTS Service - Step3 메인 파이프라인
5000바이트 제한 해결 + FFmpeg 병합 + SRT 자막 생성

핵심 흐름:
1. 씬별 나레이션 → 청크 분할 (tts_chunking)
2. 청크별 TTS 호출 → WAV/MP3 세그먼트 생성
3. FFmpeg로 전체 오디오 병합
4. 문장별 타임라인 계산 → SRT 자막 생성
"""

import os
import uuid
import subprocess
import tempfile
from typing import Dict, Any, List, Optional

from .tts_chunking import build_chunks_for_scenes, estimate_chunk_stats

# 출력 디렉토리
AUDIO_DIR = "outputs/audio"
SUBTITLE_DIR = "outputs/subtitles"

os.makedirs(AUDIO_DIR, exist_ok=True)
os.makedirs(SUBTITLE_DIR, exist_ok=True)


def run_tts_pipeline(step3_input: Dict[str, Any]) -> Dict[str, Any]:
    """
    Step3 TTS 전체 파이프라인 실행
    
    Args:
        step3_input: {
            "episode_id": "...",
            "language": "ko-KR",
            "voice": { "gender": "MALE", "name": "ko-KR-Neural2-B", "speaking_rate": 0.9 },
            "scenes": [{ "id": "scene1", "narration": "..." }, ...]
        }
        
    Returns:
        {
            "ok": True,
            "episode_id": "...",
            "audio_file": "outputs/audio/xxx_full.mp3",
            "srt_file": "outputs/subtitles/xxx.srt",
            "timeline": [...],
            "stats": {...}
        }
    """
    episode_id = step3_input.get("episode_id") or str(uuid.uuid4())[:12]
    scenes = step3_input.get("scenes", [])
    
    voice_config = {
        "language_code": step3_input.get("language", "ko-KR"),
        "name": step3_input.get("voice", {}).get("name", "ko-KR-Neural2-B"),
        "gender": step3_input.get("voice", {}).get("gender", "MALE"),
        "speaking_rate": step3_input.get("voice", {}).get("speaking_rate", 0.9),
    }
    
    print(f"[TTS-PIPELINE] 시작: episode={episode_id}, scenes={len(scenes)}")
    
    # 1. 씬 → 청크 리스트 생성
    chunks = build_chunks_for_scenes(scenes)
    chunk_stats = estimate_chunk_stats(chunks)
    print(f"[TTS-PIPELINE] 청크 생성: {chunk_stats}")
    
    if not chunks:
        return {
            "ok": False,
            "error": "나레이션이 없습니다.",
            "episode_id": episode_id
        }
    
    # 2. 청크별 TTS 생성
    audio_segments = []
    
    for idx, chunk in enumerate(chunks):
        print(f"[TTS-PIPELINE] TTS 생성 {idx+1}/{len(chunks)}: {chunk['byte_length']}bytes")
        
        filename = f"{episode_id}_chunk_{idx:03d}.mp3"
        out_path = os.path.join(AUDIO_DIR, filename)
        
        # TTS 호출
        success = synthesize_chunk_google_api(
            text=chunk["text"],
            voice_config=voice_config,
            output_path=out_path
        )
        
        if success:
            duration = get_audio_duration_ffprobe(out_path)
        else:
            duration = estimate_duration_from_text(chunk["text"], voice_config["speaking_rate"])
        
        audio_segments.append({
            "scene_id": chunk["scene_id"],
            "chunk_index": chunk["chunk_index"],
            "file": out_path,
            "sentences": chunk["sentences"],
            "duration_sec": duration,
            "success": success
        })
    
    # 3. 전체 오디오 병합 (FFmpeg)
    successful_files = [seg["file"] for seg in audio_segments if seg["success"]]
    
    if not successful_files:
        return {
            "ok": False,
            "error": "TTS 생성 실패",
            "episode_id": episode_id
        }
    
    merged_path = os.path.join(AUDIO_DIR, f"{episode_id}_full.mp3")
    concat_audio_ffmpeg(successful_files, merged_path)
    
    # 4. SRT 자막 생성
    srt_path = os.path.join(SUBTITLE_DIR, f"{episode_id}.srt")
    timeline = build_srt_from_segments(audio_segments, srt_path)
    
    # 결과 반환
    total_duration = sum(seg["duration_sec"] for seg in audio_segments)
    
    return {
        "ok": True,
        "episode_id": episode_id,
        "audio_file": merged_path,
        "srt_file": srt_path,
        "timeline": timeline,
        "stats": {
            **chunk_stats,
            "total_duration_sec": round(total_duration, 1),
            "successful_chunks": len(successful_files),
            "failed_chunks": len(chunks) - len(successful_files)
        }
    }


def synthesize_chunk_google_api(
    text: str,
    voice_config: Dict,
    output_path: str
) -> bool:
    """
    Google Cloud TTS API REST 호출로 음성 생성
    
    Returns:
        성공 여부
    """
    import requests
    import base64
    
    api_key = os.getenv("GOOGLE_CLOUD_API_KEY", "")
    
    if not api_key:
        print("[TTS] GOOGLE_CLOUD_API_KEY 없음, gTTS 폴백")
        return synthesize_chunk_gtts(text, output_path, voice_config.get("speaking_rate", 0.9))
    
    url = f"https://texttospeech.googleapis.com/v1/text:synthesize?key={api_key}"
    
    # 속도/피치 변환
    speaking_rate = voice_config.get("speaking_rate", 0.9)
    
    payload = {
        "input": {"text": text},
        "voice": {
            "languageCode": voice_config.get("language_code", "ko-KR"),
            "name": voice_config.get("name", "ko-KR-Neural2-B")
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
            
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            with open(output_path, "wb") as f:
                f.write(audio_content)
            
            return True
        else:
            print(f"[TTS] Google API 오류: {response.status_code}")
            return synthesize_chunk_gtts(text, output_path, speaking_rate)
            
    except Exception as e:
        print(f"[TTS] 오류: {e}")
        return synthesize_chunk_gtts(text, output_path, speaking_rate)


def synthesize_chunk_gtts(text: str, output_path: str, speaking_rate: float = 0.9) -> bool:
    """gTTS 폴백 (무료)"""
    try:
        from gtts import gTTS
        
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        slow = speaking_rate < 0.85
        tts = gTTS(text=text, lang='ko', slow=slow)
        tts.save(output_path)
        
        return True
    except Exception as e:
        print(f"[gTTS] 오류: {e}")
        return False


def get_audio_duration_ffprobe(path: str) -> float:
    """ffprobe로 오디오 길이(초) 측정"""
    if not os.path.exists(path):
        return 0.0
    
    try:
        cmd = [
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            path
        ]
        out = subprocess.check_output(cmd, stderr=subprocess.DEVNULL).decode().strip()
        return float(out)
    except Exception:
        return estimate_duration_from_file_size(path)


def estimate_duration_from_file_size(path: str) -> float:
    """파일 크기 기반 재생 시간 추정 (MP3 128kbps 기준)"""
    try:
        file_size = os.path.getsize(path)
        return file_size / 16000  # 128kbps = 16KB/sec
    except Exception:
        return 0.0


def estimate_duration_from_text(text: str, speaking_rate: float = 0.9) -> float:
    """텍스트 길이 기반 재생 시간 추정"""
    char_count = len(text.replace(" ", "").replace("\n", ""))
    # 분당 150자 기준, speaking_rate 반영
    chars_per_sec = (150 * speaking_rate) / 60
    return char_count / chars_per_sec if chars_per_sec > 0 else 0.0


def concat_audio_ffmpeg(files: List[str], output_path: str) -> bool:
    """FFmpeg로 오디오 파일 병합"""
    if not files:
        return False
    
    if len(files) == 1:
        # 파일이 하나면 복사
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
        
        print(f"[TTS-MERGE] 병합 완료: {len(files)}개 → {output_path}")
        return True
        
    except Exception as e:
        print(f"[TTS-MERGE] 오류: {e}")
        return False


def build_srt_from_segments(audio_segments: List[Dict], srt_path: str) -> List[Dict]:
    """
    오디오 세그먼트 정보를 바탕으로 SRT 자막 생성
    
    문장별로 시간을 균등 배분하는 단순 버전
    """
    timeline = []
    current_time = 0.0
    index = 1
    
    for seg in audio_segments:
        if not seg.get("success"):
            continue
            
        seg_duration = seg.get("duration_sec", 0.0)
        sentences = seg.get("sentences", [])
        
        if not sentences or seg_duration <= 0:
            continue
        
        # 문장별 시간 균등 배분
        per_sentence = seg_duration / len(sentences)
        
        for sent in sentences:
            start = current_time
            end = current_time + per_sentence
            
            timeline.append({
                "index": index,
                "start_sec": round(start, 3),
                "end_sec": round(end, 3),
                "text": sent
            })
            
            index += 1
            current_time = end
    
    # SRT 파일 저장
    os.makedirs(os.path.dirname(srt_path), exist_ok=True)
    
    with open(srt_path, "w", encoding="utf-8") as f:
        for entry in timeline:
            f.write(f"{entry['index']}\n")
            f.write(f"{sec_to_srt_time(entry['start_sec'])} --> {sec_to_srt_time(entry['end_sec'])}\n")
            f.write(f"{entry['text']}\n\n")
    
    print(f"[SRT] 자막 생성: {len(timeline)}개 항목 → {srt_path}")
    return timeline


def sec_to_srt_time(sec: float) -> str:
    """초를 SRT 타임코드 형식으로 변환 (HH:MM:SS,mmm)"""
    h = int(sec // 3600)
    m = int((sec % 3600) // 60)
    s = int(sec % 60)
    ms = int((sec - int(sec)) * 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


# ===== 테스트 =====
if __name__ == "__main__":
    import json
    
    test_input = {
        "episode_id": "test_001",
        "language": "ko-KR",
        "voice": {
            "gender": "MALE",
            "name": "ko-KR-Neural2-B",
            "speaking_rate": 0.9
        },
        "scenes": [
            {
                "id": "scene1",
                "narration": "오늘은 그 시절, 우리 동네 작은 구멍가게 이야기를 나눠보려고 합니다. 아침마다 문을 열던 구멍가게 앞에는 늘 아이들이 모여들었어요."
            },
            {
                "id": "scene2", 
                "narration": "그때 우리 동네 아이들은 학교가 끝나면 항상 그 가게 앞으로 모였습니다. 손에 쥔 몇십 원짜리 동전 하나로 무엇을 살지 한참을 고민하던 그때가 떠오릅니다."
            }
        ]
    }
    
    print("=== TTS 파이프라인 테스트 ===")
    result = run_tts_pipeline(test_input)
    print(json.dumps(result, ensure_ascii=False, indent=2))
