"""
SupervisorAgent - 총괄 에이전트 (대표)

역할:
- 사용자 명령 수신 및 해석
- 하위 에이전트 조율 (기획, 이미지, 검수)
- 품질 검수 결과에 따라 재작업 지시
- 최종 결과 승인 및 보고
"""

import asyncio
import time
from typing import Any, Dict, Optional

try:
    from .base import BaseAgent, AgentResult, AgentStatus, TaskContext
    from .script_agent import ScriptAgent
    from .image_agent import ImageAgent
    from .review_agent import ReviewAgent
except ImportError:
    from base import BaseAgent, AgentResult, AgentStatus, TaskContext
    from script_agent import ScriptAgent
    from image_agent import ImageAgent
    from review_agent import ReviewAgent


class SupervisorAgent(BaseAgent):
    """총괄 에이전트 (대표)"""

    def __init__(self):
        super().__init__("Supervisor")

        # 하위 에이전트 초기화
        self.script_agent = ScriptAgent()
        self.image_agent = ImageAgent()
        self.review_agent = ReviewAgent()

        # 설정
        self.max_script_attempts = 3
        self.max_image_attempts = 2

    async def execute(self, context: TaskContext, **kwargs) -> AgentResult:
        """
        전체 파이프라인 실행

        Args:
            context: 작업 컨텍스트
            **kwargs:
                skip_images: 이미지 생성 스킵 (테스트용)

        Returns:
            AgentResult with final outputs
        """
        self.set_status(AgentStatus.RUNNING)
        start_time = time.time()

        skip_images = kwargs.get("skip_images", False)

        self.log(f"=== 작업 시작: {context.topic} ===")
        context.add_log(self.name, "start", "running", f"Topic: {context.topic}")

        total_cost = 0

        try:
            # ========================================
            # PHASE 1: 대본 생성 + 검수 루프
            # ========================================
            self.log("Phase 1: 대본 생성")
            script_approved = False

            while context.script_attempts < self.max_script_attempts and not script_approved:
                # 1-1. 대본 생성 (또는 개선)
                if context.script_attempts == 0:
                    script_result = await self.script_agent.execute(context)
                else:
                    # 피드백 반영하여 개선
                    script_result = await self.script_agent.execute(
                        context,
                        feedback=context.script_feedback
                    )

                total_cost += script_result.cost

                if not script_result.success:
                    self.log(f"대본 생성 실패 (시도 {context.script_attempts}): {script_result.error}", "error")
                    continue

                # 1-2. 대본 검수
                review_result = await self.review_agent.execute(context, review_type="script")
                total_cost += review_result.cost

                if not review_result.needs_improvement:
                    script_approved = True
                    self.log(f"대본 검수 통과 (시도 {context.script_attempts})")
                else:
                    self.log(f"대본 개선 필요 (시도 {context.script_attempts}): {review_result.feedback[:100]}...")

            if not script_approved:
                self.log("대본 최대 시도 횟수 초과, 현재 버전 사용", "warning")

            # ========================================
            # PHASE 2: 이미지 최적화 + 생성 + 검수 루프
            # ========================================
            if not skip_images:
                self.log("Phase 2: 이미지 생성")

                # 2-0. 이미지 캐시 최적화 (슈퍼바이저가 판단)
                optimization = await self._optimize_image_generation(context)
                if optimization:
                    self.log(f"이미지 최적화: {optimization['summary']}")
                    context.add_log(self.name, "optimize_images", "success", optimization['summary'])

                image_approved = False

                while context.image_attempts < self.max_image_attempts and not image_approved:
                    # 2-1. 이미지 생성 (최적화 정보 전달)
                    if context.image_attempts == 0:
                        image_result = await self.image_agent.execute(
                            context,
                            optimization=optimization
                        )
                    else:
                        # 실패한 씬만 재생성
                        failed_scenes = context.image_feedback.get("failed_scenes", []) if isinstance(context.image_feedback, dict) else []
                        image_result = await self.image_agent.execute(
                            context,
                            feedback=str(context.image_feedback),
                            failed_scenes=failed_scenes
                        )

                    total_cost += image_result.cost

                    if not image_result.success:
                        self.log(f"이미지 생성 실패 (시도 {context.image_attempts}): {image_result.error}", "error")
                        continue

                    # 2-2. 이미지 검수
                    review_result = await self.review_agent.execute(context, review_type="image")
                    total_cost += review_result.cost

                    if not review_result.needs_improvement:
                        image_approved = True
                        self.log(f"이미지 검수 통과 (시도 {context.image_attempts})")
                    else:
                        # 피드백 저장 (재생성용)
                        if review_result.data and review_result.data.get("image_review"):
                            context.image_feedback = review_result.data["image_review"]
                        self.log(f"이미지 재생성 필요 (시도 {context.image_attempts})")

                if not image_approved:
                    self.log("이미지 최대 시도 횟수 초과, 현재 버전 사용", "warning")

            # ========================================
            # PHASE 3: 최종 결과 정리
            # ========================================
            duration = time.time() - start_time

            self.log(f"=== 작업 완료 ===")
            self.log(f"총 소요 시간: {duration:.1f}초")
            self.log(f"총 비용: ${total_cost:.4f}")
            self.log(f"대본 시도: {context.script_attempts}회")
            self.log(f"이미지 시도: {context.image_attempts}회")

            context.add_log(self.name, "complete", "success", f"${total_cost:.4f}, {duration:.1f}초")

            self.set_status(AgentStatus.SUCCESS)

            return AgentResult(
                success=True,
                data={
                    "task_id": context.task_id,
                    "script": context.script,
                    "images": context.images,
                    "script_attempts": context.script_attempts,
                    "image_attempts": context.image_attempts,
                    "logs": context.logs,
                },
                cost=total_cost,
                duration=duration,
            )

        except Exception as e:
            self.set_status(AgentStatus.FAILED)
            context.add_log(self.name, "execute", "exception", str(e))

            return AgentResult(
                success=False,
                error=str(e),
                data={"logs": context.logs},
                cost=total_cost,
                duration=time.time() - start_time,
            )

    async def _optimize_image_generation(self, context: TaskContext) -> Optional[Dict[str, Any]]:
        """
        이미지 생성 최적화 (슈퍼바이저가 판단)

        - 이슈 타입별 템플릿 활용
        - 캐시된 성공 프롬프트 재사용
        - 비용 절감 전략 수립

        Returns:
            {
                "optimized_scenes": [...],
                "cache_hits": 2,
                "generate_count": 3,
                "estimated_savings": 0.10,
                "summary": "5개 씬 중 2개 캐시 사용, $0.10 절감 예상"
            }
        """
        if not context.script or not context.script.get("scenes"):
            return None

        try:
            # 이미지 캐시 로드
            try:
                from image_cache import get_image_cache
            except ImportError:
                from .image_cache import get_image_cache

            cache = get_image_cache()
            scenes = context.script.get("scenes", [])
            issue_type = context.issue_type or "default"

            # 최적화된 프롬프트 목록 생성
            optimized = cache.get_optimized_prompts(scenes, issue_type)

            # 통계 계산
            cache_hits = sum(1 for s in optimized if s.get("use_cache"))
            generate_count = sum(1 for s in optimized if s.get("generate"))
            estimated_savings = cache_hits * 0.05  # 캐시 1개당 $0.05 절감

            summary = f"{len(scenes)}개 씬 중 {cache_hits}개 캐시, {generate_count}개 생성"
            if estimated_savings > 0:
                summary += f", ${estimated_savings:.2f} 절감"

            self.log(f"최적화 분석: {summary}")

            return {
                "optimized_scenes": optimized,
                "cache_hits": cache_hits,
                "generate_count": generate_count,
                "estimated_savings": estimated_savings,
                "summary": summary,
                "issue_type": issue_type,
            }

        except Exception as e:
            self.log(f"이미지 최적화 실패 (무시): {e}", "warning")
            return None

    async def run(
        self,
        topic: str,
        person: str = "",
        category: str = "연예인",
        issue_type: str = "이슈",
        **kwargs
    ) -> AgentResult:
        """
        간편 실행 메서드 (사용자 인터페이스)

        사용법:
            supervisor = SupervisorAgent()
            result = await supervisor.run(
                topic="BTS 컴백 소식",
                person="BTS",
                category="연예인",
                issue_type="컴백"
            )

        Args:
            topic: 쇼츠 주제/뉴스 제목
            person: 대상 인물
            category: 카테고리 (연예인/운동선수/국뽕)
            issue_type: 이슈 타입 (논란/열애/컴백/사건/근황/성과)
            **kwargs: 추가 옵션 (skip_images 등)

        Returns:
            AgentResult
        """
        # 컨텍스트 생성
        context = TaskContext(
            topic=topic,
            person=person or topic.split()[0],  # 첫 단어를 인물명으로 추정
            category=category,
            issue_type=issue_type,
            max_attempts=kwargs.get("max_attempts", 3),
        )

        # 실행
        return await self.execute(context, **kwargs)

    def run_sync(
        self,
        topic: str,
        person: str = "",
        category: str = "연예인",
        issue_type: str = "이슈",
        **kwargs
    ) -> AgentResult:
        """
        동기 실행 메서드 (asyncio 없이 사용)

        사용법:
            supervisor = SupervisorAgent()
            result = supervisor.run_sync(
                topic="BTS 컴백 소식",
                person="BTS"
            )
        """
        return asyncio.run(self.run(topic, person, category, issue_type, **kwargs))

    def get_status_report(self, context: TaskContext) -> str:
        """현재 상태 리포트 생성"""
        lines = [
            f"=== 작업 상태 리포트 ===",
            f"Task ID: {context.task_id}",
            f"주제: {context.topic}",
            f"인물: {context.person}",
            f"",
            f"[대본]",
            f"  시도 횟수: {context.script_attempts}",
            f"  상태: {'완료' if context.script else '미완료'}",
            f"",
            f"[이미지]",
            f"  시도 횟수: {context.image_attempts}",
            f"  생성된 이미지: {len(context.images) if context.images else 0}개",
            f"",
            f"[로그]",
        ]

        for log in context.logs[-5:]:  # 최근 5개 로그
            lines.append(f"  {log['timestamp']} [{log['agent']}] {log['action']}: {log['result']}")

        return "\n".join(lines)
