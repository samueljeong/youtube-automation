"""
Video Pipeline - 에이전트 기반 영상 생성 파이프라인

기존 run_automation_pipeline() 함수를 슈퍼바이저 에이전트 기반으로 실행합니다.

사용법:
    from scripts.video_pipeline import run_agent_pipeline

    # 기존 파이프라인과 동일한 인터페이스
    result = await run_agent_pipeline(
        row_data={
            "대본": "대본 내용...",
            "제목(입력)": "영상 제목",
            "채널ID": "UCxxx",
            ...
        },
        row_number=3,
        sheet_name="뉴스채널"
    )
"""

from .agents import (
    VideoSupervisorAgent,
    VideoTaskContext,
    AgentResult,
    PipelineStrategy,
)
from .pipeline import run_agent_pipeline, AgentPipelineRunner


__all__ = [
    "VideoSupervisorAgent",
    "VideoTaskContext",
    "AgentResult",
    "PipelineStrategy",
    "run_agent_pipeline",
    "AgentPipelineRunner",
]
