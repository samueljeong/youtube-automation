"""
AnalysisAgent - 대본 분석 에이전트

역할:
- GPT-5.1로 대본 분석
- 씬 분할 및 나레이션 추출
- 카테고리 감지 (news/story/mystery)
- 유튜브 메타데이터 생성
- video_effects 생성 (BGM, SFX, 전환)
- 최적 전략 제안
"""

import asyncio
import time
import json
import re
import httpx
from typing import Any, Dict, List, Optional

from .base import BaseAgent, AgentResult, VideoTaskContext, AgentStatus


class AnalysisAgent(BaseAgent):
    """대본 분석 에이전트"""

    def __init__(self, server_url: str = "http://localhost:5059"):
        super().__init__("AnalysisAgent", max_retries=2)
        self.server_url = server_url
        self.timeout = 900  # 15분

    async def execute(self, context: VideoTaskContext, **kwargs) -> AgentResult:
        """
        대본 분석 실행

        Args:
            context: 작업 컨텍스트
            **kwargs:
                feedback: 이전 분석의 피드백
                channel_style: 채널 스타일 정보

        Returns:
            AgentResult with scenes, youtube metadata, video_effects
        """
        start_time = time.time()
        self.set_status(AgentStatus.RUNNING)
        context.analysis_attempts += 1

        feedback = kwargs.get("feedback")
        channel_style = kwargs.get("channel_style")

        try:
            # 대본 길이로 이미지 개수 계산
            script_length = len(context.script)
            estimated_minutes = script_length / 910  # 한국어 기준

            if estimated_minutes <= 8:
                image_count = 5
            elif estimated_minutes <= 10:
                image_count = 8
            elif estimated_minutes <= 15:
                image_count = 11
            else:
                image_count = 12

            self.log(f"대본 길이: {script_length}자, 예상 {estimated_minutes:.1f}분, 이미지 {image_count}개")

            # API 호출 데이터 준비
            payload = {
                "script": context.script,
                "content_type": "drama",
                "image_style": "animation",
                "image_count": image_count,
                "audience": "general",
                "output_language": "ko",
            }

            # 채널 스타일 추가
            if channel_style:
                payload["channel_style"] = channel_style

            # 피드백이 있으면 프롬프트에 반영
            if feedback:
                payload["additional_instructions"] = f"이전 분석 피드백: {feedback}"

            # API 호출
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.server_url}/api/image/analyze-script",
                    json=payload
                )
                response.raise_for_status()
                result = response.json()

            if not result.get("ok"):
                return AgentResult(
                    success=False,
                    error=result.get("error", "분석 실패"),
                    cost=result.get("cost", 0.03)
                )

            # 결과 저장
            context.analysis_result = result
            context.scenes = result.get("scenes", [])
            context.youtube_metadata = result.get("youtube", {})
            context.thumbnail_config = result.get("thumbnail", {})
            context.video_effects = result.get("video_effects", {})
            context.detected_category = result.get("detected_category", "story")

            # 사용자 입력 제목이 있으면 덮어쓰기
            if context.title_input:
                context.youtube_metadata["title"] = context.title_input

            # 사용자 입력 썸네일 문구가 있으면 덮어쓰기
            if context.thumbnail_text_input:
                lines = context.thumbnail_text_input.split("\n")
                context.thumbnail_config["user_text"] = {
                    "line1": lines[0] if len(lines) > 0 else "",
                    "line2": lines[1] if len(lines) > 1 else "",
                }

            duration = time.time() - start_time
            cost = result.get("cost", 0.03)
            context.add_cost("analysis", cost)

            self.log(f"분석 완료: {len(context.scenes)}개 씬, 카테고리={context.detected_category}")
            context.add_log(self.name, "analyze", "success", f"{len(context.scenes)} scenes, ${cost:.4f}")

            self.set_status(AgentStatus.SUCCESS)

            return AgentResult(
                success=True,
                data={
                    "scenes": context.scenes,
                    "youtube": context.youtube_metadata,
                    "thumbnail": context.thumbnail_config,
                    "video_effects": context.video_effects,
                    "detected_category": context.detected_category,
                    "image_count": image_count,
                },
                cost=cost,
                duration=duration
            )

        except httpx.TimeoutException:
            self.set_status(AgentStatus.FAILED)
            return AgentResult(
                success=False,
                error="대본 분석 타임아웃 (15분 초과)",
                cost=0.0
            )
        except Exception as e:
            self.set_status(AgentStatus.FAILED)
            context.add_log(self.name, "analyze", "error", str(e))
            return AgentResult(
                success=False,
                error=str(e),
                cost=0.0
            )

    async def analyze_channel_style(self, channel_id: str) -> Optional[Dict[str, Any]]:
        """
        채널 스타일 분석 (TUBELENS)

        7일 캐시를 사용하여 비용 절감
        """
        if not channel_id:
            return None

        try:
            async with httpx.AsyncClient(timeout=60) as client:
                response = await client.get(
                    f"{self.server_url}/api/channel/style",
                    params={"channel_id": channel_id}
                )
                if response.status_code == 200:
                    return response.json()
        except Exception as e:
            self.log(f"채널 스타일 분석 실패 (무시): {e}", "warning")

        return None

    def generate_strategy_recommendations(self, context: VideoTaskContext) -> Dict[str, Any]:
        """
        분석 결과를 바탕으로 전략 권장사항 생성

        슈퍼바이저가 이 권장사항을 참고하여 하위 에이전트 설정을 결정합니다.
        """
        recommendations = {
            "image_style": "animation",
            "voice": context.voice or "ko-KR-Neural2-C",
            "bgm_mood": "calm",
            "parallel_images": True,
            "premium_thumbnail": False,
        }

        if context.video_effects:
            recommendations["bgm_mood"] = context.video_effects.get("bgm_mood", "calm")

        # 카테고리별 추천
        category = context.detected_category
        if category == "news":
            recommendations["image_style"] = "realistic"
            recommendations["voice"] = "ko-KR-Neural2-A"  # 뉴스는 여성 음성
        elif category == "mystery":
            recommendations["image_style"] = "cinematic"
            recommendations["bgm_mood"] = "mysterious"
        elif category == "history":
            recommendations["image_style"] = "painting"
            recommendations["bgm_mood"] = "epic"

        # 대본 길이에 따른 추천
        script_length = len(context.script)
        if script_length > 15000:  # 15분 이상
            recommendations["parallel_images"] = True
            recommendations["premium_thumbnail"] = True  # 긴 영상은 썸네일 중요

        return recommendations
