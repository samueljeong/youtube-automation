"""
TTS Chunking Module
Google TTS 5000바이트 제한을 해결하기 위한 텍스트 분할 알고리즘

핵심 기능:
1. 한글 문장 단위 분리
2. 바이트 제한에 맞는 청크 생성
3. 씬별 청크 빌더
"""

import re
from typing import List, Dict

# Google TTS 바이트 제한 (5000) 보다 여유있게 설정
MAX_BYTES = 4800


def utf8_len(text: str) -> int:
    """UTF-8 인코딩 바이트 길이 계산"""
    return len(text.encode("utf-8"))


def _protect_numbers(text: str) -> tuple[str, dict]:
    """
    숫자+마침표+숫자 패턴(소수점, 버전 등)을 임시 플레이스홀더로 치환
    예: 1.5톤 → __NUM_0__톤

    Returns:
        (치환된 텍스트, 복원용 딕셔너리)
    """
    import re
    placeholders = {}
    counter = [0]

    def replacer(match):
        key = f"__NUM_{counter[0]}__"
        placeholders[key] = match.group(0)
        counter[0] += 1
        return key

    # 숫자.숫자 패턴 (1.5, 3.14, 2.0 등)
    protected = re.sub(r'(\d+\.\d+)', replacer, text)
    return protected, placeholders


def _restore_numbers(text: str, placeholders: dict) -> str:
    """플레이스홀더를 원래 숫자로 복원"""
    for key, value in placeholders.items():
        text = text.replace(key, value)
    return text


def preprocess_for_tts(text: str) -> str:
    """
    TTS 전송 전 텍스트 전처리

    1. 숫자.숫자 패턴 보호 (소수점)
    2. 쉼표 뒤에 휴지 추가 (자연스러운 발음)
    3. 단위 표기 개선 (1.5톤 → 1점5톤)

    Args:
        text: 원본 텍스트

    Returns:
        TTS에 최적화된 텍스트
    """
    import re

    if not text:
        return text

    # 1) 숫자.숫자 패턴을 "숫자점숫자"로 변환 (TTS가 자연스럽게 읽도록)
    # 예: 1.5톤 → 1점5톤, 3.14 → 3점14
    def replace_decimal(match):
        num = match.group(0)
        return num.replace('.', '점')

    text = re.sub(r'(\d+)\.(\d+)', replace_decimal, text)

    # 2) 쉼표 뒤에 공백이 없으면 추가 (TTS 휴지 개선)
    text = re.sub(r',(\S)', r', \1', text)

    # 3) 연속 쉼표 정리
    text = re.sub(r',\s*,+', ',', text)

    return text


def preprocess_for_tts_ssml(text: str) -> str:
    """
    SSML 모드용 TTS 전처리 (쉼표에 명시적 휴지 추가)

    Args:
        text: 원본 텍스트

    Returns:
        SSML 휴지가 포함된 텍스트 (아직 <speak> 태그 없음)
    """
    import re
    import html

    if not text:
        return text

    # 1) 먼저 기본 전처리 적용
    text = preprocess_for_tts(text)

    # 2) XML 특수문자 이스케이프
    text = html.escape(text, quote=False)

    # 3) 쉼표 뒤에 SSML 휴지 추가 (150ms - 자연스러운 짧은 휴지)
    text = re.sub(r',\s*', ',<break time="150ms"/> ', text)

    return text


# 마침표, 물음표, 느낌표, 말줄임표 기준으로 분리
SENTENCE_SPLIT_REGEX = re.compile(r'([^.?!…]*[.?!…]+\s*)')


def split_korean_sentences(text: str) -> List[str]:
    """
    한글 텍스트를 문장 단위로 분리
    (숫자.숫자 패턴은 분리하지 않음 - 1.5톤, 3.14 등)

    Args:
        text: 분리할 텍스트

    Returns:
        문장 리스트
    """
    text = text.strip()
    if not text:
        return []

    # 1) 숫자.숫자 패턴 보호 (소수점)
    protected_text, placeholders = _protect_numbers(text)

    # 2) 정규식으로 문장 분리
    parts = SENTENCE_SPLIT_REGEX.findall(protected_text + " ")
    sentences = [s.strip() for s in parts if s.strip()]

    # 마침표 없는 텍스트가 남으면 그대로 반환
    if not sentences:
        return [_restore_numbers(text, placeholders)]

    # 3) 숫자 복원
    sentences = [_restore_numbers(s, placeholders) for s in sentences]

    return sentences


def chunk_sentences(sentences: List[str], max_bytes: int = MAX_BYTES) -> List[str]:
    """
    문장 리스트를 바이트 제한에 맞게 청크로 묶기
    
    Args:
        sentences: 문장 리스트
        max_bytes: 최대 바이트 (기본 4800)
        
    Returns:
        청크 리스트 (각 청크는 max_bytes 이하)
    """
    chunks: List[str] = []
    current: List[str] = []
    current_len = 0
    
    for sent in sentences:
        sent_len = utf8_len(sent)
        
        # 한 문장 자체가 너무 길면 단독 청크로
        if sent_len > max_bytes:
            # 현재까지 모은 것 저장
            if current:
                chunks.append(" ".join(current))
                current = []
                current_len = 0
            
            # 긴 문장은 쉼표 단위로 추가 분할
            sub_chunks = _split_long_sentence(sent, max_bytes)
            chunks.extend(sub_chunks)
            continue
        
        # 새 문장 추가 시 바이트 초과하면 새 청크 시작
        if current and current_len + 1 + sent_len > max_bytes:
            chunks.append(" ".join(current))
            current = [sent]
            current_len = sent_len
        else:
            if current:
                current_len += 1 + sent_len  # 공백 포함
                current.append(sent)
            else:
                current = [sent]
                current_len = sent_len
    
    # 마지막 청크 저장
    if current:
        chunks.append(" ".join(current))
    
    return chunks


