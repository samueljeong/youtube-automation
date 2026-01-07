"""
Bible Pipeline Blueprint
성경통독 파이프라인 API

Routes:
- /api/sheets/create-bible: BIBLE 시트 생성
- /api/bible/add-test: 테스트 에피소드 추가
- /api/bible/test-background: 배경 이미지 테스트
- /api/bible/check-and-process: 대기 에피소드 처리
"""

import os
import tempfile
from flask import Blueprint, request, jsonify
from datetime import datetime as dt, timezone, timedelta

# Blueprint 생성
bible_bp = Blueprint('bible', __name__)

# 의존성 주입을 위한 전역 변수
_get_sheets_service = None
_mix_bgm_func = None
_pipeline_lock = None


def set_sheets_service_getter(func):
    """Google Sheets 서비스 getter 함수 주입"""
    global _get_sheets_service
    _get_sheets_service = func


def set_bgm_mixer(func):
    """BGM 믹싱 함수 주입"""
    global _mix_bgm_func
    _mix_bgm_func = func


def set_pipeline_lock(lock):
    """파이프라인 Lock 주입"""
    global _pipeline_lock
    _pipeline_lock = lock


# ===== Bible TTS 함수 =====

def generate_bible_tts_with_durations(verse_texts, voice_name="ko-KR-Chirp3-HD-Charon"):
    """
    BIBLE용 TTS 생성 - 절별 정확한 duration 반환 (Chirp3 HD)

    Args:
        verse_texts: 각 절의 TTS 텍스트 리스트 ["태초에...", "땅이 혼돈하고...", ...]
        voice_name: Chirp 3 HD 음성 이름

    Returns:
        {
            "ok": True,
            "audio_data": bytes,
            "total_duration": float,
            "verse_durations": [float, ...]
        }
    """
    import subprocess
    import io
    from scripts.common.tts import preprocess_tts_text

    try:
        from google.cloud import texttospeech
        from google.oauth2 import service_account
        import json

        print(f"[BIBLE-TTS] 시작 - {len(verse_texts)}개 절, 음성: {voice_name}", flush=True)

        # 서비스 계정 인증
        service_account_json = os.environ.get('GOOGLE_SERVICE_ACCOUNT_JSON')
        if not service_account_json:
            return {"ok": False, "error": "GOOGLE_SERVICE_ACCOUNT_JSON 환경변수가 없습니다"}

        service_account_info = json.loads(service_account_json)
        credentials = service_account.Credentials.from_service_account_info(
            service_account_info,
            scopes=["https://www.googleapis.com/auth/cloud-platform"]
        )

        client = texttospeech.TextToSpeechClient(credentials=credentials)
        voice = texttospeech.VoiceSelectionParams(
            language_code="ko-KR",
            name=voice_name,
        )
        audio_config = texttospeech.AudioConfig(
            audio_encoding=texttospeech.AudioEncoding.MP3
        )

        # ========== 1. 절을 청크로 그룹핑 (5000바이트 ≈ 1400자 제한) ==========
        MAX_CHARS = 1200
        chunks = []
        current_chunk_start = 0
        current_chunk_text = ""

        for i, verse_text in enumerate(verse_texts):
            clean_text = preprocess_tts_text(verse_text)

            if len(current_chunk_text) + len(clean_text) + 1 > MAX_CHARS:
                if current_chunk_text:
                    chunks.append((current_chunk_start, i - 1, current_chunk_text.strip()))
                current_chunk_start = i
                current_chunk_text = clean_text + " "
            else:
                current_chunk_text += clean_text + " "

        if current_chunk_text:
            chunks.append((current_chunk_start, len(verse_texts) - 1, current_chunk_text.strip()))

        print(f"[BIBLE-TTS] {len(chunks)}개 청크로 분할", flush=True)

        # ========== 2. 청크별 TTS + duration 측정 ==========
        chunk_audios = []

        def get_audio_duration(audio_bytes):
            """ffprobe로 오디오 duration 측정"""
            try:
                with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as tmp:
                    tmp.write(audio_bytes)
                    tmp_path = tmp.name

                cmd = [
                    "ffprobe", "-v", "error",
                    "-show_entries", "format=duration",
                    "-of", "default=noprint_wrappers=1:nokey=1",
                    tmp_path
                ]
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
                os.unlink(tmp_path)

                if result.returncode == 0 and result.stdout.strip():
                    return float(result.stdout.strip())
            except Exception as e:
                print(f"[BIBLE-TTS] ffprobe 오류: {e}")

            return len(audio_bytes) / 16000

        for idx, (start_idx, end_idx, chunk_text) in enumerate(chunks):
            print(f"[BIBLE-TTS] 청크 {idx+1}/{len(chunks)} 처리 중... ({len(chunk_text)}자)", flush=True)

            input_text = texttospeech.SynthesisInput(text=chunk_text)
            response = client.synthesize_speech(
                input=input_text,
                voice=voice,
                audio_config=audio_config,
            )

            audio_bytes = response.audio_content
            duration = get_audio_duration(audio_bytes)

            chunk_audios.append((audio_bytes, duration, start_idx, end_idx))

            print(f"[BIBLE-TTS] 청크 {idx+1}: {duration:.2f}초 (절 {start_idx+1}~{end_idx+1})", flush=True)

            if idx < len(chunks) - 1:
                import time
                time.sleep(0.2)

        # ========== 3. 절별 duration 계산 ==========
        verse_durations = [0.0] * len(verse_texts)

        for audio_bytes, chunk_duration, start_idx, end_idx in chunk_audios:
            chunk_verses = verse_texts[start_idx:end_idx + 1]
            total_chars = sum(len(v) for v in chunk_verses)

            if total_chars > 0:
                for i, verse_text in enumerate(chunk_verses):
                    verse_idx = start_idx + i
                    ratio = len(verse_text) / total_chars
                    verse_durations[verse_idx] = chunk_duration * ratio
            else:
                count = end_idx - start_idx + 1
                for i in range(count):
                    verse_durations[start_idx + i] = chunk_duration / count

        # ========== 4. 오디오 합치기 ==========
        try:
            from pydub import AudioSegment

            combined = AudioSegment.empty()
            for audio_bytes, _, _, _ in chunk_audios:
                segment = AudioSegment.from_mp3(io.BytesIO(audio_bytes))
                combined += segment

            output_buffer = io.BytesIO()
            combined.export(output_buffer, format="mp3")
            final_audio = output_buffer.getvalue()
        except ImportError:
            final_audio = b''.join(audio_bytes for audio_bytes, _, _, _ in chunk_audios)

        total_duration = sum(verse_durations)
        print(f"[BIBLE-TTS] 완료 - 총 {total_duration:.1f}초, {len(verse_durations)}개 절", flush=True)

        return {
            "ok": True,
            "audio_data": final_audio,
            "total_duration": total_duration,
            "verse_durations": verse_durations
        }

    except Exception as e:
        print(f"[BIBLE-TTS] 오류: {e}", flush=True)
        import traceback
        traceback.print_exc()
        return {"ok": False, "error": str(e)}


