"""
Subtitle Generator for Step 3
나레이션 텍스트를 SRT 형식 자막으로 변환
"""

from typing import List


def generate_srt(narration: str, duration_seconds: float, start_offset: float = 0.0) -> str:
    """
    나레이션 텍스트를 SRT 형식 자막으로 변환

    Args:
        narration: 나레이션 텍스트
        duration_seconds: 전체 오디오 길이(초)
        start_offset: 시작 시간 오프셋(초)

    Returns:
        SRT 형식 문자열
    """
    segments = _split_narration(narration)

    if not segments:
        return ""

    segment_duration = duration_seconds / len(segments) if segments else 0

    srt_lines = []
    current_time = start_offset

    for idx, segment in enumerate(segments, 1):
        start_time = current_time
        end_time = current_time + segment_duration

        srt_entry = _format_srt_entry(idx, start_time, end_time, segment)
        srt_lines.append(srt_entry)

        current_time = end_time

    return "\n".join(srt_lines)


def _split_narration(narration: str) -> List[str]:
    """
    나레이션을 자막 단위로 분리 (한 줄 최대 18글자)
    """
    if not narration:
        return []

    import re
    max_chars_per_line = 18
    segments = []

    sentences = re.split(r'(?<=[.?!])\s*', narration)

    for sentence in sentences:
        sentence = sentence.strip()
        if not sentence:
            continue

        if len(sentence) <= max_chars_per_line:
            segments.append(sentence)
        else:
            sub_segments = _split_long_sentence(sentence, max_chars_per_line)
            segments.extend(sub_segments)

    return segments


def _split_long_sentence(sentence: str, max_chars: int) -> List[str]:
    """긴 문장을 최대 글자 수 기준으로 분리"""
    segments = []
    current_segment = ""

    parts = sentence.split(",")

    for i, part in enumerate(parts):
        part = part.strip()
        if i < len(parts) - 1:
            part += ","

        if len(current_segment) + len(part) + 1 <= max_chars:
            if current_segment:
                current_segment += " " + part
            else:
                current_segment = part
        else:
            if current_segment:
                segments.append(current_segment.strip())
            current_segment = part

    if current_segment:
        segments.append(current_segment.strip())

    final_segments = []
    for seg in segments:
        if len(seg) <= max_chars:
            final_segments.append(seg)
        else:
            for i in range(0, len(seg), max_chars):
                final_segments.append(seg[i:i + max_chars])

    return final_segments


def _format_srt_entry(index: int, start_time: float, end_time: float, text: str) -> str:
    """SRT 엔트리 포맷팅"""
    start_str = _seconds_to_srt_time(start_time)
    end_str = _seconds_to_srt_time(end_time)
    return f"{index}\n{start_str} --> {end_str}\n{text}\n"


def _seconds_to_srt_time(seconds: float) -> str:
    """초를 SRT 시간 형식으로 변환 (HH:MM:SS,mmm)"""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int((seconds % 1) * 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


if __name__ == "__main__":
    test_narration = "안녕하세요. 저는 경북 영덕군 병곡면에서 사십칠 년째 살고 있는 박용팔입니다."
    test_duration = 15.0
    srt_result = generate_srt(test_narration, test_duration)
    print("=== Generated SRT ===")
    print(srt_result)