def _split_long_sentence(sentence: str, max_bytes: int) -> List[str]:
    """
    너무 긴 문장을 쉼표나 공백 기준으로 분할
    
    Args:
        sentence: 긴 문장
        max_bytes: 최대 바이트
        
    Returns:
        분할된 청크 리스트
    """
    chunks = []
    
    # 쉼표 기준으로 먼저 분할 시도
    parts = re.split(r'([,，、]\s*)', sentence)
    
    current = ""
    for part in parts:
        if utf8_len(current + part) < max_bytes:
            current += part
        else:
            if current.strip():
                chunks.append(current.strip())
            current = part
    
    if current.strip():
        chunks.append(current.strip())
    
    # 여전히 긴 청크가 있으면 강제 분할
    final_chunks = []
    for chunk in chunks:
        if utf8_len(chunk) > max_bytes:
            # 강제로 바이트 단위 분할
            final_chunks.extend(_force_split_by_bytes(chunk, max_bytes))
        else:
            final_chunks.append(chunk)
    
    return final_chunks


def _force_split_by_bytes(text: str, max_bytes: int) -> List[str]:
    """바이트 제한에 맞게 강제 분할 (최후의 수단)"""
    chunks = []
    current = ""
    
    for char in text:
        if utf8_len(current + char) < max_bytes:
            current += char
        else:
            if current:
                chunks.append(current)
            current = char
    
    if current:
        chunks.append(current)
    
    return chunks


def build_chunks_for_scenes(scenes: List[Dict]) -> List[Dict]:
    """
    씬 리스트를 받아 TTS용 청크 리스트 생성
    
    Args:
        scenes: 씬 정보 리스트
            [{ "id": "scene1", "narration": "...", ... }, ...]
            
    Returns:
        청크 정보 리스트
            [{
                "scene_id": "scene1",
                "chunk_index": 0,
                "text": "청크 텍스트",
                "sentences": ["문장1", "문장2", ...]
            }, ...]
    """
    all_chunks = []
    
    for scene in scenes:
        scene_id = scene.get("id") or scene.get("scene_id", f"scene_{len(all_chunks)}")
        narration = scene.get("narration", "").strip()
        
        if not narration:
            continue
        
        # 문장 분리
        sentences = split_korean_sentences(narration)
        
        # 청크로 묶기
        chunks = chunk_sentences(sentences)
        
        # 청크별 정보 생성
        for idx, chunk_text in enumerate(chunks):
            all_chunks.append({
                "scene_id": scene_id,
                "chunk_index": idx,
                "text": chunk_text,
                "sentences": split_korean_sentences(chunk_text),
                "byte_length": utf8_len(chunk_text)
            })
    
    return all_chunks


def estimate_chunk_stats(chunks: List[Dict]) -> Dict:
    """청크 통계 정보 생성"""
    if not chunks:
        return {"total_chunks": 0, "total_bytes": 0, "avg_bytes": 0}
    
    total_bytes = sum(c.get("byte_length", 0) for c in chunks)
    
    return {
        "total_chunks": len(chunks),
        "total_bytes": total_bytes,
        "avg_bytes": total_bytes // len(chunks) if chunks else 0,
        "max_bytes": max(c.get("byte_length", 0) for c in chunks),
        "min_bytes": min(c.get("byte_length", 0) for c in chunks)
    }


# ===== 테스트 =====
if __name__ == "__main__":
    # 테스트 텍스트
    test_narration = """
    오늘은 그 시절, 우리 동네 작은 구멍가게 이야기를 나눠보려고 합니다. 
    아침마다 문을 열던 구멍가게 앞에는 늘 아이들이 모여들었어요. 
    손에 쥔 몇십 원짜리 동전 하나로 무엇을 살지 한참을 고민하던 그때가 떠오릅니다.
    그 시절 구멍가게 아저씨는 동네 아이들 이름을 다 외우고 계셨어요.
    "영수야, 오늘은 뭐 먹을래?" 하고 물어보시던 그 목소리가 아직도 귀에 맴돕니다.
    """
    
    test_scenes = [
        {"id": "scene1", "narration": test_narration},
        {"id": "scene2", "narration": "이것은 두 번째 씬입니다. 짧은 테스트 문장이에요."}
    ]
    
    # 청크 생성
    chunks = build_chunks_for_scenes(test_scenes)
    
    print("=== 청크 결과 ===")
    for chunk in chunks:
        print(f"[{chunk['scene_id']}][청크{chunk['chunk_index']}] {chunk['byte_length']}bytes")
        print(f"  텍스트: {chunk['text'][:50]}...")
        print(f"  문장 수: {len(chunk['sentences'])}")
        print()
    
    stats = estimate_chunk_stats(chunks)
    print("=== 통계 ===")
    print(stats)