def generate_bible_tts_with_durations_gemini(verse_texts, voice_name="Charon", model="gemini-2.5-flash-preview-tts"):
    """
    Gemini TTS를 사용한 BIBLE TTS 생성 - 절별 정확한 duration 반환

    Args:
        verse_texts: 각 절의 TTS 텍스트 리스트
        voice_name: Gemini 음성 이름 (Charon, Fenrir, Orus, Kore 등)
        model: Gemini 모델

    Returns:
        {
            "ok": True,
            "audio_data": bytes,
            "total_duration": float,
            "verse_durations": [float, ...]
        }
    """
    import subprocess
    import time as time_module
    from scripts.common.tts import preprocess_tts_text

    try:
        api_key = os.getenv("GOOGLE_API_KEY", "")
        if not api_key:
            return {"ok": False, "error": "GOOGLE_API_KEY 환경변수가 없습니다"}

        print(f"[BIBLE-GEMINI-TTS] 시작 - {len(verse_texts)}개 절, 음성: {voice_name}, 모델: {model}", flush=True)

        # ========== 1. 절을 청크로 그룹핑 ==========
        MAX_CHARS = 2000
        chunks = []
        current_chunk_start = 0
        current_chunk_text = ""

        for i, verse_text in enumerate(verse_texts):
            clean_text = preprocess_tts_text(verse_text)

            if len(current_chunk_text) + len(clean_text) + 1 > MAX_CHARS:
                if current_chunk_text:
                    chunks.append((current_chunk_start, i - 1, current_chunk_text.strip()))
                current_chunk_start = i
                current_chunk_text = clean_text + " "
            else:
                current_chunk_text += clean_text + " "

        if current_chunk_text:
            chunks.append((current_chunk_start, len(verse_texts) - 1, current_chunk_text.strip()))

        print(f"[BIBLE-GEMINI-TTS] {len(chunks)}개 청크로 분할 (Rate Limit: 10 req/min)", flush=True)

        # ========== 2. 청크별 TTS + duration 측정 ==========
        chunk_audios = []

        def get_audio_duration_wav(audio_bytes):
            """ffprobe로 WAV 오디오 duration 측정"""
            try:
                with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp:
                    tmp.write(audio_bytes)
                    tmp_path = tmp.name

                cmd = [
                    "ffprobe", "-v", "error",
                    "-show_entries", "format=duration",
                    "-of", "default=noprint_wrappers=1:nokey=1",
                    tmp_path
                ]
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
                os.unlink(tmp_path)

                if result.returncode == 0 and result.stdout.strip():
                    return float(result.stdout.strip())
            except Exception as e:
                print(f"[BIBLE-GEMINI-TTS] ffprobe 오류: {e}", flush=True)

            return len(audio_bytes) / 48000

        for idx, (start_idx, end_idx, chunk_text) in enumerate(chunks):
            print(f"[BIBLE-GEMINI-TTS] 청크 {idx+1}/{len(chunks)} 처리 중... ({len(chunk_text)}자)", flush=True)

            import google.generativeai as genai
            genai.configure(api_key=api_key)

            try:
                response = genai.GenerativeModel(model).generate_content(
                    chunk_text,
                    generation_config=genai.GenerationConfig(
                        response_modalities=["AUDIO"],
                        speech_config=genai.SpeechConfig(
                            voice_config=genai.VoiceConfig(
                                prebuilt_voice_config=genai.PrebuiltVoiceConfig(voice_name=voice_name)
                            )
                        )
                    )
                )

                audio_data = None
                if response.candidates and response.candidates[0].content.parts:
                    for part in response.candidates[0].content.parts:
                        if hasattr(part, 'inline_data') and part.inline_data:
                            audio_data = part.inline_data.data
                            break

                if not audio_data:
                    print(f"[BIBLE-GEMINI-TTS] 청크 {idx+1} 오디오 데이터 없음", flush=True)
                    return {"ok": False, "error": f"청크 {idx+1} 오디오 생성 실패"}

                duration = get_audio_duration_wav(audio_data)
                chunk_audios.append((audio_data, duration, start_idx, end_idx))

                print(f"[BIBLE-GEMINI-TTS] 청크 {idx+1}: {duration:.2f}초 (절 {start_idx+1}~{end_idx+1})", flush=True)

            except Exception as e:
                print(f"[BIBLE-GEMINI-TTS] 청크 {idx+1} API 오류: {e}", flush=True)
                return {"ok": False, "error": f"Gemini TTS API 오류: {e}"}

            if idx < len(chunks) - 1:
                print(f"[BIBLE-GEMINI-TTS] Rate Limit 대기 (6초)...", flush=True)
                time_module.sleep(6)

        # ========== 3. 절별 duration 계산 ==========
        verse_durations = [0.0] * len(verse_texts)

        for audio_bytes, chunk_duration, start_idx, end_idx in chunk_audios:
            chunk_verses = verse_texts[start_idx:end_idx + 1]
            total_chars = sum(len(v) for v in chunk_verses)

            if total_chars > 0:
                for i, verse_text in enumerate(chunk_verses):
                    verse_idx = start_idx + i
                    ratio = len(verse_text) / total_chars
                    verse_durations[verse_idx] = chunk_duration * ratio
            else:
                count = end_idx - start_idx + 1
                for i in range(count):
                    verse_durations[start_idx + i] = chunk_duration / count

        # ========== 4. WAV 오디오 합치기 → MP3 변환 ==========
        print(f"[BIBLE-GEMINI-TTS] 오디오 합치기 및 MP3 변환...", flush=True)

        try:
            wav_files = []
            for i, (audio_bytes, _, _, _) in enumerate(chunk_audios):
                wav_path = tempfile.mktemp(suffix=f'_chunk{i}.wav')
                with open(wav_path, 'wb') as f:
                    f.write(audio_bytes)
                wav_files.append(wav_path)

            concat_list_path = tempfile.mktemp(suffix='.txt')
            with open(concat_list_path, 'w') as f:
                for wav_path in wav_files:
                    f.write(f"file '{wav_path}'\n")

            output_mp3_path = tempfile.mktemp(suffix='.mp3')
            concat_cmd = [
                'ffmpeg', '-y', '-f', 'concat', '-safe', '0',
                '-i', concat_list_path,
                '-c:a', 'libmp3lame', '-b:a', '128k',
                output_mp3_path
            ]

            result = subprocess.run(
                concat_cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                timeout=120
            )

            if result.returncode != 0:
                stderr = result.stderr.decode('utf-8', errors='ignore')[:200] if result.stderr else ""
                print(f"[BIBLE-GEMINI-TTS] FFmpeg 오류: {stderr}", flush=True)
                return {"ok": False, "error": "오디오 합치기 실패"}

            with open(output_mp3_path, 'rb') as f:
                final_audio = f.read()

            for wav_path in wav_files:
                try:
                    os.unlink(wav_path)
                except:
                    pass
            try:
                os.unlink(concat_list_path)
                os.unlink(output_mp3_path)
            except:
                pass

        except Exception as e:
            print(f"[BIBLE-GEMINI-TTS] 오디오 합치기 오류: {e}", flush=True)
            return {"ok": False, "error": f"오디오 합치기 오류: {e}"}

        total_duration = sum(verse_durations)
        print(f"[BIBLE-GEMINI-TTS] 완료 - 총 {total_duration:.1f}초, {len(verse_durations)}개 절", flush=True)

        return {
            "ok": True,
            "audio_data": final_audio,
            "total_duration": total_duration,
            "verse_durations": verse_durations
        }

    except Exception as e:
        print(f"[BIBLE-GEMINI-TTS] 오류: {e}", flush=True)
        import traceback
        traceback.print_exc()
        return {"ok": False, "error": str(e)}


