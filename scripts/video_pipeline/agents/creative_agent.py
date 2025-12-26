"""
CreativeAgent - 창작 에이전트

역할:
- 씬별 이미지 생성 (병렬)
- 썸네일 생성 (Gemini 3 Pro)
- 스타일 일관성 유지
- 캐시 활용 최적화
"""

import asyncio
import time
import json
from typing import Any, Dict, List, Optional, Tuple

import httpx

from .base import BaseAgent, AgentResult, VideoTaskContext, AgentStatus


class CreativeAgent(BaseAgent):
    """창작 에이전트 (이미지 + 썸네일)"""

    def __init__(self, server_url: str = "http://localhost:5059"):
        super().__init__("CreativeAgent", max_retries=2)
        self.server_url = server_url
        self.image_timeout = 60  # 이미지당 60초
        self.thumbnail_timeout = 180  # 썸네일 180초

    async def execute(self, context: VideoTaskContext, **kwargs) -> AgentResult:
        """
        이미지 + 썸네일 생성

        Args:
            context: 작업 컨텍스트
            **kwargs:
                feedback: 이전 생성의 피드백
                failed_scenes: 재생성이 필요한 씬 인덱스 목록
                parallel: 병렬 실행 여부 (기본 True)
                image_style: 이미지 스타일 오버라이드

        Returns:
            AgentResult with images and thumbnail
        """
        start_time = time.time()
        self.set_status(AgentStatus.RUNNING)
        context.image_attempts += 1

        feedback = kwargs.get("feedback")
        failed_scenes = kwargs.get("failed_scenes", [])
        use_parallel = kwargs.get("parallel", True)
        image_style = kwargs.get("image_style", "animation")

        try:
            if not context.scenes:
                return AgentResult(
                    success=False,
                    error="씬 데이터 없음 - 먼저 분석을 실행하세요"
                )

            total_cost = 0.0

            # 1. 이미지 생성
            if use_parallel:
                images, image_cost = await self._generate_images_parallel(
                    context, failed_scenes, image_style
                )
            else:
                images, image_cost = await self._generate_images_sequential(
                    context, failed_scenes, image_style
                )

            total_cost += image_cost
            context.images = images

            # 2. 썸네일 생성
            thumbnail_path, thumbnail_cost = await self._generate_thumbnail(context)
            total_cost += thumbnail_cost
            context.thumbnail_path = thumbnail_path

            duration = time.time() - start_time
            context.add_cost("creative", total_cost)

            # 성공 여부 판단
            successful_images = sum(1 for img in images if img is not None)
            total_images = len(context.scenes)

            self.log(f"생성 완료: 이미지 {successful_images}/{total_images}, 썸네일 {'O' if thumbnail_path else 'X'}")
            context.add_log(
                self.name, "create", "success",
                f"{successful_images}/{total_images} images, thumbnail={'yes' if thumbnail_path else 'no'}, ${total_cost:.4f}"
            )

            self.set_status(AgentStatus.SUCCESS)

            return AgentResult(
                success=successful_images >= total_images * 0.8,  # 80% 이상 성공
                data={
                    "images": images,
                    "thumbnail_path": thumbnail_path,
                    "successful_count": successful_images,
                    "total_count": total_images,
                    "failed_indices": [i for i, img in enumerate(images) if img is None],
                },
                cost=total_cost,
                duration=duration,
                needs_improvement=successful_images < total_images,
                improvement_targets=["images"] if successful_images < total_images else []
            )

        except Exception as e:
            self.set_status(AgentStatus.FAILED)
            context.add_log(self.name, "create", "error", str(e))
            return AgentResult(
                success=False,
                error=str(e),
                cost=0.0
            )

    async def _generate_images_parallel(
        self,
        context: VideoTaskContext,
        failed_scenes: List[int],
        image_style: str
    ) -> Tuple[List[Optional[str]], float]:
        """
        이미지 병렬 생성

        Args:
            context: 작업 컨텍스트
            failed_scenes: 재생성할 씬 인덱스 (빈 리스트면 전체)
            image_style: 이미지 스타일

        Returns:
            (이미지 경로 목록, 총 비용)
        """
        scenes_to_generate = failed_scenes if failed_scenes else range(len(context.scenes))

        self.log(f"이미지 병렬 생성: {len(list(scenes_to_generate))}개 씬")

        # 기존 이미지 복사 (재생성 대상이 아닌 것)
        images = context.images[:] if context.images else [None] * len(context.scenes)

        # 병렬 태스크 생성
        tasks = []
        for i in scenes_to_generate:
            if i < len(context.scenes):
                scene = context.scenes[i]
                tasks.append(self._generate_single_image(scene, i, image_style))

        # 병렬 실행
        results = await asyncio.gather(*tasks, return_exceptions=True)

        total_cost = 0.0
        for idx, result in zip(scenes_to_generate, results):
            if isinstance(result, Exception):
                self.log(f"이미지 {idx} 생성 실패: {result}", "warning")
                images[idx] = None
            elif result:
                images[idx] = result.get("image_path")
                total_cost += result.get("cost", 0.02)

        return images, total_cost

    async def _generate_images_sequential(
        self,
        context: VideoTaskContext,
        failed_scenes: List[int],
        image_style: str
    ) -> Tuple[List[Optional[str]], float]:
        """이미지 순차 생성 (병렬 비활성화 시)"""
        scenes_to_generate = failed_scenes if failed_scenes else range(len(context.scenes))

        self.log(f"이미지 순차 생성: {len(list(scenes_to_generate))}개 씬")

        images = context.images[:] if context.images else [None] * len(context.scenes)
        total_cost = 0.0

        for i in scenes_to_generate:
            if i < len(context.scenes):
                scene = context.scenes[i]
                try:
                    result = await self._generate_single_image(scene, i, image_style)
                    images[i] = result.get("image_path")
                    total_cost += result.get("cost", 0.02)
                except Exception as e:
                    self.log(f"이미지 {i} 생성 실패: {e}", "warning")
                    images[i] = None

        return images, total_cost

    async def _generate_single_image(
        self,
        scene: Dict[str, Any],
        index: int,
        style: str
    ) -> Dict[str, Any]:
        """
        단일 이미지 생성

        Args:
            scene: 씬 데이터
            index: 씬 인덱스
            style: 이미지 스타일

        Returns:
            {"image_path": ..., "cost": ...}
        """
        prompt = scene.get("image_prompt") or scene.get("description", "")

        if not prompt:
            return {"image_path": None, "cost": 0.0}

        payload = {
            "prompt": prompt,
            "style": style,
            "scene_index": index,
        }

        async with httpx.AsyncClient(timeout=self.image_timeout) as client:
            response = await client.post(
                f"{self.server_url}/api/drama/generate-image",
                json=payload
            )
            response.raise_for_status()
            result = response.json()

        if result.get("ok"):
            return {
                "image_path": result.get("image_path"),
                "cost": result.get("cost", 0.02)
            }
        else:
            raise Exception(result.get("error", "이미지 생성 실패"))

    async def _generate_thumbnail(
        self,
        context: VideoTaskContext
    ) -> Tuple[Optional[str], float]:
        """
        썸네일 생성

        Args:
            context: 작업 컨텍스트

        Returns:
            (썸네일 경로, 비용)
        """
        self.log("썸네일 생성 시작")

        try:
            # 썸네일 설정 준비
            thumbnail_config = context.thumbnail_config or {}
            title = context.youtube_metadata.get("title", "") if context.youtube_metadata else ""

            # 사용자 입력 썸네일 문구 우선
            user_text = thumbnail_config.get("user_text", {})

            payload = {
                "title": title,
                "thumbnail_config": thumbnail_config,
                "script_summary": context.script[:500] if context.script else "",
            }

            if user_text:
                payload["text_line1"] = user_text.get("line1", "")
                payload["text_line2"] = user_text.get("line2", "")

            async with httpx.AsyncClient(timeout=self.thumbnail_timeout) as client:
                response = await client.post(
                    f"{self.server_url}/api/thumbnail-ai/generate-single",
                    json=payload
                )
                response.raise_for_status()
                result = response.json()

            if result.get("ok"):
                return result.get("thumbnail_path"), result.get("cost", 0.03)
            else:
                self.log(f"썸네일 생성 실패: {result.get('error')}", "warning")
                return None, 0.0

        except Exception as e:
            self.log(f"썸네일 생성 예외: {e}", "warning")
            return None, 0.0

    async def regenerate_failed_images(
        self,
        context: VideoTaskContext,
        failed_indices: List[int],
        feedback: Optional[str] = None
    ) -> AgentResult:
        """
        실패한 이미지만 재생성

        품질 검증 후 특정 이미지만 재생성할 때 사용
        """
        self.log(f"이미지 재생성: {failed_indices}")

        return await self.execute(
            context,
            failed_scenes=failed_indices,
            feedback=feedback
        )
