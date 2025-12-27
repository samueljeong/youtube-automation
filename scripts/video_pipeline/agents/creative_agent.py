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
        self.image_timeout = 300  # 이미지당 5분 (Gemini는 2-3분 소요)
        self.thumbnail_timeout = 300  # 썸네일 5분

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

            # ★ scenes에 이미지 URL 반영 (영상 생성에 필요)
            for idx, image_path in enumerate(images):
                if image_path and idx < len(context.scenes):
                    context.scenes[idx]['image_url'] = image_path

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
        이미지 배치 병렬 생성 (한 번에 2개씩)

        Gemini API는 순차 처리하므로 모든 요청을 동시에 보내면 타임아웃 발생.
        2개씩 배치로 처리하여 안정성 확보.

        Args:
            context: 작업 컨텍스트
            failed_scenes: 재생성할 씬 인덱스 (빈 리스트면 전체)
            image_style: 이미지 스타일

        Returns:
            (이미지 경로 목록, 총 비용)
        """
        scenes_to_generate = list(failed_scenes if failed_scenes else range(len(context.scenes)))

        self.log(f"이미지 배치 생성: {len(scenes_to_generate)}개 씬 (2개씩 병렬)")

        # 기존 이미지 복사 (재생성 대상이 아닌 것)
        images = context.images[:] if context.images else [None] * len(context.scenes)
        total_cost = 0.0

        # 2개씩 배치 처리 (Gemini 순차 처리 대응)
        batch_size = 2
        for batch_start in range(0, len(scenes_to_generate), batch_size):
            batch_indices = scenes_to_generate[batch_start:batch_start + batch_size]
            batch_num = batch_start // batch_size + 1
            total_batches = (len(scenes_to_generate) + batch_size - 1) // batch_size

            self.log(f"배치 {batch_num}/{total_batches}: 씬 {batch_indices}")

            # 배치 태스크 생성
            tasks = []
            for i in batch_indices:
                if i < len(context.scenes):
                    scene = context.scenes[i]
                    tasks.append(self._generate_single_image(scene, i, image_style))

            # 배치 실행
            results = await asyncio.gather(*tasks, return_exceptions=True)

            for idx, result in zip(batch_indices, results):
                if isinstance(result, Exception):
                    error_type = type(result).__name__
                    error_msg = str(result) or "(빈 메시지)"
                    self.log(f"이미지 {idx} 생성 실패: [{error_type}] {error_msg}", "warning")
                    images[idx] = None
                elif result:
                    image_path = result.get("image_path")
                    if image_path:
                        # URL 경로를 파일 경로로 변환 (/uploads/xxx → uploads/xxx)
                        if image_path.startswith("/"):
                            image_path = image_path.lstrip("/")
                        images[idx] = image_path
                        total_cost += result.get("cost", 0.02)
                    else:
                        self.log(f"이미지 {idx} 결과에 image_path 없음: {result}", "warning")
                        images[idx] = None
                else:
                    self.log(f"이미지 {idx} 결과가 None 또는 빈 값", "warning")
                    images[idx] = None

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
            self.log(f"씬 {index}: 프롬프트 없음", "warning")
            return {"image_path": None, "cost": 0.0}

        payload = {
            "prompt": prompt,
            "size": "1280x720",  # 기존 파이프라인과 동일 (16:9)
            "imageProvider": "gemini",
            "scene_index": index,
        }

        try:
            async with httpx.AsyncClient(timeout=self.image_timeout) as client:
                response = await client.post(
                    f"{self.server_url}/api/drama/generate-image",
                    json=payload
                )
                response.raise_for_status()
                result = response.json()
        except httpx.TimeoutException:
            raise Exception(f"씬 {index} 타임아웃 ({self.image_timeout}초)")
        except httpx.ConnectError as e:
            raise Exception(f"씬 {index} 연결 실패: {e}")
        except httpx.HTTPStatusError as e:
            raise Exception(f"씬 {index} HTTP {e.response.status_code}: {e.response.text[:100]}")

        if result.get("ok"):
            # API 응답: imageUrl 또는 image_url (drama_server.py 호환)
            image_path = (
                result.get("imageUrl") or
                result.get("image_url") or
                result.get("image_path")
            )
            if not image_path:
                self.log(f"씬 {index}: API ok=true지만 이미지 경로 없음. 응답: {result}", "warning")
            return {
                "image_path": image_path,
                "cost": result.get("costUsd") or result.get("cost", 0.02)
            }
        else:
            error_msg = result.get("error") or f"API 응답: {result}"
            raise Exception(f"씬 {index}: {error_msg}")

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

            # 썸네일 프롬프트 구성 (API 형식에 맞춤)
            # ai_prompts가 있으면 A 프롬프트 사용, 없으면 기본 생성
            ai_prompts = thumbnail_config.get("ai_prompts", {})
            prompt_a = ai_prompts.get("A", {}) if ai_prompts else {}

            # 사용자 입력 또는 AI 생성 텍스트
            user_text = context.thumbnail_text_input or ""
            if user_text:
                # 줄바꿈으로 line1/line2 분리
                lines = user_text.split("\n")
                main_text = lines[0] if lines else ""
                sub_text = lines[1] if len(lines) > 1 else ""
            else:
                text_overlay = prompt_a.get("text_overlay", {})
                main_text = text_overlay.get("main", title[:20] if title else "")
                sub_text = text_overlay.get("sub", "")

            # 이미지 프롬프트 (ai_prompts.A.prompt 또는 기본)
            image_prompt = prompt_a.get("prompt", "")
            if not image_prompt:
                # 기본 프롬프트 생성
                image_prompt = f"Korean WEBTOON style YouTube thumbnail. Title: {title}. Style: Korean webtoon/manhwa illustration, exaggerated expression, clean bold outlines, vibrant colors, comic style. NO photorealistic. 16:9 aspect ratio."

            # API 형식으로 payload 구성
            payload = {
                "session_id": f"thumb_{context.task_id}",
                "prompt": {
                    "prompt": image_prompt,
                    "text_overlay": {"main": main_text, "sub": sub_text}
                },
                "category": context.detected_category or "story",
                "lang": "ko"
            }

            self.log(f"  - 프롬프트: {image_prompt[:50]}...")
            self.log(f"  - 텍스트: {main_text} / {sub_text}")

            async with httpx.AsyncClient(timeout=self.thumbnail_timeout) as client:
                response = await client.post(
                    f"{self.server_url}/api/thumbnail-ai/generate-single",
                    json=payload
                )
                response.raise_for_status()
                result = response.json()

            if result.get("ok"):
                thumbnail_path = result.get("thumbnail_path") or result.get("image_url")
                # URL 경로를 파일 경로로 변환 (/uploads/xxx → uploads/xxx)
                if thumbnail_path and thumbnail_path.startswith("/"):
                    thumbnail_path = thumbnail_path.lstrip("/")
                return thumbnail_path, result.get("cost", 0.03)
            else:
                self.log(f"썸네일 생성 실패: {result.get('error')}", "warning")
                return None, 0.0

        except httpx.TimeoutException:
            self.log(f"썸네일 생성 타임아웃 ({self.thumbnail_timeout}초)", "warning")
            return None, 0.0
        except httpx.ConnectError as e:
            self.log(f"썸네일 API 연결 실패: {e}", "warning")
            return None, 0.0
        except httpx.HTTPStatusError as e:
            self.log(f"썸네일 API HTTP {e.response.status_code}: {e.response.text[:100]}", "warning")
            return None, 0.0
        except Exception as e:
            error_type = type(e).__name__
            self.log(f"썸네일 생성 예외: [{error_type}] {e}", "warning")
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