# ===== Bible Pipeline 메인 함수 =====

def run_bible_episode_pipeline(
    service,
    sheet_id: str,
    row_idx: int,
    episode_data: dict,
    channel_id: str = ""
) -> dict:
    """
    성경통독 에피소드 파이프라인 실행

    Args:
        service: Google Sheets API 서비스 객체
        sheet_id: 스프레드시트 ID
        row_idx: 행 번호
        episode_data: 시트에서 읽은 에피소드 데이터
        channel_id: YouTube 채널 ID

    Returns:
        {"ok": True, "video_url": str} 또는 {"ok": False, "error": str}
    """
    import time as time_module
    import glob
    import random
    from scripts.common.tts import parse_chirp3_voice, parse_gemini_voice

    start_time = time_module.time()

    try:
        # 에피소드 정보 파싱
        episode_id = episode_data.get("에피소드", "")
        day_number = int(episode_id.replace("EP", "")) if episode_id.startswith("EP") else 1
        book = episode_data.get("책", "")
        title = episode_data.get("제목", f"[100일 성경통독] Day {day_number}")
        voice = episode_data.get("음성", "").strip() or "chirp3:Charon"
        visibility = episode_data.get("공개설정", "").strip() or "unlisted"
        playlist_id = episode_data.get("플레이리스트ID", "").strip()
        publish_time = episode_data.get("예약시간", "").strip()

        print(f"[BIBLE] ========== 파이프라인 시작: Day {day_number} ==========")
        print(f"[BIBLE] 책: {book}")
        print(f"[BIBLE] 제목: {title}")
        print(f"[BIBLE] 음성: {voice}")
        print(f"[BIBLE] 공개설정: {visibility}")

        # 테스트 에피소드 처리
        is_test_episode = episode_id.startswith("TEST")
        test_verse_range = None
        if is_test_episode:
            import re
            verse_match = re.search(r'\(verses:(\d+)-(\d+)\)', title)
            if verse_match:
                test_verse_range = (int(verse_match.group(1)), int(verse_match.group(2)))
                print(f"[BIBLE] ★ 테스트 모드: {book} {episode_data.get('시작장', 1)}장 {test_verse_range[0]}-{test_verse_range[1]}절", flush=True)

        # 상태를 '처리중'으로 변경
        from scripts.bible_pipeline.sheets import update_episode_status
        kst = timezone(timedelta(hours=9))
        start_time_str = dt.now(kst).strftime('%Y-%m-%d %H:%M:%S')
        update_episode_status(service, sheet_id, row_idx, "처리중", work_time=start_time_str)

        # BiblePipeline에서 에피소드 데이터 가져오기
        from scripts.bible_pipeline.run import BiblePipeline, Episode, Chapter, Verse
        from scripts.bible_pipeline.config import BIBLE_TTS_VOICE

        pipeline = BiblePipeline()

        # 테스트 에피소드 또는 일반 에피소드 처리
        if is_test_episode and test_verse_range:
            start_chapter = int(episode_data.get("시작장", 1))
            chapter = pipeline.get_chapter(book, start_chapter)
            if not chapter:
                return {"ok": False, "error": f"장을 찾을 수 없습니다: {book} {start_chapter}장"}

            start_v, end_v = test_verse_range
            filtered_verses = [v for v in chapter.verses if start_v <= v.verse <= end_v]

            if not filtered_verses:
                return {"ok": False, "error": f"절을 찾을 수 없습니다: {book} {start_chapter}장 {start_v}-{end_v}절"}

            test_chapter = Chapter(book=book, chapter=start_chapter, verses=filtered_verses)
            episode = Episode(
                episode_id=episode_id,
                book=book,
                start_chapter=start_chapter,
                end_chapter=start_chapter,
                chapters=[test_chapter],
                day_number=0
            )
            print(f"[BIBLE] 테스트 에피소드 생성: {len(filtered_verses)}개 절", flush=True)
        else:
            episodes = pipeline.generate_all_bible_episodes()
            episode = next((ep for ep in episodes if ep.day_number == day_number), None)

            if not episode:
                return {"ok": False, "error": f"Day {day_number} 에피소드를 찾을 수 없습니다"}

        # 임시 디렉토리 생성
        temp_dir = os.path.join(tempfile.gettempdir(), f"bible_day_{day_number}")
        os.makedirs(temp_dir, exist_ok=True)

        # ========== 1. TTS 생성 ==========
        print(f"[BIBLE] 1. TTS 생성 시작...", flush=True)

        tts_texts = []
        for chapter in episode.chapters:
            for i, verse in enumerate(chapter.verses):
                if i == 0:
                    chapter_intro = f"{chapter.book} {chapter.chapter}장."
                    tts_texts.append(f"{chapter_intro} {verse.tts_text}")
                else:
                    tts_texts.append(verse.tts_text)

        print(f"[BIBLE] TTS 텍스트: {len(tts_texts)}개 절 (장 제목 포함)", flush=True)

        audio_path = os.path.join(temp_dir, f"day_{day_number:03d}.mp3")

        if voice.startswith("chirp3:"):
            chirp3_config = parse_chirp3_voice(voice)
            tts_result = generate_bible_tts_with_durations(
                verse_texts=tts_texts,
                voice_name=chirp3_config["voice"]
            )
            if tts_result.get("ok"):
                verse_durations = tts_result.get("verse_durations", [])
                audio_duration = tts_result.get("total_duration", 0)
            else:
                error_msg = f"TTS 생성 실패: {tts_result.get('error')}"
                update_episode_status(service, sheet_id, row_idx, "실패", error_message=error_msg)
                return {"ok": False, "error": error_msg}

        elif voice.startswith("gemini:"):
            gemini_config = parse_gemini_voice(voice)
            print(f"[BIBLE] Gemini TTS 사용: {gemini_config['voice']} ({gemini_config['model']})", flush=True)

            tts_result = generate_bible_tts_with_durations_gemini(
                verse_texts=tts_texts,
                voice_name=gemini_config["voice"],
                model=gemini_config["model"]
            )
            if tts_result.get("ok"):
                verse_durations = tts_result.get("verse_durations", [])
                audio_duration = tts_result.get("total_duration", 0)
            else:
                error_msg = f"TTS 생성 실패: {tts_result.get('error')}"
                update_episode_status(service, sheet_id, row_idx, "실패", error_message=error_msg)
                return {"ok": False, "error": error_msg}

        else:
            full_text = " ".join(tts_texts)
            from scripts.tts.google_tts import generate_google_tts
            tts_result = generate_google_tts(full_text, voice)

            if not tts_result.get("ok"):
                error_msg = f"TTS 생성 실패: {tts_result.get('error')}"
                update_episode_status(service, sheet_id, row_idx, "실패", error_message=error_msg)
                return {"ok": False, "error": error_msg}

            audio_duration = tts_result.get("duration", len(full_text) / 15.0)
            total_chars = sum(len(t) for t in tts_texts)
            verse_durations = []
            for text in tts_texts:
                ratio = len(text) / total_chars if total_chars > 0 else 1.0 / len(tts_texts)
                verse_durations.append(audio_duration * ratio)

        audio_data = tts_result.get("audio_data")
        with open(audio_path, "wb") as f:
            f.write(audio_data)

        print(f"[BIBLE] TTS 완료: {audio_duration:.1f}초, {len(verse_durations)}개 절 duration 계산됨", flush=True)

        # ========== 2. 배경 이미지 ==========
        print(f"[BIBLE] 2. 배경 이미지 확인...", flush=True)
        from scripts.bible_pipeline.background import get_background_path, generate_book_background

        background_path = get_background_path(episode.book)
        if not background_path:
            print(f"[BIBLE] 배경 이미지 생성: {episode.book}", flush=True)
            bg_result = generate_book_background(episode.book)
            if bg_result.get("ok"):
                background_path = bg_result.get("image_path")
                print(f"[BIBLE] 배경 이미지 생성 완료: {background_path}", flush=True)
            else:
                print(f"[BIBLE] 배경 생성 실패, 기본 배경 사용", flush=True)
                background_path = None
        else:
            print(f"[BIBLE] 기존 배경 이미지 사용: {background_path}", flush=True)

        # ========== 3. 썸네일 생성 ==========
        print(f"[BIBLE] 3. 썸네일 생성...", flush=True)
        from scripts.bible_pipeline.thumbnail import generate_episode_thumbnail

        thumb_result = generate_episode_thumbnail(episode)
        thumbnail_path = thumb_result.get("image_path") if thumb_result.get("ok") else None
        if thumbnail_path:
            print(f"[BIBLE] 썸네일 생성 완료: {thumbnail_path}", flush=True)
        else:
            print(f"[BIBLE] 썸네일 생성 실패: {thumb_result.get('error', 'Unknown')}", flush=True)

        # ========== 4. 영상 렌더링 ==========
        print(f"[BIBLE] 4. 영상 렌더링...", flush=True)
        from scripts.bible_pipeline.renderer import render_episode_video

        video_result = render_episode_video(
            episode=episode,
            audio_path=audio_path,
            verse_durations=verse_durations,
            output_dir=temp_dir,
            background_path=background_path,
            use_ass=True
        )

        if not video_result.get("ok"):
            error_msg = f"영상 렌더링 실패: {video_result.get('error')}"
            update_episode_status(service, sheet_id, row_idx, "실패", error_message=error_msg)
            return {"ok": False, "error": error_msg}

        video_path = video_result.get("video_path")
        print(f"[BIBLE] 영상 생성 완료: {video_path}", flush=True)

        # ========== 4.5. BGM 믹싱 ==========
        print(f"[BIBLE] 4.5. BGM 믹싱...", flush=True)

        script_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        bgm_dir = os.path.join(script_dir, "static", "audio", "bgm")
        calm_bgms = glob.glob(os.path.join(bgm_dir, "calm_*.mp3"))

        if calm_bgms and _mix_bgm_func:
            bgm_path = random.choice(calm_bgms)
            bgm_output_path = video_path.replace(".mp4", "_bgm.mp4")

            print(f"[BIBLE] BGM 파일: {os.path.basename(bgm_path)}", flush=True)

            if _mix_bgm_func(video_path, bgm_path, bgm_output_path, bgm_volume=0.10):
                os.replace(bgm_output_path, video_path)
                print(f"[BIBLE] BGM 믹싱 완료 (볼륨 10%)", flush=True)
            else:
                print(f"[BIBLE] BGM 믹싱 실패 - 원본 영상 사용", flush=True)
        else:
            print(f"[BIBLE] calm BGM 파일 없음 - BGM 없이 진행", flush=True)

        # ========== 5. YouTube 업로드 ==========
        print(f"[BIBLE] 5. YouTube 업로드...", flush=True)

        from scripts.bible_pipeline.seo import generate_seo_title, generate_seo_description, validate_seo_title

        total_verses = sum(len(ch.verses) for ch in episode.chapters)
        estimated_minutes = int(audio_duration / 60) + 1

        default_title_pattern = f"[100일 성경통독] Day {day_number}"
        if title.startswith(default_title_pattern) or title == default_title_pattern:
            seo_title = generate_seo_title(
                day_number=day_number,
                book=episode.book,
                start_chapter=episode.start_chapter,
                end_chapter=episode.end_chapter
            )
            print(f"[BIBLE] SEO 제목 생성: {seo_title}", flush=True)
        else:
            seo_title = title
            print(f"[BIBLE] 사용자 제목 유지: {seo_title}", flush=True)

        title_validation = validate_seo_title(seo_title)
        if title_validation.get("warnings"):
            for warning in title_validation["warnings"]:
                print(f"[BIBLE] SEO 경고: {warning}", flush=True)

        description = generate_seo_description(
            day_number=day_number,
            book=episode.book,
            start_chapter=episode.start_chapter,
            end_chapter=episode.end_chapter,
            total_verses=total_verses,
            estimated_minutes=estimated_minutes,
            playlist_url=None
        )

        title = seo_title

        import requests as req
        base_url = os.environ.get('RENDER_EXTERNAL_URL', 'http://127.0.0.1:10000')

        upload_payload = {
            "videoPath": video_path,
            "title": title,
            "description": description,
            "privacyStatus": visibility,
            "thumbnailPath": thumbnail_path,
        }

        if playlist_id:
            upload_payload["playlistId"] = playlist_id
        if publish_time:
            upload_payload["publish_at"] = publish_time
        if channel_id:
            upload_payload["channelId"] = channel_id

        upload_resp = req.post(f"{base_url}/api/youtube/upload", json=upload_payload, timeout=1800)
        upload_result = upload_resp.json()

        if not upload_result.get("ok"):
            error_msg = f"YouTube 업로드 실패: {upload_result.get('error')}"
            update_episode_status(service, sheet_id, row_idx, "실패", error_message=error_msg)
            return {"ok": False, "error": error_msg}

        video_url = upload_result.get("videoUrl", "")
        print(f"[BIBLE] YouTube 업로드 완료: {video_url}", flush=True)

        # ========== 6. 시트 업데이트 ==========
        print(f"[BIBLE] 6. 시트 업데이트...", flush=True)
        elapsed_time = time_module.time() - start_time
        work_time_str = f"{elapsed_time / 60:.1f}분"

        update_episode_status(
            service, sheet_id, row_idx, "완료",
            video_url=video_url,
            work_time=work_time_str
        )

        # 임시 파일 정리
        print(f"[BIBLE] 7. 임시 파일 정리...", flush=True)
        try:
            import shutil
            shutil.rmtree(temp_dir, ignore_errors=True)
        except:
            pass

        print(f"[BIBLE] ========== 파이프라인 완료: Day {day_number} ({work_time_str}) ==========", flush=True)

        return {"ok": True, "video_url": video_url}

    except Exception as e:
        import traceback
        traceback.print_exc()
        error_msg = str(e)

        try:
            from scripts.bible_pipeline.sheets import update_episode_status
            update_episode_status(service, sheet_id, row_idx, "실패", error_message=error_msg)
        except:
            pass

        return {"ok": False, "error": error_msg}


