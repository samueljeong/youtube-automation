import os
import json
from pathlib import Path
from typing import Dict, Any, Optional


def load_system_prompt() -> str:
    """
    metadata_prompt_rules.txt 내용을 읽어온다.
    """
    prompt_path = Path(__file__).parent / "metadata_prompt_rules.txt"
    return prompt_path.read_text(encoding="utf-8")


def _get_openai_client() -> Optional[object]:
    """
    OpenAI 클라이언트를 가져온다. API 키가 없으면 None 반환.
    """
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return None

    try:
        from openai import OpenAI
        return OpenAI(api_key=api_key)
    except ImportError:
        print("[WARNING] openai package not installed")
        return None


def _generate_rule_based_metadata(step1_output: Dict[str, Any], thumbnail: Dict[str, Any]) -> Dict[str, Any]:
    """
    규칙 기반 메타데이터 생성 (API 키 없을 때 fallback)
    """
    main_title = step1_output.get("titles", {}).get("main_title", "제목 미정")
    category = step1_output.get("category", "category1")
    scenes = step1_output.get("scenes", [])

    # 첫 씬 나레이션에서 설명 추출
    first_narration = ""
    if scenes:
        first_narration = scenes[0].get("narration", "")[:100]

    # 카테고리별 기본 태그
    if category == "category1":
        default_tags = ["향수", "추억", "그때그시절", "옛날이야기", "시골", "70년대", "80년대", "시니어", "감성", "힐링"]
    else:
        default_tags = ["명언", "인생", "지혜", "마음", "위로", "시니어", "라디오", "감성", "힐링", "오늘의명언"]

    description = f"{main_title}\n\n{first_narration}\n\n오늘도 함께해 주셔서 감사합니다.\n함께 그 시절을 떠올려 보시면 좋겠습니다."

    return {
        "title": main_title,
        "description": description,
        "tags": default_tags
    }


def build_metadata(step1_output: Dict[str, Any], thumbnail: Dict[str, Any]) -> Dict[str, Any]:
    """
    Step1 결과와 Step4 썸네일 정보를 바탕으로
    YouTube 업로드용 title / description / tags를 생성한다.
    """
    client = _get_openai_client()

    if not client:
        print("[Step5-Metadata] OPENAI_API_KEY not set. Using rule-based generation.")
        return _generate_rule_based_metadata(step1_output, thumbnail)

    system_prompt = load_system_prompt()

    user_input = {
        "category": step1_output.get("category", "category1"),
        "main_title": step1_output.get("titles", {}).get("main_title", ""),
        "scenes": step1_output.get("scenes", []),
        "thumbnail_text": thumbnail.get("thumbnail_text", "")
    }

    try:
        print("[Step5-Metadata] Calling GPT-4o-mini for metadata generation...")

        completion = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": json.dumps(user_input, ensure_ascii=False)}
            ],
            temperature=0.6,
        )

        content = completion.choices[0].message.content
        print(f"[Step5-Metadata] Response received ({len(content)} chars)")

        # 모델이 JSON만 반환한다고 가정하지만, 방어적으로 파싱
        try:
            metadata = json.loads(content)
        except json.JSONDecodeError:
            # 파싱 실패 시, 최소한의 기본값으로 대체
            metadata = {
                "title": step1_output.get("titles", {}).get("main_title", "제목 미정"),
                "description": "이 영상은 시니어 시청자를 위한 옛날 이야기 / 향수 콘텐츠입니다.",
                "tags": ["추억", "그때그시절", "옛날이야기"]
            }

        # 필수 필드 보정
        metadata.setdefault("title", "제목 미정")
        metadata.setdefault("description", "시니어 시청자를 위한 영상입니다.")
        metadata.setdefault("tags", ["추억", "시니어"])

        return metadata

    except Exception as e:
        print(f"[Step5-Metadata] API call failed: {e}")
        print("[Step5-Metadata] Falling back to rule-based generation.")
        return _generate_rule_based_metadata(step1_output, thumbnail)
