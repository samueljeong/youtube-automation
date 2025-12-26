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
                "output_language": "auto",  # ★ 자동 언어 감지 (원본 파이프라인과 동일)
            }

            # 채널 스타일 추가
            if channel_style:
                payload["channel_style"] = channel_style

            # 카테고리 추가 (시트에서 입력된 경우)
            if hasattr(context, 'input_category') and context.input_category:
                payload["category"] = context.input_category

            # 피드백이 있으면 프롬프트에 반영
            if feedback:
                payload["additional_instructions"] = f"이전 분석 피드백: {feedback}"

            # API 호출 (timeout 설정 상세화 + 연결 재시도)
            timeout_config = httpx.Timeout(
                timeout=self.timeout,
                connect=30.0,  # 연결 타임아웃 30초
                read=self.timeout,  # 읽기 타임아웃
                write=60.0,  # 쓰기 타임아웃
                pool=30.0  # 커넥션 풀 타임아웃
            )

            api_url = f"{self.server_url}/api/image/analyze-script"
            self.log(f"API 호출: {api_url}")

            # 연결 재시도 (최대 3회, 지수 백오프)
            result = None
            last_connect_error = None
            for connect_attempt in range(3):
                try:
                    async with httpx.AsyncClient(timeout=timeout_config) as client:
                        response = await client.post(api_url, json=payload)
                        response.raise_for_status()
                        result = response.json()
                        break  # 성공
                except httpx.ConnectError as ce:
                    last_connect_error = ce
                    self.log(f"연결 실패 (시도 {connect_attempt + 1}/3): {ce}", "warning")
                    if connect_attempt < 2:
                        await asyncio.sleep(2 ** connect_attempt)  # 1초, 2초, 4초
                    continue

            if result is None:
                raise httpx.ConnectError(f"API 서버 연결 실패 (3회 시도): {last_connect_error}")

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

            # ★ 전용 썸네일 분석 API 호출 (원본 파이프라인과 동일)
            # 더 나은 썸네일 프롬프트 생성을 위해 별도 API 호출
            await self._analyze_thumbnail(context)

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

            # ★★★ 대본 강제 분할 (원본 파이프라인과 동일) ★★★
            # GPT가 요약하지 못하도록 원본 대본을 씬별로 균등 분할
            self._force_split_script(context)

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

        except httpx.TimeoutException as e:
            self.set_status(AgentStatus.FAILED)
            self.log(f"타임아웃 오류: {e}", "error")
            return AgentResult(
                success=False,
                error="대본 분석 타임아웃 (15분 초과)",
                cost=0.0
            )
        except httpx.ConnectError as e:
            self.set_status(AgentStatus.FAILED)
            self.log(f"연결 오류: {e} (server_url={self.server_url})", "error")
            return AgentResult(
                success=False,
                error=f"API 서버 연결 실패: {self.server_url} - {e}",
                cost=0.0
            )
        except httpx.HTTPStatusError as e:
            self.set_status(AgentStatus.FAILED)
            self.log(f"HTTP 오류: {e.response.status_code} - {e.response.text[:200]}", "error")
            return AgentResult(
                success=False,
                error=f"API 오류 {e.response.status_code}: {e.response.text[:100]}",
                cost=0.0
            )
        except Exception as e:
            self.set_status(AgentStatus.FAILED)
            self.log(f"예외 발생: {type(e).__name__}: {e}", "error")
            context.add_log(self.name, "analyze", "error", str(e))
            return AgentResult(
                success=False,
                error=f"{type(e).__name__}: {e}",
                cost=0.0
            )

    def _force_split_script(self, context: VideoTaskContext) -> None:
        """
        대본 강제 분할 (원본 파이프라인과 동일)

        GPT가 대본을 요약하지 못하도록 원본 대본을 씬별로 균등 분할합니다.
        문장 단위로 자연스럽게 끊어서 배분합니다.
        """
        if not context.scenes or not context.script:
            return

        original_len = len(context.script)
        scene_count = len(context.scenes)

        # 문장 단위로 분할 (자연스러운 끊김)
        # 문장 종결 패턴: 마침표/물음표/느낌표 + 공백 또는 끝
        sentences = re.split(r'(?<=[.?!。？！])\s+', context.script)
        sentences = [s.strip() for s in sentences if s.strip()]

        if sentences:
            # 각 씬에 배정할 문장 수 계산
            sentences_per_scene = max(1, len(sentences) // scene_count)

            for i, scene in enumerate(context.scenes):
                start_idx = i * sentences_per_scene
                if i == scene_count - 1:
                    # 마지막 씬은 남은 모든 문장
                    end_idx = len(sentences)
                else:
                    end_idx = start_idx + sentences_per_scene

                scene_narration = ' '.join(sentences[start_idx:end_idx])
                scene['narration'] = scene_narration

            # 검증 로깅
            total_forced_len = sum(len(s.get('narration', '')) for s in context.scenes)
            self.log(f"대본 강제 분할: {original_len}자 → {total_forced_len}자 ({len(sentences)}문장 → 씬당 ~{sentences_per_scene}문장)")
        else:
            # 문장 분리 실패 시 글자수로 균등 분할
            chunk_size = len(context.script) // scene_count
            for i, scene in enumerate(context.scenes):
                start = i * chunk_size
                end = len(context.script) if i == scene_count - 1 else (i + 1) * chunk_size
                scene['narration'] = context.script[start:end]
            self.log(f"대본 글자수 분할: {original_len}자 → {scene_count}씬")

    async def _analyze_thumbnail(self, context: VideoTaskContext) -> None:
        """
        전용 썸네일 분석 API 호출 (원본 파이프라인과 동일)

        /api/thumbnail-ai/analyze 엔드포인트를 호출하여
        더 나은 썸네일 프롬프트(ai_prompts)를 생성합니다.
        """
        try:
            title = context.youtube_metadata.get("title", "") if context.youtube_metadata else ""

            async with httpx.AsyncClient(timeout=120) as client:
                response = await client.post(
                    f"{self.server_url}/api/thumbnail-ai/analyze",
                    json={
                        "script": context.script,
                        "title": title,
                    }
                )

                if response.status_code == 200:
                    result = response.json()
                    if result.get("ok"):
                        # prompts 구조: {"A": {"prompt": "...", "text_overlay": {...}}, "B": {...}}
                        ai_prompts = result.get("prompts", {})
                        if ai_prompts:
                            # thumbnail_config에 ai_prompts 추가
                            if not context.thumbnail_config:
                                context.thumbnail_config = {}
                            context.thumbnail_config["ai_prompts"] = ai_prompts
                            self.log(f"썸네일 분석 완료: {list(ai_prompts.keys())}")
                        else:
                            self.log("썸네일 분석 결과 비어있음 (폴백 사용)", "warning")
                    else:
                        self.log(f"썸네일 분석 실패: {result.get('error')} (폴백 사용)", "warning")
                else:
                    self.log(f"썸네일 분석 HTTP 오류: {response.status_code} (폴백 사용)", "warning")

        except httpx.ConnectError:
            self.log("썸네일 분석 API 연결 실패 (폴백 사용)", "warning")
        except Exception as e:
            self.log(f"썸네일 분석 예외: {e} (폴백 사용)", "warning")

    async def analyze_channel_style(self, channel_id: str) -> Optional[Dict[str, Any]]:
        """
        채널 스타일 분석 (TUBELENS)

        7일 캐시를 사용하여 비용 절감
        엔드포인트가 없으면 None 반환 (선택적 기능)
        """
        if not channel_id:
            return None

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.get(
                    f"{self.server_url}/api/channel/style",
                    params={"channel_id": channel_id}
                )
                if response.status_code == 200:
                    return response.json()
                elif response.status_code == 404:
                    # 엔드포인트 없음 - 정상적으로 무시
                    self.log("채널 스타일 API 없음 (무시)", "debug")
                    return None
                else:
                    self.log(f"채널 스타일 API 응답: {response.status_code}", "warning")
                    return None
        except httpx.ConnectError:
            # 연결 실패 - 무시하고 진행
            self.log("채널 스타일 API 연결 실패 (무시)", "debug")
            return None
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
