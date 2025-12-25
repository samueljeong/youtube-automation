"""
쇼츠 파이프라인 - 대본 및 이미지 프롬프트 생성

GPT-5.1 Responses API를 사용하여:
1. 60초 쇼츠 대본 생성 (9개 씬)
2. 씬별 이미지 프롬프트 생성 (실루엣 포함)
"""

import os
import re
import json
from typing import Dict, Any, List, Optional

from openai import OpenAI


def repair_json(text: str) -> str:
    """
    불완전한 JSON 수정 시도
    - 마크다운 코드 블록 제거
    - 후행 콤마 제거
    - 누락된 콤마 추가
    """
    # 1) 마크다운 코드 블록 제거
    if "```" in text:
        match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', text)
        if match:
            text = match.group(1)
        else:
            # 시작만 있고 끝이 없는 경우
            text = re.sub(r'^```(?:json)?\s*', '', text)
            text = re.sub(r'\s*```$', '', text)

    # 2) 후행 콤마 제거 (배열/객체 끝의 콤마)
    text = re.sub(r',\s*([}\]])', r'\1', text)

    # 3) 줄바꿈 후 따옴표가 오는데 콤마가 없는 경우 수정
    # "value"\n"key" → "value",\n"key"
    text = re.sub(r'"\s*\n\s*"(?=[a-zA-Z_가-힣])', '",\n"', text)

    # 4) 객체/배열 끝 후 콤마 없이 다음 요소가 오는 경우
    # }\n{ → },\n{
    text = re.sub(r'}\s*\n\s*{', '},\n{', text)
    # ]\n[ → ],\n[
    text = re.sub(r']\s*\n\s*\[', '],\n[', text)

    return text.strip()


def safe_json_parse(text: str) -> Dict[str, Any]:
    """
    안전한 JSON 파싱 (수정 시도 포함)
    """
    # 1차 시도: 직접 파싱
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # 2차 시도: 수정 후 파싱
    repaired = repair_json(text)
    try:
        return json.loads(repaired)
    except json.JSONDecodeError as e:
        # 최종 실패 시 상세 에러 출력
        print(f"[SHORTS] JSON 수정 후에도 파싱 실패")
        print(f"[SHORTS] 에러 위치: line {e.lineno}, col {e.colno}")
        print(f"[SHORTS] 수정된 JSON 앞 500자:\n{repaired[:500]}")
        raise

from .config import (
    DEFAULT_SCENE_COUNT,
    TARGET_SCRIPT_LENGTH,
    BACKGROUND_STYLES,
    SILHOUETTE_TEMPLATE,
    BACKGROUND_ONLY_TEMPLATE,
    VIDEO_WIDTH,
    VIDEO_HEIGHT,
)


# 기본 모델
DEFAULT_MODEL = "gpt-5.1"

# GPT-5.1 비용 (USD per 1K tokens)
GPT51_COSTS = {
    "input": 0.01,   # $0.01 per 1K input tokens
    "output": 0.03,  # $0.03 per 1K output tokens
}


def get_openai_client() -> OpenAI:
    """OpenAI 클라이언트 반환"""
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY 환경변수가 설정되지 않았습니다")
    return OpenAI(api_key=api_key)


def extract_gpt51_response(response) -> str:
    """
    GPT-5.1 Responses API 응답에서 텍스트 추출

    Args:
        response: client.responses.create() 응답 객체

    Returns:
        추출된 텍스트
    """
    # 방법 1: output_text 직접 접근
    if getattr(response, "output_text", None):
        return response.output_text.strip()

    # 방법 2: output 배열에서 추출
    text_chunks = []
    for item in getattr(response, "output", []) or []:
        for content in getattr(item, "content", []) or []:
            if getattr(content, "type", "") == "text":
                text_chunks.append(getattr(content, "text", ""))

    return "\n".join(text_chunks).strip()


