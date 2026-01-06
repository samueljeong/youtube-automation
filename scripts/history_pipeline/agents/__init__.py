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

### 대본 리뷰 에이전트 (ReviewAgent)
- 역할: 깐깐하고 철저한 검수자
- 특징: 대충 넘어가지 않고 문제를 파악해서 개선
- 책임: 대본 품질 검수, 피드백 생성, 승인/반려 결정

### 이미지 에이전트 (ImageAgent)
- 역할: 텍스트를 이미지화하는 전문가
- 특징: 이미지만 봐도 내용이 이해될 수 있게 함
- 책임: 씬별 이미지 프롬프트 생성, 썸네일 가이드

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
│  │  │  ScriptAgent ──→ ReviewAgent ──→ ImageAgent    │  │  │
│  │  │   (대본 작성)     (검수/피드백)   (이미지 생성)   │  │  │
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
    SCRIPT_STYLE_GUIDE,
)

from .review_agent import (
    ReviewAgent,
    review_script,
    quick_review,
    REVIEW_CRITERIA,
)

from .image_agent import (
    ImageAgent,
    generate_image_guide,
    calculate_image_count,
    IMAGE_STYLE_GUIDE,
    ERA_STYLE_PRESETS,
)

from .code_review_agent import (
    CodeReviewAgent,
    review_pipeline,
    can_commit,
    CODE_REVIEW_CHECKLIST,
)


def run_full_pipeline(context: EpisodeContext) -> dict:
    """
    전체 파이프라인 실행 (기획 → 대본 → 검수 → 이미지)

    모든 단계는 CodeReviewAgent가 감시합니다.

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
        # 1. 기획 단계
        planner = PlannerAgent()

        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

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

        # 1-1. 기획 검수
        code_reviewer = CodeReviewAgent()
        planning_review = loop.run_until_complete(
            code_reviewer.execute(context, phase="planning")
        )
        phases["planning_review"] = {
            "success": planning_review.success,
            "approval": planning_review.data.get("approval_status") if planning_review.success else None,
        }

        if planning_review.data.get("approval_status") == "rejected":
            return {
                "success": False,
                "phases": phases,
                "can_commit": False,
                "error": "기획 검수 거부: " + str(planning_review.data.get("findings", {}).get("critical", []))
            }

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

        # 3. 대본 검수 (대본이 있는 경우만)
        if context.script:
            review_agent = ReviewAgent()
            review_result = loop.run_until_complete(review_agent.execute(context))
            phases["script_review"] = {
                "success": review_result.success,
                "grade": review_result.data.get("grade") if review_result.success else None,
                "passed": review_result.data.get("passed") if review_result.success else False,
            }

            # 대본 검수 통과하지 못하면 경고 (중단하지 않음)
            if review_result.success and not review_result.data.get("passed"):
                phases["script_review"]["warning"] = review_result.data.get("feedback", {}).get("summary")

        # 4. 이미지 가이드 생성 (대본이 있는 경우만)
        if context.script:
            image_agent = ImageAgent()
            image_result = loop.run_until_complete(image_agent.execute(context))
            phases["image_guide"] = {
                "success": image_result.success,
                "image_count": image_result.data.get("image_count") if image_result.success else 0,
            }

        # 5. 최종 검수
        final_review = loop.run_until_complete(
            code_reviewer.execute(context, phase="final")
        )
        phases["final_review"] = {
            "success": final_review.success,
            "approval": final_review.data.get("approval_status") if final_review.success else None,
            "can_commit": final_review.data.get("can_commit") if final_review.success else False,
        }

        return {
            "success": True,
            "phases": phases,
            "can_commit": phases["final_review"].get("can_commit", False),
            "error": None
        }

    except Exception as e:
        return {
            "success": False,
            "phases": phases,
            "can_commit": False,
            "error": str(e)
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
    "ReviewAgent",
    "ImageAgent",
    "CodeReviewAgent",

    # Sync wrappers
    "plan_episode",
    "generate_script_guide",
    "validate_script",
    "review_script",
    "quick_review",
    "generate_image_guide",
    "calculate_image_count",
    "review_pipeline",
    "can_commit",

    # Pipeline
    "run_full_pipeline",

    # Constants
    "SCRIPT_STYLE_GUIDE",
    "REVIEW_CRITERIA",
    "IMAGE_STYLE_GUIDE",
    "ERA_STYLE_PRESETS",
    "CODE_REVIEW_CHECKLIST",
]
