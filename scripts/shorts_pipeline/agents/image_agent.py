"""
ImageAgent - 이미지 생성 에이전트

역할:
- 씬별 이미지 생성 (썸네일 제외)
- 검수 피드백 반영하여 재생성
- 캐시된 이미지/프롬프트 재사용 (비용 절감)
"""

import os
import shutil
import time
from typing import Any, Dict, List, Optional

try:
    from .base import BaseAgent, AgentResult, AgentStatus, TaskContext
    from .image_cache import get_image_cache
except ImportError:
    from base import BaseAgent, AgentResult, AgentStatus, TaskContext
    from image_cache import get_image_cache


def generate_images_parallel(scenes, output_dir, max_workers=4):
    """
    씬 이미지 병렬 생성 (동적 임포트)
    """
    try:
        # 런타임에 임포트 시도
        import sys
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
        if project_root not in sys.path:
            sys.path.insert(0, project_root)

        from image import generate_image as main_generate_image
        from concurrent.futures import ThreadPoolExecutor, as_completed

        os.makedirs(output_dir, exist_ok=True)
        images = []
        failed = []

        print(f"[ImageAgent] 이미지 생성 시작: {len(scenes)}개 씬")

        def generate_single(scene):
            scene_num = scene.get("scene_number", 1)
            prompt = scene.get("image_prompt_enhanced", scene.get("image_prompt", ""))

            try:
                result = main_generate_image(
                    prompt=prompt,
                    aspect_ratio="1:1",
                    model="gemini-2.0-flash-exp"
                )

                if result.get("ok") and result.get("local_path"):
                    return {"ok": True, "scene": scene_num, "path": result["local_path"]}
                else:
                    return {"ok": False, "scene": scene_num, "error": result.get("error", "Unknown")}
            except Exception as e:
                return {"ok": False, "scene": scene_num, "error": str(e)}

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {executor.submit(generate_single, scene): scene for scene in scenes}

            for future in as_completed(futures):
                result = future.result()
                if result.get("ok"):
                    images.append(result)
                else:
                    failed.append(result)

        cost = len(images) * 0.05
        print(f"[ImageAgent] 이미지 생성 완료: {len(images)}개 성공, {len(failed)}개 실패")

        return {
            "ok": len(failed) == 0,
            "images": sorted(images, key=lambda x: x["scene"]),
            "failed": failed,
            "cost": round(cost, 3),
        }

    except ImportError as e:
        print(f"[ImageAgent] 이미지 모듈 임포트 실패: {e}")
        return {
            "ok": False,
            "images": [],
            "failed": [{"scene": i+1, "error": str(e)} for i in range(len(scenes))],
            "cost": 0,
        }


