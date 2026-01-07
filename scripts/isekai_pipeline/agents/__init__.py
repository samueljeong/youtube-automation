"""
혈영 이세계편 - 에이전트 모듈

## 에이전트 팀 구성

### 기획 에이전트 (PlannerAgent)
- 역할: Series Bible 기반 에피소드 구조 설계
- 특징: 60화 스토리 일관성 유지
- 책임: 씬 구조 설계, 캐릭터 등장 시점 관리

### BriefCheckerAgent (기획서 검증)
- 역할: 기획서가 Series Bible을 준수하는지 검증
- 특징: 캐릭터 등장 시점, 씬 구조 완성도 검증
- 책임: 80점 미만 시 재작성 권고

### ScriptAgent (대본)
- 역할: 12,000~15,000자 대본 작성
- 특징: 씬 단위 분할 작성 (토큰 제한 대응)
- 책임: 무협 소설체 문장, TTS 최적화

### FormCheckerAgent (문체 검증)
- 역할: 문체/형식 일관성 검증
- 특징: 문장 길이, 문단 길이, 태그 없음 검증
- 책임: 50자 이하 문장, 5줄 이하 문단

### VoiceCheckerAgent (말투 검증)
- 역할: 캐릭터 대사 일관성 검증
- 특징: 캐릭터별 말투 패턴 검증
- 책임: 무영(건조), 카이든(밝음), 에이라(고아체)

### FeelCheckerAgent (감정 검증)
- 역할: 분위기/감정 흐름 검증
- 특징: 감정 전환 자연스러움, 클라이맥스 임팩트
- 책임: 긴장-이완 밸런스

### ImageAgent (이미지)
- 역할: 무협+판타지 융합 이미지 프롬프트 생성
- 특징: 동양 검객 + 서양 판타지 세계
- 책임: 씬별 5~12개 프롬프트, 썸네일 1개

### YouTubeAgent (메타데이터)
- 역할: SEO 최적화 메타데이터 생성
- 특징: 클릭 유도 제목, 검색 친화적 설명
- 책임: 제목 3종, 설명, 태그 15~20개

### ReviewAgent (최종 검토)
- 역할: 최종 품질 검증
- 특징: 스토리 일관성 최우선
- 책임: S/A/B/C/D 등급 산정, C/D등급 시 수정 필요

## 워크플로우

```
┌─────────────────────────────────────────────────────────────┐
│  PlannerAgent (기획)                                        │
│  - Series Bible 기반 에피소드 구조 설계                     │
│  - 씬 구조 (5개: 오프닝/전개/클라이맥스/해결/엔딩)          │
└─────────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│  BriefCheckerAgent (기획서 검증)                            │
│  - Series Bible 준수 여부 검증                              │
│  - 캐릭터 등장 시점 검증 (카이든 2화~, 에이라 12화~ 등)     │
│  ⚠️ 80점 미만 시 재작성                                    │
└─────────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│  ScriptAgent (대본)                                         │
│  - 12,000~15,000자 (13~16분) 대본 작성                     │
│  - 씬 단위로 분할 작성 (토큰 제한 대응)                    │
│  - 무협 소설체 문장, TTS 최적화                            │
└─────────────────────────────────────────────────────────────┘
                          │
        ┌─────────────────┼─────────────────┐
        ▼                 ▼                 ▼
┌───────────────┐ ┌───────────────┐ ┌───────────────┐
│ FormChecker   │ │ VoiceChecker  │ │ FeelChecker   │
│ (문체 검증)    │ │ (말투 검증)    │ │ (감정 검증)    │
│ - 문장 길이    │ │ - 캐릭터 말투  │ │ - 분위기 흐름  │
│ - 문체 일관성  │ │ - 대사 일관성  │ │ - 감정 전환    │
└───────────────┘ └───────────────┘ └───────────────┘
        │                 │                 │
        └─────────────────┴─────────────────┘
                          │
                      (80점↑ 통과)
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│  ImageAgent → YouTubeAgent → ReviewAgent                   │
└─────────────────────────────────────────────────────────────┘
```

## 사용법

```python
from scripts.isekai_pipeline.agents import (
    EpisodeContext,
    BriefCheckerAgent,
    FormCheckerAgent,
    VoiceCheckerAgent,
    FeelCheckerAgent,
)

# 컨텍스트 생성
context = EpisodeContext.from_episode(
    episode_number=1,
    title="전생, 이계에서의 첫 걸음",
    characters=["무영"],
)

# 기획서 검증
brief_checker = BriefCheckerAgent()
brief = {
    "characters": ["무영"],
    "scenes": ["오프닝", "전개", "클라이맥스", "해결", "엔딩"],
    "next_episode_hook": "다음화 훅",
}
result = brief_checker.check(context.episode_number, brief)
print(f"기획서 검증: {result['grade']} ({result['total_score']}점)")

# 대본 검증 (병렬)
script = "대본 내용..."
form_result = FormCheckerAgent().check(script)
voice_result = VoiceCheckerAgent().check(script)
feel_result = FeelCheckerAgent().check(script, scenes=["씬1", "씬2", ...])
```
"""

