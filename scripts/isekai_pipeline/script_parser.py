"""
이세계 파이프라인 - AI 스크립트 파서

대본에서 나레이션/대사를 자동으로 파싱하여 하이브리드 TTS 생성 지원
- 따옴표 안 텍스트 → 대사로 인식
- 문맥에서 화자 추출
- 문맥에서 감정 추론
"""

import os
import re
import json
import requests
from typing import Dict, Any, List, Optional


# Gemini API 설정
GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models"
GEMINI_MODEL = "gemini-2.0-flash"

# 캐릭터별 기본 보이스 설정 (Gemini TTS)
CHARACTER_VOICES = {
    "무영": "Orus",      # 남성, 주인공
    "혈영": "Orus",      # 무영의 별칭
    "노인": "Charon",    # 노인, 스승
    "스승": "Charon",
    "설하": "Aoede",     # 여성
    "혈마": "Fenrir",    # 악역, 광기
    "default": "Kore",
}

# 감정별 스타일 프롬프트
EMOTION_STYLES = {
    "calm": "차분하고 안정적인 목소리로, 편안하게",
    "wise": "지혜롭고 깊은 목소리로, 천천히 의미를 담아서",
    "romantic": "부드럽고 따뜻한 목소리로, 사랑이 담긴 톤으로",
    "worried": "걱정스럽고 불안한 목소리로, 떨리는 듯이",
    "tense": "긴장감 있고 급박한 목소리로, 숨이 가쁜 듯이",
    "desperate": "절박하고 간절한 목소리로, 필사적으로",
    "cold": "차갑고 감정 없는 목소리로, 무심하게",
    "dramatic": "극적이고 감정이 고조된 목소리로",
    "mad": "광기 어린 목소리로, 미친 듯이 웃으며",
    "shocked": "놀라고 당황한 목소리로, 급하게",
    "sad": "슬프고 침울한 목소리로, 천천히",
    "default": "자연스럽고 명확한 목소리로",
}


def parse_script_with_ai(script: str, api_key: str = None) -> Dict[str, Any]:
    """
    AI를 사용해 대본에서 대사를 자동 파싱

    Args:
        script: 원본 대본 텍스트
        api_key: Google API 키 (없으면 환경변수에서 가져옴)

    Returns:
        {
            "ok": True,
            "dialogues": [
                {"text": "대사", "speaker": "화자", "emotion": "감정"},
                ...
            ],
            "stats": {"dialogue": N}
        }
    """
    api_key = api_key or os.environ.get('GOOGLE_API_KEY')
    if not api_key:
        return {"ok": False, "error": "GOOGLE_API_KEY 환경변수가 필요합니다"}

    # 긴 대본은 청크로 분할
    MAX_CHUNK_SIZE = 6000
    chunks = []

    if len(script) > MAX_CHUNK_SIZE:
        # 문단 단위로 분할
        paragraphs = script.split('\n\n')
        current_chunk = ""
        for para in paragraphs:
            if len(current_chunk) + len(para) < MAX_CHUNK_SIZE:
                current_chunk += para + "\n\n"
            else:
                if current_chunk:
                    chunks.append(current_chunk.strip())
                current_chunk = para + "\n\n"
        if current_chunk:
            chunks.append(current_chunk.strip())
    else:
        chunks = [script]

    all_dialogues = []

    for i, chunk in enumerate(chunks):
        print(f"[파서] 청크 {i+1}/{len(chunks)} 파싱 중...")

        prompt = f'''다음 소설에서 대사만 추출해서 JSON으로 반환해주세요.

규칙:
1. 따옴표("") 안의 텍스트가 대사입니다
2. 대사의 화자는 문맥에서 추론 (예: "~라고 노인이 말했다" → 화자: 노인)
3. 감정: calm, wise, romantic, worried, tense, desperate, cold, dramatic, mad, shocked, sad 중 선택

JSON만 출력 (다른 텍스트 없이):
{{"dialogues": [{{"text": "대사", "speaker": "화자", "emotion": "감정"}}]}}

대본:
{chunk}
'''

        url = f"{GEMINI_API_URL}/{GEMINI_MODEL}:generateContent?key={api_key}"

        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": 0.1,
                "maxOutputTokens": 8000,
            }
        }

        try:
            response = requests.post(url, json=payload, timeout=120)

            if response.status_code != 200:
                print(f"[파서] 청크 {i+1} API 오류: {response.status_code}")
                continue

            result = response.json()
            candidates = result.get("candidates", [])

            if not candidates:
                continue

            text = candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "")

            # JSON 추출 (마크다운 코드블록 제거)
            json_match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', text)
            if json_match:
                json_str = json_match.group(1)
            else:
                json_str = text.strip()

            # JSON 파싱
            parsed = json.loads(json_str)
            dialogues = parsed.get("dialogues", [])
            all_dialogues.extend(dialogues)

        except json.JSONDecodeError as e:
            print(f"[파서] 청크 {i+1} JSON 파싱 실패: {e}")
            continue
        except Exception as e:
            print(f"[파서] 청크 {i+1} 오류: {e}")
            continue

    if not all_dialogues:
        return {"ok": False, "error": "대사를 추출하지 못했습니다"}

    return {
        "ok": True,
        "dialogues": all_dialogues,
        "stats": {
            "dialogue": len(all_dialogues),
        }
    }


