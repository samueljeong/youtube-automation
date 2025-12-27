"""
Base Agent - 모든 에이전트의 기본 클래스
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from enum import Enum
import logging
import time
import uuid

logger = logging.getLogger(__name__)


class AgentStatus(Enum):
    """에이전트 상태"""
    IDLE = "idle"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    WAITING_REVIEW = "waiting_review"


@dataclass
class AgentResult:
    """에이전트 실행 결과"""
    success: bool
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    feedback: Optional[str] = None  # 검수 에이전트의 피드백
    needs_improvement: bool = False
    improvement_targets: List[str] = field(default_factory=list)  # ["script", "images"]
    cost: float = 0.0
    duration: float = 0.0

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
        }


@dataclass
class TaskContext:
    """작업 컨텍스트 - 에이전트 간 공유 데이터"""
    task_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    topic: str = ""
    category: str = ""  # 연예인/운동선수/국뽕
    issue_type: str = ""  # 논란/열애/컴백/사건/근황/성과
    person: str = ""

    # 뉴스 분석 데이터 (news_scorer에서 생성)
    script_hints: Optional[Dict[str, Any]] = None  # 실제 댓글 기반 힌트
    viral_score: Optional[Dict[str, Any]] = None   # 바이럴 잠재력 점수
    comments_summary: Optional[Dict[str, Any]] = None  # 댓글 요약

    # 생성된 데이터
    script: Optional[Dict[str, Any]] = None
    images: Optional[List[str]] = None  # 이미지 경로 리스트
    subtitle_data: Optional[Dict[str, Any]] = None  # TTS + 자막 데이터

    # 검수 피드백
    script_feedback: Optional[str] = None
    image_feedback: Optional[str] = None
    subtitle_feedback: Optional[str] = None

    # 시도 횟수
    script_attempts: int = 0
    image_attempts: int = 0
    subtitle_attempts: int = 0

    # 설정
    max_attempts: int = 3

    # 로그
    logs: List[Dict[str, Any]] = field(default_factory=list)

    def add_log(self, agent: str, action: str, result: str, details: str = ""):
        self.logs.append({
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "agent": agent,
            "action": action,
            "result": result,
            "details": details,
        })

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "topic": self.topic,
            "category": self.category,
            "issue_type": self.issue_type,
            "person": self.person,
            "script_hints": self.script_hints,
            "viral_score": self.viral_score,
            "comments_summary": self.comments_summary,
            "script": self.script,
            "images": self.images,
            "subtitle_data": self.subtitle_data,
            "script_attempts": self.script_attempts,
            "image_attempts": self.image_attempts,
            "subtitle_attempts": self.subtitle_attempts,
            "logs": self.logs,
        }


class BaseAgent(ABC):
    """에이전트 기본 클래스"""

    def __init__(self, name: str):
        self.name = name
        self.status = AgentStatus.IDLE
        self.logger = logging.getLogger(f"agent.{name}")

    @abstractmethod
    async def execute(self, context: TaskContext, **kwargs) -> AgentResult:
        """에이전트 실행 - 하위 클래스에서 구현"""
        pass

    def log(self, message: str, level: str = "info"):
        """로그 출력"""
        log_func = getattr(self.logger, level, self.logger.info)
        log_func(f"[{self.name}] {message}")

    def set_status(self, status: AgentStatus):
        """상태 변경"""
        self.status = status
        self.log(f"Status changed to: {status.value}")