# Base classes
from .base import (
    AgentStatus,
    AgentResult,
    EpisodeContext,
    BaseAgent,
)

# Checker Agents
from .brief_checker_agent import (
    BriefCheckerAgent,
    CHARACTER_APPEARANCE,
)

from .form_checker_agent import (
    FormCheckerAgent,
)

from .voice_checker_agent import (
    VoiceCheckerAgent,
    CHARACTER_VOICES,
)

from .feel_checker_agent import (
    FeelCheckerAgent,
    EMOTION_KEYWORDS,
    SCENE_EMOTIONS,
)


def check_script_quality(script: str, scenes: list = None, episode: int = 1) -> dict:
    """
    대본 품질 종합 검증 (FormChecker + VoiceChecker + FeelChecker)

    Args:
        script: 대본 전문
        scenes: 씬별 분할 대본 (없으면 전체를 1씬으로 처리)
        episode: 에피소드 번호 (캐릭터 등장 검증용)

    Returns:
        {
            "passed": bool,
            "total_score": float,
            "grade": str (S/A/B/C/D),
            "form": {...},
            "voice": {...},
            "feel": {...},
        }
    """
    form_checker = FormCheckerAgent()
    voice_checker = VoiceCheckerAgent()
    feel_checker = FeelCheckerAgent()

    form_result = form_checker.check(script)
    voice_result = voice_checker.check(script)
    feel_result = feel_checker.check(script, scenes)

    # 총점 계산 (가중 평균)
    total_score = (
        form_result["total_score"] * 0.3 +
        voice_result["total_score"] * 0.3 +
        feel_result["total_score"] * 0.4
    )

    # 등급 산정
    if total_score >= 90:
        grade = "S"
    elif total_score >= 80:
        grade = "A"
    elif total_score >= 70:
        grade = "B"
    elif total_score >= 60:
        grade = "C"
    else:
        grade = "D"

    passed = grade in ["S", "A", "B"]

    return {
        "passed": passed,
        "total_score": total_score,
        "grade": grade,
        "form": form_result,
        "voice": voice_result,
        "feel": feel_result,
    }


def check_brief(episode: int, brief: dict, prev_brief: dict = None) -> dict:
    """
    기획서 검증

    Args:
        episode: 에피소드 번호
        brief: 기획서 딕셔너리
        prev_brief: 이전화 기획서 (연속성 검증용)

    Returns:
        BriefCheckerAgent.check() 결과
    """
    checker = BriefCheckerAgent()
    return checker.check(episode, brief, prev_brief)


__all__ = [
    # Base
    "AgentStatus",
    "AgentResult",
    "EpisodeContext",
    "BaseAgent",

    # Agents
    "BriefCheckerAgent",
    "FormCheckerAgent",
    "VoiceCheckerAgent",
    "FeelCheckerAgent",

    # Helper functions
    "check_script_quality",
    "check_brief",

    # Constants
    "CHARACTER_APPEARANCE",
    "CHARACTER_VOICES",
    "EMOTION_KEYWORDS",
    "SCENE_EMOTIONS",
]
