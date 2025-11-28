"""
Actual Audio Generation for Step 3
각 씬별로 실제 TTS 오디오 파일 생성

Usage:
    pip install gtts  # 무료 TTS
    python3 generate_audio.py
"""

import os
import json
from pathlib import Path
from typing import Dict, Any, List, Optional
from .call_google_tts import generate_tts, get_audio_duration, estimate_audio_duration


def generate_all_scene_audio(
    step1_output: Dict[str, Any],
    output_dir: str = "outputs/audio"
) -> Dict[str, Any]:
    """
    Step1 출력의 모든 씬에 대해 TTS 오디오 생성

    Args:
        step1_output: Step1 출력 (scenes 포함)
        output_dir: 오디오 저장 디렉토리

    Returns:
        오디오 정보가 포함된 Step3 출력
    """
    scenes = step1_output.get("scenes", [])
    titles = step1_output.get("titles", {})
    title = titles.get("main_title", "Untitled")

    print(f"\n=== [Audio Generation] Generating TTS for {len(scenes)} scenes ===")

    os.makedirs(output_dir, exist_ok=True)

    audio_files = []
    timeline = []
    tts_script_parts = []
    current_time = 0.0

    for i, scene in enumerate(scenes):
        scene_id = scene.get("id", f"scene{i+1}")
        narration = scene.get("narration", "")
        gender = scene.get("speaker_gender", "male")

        if not narration:
            print(f"[WARNING] No narration for {scene_id}, skipping")
            continue

        output_path = os.path.join(output_dir, f"{scene_id}.mp3")

        print(f"\n[Scene {i+1}/{len(scenes)}] Generating {scene_id}...")
        result = generate_tts(
            text=narration,
            gender=gender,
            output_filename=output_path,
            speaking_rate=0.9  # 시니어용 약간 느린 속도
        )

        if result and os.path.exists(result):
            # 실제 오디오 길이 측정
            duration = get_audio_duration(result)
            if duration == 0:
                duration = estimate_audio_duration(narration)

            audio_files.append({
                "scene_id": scene_id,
                "order": i + 1,
                "audio_filename": result,
                "audio_path": result,  # FFmpeg 호환용
                "subtitle_filename": f"subtitles/{scene_id}.srt",
                "duration_seconds": round(duration, 2)
            })

            # Timeline 추가
            timeline.append({
                "id": scene_id,
                "start": round(current_time, 2),
                "end": round(current_time + duration, 2),
                "audio_path": result  # FFmpeg 호환용
            })

            tts_script_parts.append(narration)
            current_time += duration

            print(f"[Audio] Generated: {result} ({duration:.1f}s)")
        else:
            print(f"[WARNING] Failed to generate audio for {scene_id}")
            # 실패해도 timeline에 추가 (추정 duration 사용)
            duration = estimate_audio_duration(narration)
            timeline.append({
                "id": scene_id,
                "start": round(current_time, 2),
                "end": round(current_time + duration, 2),
                "audio_path": output_path
            })
            audio_files.append({
                "scene_id": scene_id,
                "order": i + 1,
                "audio_filename": output_path,
                "audio_path": output_path,
                "subtitle_filename": f"subtitles/{scene_id}.srt",
                "duration_seconds": round(duration, 2)
            })
            current_time += duration

    # 자막 라인 생성
    subtitle_lines = _generate_subtitle_lines(scenes, timeline)

    print(f"\n[Audio Generation] Complete: {len(audio_files)} audio files generated")
    print(f"[Audio Generation] Total duration: {current_time:.1f} seconds")

    return {
        "step": "step3_tts_result",
        "title": title,
        "tts_script": "\n\n".join(tts_script_parts),
        "timeline": timeline,
        "subtitle_lines": subtitle_lines,
        "audio_files": audio_files,
        "total_duration_seconds": round(current_time, 2)
    }


def _generate_subtitle_lines(
    scenes: List[Dict[str, Any]],
    timeline: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """자막 라인 생성"""
    import re

    subtitle_lines = []

    for scene, time_info in zip(scenes, timeline):
        narration = scene.get("narration", "")
        start = time_info.get("start", 0)
        end = time_info.get("end", 0)

        if not narration:
            continue

        # 문장 단위로 분리
        sentences = re.split(r'[.!?。]\s*', narration)
        sentences = [s.strip() for s in sentences if s.strip()]

        if not sentences:
            subtitle_lines.append({
                "start": round(start, 1),
                "end": round(end, 1),
                "text": narration
            })
            continue

        # 시간 균등 배분
        duration = end - start
        time_per_sentence = duration / len(sentences)
        current = start

        for sentence in sentences:
            # 긴 문장 분리 (22자 초과)
            if len(sentence) > 22:
                parts = _split_long_sentence(sentence)
                sub_duration = time_per_sentence / len(parts)
                for part in parts:
                    subtitle_lines.append({
                        "start": round(current, 1),
                        "end": round(current + sub_duration, 1),
                        "text": part
                    })
                    current += sub_duration
            else:
                subtitle_lines.append({
                    "start": round(current, 1),
                    "end": round(current + time_per_sentence, 1),
                    "text": sentence
                })
                current += time_per_sentence

    return subtitle_lines


def _split_long_sentence(sentence: str, max_len: int = 20) -> List[str]:
    """긴 문장을 적절히 분리"""
    if len(sentence) <= max_len:
        return [sentence]

    # 쉼표로 분리 시도
    if ',' in sentence:
        parts = sentence.split(',')
        return [p.strip() for p in parts if p.strip()]

    # 중간에서 분리
    mid = len(sentence) // 2
    return [sentence[:mid].strip(), sentence[mid:].strip()]


def generate_srt_file(
    subtitle_lines: List[Dict[str, Any]],
    output_path: str
) -> str:
    """SRT 자막 파일 생성"""
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as f:
        for i, line in enumerate(subtitle_lines, 1):
            start = _seconds_to_srt_time(line["start"])
            end = _seconds_to_srt_time(line["end"])
            text = line["text"]

            f.write(f"{i}\n")
            f.write(f"{start} --> {end}\n")
            f.write(f"{text}\n\n")

    return output_path


def _seconds_to_srt_time(seconds: float) -> str:
    """초를 SRT 시간 형식으로 변환 (HH:MM:SS,mmm)"""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int((seconds % 1) * 1000)

    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


if __name__ == "__main__":
    # 테스트
    mock_step1 = {
        "titles": {"main_title": "테스트 영상"},
        "scenes": [
            {
                "id": "scene1",
                "narration": "안녕하세요. 오늘은 옛날 우리 동네 구멍가게 이야기를 들려드릴게요.",
                "speaker_gender": "male"
            },
            {
                "id": "scene2",
                "narration": "겨울이면 문틈으로 새어나오던 연탄 냄새가 생각납니다.",
                "speaker_gender": "male"
            }
        ]
    }

    result = generate_all_scene_audio(mock_step1, "outputs/test_audio")
    print(json.dumps(result, ensure_ascii=False, indent=2))
