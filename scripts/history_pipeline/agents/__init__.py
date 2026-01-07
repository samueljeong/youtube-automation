"""
한국사 파이프라인 - 에이전트 모듈

## 에이전트 팀 구성

### 기획 에이전트 (PlannerAgent)
- 역할: 40년간 기획을 해온 전문가
- 특징: 하위 에이전트들을 잘 컨트롤해서 문제가 없게 만듦
- 책임: 에피소드 구조 설계, 워크플로우 관리, 품질 보증

### 대본 에이전트 (ScriptAgent)
- 역할: 세계에서 가장 유명한 작가
- 특징: 사람들이 좋아할 만한 톤과 어체로 대본 작성
- 책임: 12,000~15,000자 대본 작성, 초반 웹서칭으로 방향 정립

### 사실 검증 에이전트 (FactCheckAgent) - 신규
- 역할: 역사학 박사 출신의 팩트체커
- 특징: AI 허구(hallucination) 철저히 탐지
- 책임: 역사적 사실 검증, 연도/인물/사건 정확성 확인

### 어투/톤 검증 에이전트 (ToneReviewAgent) - 신규
- 역할: 방송작가 출신 톤/문체 전문가
- 특징: 40-60대 대상 어투 지침 준수 여부 검증
- 책임: TTS 적합성, 종결어미, 문체 일관성 검사

### 대본 리뷰 에이전트 (ReviewAgent) - 기존
- 역할: 깐깐하고 철저한 검수자
- 특징: 대충 넘어가지 않고 문제를 파악해서 개선
- 책임: 대본 품질 검수, 피드백 생성, 승인/반려 결정

### 이미지 에이전트 (ImageAgent)
- 역할: 텍스트를 이미지화하는 전문가
- 특징: 이미지만 봐도 내용이 이해될 수 있게 함
- 책임: 씬별 이미지 프롬프트 생성, 썸네일 가이드

### 유튜브 에이전트 (YouTubeAgent)
- 역할: SEO 전문가이자 YouTube 알고리즘 마스터
- 특징: 시청자의 클릭을 유도하는 메타데이터 생성
- 책임: SEO 최적화된 제목, 설명, 태그, 썸네일 텍스트 생성

### 코드 리뷰 에이전트 (CodeReviewAgent)
- 역할: 기획 에이전트를 감시하는 최상위 감시자
- 특징: 어떤 코드가 작성되도 커밋 전에 검수
- 책임: 전체 파이프라인 검수, 오류 없는 커밋 보장

## 워크플로우

```
┌─────────────────────────────────────────────────────────────┐
│                    CodeReviewAgent (감시)                   │
│                          ↓ 검수                             │
│  ┌───────────────────────────────────────────────────────┐  │
│  │              PlannerAgent (총괄 기획)                  │  │
│  │                    ↓ 지시                              │  │
│  │  ┌─────────────────────────────────────────────────┐  │  │
│  │  │                                                  │  │  │
│  │  │  ScriptAgent ──→ FactCheckAgent ──→ ToneReviewAgent  │  │
│  │  │   (대본 작성)    (사실 검증)       (어투/톤 검증)     │  │
│  │  │                       ↓                               │  │
│  │  │              ReviewAgent ──→ ImageAgent               │  │
│  │  │             (품질 검수)     (이미지 생성)             │  │
│  │  │                       ↓                               │  │
│  │  │                YouTubeAgent                           │  │
│  │  │               (SEO 메타데이터)                        │  │
│  │  │                                                  │  │  │
│  │  └─────────────────────────────────────────────────┘  │  │
│  └───────────────────────────────────────────────────────┘  │
│                          ↓ 최종 검수                        │
│                    커밋 승인/거부                           │
└─────────────────────────────────────────────────────────────┘
```

## 사용법

```python
from scripts.history_pipeline.agents import (
    EpisodeContext,
    PlannerAgent,
    ScriptAgent,
    ReviewAgent,
    ImageAgent,
    CodeReviewAgent,
    run_full_pipeline,
)

# 컨텍스트 생성
context = EpisodeContext(
    episode_id="ep018",
    episode_number=18,
    era_name="통일신라",
    era_episode=4,
    title="9주 5소경, 통일신라의 행정개혁",
    topic="신라의 지방 행정 체계",
)

# 전체 파이프라인 실행
result = run_full_pipeline(context)

if result["success"]:
    print("파이프라인 완료!")
    print(f"대본: {len(context.script)}자")
    print(f"이미지: {len(context.image_prompts)}개")
else:
    print(f"실패: {result['error']}")
```
"""

