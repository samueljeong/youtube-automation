"""
Call GPT for Step 3 TTS Engine
TTS-friendly script, timeline, subtitle generation
"""

import os
import json
from pathlib import Path
from typing import Dict, Any, List


def load_system_prompt() -> str:
    """Load system prompt from tts_prompt.txt"""
    prompt_path = Path(__file__).parent / "tts_prompt.txt"
    if prompt_path.exists():
        return prompt_path.read_text(encoding="utf-8")
    else:
        raise FileNotFoundError(f"System prompt not found: {prompt_path}")


def generate_tts_output(step1_output: Dict[str, Any]) -> Dict[str, Any]:
    """
    Generate TTS-friendly script, timeline, and subtitles

    Args:
        step1_output: Step1 script generation result

    Returns:
        Step3 output with tts_script, timeline, subtitle_lines
    """
    api_key = os.getenv("OPENAI_API_KEY")
    scenes = step1_output.get("scenes", [])
    titles = step1_output.get("titles", {})
    title = titles.get("main_title", "Untitled")

    print(f"[Step3] Processing {len(scenes)} scenes for TTS")

    if not api_key:
        print("[WARNING] OPENAI_API_KEY not set. Using rule-based conversion.")
        return _generate_rule_based_output(step1_output)

    try:
        from openai import OpenAI

        client = OpenAI(api_key=api_key)
        system_prompt = load_system_prompt()

        print("[GPT] Calling GPT for TTS-friendly script generation...")

        input_for_gpt = {
            "scenes": [
                {
                    "id": scene.get("id"),
                    "narration": scene.get("narration", ""),
                    "emotion": scene.get("emotion", "nostalgic"),
                    "visual_description": scene.get("visual_description", "")
                }
                for scene in scenes
            ]
        }

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": json.dumps(input_for_gpt, ensure_ascii=False)}
            ],
            max_tokens=4096,
            temperature=0.7
        )

        response_text = response.choices[0].message.content
        print(f"[GPT] Response received ({len(response_text)} chars)")

        result = _parse_json_response(response_text)
        return _ensure_pipeline_compatibility(result, step1_output)

    except ImportError:
        print("[ERROR] openai package not installed. Using rule-based conversion.")
        return _generate_rule_based_output(step1_output)
    except Exception as e:
        print(f"[ERROR] API call failed: {e}")
        print("[FALLBACK] Using rule-based conversion.")
        return _generate_rule_based_output(step1_output)


def _parse_json_response(response_text: str) -> Dict[str, Any]:
    """Extract and parse JSON from response text"""
    text = response_text.strip()

    if text.startswith("```json"):
        text = text[7:]
    elif text.startswith("```"):
        text = text[3:]

    if text.endswith("```"):
        text = text[:-3]

    text = text.strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        print(f"[ERROR] JSON parsing failed: {e}")
        print(f"[DEBUG] Response text: {text[:500]}...")
        raise


def _ensure_pipeline_compatibility(result: Dict[str, Any], step1_output: Dict[str, Any]) -> Dict[str, Any]:
    """Ensure pipeline compatibility"""
    titles = step1_output.get("titles", {})
    title = titles.get("main_title", "Untitled")

    result["step"] = "step3_tts_result"
    result["title"] = title

    # Ensure timeline exists
    if "timeline" not in result:
        result["timeline"] = []

    # Ensure subtitle_lines exists
    if "subtitle_lines" not in result:
        result["subtitle_lines"] = []

    # Create audio_files structure for pipeline compatibility
    result["audio_files"] = []
    for i, scene in enumerate(result.get("timeline", [])):
        scene_id = scene.get("id", f"scene{i+1}")
        result["audio_files"].append({
            "scene_id": scene_id,
            "order": i + 1,
            "audio_filename": f"audio/{scene_id}.mp3",
            "subtitle_filename": f"subtitles/{scene_id}.srt",
            "duration_seconds": scene.get("end", 0) - scene.get("start", 0)
        })

    return result