# ===== API Routes =====

@bible_bp.route('/api/sheets/create-bible', methods=['GET', 'POST'])
def api_create_bible_sheet():
    """성경통독 BIBLE 시트 생성 API"""
    print("[BIBLE-SHEETS] ===== create-bible 호출됨 =====")

    try:
        if not _get_sheets_service:
            return jsonify({"ok": False, "error": "Sheets 서비스가 설정되지 않았습니다"}), 500

        service = _get_sheets_service()
        if not service:
            return jsonify({
                "ok": False,
                "error": "Google Sheets 서비스 계정이 설정되지 않았습니다"
            }), 400

        sheet_id = os.environ.get('AUTOMATION_SHEET_ID')
        if not sheet_id:
            return jsonify({
                "ok": False,
                "error": "AUTOMATION_SHEET_ID 환경변수가 필요합니다"
            }), 400

        channel_id = request.args.get('channel_id', '')
        force_recreate = request.args.get('force', '0') == '1'

        from scripts.bible_pipeline.sheets import create_bible_sheet

        result = create_bible_sheet(
            service=service,
            sheet_id=sheet_id,
            channel_id=channel_id,
            force_recreate=force_recreate
        )

        if result.get("ok"):
            return jsonify(result)
        else:
            return jsonify(result), 500

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"ok": False, "error": str(e)}), 500


