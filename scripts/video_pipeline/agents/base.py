"""
Base Agent - 모든 에이전트의 기본 클래스

영상 생성 파이프라인용 에이전트 시스템의 기반 클래스들을 정의합니다.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Callable
from enum import Enum
import logging
import time
import uuid
import asyncio

logger = logging.getLogger(__name__)


class AgentStatus(Enum):
    """에이전트 상태"""
    IDLE = "idle"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    WAITING_REVIEW = "waiting_review"
    RETRYING = "retrying"


@dataclass
class AgentResult:
    """에이전트 실행 결과"""
    success: bool
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    feedback: Optional[str] = None
    needs_improvement: bool = False
    improvement_targets: List[str] = field(default_factory=list)
    cost: float = 0.0
    duration: float = 0.0
    retries: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "data": self.data,
            "error": self.error,
            "feedback": self.feedback,
            "needs_improvement": self.needs_improvement,
            "improvement_targets": self.improvement_targets,
            "cost": self.cost,
            "duration": self.duration,
            "retries": self.retries,
        }


@dataclass
class VideoTaskContext:
    """
    영상 생성 작업 컨텍스트 - 에이전트 간 공유 데이터

    Google Sheets 행 데이터를 기반으로 전체 파이프라인에서 사용됩니다.
    """
    # 기본 식별자
    task_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    row_number: int = 0
    sheet_name: str = ""

    # 입력 데이터 (Google Sheets에서)
    script: str = ""  # 원본 대본
    title_input: str = ""  # 사용자 입력 제목
    thumbnail_text_input: str = ""  # 사용자 입력 썸네일 문구
    channel_id: str = ""
    privacy_status: str = "private"
    publish_at: Optional[str] = None
    playlist_id: Optional[str] = None
    voice: str = "ko-KR-Neural2-C"
    project_suffix: str = ""  # YouTube 프로젝트 ('', '_2')
    input_category: str = ""  # 시트에서 입력된 카테고리 (news 등)

    # 분석 결과
    analysis_result: Optional[Dict[str, Any]] = None
    scenes: Optional[List[Dict[str, Any]]] = None
    youtube_metadata: Optional[Dict[str, Any]] = None
    thumbnail_config: Optional[Dict[str, Any]] = None
    video_effects: Optional[Dict[str, Any]] = None
    detected_category: str = ""

    # 생성된 에셋
    tts_result: Optional[Dict[str, Any]] = None
    subtitles: Optional[List[Dict[str, Any]]] = None
    images: Optional[List[str]] = None
    thumbnail_path: Optional[str] = None
    video_path: Optional[str] = None

    # 품질 검증 결과
    quality_scores: Dict[str, float] = field(default_factory=dict)
    quality_feedback: Dict[str, str] = field(default_factory=dict)

    # 최종 결과
    video_url: Optional[str] = None
    shorts_url: Optional[str] = None

    # 시도 횟수
    analysis_attempts: int = 0
    tts_attempts: int = 0
    image_attempts: int = 0
    video_attempts: int = 0
    upload_attempts: int = 0

    # 설정
    max_attempts: int = 3

    # 비용 추적
    total_cost: float = 0.0
    cost_breakdown: Dict[str, float] = field(default_factory=dict)

    # 로그
    logs: List[Dict[str, Any]] = field(default_factory=list)

    # 전략 (슈퍼바이저가 결정)
    strategy: Optional[Dict[str, Any]] = None

    def add_log(self, agent: str, action: str, result: str, details: str = ""):
        """로그 추가"""
        self.logs.append({
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "agent": agent,
            "action": action,
            "result": result,
            "details": details,
        })

    def add_cost(self, agent: str, amount: float):
        """비용 추가"""
        self.total_cost += amount
        self.cost_breakdown[agent] = self.cost_breakdown.get(agent, 0) + amount

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "row_number": self.row_number,
            "sheet_name": self.sheet_name,
            "script_length": len(self.script) if self.script else 0,
            "scenes_count": len(self.scenes) if self.scenes else 0,
            "images_count": len(self.images) if self.images else 0,
            "video_url": self.video_url,
            "shorts_url": self.shorts_url,
            "total_cost": self.total_cost,
            "cost_breakdown": self.cost_breakdown,
            "quality_scores": self.quality_scores,
            "logs": self.logs,
        }


class BaseAgent(ABC):
    """에이전트 기본 클래스"""

    def __init__(self, name: str, max_retries: int = 3):
        self.name = name
        self.status = AgentStatus.IDLE
        self.max_retries = max_retries
        self.logger = logging.getLogger(f"agent.{name}")

    @abstractmethod
    async def execute(self, context: VideoTaskContext, **kwargs) -> AgentResult:
        """
        에이전트 실행 - 하위 클래스에서 구현

        Args:
            context: 작업 컨텍스트
            **kwargs: 추가 옵션 (feedback 등)

        Returns:
            AgentResult
        """
        pass

    async def execute_with_retry(
        self,
        context: VideoTaskContext,
        feedback: Optional[str] = None,
        **kwargs
    ) -> AgentResult:
        """
        재시도 로직이 포함된 실행

        Args:
            context: 작업 컨텍스트
            feedback: 이전 시도의 피드백 (개선 시 사용)
            **kwargs: 추가 옵션

        Returns:
            AgentResult
        """
        last_error = None

        for attempt in range(self.max_retries):
            try:
                self.set_status(AgentStatus.RUNNING if attempt == 0 else AgentStatus.RETRYING)
                self.log(f"실행 시작 (시도 {attempt + 1}/{self.max_retries})")

                result = await self.execute(context, feedback=feedback, **kwargs)
                result.retries = attempt

                if result.success:
                    self.set_status(AgentStatus.SUCCESS)
                    return result
                else:
                    last_error = result.error
                    feedback = result.feedback  # 다음 시도에 피드백 전달
                    self.log(f"실행 실패: {last_error}", "warning")

            except Exception as e:
                last_error = str(e)
                self.log(f"예외 발생: {last_error}", "error")

            # 재시도 전 잠시 대기
            if attempt < self.max_retries - 1:
                await asyncio.sleep(2 ** attempt)  # 지수 백오프

        self.set_status(AgentStatus.FAILED)
        return AgentResult(
            success=False,
            error=f"최대 재시도 횟수 초과: {last_error}",
            retries=self.max_retries
        )

    def log(self, message: str, level: str = "info"):
        """로그 출력"""
        log_func = getattr(self.logger, level, self.logger.info)
        log_func(f"[{self.name}] {message}")

    def set_status(self, status: AgentStatus):
        """상태 변경"""
        self.status = status
        self.log(f"상태 변경: {status.value}")


class BudgetManager:
    """
    동적 예산 관리자

    에이전트별 예산을 관리하고, 필요시 동적으로 재분배합니다.
    """

    def __init__(self, total_budget: float = 1.00):
        self.total_budget = total_budget

        # 기본 예산 분배 비율
        self.default_allocation = {
            "analysis": 0.10,   # 대본 분석 (GPT-5.1)
            "audio": 0.15,      # TTS + 자막
            "creative": 0.50,   # 이미지 + 썸네일
            "quality": 0.05,    # 품질 검증
            "production": 0.05, # 영상 렌더링 (주로 무료)
            "publish": 0.05,    # 업로드 (주로 무료)
            "reserve": 0.10,    # 예비
        }

        # 현재 사용량
        self.spent: Dict[str, float] = {k: 0.0 for k in self.default_allocation}

        # 품질 점수 (0~1)
        self.quality_scores: Dict[str, float] = {}

    def get_allocated(self, agent: str) -> float:
        """에이전트 할당 예산"""
        return self.total_budget * self.default_allocation.get(agent, 0)

    def get_remaining(self, agent: str) -> float:
        """에이전트 잔여 예산"""
        allocated = self.get_allocated(agent)
        return max(0, allocated - self.spent.get(agent, 0))

    def get_total_remaining(self) -> float:
        """전체 잔여 예산"""
        return self.total_budget - sum(self.spent.values())

    def spend(self, agent: str, amount: float) -> bool:
        """
        예산 사용

        Returns:
            예산 내 사용 여부
        """
        self.spent[agent] = self.spent.get(agent, 0) + amount
        return self.spent[agent] <= self.get_allocated(agent)

    def set_quality(self, agent: str, score: float):
        """품질 점수 기록 (0~1)"""
        self.quality_scores[agent] = min(1.0, max(0, score))

    def reallocate(self, from_agent: str, to_agent: str, amount: float) -> bool:
        """
        예산 재분배

        Args:
            from_agent: 예산을 빼올 에이전트
            to_agent: 예산을 추가할 에이전트
            amount: 재분배 금액

        Returns:
            성공 여부
        """
        from_remaining = self.get_remaining(from_agent)
        if from_remaining < amount:
            return False

        self.default_allocation[from_agent] -= amount / self.total_budget
        self.default_allocation[to_agent] = self.default_allocation.get(to_agent, 0) + amount / self.total_budget
        return True

    def should_use_premium(self, agent: str) -> bool:
        """
        프리미엄 모델 사용 여부 판단

        예산 여유가 있고 품질이 낮으면 프리미엄 모델 사용 권장
        """
        remaining = self.get_remaining(agent)
        quality = self.quality_scores.get(agent, 1.0)
        allocated = self.get_allocated(agent)

        # 잔여 예산 50% 이상 + 품질 70% 미만이면 프리미엄 권장
        return remaining > (allocated * 0.5) and quality < 0.7

    def get_report(self) -> Dict[str, Any]:
        """예산 리포트"""
        return {
            "total_budget": self.total_budget,
            "total_spent": sum(self.spent.values()),
            "total_remaining": self.get_total_remaining(),
            "by_agent": {
                agent: {
                    "allocated": self.get_allocated(agent),
                    "spent": self.spent.get(agent, 0),
                    "remaining": self.get_remaining(agent),
                    "quality": self.quality_scores.get(agent, None),
                }
                for agent in self.default_allocation
            }
        }
