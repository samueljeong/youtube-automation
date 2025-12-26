"""
AudioAgent - 오디오 에이전트

역할:
- TTS 생성 (Google Cloud / Gemini)
- 자막 동기화 (문장 단위)
- BGM 선택
- SFX 삽입 포인트 계획
"""

import asyncio
import time
import json
from typing import Any, Dict, List, Optional

import httpx

from .base import BaseAgent, AgentResult, VideoTaskContext, AgentStatus


class AudioAgent(BaseAgent):
    """오디오 에이전트 (TTS + BGM + SFX)"""

    def __init__(self, server_url: str = "http://localhost:5059"):
        super().__init__("AudioAgent", max_retries=2)
        self.server_url = server_url
        self.timeout = 600  # 10분

    async def execute(self, context: VideoTaskContext, **kwargs) -> AgentResult:
        """
        TTS + 자막 생성

        Args:
            context: 작업 컨텍스트
            **kwargs:
                feedback: 이전 생성의 피드백
                voice_override: 음성 오버라이드

        Returns:
            AgentResult with TTS data and subtitles
        """
        start_time = time.time()
        self.set_status(AgentStatus.RUNNING)
        context.tts_attempts += 1

        feedback = kwargs.get("feedback")
        voice_override = kwargs.get("voice_override")

        try:
            if not context.scenes:
                return AgentResult(
                    success=False,
                    error="씬 데이터 없음 - 먼저 분석을 실행하세요"
                )

            # 음성 결정
            voice = voice_override or context.voice or "ko-KR-Neural2-C"

            # 언어 감지
            language = self._detect_language(context.script)

            # session_id 생성 (원래 파이프라인과 동일한 패턴)
            session_id = f"agent_{context.task_id}_{int(time.time())}"
            self.log(f"TTS 생성 시작: {len(context.scenes)}개 씬, 음성={voice}, session={session_id}")

            # API 호출 데이터 준비
            payload = {
                "session_id": session_id,  # ★ session_id 전달 (영상 생성에 필요)
                "scenes": context.scenes,
                "language": language,
                "base_voice": voice,
            }

            # API 호출
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.server_url}/api/image/generate-assets-zip",
                    json=payload
                )
                response.raise_for_status()
                result = response.json()

            if not result.get("ok"):
                return AgentResult(
                    success=False,
                    error=result.get("error", "TTS 생성 실패"),
                    cost=result.get("cost", 0.0)
                )

            # 결과 저장 (session_id 명시적 추가 - API 응답에는 없음)
            result["session_id"] = session_id
            context.tts_result = result
            context.subtitles = result.get("subtitles", [])

            duration = time.time() - start_time
            cost = result.get("cost", 0.0)
            context.add_cost("audio", cost)

            # BGM 및 SFX 계획
            bgm_plan = self._plan_bgm(context)
            sfx_plan = self._plan_sfx(context)

            self.log(f"TTS 완료: {len(context.subtitles)}개 자막, ${cost:.4f}")
            context.add_log(self.name, "tts", "success", f"{len(context.subtitles)} subtitles, ${cost:.4f}")

            self.set_status(AgentStatus.SUCCESS)

            return AgentResult(
                success=True,
                data={
                    "tts_result": context.tts_result,
                    "subtitles": context.subtitles,
                    "session_id": result.get("session_id"),
                    "total_duration": result.get("total_duration"),
                    "bgm_plan": bgm_plan,
                    "sfx_plan": sfx_plan,
                    "voice": voice,
                    "language": language,
                },
                cost=cost,
                duration=duration
            )

        except httpx.TimeoutException:
            self.set_status(AgentStatus.FAILED)
            return AgentResult(
                success=False,
                error="TTS 생성 타임아웃 (10분 초과)",
                cost=0.0
            )
        except Exception as e:
            self.set_status(AgentStatus.FAILED)
            context.add_log(self.name, "tts", "error", str(e))
            return AgentResult(
                success=False,
                error=str(e),
                cost=0.0
            )

    def _detect_language(self, text: str) -> str:
        """텍스트에서 언어 감지"""
        if not text:
            return "ko"

        # 간단한 언어 감지 (한글 비율)
        korean_chars = sum(1 for c in text if '\uac00' <= c <= '\ud7a3')
        total_chars = len(text.replace(" ", ""))

        if total_chars == 0:
            return "ko"

        korean_ratio = korean_chars / total_chars

        if korean_ratio > 0.3:
            return "ko"
        elif any('\u3040' <= c <= '\u30ff' for c in text):  # 일본어
            return "ja"
        else:
            return "en"

    def _plan_bgm(self, context: VideoTaskContext) -> Dict[str, Any]:
        """
        BGM 계획 수립

        video_effects의 bgm_mood와 scene_bgm_changes를 기반으로 계획
        """
        if not context.video_effects:
            return {"mood": "calm", "changes": []}

        return {
            "mood": context.video_effects.get("bgm_mood", "calm"),
            "changes": context.video_effects.get("scene_bgm_changes", []),
        }

    def _plan_sfx(self, context: VideoTaskContext) -> List[Dict[str, Any]]:
        """
        SFX 삽입 계획 수립

        video_effects의 sound_effects를 기반으로 계획
        """
        if not context.video_effects:
            return []

        return context.video_effects.get("sound_effects", [])

    async def regenerate_scene(
        self,
        context: VideoTaskContext,
        scene_index: int,
        feedback: str
    ) -> AgentResult:
        """
        특정 씬의 TTS만 재생성

        품질 검증에서 특정 씬만 문제가 있을 때 사용
        """
        self.log(f"씬 {scene_index} TTS 재생성: {feedback}")

        try:
            if scene_index >= len(context.scenes):
                return AgentResult(
                    success=False,
                    error=f"씬 인덱스 초과: {scene_index}"
                )

            scene = context.scenes[scene_index]

            # 단일 씬 TTS 생성
            payload = {
                "scenes": [scene],
                "language": self._detect_language(scene.get("narration", "")),
                "base_voice": context.voice,
            }

            async with httpx.AsyncClient(timeout=120) as client:
                response = await client.post(
                    f"{self.server_url}/api/drama/generate-tts",
                    json=payload
                )
                response.raise_for_status()
                result = response.json()

            if result.get("ok"):
                # 기존 결과 업데이트
                # (실제 구현에서는 적절히 병합)
                return AgentResult(
                    success=True,
                    data={"scene_index": scene_index, "tts": result},
                    cost=result.get("cost", 0.0)
                )
            else:
                return AgentResult(
                    success=False,
                    error=result.get("error", "씬 TTS 재생성 실패")
                )

        except Exception as e:
            return AgentResult(
                success=False,
                error=str(e)
            )