@bible_bp.route('/api/bible/add-test', methods=['GET', 'POST'])
def api_add_bible_test():
    """성경통독 BIBLE 시트에 테스트용 행 추가"""
    print("[BIBLE-TEST] ===== add-test 호출됨 =====")

    try:
        if not _get_sheets_service:
            return jsonify({"ok": False, "error": "Sheets 서비스가 설정되지 않았습니다"}), 500

        service = _get_sheets_service()
        if not service:
            return jsonify({
                "ok": False,
                "error": "Google Sheets 서비스 계정이 설정되지 않았습니다"
            }), 400

        sheet_id = os.environ.get('AUTOMATION_SHEET_ID')
        if not sheet_id:
            return jsonify({
                "ok": False,
                "error": "AUTOMATION_SHEET_ID 환경변수가 필요합니다"
            }), 400

        book = request.args.get('book', '창세기')
        chapter = int(request.args.get('chapter', 1))
        start_verse = int(request.args.get('start_verse', 1))
        end_verse = int(request.args.get('end_verse', 10))
        status = request.args.get('status', '대기')

        from scripts.bible_pipeline.sheets import add_test_episode

        result = add_test_episode(
            service=service,
            sheet_id=sheet_id,
            book=book,
            start_chapter=chapter,
            end_chapter=chapter,
            start_verse=start_verse,
            end_verse=end_verse,
            status=status
        )

        if result.get("ok"):
            return jsonify(result)
        else:
            return jsonify(result), 500

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"ok": False, "error": str(e)}), 500


