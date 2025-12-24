"""
쇼츠 파이프라인 - 대본 및 이미지 프롬프트 생성

GPT-4o를 사용하여:
1. 60초 쇼츠 대본 생성 (9개 씬)
2. 씬별 이미지 프롬프트 생성 (실루엣 포함)
"""

import os
import json
from typing import Dict, Any, List, Optional

from openai import OpenAI

from .config import (
    DEFAULT_SCENE_COUNT,
    TARGET_SCRIPT_LENGTH,
    BACKGROUND_STYLES,
    SILHOUETTE_TEMPLATE,
    BACKGROUND_ONLY_TEMPLATE,
    VIDEO_WIDTH,
    VIDEO_HEIGHT,
)


def get_openai_client() -> OpenAI:
    """OpenAI 클라이언트 반환"""
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY 환경변수가 설정되지 않았습니다")
    return OpenAI(api_key=api_key)


SCRIPT_GENERATION_PROMPT = """
당신은 연예 뉴스 쇼츠 전문 작가입니다.
아래 뉴스 정보를 60초 YouTube Shorts 대본으로 변환하세요.

## 뉴스 정보
- 연예인: {celebrity}
- 이슈 유형: {issue_type}
- 뉴스 제목: {news_title}
- 뉴스 요약: {news_summary}
- 훅 문장 (참고): {hook_text}

## 실루엣 특징 (이미지용)
{silhouette_desc}

## 대본 규칙
1. 총 450자 내외 (한국어 TTS 60초 기준)
2. 9개 씬으로 구성
3. 첫 문장(씬1)은 충격적인 훅으로 시작 - 시청자가 스크롤을 멈추게
4. 마지막 씬(씬9)은 "구독과 좋아요 부탁드립니다" CTA로 마무리
5. 사실 기반으로 작성, 추측이나 비방 금지
6. 짧고 임팩트 있는 문장 사용
7. 각 씬은 약 50자 내외

## 씬 구성 가이드
- 씬1 (0-5초): 훅 - 충격적인 첫 문장
- 씬2 (5-12초): 상황 설명 - 무슨 일이 있었는지
- 씬3 (12-20초): 핵심 내용 - 폭로/사건의 핵심
- 씬4 (20-27초): 반응 - 본인/소속사 반응
- 씬5 (27-35초): 여론 - 네티즌/팬 반응
- 씬6 (35-42초): 영향 - 방송/활동 영향
- 씬7 (42-50초): 전문가/업계 반응
- 씬8 (50-55초): 결론 - 현재 상황 정리
- 씬9 (55-60초): CTA - 구독 유도

## 이미지 프롬프트 규칙
- 영어로 작성
- 9:16 세로 비율 (YouTube Shorts)
- 연예인 얼굴 사용 금지 - 실루엣만 사용
- 씬1에는 연예인 실루엣 포함
- 나머지 씬은 분위기 배경 위주
- 텍스트 오버레이 공간 확보

## 출력 형식 (JSON만 반환, 다른 텍스트 없이)
{{
    "title": "쇼츠 제목 (30자 이내, 이모지 1-2개 포함)",
    "scenes": [
        {{
            "scene_number": 1,
            "duration": "0-5초",
            "narration": "훅 문장 (약 50자)",
            "image_prompt": "영어 이미지 프롬프트",
            "text_overlay": "화면에 표시할 핵심 텍스트 (10자 이내)"
        }},
        {{
            "scene_number": 2,
            ...
        }},
        ...총 9개 씬
    ],
    "total_chars": 450,
    "hashtags": ["#연예", "#이슈", "#쇼츠", "..."]
}}
"""


def generate_shorts_script(
    celebrity: str,
    issue_type: str,
    news_title: str,
    news_summary: str,
    hook_text: str,
    silhouette_desc: str,
    model: str = "gpt-4o"
) -> Dict[str, Any]:
    """
    GPT를 사용하여 쇼츠 대본 생성

    Args:
        celebrity: 연예인 이름
        issue_type: 이슈 유형
        news_title: 뉴스 제목
        news_summary: 뉴스 요약
        hook_text: 훅 문장
        silhouette_desc: 실루엣 특징 설명
        model: 사용할 GPT 모델

    Returns:
        {
            "ok": True,
            "title": "쇼츠 제목",
            "scenes": [...],
            "full_script": "전체 대본",
            "total_chars": 450,
            "hashtags": [...],
            "cost": 0.03
        }
    """
    try:
        client = get_openai_client()

        prompt = SCRIPT_GENERATION_PROMPT.format(
            celebrity=celebrity,
            issue_type=issue_type,
            news_title=news_title,
            news_summary=news_summary,
            hook_text=hook_text,
            silhouette_desc=silhouette_desc,
        )

        print(f"[SHORTS] 대본 생성 중: {celebrity} - {issue_type}")

        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "당신은 연예 뉴스 쇼츠 전문 작가입니다. JSON 형식으로만 응답하세요."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=2000,
            response_format={"type": "json_object"}
        )

        result_text = response.choices[0].message.content
        result = json.loads(result_text)

        # 전체 대본 조합
        full_script = "\n".join([
            scene["narration"] for scene in result.get("scenes", [])
        ])

        # 비용 계산 (대략적)
        input_tokens = response.usage.prompt_tokens
        output_tokens = response.usage.completion_tokens
        cost = (input_tokens * 0.005 + output_tokens * 0.015) / 1000

        print(f"[SHORTS] 대본 생성 완료: {len(full_script)}자, ${cost:.4f}")

        return {
            "ok": True,
            "title": result.get("title", f"{celebrity} 이슈"),
            "scenes": result.get("scenes", []),
            "full_script": full_script,
            "total_chars": len(full_script),
            "hashtags": result.get("hashtags", []),
            "cost": round(cost, 4),
        }

    except json.JSONDecodeError as e:
        print(f"[SHORTS] JSON 파싱 실패: {e}")
        return {"ok": False, "error": f"JSON 파싱 실패: {e}"}
    except Exception as e:
        print(f"[SHORTS] 대본 생성 실패: {e}")
        return {"ok": False, "error": str(e)}


