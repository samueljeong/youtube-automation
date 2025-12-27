"""
Video Pipeline Agents

영상 생성 파이프라인을 위한 에이전트 시스템

사용법:
    from scripts.video_pipeline.agents import VideoSupervisorAgent, VideoTaskContext

    # 슈퍼바이저 생성
    supervisor = VideoSupervisorAgent(
        server_url="http://localhost:5059",
        budget=1.00
    )

    # 컨텍스트 생성
    context = VideoTaskContext(
        script="대본 내용...",
        channel_id="UCxxx",
        title_input="영상 제목",
        voice="chirp3:Charon"  # 기본: Chirp 3 HD 남성 음성
    )

    # 실행
    result = await supervisor.execute(context)

    # 또는 간편 실행
    result = await supervisor.run(
        script="대본 내용...",
        channel_id="UCxxx",
        title="영상 제목"
    )
"""

from .base import (
    AgentStatus,
    AgentResult,
    VideoTaskContext,
    BaseAgent,
    BudgetManager,
)

from .analysis_agent import AnalysisAgent
from .audio_agent import AudioAgent
from .creative_agent import CreativeAgent
from .quality_agent import QualityAgent
from .production_agent import ProductionAgent
from .publish_agent import PublishAgent
from .review_agent import ReviewAgent, ReviewScore, ReviewReport
from .supervisor import VideoSupervisorAgent, PipelineStrategy


__all__ = [
    # Base
    "AgentStatus",
    "AgentResult",
    "VideoTaskContext",
    "BaseAgent",
    "BudgetManager",

    # Agents
    "AnalysisAgent",
    "AudioAgent",
    "CreativeAgent",
    "QualityAgent",
    "ProductionAgent",
    "PublishAgent",
    "ReviewAgent",
    "ReviewScore",
    "ReviewReport",

    # Supervisor
    "VideoSupervisorAgent",
    "PipelineStrategy",
]

__version__ = "1.0.0"
