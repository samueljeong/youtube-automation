"""
묵상 비디오 자동 생성 스케줄러

매일 정해진 시간에 묵상 메시지 비디오를 자동으로 생성합니다.
"""

import os
from datetime import datetime
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from openai import OpenAI
from image_fetcher import ImageFetcher
from shorts_maker import ShortsMaker
from tts_generator import TTSGenerator
from video_themes import VideoThemes
from PIL import Image, ImageDraw
import traceback
from dotenv import load_dotenv

# .env 파일 로드
load_dotenv()


class DevotionalScheduler:
    """묵상 비디오 자동 생성 스케줄러"""

    def __init__(self):
        self.scheduler = BackgroundScheduler(timezone='Asia/Seoul')
        self.openai_client = self._get_openai_client()

    def _get_openai_client(self):
        """OpenAI 클라이언트 생성"""
        key = (os.getenv("OPENAI_API_KEY") or "").strip()
        if not key:
            print("[Warning] OPENAI_API_KEY가 설정되지 않았습니다. 기본 메시지를 사용합니다.")
            return None
        return OpenAI(api_key=key)

    def create_gradient_background(self, width, height, color1, color2, output_path):
        """그라데이션 배경 이미지 생성"""
        base = Image.new('RGB', (width, height), color1)
        top = Image.new('RGB', (width, height), color2)
        mask = Image.new('L', (width, height))
        mask_data = []
        for y in range(height):
            mask_data.extend([int(255 * (y / height))] * width)
        mask.putdata(mask_data)
        base.paste(top, (0, 0), mask)

        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        base.save(output_path, quality=95)
        return output_path

    def create_gradient_background_with_theme(self, width, height, theme_name, output_path):
        """테마를 사용한 그라데이션 배경 생성"""
        theme = VideoThemes.get_theme(theme_name)
        return self.create_gradient_background(
            width, height,
            theme["color1"],
            theme["color2"],
            output_path
        )

    def generate_devotional_message(self, time_of_day="morning"):
        """GPT로 묵상 메시지 생성"""
        # OpenAI 클라이언트가 없으면 기본 메시지 반환
        if not self.openai_client:
            messages = [
                "오늘 하루도 평안하고 감사한 하루 되세요.",
                "주님의 사랑이 함께 하시기를 기도합니다.",
                "작은 일에도 감사하며 기쁨을 찾는 하루가 되길 바랍니다.",
            ]
            import random
            message = random.choice(messages)
            print(f"[Scheduler] Using default message: {message}")
            return message

        try:
            now = datetime.now()
            month = now.month
            day = now.day

            time_label = "오전" if time_of_day == "morning" else "저녁"
            system_msg = f"You help create {time_of_day} devotional messages in Korean."

            guide = f"""
간단하고 따뜻한 {time_label} 묵상 메시지를 작성해주세요.

형식:
- 2-3문장의 짧은 메시지
- 희망과 위로를 주는 내용
- 일상에서 실천 가능한 메시지

예시:
"오늘 하루도 주님의 사랑 안에서 평안하시기 바랍니다.
작은 일에도 감사하며, 서로에게 친절을 베푸는 하루가 되길 소망합니다."
"""

            completion = self.openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": system_msg},
                    {"role": "user", "content": f"[날짜]\n{month}월 {day}일\n\n{guide}"}
                ],
                temperature=0.7,
            )

            message = completion.choices[0].message.content.strip()
            print(f"[Scheduler] Generated message: {message[:50]}...")
            return message

        except Exception as e:
            print(f"[Scheduler] Error generating message: {e}")
            traceback.print_exc()
            # 기본 메시지 반환
            return "오늘도 평안하고 감사한 하루 되세요."

    def create_daily_video(self, time_of_day="morning", use_tts=True, use_theme=True):
        """일일 묵상 비디오 생성 (TTS + 테마 지원)"""
        try:
            print(f"\n{'='*60}")
            print(f"[Scheduler] Starting daily video creation - {time_of_day}")
            print(f"[Scheduler] Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"[Scheduler] TTS: {use_tts}, Theme: {use_theme}")
            print(f"{'='*60}\n")

            # 타임스탬프
            timestamp = datetime.now().strftime("%Y%m%d_%H%M")

            # 1. 묵상 메시지 생성
            print("[Step 1/6] Generating devotional message...")
            message = self.generate_devotional_message(time_of_day)

            # 2. 테마 선택
            print("[Step 2/6] Selecting theme...")
            if use_theme:
                theme_name = VideoThemes.get_random_theme(time_of_day)
                print(f"   Selected theme: {theme_name}")
            else:
                theme_name = "morning_blue" if time_of_day == "morning" else "evening_purple"

            # 3. 배경 이미지 생성
            print("[Step 3/6] Creating background image with theme...")
            bg_path = f"output/images/bg_{timestamp}.jpg"
            self.create_gradient_background_with_theme(1080, 1920, theme_name, bg_path)

            # 4. TTS 생성 (선택사항)
            audio_path = None
            if use_tts:
                print("[Step 4/6] Generating TTS audio...")
                tts_gen = TTSGenerator()
                audio_path = f"output/audio/tts_{timestamp}.mp3"
                os.makedirs(os.path.dirname(audio_path), exist_ok=True)

                audio_result = tts_gen.generate_tts(message, audio_path, use_openai=True)
                if audio_result:
                    print(f"   TTS created: {audio_path}")
                else:
                    print("   TTS failed, continuing without audio")
                    audio_path = None
            else:
                print("[Step 4/6] Skipping TTS (disabled)")

            # 5. 비디오 생성
            print("[Step 5/6] Creating devotional video...")
            maker = ShortsMaker()
            video_path_temp = f"output/videos/devotional_{timestamp}_novideo.mp4"

            bible_ref = None  # 성경 구절은 선택사항

            result = maker.create_devotional_video(
                bg_path,
                message,
                video_path_temp,
                bible_ref,
                duration=10
            )

            if not result:
                print("❌ Video creation failed")
                return None

            # 6. 오디오 추가 (TTS가 있으면)
            print("[Step 6/6] Adding audio to video...")
            if audio_path and os.path.exists(audio_path):
                final_video_path = f"output/videos/devotional_{timestamp}.mp4"
                result_with_audio = maker.add_audio_to_video(
                    video_path_temp,
                    audio_path,
                    final_video_path
                )

                if result_with_audio:
                    result = result_with_audio
                    # 임시 파일 삭제
                    if os.path.exists(video_path_temp):
                        os.remove(video_path_temp)
                else:
                    print("   Audio addition failed, using video without audio")
                    # 임시 파일을 최종 파일로 이름 변경
                    final_video_path = f"output/videos/devotional_{timestamp}.mp4"
                    os.rename(video_path_temp, final_video_path)
                    result = final_video_path
            else:
                # 임시 파일을 최종 파일로 이름 변경
                final_video_path = f"output/videos/devotional_{timestamp}.mp4"
                os.rename(video_path_temp, final_video_path)
                result = final_video_path

            # 7. 결과 로깅
            print("[Step 7/7] Logging result...")
            if result:
                file_size = os.path.getsize(result) / 1024  # KB
                log_message = f"""
{'='*60}
✅ 비디오 생성 성공!
시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
파일: {result}
크기: {file_size:.1f} KB
메시지: {message[:100]}...
{'='*60}
"""
                print(log_message)

                # 로그 파일에 기록
                log_path = "output/logs/devotional.log"
                os.makedirs(os.path.dirname(log_path), exist_ok=True)
                with open(log_path, 'a', encoding='utf-8') as f:
                    f.write(log_message + "\n")

                return result
            else:
                print("❌ 비디오 생성 실패")
                return None

        except Exception as e:
            error_msg = f"[Scheduler] Error in create_daily_video: {e}"
            print(error_msg)
            traceback.print_exc()

            # 에러 로그
            log_path = "output/logs/devotional_error.log"
            os.makedirs(os.path.dirname(log_path), exist_ok=True)
            with open(log_path, 'a', encoding='utf-8') as f:
                f.write(f"{datetime.now()}: {error_msg}\n")

            return None

    def schedule_daily_tasks(self, morning_hour=9, evening_hour=20):
        """
        일일 작업 스케줄 설정

        Args:
            morning_hour: 오전 비디오 생성 시간 (기본: 9시)
            evening_hour: 저녁 비디오 생성 시간 (기본: 20시)
        """
        # 오전 묵상 비디오 생성 (매일 오전 9시)
        self.scheduler.add_job(
            func=lambda: self.create_daily_video("morning"),
            trigger=CronTrigger(hour=morning_hour, minute=0),
            id='morning_devotional',
            name='오전 묵상 비디오 생성',
            replace_existing=True
        )

        # 저녁 묵상 비디오 생성 (매일 저녁 8시)
        self.scheduler.add_job(
            func=lambda: self.create_daily_video("evening"),
            trigger=CronTrigger(hour=evening_hour, minute=0),
            id='evening_devotional',
            name='저녁 묵상 비디오 생성',
            replace_existing=True
        )

        print(f"✅ 스케줄 설정 완료:")
        print(f"   - 오전 묵상: 매일 {morning_hour:02d}:00")
        print(f"   - 저녁 묵상: 매일 {evening_hour:02d}:00")

    def start(self):
        """스케줄러 시작"""
        if not self.scheduler.running:
            self.scheduler.start()
            print("✅ 스케줄러 시작됨")
            print("\n등록된 작업:")
            for job in self.scheduler.get_jobs():
                print(f"  - {job.name} (다음 실행: {job.next_run_time})")
        else:
            print("⚠️  스케줄러가 이미 실행 중입니다")

    def stop(self):
        """스케줄러 중지"""
        if self.scheduler.running:
            self.scheduler.shutdown()
            print("✅ 스케줄러 중지됨")

    def run_now(self, time_of_day="morning"):
        """즉시 실행 (테스트용)"""
        print("🚀 테스트 실행 중...")
        return self.create_daily_video(time_of_day)


# 메인 실행
if __name__ == "__main__":
    import sys

    scheduler = DevotionalScheduler()

    if len(sys.argv) > 1 and sys.argv[1] == "test":
        # 테스트 모드: 즉시 실행
        print("=== 테스트 모드 ===")
        scheduler.run_now("morning")
    else:
        # 스케줄 모드: 백그라운드 실행
        print("=== 스케줄 모드 ===")
        scheduler.schedule_daily_tasks(morning_hour=9, evening_hour=20)
        scheduler.start()

        # 종료하지 않고 계속 실행
        try:
            import time
            while True:
                time.sleep(60)
        except (KeyboardInterrupt, SystemExit):
            scheduler.stop()
