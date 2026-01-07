"""
한국사 파이프라인 - Planner Agent (기획 에이전트)

## 성격 및 역할
40년간 기획을 해온 전문가.
하위 에이전트들을 잘 컨트롤해서 문제가 없게 만듦.

## 철학
- "기획이 80%다" - 좋은 기획 없이 좋은 결과물은 없다
- 모든 하위 에이전트의 작업을 미리 예상하고 가이드를 제공
- 문제가 생기기 전에 예방하는 것이 최우선

## 책임
- 에피소드 구조 설계 (인트로/배경/본론1/본론2/마무리)
- 대본 흐름 기획 및 방향 설정
- 핵심 포인트 도출 및 스토리 아크 설계
- 다음화 연결 훅 설계
- 하위 에이전트(대본, 검수, 이미지)에게 명확한 지시 전달

## 하위 에이전트 관리
- ScriptAgent: 대본 작성 가이드라인 제공
- ReviewAgent: 검수 기준 사전 공유
- ImageAgent: 시각적 톤앤매너 방향 설정
"""

import time
from typing import Any, Dict, Optional

from .base import BaseAgent, AgentResult, AgentStatus, EpisodeContext


class PlannerAgent(BaseAgent):
    """기획 에이전트"""

    def __init__(self):
        super().__init__("PlannerAgent")

    async def execute(self, context: EpisodeContext, **kwargs) -> AgentResult:
        """
        에피소드 기획 실행

        Args:
            context: 에피소드 컨텍스트
            **kwargs:
                feedback: 검수 피드백 (개선 시)

        Returns:
            AgentResult with brief data
        """
        self.set_status(AgentStatus.RUNNING)
        start_time = time.time()

        feedback = kwargs.get("feedback")
        is_improvement = feedback is not None

        context.brief_attempts += 1
        context.add_log(
            self.name,
            "기획 시작" if not is_improvement else "기획 개선",
            "running",
            f"시도 {context.brief_attempts}/{context.max_attempts}"
        )

        try:
            # 기획서 생성
            brief = self._generate_brief(context, feedback)

            context.brief = brief
            duration = time.time() - start_time

            context.add_log(self.name, "기획 완료", "success", f"{duration:.1f}초")
            self.set_status(AgentStatus.SUCCESS)

            return AgentResult(
                success=True,
                data={"brief": brief},
                duration=duration,
            )

        except Exception as e:
            duration = time.time() - start_time
            error_msg = str(e)

            context.add_log(self.name, "기획 실패", "error", error_msg)
            self.set_status(AgentStatus.FAILED)

            return AgentResult(
                success=False,
                error=error_msg,
                duration=duration,
            )

    def _generate_brief(
        self,
        context: EpisodeContext,
        feedback: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        에피소드 기획서 생성

        실제로는 Claude가 대화에서 직접 기획하므로,
        이 메서드는 기획서 구조의 템플릿을 제공합니다.
        """

        # 기본 구조 (12,000~15,000자 기준)
        structure = [
            {
                "part": "인트로",
                "description": "시청자 주의를 끄는 훅, 에피소드 주제 소개",
                "target_chars": 1500,
                "tips": [
                    "구체적인 시점/상황으로 시작 (예: '서기 685년 겨울이었어요')",
                    "질문으로 호기심 유발",
                    "이번 영상에서 다룰 내용 예고",
                ],
            },
            {
                "part": "배경",
                "description": "역사적 맥락, 상황 설명",
                "target_chars": 2500,
                "tips": [
                    "이전 에피소드와 연결 (시청자 기억 환기)",
                    "당시 상황의 문제점/갈등 제시",
                    "인물의 고민이나 선택의 순간 묘사",
                ],
            },
            {
                "part": "본론1",
                "description": "핵심 사건/인물/제도 설명 (전반)",
                "target_chars": 4000,
                "tips": [
                    "구체적인 에피소드와 숫자 사용",
                    "가정법으로 몰입감 유도 ('~했을까요?')",
                    "중간중간 시청자 질문 던지기",
                ],
            },
            {
                "part": "본론2",
                "description": "핵심 사건/인물/제도 설명 (후반)",
                "target_chars": 4500,
                "tips": [
                    "본론1과 연결되는 흐름",
                    "반전이나 새로운 시각 제시",
                    "역사적 의의와 영향 분석",
                ],
            },
            {
                "part": "마무리",
                "description": "정리, 현재와의 연결, 다음화 예고",
                "target_chars": 2500,
                "tips": [
                    "핵심 내용 간단히 정리",
                    "현재까지 이어지는 영향 언급",
                    "다음 에피소드 훅으로 마무리",
                ],
            },
        ]

        # 다음화 정보가 있으면 예고 훅 생성
        ending_hook = ""
        if context.next_episode:
            next_title = context.next_episode.get("title", "")
            next_topic = context.next_episode.get("topic", "")
            ending_hook = f"다음 시간에는 '{next_title}'을 살펴볼게요. {next_topic}의 이야기가 시작됩니다."

        brief = {
            "episode_id": context.episode_id,
            "episode_number": context.episode_number,
            "era": context.era,
            "era_name": context.era_name,
            "title": context.title,
            "topic": context.topic,

            # 기획 내용
            "hook": self._generate_hook(context),
            "structure": structure,
            "key_points": self._extract_key_points(context),
            "narrative_style": "스토리텔링형 (대화체, ~거든요/~었어요 종결)",
            "ending_hook": ending_hook,

            # 참고 정보
            "reference_links": context.reference_links,
            "keywords": context.keywords,

            # 이전/다음 에피소드 연결
            "prev_episode": context.prev_episode,
            "next_episode": context.next_episode,

            # 검수 피드백 반영
            "feedback_applied": feedback if feedback else None,
        }

        return brief

    def _generate_hook(self, context: EpisodeContext) -> str:
        """첫 문장 훅 생성"""
        # 주제에 따른 훅 템플릿
        hooks = {
            "건국": f"{context.era_name}이 시작되는 순간이었어요.",
            "전쟁": "전쟁의 그림자가 드리웠어요.",
            "개혁": "변화의 바람이 불기 시작했어요.",
            "멸망": "끝이 보이기 시작했어요.",
            "문화": "새로운 문화가 꽃피던 시절이었어요.",
        }

        # 기본 훅
        return f"서기 {context.era_name} 시대였어요. {context.title}의 이야기가 시작됩니다."

    def _extract_key_points(self, context: EpisodeContext) -> list:
        """핵심 포인트 추출"""
        key_points = []

        # 키워드에서 핵심 포인트 도출
        if context.keywords:
            for kw in context.keywords[:5]:
                key_points.append(f"'{kw}'의 의미와 역사적 맥락")

        # 주제에서 핵심 질문 도출
        if context.topic:
            key_points.append(f"왜 {context.topic}이/가 중요했는가?")
            key_points.append(f"{context.topic}의 결과와 영향")

        return key_points


# 동기 실행 래퍼
def plan_episode(context: EpisodeContext, feedback: str = None) -> Dict[str, Any]:
    """
    에피소드 기획 (동기 버전)

    Args:
        context: 에피소드 컨텍스트
        feedback: 검수 피드백

    Returns:
        기획서 딕셔너리
    """
    import asyncio

    agent = PlannerAgent()

    # 이벤트 루프 실행
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    result = loop.run_until_complete(
        agent.execute(context, feedback=feedback)
    )

    if result.success:
        return result.data.get("brief", {})
    else:
        raise Exception(result.error)
