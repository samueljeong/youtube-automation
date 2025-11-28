import json
from pathlib import Path
from typing import Dict, Any

from openai import OpenAI

client = OpenAI()


def load_system_prompt() -> str:
    """
    metadata_prompt_rules.txt 내용을 읽어온다.
    """
    prompt_path = Path(__file__).parent / "metadata_prompt_rules.txt"
    return prompt_path.read_text(encoding="utf-8")


def build_metadata(step1_output: Dict[str, Any], thumbnail: Dict[str, Any]) -> Dict[str, Any]:
    """
    Step1 결과와 Step4 썸네일 정보를 바탕으로
    YouTube 업로드용 title / description / tags를 생성한다.
    """
    system_prompt = load_system_prompt()

    user_input = {
        "category": step1_output.get("category", "category1"),
        "main_title": step1_output.get("titles", {}).get("main_title", ""),
        "scenes": step1_output.get("scenes", []),
        "thumbnail_text": thumbnail.get("thumbnail_text", "")
    }

    completion = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": json.dumps(user_input, ensure_ascii=False)}
        ],
        temperature=0.6,
    )

    content = completion.choices[0].message.content

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
