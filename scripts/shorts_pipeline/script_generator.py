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
당신은 **리텐션 85% 쇼츠 전문가**입니다.

## 🎯 목표 우선순위
1. **리텐션 85%+** - 끝까지 보게 만들기 (가장 중요!)
2. **댓글 유도** - "나도 한마디" 느끼게
3. **반복 시청** - 다시 보고 싶게

## 📊 YouTube 알고리즘 핵심
- 70% 스와이프 → 노출 중단
- 85%+ 시청률 → 추천 시작
- 100%+ APV (반복시청) → 바이럴

## ⚠️ 말투 규칙 (필수!)
- **존댓말(~요, ~습니다)로 통일** - 반말 절대 금지!
- 처음부터 끝까지 일관된 말투 유지
- ❌ 금지: "~야", "~해", "~봐", "~거든", "~지?"
- ✅ 사용: "~예요", "~해요", "~보세요", "~거든요", "~죠?"
- 예시:
  - ❌ "이게 다가 아니야" → ✅ "이게 다가 아니에요"
  - ❌ "진짜는 지금부터야" → ✅ "진짜는 지금부터예요"
  - ❌ "어느 쪽이야?" → ✅ "어느 쪽이에요?"
  - ❌ "댓글로 알려줘" → ✅ "댓글로 알려주세요"

## 뉴스 정보
- 연예인: {celebrity}
- 이슈: {issue_type}
- 제목: {news_title}
- 요약: {news_summary}
- 훅 참고: {hook_text}
- 실루엣: {silhouette_desc}

## 💬 실제 댓글 분석 (대본에 반영!)
{comment_section}

## 🔒 리텐션 높이는 구조 (필수!)

### 씬별 이탈 방지 전략
- **씬1**: 스크롤 멈춤 → "뭐지?" 궁금증
- **씬2**: 이탈 방지 → "더 있어요?" 예고
- **씬3**: 클라이맥스 → "대박" 충격
- **씬4**: 참여 유도 → "나도 한마디"
- **씬5**: 마무리 → "어떻게 될까요" 여운

### 이탈 방지 문구 (씬2-3에 필수!)
- "근데 여기서 끝이 아니에요."
- "진짜는 지금부터예요."
- "이게 다가 아니거든요."

## 🔥 댓글이 달리는 5가지 기법

### 1. 편가르기 (가장 강력!)
시청자에게 A vs B 선택을 강요하세요.
- "{celebrity} 잘못 vs 상대방이 예민. 어느 쪽이에요?"
- "이건 문제다 vs 별거 아니다. 어떻게 생각하세요?"
- "용서된다 vs 절대 안 된다. 댓글로 알려주세요!"

### 2. 도발적 한마디
살짝 논쟁을 유발하는 말로 반응을 끌어내세요.
- "솔직히 이건 좀 심한 거 아니에요?"
- "근데 진짜 잘못한 거 맞아요?"
- "저만 이상하게 느끼나요?"

### 3. 예측 대결
미래를 맞춰보게 하세요.
- "복귀할 수 있을까요? 못 할까요?"
- "사과할 것 같아요? 버틸 것 같아요?"
- "3개월 후 어떻게 될까요?"

### 4. 경험 공유 유도
개인 경험을 끌어내세요.
- "직장에서 이런 일 당해보신 분 계세요?"
- "비슷한 경험 있으시면 댓글로 알려주세요!"
- "저만 이런 경험 있나요?"

### 5. 강렬한 단정 (반박 유도)
확신에 찬 말로 반박을 유도하세요.
- "이건 무조건 잘못이에요."
- "변명의 여지가 없어요."
- "이번엔 달라요."

## ⚡ 문장 규칙 (TTS + 자막 자연스럽게!)

### 길이
- **한 문장 = 15-25자** (TTS가 자연스럽게 읽을 수 있는 길이)
- **씬당 3-4문장** (호흡 있게)
- **총 250-350자** (이게 30-40초)

### TTS 스타일 (중요!)
- 뉴스 앵커가 읽는 것처럼 자연스럽게
- 마침표 사이에 의미 있는 문장 단위로
- 끊어 읽기는 TTS가 자동으로 함

