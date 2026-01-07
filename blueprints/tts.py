"""
TTS API Blueprint
음성 합성(Text-to-Speech) 관련 API

Routes:
- /api/drama/generate-tts: Google Cloud/네이버 TTS 생성
- /api/drama/step3/tts: TTS 파이프라인 (청킹 + SRT 자막)
- /api/drama/generate-subtitle: SRT/VTT 자막 생성
"""

import os
import re
import tempfile
import subprocess
import shutil
import gc
import base64
from flask import Blueprint, request, jsonify

# TTS 서비스 모듈
from tts import run_tts_pipeline

# Blueprint 생성
tts_bp = Blueprint('tts', __name__)

# 의존성 주입
_lang_ko = None


def set_lang_ko(lang_ko_module):
    """lang_ko 모듈 주입"""
    global _lang_ko
    _lang_ko = lang_ko_module


# ===== 한글 숫자 → 아라비아 숫자 변환 (자막용) =====
def korean_number_to_arabic(text):
    """
    한글 숫자를 아라비아 숫자로 변환 (자막 표시용)
    TTS용 대본은 한글 숫자로 작성되어 있으므로, 자막 표시 시 아라비아 숫자로 변환
    """
    result = text

    # 1. 고유어 숫자 (나이, 개수 등에 사용)
    # 일흔여섯 살 → 76살, 여든일곱 살 → 87살
    native_tens = {
        '열': 10, '스물': 20, '서른': 30, '마흔': 40, '쉰': 50,
        '예순': 60, '일흔': 70, '여든': 80, '아흔': 90
    }
    native_ones = {
        '하나': 1, '둘': 2, '셋': 3, '넷': 4, '다섯': 5,
        '여섯': 6, '일곱': 7, '여덟': 8, '아홉': 9,
        '한': 1, '두': 2, '세': 3, '네': 4
    }

    # 고유어 십단위+일단위 패턴 (예: 일흔여섯)
    for ten_kr, ten_val in native_tens.items():
        for one_kr, one_val in native_ones.items():
            pattern = ten_kr + one_kr
            if pattern in result:
                result = result.replace(pattern, str(ten_val + one_val))

    # 고유어 십단위만 (예: 스물, 서른)
    for ten_kr, ten_val in native_tens.items():
        # "스물 " 또는 "스물살" 등의 패턴
        result = re.sub(rf'{ten_kr}(?=\s|살|세|명|개|번|년|월|일|시|분|$)', str(ten_val), result)

    # 고유어 일단위만 (한, 두, 세, 네 + 단위)
    result = re.sub(r'한(?=\s*(?:명|개|번|살|분|시간|달|해))', '1', result)
    result = re.sub(r'두(?=\s*(?:명|개|번|살|분|시간|달|해))', '2', result)
    result = re.sub(r'세(?=\s*(?:명|개|번|살|분|시간|달|해))', '3', result)
    result = re.sub(r'네(?=\s*(?:명|개|번|살|분|시간|달|해))', '4', result)
    result = re.sub(r'다섯(?=\s*(?:명|개|번|살|분|시간|달|해))', '5', result)
    result = re.sub(r'여섯(?=\s*(?:명|개|번|살|분|시간|달|해))', '6', result)
    result = re.sub(r'일곱(?=\s*(?:명|개|번|살|분|시간|달|해))', '7', result)
    result = re.sub(r'여덟(?=\s*(?:명|개|번|살|분|시간|달|해))', '8', result)
    result = re.sub(r'아홉(?=\s*(?:명|개|번|살|분|시간|달|해))', '9', result)
    result = re.sub(r'열(?=\s*(?:명|개|번|살|분|시간|달|해))', '10', result)

    # 2. 한자어 숫자 (전화번호, 연도, 금액 등)
    sino_digits = {
        '영': '0', '일': '1', '이': '2', '삼': '3', '사': '4',
        '오': '5', '육': '6', '칠': '7', '팔': '8', '구': '9'
    }

    # 전화번호 패턴 (일일이, 일일구, 일이삼사 등)
    # 연속된 한자어 숫자를 아라비아 숫자로 변환
    def convert_sino_sequence(match):
        seq = match.group(0)
        result_num = ''
        for char in seq:
            if char in sino_digits:
                result_num += sino_digits[char]
        return result_num

    # 2-4자리 연속 한자어 숫자 (전화번호 등)
    sino_pattern = '[영일이삼사오육칠팔구]{2,4}'
    result = re.sub(sino_pattern, convert_sino_sequence, result)

    # 3. 한자어 복합 숫자 (이십, 삼십, 백, 천, 만 등)
    # 이십 년 → 20년, 사십칠 년 → 47년
    sino_tens = {'이십': 20, '삼십': 30, '사십': 40, '오십': 50, '육십': 60, '칠십': 70, '팔십': 80, '구십': 90}
    sino_ones_after = {'일': 1, '이': 2, '삼': 3, '사': 4, '오': 5, '육': 6, '칠': 7, '팔': 8, '구': 9}

    # 십단위+일단위 (사십칠 → 47)
    for ten_kr, ten_val in sino_tens.items():
        for one_kr, one_val in sino_ones_after.items():
            pattern = ten_kr + one_kr
            if pattern in result:
                result = result.replace(pattern, str(ten_val + one_val))

    # 십단위만 (이십 → 20)
    for ten_kr, ten_val in sino_tens.items():
        result = result.replace(ten_kr, str(ten_val))

    # 십+일단위 (십오 → 15)
    for one_kr, one_val in sino_ones_after.items():
        pattern = f'십{one_kr}'
        if pattern in result:
            result = result.replace(pattern, str(10 + one_val))

    # 십 → 10
    result = re.sub(r'(?<![이삼사오육칠팔구])십(?![일이삼사오육칠팔구])', '10', result)

    # 4. 큰 단위 (백, 천, 만)
    # 백만 원 → 100만원, 오십만 원 → 50만원
    result = re.sub(r'(\d+)백(\d+)', lambda m: str(int(m.group(1)) * 100 + int(m.group(2))), result)
    result = re.sub(r'(\d+)백(?!\d)', lambda m: str(int(m.group(1)) * 100), result)
    result = re.sub(r'(?<!\d)백(?!\d)', '100', result)

    # 5. 공백 정리 (예: "50 만 원" → "50만원")
    result = re.sub(r'(\d+)\s*(만|천|백)\s*(원|명|개)', r'\1\2\3', result)
    result = re.sub(r'(\d+)\s+(년|월|일|살|세|명|개|번|시|분|초)', r'\1\2', result)

    return result


