"""
SupervisorAgent - 총괄 에이전트 (대표)

역할:
- 사용자 명령 수신 및 해석
- 하위 에이전트 조율 (기획, 자막, 이미지, 검수)
- 품질 검수 결과에 따라 재작업 지시
- 시스템 구조 분석 및 개선 제안
- 최종 결과 승인 및 보고
"""

import asyncio
import time
from typing import Any, Dict, List, Optional

try:
    from .base import BaseAgent, AgentResult, AgentStatus, TaskContext
    from .script_agent import ScriptAgent
    from .image_agent import ImageAgent
    from .review_agent import ReviewAgent
    from .subtitle_agent import SubtitleAgent
except ImportError:
    from base import BaseAgent, AgentResult, AgentStatus, TaskContext
    from script_agent import ScriptAgent
    from image_agent import ImageAgent
    from review_agent import ReviewAgent
    try:
        from subtitle_agent import SubtitleAgent
    except ImportError:
        SubtitleAgent = None  # 아직 구현 안됨


class SupervisorAgent(BaseAgent):
    """총괄 에이전트 (대표)"""

    # 쇼츠 제작에 필요한 필수 역할 정의
    REQUIRED_CAPABILITIES = {
        "script": {
            "name": "대본 생성",
            "description": "주제를 바탕으로 쇼츠 대본 작성",
            "agent_class": "ScriptAgent",
        },
        "subtitle": {
            "name": "TTS + 자막",
            "description": "대본을 음성으로 변환하고 자막 생성/동기화",
            "agent_class": "SubtitleAgent",
        },
        "image": {
            "name": "이미지 생성",
            "description": "씬별 배경 이미지 생성",
            "agent_class": "ImageAgent",
        },
        "review": {
            "name": "품질 검수",
            "description": "대본, 자막, 이미지 품질 검토 및 피드백",
            "agent_class": "ReviewAgent",
        },
    }

    def __init__(self):
        super().__init__("Supervisor")

        # 하위 에이전트 초기화
        self.script_agent = ScriptAgent()
        self.image_agent = ImageAgent()
        self.review_agent = ReviewAgent()

        # SubtitleAgent는 구현되어 있으면 초기화
        self.subtitle_agent = SubtitleAgent() if SubtitleAgent else None

        # 에이전트 레지스트리
        self.agents: Dict[str, BaseAgent] = {
            "script": self.script_agent,
            "image": self.image_agent,
            "review": self.review_agent,
        }
        if self.subtitle_agent:
            self.agents["subtitle"] = self.subtitle_agent

        # 설정
        self.max_script_attempts = 3
        self.max_image_attempts = 2
        self.max_subtitle_attempts = 2

        # 초기화 시 시스템 분석 수행
        self._system_analysis = self._analyze_system_structure()

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
            # PHASE 2: TTS + 자막 생성
            # ========================================
            skip_subtitle = kwargs.get("skip_subtitle", False)

            if self.subtitle_agent and not skip_subtitle:
                self.log("Phase 2: TTS + 자막 생성")
                subtitle_approved = False

                while context.subtitle_attempts < self.max_subtitle_attempts and not subtitle_approved:
                    if context.subtitle_attempts == 0:
                        subtitle_result = await self.subtitle_agent.execute(context)
                    else:
                        subtitle_result = await self.subtitle_agent.execute(
                            context,
                            feedback=context.subtitle_feedback
                        )

                    total_cost += subtitle_result.cost
                    context.subtitle_attempts += 1

                    if not subtitle_result.success:
                        self.log(f"자막 생성 실패 (시도 {context.subtitle_attempts}): {subtitle_result.error}", "error")
                        continue

                    # 자막 검수 (ReviewAgent가 subtitle 검수 지원하는 경우)
                    review_result = await self.review_agent.execute(context, review_type="subtitle")
                    total_cost += review_result.cost

                    if not review_result.needs_improvement:
                        subtitle_approved = True
                        self.log(f"자막 검수 통과 (시도 {context.subtitle_attempts})")
                    else:
                        context.subtitle_feedback = review_result.feedback
                        self.log(f"자막 개선 필요 (시도 {context.subtitle_attempts})")

                if not subtitle_approved:
                    self.log("자막 최대 시도 횟수 초과, 현재 버전 사용", "warning")
            else:
                if not self.subtitle_agent:
                    self.log("SubtitleAgent 미구현 - 자막 생성 스킵", "warning")

            # ========================================
            # PHASE 3: 이미지 최적화 + 생성 + 검수 루프
            # ========================================
            if not skip_images:
                self.log("Phase 3: 이미지 생성")

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
            # PHASE 4: 최종 결과 정리
            # ========================================
            duration = time.time() - start_time

            self.log(f"=== 작업 완료 ===")
            self.log(f"총 소요 시간: {duration:.1f}초")
            self.log(f"총 비용: ${total_cost:.4f}")
            self.log(f"대본 시도: {context.script_attempts}회")
            self.log(f"자막 시도: {context.subtitle_attempts}회")
            self.log(f"이미지 시도: {context.image_attempts}회")

            context.add_log(self.name, "complete", "success", f"${total_cost:.4f}, {duration:.1f}초")

            self.set_status(AgentStatus.SUCCESS)

            return AgentResult(
                success=True,
                data={
                    "task_id": context.task_id,
                    "script": context.script,
                    "subtitle_data": context.subtitle_data,
                    "images": context.images,
                    "script_attempts": context.script_attempts,
                    "subtitle_attempts": context.subtitle_attempts,
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

    # =========================================================================
    # 시스템 자기 분석 (메타 레벨)
    # =========================================================================

    def _analyze_system_structure(self) -> Dict[str, Any]:
        """
        시스템 구조 분석 및 누락된 역할 감지

        슈퍼바이저가 스스로 판단:
        - 현재 에이전트 구성이 충분한가?
        - 어떤 역할이 누락되었는가?
        - 어떤 개선이 필요한가?

        Returns:
            {
                "available_agents": ["script", "image", "review"],
                "missing_agents": ["subtitle"],
                "recommendations": [...],
                "is_complete": False
            }
        """
        available = list(self.agents.keys())
        missing = []
        recommendations = []

        # 필수 역할 중 누락된 것 확인
        for capability, info in self.REQUIRED_CAPABILITIES.items():
            if capability not in self.agents or self.agents[capability] is None:
                missing.append(capability)
                recommendations.append({
                    "type": "missing_agent",
                    "capability": capability,
                    "agent_class": info["agent_class"],
                    "reason": f"{info['name']} 기능이 없습니다. {info['description']}",
                    "priority": "high" if capability in ["script", "subtitle"] else "medium",
                })

        # 시스템 완전성 판단
        is_complete = len(missing) == 0

        # 추가 분석: 현재 에이전트들의 상태
        agent_status = {}
        for name, agent in self.agents.items():
            if agent:
                agent_status[name] = {
                    "status": agent.status.value if hasattr(agent, 'status') else "unknown",
                    "initialized": True,
                }
            else:
                agent_status[name] = {
                    "status": "not_initialized",
                    "initialized": False,
                }

        analysis = {
            "available_agents": available,
            "missing_agents": missing,
            "agent_status": agent_status,
            "recommendations": recommendations,
            "is_complete": is_complete,
            "summary": self._generate_analysis_summary(available, missing, recommendations),
        }

        # 로그 출력
        if missing:
            self.log(f"⚠️ 시스템 분석: {len(missing)}개 역할 누락 - {missing}")
            for rec in recommendations:
                self.log(f"  └ {rec['reason']}")

        return analysis

    def _generate_analysis_summary(
        self,
        available: List[str],
        missing: List[str],
        recommendations: List[Dict]
    ) -> str:
        """분석 결과 요약 생성"""
        if not missing:
            return f"✅ 시스템 완전: {len(available)}개 에이전트 모두 정상"

        lines = [
            f"⚠️ 시스템 불완전: {len(available)}개 활성, {len(missing)}개 누락",
            "",
            "누락된 역할:",
        ]

        for cap in missing:
            info = self.REQUIRED_CAPABILITIES.get(cap, {})
            lines.append(f"  - {cap}: {info.get('name', '')} ({info.get('description', '')})")

        lines.extend([
            "",
            "권장 조치:",
        ])

        for rec in recommendations:
            lines.append(f"  - {rec['agent_class']} 구현 필요 (우선순위: {rec['priority']})")

        return "\n".join(lines)

    def get_system_analysis(self) -> Dict[str, Any]:
        """시스템 분석 결과 반환 (외부 호출용)"""
        return self._system_analysis

    def diagnose(self) -> str:
        """
        시스템 진단 결과를 사람이 읽기 쉬운 형태로 반환

        사용법:
            supervisor = SupervisorAgent()
            print(supervisor.diagnose())
        """
        analysis = self._system_analysis
        return analysis.get("summary", "분석 결과 없음")