# Base classes
from .base import (
    AgentStatus,
    AgentResult,
    EpisodeContext,
    BaseAgent,
)

# Agents
from .planner_agent import (
    PlannerAgent,
    plan_episode,
)

from .script_agent import (
    ScriptAgent,
    generate_script_guide,
    validate_script,
    validate_script_strict,  # 엄격 검증 (블로킹)
    SCRIPT_STYLE_GUIDE,
    SCENE_STRUCTURE,  # 씬 구조 템플릿
)

from .review_agent import (
    ReviewAgent,
    review_script,
    quick_review,
    review_script_strict,  # 엄격 검증 (블로킹)
    review_image_prompts_strict,  # 이미지 프롬프트 엄격 검증
    REVIEW_CRITERIA,
)

from .fact_check_agent import (
    FactCheckAgent,
    check_facts,
    check_facts_strict,  # 사실 검증 (블로킹)
    KOREAN_HISTORY_DATES,
)

from .tone_review_agent import (
    ToneReviewAgent,
    review_tone,
    review_tone_strict,  # 어투/톤 검증 (블로킹)
    INAPPROPRIATE_FOR_SENIOR,
    RECOMMENDED_ENDINGS,
)

from .image_agent import (
    ImageAgent,
    generate_image_guide,
    calculate_image_count,
    validate_image_prompts_strict,  # 엄격 검증 (블로킹)
    enhance_prompt_with_era_style,  # 시대 스타일 강화
    get_era_style,  # 시대 스타일 조회
    IMAGE_STYLE_GUIDE,
    ERA_STYLE_PRESETS,
)

from .youtube_agent import (
    YouTubeAgent,
    generate_youtube_metadata,
    quick_metadata,
    TITLE_TEMPLATES,
    ERA_KEYWORDS,
)

from .code_review_agent import (
    CodeReviewAgent,
    review_pipeline,
    can_commit,
    CODE_REVIEW_CHECKLIST,
)


