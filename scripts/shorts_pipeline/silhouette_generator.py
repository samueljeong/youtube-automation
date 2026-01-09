"""
동적 실루엣 생성기

Google 검색으로 인물 특징을 자동 추출하여 실루엣 프롬프트 생성
- 캐시 기능으로 중복 검색 방지
- GPT로 특징 추출 (성별, 헤어스타일, 체형, 대표 포즈)
"""

import os
import json
import time
from typing import Optional, Dict, Any
from datetime import datetime

# 캐시 파일 경로
CACHE_DIR = os.path.join(os.path.dirname(__file__), ".cache")
SILHOUETTE_CACHE_FILE = os.path.join(CACHE_DIR, "silhouette_cache.json")

# 캐시 만료 시간 (30일)
CACHE_EXPIRY_DAYS = 30


def ensure_cache_dir():
    """캐시 디렉토리 생성"""
    if not os.path.exists(CACHE_DIR):
        os.makedirs(CACHE_DIR, exist_ok=True)


def load_cache() -> Dict[str, Any]:
    """캐시 로드"""
    ensure_cache_dir()
    if os.path.exists(SILHOUETTE_CACHE_FILE):
        try:
            with open(SILHOUETTE_CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return {}
    return {}


def save_cache(cache: Dict[str, Any]):
    """캐시 저장"""
    ensure_cache_dir()
    try:
        with open(SILHOUETTE_CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(cache, f, ensure_ascii=False, indent=2)
    except IOError as e:
        print(f"[SilhouetteGenerator] 캐시 저장 실패: {e}")


def get_cached_silhouette(person: str) -> Optional[str]:
    """캐시에서 실루엣 조회"""
    cache = load_cache()

    if person in cache:
        entry = cache[person]
        # 만료 체크
        cached_time = datetime.fromisoformat(entry.get("cached_at", "2000-01-01"))
        age_days = (datetime.now() - cached_time).days

        if age_days < CACHE_EXPIRY_DAYS:
            print(f"[SilhouetteGenerator] 캐시 히트: {person}")
            return entry.get("silhouette_desc")
        else:
            print(f"[SilhouetteGenerator] 캐시 만료: {person} ({age_days}일 전)")

    return None


def save_to_cache(person: str, silhouette_desc: str, source_info: str = ""):
    """캐시에 저장"""
    cache = load_cache()
    cache[person] = {
        "silhouette_desc": silhouette_desc,
        "source_info": source_info,
        "cached_at": datetime.now().isoformat(),
    }
    save_cache(cache)
    print(f"[SilhouetteGenerator] 캐시 저장: {person}")


def search_celebrity_info(person: str, category: str = "연예인") -> Optional[str]:
    """
    Google 검색으로 인물 정보 조회

    Args:
        person: 인물 이름
        category: 카테고리 (연예인/운동선수/국뽕)

    Returns:
        검색 결과 텍스트 (상위 결과 요약)
    """
    try:
        # googlesearch-python 라이브러리 사용 시도
        try:
            from googlesearch import search as google_search

            # 카테고리별 검색 쿼리
            if category == "운동선수":
                query = f"{person} 선수 프로필 외모 특징"
            else:
                query = f"{person} 연예인 프로필 외모 특징"

            print(f"[SilhouetteGenerator] Google 검색: {query}")

            # 상위 5개 결과 URL 수집
            results = []
            for url in google_search(query, num_results=5, lang="ko"):
                results.append(url)

            if results:
                return f"검색 결과 URL: {', '.join(results[:3])}"

        except ImportError:
            pass

        # requests + BeautifulSoup으로 직접 검색 시도
        import requests
        from urllib.parse import quote

        if category == "운동선수":
            query = f"{person} 선수 프로필 키 외모"
        else:
            query = f"{person} 연예인 프로필 키 외모"

        encoded_query = quote(query)
        url = f"https://www.google.com/search?q={encoded_query}&hl=ko"

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }

        response = requests.get(url, headers=headers, timeout=10)

        if response.status_code == 200:
            # 간단한 텍스트 추출 (HTML 파싱 없이)
            text = response.text[:5000]  # 상위 5000자만
            return f"검색 결과 (raw): {text[:500]}..."

        return None

    except Exception as e:
        print(f"[SilhouetteGenerator] 검색 실패: {e}")
        return None


def extract_features_with_llm(
    person: str,
    category: str = "연예인",
    search_result: Optional[str] = None
) -> Optional[str]:
    """
    LLM으로 인물 특징 추출하여 실루엣 프롬프트 생성

    Args:
        person: 인물 이름
        category: 카테고리
        search_result: 검색 결과 (없으면 이름 기반 추론)

    Returns:
        영어 실루엣 프롬프트
    """
    try:
        from openai import OpenAI

        client = OpenAI()

        # 프롬프트 구성
        if search_result:
            context = f"""
검색 결과:
{search_result[:1000]}
"""
        else:
            context = "(검색 결과 없음 - 이름과 카테고리만으로 추론)"

        prompt = f"""
당신은 이미지 생성을 위한 실루엣 프롬프트 전문가입니다.

다음 인물의 특징을 분석하여 실루엣(검은 그림자) 이미지 생성용 영어 프롬프트를 작성하세요.

## 인물 정보
- 이름: {person}
- 카테고리: {category}
{context}

## 추출할 특징
1. 성별 (male/female)
2. 체형 (slim/athletic/average/stocky 등)
3. 헤어스타일 (short/long/curly/straight 등)
4. 대표적인 포즈나 특징 (예: 마이크 들고 있는, 운동하는, 우아한 자세 등)
5. 직업/활동 관련 특징

## 출력 형식
영어로 30단어 이내의 실루엣 설명을 작성하세요.
기존 예시:
- "athletic female figure with strong posture, confident mother stance, short hair, action hero pose"
- "male figure with messy hair, casual comedian pose"
- "tall athletic female volleyball player in spiking pose"

## 주의사항
- 얼굴 특징은 포함하지 마세요 (실루엣이므로)
- 구체적인 외모 묘사 대신 체형과 포즈에 집중
- 영어로만 작성

실루엣 프롬프트:
"""

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a silhouette image prompt expert. Output only the English silhouette description, nothing else."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=100,
            temperature=0.7
        )

        result = response.choices[0].message.content.strip()

        # 따옴표 제거
        result = result.strip('"\'')

        print(f"[SilhouetteGenerator] LLM 결과: {result}")
        return result

    except ImportError:
        print("[SilhouetteGenerator] OpenAI 라이브러리 없음")
        return None
    except Exception as e:
        print(f"[SilhouetteGenerator] LLM 추출 실패: {e}")
        return None


