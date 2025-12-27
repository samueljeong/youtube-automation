"""
VideoSupervisorAgent - 영상 생성 총괄 에이전트

역할:
- 대본 분석 → 최적 전략 결정
- 하위 에이전트 스케줄링 및 병렬 처리 조율
- 품질 검증 결과에 따른 재작업 지시
- 예산 동적 분배
- 최종 결과 승인 및 보고

권한:
- 병렬 실행: TTS 완료 후 이미지/썸네일 동시 생성
- 동적 예산 분배: 품질에 따라 에이전트간 예산 재분배
- 피드백 루프: 품질 미달 시 자동 재생성 (최대 3회)
"""

import asyncio
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from .base import (
    BaseAgent, AgentResult, AgentStatus,
    VideoTaskContext, BudgetManager
)
from .analysis_agent import AnalysisAgent
from .audio_agent import AudioAgent
from .creative_agent import CreativeAgent
from .quality_agent import QualityAgent
from .production_agent import ProductionAgent
from .publish_agent import PublishAgent
from .review_agent import ReviewAgent


@dataclass
class PipelineStrategy:
    """파이프라인 실행 전략"""
    image_style: str = "animation"
    voice: str = "chirp3:Charon"  # 기본: Chirp 3 HD 남성 음성
    bgm_mood: str = "calm"
    parallel_images: bool = True
    parallel_workers: int = 2
    premium_thumbnail: bool = False
    enable_shorts: bool = True
    max_retries: int = 3
    quality_threshold: float = 0.8


