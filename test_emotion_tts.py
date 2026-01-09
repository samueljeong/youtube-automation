#!/usr/bin/env python3
"""감정 태그 TTS 테스트"""

import os
import sys

# 프로젝트 루트 추가
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, "scripts", "isekai_pipeline"))

# tts.py 직접 import (workers.py 의존성 피하기)
from tts import generate_tts

# 테스트 대본
TEST_SCRIPT = """
[회상] 설하의 얼굴이 스쳐 지나갔다. 마지막으로 본 그녀의 눈에는 두려움과 믿음이 함께 어려 있었다.
[회상] "무영아...!"
[충격] 그 목소리와 함께 눈이 떠졌고, 시야에 들어온 것은 낯선 천장이었다. 거칠게 다듬어진 돌벽으로 보아 어딘가 건물 안인 듯했다.
"...여기가 어디지."
몸을 일으키려 했으나 팔에 힘이 들어가질 않았다.
[긴장] 아니, 힘이 없는 게 아니었다. 내공 자체가 사라져 버린 것이다. 단전을 더듬어 보았으나 그곳은 텅 비어 아무런 기운도 느껴지지 않았다.
무영은 떨리는 손으로 가슴을 짚었다. 다행히 심장은 아직 힘차게 뛰고 있었다.
'살아있다.'
하지만 내공만은 돌아오지 않았다. 평생에 걸쳐 쌓아 올린 혈영심법의 기운이 흔적조차 남기지 않고 증발해 버린 것이다.
[비장] 그럼에도 몸은 여전히 기억하고 있었다. 수만 번 휘둘렀던 검의 궤적과 수천 번 피해냈던 공격의 감각이 근육 깊숙이 새겨져 있었다.
'검술만큼은 남아있다.'
창밖으로 한 줄기 빛이 스며들자 무영은 천천히 상체를 일으켰다.
[고요] 창 너머로 펼쳐진 하늘은 낯설기 그지없었다. 하늘에는 달이 두 개나 떠 있었다.
"......"
이곳은 무림이 아니었다. 그것만큼은 분명했다.
[비장] 무영은 천천히 주먹을 쥐었다. 어디든 상관없다. 살아남기만 하면 언젠가 길은 열린다.
[여운] 설하. 반드시 돌아가겠다. 그 다짐을 품은 채 이세계에서의 첫 아침이 밝아오고 있었다.
"""

def main():
    print("=" * 50)
    print("감정 태그 TTS 테스트")
    print("=" * 50)

    # 환경변수 확인
    api_key = os.environ.get('GOOGLE_CLOUD_API_KEY') or os.environ.get('GOOGLE_API_KEY')
    if not api_key:
        print("❌ GOOGLE_API_KEY 환경변수가 필요합니다")
        return

    print(f"✅ API Key 확인됨 (길이: {len(api_key)})")
    print()

    # TTS 생성 - 여러 음성 비교
    output_dir = "outputs/isekai/audio"

    # 테스트할 남성 음성들
    male_voices = ["Fenrir"]  # SSML break 테스트용

    for voice in male_voices:
        print(f"\n{'='*50}")
        print(f"음성: {voice}")
        print("="*50)

        result = generate_tts(
            episode_id=f"test_{voice.lower()}",
            script=TEST_SCRIPT.strip(),
            output_dir=output_dir,
            voice=voice,
            speed=0.9,
        )

        if result.get("ok"):
            print(f"✅ {voice}: {result.get('audio_path')}")
        else:
            print(f"❌ {voice}: {result.get('error')}")

    return  # 아래 코드 스킵

    result = None  # placeholder

    print()
    print("=" * 50)
    print("결과")
    print("=" * 50)

    if result.get("ok"):
        print(f"✅ 성공!")
        print(f"   오디오: {result.get('audio_path')}")
        print(f"   자막: {result.get('srt_path')}")
        print(f"   길이: {result.get('duration', 0):.1f}초")

        # 자막 파일 내용 확인
        srt_path = result.get('srt_path')
        if srt_path and os.path.exists(srt_path):
            print()
            print("자막 미리보기 (첫 5개):")
            print("-" * 30)
            with open(srt_path, 'r', encoding='utf-8') as f:
                lines = f.read().split('\n\n')[:5]
                for line in lines:
                    print(line)
                    print()
    else:
        print(f"❌ 실패: {result.get('error')}")

if __name__ == "__main__":
    main()
