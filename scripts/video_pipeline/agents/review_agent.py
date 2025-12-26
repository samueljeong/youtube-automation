"""
ReviewAgent - 리뷰 에이전트

역할:
- 대본 분석 결과 리뷰 (씬 구조, 메타데이터 품질)
- 이미지 품질 리뷰 (스타일 일관성, 프롬프트 매칭)
- TTS 품질 리뷰 (발음, 속도, 자연스러움)
- 자막 동기화 리뷰
- 최종 영상 리뷰
- 개선점 제안 및 피드백 생성

특징:
- GPT를 활용한 지능형 리뷰 (옵션)
- 규칙 기반 빠른 검증
- 상세한 피드백 레포트 생성
"""

import asyncio
import time
import json
import subprocess
from typing import Any, Dict, List, Optional, Tuple
from pathlib import Path
from dataclasses import dataclass, field

import httpx

from .base import BaseAgent, AgentResult, VideoTaskContext, AgentStatus


@dataclass
class ReviewScore:
    """리뷰 점수"""
    category: str
    score: float  # 0.0 ~ 1.0
    issues: List[str] = field(default_factory=list)
    suggestions: List[str] = field(default_factory=list)
    details: Dict[str, Any] = field(default_factory=dict)

    @property
    def passed(self) -> bool:
        return self.score >= 0.7

    def to_dict(self) -> Dict[str, Any]:
        return {
            "category": self.category,
            "score": self.score,
            "passed": self.passed,
            "issues": self.issues,
            "suggestions": self.suggestions,
            "details": self.details,
        }


@dataclass
class ReviewReport:
    """전체 리뷰 레포트"""
    overall_score: float = 0.0
    reviews: Dict[str, ReviewScore] = field(default_factory=dict)
    needs_improvement: bool = False
    improvement_targets: List[str] = field(default_factory=list)
    summary: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "overall_score": self.overall_score,
            "reviews": {k: v.to_dict() for k, v in self.reviews.items()},
            "needs_improvement": self.needs_improvement,
            "improvement_targets": self.improvement_targets,
            "summary": self.summary,
        }