def parse_script_simple(script: str) -> Dict[str, Any]:
    """
    AI 없이 간단한 규칙 기반 파싱 (폴백용)
    따옴표 안의 텍스트를 대사로 추출
    """
    segments = []

    # 따옴표로 대사 분리
    pattern = r'"([^"]+)"'
    last_end = 0

    for match in re.finditer(pattern, script):
        # 대사 앞의 나레이션
        if match.start() > last_end:
            narration = script[last_end:match.start()].strip()
            if narration:
                segments.append({"type": "narration", "text": narration})

        # 대사
        dialogue_text = match.group(1)

        # 대사 뒤에서 화자 추출 시도
        after_text = script[match.end():match.end()+50]
        speaker = "unknown"

        # "~라고 X가 말했다" 패턴
        speaker_match = re.search(r'(\w+)[이가]?\s*(말했다|물었다|외쳤다|중얼거렸다|속삭였다|소리쳤다)', after_text)
        if speaker_match:
            speaker = speaker_match.group(1)

        segments.append({
            "type": "dialogue",
            "text": dialogue_text,
            "speaker": speaker,
            "emotion": "default"
        })

        last_end = match.end()

    # 마지막 나레이션
    if last_end < len(script):
        narration = script[last_end:].strip()
        if narration:
            segments.append({"type": "narration", "text": narration})

    dialogues = [s for s in segments if s.get("type") == "dialogue"]

    return {
        "ok": True,
        "segments": segments,
        "dialogues": dialogues,
        "stats": {
            "total": len(segments),
            "narration": len(segments) - len(dialogues),
            "dialogue": len(dialogues),
        }
    }


def get_voice_for_character(speaker: str) -> str:
    """캐릭터에 맞는 Gemini TTS 보이스 반환"""
    return CHARACTER_VOICES.get(speaker, CHARACTER_VOICES["default"])


def get_style_for_emotion(emotion: str) -> str:
    """감정에 맞는 스타일 프롬프트 반환"""
    return EMOTION_STYLES.get(emotion, EMOTION_STYLES["default"])


def prepare_hybrid_tts_data(parsed_result: Dict[str, Any]) -> Dict[str, Any]:
    """
    파싱 결과를 하이브리드 TTS 생성에 맞게 변환

    Returns:
        {
            "narration_text": "전체 나레이션 텍스트 (ElevenLabs용)",
            "dialogues": [
                {
                    "text": "대사",
                    "speaker": "화자",
                    "emotion": "감정",
                    "voice": "Gemini 보이스",
                    "style_prompt": "스타일 지침",
                    "position": 문자위치  # 나레이션 내 삽입 위치
                }
            ]
        }
    """
    if not parsed_result.get("ok"):
        return parsed_result

    segments = parsed_result.get("segments", [])

    narration_parts = []
    dialogues = []
    char_position = 0

    for segment in segments:
        if segment["type"] == "narration":
            narration_parts.append(segment["text"])
            char_position += len(segment["text"])
        else:  # dialogue
            speaker = segment.get("speaker", "unknown")
            emotion = segment.get("emotion", "default")

            dialogues.append({
                "text": segment["text"],
                "speaker": speaker,
                "emotion": emotion,
                "voice": get_voice_for_character(speaker),
                "style_prompt": get_style_for_emotion(emotion),
                "position": char_position,
            })

            # 나레이션에 대사 플레이스홀더 추가 (타이밍 동기화용)
            placeholder = f"[DIALOGUE:{len(dialogues)-1}]"
            narration_parts.append(placeholder)
            char_position += len(placeholder)

    return {
        "ok": True,
        "narration_text": " ".join(narration_parts),
        "dialogues": dialogues,
        "stats": parsed_result.get("stats", {}),
    }


if __name__ == "__main__":
    # 테스트
    test_script = """
    어둠 속에서 목소리가 들려왔다. "이 검법을 네게 전하마." 주름진 손이 어린 소년의 이마를 짚었다.

    "네 눈빛이 마음에 든다." 노인이 말했다.

    그러던 어느 날이었다. "당신이... 혈영인가요?" 하얀 옷을 입은 여인이 앞을 막아섰다.
    """

    print("=== AI 파싱 테스트 ===")
    api_key = os.environ.get('GOOGLE_API_KEY')

    if api_key:
        result = parse_script_with_ai(test_script, api_key)
        if result["ok"]:
            print(f"총 {result['stats']['total']}개 세그먼트")
            print(f"- 나레이션: {result['stats']['narration']}개")
            print(f"- 대사: {result['stats']['dialogue']}개")
            print("\n대사 목록:")
            for d in result["dialogues"]:
                print(f"  [{d['speaker']}:{d['emotion']}] \"{d['text']}\"")
        else:
            print(f"실패: {result['error']}")
    else:
        print("API 키 없음, 간단 파싱으로 테스트")
        result = parse_script_simple(test_script)
        print(f"대사 {result['stats']['dialogue']}개 추출")
        for d in result["dialogues"]:
            print(f"  [{d['speaker']}] \"{d['text']}\"")
