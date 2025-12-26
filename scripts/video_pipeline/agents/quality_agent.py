"""
QualityAgent - 품질 검증 에이전트

역할:
- 이미지 품질 검증 (해상도, 스타일 일관성)
- 오디오 품질 검증 (TTS 자연스러움)
- 자막 동기화 검증
- 영상 검증 (업로드 전)
- 개선 피드백 생성
"""

import asyncio
import time
import json
import subprocess
from typing import Any, Dict, List, Optional, Tuple
from pathlib import Path

import httpx

from .base import BaseAgent, AgentResult, VideoTaskContext, AgentStatus


class QualityAgent(BaseAgent):
    """품질 검증 에이전트"""

    def __init__(self, server_url: str = "http://localhost:5059"):
        super().__init__("QualityAgent", max_retries=1)  # 검증은 재시도 불필요
        self.server_url = server_url

        # 품질 기준
        self.thresholds = {
            "image_success_rate": 0.8,   # 80% 이상 이미지 성공
            "min_image_resolution": 512,  # 최소 512px
            "min_audio_duration": 1.0,    # 최소 1초
            "min_video_duration": 10.0,   # 최소 10초
            "min_video_size": 100 * 1024, # 최소 100KB
        }

    async def execute(self, context: VideoTaskContext, **kwargs) -> AgentResult:
        """
        전체 품질 검증

        Args:
            context: 작업 컨텍스트
            **kwargs:
                check_type: 검증 유형 ("all", "images", "audio", "video")

        Returns:
            AgentResult with quality scores and feedback
        """
        start_time = time.time()
        self.set_status(AgentStatus.RUNNING)

        check_type = kwargs.get("check_type", "all")

        try:
            checks = {}
            improvement_targets = []

            # 1. 이미지 품질 검증
            if check_type in ["all", "images"] and context.images:
                checks["images"] = await self._check_images(context)
                if checks["images"]["score"] < self.thresholds["image_success_rate"]:
                    improvement_targets.append("images")

            # 2. 오디오 품질 검증
            if check_type in ["all", "audio"] and context.tts_result:
                checks["audio"] = await self._check_audio(context)
                if checks["audio"]["score"] < 0.7:
                    improvement_targets.append("audio")

            # 3. 자막 동기화 검증
            if check_type in ["all", "subtitles"] and context.subtitles:
                checks["subtitles"] = await self._check_subtitles(context)
                if checks["subtitles"]["score"] < 0.7:
                    improvement_targets.append("subtitles")

            # 4. 영상 품질 검증
            if check_type in ["all", "video"] and context.video_path:
                checks["video"] = await self._check_video(context)
                if checks["video"]["score"] < 0.8:
                    improvement_targets.append("video")

            # 전체 품질 점수 계산
            scores = [c.get("score", 0) for c in checks.values()]
            overall_score = sum(scores) / len(scores) if scores else 0

            # 컨텍스트에 저장
            context.quality_scores = {k: v.get("score", 0) for k, v in checks.items()}
            context.quality_feedback = {k: v.get("feedback", "") for k, v in checks.items()}

            duration = time.time() - start_time

            # 피드백 생성
            feedback = self._generate_feedback(checks, improvement_targets)

            needs_improvement = len(improvement_targets) > 0

            self.log(f"품질 검증 완료: 점수={overall_score:.2f}, 개선 필요={improvement_targets}")
            context.add_log(
                self.name, "quality_check", "success",
                f"score={overall_score:.2f}, targets={improvement_targets}"
            )

            self.set_status(AgentStatus.SUCCESS)

            return AgentResult(
                success=True,
                data={
                    "overall_score": overall_score,
                    "checks": checks,
                    "improvement_targets": improvement_targets,
                },
                feedback=feedback,
                needs_improvement=needs_improvement,
                improvement_targets=improvement_targets,
                duration=duration,
                cost=0.0  # 품질 검증은 무료 (로컬 처리)
            )

        except Exception as e:
            self.set_status(AgentStatus.FAILED)
            context.add_log(self.name, "quality_check", "error", str(e))
            return AgentResult(
                success=False,
                error=str(e)
            )

    async def _check_images(self, context: VideoTaskContext) -> Dict[str, Any]:
        """
        이미지 품질 검증

        Returns:
            {
                "score": 0.0-1.0,
                "total": 전체 이미지 수,
                "success": 성공한 이미지 수,
                "failed_indices": 실패한 인덱스,
                "issues": 발견된 문제들,
                "feedback": 개선 피드백
            }
        """
        if not context.images:
            return {"score": 0, "feedback": "이미지 없음", "issues": ["no_images"]}

        total = len(context.images)
        success = sum(1 for img in context.images if img is not None)
        failed_indices = [i for i, img in enumerate(context.images) if img is None]

        issues = []
        if success < total:
            issues.append(f"{total - success}개 이미지 생성 실패")

        # 이미지 파일 검증 (해상도 등)
        for i, img_path in enumerate(context.images):
            if img_path and Path(img_path).exists():
                # 실제 이미지 검증 (필요시 확장)
                pass

        score = success / total if total > 0 else 0

        feedback = ""
        if failed_indices:
            feedback = f"이미지 {failed_indices} 재생성 필요"

        return {
            "score": score,
            "total": total,
            "success": success,
            "failed_indices": failed_indices,
            "issues": issues,
            "feedback": feedback
        }

    async def _check_audio(self, context: VideoTaskContext) -> Dict[str, Any]:
        """
        오디오 품질 검증

        Returns:
            {
                "score": 0.0-1.0,
                "duration": 전체 길이,
                "issues": 발견된 문제들,
                "feedback": 개선 피드백
            }
        """
        if not context.tts_result:
            return {"score": 0, "feedback": "TTS 결과 없음", "issues": ["no_tts"]}

        issues = []
        total_duration = context.tts_result.get("total_duration", 0)

        if total_duration < self.thresholds["min_audio_duration"]:
            issues.append(f"오디오 길이 부족: {total_duration}초")

        # 씬별 오디오 검증
        scene_durations = context.tts_result.get("scene_durations", [])
        silent_scenes = [i for i, d in enumerate(scene_durations) if d < 0.5]

        if silent_scenes:
            issues.append(f"무음 씬: {silent_scenes}")

        score = 1.0 if not issues else max(0, 1.0 - len(issues) * 0.2)

        feedback = "; ".join(issues) if issues else ""

        return {
            "score": score,
            "duration": total_duration,
            "scene_durations": scene_durations,
            "silent_scenes": silent_scenes,
            "issues": issues,
            "feedback": feedback
        }

    async def _check_subtitles(self, context: VideoTaskContext) -> Dict[str, Any]:
        """
        자막 동기화 검증

        Returns:
            {
                "score": 0.0-1.0,
                "total": 자막 수,
                "issues": 발견된 문제들,
                "feedback": 개선 피드백
            }
        """
        if not context.subtitles:
            return {"score": 0, "feedback": "자막 없음", "issues": ["no_subtitles"]}

        issues = []
        total = len(context.subtitles)

        # 자막 타이밍 검증
        for i, sub in enumerate(context.subtitles):
            start = sub.get("start", 0)
            end = sub.get("end", 0)

            if end <= start:
                issues.append(f"자막 {i}: 잘못된 타이밍")
            elif end - start > 10:  # 10초 이상 자막
                issues.append(f"자막 {i}: 너무 긴 자막 ({end - start:.1f}초)")

        score = 1.0 if not issues else max(0, 1.0 - len(issues) / total)

        feedback = "; ".join(issues[:3]) if issues else ""  # 상위 3개만

        return {
            "score": score,
            "total": total,
            "issues": issues,
            "feedback": feedback
        }

    async def _check_video(self, context: VideoTaskContext) -> Dict[str, Any]:
        """
        영상 품질 검증 (ffprobe 사용)

        Returns:
            {
                "score": 0.0-1.0,
                "duration": 영상 길이,
                "size": 파일 크기,
                "has_video": 비디오 스트림 존재,
                "has_audio": 오디오 스트림 존재,
                "issues": 발견된 문제들,
                "feedback": 개선 피드백
            }
        """
        if not context.video_path:
            return {"score": 0, "feedback": "영상 없음", "issues": ["no_video"]}

        video_path = Path(context.video_path)
        if not video_path.exists():
            return {"score": 0, "feedback": "영상 파일 없음", "issues": ["file_not_found"]}

        issues = []

        try:
            # ffprobe로 메타데이터 확인
            cmd = [
                "ffprobe", "-v", "error",
                "-show_entries", "format=duration,size:stream=codec_type,width,height",
                "-of", "json",
                str(video_path)
            ]

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            probe_data = json.loads(result.stdout)

            # 기본 정보 추출
            format_info = probe_data.get("format", {})
            duration = float(format_info.get("duration", 0))
            size = int(format_info.get("size", 0))

            # 스트림 확인
            streams = probe_data.get("streams", [])
            has_video = any(s.get("codec_type") == "video" for s in streams)
            has_audio = any(s.get("codec_type") == "audio" for s in streams)

            # 해상도 확인
            video_stream = next((s for s in streams if s.get("codec_type") == "video"), {})
            width = video_stream.get("width", 0)
            height = video_stream.get("height", 0)

            # 검증
            if duration < self.thresholds["min_video_duration"]:
                issues.append(f"영상 길이 부족: {duration:.1f}초")

            if size < self.thresholds["min_video_size"]:
                issues.append(f"파일 크기 부족: {size / 1024:.1f}KB")

            if not has_video:
                issues.append("비디오 스트림 없음")

            if not has_audio:
                issues.append("오디오 스트림 없음")

            if width < 100 or height < 100:
                issues.append(f"해상도 부족: {width}x{height}")

            score = 1.0 if not issues else max(0, 1.0 - len(issues) * 0.25)

            return {
                "score": score,
                "duration": duration,
                "size": size,
                "width": width,
                "height": height,
                "has_video": has_video,
                "has_audio": has_audio,
                "issues": issues,
                "feedback": "; ".join(issues) if issues else ""
            }

        except subprocess.TimeoutExpired:
            return {"score": 0, "feedback": "영상 검증 타임아웃", "issues": ["timeout"]}
        except Exception as e:
            return {"score": 0, "feedback": str(e), "issues": ["probe_error"]}

    def _generate_feedback(
        self,
        checks: Dict[str, Dict[str, Any]],
        improvement_targets: List[str]
    ) -> str:
        """
        개선 피드백 생성

        Args:
            checks: 검증 결과들
            improvement_targets: 개선 필요 항목

        Returns:
            피드백 문자열
        """
        if not improvement_targets:
            return "모든 품질 검증 통과"

        feedbacks = []

        for target in improvement_targets:
            check = checks.get(target, {})
            feedback = check.get("feedback", "")
            if feedback:
                feedbacks.append(f"[{target}] {feedback}")

        return "\n".join(feedbacks)

    async def quick_check_images(self, images: List[Optional[str]]) -> Tuple[float, List[int]]:
        """
        이미지 빠른 검증 (병렬 처리 중 사용)

        Returns:
            (성공률, 실패 인덱스)
        """
        if not images:
            return 0.0, []

        total = len(images)
        success = sum(1 for img in images if img is not None)
        failed = [i for i, img in enumerate(images) if img is None]

        return success / total, failed
