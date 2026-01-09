#!/usr/bin/env python3
"""
하이브리드 TTS 테스트 스크립트

ElevenLabs (나레이션) + Gemini TTS (대사) 조합 테스트
"""

import os
import sys

# 프로젝트 루트를 path에 추가
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from scripts.isekai_pipeline.tts import generate_hybrid_tts


def test_hybrid_tts_short():
    """짧은 대본으로 하이브리드 TTS 테스트"""

    # 테스트용 짧은 대본 (EP001 일부)
    test_script = """
어둠 속에서 목소리가 들려왔다. "이 검법을 네게 전하마." 주름진 손이 어린 소년의 이마를 짚는 순간, 머릿속으로 밀려드는 것이 있었다.

"네 눈빛이 마음에 든다." 노인이 말했다. 버려진 절터에서 만난 그 노인의 이름은 끝내 알지 못했다.

그러던 어느 날이었다. "당신이... 혈영인가요?" 하얀 옷을 입은 여인이 앞을 막아섰다. 밤이었고, 보름달이 하늘에 떠 있었다.

"무섭지 않아요." 그녀가 웃으며 말했다. 달빛처럼 고운 미소였다.
"""

    output_dir = "outputs/isekai/EP001/audio/hybrid_test"

    print("=" * 60)
    print("하이브리드 TTS 테스트 (짧은 대본)")
    print("=" * 60)
    print(f"대본 길이: {len(test_script)}자")
    print(f"출력 디렉토리: {output_dir}")
    print("=" * 60)

    result = generate_hybrid_tts(
        episode_id="test_hybrid",
        script=test_script,
        output_dir=output_dir,
    )

    if result.get("ok"):
        print("\n" + "=" * 60)
        print("테스트 성공!")
        print(f"오디오: {result['audio_path']}")
        print(f"자막: {result['srt_path']}")
        print(f"총 길이: {result['duration']:.1f}초")
        print(f"대사 수: {result['dialogues_count']}개")
        print("=" * 60)
        return True
    else:
        print(f"\n테스트 실패: {result.get('error')}")
        return False


if __name__ == "__main__":
    # 환경변수 체크
    if not os.environ.get('ELEVENLABS_API_KEY'):
        print("ELEVENLABS_API_KEY 환경변수가 필요합니다")
        sys.exit(1)
    if not os.environ.get('GOOGLE_API_KEY'):
        print("GOOGLE_API_KEY 환경변수가 필요합니다")
        sys.exit(1)

    success = test_hybrid_tts_short()
    sys.exit(0 if success else 1)