# ===== MP3 청크 병합 (FFmpeg 기반) =====
def merge_audio_chunks_ffmpeg(audio_data_list):
    """여러 MP3 바이트 데이터를 FFmpeg로 병합"""
    if not audio_data_list:
        return b''

    if len(audio_data_list) == 1:
        return audio_data_list[0]

    ffmpeg_path = shutil.which('ffmpeg')
    if not ffmpeg_path:
        # FFmpeg 없으면 단순 결합 (폴백)
        print("[TTS-MERGE][WARN] FFmpeg 없음, 단순 바이트 결합 사용")
        return b''.join(audio_data_list)

    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            # 각 청크를 임시 파일로 저장
            chunk_files = []
            for i, chunk_data in enumerate(audio_data_list):
                chunk_path = os.path.join(tmpdir, f"chunk_{i:03d}.mp3")
                with open(chunk_path, 'wb') as f:
                    f.write(chunk_data)
                chunk_files.append(chunk_path)

            # FFmpeg concat 리스트 파일 생성
            list_path = os.path.join(tmpdir, "concat_list.txt")
            with open(list_path, 'w') as f:
                for chunk_path in chunk_files:
                    f.write(f"file '{chunk_path}'\n")

            # 출력 파일
            output_path = os.path.join(tmpdir, "merged.mp3")

            # FFmpeg concat 실행
            cmd = [
                'ffmpeg', '-y',
                '-f', 'concat',
                '-safe', '0',
                '-i', list_path,
                '-c', 'copy',  # 재인코딩 없이 병합
                output_path
            ]

            # 메모리 최적화: stdout DEVNULL, stderr만 PIPE (OOM 방지)
            result = subprocess.run(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                timeout=60
            )

            if result.returncode != 0:
                stderr_msg = result.stderr[:200].decode('utf-8', errors='ignore') if result.stderr else '(stderr 없음)'
                print(f"[TTS-MERGE][ERROR] FFmpeg 실패: {stderr_msg}")
                del result
                gc.collect()
                # 폴백: 단순 바이트 결합
                return b''.join(audio_data_list)
            del result
            gc.collect()

            # 병합된 파일 읽기
            with open(output_path, 'rb') as f:
                merged_audio = f.read()

            print(f"[TTS-MERGE] FFmpeg 병합 완료: {len(audio_data_list)}개 청크 → {len(merged_audio)} bytes")
            return merged_audio

    except Exception as e:
        print(f"[TTS-MERGE][ERROR] 병합 실패: {e}")
        # 폴백: 단순 바이트 결합
        return b''.join(audio_data_list)


