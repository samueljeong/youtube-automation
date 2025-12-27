"""
ProductionAgent - 제작 에이전트

역할:
- 씬별 클립 생성 (이미지 + 오디오)
- 자막 burn-in
- 전환 효과 적용
- BGM/SFX 믹싱
- 최종 영상 렌더링
- 영상 검증
"""

import asyncio
import time
import json
from typing import Any, Dict, List, Optional, Tuple

import httpx

from .base import BaseAgent, AgentResult, VideoTaskContext, AgentStatus


class ProductionAgent(BaseAgent):
    """제작 에이전트 (FFmpeg 영상 생성)"""

    def __init__(self, server_url: str = "http://localhost:5059"):
        super().__init__("ProductionAgent", max_retries=2)
        self.server_url = server_url
        self.poll_interval = 2  # 폴링 간격 (초)
        self.max_poll_time = 2400  # 최대 40분

    async def execute(self, context: VideoTaskContext, **kwargs) -> AgentResult:
        """
        영상 생성

        Args:
            context: 작업 컨텍스트
            **kwargs:
                skip_validation: 검증 스킵 여부
                transitions: 전환 효과 설정

        Returns:
            AgentResult with video path
        """
        start_time = time.time()
        self.set_status(AgentStatus.RUNNING)
        context.video_attempts += 1

        skip_validation = kwargs.get("skip_validation", False)

        try:
            if not context.scenes or not context.tts_result:
                return AgentResult(
                    success=False,
                    error="씬 또는 TTS 데이터 없음"
                )

            self.log(f"영상 생성 시작: {len(context.scenes)}개 씬")

            # 세션 ID 가져오기
            session_id = context.tts_result.get("session_id")
            if not session_id:
                return AgentResult(
                    success=False,
                    error="세션 ID 없음"
                )

            # video_effects 준비
            video_effects = context.video_effects or {}

            # API 호출
            payload = {
                "session_id": session_id,
                "scenes": context.scenes,
                "language": context.tts_result.get("language", "ko"),
                "video_effects": video_effects,
            }

            # 영상 생성 요청 (비동기)
            async with httpx.AsyncClient(timeout=60) as client:
                response = await client.post(
                    f"{self.server_url}/api/image/generate-video",
                    json=payload
                )
                response.raise_for_status()
                result = response.json()

            if not result.get("ok"):
                return AgentResult(
                    success=False,
                    error=result.get("error", "영상 생성 요청 실패")
                )

            job_id = result.get("job_id")
            if not job_id:
                return AgentResult(
                    success=False,
                    error="작업 ID 없음"
                )

            self.log(f"영상 생성 작업 시작: job_id={job_id}")

            # 상태 폴링
            video_result = await self._poll_video_status(job_id)

            if not video_result.get("ok"):
                return AgentResult(
                    success=False,
                    error=video_result.get("error", "영상 생성 실패")
                )

            # 결과 저장
            context.video_path = video_result.get("video_path")

            # video_path가 없으면 실패 처리
            if not context.video_path:
                return AgentResult(
                    success=False,
                    error="영상 생성 완료했으나 video_path 없음"
                )

            duration = time.time() - start_time

            self.log(f"영상 생성 완료: {context.video_path}, {duration:.1f}초")
            context.add_log(
                self.name, "render", "success",
                f"path={context.video_path}, duration={duration:.1f}s"
            )

            self.set_status(AgentStatus.SUCCESS)

            return AgentResult(
                success=True,
                data={
                    "video_path": context.video_path,
                    "job_id": job_id,
                    "render_duration": duration,
                },
                cost=0.0,  # FFmpeg는 무료
                duration=duration
            )

        except httpx.TimeoutException:
            self.set_status(AgentStatus.FAILED)
            return AgentResult(
                success=False,
                error="영상 생성 요청 타임아웃"
            )
        except Exception as e:
            self.set_status(AgentStatus.FAILED)
            context.add_log(self.name, "render", "error", str(e))
            return AgentResult(
                success=False,
                error=str(e)
            )

    async def _poll_video_status(self, job_id: str) -> Dict[str, Any]:
        """
        영상 생성 상태 폴링

        Args:
            job_id: 작업 ID

        Returns:
            최종 결과
        """
        start_time = time.time()

        while True:
            elapsed = time.time() - start_time
            if elapsed > self.max_poll_time:
                return {"ok": False, "error": "영상 생성 타임아웃 (40분 초과)"}

            try:
                async with httpx.AsyncClient(timeout=30) as client:
                    response = await client.get(
                        f"{self.server_url}/api/image/video-status/{job_id}"
                    )
                    response.raise_for_status()
                    status = response.json()

                state = status.get("status", "unknown")

                if state == "completed":
                    # API는 video_url 반환 (URL 경로: /uploads/xxx.mp4)
                    video_url = status.get("video_url") or status.get("video_path")

                    # URL 경로를 파일 경로로 변환 (/uploads/xxx.mp4 → uploads/xxx.mp4)
                    if video_url and video_url.startswith("/"):
                        video_path = video_url.lstrip("/")
                    else:
                        video_path = video_url

                    return {
                        "ok": True,
                        "video_path": video_path,
                        "duration": status.get("duration"),
                    }
                elif state == "failed":
                    return {
                        "ok": False,
                        "error": status.get("error", "영상 생성 실패")
                    }
                elif state in ["pending", "processing"]:
                    progress = status.get("progress", 0)
                    self.log(f"영상 생성 중: {progress}% ({elapsed:.0f}초 경과)")
                else:
                    self.log(f"알 수 없는 상태: {state}", "warning")

            except Exception as e:
                self.log(f"상태 확인 실패: {e}", "warning")

            await asyncio.sleep(self.poll_interval)

    async def generate_shorts(
        self,
        context: VideoTaskContext,
        highlight_scenes: List[int],
        max_duration: int = 60
    ) -> AgentResult:
        """
        쇼츠 영상 생성

        Args:
            context: 작업 컨텍스트
            highlight_scenes: 하이라이트 씬 인덱스
            max_duration: 최대 길이 (초)

        Returns:
            AgentResult with shorts video path
        """
        if not context.video_path:
            return AgentResult(
                success=False,
                error="메인 영상이 없음"
            )

        self.log(f"쇼츠 생성: 하이라이트 씬={highlight_scenes}")

        try:
            shorts_config = context.video_effects.get("shorts", {}) if context.video_effects else {}

            payload = {
                "video_path": context.video_path,
                "highlight_scenes": highlight_scenes,
                "max_duration": max_duration,
                "hook_text": shorts_config.get("hook_text", ""),
                "title": shorts_config.get("title", ""),
            }

            async with httpx.AsyncClient(timeout=300) as client:
                response = await client.post(
                    f"{self.server_url}/api/shorts/generate",
                    json=payload
                )
                response.raise_for_status()
                result = response.json()

            if result.get("ok"):
                return AgentResult(
                    success=True,
                    data={
                        "shorts_path": result.get("shorts_path"),
                        "duration": result.get("duration"),
                    },
                    cost=0.0
                )
            else:
                return AgentResult(
                    success=False,
                    error=result.get("error", "쇼츠 생성 실패")
                )

        except Exception as e:
            return AgentResult(
                success=False,
                error=str(e)
            )
