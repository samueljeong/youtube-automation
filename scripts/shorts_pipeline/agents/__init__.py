"""
Shorts Pipeline Multi-Agent System

구조:
- SupervisorAgent: 전체 총괄, 사용자 명령 수신
- ScriptAgent: 기획/대본 생성
- SubtitleAgent: TTS + 자막 생성/동기화
- ImageAgent: 씬 이미지 생성
- ReviewAgent: 품질 검수 및 피드백
"""

from .base import BaseAgent, AgentResult, TaskContext
from .script_agent import ScriptAgent
from .subtitle_agent import SubtitleAgent
from .image_agent import ImageAgent
from .review_agent import ReviewAgent
from .supervisor import SupervisorAgent

__all__ = [
    "BaseAgent",
    "AgentResult",
    "TaskContext",
    "ScriptAgent",
    "SubtitleAgent",
    "ImageAgent",
    "ReviewAgent",
    "SupervisorAgent",
]