def generate_silhouette_dynamic(
    person: str,
    category: str = "연예인",
    use_cache: bool = True,
    use_search: bool = True,
    use_llm: bool = True
) -> str:
    """
    동적 실루엣 생성 메인 함수

    1. 캐시 확인
    2. Google 검색으로 정보 수집
    3. LLM으로 특징 추출
    4. 결과 캐시 저장

    Args:
        person: 인물 이름
        category: 카테고리
        use_cache: 캐시 사용 여부
        use_search: Google 검색 사용 여부
        use_llm: LLM 사용 여부

    Returns:
        실루엣 프롬프트 (영어)
    """
    print(f"[SilhouetteGenerator] 동적 생성 시작: {person} ({category})")

    # 1. 캐시 확인
    if use_cache:
        cached = get_cached_silhouette(person)
        if cached:
            return cached

    # 2. Google 검색
    search_result = None
    if use_search:
        search_result = search_celebrity_info(person, category)
        time.sleep(0.5)  # 검색 API 부하 방지

    # 3. LLM으로 특징 추출
    silhouette_desc = None
    if use_llm:
        silhouette_desc = extract_features_with_llm(person, category, search_result)

    # 4. 결과 처리
    if silhouette_desc:
        # 캐시에 저장
        if use_cache:
            save_to_cache(person, silhouette_desc, f"search: {bool(search_result)}")
        return silhouette_desc

    # 5. Fallback: 성별 추정으로 기본값 반환
    print(f"[SilhouetteGenerator] Fallback: 성별 추정으로 기본값 사용")

    # 여성에 많은 끝글자
    female_endings = ["희", "영", "경", "숙", "정", "연", "아", "이", "나", "라", "지", "은", "현"]

    if person and len(person) >= 2:
        if person[-1] in female_endings:
            default = "female figure in casual standing pose"
        else:
            default = "male figure in casual standing pose"
    else:
        default = "person figure in standing pose"

    # 기본값도 캐시에 저장 (재검색 방지)
    if use_cache:
        save_to_cache(person, default, "fallback")

    return default


def clear_cache(person: Optional[str] = None):
    """
    캐시 초기화

    Args:
        person: 특정 인물만 삭제 (None이면 전체 삭제)
    """
    if person:
        cache = load_cache()
        if person in cache:
            del cache[person]
            save_cache(cache)
            print(f"[SilhouetteGenerator] 캐시 삭제: {person}")
    else:
        if os.path.exists(SILHOUETTE_CACHE_FILE):
            os.remove(SILHOUETTE_CACHE_FILE)
            print("[SilhouetteGenerator] 전체 캐시 삭제")


def get_cache_stats() -> Dict[str, Any]:
    """캐시 통계"""
    cache = load_cache()
    return {
        "total_entries": len(cache),
        "entries": list(cache.keys()),
    }


# CLI 테스트용
if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        person = sys.argv[1]
        category = sys.argv[2] if len(sys.argv) > 2 else "연예인"

        result = generate_silhouette_dynamic(person, category)
        print(f"\n결과: {result}")
    else:
        print("사용법: python silhouette_generator.py <인물이름> [카테고리]")
        print("예시: python silhouette_generator.py 이시영 연예인")
