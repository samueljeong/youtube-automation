"""
TTS & SRT Smoke Test
Step3 TTS 및 자막 생성 기능이 정상 동작하는지 확인

Usage:
    python3 -m step3_tts_and_subtitles.tts_srt_smoke_test
    또는
    python3 step3_tts_and_subtitles/tts_srt_smoke_test.py
"""

import os
import sys
import json
import tempfile
import shutil
from typing import Dict, Any, List, Optional

# 테스트용 샘플 세그먼트
SAMPLE_SEGMENTS = [
    {
        "id": "test_scene1",
        "narration": "옛날 우리 동네 구멍가게에는 항상 달콤한 냄새가 가득했습니다.",
        "speaker_gender": "male"
    },
    {
        "id": "test_scene2",
        "narration": "겨울이면 연탄 냄새가 퍼지고, 아이들 웃음소리가 골목을 채웠죠.",
        "speaker_gender": "male"
    }
]


def check_dependencies() -> bool:
    """필요한 라이브러리 설치 확인"""
    missing = []

    try:
        from gtts import gTTS
    except ImportError:
        missing.append("gtts")

    try:
        from mutagen.mp3 import MP3
    except ImportError:
        missing.append("mutagen")

    if missing:
        print("❌ 필요한 라이브러리가 설치되지 않았습니다:")
        for lib in missing:
            print(f"   pip install {lib}")
        return False

    return True


def test_tts_generation(output_dir: str) -> Dict[str, Any]:
    """TTS 음성 생성 테스트"""
    print("\n[TTS TEST] TTS 음성 생성 테스트 시작...")

    results = {
        "success": True,
        "generated_files": [],
        "errors": []
    }

    try:
        from .call_google_tts import generate_tts, get_audio_duration, estimate_audio_duration
    except ImportError:
        # 직접 실행 시
        from call_google_tts import generate_tts, get_audio_duration, estimate_audio_duration

    for i, segment in enumerate(SAMPLE_SEGMENTS):
        scene_id = segment["id"]
        narration = segment["narration"]
        gender = segment["speaker_gender"]

        output_path = os.path.join(output_dir, f"{scene_id}.mp3")

        print(f"\n  [{i+1}/{len(SAMPLE_SEGMENTS)}] 생성 중: {scene_id}")
        print(f"      텍스트: {narration[:30]}...")

        try:
            result = generate_tts(
                text=narration,
                gender=gender,
                output_filename=output_path,
                speaking_rate=0.9
            )

            if result and os.path.exists(result):
                # 파일 크기 확인
                file_size = os.path.getsize(result)
                duration = get_audio_duration(result)
                if duration == 0:
                    duration = estimate_audio_duration(narration)

                print(f"      ✅ 생성 완료: {file_size} bytes, {duration:.1f}초")
                results["generated_files"].append({
                    "scene_id": scene_id,
                    "path": result,
                    "size": file_size,
                    "duration": duration
                })
            else:
                print(f"      ❌ 생성 실패: 파일이 생성되지 않음")
                results["success"] = False
                results["errors"].append(f"{scene_id}: 파일 생성 실패")

        except Exception as e:
            print(f"      ❌ 오류 발생: {e}")
            results["success"] = False
            results["errors"].append(f"{scene_id}: {str(e)}")

    return results


def test_srt_generation(output_dir: str, tts_results: Dict[str, Any]) -> Dict[str, Any]:
    """SRT 자막 생성 테스트"""
    print("\n[SRT TEST] SRT 자막 생성 테스트 시작...")

    results = {
        "success": True,
        "generated_files": [],
        "errors": []
    }

    try:
        from .generate_audio import generate_srt_file, _seconds_to_srt_time
    except ImportError:
        from generate_audio import generate_srt_file, _seconds_to_srt_time

    # 자막 라인 구성
    subtitle_lines = []
    current_time = 0.0

    for i, segment in enumerate(SAMPLE_SEGMENTS):
        # TTS 결과에서 duration 가져오기
        duration = 5.0  # 기본값
        for gen_file in tts_results.get("generated_files", []):
            if gen_file["scene_id"] == segment["id"]:
                duration = gen_file["duration"]
                break

        subtitle_lines.append({
            "start": current_time,
            "end": current_time + duration,
            "text": segment["narration"]
        })
        current_time += duration

    # SRT 파일 생성
    srt_path = os.path.join(output_dir, "test_subtitles.srt")

    try:
        result = generate_srt_file(subtitle_lines, srt_path)

        if result and os.path.exists(result):
            # 파일 내용 확인
            with open(result, "r", encoding="utf-8") as f:
                content = f.read()

            line_count = content.count("\n\n")
            print(f"  ✅ SRT 생성 완료: {srt_path}")
            print(f"     자막 라인 수: {line_count}")
            print(f"     파일 미리보기:")
            preview = content[:300] + "..." if len(content) > 300 else content
            for line in preview.split("\n")[:10]:
                print(f"       {line}")

            results["generated_files"].append({
                "path": result,
                "line_count": line_count
            })
        else:
            print(f"  ❌ SRT 생성 실패")
            results["success"] = False
            results["errors"].append("SRT 파일 생성 실패")

    except Exception as e:
        print(f"  ❌ 오류 발생: {e}")
        results["success"] = False
        results["errors"].append(str(e))

    return results