# ===== TTS 음성 사전 검증 (파이프라인 시작 시 호출) =====
def validate_tts_voice(voice: str) -> dict:
    """
    TTS 음성 사전 검증 - 비싼 작업 전에 음성 설정과 필수 환경변수 확인

    Args:
        voice: 음성 이름 (chirp3:Charon, gemini:Kore, ko-KR-Neural2-C 등)

    Returns:
        dict: {"ok": True, "voice_type": "chirp3"} 또는 {"ok": False, "error": str}

    음성 유형별 필수 환경변수:
    - chirp3:*  → GOOGLE_SERVICE_ACCOUNT_JSON
    - gemini:*  → GOOGLE_API_KEY
    - ko-KR-*, ja-JP-*, en-US-* → GOOGLE_CLOUD_API_KEY
    """
    if not voice:
        return {"ok": False, "error": "음성이 지정되지 않았습니다"}

    voice_lower = voice.lower()

    # ========== Chirp3 HD TTS ==========
    if voice.startswith("chirp3:") or "chirp3" in voice_lower:
        voice_type = "chirp3"
        required_env = "GOOGLE_SERVICE_ACCOUNT_JSON"
        env_value = os.environ.get(required_env, "")

        if not env_value:
            return {
                "ok": False,
                "error": f"Chirp3 TTS 사용을 위해 {required_env} 환경변수가 필요합니다",
                "voice_type": voice_type
            }

        # Chirp3 음성 이름 검증
        valid_chirp3_voices = ["Charon", "Kore", "Fenrir", "Aoede", "Puck"]
        voice_name = voice.split(":")[-1] if ":" in voice else voice
        if voice_name not in valid_chirp3_voices:
            return {
                "ok": False,
                "error": f"지원되지 않는 Chirp3 음성: {voice_name} (지원: {', '.join(valid_chirp3_voices)})",
                "voice_type": voice_type
            }

        return {"ok": True, "voice_type": voice_type, "voice_name": voice_name}

    # ========== Gemini TTS ==========
    elif voice.startswith("gemini:"):
        voice_type = "gemini"
        required_env = "GOOGLE_API_KEY"
        env_value = os.environ.get(required_env, "")

        if not env_value:
            return {
                "ok": False,
                "error": f"Gemini TTS 사용을 위해 {required_env} 환경변수가 필요합니다",
                "voice_type": voice_type
            }

        # Gemini 음성 이름 검증
        valid_gemini_voices = ["Kore", "Charon", "Puck", "Fenrir", "Aoede"]
        parts = voice.split(":")
        voice_name = parts[-1] if len(parts) > 1 else "Kore"
        if voice_name not in valid_gemini_voices:
            return {
                "ok": False,
                "error": f"지원되지 않는 Gemini 음성: {voice_name} (지원: {', '.join(valid_gemini_voices)})",
                "voice_type": voice_type
            }

        return {"ok": True, "voice_type": voice_type, "voice_name": voice_name}

    # ========== Google Cloud TTS ==========
    elif voice.startswith("ko-KR-") or voice.startswith("ja-JP-") or voice.startswith("en-US-"):
        voice_type = "google_cloud"
        required_env = "GOOGLE_CLOUD_API_KEY"
        env_value = os.environ.get(required_env, "")

        if not env_value:
            return {
                "ok": False,
                "error": f"Google Cloud TTS 사용을 위해 {required_env} 환경변수가 필요합니다",
                "voice_type": voice_type
            }

        return {"ok": True, "voice_type": voice_type, "voice_name": voice}

    # ========== 알 수 없는 음성 ==========
    else:
        return {
            "ok": False,
            "error": f"지원되지 않는 음성 형식: {voice} (지원: chirp3:*, gemini:*, ko-KR-*, ja-JP-*, en-US-*)"
        }


