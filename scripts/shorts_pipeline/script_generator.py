"""
쇼츠 파이프라인 - 대본 및 이미지 프롬프트 생성

GPT-5.1 Responses API를 사용하여:
1. 60초 쇼츠 대본 생성 (9개 씬)
2. 씬별 이미지 프롬프트 생성 (실루엣 포함)

Note: 이 파일은 레거시 코드입니다.
      새 구현은 agents/script_agent.py를 사용하세요.
"""

from typing import Dict, Any, List, Optional

from .config import (
    DEFAULT_SCENE_COUNT,
    TARGET_SCRIPT_LENGTH,
    BACKGROUND_STYLES,
    SILHOUETTE_TEMPLATE,
    BACKGROUND_ONLY_TEMPLATE,
    VIDEO_WIDTH,
    VIDEO_HEIGHT,
)

# 공통 유틸리티 임포트
from .agents.utils import (
    GPT51_COSTS,
    get_openai_client,
    extract_gpt51_response,
    safe_json_parse,
    repair_json,
)


# 기본 모델
DEFAULT_MODEL = "gpt-5.1"


SCRIPT_GENERATION_PROMPT = """
당신은 **1000만 조회수 쇼츠 전문가**입니다.
시청자의 스크롤을 멈추고, 끝까지 보게 만드는 대본을 작성하세요.

## 뉴스 정보
- 연예인: {celebrity}
- 이슈: {issue_type}
- 제목: {news_title}
- 요약: {news_summary}
- 훅 참고: {hook_text}
- 실루엣: {silhouette_desc}

## ⚡ 핵심 규칙: 짧게! 끊어서! 강렬하게!

### 문장 길이 (가장 중요!)
- **한 문장 = 최대 12자**
- 긴 문장은 끊어서 2-3개로 분리
- 마침표(.) 많이 사용

### 좋은 예시 vs 나쁜 예시
❌ 나쁨: "코미디언 박나래가 매니저에게 갑질 의혹을 받았다는 보도가 나왔습니다." (39자)
✅ 좋음: "박나래. 갑질 의혹. 터졌습니다." (16자, 3문장)

❌ 나쁨: "이게 사실이라면, 연예계가 뒤집힐 수 있습니다." (25자)
✅ 좋음: "박나래 논란. 이번엔 다릅니다." (15자)

❌ 나쁨: "온라인에서는 비판과 우려의 목소리가 동시에 나오고 있습니다." (31자)
✅ 좋음: "팬들 반응? 갈렸습니다. 완전히." (16자)

## 🎯 씬별 가이드 (5개 씬, 총 30-40초)

### 씬1 (훅, 3초) - 스크롤 멈추기
- **{celebrity} 이름 + 핵심 단어 + 단정**
- 예: "박나래. 갑질. 터졌습니다."
- 예: "손흥민. 부상. 시즌 아웃?"
- ❌ 금지: "이게 사실이라면", "충격", "여러분"

### 씬2 (상황, 9초) - 무슨 일?
- 육하원칙으로 간단히
- 2-3개 짧은 문장
- 예: "매니저에게 갑질. 폭언까지. 제보가 쏟아졌습니다."

### 씬3 (핵심, 10초) - 가장 충격적인 내용
- 구체적 팩트 제시
- 숫자, 날짜, 인용문 활용
- 예: "불법 시술 의혹까지. 10대 뉴스 선정됐습니다."

### 씬4 (여론, 10초) - 반응 + 댓글유도
- 팬/대중 반응
- **반드시 댓글 유도 문구 포함**
- 예: "팬들? 갈렸습니다. 여러분 생각은요?"

### 씬5 (마무리, 8초) - 앞으로는?
- 향후 전망
- ❌ 훅 반복 금지!
- 예: "해명? 아직 없습니다. 지켜봐야 할 것 같습니다."

## 📝 작성 체크리스트
1. ☐ 모든 문장이 12자 이내인가?
2. ☐ 씬당 2-4개 문장으로 구성했는가?
3. ☐ 씬4에 댓글 유도가 있는가?
4. ☐ 씬5가 씬1과 다른 문장인가?
5. ☐ 총 글자수가 150-200자인가?

## 출력 (JSON만!)
{{
    "title": "쇼츠 제목 (20자, 이모지 1개)",
    "hook_strength": 8,
    "no_repetition_check": "예",
    "comment_trigger": {{
        "scene": 4,
        "type": "opinion",
        "text": "실제 삽입된 문구"
    }},
    "fact_sources": ["사실 1", "사실 2"],
    "bgm": {{
        "mood": "tense",
        "reason": "갑질 논란이므로"
    }},
    "highlight_keywords": ["갑질", "의혹"],
    "youtube_seo": {{
        "title": "YouTube 제목 (50자)",
        "description": "설명 + 해시태그",
        "tags": ["태그들"]
    }},
    "thumbnail": {{
        "hook_text": "갑질\\n의혹",
        "style": "논란",
        "image_prompt": "썸네일 프롬프트"
    }},
    "scenes": [
        {{
            "scene_number": 1,
            "duration": "0-3초",
            "narration": "박나래. 갑질. 터졌습니다.",
            "image_prompt": "이미지 프롬프트",
            "text_overlay": "갑질",
            "emphasis": true
        }},
        {{
            "scene_number": 2,
            "duration": "3-12초",
            "narration": "매니저에게 폭언. 부당대우까지. 제보가 터졌습니다.",
            "image_prompt": "이미지 프롬프트",
            "text_overlay": "폭언",
            "emphasis": false
        }},
        {{
            "scene_number": 3,
            "duration": "12-22초",
            "narration": "여기서 끝이 아닙니다. 불법 시술 의혹까지. 10대 뉴스 선정됐습니다.",
            "image_prompt": "이미지 프롬프트",
            "text_overlay": "불법시술",
            "emphasis": true
        }},
        {{
            "scene_number": 4,
            "duration": "22-32초",
            "narration": "팬들 반응? 완전히 갈렸습니다. 여러분 생각은요?",
            "image_prompt": "이미지 프롬프트",
            "text_overlay": "의견",
            "emphasis": false
        }},
        {{
            "scene_number": 5,
            "duration": "32-40초",
            "narration": "해명은 아직. 조사 결과 지켜봐야 합니다.",
            "image_prompt": "이미지 프롬프트",
            "text_overlay": "지켜봐야",
            "emphasis": false
        }}
    ],
    "total_chars": 180,
    "estimated_seconds": 35,
    "hashtags": ["#박나래", "#갑질", "#연예뉴스"]
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

⚠️ CRITICAL: ABSOLUTELY NO TEXT, NO LETTERS, NO WORDS, NO WATERMARKS, NO LOGOS on the image!
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

⚠️ CRITICAL: ABSOLUTELY NO TEXT, NO LETTERS, NO WORDS, NO WATERMARKS, NO LOGOS on the image!
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

⚠️ CRITICAL: ABSOLUTELY NO TEXT, NO LETTERS, NO WORDS, NO WATERMARKS, NO LOGOS on the image!
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