def run_full_pipeline(context: EpisodeContext) -> dict:
    """
    전체 파이프라인 실행 (기획 → 대본 → 자동검수 → 이미지)

    ★ 모든 리뷰 에이전트(FactCheck, ToneReview, Review)가 자동 실행됩니다.
    검수 실패 시 파이프라인이 차단됩니다.

    Args:
        context: 에피소드 컨텍스트

    Returns:
        {
            "success": bool,
            "phases": dict,  # 각 단계별 결과
            "can_commit": bool,
            "error": str or None
        }
    """
    import asyncio

    phases = {}

    try:
        # Event loop 설정
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        # 1. 기획 단계
        planner = PlannerAgent()
        plan_result = loop.run_until_complete(planner.execute(context))
        phases["planning"] = {
            "success": plan_result.success,
            "duration": plan_result.duration,
        }

        if not plan_result.success:
            return {
                "success": False,
                "phases": phases,
                "can_commit": False,
                "error": f"기획 실패: {plan_result.error}"
            }

        # 기획 결과를 context에 저장
        context.brief = plan_result.data.get("brief")

        # 2. 대본 가이드 생성
        script_agent = ScriptAgent()
        script_result = loop.run_until_complete(script_agent.execute(context))
        phases["script_guide"] = {
            "success": script_result.success,
            "duration": script_result.duration,
        }

        if not script_result.success:
            return {
                "success": False,
                "phases": phases,
                "can_commit": False,
                "error": f"대본 가이드 생성 실패: {script_result.error}"
            }

        # ═══════════════════════════════════════════════════════════════
        # ★★★ 대본이 있는 경우: 자동 검수 체인 실행 ★★★
        # ═══════════════════════════════════════════════════════════════
        if context.script:
            print("\n" + "="*60)
            print("★ 자동 검수 체인 시작 (대본 → 사실검증 → 어투검증 → 품질검수)")
            print("="*60 + "\n")

            # ─────────────────────────────────────────────────────────────
            # 2-1. 대본 길이 검증 (블로킹)
            # ─────────────────────────────────────────────────────────────
            print("[1/4] ScriptAgent: 대본 길이 검증...")
            try:
                script_validation = validate_script_strict(context.script)
                phases["script_validation"] = {
                    "success": True,
                    "length": script_validation["length"],
                    "score": script_validation["score"],
                }
            except ValueError as e:
                phases["script_validation"] = {"success": False, "error": str(e)}
                return {
                    "success": False,
                    "phases": phases,
                    "can_commit": False,
                    "error": f"❌ 대본 길이 검증 실패: {str(e)}"
                }

            # ─────────────────────────────────────────────────────────────
            # 2-2. 사실 검증 (블로킹)
            # ─────────────────────────────────────────────────────────────
            print("[2/4] FactCheckAgent: 역사적 사실 검증...")
            try:
                fact_result = check_facts_strict(context.script, context.era_name)
                phases["fact_check"] = {
                    "success": True,
                    "total_issues": fact_result["total_issues"],
                    "summary": fact_result["summary"],
                }
            except ValueError as e:
                phases["fact_check"] = {"success": False, "error": str(e)}
                return {
                    "success": False,
                    "phases": phases,
                    "can_commit": False,
                    "error": f"❌ 사실 검증 실패: {str(e)}"
                }

            # ─────────────────────────────────────────────────────────────
            # 2-3. 어투/톤 검증 (블로킹)
            # ─────────────────────────────────────────────────────────────
            print("[3/4] ToneReviewAgent: 어투/톤 검증...")
            try:
                tone_result = review_tone_strict(context.script)
                phases["tone_review"] = {
                    "success": True,
                    "grade": tone_result["grade"],
                    "score": tone_result["score"],
                    "total_issues": tone_result["total_issues"],
                }
            except ValueError as e:
                phases["tone_review"] = {"success": False, "error": str(e)}
                return {
                    "success": False,
                    "phases": phases,
                    "can_commit": False,
                    "error": f"❌ 어투/톤 검증 실패: {str(e)}"
                }

            # ─────────────────────────────────────────────────────────────
            # 2-4. 종합 품질 검수
            # ─────────────────────────────────────────────────────────────
            print("[4/4] ReviewAgent: 종합 품질 검수...")
            review_agent = ReviewAgent()
            review_result = loop.run_until_complete(review_agent.execute(context, strict=True))
            phases["quality_review"] = {
                "success": review_result.success,
                "grade": review_result.data.get("grade") if review_result.success else None,
                "score": review_result.data.get("total_score") if review_result.success else 0,
                "passed": review_result.data.get("passed") if review_result.success else False,
            }

            # C/D등급이면 경고 (차단은 하지 않음 - 이미 위에서 검증됨)
            if review_result.success:
                grade = review_result.data.get("grade")
                if grade in ["C", "D"]:
                    print(f"  ⚠️ 품질 등급 {grade}: 개선 권장")
                    phases["quality_review"]["warning"] = review_result.data.get("feedback", {}).get("summary")
                else:
                    print(f"  ✓ 품질 등급 {grade}: 통과")

            print("\n" + "="*60)
            print("★ 자동 검수 체인 완료")
            print("="*60 + "\n")

        # ═══════════════════════════════════════════════════════════════
        # 3. 이미지 가이드 생성 (대본이 있는 경우만)
        # ═══════════════════════════════════════════════════════════════
        if context.script:
            print("[5/5] ImageAgent: 이미지 가이드 생성...")
            image_agent = ImageAgent()
            image_result = loop.run_until_complete(image_agent.execute(context))
            phases["image_guide"] = {
                "success": image_result.success,
                "image_count": image_result.data.get("image_count") if image_result.success else 0,
            }

            # 이미지 프롬프트 검증
            if image_result.success and context.image_prompts:
                try:
                    review_image_prompts_strict(
                        context.image_prompts,
                        context.era_name,
                        len(context.script)
                    )
                    phases["image_validation"] = {"success": True}
                except ValueError as e:
                    phases["image_validation"] = {"success": False, "warning": str(e)}
                    print(f"  ⚠️ 이미지 프롬프트 경고: {str(e)}")

        # 4. 최종 결과
        all_passed = all(
            phase.get("success", True)
            for phase in phases.values()
        )

        return {
            "success": all_passed,
            "phases": phases,
            "can_commit": all_passed,
            "error": None if all_passed else "일부 검수 단계 실패"
        }

    except Exception as e:
        return {
            "success": False,
            "phases": phases,
            "can_commit": False,
            "error": str(e)
        }