### 자막 친화적 문장 (중요!)
- **한 문장 = 하나의 완결된 의미** (자막으로 보여도 이해 가능해야 함)
- 마침표 뒤에 바로 다음 문장 시작하지 말 것 (자막이 어색하게 끊김)
- ❌ "산다는 거죠. 근데 이게 다가" (마침표 뒤에 이어지는 문장)
- ✅ 문장마다 독립적인 의미 전달

### 예시
❌ "박나래. 갑질. 터졌다. 매니저한테." (로봇 같음, TTS 부자연스러움)
❌ "사실상 나혼산 나오려고 산다는 거죠. 근데 이게 다가 아니에요." (마침표 뒤 "근데"로 시작 - 자막 끊김)
✅ "박나래 갑질 의혹이 터졌습니다." (문장1)
✅ "매니저한테 폭언했다는 거예요." (문장2)
✅ "근데 이게 끝이 아니에요." (문장3 - 독립적)

## 🎯 씬 구성 (5개, 총 30-40초, 총 250-350자)

### 씬1 (훅, 3초, 40자) - 🔒 스크롤 멈춤
- **{celebrity} + 핵심어** (2-3문장, 자연스럽게)
- "박나래 갑질 의혹 터졌습니다. 이번엔 진짜 큰일났어요."
- ❌ 금지: "여러분", "이게 사실이라면", "충격적인"

### 씬2 (상황, 8초, 60자) - 🔒 이탈 방지!
- 팩트 + **"근데 여기서 끝이 아니에요"** (2-3문장)
- "매니저한테 폭언하고 부당대우 했대요. 제보가 쏟아지고 있어요. 근데 이게 끝이 아니에요."

### 씬3 (핵심, 10초, 80자) - 🔥 클라이맥스
- 가장 충격적인 내용 + **"진짜는 지금부터예요"** (2-3문장)
- "진짜 문제는 이거예요. 불법 시술 의혹까지 나왔어요. 면허도 없이 주사 놨다는 거예요. 이건 선 넘었죠."

### 씬4 (댓글 유도, 12초, 100자) - 💬 참여 유도
- **편가르기 + 경험 질문** (3-4문장)
- "이건 {celebrity} 잘못일까요, 아니면 상대방이 예민한 걸까요? 솔직히 어느 쪽이에요? 비슷한 경험 있으시면 댓글로 알려주세요."

### 씬5 (마무리, 7초, 50자) - 🔄 여운 + 반복시청 유도
- 예측 + 미해결 궁금증 (2-3문장)
- "복귀할 수 있을까요? 반전이 있을 수도 있어요. 3개월 뒤 어떻게 될지 지켜봐요."
- ❌ 씬1 반복 금지