def _generate_rule_based_output(step1_output: Dict[str, Any]) -> Dict[str, Any]:
    """Generate TTS output using rule-based conversion (fallback)"""
    scenes = step1_output.get("scenes", [])
    titles = step1_output.get("titles", {})
    title = titles.get("main_title", "Untitled")

    # Build TTS script
    tts_script_parts = []
    timeline = []
    subtitle_lines = []
    audio_files = []

    current_time = 0.0

    for i, scene in enumerate(scenes):
        scene_id = scene.get("id", f"scene{i+1}")
        narration = scene.get("narration", "")
        emotion = scene.get("emotion", "nostalgic")

        # Convert to TTS-friendly text
        tts_text = _convert_to_tts_friendly(narration)
        tts_script_parts.append(tts_text)

        # Calculate duration based on syllables
        duration = _calculate_duration(tts_text, emotion)

        # Add to timeline
        start_time = current_time
        end_time = current_time + duration
        timeline.append({
            "id": scene_id,
            "start": round(start_time, 1),
            "end": round(end_time, 1)
        })

        # Generate subtitles for this scene
        scene_subtitles = _generate_subtitles(tts_text, start_time, end_time)
        subtitle_lines.extend(scene_subtitles)

        # Add audio file info
        audio_files.append({
            "scene_id": scene_id,
            "order": i + 1,
            "audio_filename": f"audio/{scene_id}.mp3",
            "subtitle_filename": f"subtitles/{scene_id}.srt",
            "duration_seconds": duration
        })

        current_time = end_time

    return {
        "step": "step3_tts_result",
        "title": title,
        "tts_script": "\n\n".join(tts_script_parts),
        "timeline": timeline,
        "subtitle_lines": subtitle_lines,
        "audio_files": audio_files
    }


def _convert_to_tts_friendly(text: str) -> str:
    """Convert narration to TTS-friendly format"""
    if not text:
        return ""

    # Remove parentheses content
    import re
    text = re.sub(r'\([^)]*\)', '', text)

    # Remove special characters that break TTS
    text = text.replace("...", ", ")
    text = text.replace("…", ", ")

    # Add commas for natural pauses
    # After proper nouns and place names
    text = re.sub(r'(역|리|동|면|군|시|구)에서', r'\1, 에서', text)

    # Soften the tone for seniors
    text = text.replace("~입니다", "입니다")
    text = text.replace("~요", "요")

    return text.strip()


def _calculate_duration(text: str, emotion: str) -> float:
    """Calculate duration based on syllable count and emotion"""
    if not text:
        return 3.0

    # Count Korean syllables (rough estimate)
    import re
    korean_chars = len(re.findall(r'[가-힣]', text))
    other_chars = len(re.findall(r'[a-zA-Z0-9]', text))

    total_syllables = korean_chars + (other_chars * 0.5)

    # Syllables per second based on emotion
    speed_map = {
        "nostalgia": 3.0,  # slower
        "warmth": 3.2,
        "bittersweet": 3.1,
        "comfort": 3.2
    }
    syllables_per_second = speed_map.get(emotion, 3.2)

    duration = total_syllables / syllables_per_second

    # Minimum 3 seconds, maximum 30 seconds per scene
    return max(3.0, min(30.0, duration))


def _generate_subtitles(text: str, start: float, end: float) -> List[Dict[str, Any]]:
    """Generate subtitle lines for a scene"""
    if not text:
        return []

    # Split into sentences
    import re
    sentences = re.split(r'[.!?。]\s*', text)
    sentences = [s.strip() for s in sentences if s.strip()]

    if not sentences:
        return [{"start": round(start, 1), "end": round(end, 1), "text": text}]

    # Distribute time evenly
    duration = end - start
    time_per_sentence = duration / len(sentences)

    subtitles = []
    current_time = start

    for sentence in sentences:
        # Split long sentences (over 22 chars)
        if len(sentence) > 22:
            parts = _split_long_sentence(sentence)
            sub_duration = time_per_sentence / len(parts)
            for part in parts:
                subtitles.append({
                    "start": round(current_time, 1),
                    "end": round(current_time + sub_duration, 1),
                    "text": part
                })
                current_time += sub_duration
        else:
            subtitles.append({
                "start": round(current_time, 1),
                "end": round(current_time + time_per_sentence, 1),
                "text": sentence
            })
            current_time += time_per_sentence

    return subtitles


def _split_long_sentence(sentence: str, max_len: int = 20) -> List[str]:
    """Split long sentence into parts"""
    if len(sentence) <= max_len:
        return [sentence]

    # Try to split at comma
    if ',' in sentence:
        parts = sentence.split(',')
        return [p.strip() for p in parts if p.strip()]

    # Otherwise split at middle
    mid = len(sentence) // 2
    return [sentence[:mid].strip(), sentence[mid:].strip()]


if __name__ == "__main__":
    mock_step1 = {
        "titles": {"main_title": "Test Title"},
        "scenes": [
            {
                "id": "scene1",
                "narration": "그 시절 우리 동네 구멍가게는 겨울이면 김 모락모락 났습니다.",
                "emotion": "nostalgia"
            }
        ]
    }

    result = generate_tts_output(mock_step1)
    print(json.dumps(result, ensure_ascii=False, indent=2))
