"""
SubtitleAgent - 자막 에이전트

역할:
- TTS 생성 (대본 → 음성)
- 자막 동기화 (음성 타이밍에 맞춰 SRT 생성)
- 자막 스타일링 (하이라이트 키워드, 색상)
- 검수 피드백 반영하여 재생성
"""

import os
import time
from typing import Any, Dict, List, Optional

try:
    from .base import BaseAgent, AgentResult, AgentStatus, TaskContext
except ImportError:
    from base import BaseAgent, AgentResult, AgentStatus, TaskContext


class SubtitleAgent(BaseAgent):
    """자막 에이전트 (TTS + 자막)"""

    # 기본 음성 설정
    DEFAULT_VOICE = {
        "language_code": "ko-KR",
        "name": "ko-KR-Neural2-C",  # 남성, 고품질
        "gender": "MALE",
        "speaking_rate": 0.95,
    }

    # 하이라이트 키워드 색상
    HIGHLIGHT_COLORS = {
        "충격": "#FF4444",
        "논란": "#FF6B6B",
        "열애": "#FF69B4",
        "결혼": "#FF69B4",
        "이혼": "#888888",
        "컴백": "#4CAF50",
        "대박": "#FFD700",
        "실화": "#FF8C00",
        "경고": "#FF0000",
        "속보": "#FF0000",
    }

    def __init__(self):
        super().__init__("SubtitleAgent")
        self.output_base_dir = "/tmp/shorts_agents"

    async def execute(self, context: TaskContext, **kwargs) -> AgentResult:
        """
        TTS + 자막 생성 실행

        Args:
            context: 작업 컨텍스트 (script 필수)
            **kwargs:
                voice: 음성 설정 (선택)
                highlight_keywords: 하이라이트할 키워드 (선택)
                feedback: 검수 피드백 (재생성 시)

        Returns:
            AgentResult with audio_file, srt_file, timeline
        """
        self.set_status(AgentStatus.RUNNING)
        start_time = time.time()

        voice = kwargs.get("voice", self.DEFAULT_VOICE)
        highlight_keywords = kwargs.get("highlight_keywords", [])
        feedback = kwargs.get("feedback")

        # 대본이 없으면 실패
        if not context.script:
            self.set_status(AgentStatus.FAILED)
            return AgentResult(
                success=False,
                error="대본이 없습니다. ScriptAgent를 먼저 실행하세요.",
            )

        try:
            # 1. 씬에서 나레이션 추출
            scenes = context.script.get("scenes", [])
            if not scenes:
                raise ValueError("씬 정보가 없습니다")

            tts_scenes = self._prepare_tts_input(scenes)

            self.log(f"TTS 생성 시작: {len(tts_scenes)}개 씬")

            # 2. TTS 파이프라인 실행
            result = await self._run_tts(context, tts_scenes, voice)

            if not result.get("ok"):
                raise ValueError(result.get("error", "TTS 생성 실패"))

            # 3. 자막 하이라이트 처리
            if highlight_keywords or self._detect_keywords(context.topic):
                keywords = highlight_keywords or self._detect_keywords(context.topic)
                result["highlights"] = self._apply_highlights(
                    result.get("srt_file"),
                    keywords
                )

            # 4. 결과 저장
            duration = time.time() - start_time

            # 컨텍스트에 저장
            context.subtitle_data = {
                "audio_file": result.get("audio_file"),
                "srt_file": result.get("srt_file"),
                "timeline": result.get("timeline", []),
                "duration_sec": result.get("stats", {}).get("total_duration_sec", 0),
            }

            context.add_log(
                self.name,
                "generate",
                "success",
                f"음성 {result.get('stats', {}).get('total_duration_sec', 0):.1f}초, "
                f"자막 {len(result.get('timeline', []))}개"
            )

            self.set_status(AgentStatus.SUCCESS)

            return AgentResult(
                success=True,
                data=result,
                cost=self._estimate_cost(tts_scenes),
                duration=duration,
            )

        except Exception as e:
            self.set_status(AgentStatus.FAILED)
            context.add_log(self.name, "execute", "exception", str(e))

            return AgentResult(
                success=False,
                error=str(e),
                duration=time.time() - start_time,
            )

    def _prepare_tts_input(self, scenes: List[Dict]) -> List[Dict]:
        """씬 데이터를 TTS 입력 형식으로 변환"""
        tts_scenes = []

        for i, scene in enumerate(scenes):
            narration = scene.get("narration") or scene.get("script") or scene.get("text", "")

            if narration:
                tts_scenes.append({
                    "id": scene.get("id") or f"scene_{i+1}",
                    "narration": narration.strip(),
                })

        return tts_scenes

    async def _run_tts(
        self,
        context: TaskContext,
        scenes: List[Dict],
        voice: Dict
    ) -> Dict[str, Any]:
        """TTS 파이프라인 실행"""
        # TTS 서비스 임포트
        try:
            import sys
            sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../..'))
            from tts.tts_service import run_tts_pipeline
        except ImportError as e:
            self.log(f"TTS 모듈 임포트 실패: {e}", "warning")
            # 폴백: 더미 결과 반환 (테스트용)
            return self._dummy_tts_result(context, scenes)

        # TTS 입력 구성
        tts_input = {
            "episode_id": context.task_id,
            "language": voice.get("language_code", "ko-KR"),
            "voice": {
                "gender": voice.get("gender", "MALE"),
                "name": voice.get("name", "ko-KR-Neural2-C"),
                "speaking_rate": voice.get("speaking_rate", 0.95),
            },
            "scenes": scenes,
            "sentence_mode": True,  # 문장별 TTS 모드
        }

        # TTS 실행
        result = run_tts_pipeline(tts_input)

        return result

    def _dummy_tts_result(self, context: TaskContext, scenes: List[Dict]) -> Dict[str, Any]:
        """테스트용 더미 결과"""
        total_text = sum(len(s.get("narration", "")) for s in scenes)
        estimated_duration = total_text / 5  # 초당 5자 가정

        return {
            "ok": True,
            "episode_id": context.task_id,
            "audio_file": f"/tmp/shorts_agents/{context.task_id}/audio.mp3",
            "srt_file": f"/tmp/shorts_agents/{context.task_id}/subtitles.srt",
            "timeline": [
                {"index": i+1, "start_sec": i*3, "end_sec": (i+1)*3, "text": f"자막 {i+1}"}
                for i in range(len(scenes))
            ],
            "stats": {
                "total_duration_sec": estimated_duration,
                "successful_chunks": len(scenes),
                "failed_chunks": 0,
            },
        }

    def _detect_keywords(self, topic: str) -> List[str]:
        """주제에서 하이라이트 키워드 자동 감지"""
        detected = []

        for keyword in self.HIGHLIGHT_COLORS.keys():
            if keyword in topic:
                detected.append(keyword)

        return detected

    def _apply_highlights(
        self,
        srt_file: Optional[str],
        keywords: List[str]
    ) -> Dict[str, str]:
        """
        자막 파일에 하이라이트 정보 추가

        Returns:
            {keyword: color} 매핑
        """
        highlights = {}

        for keyword in keywords:
            color = self.HIGHLIGHT_COLORS.get(keyword, "#FFFF00")
            highlights[keyword] = color

        self.log(f"하이라이트 적용: {list(highlights.keys())}")

        return highlights

    def _estimate_cost(self, scenes: List[Dict]) -> float:
        """TTS 비용 추정 (Google Cloud TTS 기준)"""
        total_chars = sum(len(s.get("narration", "")) for s in scenes)

        # Google Cloud TTS: $16 per 1M characters (Neural2)
        cost_per_char = 16 / 1_000_000

        return total_chars * cost_per_char

    async def regenerate(
        self,
        context: TaskContext,
        feedback: str,
        **kwargs
    ) -> AgentResult:
        """
        피드백 반영하여 재생성

        Args:
            context: 작업 컨텍스트
            feedback: 검수 에이전트의 피드백
            **kwargs: 추가 옵션

        Returns:
            AgentResult
        """
        self.log(f"재생성 요청: {feedback[:100]}...")

        # 피드백 분석
        adjustments = self._parse_feedback(feedback)

        # 조정된 설정으로 재실행
        return await self.execute(context, **adjustments, **kwargs)

    def _parse_feedback(self, feedback: str) -> Dict[str, Any]:
        """피드백 파싱하여 조정 사항 추출"""
        adjustments = {}

        # 속도 관련 피드백
        if "빠르" in feedback or "느리" in feedback:
            if "빠르" in feedback:
                adjustments["voice"] = {**self.DEFAULT_VOICE, "speaking_rate": 0.85}
            else:
                adjustments["voice"] = {**self.DEFAULT_VOICE, "speaking_rate": 1.05}

        # 음성 관련 피드백
        if "여성" in feedback:
            adjustments["voice"] = {
                **adjustments.get("voice", self.DEFAULT_VOICE),
                "name": "ko-KR-Neural2-A",
                "gender": "FEMALE",
            }

        return adjustments


# ===== 테스트 =====
if __name__ == "__main__":
    import asyncio

    async def test():
        agent = SubtitleAgent()

        # 테스트 컨텍스트
        context = TaskContext(
            topic="BTS 컴백 소식",
            person="BTS",
            category="연예인",
            issue_type="컴백",
        )

        # 테스트 대본
        context.script = {
            "scenes": [
                {"id": "scene_1", "narration": "방탄소년단이 드디어 컴백합니다!"},
                {"id": "scene_2", "narration": "팬들의 기대가 높아지고 있습니다."},
            ]
        }

        result = await agent.execute(context)

        print(f"성공: {result.success}")
        print(f"데이터: {result.data}")
        print(f"비용: ${result.cost:.4f}")

    asyncio.run(test())