SCRIPT_GENERATION_PROMPT = """
당신은 조회수 1000만을 만드는 연예 뉴스 쇼츠 전문 작가입니다.
아래 뉴스 정보를 30-40초 YouTube Shorts 대본으로 변환하세요.

## 뉴스 정보
- 연예인: {celebrity}
- 이슈 유형: {issue_type}
- 뉴스 제목: {news_title}
- 뉴스 요약: {news_summary}
- 훅 문장 (참고): {hook_text}

## 실루엣 특징 (이미지용)
{silhouette_desc}

## ⚠️ 가장 중요: 첫 3초 훅

첫 3초가 전부입니다. 시청자가 스크롤을 멈추고 "뭐지?" 하고 보게 만들어야 합니다.

### 훅 작성 공식
1. **궁금증 유발**: "이게 사실이라면..." / "아무도 몰랐던..."
2. **충격 예고**: "결국 이렇게 됐습니다" / "모두가 충격받았습니다"
3. **감정 자극**: "팬들이 울었습니다" / "업계가 발칵 뒤집혔습니다"
4. **숫자 활용**: "24시간 만에..." / "10년 만에 처음..."
5. **대비 활용**: "웃으며 말했지만..." / "모두가 축하했는데..."

### 훅 금지 표현
- "안녕하세요", "오늘은", "여러분" (지루함)
- 질문으로 시작 (약함)
- 설명으로 시작 (이탈)

## 🔄 스토리 구조 (핵심!)

시청자가 끝까지 보고 "이 결말이구나!" 하고 만족하게 만드세요.
**절대 반복 금지!** 각 씬은 새로운 정보를 담아야 합니다.

### ⚠️ 반복 금지 규칙
1. **훅 문구 반복 금지**: 첫 씬의 훅 문구를 마지막에 재사용하지 마세요
2. **같은 표현 금지**: "이렇게 됐습니다", "결국" 등 2번 이상 사용 금지
3. **각 씬 독립적**: 모든 씬이 새로운 사실/관점을 제공해야 함

### 좋은 결말 예시
- "앞으로 [구체적 상황]이 주목됩니다" (미래 예측)
- "이 사건으로 [구체적 변화]가 예상됩니다" (파급 효과)
- "[인물]의 다음 행보가 궁금해집니다" (후속 관심)

### 나쁜 결말 예시 (금지!)
- ❌ "결국 이렇게 됐습니다" (훅 반복)
- ❌ "그래서 [인물]은..." (결론 없이 흐지부지)
- ❌ 첫 씬과 같은 문장 사용

## 📌 사실 검증 규칙 (필수!)

1. **출처 기반**: 뉴스 기사 내용만 사용, 추측/창작 금지
2. **확인된 사실만**: "~라고 한다", "~로 알려졌다" 등 불확실 표현 사용
3. **법적 리스크 회피**:
   - 유죄 확정 전: "혐의", "의혹" 표현 필수
   - "범인", "가해자" 단정 금지
4. **금지 표현**: "확실히 ~이다", "~임이 밝혀졌다"(미확인), 비속어

## 💬 댓글 유도 기술 (알고리즘 핵심!)

댓글이 많으면 알고리즘이 영상을 더 많이 노출합니다.
씬5(여론)나 씬7(반전) 후에 자연스럽게 댓글 유도 문구를 삽입하세요.

### 댓글 유도 기법
1. **의견 요청**: "여러분 생각은 어떠세요?" (자연스럽게)
2. **투표형**: "응원하면 ❤️, 실망이면 💔" (참여 유도)
3. **예측형**: "앞으로 어떻게 될까요?" (궁금증 연장)
4. **논쟁 유발**: "팬들 사이에서도 의견이 갈리고 있습니다" (양측 의견 충돌)
5. **경험 공유**: "비슷한 경험 있으신 분?" (공감대 형성)

### 댓글 유도 예시
- "이거... 여러분은 어떻게 생각하세요?" (씬5 끝)
- "결과가 어떻게 될지... 댓글로 예측해보세요" (씬7 끝)

## 대본 규칙
1. 총 200-260자 (30-40초 TTS 기준)
2. 5개 씬으로 구성 (짧고 임팩트있게!)
3. 모든 문장은 짧고 강렬하게 (한 문장 15자 이내 권장)
4. 사실 기반, 추측/비방 금지
5. **매 씬마다 새로운 정보** (반복 절대 금지!)
6. **씬4에 댓글 유도 문구 1개 필수 삽입**

## 씬 구성 가이드 (30-40초, 5개 씬)
- 씬1 (0-3초): ⚡ 킬러 훅 - 스크롤 멈추게
- 씬2 (3-12초): 상황 설명 - 무슨 일이 있었나
- 씬3 (12-22초): 핵심 내용 - 가장 충격적인 사실
- 씬4 (22-32초): 반응/여론 + 💬댓글유도
- 씬5 (32-40초): 🎯 결론 - 구체적 마무리 (훅 반복 금지!)

## 이미지 프롬프트 규칙
- 영어로 작성
- 9:16 세로 비율 (YouTube Shorts)
- ⚠️ 실루엣은 씬1에만! 나머지는 대본 내용에 맞는 배경 이미지
- 씬1: 연예인 실루엣 (검은 그림자, 첫 인상용)
- 씬2-4: 대본 내용을 시각화한 배경 (사람 없이!)
- 씬5: 결론 분위기에 맞는 이미지
- 텍스트 오버레이 공간 확보
- 4K 퀄리티, 영화적 조명

## 출력 형식 (JSON만 반환)
{{
    "title": "쇼츠 제목 (30자 이내, 이모지 1-2개, 궁금증 유발)",
    "hook_strength": "훅의 강도 1-10점 자체 평가",
    "no_repetition_check": "각 씬이 반복 없이 새로운 정보를 담고 있는지 확인 (예/아니오)",
    "comment_trigger": {{
        "scene": 4,
        "type": "opinion/vote/predict/debate/share 중 하나",
        "text": "실제 삽입된 댓글 유도 문구"
    }},
    "fact_sources": ["뉴스 기사에서 인용한 사실들 요약"],
    "bgm": {{
        "mood": "hopeful/sad/tense/dramatic/calm/inspiring/mysterious/epic/romantic/upbeat 중 하나",
        "reason": "이 분위기를 선택한 이유 (한 줄)"
    }},
    "highlight_keywords": ["충격", "폭로", "...자막에서 강조할 키워드들"],

    "youtube_seo": {{
        "title": "YouTube 제목 (70자 이내, 핵심 키워드 앞에, 이모지 1-2개)",
        "description": "YouTube 설명\\n- 첫 줄: 핵심 요약\\n- 주요 포인트 3개\\n- 해시태그\\n\\n#연예인이름 #이슈 #Shorts",
        "tags": ["인물명한글", "인물명영문", "이슈키워드", "연예뉴스", "쇼츠", "최대30개"]
    }},

    "thumbnail": {{
        "hook_text": "썸네일에 표시할 핵심 문구 (10자 이내, 2줄로 줄바꿈 가능)",
        "style": "논란/열애/성과/자랑/default 중 하나 (이슈 타입에 맞게)",
        "image_prompt": "썸네일 이미지 프롬프트 (영어, 실루엣 포함, 극적 조명)"
    }},

    "scenes": [
        {{
            "scene_number": 1,
            "duration": "0-3초",
            "narration": "킬러 훅 문장",
            "image_prompt": "영어 이미지 프롬프트 (실루엣 포함)",
            "text_overlay": "화면 핵심 텍스트 (5자 이내)",
            "emphasis": true
        }},
        ...총 5개 씬
    ],
    "total_chars": 260,
    "estimated_seconds": 35,
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
    model: str = None
) -> Dict[str, Any]:
    """
    GPT-5.1 Responses API를 사용하여 쇼츠 대본 생성

    Args:
        celebrity: 연예인 이름
        issue_type: 이슈 유형
        news_title: 뉴스 제목
        news_summary: 뉴스 요약
        hook_text: 훅 문장
        silhouette_desc: 실루엣 특징 설명
        model: 사용할 GPT 모델 (기본: gpt-5.1)

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
    if model is None:
        model = DEFAULT_MODEL

    try:
        client = get_openai_client()

        user_prompt = SCRIPT_GENERATION_PROMPT.format(
            celebrity=celebrity,
            issue_type=issue_type,
            news_title=news_title,
            news_summary=news_summary,
            hook_text=hook_text,
            silhouette_desc=silhouette_desc,
        )

        system_prompt = "당신은 연예 뉴스 쇼츠 전문 작가입니다. 반드시 JSON 형식으로만 응답하세요. 다른 텍스트 없이 순수 JSON만 출력하세요."

        print(f"[SHORTS] GPT-5.1 대본 생성 중: {celebrity} - {issue_type}")

        # GPT-5.1 Responses API 호출
        response = client.responses.create(
            model=model,
            input=[
                {
                    "role": "system",
                    "content": [{"type": "input_text", "text": system_prompt}]
                },
                {
                    "role": "user",
                    "content": [{"type": "input_text", "text": user_prompt}]
                }
            ],
            temperature=0.7
        )

        # 응답 추출
        result_text = extract_gpt51_response(response)

        if not result_text:
            raise ValueError("GPT-5.1에서 빈 응답을 받았습니다")

        # 안전한 JSON 파싱 (마크다운 제거 + 수정 시도)
        result = safe_json_parse(result_text)

        # 전체 대본 조합
        full_script = "\n".join([
            scene["narration"] for scene in result.get("scenes", [])
        ])

        # 비용 계산 (GPT-5.1 기준)
        # usage 정보가 있으면 사용, 없으면 추정
        if hasattr(response, 'usage') and response.usage:
            input_tokens = getattr(response.usage, 'input_tokens', 0) or getattr(response.usage, 'prompt_tokens', 0)
            output_tokens = getattr(response.usage, 'output_tokens', 0) or getattr(response.usage, 'completion_tokens', 0)
        else:
            # 대략적 추정 (한글 기준)
            input_tokens = len(system_prompt + user_prompt) // 2
            output_tokens = len(result_text) // 2

        cost = (input_tokens * GPT51_COSTS["input"] + output_tokens * GPT51_COSTS["output"]) / 1000

        print(f"[SHORTS] GPT-5.1 대본 생성 완료: {len(full_script)}자, ${cost:.4f}")

        # YouTube SEO 데이터 추출
        youtube_seo = result.get("youtube_seo", {})
        if not youtube_seo:
            # 기본값 생성
            youtube_seo = {
                "title": result.get("title", f"{celebrity} 이슈"),
                "description": f"{result.get('title', celebrity)}\n\n#Shorts #{celebrity}",
                "tags": [celebrity, issue_type, "쇼츠", "연예뉴스"] + result.get("hashtags", [])[:10],
            }

        # 썸네일 데이터 추출
        thumbnail = result.get("thumbnail", {})
        if not thumbnail:
            # 기본값 생성
            thumbnail = {
                "hook_text": result.get("title", celebrity)[:20],
                "style": issue_type if issue_type in ["논란", "열애", "성과", "자랑"] else "default",
                "image_prompt": f"YouTube Shorts thumbnail, dramatic black silhouette of {silhouette_desc}, spotlight, 9:16 vertical",
            }

        return {
            "ok": True,
            "title": result.get("title", f"{celebrity} 이슈"),
            "scenes": result.get("scenes", []),
            "full_script": full_script,
            "total_chars": len(full_script),
            "hashtags": result.get("hashtags", []),
            "youtube_seo": youtube_seo,
            "thumbnail": thumbnail,
            "bgm": result.get("bgm", {"mood": "dramatic", "reason": "기본값"}),
            "highlight_keywords": result.get("highlight_keywords", []),
            "comment_trigger": result.get("comment_trigger", {}),
            "cost": round(cost, 4),
            "model": model,
        }

    except json.JSONDecodeError as e:
        print(f"[SHORTS] JSON 파싱 실패: {e}")
        print(f"[SHORTS] 원본 응답: {result_text[:500] if 'result_text' in dir() else 'N/A'}")
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

    - 씬1 (훅): 연예인 실루엣 포함 (영상당 유일한 실루엣!)
    - 나머지: 대본 내용에 맞는 배경 이미지 (실루엣 없음)

    Args:
        scenes: GPT가 생성한 씬 목록
        celebrity: 연예인 이름
        silhouette_desc: 실루엣 특징 설명

    Returns:
        강화된 씬 목록
    """
    enhanced_scenes = []
    total_scenes = len(scenes)

    for scene in scenes:
        scene_num = scene.get("scene_number", 1)
        original_prompt = scene.get("image_prompt", "")
        narration = scene.get("narration", "")
        is_last_scene = (scene_num == total_scenes)

        # 9:16 비율 강제
        aspect_instruction = (
            f"CRITICAL: Generate image in EXACT 9:16 VERTICAL PORTRAIT aspect ratio. "
            f"Target dimensions: {VIDEO_WIDTH}x{VIDEO_HEIGHT} pixels. "
            f"This is MANDATORY for YouTube Shorts format."
        )

        if scene_num == 1:
            # 첫 씬 (훅): 영상에서 유일하게 실루엣 포함
            enhanced_prompt = f"""
{aspect_instruction}