def test_audio_sync(tts_results: Dict[str, Any]) -> Dict[str, Any]:
    """오디오-자막 싱크 테스트 (Duration 비교)"""
    print("\n[SYNC TEST] 오디오-자막 싱크 테스트...")

    results = {
        "success": True,
        "sync_info": [],
        "errors": []
    }

    try:
        from .call_google_tts import estimate_audio_duration
    except ImportError:
        from call_google_tts import estimate_audio_duration

    for i, segment in enumerate(SAMPLE_SEGMENTS):
        scene_id = segment["id"]
        narration = segment["narration"]

        # 실제 duration vs 추정 duration 비교
        actual_duration = 0
        for gen_file in tts_results.get("generated_files", []):
            if gen_file["scene_id"] == scene_id:
                actual_duration = gen_file["duration"]
                break

        estimated_duration = estimate_audio_duration(narration)

        diff = abs(actual_duration - estimated_duration)
        sync_ok = diff < 3.0  # 3초 이내 차이면 OK

        status = "✅" if sync_ok else "⚠️"
        print(f"  {status} {scene_id}:")
        print(f"      실제: {actual_duration:.1f}초, 추정: {estimated_duration:.1f}초, 차이: {diff:.1f}초")

        results["sync_info"].append({
            "scene_id": scene_id,
            "actual": actual_duration,
            "estimated": estimated_duration,
            "diff": diff,
            "sync_ok": sync_ok
        })

        if not sync_ok:
            results["errors"].append(f"{scene_id}: 싱크 차이 {diff:.1f}초")

    return results


def run_smoke_test() -> bool:
    """전체 스모크 테스트 실행"""
    print("=" * 50)
    print("🔎 TTS & SRT Smoke Test")
    print("=" * 50)

    # 1) 의존성 확인
    print("\n[1/4] 라이브러리 확인...")
    if not check_dependencies():
        return False
    print("✅ 필요한 라이브러리 설치됨")

    # 임시 디렉토리 생성
    temp_dir = tempfile.mkdtemp(prefix="tts_srt_test_")
    print(f"\n[INFO] 임시 디렉토리: {temp_dir}")

    try:
        # 2) TTS 테스트
        print("\n[2/4] TTS 생성 테스트...")
        tts_results = test_tts_generation(temp_dir)

        if not tts_results["success"]:
            print("\n❌ TTS 테스트 실패")
            for err in tts_results["errors"]:
                print(f"   - {err}")
            return False
        print("✅ TTS 테스트 통과")

        # 3) SRT 테스트
        print("\n[3/4] SRT 생성 테스트...")
        srt_results = test_srt_generation(temp_dir, tts_results)

        if not srt_results["success"]:
            print("\n❌ SRT 테스트 실패")
            for err in srt_results["errors"]:
                print(f"   - {err}")
            return False
        print("✅ SRT 테스트 통과")

        # 4) 싱크 테스트
        print("\n[4/4] 오디오-자막 싱크 테스트...")
        sync_results = test_audio_sync(tts_results)
        print("✅ 싱크 테스트 완료")

        # 최종 결과
        print("\n" + "=" * 50)
        print("🎉 TTS & SRT Smoke Test 통과!")
        print("=" * 50)

        total_duration = sum(f["duration"] for f in tts_results["generated_files"])
        print(f"\n요약:")
        print(f"  - 생성된 TTS 파일: {len(tts_results['generated_files'])}개")
        print(f"  - 총 오디오 길이: {total_duration:.1f}초")
        print(f"  - SRT 파일: {len(srt_results['generated_files'])}개")

        return True

    finally:
        # 임시 디렉토리 정리
        print(f"\n[CLEANUP] 임시 디렉토리 삭제: {temp_dir}")
        shutil.rmtree(temp_dir, ignore_errors=True)


if __name__ == "__main__":
    success = run_smoke_test()
    sys.exit(0 if success else 1)
