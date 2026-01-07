"""
Base Agent - 모든 에이전트의 기본 클래스

모든 파이프라인(history, isekai, shorts, video)에서 공통으로 사용하는
에이전트 시스템의 기반 클래스들을 정의합니다.

사용법:
    from scripts.common.base_agent import AgentStatus, AgentResult, BaseAgent

    class MyAgent(BaseAgent):
        async def execute(self, context, **kwargs) -> AgentResult:
            # 구현
            pass
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from enum import Enum
import logging
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
    """
    에이전트 실행 결과

    Attributes:
        success: 성공 여부
        data: 결과 데이터
        error: 에러 메시지 (실패 시)
        feedback: 검수 에이전트의 피드백
        needs_improvement: 개선 필요 여부
        improvement_targets: 개선 대상 목록 (예: ["script", "images"])
        cost: API 호출 비용 ($)
        duration: 실행 시간 (초)
        retries: 재시도 횟수
    """
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


class BaseAgent(ABC):
    """
    에이전트 기본 클래스

    모든 에이전트는 이 클래스를 상속받아 execute() 메서드를 구현합니다.

    사용법:
        class ScriptAgent(BaseAgent):
            async def execute(self, context, **kwargs) -> AgentResult:
                # 대본 생성 로직
                return AgentResult(success=True, data={"script": "..."})
    """

    def __init__(self, name: str, max_retries: int = 3):
        """
        Args:
            name: 에이전트 이름 (로깅용)
            max_retries: 최대 재시도 횟수
        """
        self.name = name
        self.status = AgentStatus.IDLE
        self.max_retries = max_retries
        self.logger = logging.getLogger(f"agent.{name}")

    @abstractmethod
    async def execute(self, context: Any, **kwargs) -> AgentResult:
        """
        에이전트 실행 - 하위 클래스에서 구현

        Args:
            context: 작업 컨텍스트 (파이프라인별로 다름)
            **kwargs: 추가 옵션 (feedback 등)

        Returns:
            AgentResult
        """
        pass

    async def execute_with_retry(
        self,
        context: Any,
        feedback: Optional[str] = None,
        **kwargs
    ) -> AgentResult:
        """
        재시도 로직이 포함된 실행

        실패 시 지수 백오프로 재시도합니다.

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

            # 재시도 전 잠시 대기 (지수 백오프)
            if attempt < self.max_retries - 1:
                await asyncio.sleep(2 ** attempt)

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
        print(f"[{self.name}] {message}")

    def set_status(self, status: AgentStatus):
        """상태 변경"""
        self.status = status
        self.log(f"상태 변경: {status.value}")


class BudgetManager:
    """
    동적 예산 관리자

    에이전트별 API 호출 예산을 관리하고, 필요시 동적으로 재분배합니다.

    사용법:
        budget = BudgetManager(total_budget=1.00)

        # 예산 사용
        budget.spend("analysis", 0.03)

        # 잔여 예산 확인
        remaining = budget.get_remaining("creative")

        # 프리미엄 모델 사용 여부 판단
        if budget.should_use_premium("creative"):
            # 고품질 모델 사용
            pass
    """

    def __init__(self, total_budget: float = 1.00):
        """
        Args:
            total_budget: 전체 예산 ($)
        """
        self.total_budget = total_budget

        # 기본 예산 분배 비율
        self.default_allocation = {
            "analysis": 0.10,   # 대본 분석
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
            예산 내 사용 여부 (초과 시 False)
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