# ===== Step5: TTS API (Google Cloud / 네이버 클로바 선택) =====
@tts_bp.route('/api/drama/generate-tts', methods=['POST'])
def api_generate_tts():
    """TTS 음성 생성 - Google Cloud TTS (기본) 또는 네이버 클로바"""
    import requests

    try:
        data = request.get_json()
        if not data:
            return jsonify({"ok": False, "error": "No data received"}), 400

        # 기본값 설정 (lang_ko 모듈 사용)
        default_voice = 'ko-KR-Neural2-C'
        default_lang_code = 'ko-KR'
        if _lang_ko:
            default_voice = _lang_ko.TTS.get('default_voice', default_voice)
            default_lang_code = _lang_ko.TTS.get('language_code', default_lang_code)

        text = data.get("text", "")
        speaker = data.get("speaker", default_voice)
        speed = data.get("speed", 1.0)
        pitch = data.get("pitch", 0)
        volume = data.get("volume", 0)
        tts_provider = data.get("ttsProvider", "google")  # google 또는 naver

        if not text:
            return jsonify({"ok": False, "error": "텍스트가 없습니다."}), 400

        char_count = len(text)

        # Google Cloud TTS
        if tts_provider == "google":
            google_api_key = os.getenv("GOOGLE_CLOUD_API_KEY", "")

            if not google_api_key:
                return jsonify({"ok": False, "error": "Google Cloud API 키가 설정되지 않았습니다. 환경변수 GOOGLE_CLOUD_API_KEY를 설정해주세요."}), 200

            print(f"[DRAMA-STEP5-TTS] Google TTS 생성 시작 - 음성: {speaker}, 텍스트 길이: {char_count}자")

            # 감정 표현 키워드 (이 표현이 포함된 문장은 더 천천히 읽음)
            emotional_keywords = [
                # 신체 반응
                "눈물이", "눈시울", "손이 떨", "목이 메", "가슴이 먹먹",
                "잠이 오지", "밥이 넘어가지", "숨이 막", "몸이 굳",
                # 감정 상태
                "마음이 무거", "희망이", "미안", "허무", "믿기지 않",
                "슬", "아프", "고통", "절망", "두려", "무서",
                "감사", "감격", "벅차", "뭉클", "찡",
                # 강조 표현
                "정말", "진심으로", "간절히", "애타게", "처절하게",
                # 특수 상황
                "마지막", "이별", "죽음", "떠나", "영원히"
            ]

            def apply_emotion_ssml(text_chunk, base_rate):
                """감정 표현이 있는 문장에 SSML 속도 조절 적용"""
                import html

                def escape_for_ssml(text):
                    """SSML에서 사용할 수 있도록 XML 특수 문자 이스케이프"""
                    return html.escape(text, quote=False)

                # ★ 소수점 보호: 숫자.숫자 패턴을 임시 마커로 치환 (2.6% → 2<DECIMAL>6%)
                decimal_pattern = r'(\d)\.(\d)'
                text_safe = re.sub(decimal_pattern, r'\1<DECIMAL>\2', text_chunk)

                # 문장 단위로 분할
                sentences = re.split(r'([.!?。！？])', text_safe)
                merged = []
                i = 0
                while i < len(sentences):
                    if i + 1 < len(sentences) and sentences[i+1] in '.!?。！？':
                        merged.append(sentences[i] + sentences[i+1])
                        i += 2
                    else:
                        if sentences[i].strip():
                            merged.append(sentences[i])
                        i += 1

                result_parts = []
                has_emotion = False

                # ★ 소수점 복원
                merged = [s.replace('<DECIMAL>', '.') for s in merged]

                for sentence in merged:
                    sentence = sentence.strip()
                    if not sentence:
                        continue

                    # 감정 키워드 체크
                    is_emotional = any(kw in sentence for kw in emotional_keywords)

                    if is_emotional:
                        has_emotion = True
                        # 감정 문장: 기본 속도의 90% (더 천천히)
                        emotion_rate = max(0.25, base_rate * 0.9)
                        # 감정 문장 전에 짧은 휴지, 더 느린 속도로 읽기
                        escaped_sentence = escape_for_ssml(sentence)
                        result_parts.append(f'<break time="300ms"/><prosody rate="{emotion_rate:.2f}">{escaped_sentence}</prosody><break time="200ms"/>')
                    else:
                        result_parts.append(escape_for_ssml(sentence))

                if has_emotion:
                    ssml_text = f'<speak>{" ".join(result_parts)}</speak>'
                    return ssml_text, True
                else:
                    return text_chunk, False

            # Google Cloud TTS는 최대 5000바이트 제한
            GOOGLE_TTS_MAX_BYTES = 5000
            max_bytes_for_plain_text = 2500  # SSML 오버헤드 고려하여 보수적 설정

            def get_byte_length(s):
                return len(s.encode('utf-8'))

            def split_text_by_bytes(text, max_bytes):
                """텍스트를 바이트 제한에 맞게 분할"""
                chunks = []
                # ★ 소수점 보호: 숫자.숫자 패턴을 임시 마커로 치환 (2.6% → 2<DECIMAL>6%)
                decimal_pattern = r'(\d)\.(\d)'
                text_safe = re.sub(decimal_pattern, r'\1<DECIMAL>\2', text)

                # 문장 단위로 먼저 분할 (마침표, 느낌표, 물음표 기준)
                sentences = re.split(r'([.!?。！？])', text_safe)
                # 구분자를 문장에 다시 붙이기
                merged_sentences = []
                i = 0
                while i < len(sentences):
                    if i + 1 < len(sentences) and sentences[i+1] in '.!?。！？':
                        merged_sentences.append(sentences[i] + sentences[i+1])
                        i += 2
                    else:
                        if sentences[i].strip():
                            merged_sentences.append(sentences[i])
                        i += 1

                # ★ 소수점 복원
                merged_sentences = [s.replace('<DECIMAL>', '.') for s in merged_sentences]

                current_chunk = ""
                for sentence in merged_sentences:
                    sentence = sentence.strip()
                    if not sentence:
                        continue

                    # 문장 자체가 너무 길면 더 작게 분할
                    if get_byte_length(sentence) > max_bytes:
                        # 현재 청크 저장
                        if current_chunk:
                            chunks.append(current_chunk.strip())
                            current_chunk = ""
                        # 긴 문장을 쉼표나 공백으로 분할
                        sub_parts = re.split(r'([,，、\s])', sentence)
                        sub_chunk = ""
                        for part in sub_parts:
                            if get_byte_length(sub_chunk + part) < max_bytes:
                                sub_chunk += part
                            else:
                                if sub_chunk:
                                    chunks.append(sub_chunk.strip())
                                sub_chunk = part
                        if sub_chunk:
                            current_chunk = sub_chunk
                    elif get_byte_length(current_chunk + " " + sentence) < max_bytes:
                        current_chunk = (current_chunk + " " + sentence).strip()
                    else:
                        if current_chunk:
                            chunks.append(current_chunk.strip())
                        current_chunk = sentence

                if current_chunk:
                    chunks.append(current_chunk.strip())

                return chunks if chunks else [text[:1000]]  # 최소 하나의 청크 보장

            text_chunks = split_text_by_bytes(text, max_bytes_for_plain_text)
            print(f"[DRAMA-STEP5-TTS] 텍스트를 {len(text_chunks)}개 청크로 분할 (바이트 제한: {max_bytes_for_plain_text})")

            audio_data_list = []
            url = f"https://texttospeech.googleapis.com/v1/text:synthesize?key={google_api_key}"

            # 속도 변환: 배율(0.85~1.1) 또는 네이버(-5~5) -> Google(0.25~4.0)
            if isinstance(speed, (int, float)):
                if 0.1 <= speed <= 2.0:
                    # 배율 형식 (0.85x, 0.95x, 1.0x, 1.1x 등) - 그대로 사용
                    google_speed = speed
                elif speed == 0:
                    google_speed = 1.0
                else:
                    # 네이버 형식 (-5~5)
                    google_speed = 1.0 + (speed * 0.1)  # -5->0.5, 0->1.0, 5->1.5
                google_speed = max(0.25, min(4.0, google_speed))
            else:
                google_speed = 1.0

            print(f"[DRAMA-STEP5-TTS] 속도 설정: 입력={speed}, Google TTS={google_speed}")

            # 피치 변환: 네이버(-5~5) -> Google(-20~20)
            google_pitch = pitch * 4 if isinstance(pitch, (int, float)) else 0

            emotion_chunk_count = 0
            ssml_fallback_count = 0  # SSML이 너무 커서 plain text로 폴백한 횟수

            for chunk in text_chunks:
                # 감정 표현 SSML 적용
                processed_chunk, is_ssml = apply_emotion_ssml(chunk, google_speed)

                # SSML 적용 후 바이트 체크 - 5000바이트 초과시 plain text로 폴백
                if is_ssml:
                    ssml_byte_length = get_byte_length(processed_chunk)
                    if ssml_byte_length >= GOOGLE_TTS_MAX_BYTES:
                        # SSML이 너무 큼 - plain text로 폴백
                        print(f"[DRAMA-STEP5-TTS][WARN] SSML 바이트 초과 ({ssml_byte_length}), plain text로 폴백")
                        is_ssml = False
                        ssml_fallback_count += 1
                    else:
                        emotion_chunk_count += 1

                # speaker 이름에서 언어 코드 추출 (예: ko-KR-Neural2-C → ko-KR)
                lang_code = '-'.join(speaker.split('-')[:2]) if speaker and '-' in speaker else default_lang_code

                if is_ssml:
                    payload = {
                        "input": {"ssml": processed_chunk},
                        "voice": {
                            "languageCode": lang_code,
                            "name": speaker
                        },
                        "audioConfig": {
                            "audioEncoding": "MP3",
                            "speakingRate": google_speed,
                            "pitch": google_pitch
                        }
                    }
                else:
                    # plain text도 5000바이트 제한 체크
                    chunk_byte_length = get_byte_length(chunk)
                    if chunk_byte_length >= GOOGLE_TTS_MAX_BYTES:
                        # 청크 자체가 너무 큼 - 강제 분할 (이 경우는 거의 없어야 함)
                        print(f"[DRAMA-STEP5-TTS][WARN] 청크가 너무 큼 ({chunk_byte_length}), 강제 절단")
                        chunk = chunk[:1500]  # 약 4500바이트 (한글 3바이트)

                    payload = {
                        "input": {"text": chunk},
                        "voice": {
                            "languageCode": lang_code,
                            "name": speaker
                        },
                        "audioConfig": {
                            "audioEncoding": "MP3",
                            "speakingRate": google_speed,
                            "pitch": google_pitch
                        }
                    }

                response = requests.post(url, json=payload, timeout=90)

                if response.status_code == 200:
                    result = response.json()
                    audio_content = base64.b64decode(result.get("audioContent", ""))
                    audio_data_list.append(audio_content)
                else:
                    error_text = response.text
                    print(f"[DRAMA-STEP5-TTS][ERROR] Google API 응답: {response.status_code} - {error_text}")

                    # 403 에러에 대한 특별한 안내
                    if response.status_code == 403:
                        error_msg = "Google TTS API 접근 권한이 없습니다. Google Cloud Console에서 'Cloud Text-to-Speech API'가 활성화되어 있는지 확인하고, API 키에 해당 API 접근 권한이 있는지 확인해주세요."
                        print(f"[DRAMA-STEP5-TTS][ERROR] 403 Forbidden - API 활성화 필요 또는 API 키 권한 부족")
                        return jsonify({"ok": False, "error": error_msg, "statusCode": 403}), 200

                    return jsonify({"ok": False, "error": f"Google TTS API 오류 ({response.status_code}): {error_text}"}), 200

            # FFmpeg로 MP3 청크 병합 (단순 바이트 결합 대신 - 헤더 중복 방지)
            if len(audio_data_list) == 1:
                # 청크가 하나면 그대로 사용
                combined_audio = audio_data_list[0]
            else:
                # 여러 청크면 FFmpeg로 병합
                combined_audio = merge_audio_chunks_ffmpeg(audio_data_list)

            audio_base64 = base64.b64encode(combined_audio).decode('utf-8')
            audio_url = f"data:audio/mp3;base64,{audio_base64}"

            # Google Cloud TTS 비용: $4/100만 글자 (Wavenet), $16/100만 글자 (Neural2)
            # 약 0.0054원/글자 (Wavenet 기준, 환율 1350원)
            cost_per_char = 0.0054 if "Wavenet" in speaker else 0.0216
            cost_krw = int(char_count * cost_per_char)

            print(f"[DRAMA-STEP5-TTS] Google TTS 완료 - 글자 수: {char_count}, 비용: ₩{cost_krw}, 감정 SSML 적용: {emotion_chunk_count}/{len(text_chunks)}청크, 폴백: {ssml_fallback_count}회")

            return jsonify({
                "ok": True,
                "audioUrl": audio_url,
                "charCount": char_count,
                "cost": cost_krw,
                "provider": "google",
                "emotionChunks": emotion_chunk_count,
                "totalChunks": len(text_chunks)
            })

        # 네이버 클로바 TTS (기존 코드)
        else:
            ncp_client_id = os.getenv("NCP_CLIENT_ID", "")
            ncp_client_secret = os.getenv("NCP_CLIENT_SECRET", "")

            if not ncp_client_id or not ncp_client_secret:
                return jsonify({"ok": False, "error": "네이버 클라우드 API 키가 설정되지 않았습니다. 환경변수 NCP_CLIENT_ID, NCP_CLIENT_SECRET을 설정해주세요."}), 200

            print(f"[DRAMA-STEP5-TTS] 네이버 TTS 생성 시작 - 음성: {speaker}, 텍스트 길이: {char_count}자")

            max_chars = 1000
            text_chunks = []

            if len(text) > max_chars:
                sentences = text.replace('\n', ' ').split('. ')
                current_chunk = ""
                for sentence in sentences:
                    if len(current_chunk) + len(sentence) + 2 < max_chars:
                        current_chunk += sentence + ". "
                    else:
                        if current_chunk:
                            text_chunks.append(current_chunk.strip())
                        current_chunk = sentence + ". "
                if current_chunk:
                    text_chunks.append(current_chunk.strip())
            else:
                text_chunks = [text]

            audio_data_list = []

            for chunk in text_chunks:
                url = "https://naveropenapi.apigw.ntruss.com/tts-premium/v1/tts"
                headers = {
                    "X-NCP-APIGW-API-KEY-ID": ncp_client_id,
                    "X-NCP-APIGW-API-KEY": ncp_client_secret,
                    "Content-Type": "application/x-www-form-urlencoded"
                }

                payload = {
                    "speaker": speaker,
                    "volume": str(volume),
                    "speed": str(speed),
                    "pitch": str(pitch),
                    "format": "mp3",
                    "text": chunk
                }

                response = requests.post(url, headers=headers, data=payload)

                if response.status_code == 200:
                    audio_data_list.append(response.content)
                else:
                    error_text = response.text
                    print(f"[DRAMA-STEP5-TTS][ERROR] 네이버 API 응답: {response.status_code} - {error_text}")

                    # 403 에러에 대한 특별한 안내
                    if response.status_code == 403:
                        error_msg = "네이버 TTS API 접근 권한이 없습니다. 네이버 클라우드 플랫폼에서 CLOVA Voice API가 활성화되어 있는지, API 키가 유효한지 확인해주세요."
                        print(f"[DRAMA-STEP5-TTS][ERROR] 403 Forbidden - 네이버 API 키 또는 권한 문제")
                        return jsonify({"ok": False, "error": error_msg, "statusCode": 403}), 200

                    return jsonify({"ok": False, "error": f"네이버 TTS API 오류 ({response.status_code}): {error_text}"}), 200

            # FFmpeg로 MP3 청크 병합 (네이버 TTS)
            if len(audio_data_list) == 1:
                combined_audio = audio_data_list[0]
            else:
                combined_audio = merge_audio_chunks_ffmpeg(audio_data_list)

            audio_base64 = base64.b64encode(combined_audio).decode('utf-8')
            audio_url = f"data:audio/mp3;base64,{audio_base64}"

            cost_krw = int(char_count * 4)

            print(f"[DRAMA-STEP5-TTS] 네이버 TTS 완료 - 글자 수: {char_count}, 비용: ₩{cost_krw}")

            return jsonify({
                "ok": True,
                "audioUrl": audio_url,
                "charCount": char_count,
                "cost": cost_krw,
                "provider": "naver"
            })

    except Exception as e:
        print(f"[DRAMA-STEP5-TTS][ERROR] {str(e)}")
        return jsonify({"ok": False, "error": str(e)}), 200


