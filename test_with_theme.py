"""
테마 시스템 테스트
"""

from devotional_scheduler import DevotionalScheduler

# 스케줄러 생성
scheduler = DevotionalScheduler()

# 테마 사용, TTS 사용 안 함 (gTTS가 작동하지 않음)
print("=== 테마 시스템 테스트 ===")
print("TTS는 비활성화 (gTTS API 이슈)")
print("테마는 활성화 (랜덤 선택)")
print()

result = scheduler.create_daily_video(
    time_of_day="morning",
    use_tts=False,  # TTS 비활성화
    use_theme=True  # 테마 활성화
)

if result:
    print(f"\n✅ 테스트 성공!")
    print(f"   생성된 비디오: {result}")
else:
    print("\n❌ 테스트 실패")