## 📝 체크리스트
1. ☐ **총 글자수 250-350자?**
2. ☐ **씬2에 "이게 다가 아니에요" 류 이탈 방지 문구?** (리텐션!)
3. ☐ **씬3에 "진짜 문제는 이거예요" 류 클라이맥스?** (리텐션!)
4. ☐ 씬4에 편가르기/질문 있음?
5. ☐ **문장이 TTS로 읽기 자연스러움?** (15-25자)
6. ☐ "여러분" 사용 안 함?

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
    "retention_hooks": {{
        "scene2": "근데 이게 다가 아니에요",
        "scene3": "진짜는 지금부터예요",
        "scene5": "반전 있을 수도 있어요"
    }},
    "scenes": [
        {{
            "scene_number": 1,
            "duration": "0-3초",
            "narration": "{celebrity} 갑질 의혹 터졌습니다. 이번엔 진짜 큰일났어요.",
            "image_prompt": "이미지 프롬프트",
            "text_overlay": "갑질",
            "emphasis": true
        }},
        {{
            "scene_number": 2,
            "duration": "3-11초",
            "narration": "매니저한테 폭언하고 부당대우 했대요. 제보가 쏟아지고 있어요. 근데 이게 끝이 아니에요.",
            "image_prompt": "이미지 프롬프트",
            "text_overlay": "폭언",
            "emphasis": false
        }},
        {{
            "scene_number": 3,
            "duration": "11-21초",
            "narration": "진짜 문제는 이거예요. 불법 시술 의혹까지 나왔어요. 면허도 없이 주사 놨다는 거예요. 이건 선 넘었죠.",
            "image_prompt": "이미지 프롬프트",
            "text_overlay": "불법시술",
            "emphasis": true
        }},
        {{
            "scene_number": 4,
            "duration": "21-33초",
            "narration": "이건 {celebrity} 잘못일까요, 아니면 상대방이 예민한 걸까요? 솔직히 어느 쪽이에요? 비슷한 경험 있으시면 댓글로 알려주세요.",
            "image_prompt": "이미지 프롬프트",
            "text_overlay": "어느 쪽?",
            "emphasis": true
        }},
        {{
            "scene_number": 5,
            "duration": "33-40초",
            "narration": "복귀할 수 있을까요? 반전이 있을 수도 있어요. 3개월 뒤 어떻게 될지 지켜봐요.",
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


def _build_comment_section(script_hints: Optional[Dict[str, Any]]) -> str:
    """
    script_hints를 프롬프트용 댓글 섹션으로 변환

    Args:
        script_hints: generate_script_hints() 결과물
            {
                "debate_topic": "갑질이다 vs 예민하다",
                "pro_arguments": ["선 넘었다", ...],
                "con_arguments": ["예민하다", ...],
                "hot_phrases": ["선 넘었다", ...],
                "suggested_scene4": "댓글 보니까...",
            }

    Returns:
        프롬프트에 삽입할 텍스트
    """
    if not script_hints or not any([
        script_hints.get("debate_topic"),
        script_hints.get("hot_phrases"),
        script_hints.get("pro_arguments"),
    ]):
        return """(댓글 데이터 없음 - 일반적인 댓글 유도 문구 사용)"""

    lines = []

    # 논쟁 주제
    if script_hints.get("debate_topic"):
        lines.append(f"🔥 **실제 논쟁 주제**: {script_hints['debate_topic']}")

    # 핫한 문구
    if script_hints.get("hot_phrases"):
        phrases = ", ".join([f'"{p}"' for p in script_hints["hot_phrases"][:5]])
        lines.append(f"💬 **인기 댓글 표현**: {phrases}")
        lines.append("   → 이 표현들을 대본에 자연스럽게 녹여주세요!")

    # 찬성 의견
    if script_hints.get("pro_arguments"):
        args = " / ".join(script_hints["pro_arguments"][:3])
        lines.append(f"👎 **비판 의견**: {args}")

    # 반대 의견
    if script_hints.get("con_arguments"):
        args = " / ".join(script_hints["con_arguments"][:3])
        lines.append(f"👍 **옹호 의견**: {args}")

    # 씬4 제안
    if script_hints.get("suggested_scene4"):
        lines.append(f"✨ **씬4 추천 멘트**: \"{script_hints['suggested_scene4']}\"")

    lines.append("")
    lines.append("⚡ **중요**: 위 실제 댓글 표현을 활용해서 시청자가 '나도 한마디!'하고 싶게 만드세요!")

    return "\n".join(lines)


def generate_shorts_script(
    celebrity: str,
    issue_type: str,
    news_title: str,
    news_summary: str,
    hook_text: str,
    silhouette_desc: str,
    model: str = None,
    script_hints: Optional[Dict[str, Any]] = None,
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
        script_hints: 실제 댓글 기반 힌트 (news_scorer에서 생성)

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

        # 댓글 섹션 생성
        comment_section = _build_comment_section(script_hints)

        user_prompt = SCRIPT_GENERATION_PROMPT.format(
            celebrity=celebrity,
            issue_type=issue_type,
            news_title=news_title,
            news_summary=news_summary,
            hook_text=hook_text,
            silhouette_desc=silhouette_desc,
            comment_section=comment_section,
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
            "silhouette_desc": "...",
            "script_hints": {...}  # 옵션: 실제 댓글 기반 힌트
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

    # 실제 댓글 기반 힌트 (news_scorer에서 생성)
    script_hints = news_data.get("script_hints")

    script_result = generate_shorts_script(
        celebrity=person,  # 함수 파라미터는 celebrity로 유지 (내부 사용)
        issue_type=news_data.get("issue_type", ""),
        news_title=news_data.get("news_title", ""),
        news_summary=news_data.get("news_summary", ""),
        hook_text=news_data.get("hook_text", ""),
        silhouette_desc=news_data.get("silhouette_desc", ""),
        model=model,
        script_hints=script_hints,
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