def enhance_image_prompts(
    scenes: List[Dict[str, Any]],
    celebrity: str,
    silhouette_desc: str
) -> List[Dict[str, Any]]:
    """
    씬별 이미지 프롬프트 강화

    - 씬1: 연예인 실루엣 포함
    - 나머지: 분위기 배경

    Args:
        scenes: GPT가 생성한 씬 목록
        celebrity: 연예인 이름
        silhouette_desc: 실루엣 특징 설명

    Returns:
        강화된 씬 목록
    """
    enhanced_scenes = []

    for scene in scenes:
        scene_num = scene.get("scene_number", 1)
        original_prompt = scene.get("image_prompt", "")

        # 9:16 비율 강제
        aspect_instruction = (
            f"CRITICAL: Generate image in EXACT 9:16 VERTICAL PORTRAIT aspect ratio. "
            f"Target dimensions: {VIDEO_WIDTH}x{VIDEO_HEIGHT} pixels. "
            f"This is MANDATORY for YouTube Shorts format."
        )

        if scene_num == 1:
            # 첫 씬: 실루엣 포함
            enhanced_prompt = f"""
{aspect_instruction}

{original_prompt}

IMPORTANT ADDITIONS:
- Include a black silhouette of {silhouette_desc}
- Dramatic spotlight from above casting long shadow
- NO facial features visible - only dark shadow outline
- Korean entertainment news style
- Large empty space at top and bottom for Korean text overlay
- 4K quality, cinematic lighting
"""
        else:
            # 나머지: 배경 위주
            enhanced_prompt = f"""
{aspect_instruction}

{original_prompt}

IMPORTANT ADDITIONS:
- NO people or human figures in this scene
- Focus on atmospheric background and mood
- Large empty space for Korean text overlay
- 4K quality, cinematic composition
- Korean news broadcast style
"""

        scene["image_prompt_enhanced"] = enhanced_prompt.strip()
        enhanced_scenes.append(scene)

    return enhanced_scenes


def generate_complete_shorts_package(
    news_data: Dict[str, Any],
    model: str = "gpt-4o"
) -> Dict[str, Any]:
    """
    쇼츠 전체 패키지 생성 (대본 + 이미지 프롬프트)

    Args:
        news_data: {
            "celebrity": "...",
            "issue_type": "...",
            "news_title": "...",
            "news_summary": "...",
            "hook_text": "...",
            "silhouette_desc": "..."
        }

    Returns:
        {
            "ok": True,
            "title": "쇼츠 제목",
            "full_script": "전체 대본",
            "scenes": [
                {
                    "scene_number": 1,
                    "narration": "...",
                    "image_prompt_enhanced": "...",
                    "text_overlay": "..."
                },
                ...
            ],
            "hashtags": [...],
            "cost": 0.03
        }
    """
    # 1) 대본 생성
    script_result = generate_shorts_script(
        celebrity=news_data.get("celebrity", ""),
        issue_type=news_data.get("issue_type", ""),
        news_title=news_data.get("news_title", ""),
        news_summary=news_data.get("news_summary", ""),
        hook_text=news_data.get("hook_text", ""),
        silhouette_desc=news_data.get("silhouette_desc", ""),
        model=model,
    )

    if not script_result.get("ok"):
        return script_result

    # 2) 이미지 프롬프트 강화
    enhanced_scenes = enhance_image_prompts(
        scenes=script_result.get("scenes", []),
        celebrity=news_data.get("celebrity", ""),
        silhouette_desc=news_data.get("silhouette_desc", ""),
    )

    return {
        "ok": True,
        "title": script_result.get("title"),
        "full_script": script_result.get("full_script"),
        "scenes": enhanced_scenes,
        "total_chars": script_result.get("total_chars"),
        "hashtags": script_result.get("hashtags", []),
        "cost": script_result.get("cost", 0),
    }


def format_script_for_sheet(scenes: List[Dict[str, Any]]) -> str:
    """
    씬 목록을 시트 저장용 대본 형식으로 변환

    Returns:
        "[씬1] 훅 문장\n[씬2] 설명 문장\n..."
    """
    lines = []
    for scene in scenes:
        scene_num = scene.get("scene_number", 0)
        narration = scene.get("narration", "")
        lines.append(f"[씬{scene_num}] {narration}")
    return "\n".join(lines)
