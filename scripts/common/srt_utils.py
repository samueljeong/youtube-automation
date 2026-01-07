"""
SRT 자막 유틸리티
"""
import os
from typing import List, Dict


def generate_srt_from_timeline(timeline: List[Dict], srt_path: str) -> bool:
    """타임라인에서 SRT 자막 생성"""
    os.makedirs(os.path.dirname(srt_path), exist_ok=True)

    with open(srt_path, "w", encoding="utf-8") as f:
        for i, entry in enumerate(timeline, 1):
            start = sec_to_srt_time(entry['start_sec'])
            end = sec_to_srt_time(entry['end_sec'])
            text = entry['text']

            # 대사에 캐릭터 표시 (옵션)
            if entry.get('tag', '나레이션') != "나레이션":
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