def auto_review_script(script: str, era_name: str = "") -> dict:
    """
    대본 자동 리뷰 (모든 검수 에이전트 순차 실행)

    ★ FactCheckAgent → ToneReviewAgent → ReviewAgent 순서로 자동 실행
    어느 하나라도 실패하면 즉시 차단

    Args:
        script: 대본 텍스트
        era_name: 시대명 (선택, 사실 검증에 사용)

    Returns:
        {
            "passed": bool,
            "results": {
                "length": {...},
                "fact_check": {...},
                "tone_review": {...},
                "quality_review": {...}
            },
            "error": str or None
        }

    Raises:
        ValueError: 검수 실패 시
    """
    results = {}

    print("\n" + "="*60)
    print("★ 대본 자동 리뷰 시작")
    print("="*60 + "\n")

    # 1. 길이 검증
    print("[1/4] 대본 길이 검증...")
    try:
        length_result = validate_script_strict(script)
        results["length"] = {
            "passed": True,
            "length": length_result["length"],
            "score": length_result["score"],
        }
        print(f"  ✓ 통과: {length_result['length']:,}자")
    except ValueError as e:
        results["length"] = {"passed": False, "error": str(e)}
        raise ValueError(f"[길이 검증 실패]\n{str(e)}")

    # 2. 사실 검증
    print("[2/4] 역사적 사실 검증...")
    try:
        fact_result = check_facts_strict(script, era_name)
        results["fact_check"] = {
            "passed": True,
            "total_issues": fact_result["total_issues"],
            "summary": fact_result["summary"],
        }
        print(f"  ✓ 통과: {fact_result['total_issues']}건 확인 필요")
    except ValueError as e:
        results["fact_check"] = {"passed": False, "error": str(e)}
        raise ValueError(f"[사실 검증 실패]\n{str(e)}")

    # 3. 어투/톤 검증
    print("[3/4] 어투/톤 검증...")
    try:
        tone_result = review_tone_strict(script)
        results["tone_review"] = {
            "passed": True,
            "grade": tone_result["grade"],
            "score": tone_result["score"],
        }
        print(f"  ✓ 통과: {tone_result['grade']}등급 ({tone_result['score']}점)")
    except ValueError as e:
        results["tone_review"] = {"passed": False, "error": str(e)}
        raise ValueError(f"[어투/톤 검증 실패]\n{str(e)}")

    # 4. 종합 품질 검수
    print("[4/4] 종합 품질 검수...")
    grade, score, issues = quick_review(script)
    results["quality_review"] = {
        "passed": grade not in ["D"],
        "grade": grade,
        "score": score,
        "issues": issues,
    }

    if grade == "D":
        raise ValueError(f"[품질 검수 실패]\nD등급 ({score}점): 재작성 필요")
    elif grade == "C":
        print(f"  ⚠️ 경고: C등급 ({score}점) - 개선 권장")
    else:
        print(f"  ✓ 통과: {grade}등급 ({score}점)")

    print("\n" + "="*60)
    print("★ 대본 자동 리뷰 완료 - 모든 검수 통과")
    print("="*60 + "\n")

    return {
        "passed": True,
        "results": results,
        "error": None,
    }


__all__ = [
    # Base
    "AgentStatus",
    "AgentResult",
    "EpisodeContext",
    "BaseAgent",

    # Agents
    "PlannerAgent",
    "ScriptAgent",
    "FactCheckAgent",  # 신규: 사실 검증
    "ToneReviewAgent",  # 신규: 어투/톤 검증
    "ReviewAgent",
    "ImageAgent",
    "YouTubeAgent",
    "CodeReviewAgent",

    # Sync wrappers
    "plan_episode",
    "generate_script_guide",
    "validate_script",
    "validate_script_strict",
    "check_facts",  # 신규: 사실 검증
    "check_facts_strict",  # 신규: 사실 검증 (블로킹)
    "review_tone",  # 신규: 어투/톤 검증
    "review_tone_strict",  # 신규: 어투/톤 검증 (블로킹)
    "review_script",
    "quick_review",
    "review_script_strict",
    "review_image_prompts_strict",
    "generate_image_guide",
    "calculate_image_count",
    "validate_image_prompts_strict",
    "enhance_prompt_with_era_style",
    "get_era_style",
    "generate_youtube_metadata",
    "quick_metadata",
    "review_pipeline",
    "can_commit",

    # Pipeline
    "run_full_pipeline",
    "auto_review_script",  # 신규: 대본 자동 리뷰 (모든 검수 순차 실행)

    # Constants
    "SCRIPT_STYLE_GUIDE",
    "SCENE_STRUCTURE",  # 신규: 씬 구조 템플릿
    "REVIEW_CRITERIA",
    "KOREAN_HISTORY_DATES",  # 신규: 한국사 연대표
    "INAPPROPRIATE_FOR_SENIOR",  # 신규: 40-60대 부적합 표현
    "RECOMMENDED_ENDINGS",  # 신규: 권장 종결어미
    "IMAGE_STYLE_GUIDE",
    "ERA_STYLE_PRESETS",
    "TITLE_TEMPLATES",
    "ERA_KEYWORDS",
    "CODE_REVIEW_CHECKLIST",
]