class VideoSupervisorAgent(BaseAgent):
    """영상 생성 총괄 에이전트"""

    def __init__(
        self,
        server_url: str = "http://localhost:5059",
        budget: float = 1.00
    ):
        super().__init__("VideoSupervisor", max_retries=1)
        self.server_url = server_url

        # 하위 에이전트 초기화
        self.analysis_agent = AnalysisAgent(server_url)
        self.audio_agent = AudioAgent(server_url)
        self.creative_agent = CreativeAgent(server_url)
        self.quality_agent = QualityAgent(server_url)
        self.production_agent = ProductionAgent(server_url)
        self.publish_agent = PublishAgent(server_url)
        self.review_agent = ReviewAgent(server_url)

        # 에이전트 레지스트리
        self.agents = {
            "analysis": self.analysis_agent,
            "audio": self.audio_agent,
            "creative": self.creative_agent,
            "quality": self.quality_agent,
            "production": self.production_agent,
            "publish": self.publish_agent,
            "review": self.review_agent,
        }

        # 예산 관리자
        self.budget = BudgetManager(total_budget=budget)

        # 기본 설정
        self.parallel_execution = True
        self.enable_quality_loop = True

    async def execute(self, context: VideoTaskContext, **kwargs) -> AgentResult:
        """
        전체 파이프라인 실행

        Args:
            context: 작업 컨텍스트
            **kwargs:
                skip_upload: 업로드 스킵 (테스트용)
                skip_shorts: 쇼츠 생성 스킵
                dry_run: 드라이런 (실제 생성 안함)

        Returns:
            AgentResult with final results
        """
        self.set_status(AgentStatus.RUNNING)
        start_time = time.time()

        skip_upload = kwargs.get("skip_upload", False)
        skip_shorts = kwargs.get("skip_shorts", False)

        self.log("=" * 50)
        self.log(f"🎬 영상 생성 파이프라인 시작")
        self.log(f"   Task ID: {context.task_id}")
        self.log(f"   대본 길이: {len(context.script)}자")
        self.log("=" * 50)

        context.add_log(self.name, "start", "running", f"Task: {context.task_id}")

        try:
            # ========================================
            # PHASE 0: 전략 수립
            # ========================================
            strategy = await self._plan_strategy(context)
            context.strategy = strategy.__dict__

            self.log(f"📋 전략 수립 완료: style={strategy.image_style}, voice={strategy.voice}")

            # ========================================
            # PHASE 1: 대본 분석
            # ========================================
            self.log("\n[Phase 1] 대본 분석")
            analysis_result = await self._run_analysis(context, strategy)

            if not analysis_result.success:
                return self._create_failure_result(
                    context, start_time,
                    f"대본 분석 실패: {analysis_result.error}"
                )

            # ========================================
            # PHASE 2: TTS + 자막 생성
            # ========================================
            self.log("\n[Phase 2] TTS + 자막 생성")
            audio_result = await self._run_audio(context, strategy)

            if not audio_result.success:
                return self._create_failure_result(
                    context, start_time,
                    f"TTS 생성 실패: {audio_result.error}"
                )

            # ========================================
            # PHASE 3: 이미지 + 썸네일 생성 (병렬)
            # ========================================
            self.log("\n[Phase 3] 이미지 + 썸네일 생성")
            creative_result = await self._run_creative_with_quality_loop(
                context, strategy
            )

            if not creative_result.success:
                return self._create_failure_result(
                    context, start_time,
                    f"이미지 생성 실패: {creative_result.error}"
                )

            # ========================================
            # PHASE 4: 영상 렌더링
            # ========================================
            self.log("\n[Phase 4] 영상 렌더링")
            production_result = await self._run_production(context)

            if not production_result.success:
                return self._create_failure_result(
                    context, start_time,
                    f"영상 생성 실패: {production_result.error}"
                )

            # ========================================
            # PHASE 5: 품질 최종 검증
            # ========================================
            self.log("\n[Phase 5] 최종 품질 검증")
            final_quality = await self.quality_agent.execute(
                context, check_type="video"
            )

            if not final_quality.success or final_quality.data.get("overall_score", 0) < 0.7:
                self.log(f"⚠️ 영상 품질 미달: {final_quality.feedback}", "warning")
                # 품질 미달이지만 계속 진행 (경고만)

            # ========================================
            # PHASE 6: YouTube 업로드
            # ========================================
            if not skip_upload:
                self.log("\n[Phase 6] YouTube 업로드")
                publish_result = await self._run_publish(context)

                if not publish_result.success:
                    return self._create_failure_result(
                        context, start_time,
                        f"업로드 실패: {publish_result.error}"
                    )

                # 쇼츠 생성
                if not skip_shorts and strategy.enable_shorts:
                    await self._run_shorts(context)

            # ========================================
            # 최종 결과 정리
            # ========================================
            duration = time.time() - start_time
            budget_report = self.budget.get_report()

            self.log("\n" + "=" * 50)
            self.log(f"✅ 파이프라인 완료!")
            self.log(f"   소요 시간: {duration:.1f}초 ({duration/60:.1f}분)")
            self.log(f"   총 비용: ${context.total_cost:.4f}")
            self.log(f"   영상 URL: {context.video_url}")
            if context.shorts_url:
                self.log(f"   쇼츠 URL: {context.shorts_url}")
            self.log("=" * 50)

            context.add_log(self.name, "complete", "success",
                           f"${context.total_cost:.4f}, {duration:.1f}s")

            self.set_status(AgentStatus.SUCCESS)

            return AgentResult(
                success=True,
                data={
                    "task_id": context.task_id,
                    "video_url": context.video_url,
                    "shorts_url": context.shorts_url,
                    "title": context.youtube_metadata.get("title") if context.youtube_metadata else None,
                    "total_cost": context.total_cost,
                    "cost_breakdown": context.cost_breakdown,
                    "quality_scores": context.quality_scores,
                    "budget_report": budget_report,
                    "logs": context.logs,
                },
                cost=context.total_cost,
                duration=duration
            )

        except Exception as e:
            self.set_status(AgentStatus.FAILED)
            context.add_log(self.name, "execute", "exception", str(e))
            return self._create_failure_result(context, start_time, str(e))

    async def _plan_strategy(self, context: VideoTaskContext) -> PipelineStrategy:
        """
        대본 분석 전 전략 수립

        대본 길이, 카테고리 추정, 채널 스타일 등을 고려하여 최적 전략 결정
        """
        strategy = PipelineStrategy()

        script_length = len(context.script)
        estimated_minutes = script_length / 910

        # 대본 길이에 따른 설정
        if estimated_minutes > 15:
            strategy.parallel_workers = 3  # 긴 영상은 더 많은 병렬 처리
            strategy.premium_thumbnail = True

        # 음성 설정
        if context.voice:
            strategy.voice = context.voice

        # 카테고리 추정 (키워드 기반)
        script_lower = context.script.lower()
        if any(kw in script_lower for kw in ["뉴스", "속보", "기자", "보도"]):
            strategy.image_style = "realistic"
            strategy.bgm_mood = "tense"
        elif any(kw in script_lower for kw in ["미스터리", "의문", "수수께끼", "진실"]):
            strategy.image_style = "cinematic"
            strategy.bgm_mood = "mysterious"
        elif any(kw in script_lower for kw in ["역사", "시대", "왕", "전쟁"]):
            strategy.image_style = "painting"
            strategy.bgm_mood = "epic"

        return strategy

    async def _run_analysis(
        self,
        context: VideoTaskContext,
        strategy: PipelineStrategy
    ) -> AgentResult:
        """대본 분석 실행"""
        # 채널 스타일 분석 - API 없으므로 비활성화
        # TODO: /api/channel/style 엔드포인트 구현 후 활성화
        channel_style = None
        # if context.channel_id:
        #     channel_style = await self.analysis_agent.analyze_channel_style(
        #         context.channel_id
        #     )

        result = await self.analysis_agent.execute_with_retry(
            context,
            channel_style=channel_style
        )

        if result.success:
            self.budget.spend("analysis", result.cost)

        return result

    async def _run_audio(
        self,
        context: VideoTaskContext,
        strategy: PipelineStrategy
    ) -> AgentResult:
        """TTS + 자막 생성"""
        result = await self.audio_agent.execute_with_retry(
            context,
            voice_override=strategy.voice
        )

        if result.success:
            self.budget.spend("audio", result.cost)

        return result

    async def _run_creative_with_quality_loop(
        self,
        context: VideoTaskContext,
        strategy: PipelineStrategy
    ) -> AgentResult:
        """
        이미지 + 썸네일 생성 (품질 피드백 루프 포함)

        품질 검증 → 미달 시 재생성 (최대 3회)
        """
        max_attempts = strategy.max_retries
        attempt = 0
        last_result = None

        while attempt < max_attempts:
            attempt += 1
            self.log(f"  이미지 생성 시도 {attempt}/{max_attempts}")

            # 이미지 생성
            if attempt == 1:
                result = await self.creative_agent.execute(
                    context,
                    parallel=strategy.parallel_images,
                    image_style=strategy.image_style
                )
            else:
                # 재생성: 실패한 이미지만
                failed_indices = last_result.data.get("failed_indices", []) if last_result else []
                result = await self.creative_agent.execute(
                    context,
                    parallel=strategy.parallel_images,
                    image_style=strategy.image_style,
                    failed_scenes=failed_indices,
                    feedback=last_result.feedback if last_result else None
                )

            self.budget.spend("creative", result.cost)

            if not result.success:
                last_result = result
                continue

            # 품질 검증
            if self.enable_quality_loop:
                quality = await self.quality_agent.execute(context, check_type="images")

                if quality.success and not quality.needs_improvement:
                    self.log(f"  ✓ 품질 검증 통과 (시도 {attempt})")
                    return result

                # 품질 미달
                self.log(f"  ⚠️ 품질 미달: {quality.feedback}")

                # 예산 재분배 시도
                if self.budget.get_remaining("reserve") > 0.05:
                    self.budget.reallocate("reserve", "creative", 0.05)
                    self.log("  💰 예산 재분배: reserve → creative $0.05")

                last_result = AgentResult(
                    success=False,
                    feedback=quality.feedback,
                    data=result.data
                )
            else:
                return result

        # 최대 시도 초과
        self.log(f"  ⚠️ 최대 시도 횟수 초과, 현재 결과 사용")
        return last_result if last_result else result

    async def _run_production(self, context: VideoTaskContext) -> AgentResult:
        """영상 렌더링"""
        result = await self.production_agent.execute_with_retry(context)

        if result.success:
            self.budget.spend("production", result.cost)

        return result

    async def _run_publish(self, context: VideoTaskContext) -> AgentResult:
        """YouTube 업로드"""
        result = await self.publish_agent.execute_with_retry(context)

        if result.success:
            self.budget.spend("publish", result.cost)

        return result

    async def _run_shorts(self, context: VideoTaskContext):
        """쇼츠 생성 및 업로드"""
        if not context.video_effects:
            return

        shorts_config = context.video_effects.get("shorts", {})
        highlight_scenes = shorts_config.get("highlight_scenes", [])

        if not highlight_scenes:
            self.log("  쇼츠: 하이라이트 씬 없음, 스킵")
            return

        self.log(f"  쇼츠 생성: 하이라이트 씬 {highlight_scenes}")

        # 쇼츠 영상 생성
        shorts_result = await self.production_agent.generate_shorts(
            context,
            highlight_scenes=highlight_scenes
        )

        if not shorts_result.success:
            self.log(f"  ⚠️ 쇼츠 생성 실패: {shorts_result.error}", "warning")
            return

        # 쇼츠 업로드
        shorts_path = shorts_result.data.get("shorts_path")
        if shorts_path:
            upload_result = await self.publish_agent.upload_shorts(
                context, shorts_path
            )

            if upload_result.success:
                self.log(f"  ✓ 쇼츠 업로드 완료: {context.shorts_url}")
            else:
                self.log(f"  ⚠️ 쇼츠 업로드 실패: {upload_result.error}", "warning")

    def _create_failure_result(
        self,
        context: VideoTaskContext,
        start_time: float,
        error: str
    ) -> AgentResult:
        """실패 결과 생성"""
        duration = time.time() - start_time

        self.log(f"\n❌ 파이프라인 실패: {error}")
        context.add_log(self.name, "execute", "failed", error)

        self.set_status(AgentStatus.FAILED)

        return AgentResult(
            success=False,
            error=error,
            data={
                "task_id": context.task_id,
                "total_cost": context.total_cost,
                "cost_breakdown": context.cost_breakdown,
                "logs": context.logs,
            },
            cost=context.total_cost,
            duration=duration
        )

    # =========================================================================
    # 편의 메서드
    # =========================================================================

    async def run(
        self,
        script: str,
        channel_id: str = "",
        title: str = "",
        voice: str = "chirp3:Charon",  # 기본: Chirp 3 HD 남성 음성
        privacy: str = "private",
        **kwargs
    ) -> AgentResult:
        """
        간편 실행 메서드

        사용법:
            supervisor = VideoSupervisorAgent()
            result = await supervisor.run(
                script="대본 내용...",
                channel_id="UCxxx",
                title="영상 제목"
            )

        Args:
            script: 대본
            channel_id: YouTube 채널 ID
            title: 영상 제목 (없으면 GPT가 생성)
            voice: TTS 음성
            privacy: 공개 설정 (public/private/unlisted)
            **kwargs: 추가 옵션

        Returns:
            AgentResult
        """
        context = VideoTaskContext(
            script=script,
            channel_id=channel_id,
            title_input=title,
            voice=voice,
            privacy_status=privacy,
        )

        return await self.execute(context, **kwargs)

    def run_sync(self, script: str, **kwargs) -> AgentResult:
        """동기 실행 메서드"""
        return asyncio.run(self.run(script, **kwargs))

    def get_status_report(self, context: VideoTaskContext) -> str:
        """현재 상태 리포트"""
        lines = [
            "=" * 50,
            f"📊 작업 상태 리포트",
            "=" * 50,
            f"Task ID: {context.task_id}",
            f"시트/행: {context.sheet_name} / {context.row_number}",
            "",
            "[진행 상황]",
            f"  분석: {'✓' if context.analysis_result else '○'} (시도 {context.analysis_attempts}회)",
            f"  TTS: {'✓' if context.tts_result else '○'} (시도 {context.tts_attempts}회)",
            f"  이미지: {'✓' if context.images else '○'} (시도 {context.image_attempts}회)",
            f"  영상: {'✓' if context.video_path else '○'} (시도 {context.video_attempts}회)",
            f"  업로드: {'✓' if context.video_url else '○'} (시도 {context.upload_attempts}회)",
            "",
            "[비용]",
            f"  총 비용: ${context.total_cost:.4f}",
        ]

        for agent, cost in context.cost_breakdown.items():
            lines.append(f"    - {agent}: ${cost:.4f}")

        lines.extend([
            "",
            "[품질 점수]",
        ])

        for target, score in context.quality_scores.items():
            lines.append(f"    - {target}: {score:.0%}")

        lines.extend([
            "",
            "[최근 로그]",
        ])

        for log in context.logs[-5:]:
            lines.append(f"  {log['timestamp']} [{log['agent']}] {log['action']}: {log['result']}")

        lines.append("=" * 50)

        return "\n".join(lines)

    def diagnose(self) -> str:
        """시스템 진단"""
        lines = [
            "=" * 50,
            "🔧 VideoSupervisor 시스템 진단",
            "=" * 50,
            "",
            "[에이전트 상태]",
        ]

        for name, agent in self.agents.items():
            status = agent.status.value if hasattr(agent, 'status') else "unknown"
            lines.append(f"  {name}: {status}")

        lines.extend([
            "",
            "[예산 현황]",
            f"  총 예산: ${self.budget.total_budget:.2f}",
            f"  사용: ${sum(self.budget.spent.values()):.4f}",
            f"  잔여: ${self.budget.get_total_remaining():.4f}",
            "",
            "[설정]",
            f"  병렬 실행: {self.parallel_execution}",
            f"  품질 루프: {self.enable_quality_loop}",
            f"  서버 URL: {self.server_url}",
        ])

        lines.append("=" * 50)

        return "\n".join(lines)