{original_prompt}

IMPORTANT - HOOK SCENE (ONLY silhouette in this video):
- Include a dramatic black silhouette of {silhouette_desc}
- Spotlight from above casting long shadow
- NO facial features visible - only dark shadow outline
- URGENT, BREAKING NEWS atmosphere
- Red/orange dramatic lighting
- Large empty space at top and bottom for Korean text overlay
- 4K quality, cinematic lighting, high contrast
"""
        elif is_last_scene:
            # 마지막 씬: 결론 분위기 (실루엣 없음!)
            enhanced_prompt = f"""
{aspect_instruction}

{original_prompt}

IMPORTANT - CONCLUSION SCENE:
- NO silhouettes, NO people, NO human figures
- Create atmosphere matching the conclusion: "{narration[:50]}..."
- Symbolic imagery representing the story's ending
- Professional, polished look
- Large empty space for Korean text overlay
- 4K quality, cinematic composition
"""
        else:
            # 중간 씬: 대본 내용에 맞는 배경 (실루엣 없음!)
            enhanced_prompt = f"""
{aspect_instruction}

{original_prompt}

IMPORTANT - CONTENT SCENE:
- NO silhouettes, NO people, NO human figures
- Visualize this narration: "{narration[:50]}..."
- Focus on objects, places, or abstract concepts from the story
- Dynamic, engaging visuals to prevent viewer drop-off
- Large empty space for Korean text overlay
- 4K quality, cinematic composition
- Korean news broadcast style atmosphere
"""

        scene["image_prompt_enhanced"] = enhanced_prompt.strip()
        enhanced_scenes.append(scene)

    return enhanced_scenes


def generate_complete_shorts_package(
    news_data: Dict[str, Any],
    model: str = None
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
    # person 필드 우선, 없으면 celebrity 호환
    person = news_data.get("person", news_data.get("celebrity", ""))

    script_result = generate_shorts_script(
        celebrity=person,  # 함수 파라미터는 celebrity로 유지 (내부 사용)
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
        celebrity=person,
        silhouette_desc=news_data.get("silhouette_desc", ""),
    )

    return {
        "ok": True,
        "title": script_result.get("title"),
        "full_script": script_result.get("full_script"),
        "scenes": enhanced_scenes,
        "total_chars": script_result.get("total_chars"),
        "hashtags": script_result.get("hashtags", []),
        "youtube_seo": script_result.get("youtube_seo", {}),
        "thumbnail": script_result.get("thumbnail", {}),
        "bgm": script_result.get("bgm", {}),
        "highlight_keywords": script_result.get("highlight_keywords", []),
        "comment_trigger": script_result.get("comment_trigger", {}),
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