class ImageAgent(BaseAgent):
    """이미지 생성 에이전트"""

    def __init__(self):
        super().__init__("ImageAgent")
        self.max_workers = 4  # 병렬 워커 수
        self.output_base_dir = "/tmp/shorts_agents"

    async def execute(self, context: TaskContext, **kwargs) -> AgentResult:
        """
        이미지 생성 실행

        Args:
            context: 작업 컨텍스트 (script 필수)
            **kwargs:
                feedback: 검수 에이전트의 피드백 (개선 시)
                failed_scenes: 재생성할 씬 번호 리스트
                optimization: 슈퍼바이저가 제공한 최적화 정보 (캐시/템플릿)

        Returns:
            AgentResult with image paths
        """
        self.set_status(AgentStatus.RUNNING)
        start_time = time.time()

        feedback = kwargs.get("feedback")
        failed_scenes = kwargs.get("failed_scenes", [])
        optimization = kwargs.get("optimization")  # 슈퍼바이저의 최적화 정보

        # 대본이 없으면 실패
        if not context.script:
            self.set_status(AgentStatus.FAILED)
            return AgentResult(
                success=False,
                error="대본이 없습니다. ScriptAgent를 먼저 실행하세요.",
            )

        try:
            if feedback and failed_scenes:
                # 특정 씬만 재생성
                result = await self._regenerate_scenes(context, failed_scenes, feedback)
            elif optimization:
                # 최적화 정보 활용 (캐시 + 템플릿)
                result = await self._generate_with_optimization(context, optimization)
            else:
                # 전체 이미지 생성 (최적화 없이)
                result = await self._generate_all_images(context)

            duration = time.time() - start_time

            if result.get("ok") or len(result.get("images", [])) >= 4:  # 80% 이상 성공
                self.set_status(AgentStatus.SUCCESS)
                context.images = [img["path"] for img in result.get("images", [])]
                context.image_attempts += 1

                # 성공 로그에 캐시 정보 추가
                cache_info = ""
                if result.get("cache_used", 0) > 0:
                    cache_info = f", 캐시 {result.get('cache_used')}개"

                context.add_log(
                    self.name,
                    "regenerate" if failed_scenes else "generate",
                    "success",
                    f"{len(result.get('images', []))}개 이미지{cache_info}, ${result.get('cost', 0):.3f}"
                )

                return AgentResult(
                    success=True,
                    data=result,
                    cost=result.get("cost", 0),
                    duration=duration,
                )
            else:
                self.set_status(AgentStatus.FAILED)
                failed_info = result.get("failed", [])
                error_msg = f"이미지 생성 실패: {len(failed_info)}개 씬 실패"
                context.add_log(self.name, "generate", "failed", error_msg)

                return AgentResult(
                    success=False,
                    error=error_msg,
                    data=result,
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

    async def _generate_all_images(self, context: TaskContext) -> Dict[str, Any]:
        """전체 씬 이미지 생성"""
        self.log(f"이미지 생성 시작: {context.task_id}")

        scenes = context.script.get("scenes", [])
        if not scenes:
            return {"ok": False, "error": "씬 정보가 없습니다", "images": [], "failed": []}

        output_dir = os.path.join(self.output_base_dir, context.task_id, "images")
        os.makedirs(output_dir, exist_ok=True)

        result = generate_images_parallel(
            scenes=scenes,
            output_dir=output_dir,
            max_workers=self.max_workers
        )

        return result

    async def _generate_with_optimization(
        self,
        context: TaskContext,
        optimization: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        최적화 정보를 활용한 이미지 생성

        - 캐시된 이미지: 복사만 수행 (비용 0)
        - 템플릿 프롬프트: 템플릿으로 생성 (일관성 ↑)
        - 새 프롬프트: 생성 후 캐시에 저장

        Args:
            context: 작업 컨텍스트
            optimization: 슈퍼바이저가 제공한 최적화 정보
                - optimized_scenes: [{scene, prompt, use_cache, generate, image_path?}, ...]
                - issue_type: 이슈 타입 (캐시 키로 사용)

        Returns:
            생성 결과 (images, failed, cost, cache_used)
        """
        self.log(f"최적화 이미지 생성 시작: {context.task_id}")

        optimized_scenes = optimization.get("optimized_scenes", [])
        issue_type = optimization.get("issue_type", "default")

        if not optimized_scenes:
            # 최적화 정보 없으면 일반 생성
            return await self._generate_all_images(context)

        output_dir = os.path.join(self.output_base_dir, context.task_id, "images")
        os.makedirs(output_dir, exist_ok=True)

        images = []
        failed = []
        scenes_to_generate = []
        cache_used = 0
        total_cost = 0

        # 1단계: 캐시된 이미지 복사, 생성 필요한 씬 분리
        for opt_scene in optimized_scenes:
            scene_num = opt_scene.get("scene")
            cached_path = opt_scene.get("image_path")

            if opt_scene.get("use_cache") and cached_path and os.path.exists(cached_path):
                # 캐시 히트: 파일 복사
                dest_path = os.path.join(output_dir, f"scene_{scene_num:03d}.png")
                try:
                    shutil.copy2(cached_path, dest_path)
                    images.append({"ok": True, "scene": scene_num, "path": dest_path, "from_cache": True})
                    cache_used += 1
                    self.log(f"씬{scene_num} 캐시 사용: {cached_path}")
                except Exception as e:
                    self.log(f"씬{scene_num} 캐시 복사 실패, 재생성 필요: {e}", "warning")
                    scenes_to_generate.append({
                        "scene_number": scene_num,
                        "image_prompt_enhanced": opt_scene.get("prompt", ""),
                    })
            elif opt_scene.get("generate"):
                # 생성 필요
                scenes_to_generate.append({
                    "scene_number": scene_num,
                    "image_prompt_enhanced": opt_scene.get("prompt", ""),
                })

        self.log(f"캐시 사용: {cache_used}개, 생성 필요: {len(scenes_to_generate)}개")

        # 2단계: 필요한 씬만 병렬 생성
        if scenes_to_generate:
            gen_result = generate_images_parallel(
                scenes=scenes_to_generate,
                output_dir=output_dir,
                max_workers=self.max_workers
            )

            # 생성된 이미지 추가
            for img in gen_result.get("images", []):
                images.append(img)

                # 성공한 이미지는 캐시에 저장
                if img.get("ok") or img.get("path"):
                    scene_num = img.get("scene")
                    # 해당 씬의 프롬프트 찾기
                    for scene in scenes_to_generate:
                        if scene.get("scene_number") == scene_num:
                            prompt = scene.get("image_prompt_enhanced", "")
                            self._save_to_cache(issue_type, scene_num, prompt, img.get("path"))
                            break

            failed.extend(gen_result.get("failed", []))
            total_cost = gen_result.get("cost", 0)

        # 결과 정렬 (씬 번호 순)
        images = sorted(images, key=lambda x: x.get("scene", 0))

        return {
            "ok": len(failed) == 0,
            "images": images,
            "failed": failed,
            "cost": total_cost,
            "cache_used": cache_used,
            "generated": len(scenes_to_generate) - len(failed),
        }

    def _save_to_cache(self, issue_type: str, scene_num: int, prompt: str, image_path: str):
        """성공한 프롬프트를 캐시에 저장"""
        try:
            cache = get_image_cache()
            cache.save_successful_prompt(
                issue_type=issue_type,
                scene_number=scene_num,
                prompt=prompt,
                image_path=image_path
            )
            self.log(f"캐시 저장: {issue_type}_scene{scene_num}")
        except Exception as e:
            self.log(f"캐시 저장 실패 (무시): {e}", "warning")

    async def _regenerate_scenes(
        self,
        context: TaskContext,
        failed_scenes: List[int],
        feedback: str
    ) -> Dict[str, Any]:
        """특정 씬 이미지 재생성"""
        self.log(f"이미지 재생성: 씬 {failed_scenes}")
        self.log(f"피드백: {feedback[:100]}...")

        scenes = context.script.get("scenes", [])
        output_dir = os.path.join(self.output_base_dir, context.task_id, "images")

        # 재생성할 씬만 필터링
        scenes_to_regenerate = [
            scene for scene in scenes
            if scene.get("scene_number") in failed_scenes
        ]

        if not scenes_to_regenerate:
            return {"ok": True, "images": [], "failed": [], "cost": 0}

        # 피드백을 반영한 프롬프트 개선 (선택적)
        for scene in scenes_to_regenerate:
            original_prompt = scene.get("image_prompt_enhanced", scene.get("image_prompt", ""))
            # 피드백 내용을 프롬프트에 추가
            scene["image_prompt_enhanced"] = f"""
{original_prompt}

IMPROVEMENT NOTES based on review feedback:
{feedback}

Please address the feedback while maintaining the overall style.
"""

        result = generate_images_parallel(
            scenes=scenes_to_regenerate,
            output_dir=output_dir,
            max_workers=self.max_workers
        )

        # 기존 이미지 목록과 병합
        if context.images:
            existing_images = []
            for i, path in enumerate(context.images):
                scene_num = i + 1
                if scene_num not in failed_scenes:
                    existing_images.append({"scene": scene_num, "path": path})

            result["images"] = sorted(
                existing_images + result.get("images", []),
                key=lambda x: x["scene"]
            )

        return result