@bible_bp.route('/api/bible/test-background', methods=['GET', 'POST'])
def api_bible_test_background():
    """배경 이미지 테스트 API"""
    try:
        book = request.args.get('book', '창세기')
        force = request.args.get('force', '0') == '1'

        from scripts.bible_pipeline.background import generate_book_background, get_background_prompt

        prompt = get_background_prompt(book)
        print(f"[BIBLE-BG-TEST] 프롬프트:\n{prompt[:500]}...")

        result = generate_book_background(book, force_regenerate=force)

        if result.get("ok"):
            return jsonify({
                "ok": True,
                "book": book,
                "image_url": result.get("image_url"),
                "image_path": result.get("image_path"),
                "cached": result.get("cached", False),
                "prompt_preview": prompt[:300] + "..."
            })
        else:
            return jsonify({
                "ok": False,
                "book": book,
                "error": result.get("error")
            })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"ok": False, "error": str(e)})


@bible_bp.route('/api/bible/check-and-process', methods=['GET', 'POST'])
def api_bible_check_and_process():
    """성경통독 파이프라인 - BIBLE 시트에서 대기 상태인 에피소드 처리"""
    print(f"[BIBLE] ===== check-and-process 호출됨 =====")

    # 동시 실행 방지
    if _pipeline_lock and not _pipeline_lock.acquire(blocking=False):
        print("[BIBLE] 다른 파이프라인이 이미 실행 중 - 스킵")
        return jsonify({
            "ok": True,
            "message": "다른 파이프라인이 이미 실행 중입니다",
            "skipped": True
        })

    try:
        if not _get_sheets_service:
            return jsonify({"ok": False, "error": "Sheets 서비스가 설정되지 않았습니다"}), 500

        service = _get_sheets_service()
        if not service:
            return jsonify({
                "ok": False,
                "error": "Google Sheets 서비스 계정이 설정되지 않았습니다"
            }), 400

        sheet_id = os.environ.get('AUTOMATION_SHEET_ID')
        if not sheet_id:
            return jsonify({
                "ok": False,
                "error": "AUTOMATION_SHEET_ID 환경변수가 필요합니다"
            }), 400

        from scripts.bible_pipeline.sheets import get_pending_episodes

        pending = get_pending_episodes(service, sheet_id, limit=1)

        if not pending:
            print("[BIBLE] 대기 중인 에피소드 없음")
            return jsonify({
                "ok": True,
                "message": "처리할 에피소드가 없습니다",
                "processed": 0
            })

        episode_data = pending[0]
        row_idx = episode_data.get("row_idx")

        print(f"[BIBLE] 대기 에피소드 발견: {episode_data.get('에피소드')} (행 {row_idx})")

        # 채널 ID 가져오기
        channel_id = ""
        try:
            result = service.spreadsheets().values().get(
                spreadsheetId=sheet_id,
                range="BIBLE!B1"
            ).execute()
            channel_id = result.get('values', [[]])[0][0] if result.get('values') else ""
        except:
            pass

        # 파이프라인 실행
        result = run_bible_episode_pipeline(
            service=service,
            sheet_id=sheet_id,
            row_idx=row_idx,
            episode_data=episode_data,
            channel_id=channel_id
        )

        if result.get("ok"):
            return jsonify({
                "ok": True,
                "message": f"Day {episode_data.get('에피소드')} 처리 완료",
                "video_url": result.get("video_url"),
                "processed": 1
            })
        else:
            return jsonify({
                "ok": False,
                "error": result.get("error"),
                "processed": 0
            }), 500

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"ok": False, "error": str(e)}), 500

    finally:
        if _pipeline_lock:
            try:
                _pipeline_lock.release()
            except:
                pass