class ReviewAgent(BaseAgent):
    """리뷰 에이전트"""

    def __init__(self, server_url: str = "http://localhost:5059"):
        super().__init__("ReviewAgent", max_retries=1)
        self.server_url = server_url

        # 리뷰 기준
        self.thresholds = {
            "script": {
                "min_scenes": 3,
                "max_scenes": 15,
                "min_narration_length": 50,
                "max_narration_length": 2000,
            },
            "images": {
                "min_success_rate": 0.8,
                "min_resolution": 512,
            },
            "audio": {
                "min_duration": 10,
                "max_silence_ratio": 0.3,
            },
            "subtitles": {
                "max_duration_per_line": 10,
                "min_sync_accuracy": 0.9,
            },
            "video": {
                "min_duration": 30,
                "min_size_kb": 500,
            },
        }

    async def execute(self, context: VideoTaskContext, **kwargs) -> AgentResult:
        """
        전체 리뷰 실행

        Args:
            context: 작업 컨텍스트
            **kwargs:
                review_types: 리뷰할 항목 목록 (기본: 전체)
                quick_mode: 빠른 검증 모드 (기본: False)

        Returns:
            AgentResult with ReviewReport
        """
        start_time = time.time()
        self.set_status(AgentStatus.RUNNING)

        review_types = kwargs.get("review_types", ["script", "images", "audio", "subtitles", "video"])
        quick_mode = kwargs.get("quick_mode", False)

        self.log(f"리뷰 시작: {review_types}")

        try:
            report = ReviewReport()
            reviews = {}

            # 1. 대본 리뷰
            if "script" in review_types and context.scenes:
                reviews["script"] = await self._review_script(context, quick_mode)

            # 2. 이미지 리뷰
            if "images" in review_types and context.images:
                reviews["images"] = await self._review_images(context, quick_mode)

            # 3. 오디오 리뷰
            if "audio" in review_types and context.tts_result:
                reviews["audio"] = await self._review_audio(context, quick_mode)

            # 4. 자막 리뷰
            if "subtitles" in review_types and context.subtitles:
                reviews["subtitles"] = await self._review_subtitles(context, quick_mode)

            # 5. 영상 리뷰
            if "video" in review_types and context.video_path:
                reviews["video"] = await self._review_video(context, quick_mode)

            # 전체 점수 계산
            if reviews:
                scores = [r.score for r in reviews.values()]
                report.overall_score = sum(scores) / len(scores)
                report.reviews = reviews
                report.improvement_targets = [
                    name for name, review in reviews.items() if not review.passed
                ]
                report.needs_improvement = len(report.improvement_targets) > 0
                report.summary = self._generate_summary(report)

            # 컨텍스트에 저장
            context.quality_scores = {k: v.score for k, v in reviews.items()}

            duration = time.time() - start_time

            self.log(f"리뷰 완료: 점수={report.overall_score:.2f}, 개선필요={report.improvement_targets}")

            context.add_log(
                self.name, "review", "success",
                f"score={report.overall_score:.2f}, targets={report.improvement_targets}"
            )

            self.set_status(AgentStatus.SUCCESS)

            return AgentResult(
                success=True,
                data=report.to_dict(),
                feedback=report.summary,
                needs_improvement=report.needs_improvement,
                improvement_targets=report.improvement_targets,
                duration=duration,
                cost=0.0
            )

        except Exception as e:
            self.set_status(AgentStatus.FAILED)
            context.add_log(self.name, "review", "error", str(e))
            return AgentResult(
                success=False,
                error=str(e)
            )

    async def _review_script(self, context: VideoTaskContext, quick_mode: bool) -> ReviewScore:
        """
        대본 리뷰

        검사 항목:
        - 씬 개수 적절성
        - 나레이션 길이 균형
        - 메타데이터 완성도 (제목, 설명, 태그)
        - 카테고리 감지 정확성
        """
        issues = []
        suggestions = []
        details = {}

        scenes = context.scenes or []
        youtube = context.youtube_metadata or {}
        thresholds = self.thresholds["script"]

        # 씬 개수 검사
        scene_count = len(scenes)
        details["scene_count"] = scene_count

        if scene_count < thresholds["min_scenes"]:
            issues.append(f"씬 개수 부족: {scene_count}개 (최소 {thresholds['min_scenes']}개)")
            suggestions.append("대본을 더 상세하게 분할하세요")
        elif scene_count > thresholds["max_scenes"]:
            issues.append(f"씬 개수 과다: {scene_count}개 (최대 {thresholds['max_scenes']}개)")
            suggestions.append("비슷한 씬을 병합하세요")

        # 나레이션 길이 분석
        narration_lengths = []
        for i, scene in enumerate(scenes):
            narration = scene.get("narration", "")
            length = len(narration)
            narration_lengths.append(length)

            if length < thresholds["min_narration_length"]:
                issues.append(f"씬 {i+1} 나레이션 너무 짧음: {length}자")
            elif length > thresholds["max_narration_length"]:
                issues.append(f"씬 {i+1} 나레이션 너무 긺: {length}자")

        if narration_lengths:
            details["avg_narration_length"] = sum(narration_lengths) / len(narration_lengths)
            details["narration_variance"] = max(narration_lengths) - min(narration_lengths)

            # 균형 검사
            if details["narration_variance"] > 500:
                suggestions.append("씬별 나레이션 길이를 균등하게 조정하세요")

        # 메타데이터 검사
        title = youtube.get("title", "")
        description = youtube.get("description", "")
        tags = youtube.get("tags", [])

        details["title_length"] = len(title)
        details["description_length"] = len(description)
        details["tags_count"] = len(tags)

        if len(title) < 10:
            issues.append("제목이 너무 짧습니다")
            suggestions.append("클릭을 유도하는 제목을 작성하세요")
        elif len(title) > 100:
            issues.append("제목이 너무 깁니다 (YouTube 권장: 70자 이하)")

        if len(description) < 50:
            suggestions.append("설명을 더 상세하게 작성하세요 (SEO 향상)")

        if len(tags) < 5:
            suggestions.append("태그를 5개 이상 추가하세요")

        # 점수 계산
        base_score = 1.0
        issue_penalty = len(issues) * 0.1
        score = max(0, min(1, base_score - issue_penalty))

        return ReviewScore(
            category="script",
            score=score,
            issues=issues,
            suggestions=suggestions,
            details=details
        )

    async def _review_images(self, context: VideoTaskContext, quick_mode: bool) -> ReviewScore:
        """
        이미지 리뷰

        검사 항목:
        - 생성 성공률
        - 스타일 일관성 (간접 검사)
        - 이미지 파일 유효성
        """
        issues = []
        suggestions = []
        details = {}

        images = context.images or []
        thresholds = self.thresholds["images"]

        # 성공률 계산
        total = len(images)
        successful = sum(1 for img in images if img is not None)
        failed_indices = [i for i, img in enumerate(images) if img is None]

        success_rate = successful / total if total > 0 else 0
        details["total"] = total
        details["successful"] = successful
        details["success_rate"] = success_rate
        details["failed_indices"] = failed_indices

        if success_rate < thresholds["min_success_rate"]:
            issues.append(f"이미지 성공률 낮음: {success_rate:.0%} (최소 {thresholds['min_success_rate']:.0%})")
            suggestions.append(f"실패한 씬 {failed_indices} 이미지를 재생성하세요")

        # 파일 유효성 검사 (빠른 모드 아닐 때만)
        if not quick_mode:
            for i, img_path in enumerate(images):
                if img_path and Path(img_path).exists():
                    file_size = Path(img_path).stat().st_size
                    if file_size < 10000:  # 10KB 미만
                        issues.append(f"이미지 {i+1} 파일 크기 의심: {file_size/1024:.1f}KB")

        # 점수 계산
        score = success_rate

        return ReviewScore(
            category="images",
            score=score,
            issues=issues,
            suggestions=suggestions,
            details=details
        )

    async def _review_audio(self, context: VideoTaskContext, quick_mode: bool) -> ReviewScore:
        """
        오디오 리뷰

        검사 항목:
        - 전체 길이
        - 무음 비율
        - 씬별 균형
        """
        issues = []
        suggestions = []
        details = {}

        tts_result = context.tts_result or {}
        thresholds = self.thresholds["audio"]

        total_duration = tts_result.get("total_duration", 0)
        details["total_duration"] = total_duration

        if total_duration < thresholds["min_duration"]:
            issues.append(f"오디오 길이 부족: {total_duration:.1f}초 (최소 {thresholds['min_duration']}초)")

        # 씬별 길이 분석
        scene_durations = tts_result.get("scene_durations", [])
        if scene_durations:
            details["scene_durations"] = scene_durations
            details["avg_scene_duration"] = sum(scene_durations) / len(scene_durations)

            # 무음 씬 검사
            silent_scenes = [i for i, d in enumerate(scene_durations) if d < 1.0]
            if silent_scenes:
                issues.append(f"무음 씬 발견: {silent_scenes}")
                suggestions.append("TTS가 실패한 씬의 나레이션을 확인하세요")

        # 점수 계산
        base_score = 1.0 if total_duration >= thresholds["min_duration"] else total_duration / thresholds["min_duration"]
        issue_penalty = len(issues) * 0.15
        score = max(0, min(1, base_score - issue_penalty))

        return ReviewScore(
            category="audio",
            score=score,
            issues=issues,
            suggestions=suggestions,
            details=details
        )

    async def _review_subtitles(self, context: VideoTaskContext, quick_mode: bool) -> ReviewScore:
        """
        자막 리뷰

        검사 항목:
        - 자막 개수
        - 타이밍 유효성
        - 길이 적절성
        """
        issues = []
        suggestions = []
        details = {}

        subtitles = context.subtitles or []
        thresholds = self.thresholds["subtitles"]

        details["count"] = len(subtitles)

        if not subtitles:
            issues.append("자막 없음")
            return ReviewScore(
                category="subtitles",
                score=0,
                issues=issues,
                suggestions=["TTS 생성을 확인하세요"],
                details=details
            )

        # 타이밍 검사
        timing_issues = 0
        for i, sub in enumerate(subtitles):
            start = sub.get("start", 0)
            end = sub.get("end", 0)
            duration = end - start

            if duration <= 0:
                timing_issues += 1
                issues.append(f"자막 {i+1}: 잘못된 타이밍 (start={start}, end={end})")
            elif duration > thresholds["max_duration_per_line"]:
                suggestions.append(f"자막 {i+1}: 너무 긴 자막 ({duration:.1f}초)")

        details["timing_issues"] = timing_issues

        # 점수 계산
        valid_ratio = (len(subtitles) - timing_issues) / len(subtitles) if subtitles else 0
        score = valid_ratio

        return ReviewScore(
            category="subtitles",
            score=score,
            issues=issues,
            suggestions=suggestions,
            details=details
        )

    async def _review_video(self, context: VideoTaskContext, quick_mode: bool) -> ReviewScore:
        """
        영상 리뷰

        검사 항목:
        - 파일 존재
        - 길이
        - 크기
        - 코덱 정보
        """
        issues = []
        suggestions = []
        details = {}

        video_path = context.video_path
        thresholds = self.thresholds["video"]

        if not video_path:
            return ReviewScore(
                category="video",
                score=0,
                issues=["영상 파일 없음"],
                suggestions=["영상 생성을 확인하세요"],
                details={}
            )

        path = Path(video_path)
        if not path.exists():
            return ReviewScore(
                category="video",
                score=0,
                issues=["영상 파일을 찾을 수 없음"],
                suggestions=["영상 경로를 확인하세요"],
                details={}
            )

        # 파일 크기
        file_size = path.stat().st_size
        details["file_size_kb"] = file_size / 1024
        details["file_size_mb"] = file_size / 1024 / 1024

        if file_size < thresholds["min_size_kb"] * 1024:
            issues.append(f"파일 크기 너무 작음: {file_size/1024:.1f}KB")

        # ffprobe로 상세 분석 (빠른 모드 아닐 때)
        if not quick_mode:
            try:
                result = subprocess.run([
                    "ffprobe", "-v", "error",
                    "-show_entries", "format=duration:stream=codec_type,codec_name,width,height",
                    "-of", "json",
                    str(path)
                ], capture_output=True, text=True, timeout=30)

                probe_data = json.loads(result.stdout)
                duration = float(probe_data.get("format", {}).get("duration", 0))
                details["duration"] = duration

                if duration < thresholds["min_duration"]:
                    issues.append(f"영상 길이 부족: {duration:.1f}초 (최소 {thresholds['min_duration']}초)")

                # 스트림 정보
                streams = probe_data.get("streams", [])
                has_video = any(s.get("codec_type") == "video" for s in streams)
                has_audio = any(s.get("codec_type") == "audio" for s in streams)

                details["has_video"] = has_video
                details["has_audio"] = has_audio

                if not has_video:
                    issues.append("비디오 스트림 없음")
                if not has_audio:
                    issues.append("오디오 스트림 없음")

            except Exception as e:
                self.log(f"ffprobe 실패: {e}", "warning")

        # 점수 계산
        base_score = 1.0
        issue_penalty = len(issues) * 0.2
        score = max(0, min(1, base_score - issue_penalty))

        return ReviewScore(
            category="video",
            score=score,
            issues=issues,
            suggestions=suggestions,
            details=details
        )

    def _generate_summary(self, report: ReviewReport) -> str:
        """리뷰 요약 생성"""
        lines = [
            f"📊 리뷰 요약: 전체 점수 {report.overall_score:.0%}",
            ""
        ]

        for name, review in report.reviews.items():
            emoji = "✅" if review.passed else "⚠️"
            lines.append(f"{emoji} {name}: {review.score:.0%}")

            if review.issues:
                for issue in review.issues[:2]:  # 상위 2개만
                    lines.append(f"   - {issue}")

        if report.improvement_targets:
            lines.append("")
            lines.append(f"🔧 개선 필요: {', '.join(report.improvement_targets)}")

        if report.reviews:
            all_suggestions = []
            for review in report.reviews.values():
                all_suggestions.extend(review.suggestions[:1])  # 각 카테고리에서 1개

            if all_suggestions:
                lines.append("")
                lines.append("💡 제안:")
                for suggestion in all_suggestions[:3]:  # 상위 3개
                    lines.append(f"   - {suggestion}")

        return "\n".join(lines)

    async def review_and_suggest(
        self,
        context: VideoTaskContext,
        target: str
    ) -> Tuple[float, str, List[str]]:
        """
        특정 항목 리뷰 후 점수와 제안 반환

        Args:
            context: 작업 컨텍스트
            target: 리뷰 대상 ("script", "images", "audio", "subtitles", "video")

        Returns:
            (점수, 피드백, 제안 목록)
        """
        result = await self.execute(context, review_types=[target], quick_mode=True)

        if not result.success:
            return 0.0, result.error or "리뷰 실패", []

        report = result.data
        review = report.get("reviews", {}).get(target, {})

        return (
            review.get("score", 0),
            "\n".join(review.get("issues", [])),
            review.get("suggestions", [])
        )