# ===== Step3 TTS 새 파이프라인 (5000바이트 제한 해결 + SRT 자막) =====
@tts_bp.route('/api/drama/step3/tts', methods=['POST'])
def api_step3_tts_pipeline():
    """
    새로운 Step3 TTS 파이프라인
    - 5000바이트 제한 자동 해결 (청킹)
    - FFmpeg로 오디오 병합
    - SRT 자막 자동 생성

    Input:
    {
        "episode_id": "xxx",
        "language": "ko-KR",
        "voice": { "gender": "MALE", "name": "ko-KR-Neural2-B", "speaking_rate": 0.9 },
        "scenes": [{ "id": "scene1", "narration": "..." }, ...]
    }

    Output:
    {
        "ok": true,
        "episode_id": "xxx",
        "audio_file": "outputs/audio/xxx_full.mp3",
        "audio_url": "/outputs/audio/xxx_full.mp3",
        "srt_file": "outputs/subtitles/xxx.srt",
        "timeline": [...],
        "stats": {...}
    }
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({"ok": False, "error": "No data received"}), 400

        scenes = data.get("scenes", [])
        if not scenes:
            return jsonify({"ok": False, "error": "씬 데이터가 없습니다."}), 400

        print(f"[STEP3-TTS] 새 파이프라인 시작: {len(scenes)}개 씬")

        result = run_tts_pipeline(data)

        # 파일 경로를 URL로 변환
        if result.get("ok") and result.get("audio_file"):
            audio_file = result["audio_file"]
            result["audio_url"] = "/" + audio_file

        if result.get("ok") and result.get("srt_file"):
            srt_file = result["srt_file"]
            result["srt_url"] = "/" + srt_file

        return jsonify(result)

    except Exception as e:
        print(f"[STEP3-TTS][ERROR] {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({"ok": False, "error": str(e)}), 200


# ===== Step5: 자막 생성 API =====
@tts_bp.route('/api/drama/generate-subtitle', methods=['POST'])
def api_generate_subtitle():
    """텍스트를 SRT/VTT 자막 형식으로 변환"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"ok": False, "error": "No data received"}), 400

        text = data.get("text", "")
        speed = data.get("speed", 0)  # TTS 속도 (-5 ~ 5)
        audio_duration = data.get("audioDuration", 0)  # 실제 TTS 오디오 길이 (초)

        if not text:
            return jsonify({"ok": False, "error": "텍스트가 없습니다."}), 400

        print(f"[DRAMA-STEP5-SUBTITLE] 자막 생성 시작 - 텍스트 길이: {len(text)}자, 오디오 길이: {audio_duration}초")

        # 글자당 시간 계산
        # 1. 실제 오디오 길이가 있으면 그에 맞게 계산
        # 2. 없으면 속도 기반으로 추정
        if audio_duration and audio_duration > 0:
            # 실제 오디오 길이 기반 계산 (여유 시간 고려)
            char_duration = audio_duration / max(len(text), 1)
            print(f"[DRAMA-STEP5-SUBTITLE] 오디오 기반 글자당 시간: {char_duration:.4f}초")
        else:
            # 속도에 따른 글자당 시간 계산 (기본: 글자당 약 0.15초)
            # 속도가 빠르면 시간 감소, 느리면 시간 증가
            base_char_duration = 0.15
            speed_factor = 1 - (speed * 0.1)  # speed가 5면 0.5배, -5면 1.5배
            char_duration = base_char_duration * speed_factor
            print(f"[DRAMA-STEP5-SUBTITLE] 속도 기반 글자당 시간: {char_duration:.4f}초")

        # 문장 단위로 분할 (개선된 로직)

        # 1단계: 줄바꿈으로 먼저 분할
        lines = text.split('\n')
        raw_sentences = []

        for line in lines:
            line = line.strip()
            if not line:
                continue

            # 2단계: 문장 종결 부호로 분할 (.!?。)
            # 한국어 문장 종료 어미도 고려 (~요, ~다, ~죠, ~네요 등)
            parts = re.split(r'([.!?。])', line)

            current = ""
            for i, part in enumerate(parts):
                if part in '.!?。':
                    current += part
                    if current.strip():
                        raw_sentences.append(current.strip())
                    current = ""
                else:
                    current += part

            # 마지막 남은 부분 추가
            if current.strip():
                raw_sentences.append(current.strip())

        # 3단계: 긴 문장은 쉼표나 적절한 위치에서 분할
        MAX_CHARS = 35  # 자막 한 줄 최대 글자 수
        sentences = []

        for sentence in raw_sentences:
            if len(sentence) <= MAX_CHARS:
                sentences.append(sentence)
            else:
                # 쉼표, 조사 위치에서 분할 시도
                # 한국어 분할 포인트: 쉼표, ~고, ~며, ~면, ~서, ~니, ~는데
                split_pattern = r'(,\s*|(?<=[가-힣])고\s+|(?<=[가-힣])며\s+|(?<=[가-힣])면\s+|(?<=[가-힣])서\s+|(?<=[가-힣])는데\s+)'
                sub_parts = re.split(split_pattern, sentence)

                current_part = ""
                for sub in sub_parts:
                    if not sub:
                        continue
                    # 분할 패턴인 경우 현재 부분에 붙임
                    if re.match(split_pattern, sub):
                        current_part += sub
                    elif len(current_part) + len(sub) <= MAX_CHARS:
                        current_part += sub
                    else:
                        if current_part.strip():
                            sentences.append(current_part.strip())
                        current_part = sub

                if current_part.strip():
                    sentences.append(current_part.strip())

        # 4단계: 여전히 긴 문장은 강제 분할
        final_sentences = []
        for sentence in sentences:
            if len(sentence) <= MAX_CHARS:
                final_sentences.append(sentence)
            else:
                # 공백 기준 분할
                words = sentence.split()
                current = ""
                for word in words:
                    if len(current) + len(word) + 1 <= MAX_CHARS:
                        current = current + " " + word if current else word
                    else:
                        if current:
                            final_sentences.append(current)
                        current = word
                if current:
                    final_sentences.append(current)

        sentences = [s for s in final_sentences if s.strip()]

        # ★ 짧은 자막 합치기 (10글자 미만은 인접 문장과 합침)
        MIN_SUBTITLE_LEN = 10
        if len(sentences) > 1:
            merged = []
            i = 0
            while i < len(sentences):
                current = sentences[i]
                # 충분히 길면 그냥 추가
                if len(current) >= MIN_SUBTITLE_LEN:
                    merged.append(current)
                    i += 1
                    continue
                # 짧으면 다음과 합치기
                if i + 1 < len(sentences):
                    next_sent = sentences[i + 1]
                    combined = current + " " + next_sent
                    if len(combined) <= MAX_CHARS:
                        merged.append(combined)
                    else:
                        # 두 줄로 (줄바꿈)
                        merged.append(current + "\n" + next_sent)
                    i += 2
                elif merged:
                    # 마지막 짧은 문장은 이전과 합침
                    prev = merged.pop()
                    combined = prev + " " + current
                    if len(combined) <= MAX_CHARS:
                        merged.append(combined)
                    else:
                        merged.append(prev + "\n" + current)
                    i += 1
                else:
                    merged.append(current)
                    i += 1
            sentences = merged

        # 문장이 없으면 전체 텍스트를 하나의 문장으로
        if not sentences and text.strip():
            sentences = [text.strip()[:MAX_CHARS]]

        # SRT 형식 생성
        srt_lines = []
        vtt_lines = ["WEBVTT", ""]

        current_time = 0.0

        for idx, sentence in enumerate(sentences, 1):
            # 문장 길이에 따른 표시 시간 계산
            sentence_duration = len(sentence) * char_duration
            # 최소 1초, 최대 10초
            sentence_duration = max(1.0, min(10.0, sentence_duration))

            start_time = current_time
            end_time = current_time + sentence_duration

            # 시간 포맷팅 함수
            def format_time_srt(seconds):
                hours = int(seconds // 3600)
                minutes = int((seconds % 3600) // 60)
                secs = int(seconds % 60)
                millis = int((seconds % 1) * 1000)
                return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"

            def format_time_vtt(seconds):
                hours = int(seconds // 3600)
                minutes = int((seconds % 3600) // 60)
                secs = int(seconds % 60)
                millis = int((seconds % 1) * 1000)
                return f"{hours:02d}:{minutes:02d}:{secs:02d}.{millis:03d}"

            # 자막용 텍스트: 한글 숫자 → 아라비아 숫자 변환
            subtitle_text = korean_number_to_arabic(sentence)

            # SRT 형식
            srt_lines.append(str(idx))
            srt_lines.append(f"{format_time_srt(start_time)} --> {format_time_srt(end_time)}")
            srt_lines.append(subtitle_text)
            srt_lines.append("")

            # VTT 형식
            vtt_lines.append(f"{format_time_vtt(start_time)} --> {format_time_vtt(end_time)}")
            vtt_lines.append(subtitle_text)
            vtt_lines.append("")

            current_time = end_time + 0.2  # 문장 사이 간격

        srt_content = "\n".join(srt_lines)
        vtt_content = "\n".join(vtt_lines)

        print(f"[DRAMA-STEP5-SUBTITLE] 자막 생성 완료 - {len(sentences)}개 문장")

        return jsonify({
            "ok": True,
            "srt": srt_content,
            "vtt": vtt_content,
            "sentenceCount": len(sentences),
            "totalDuration": current_time
        })

    except Exception as e:
        print(f"[DRAMA-STEP5-SUBTITLE][ERROR] {str(e)}")
        return jsonify({"ok": False, "error": str(e)}), 200
