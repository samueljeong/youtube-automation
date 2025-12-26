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
당신은 **댓글 1000개 쇼츠 전문가**입니다.
조회수보다 **댓글**이 중요합니다. 시청자가 "나도 한마디 해야겠다"고 느끼게 만드세요.

## 뉴스 정보
- 연예인: {celebrity}
- 이슈: {issue_type}
- 제목: {news_title}
- 요약: {news_summary}
- 훅 참고: {hook_text}
- 실루엣: {silhouette_desc}

## 🔥 댓글이 달리는 5가지 기법 (필수!)

### 1. 편가르기 (가장 강력!)
시청자에게 A vs B 선택을 강요하세요.
- "{celebrity} 잘못 vs 상대방이 예민. 어느 쪽?"
- "이건 문제다 vs 별거 아니다. 뭐라고 봄?"
- "용서된다 vs 절대 안 된다. 댓글로!"

### 2. 도발적 한마디
살짝 논쟁을 유발하는 말로 반응을 끌어내세요.
- "솔직히 이건 좀 심한 거 아니야?"
- "근데 진짜 잘못한 거 맞아?"
- "나만 이상하게 느껴?"

### 3. 예측 대결
미래를 맞춰보게 하세요.
- "복귀할까? 못 할까?"
- "사과할 것 같아? 버틸 것 같아?"
- "3개월 후 어떻게 될까?"

### 4. 경험 공유 유도
개인 경험을 끌어내세요.
- "직장에서 이런 일 당해본 사람?"
- "비슷한 경험 있으면 댓글!"
- "나만 이런 상사 있었어?"

### 5. 강렬한 단정 (반박 유도)
확신에 찬 말로 반박을 유도하세요.
- "이건 무조건 잘못이다."
- "변명의 여지가 없다."
- "이번엔 다르다."

## ⚡ 문장 규칙

### 길이 (중요!)
- **한 문장 = 최대 12자**
- **씬당 4-6문장** (많이 써야 30초 됨!)
- **총 300-400자** (이게 30-40초)
- 마침표(.) 많이. 끊어서. 강렬하게.

### 예시
❌ "코미디언 박나래가 매니저에게 갑질 의혹을 받았다는 보도가 나왔습니다." (39자, 1문장)
✅ "박나래. 갑질. 터졌다. 매니저한테. 폭언했대. 진짜래." (27자, 6문장)

## 🎯 씬 구성 (5개, 총 30-40초, 총 300-400자)

### 씬1 (훅, 3초, 30자) - 스크롤 멈춤
- **{celebrity} + 핵심어 + 단정** (4-5문장)
- "박나래. 갑질. 터졌다. 이번엔 진짜다. 큰일났다."
- ❌ 금지: "여러분", "이게 사실이라면", "충격적인"

### 씬2 (상황, 8초, 80자) - 팩트만
- 육하원칙. 짧게. (5-6문장)
- "매니저에게 폭언. 부당대우. 제보 폭주. 녹음도 있대. 증거가 쌓인다. 심각하다."

### 씬3 (핵심, 10초, 100자) - 제일 센 내용
- 숫자, 인용문 활용 (5-6문장)
- "불법 시술 의혹까지. 주사 놔줬대. 면허도 없이. 이건 범죄다. 선 넘었다. 진짜야 이거."

### 씬4 (댓글 유도, 12초, 120자) - 🔥 가장 중요!
- **반드시 편가르기 + 경험 질문** (5-6문장)
- "{celebrity} 잘못이다. vs 매니저가 예민하다. 솔직히 어느 쪽이야? 댓글로. 비슷한 상사 있었어? 말해봐."

### 씬5 (마무리, 7초, 70자) - 강렬하게 끝
- 예측 + 단정 (4-5문장)
- "복귀? 쉽지 않다. 이미지 타격 크다. 3개월 뒤 어떨까? 지켜보자."
- ❌ 씬1 반복 금지

## 📝 체크리스트
1. ☐ **총 글자수 300-400자?** (가장 중요!)
2. ☐ 씬당 4-6문장?
3. ☐ 씬4에 편가르기/질문 있음?
4. ☐ 모든 문장 12자 이하?
5. ☐ "여러분" 사용 안 함?

## 출력 (JSON만!)
{{
    "title": "쇼츠 제목 (20자)",
    "engagement_score": 9,
    "engagement_tactics": ["편가르기", "도발"],
    "comment_bait": {{
        "scene": 4,
        "type": "versus",
        "text": "{celebrity} 잘못 vs 상대방 예민. 어느 쪽?"
    }},
    "provocative_line": "솔직히 이건 좀 심하지 않아?",
    "predicted_comments": ["{celebrity} 잘못", "상대방이 예민", "둘 다 문제"],
    "bgm": {{
        "mood": "tense",
        "reason": "논란"
    }},
    "highlight_keywords": ["갑질", "폭언"],
    "youtube_seo": {{
        "title": "YouTube 제목 (50자)",
        "description": "설명 + 해시태그",
        "tags": ["태그들"]
    }},
    "thumbnail": {{
        "hook_text": "갑질\\n논란",
        "style": "논란",
        "image_prompt": "썸네일 프롬프트"
    }},
    "scenes": [
        {{
            "scene_number": 1,
            "duration": "0-3초",
            "narration": "{celebrity}. 갑질. 터졌다. 이번엔 진짜다. 큰일났다.",
            "image_prompt": "이미지 프롬프트",
            "text_overlay": "갑질",
            "emphasis": true
        }},
        {{
            "scene_number": 2,
            "duration": "3-11초",
            "narration": "매니저에게 폭언. 부당대우. 제보 폭주. 녹음도 있대. 증거가 쌓인다. 심각하다.",
            "image_prompt": "이미지 프롬프트",
            "text_overlay": "폭언",
            "emphasis": false
        }},
        {{
            "scene_number": 3,
            "duration": "11-21초",
            "narration": "불법 시술 의혹까지. 주사 놔줬대. 면허도 없이. 이건 범죄다. 선 넘었다. 진짜야 이거.",
            "image_prompt": "이미지 프롬프트",
            "text_overlay": "불법시술",
            "emphasis": true
        }},
        {{
            "scene_number": 4,
            "duration": "21-33초",
            "narration": "{celebrity} 잘못이다. vs 매니저가 예민하다. 솔직히 어느 쪽이야? 댓글로. 비슷한 상사 있었어? 말해봐.",
            "image_prompt": "이미지 프롬프트",
            "text_overlay": "어느 쪽?",
            "emphasis": true
        }},
        {{
            "scene_number": 5,
            "duration": "33-40초",
            "narration": "복귀? 쉽지 않다. 이미지 타격 크다. 3개월 뒤 어떨까? 지켜보자.",
            "image_prompt": "이미지 프롬프트",
            "text_overlay": "복귀?",
            "emphasis": false
        }}
    ],
    "total_chars": 350,
    "estimated_seconds": 38,
    "hashtags": ["#{celebrity}", "#갑질", "#연예뉴스"]
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
