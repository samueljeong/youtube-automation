"""
Pipeline Runner - 에이전트 파이프라인 실행기

기존 run_automation_pipeline() 함수와 동일한 인터페이스를 제공하면서
내부적으로 VideoSupervisorAgent를 사용합니다.
"""

import asyncio
import os
import logging
from typing import Any, Dict, Optional, Tuple

from .agents import VideoSupervisorAgent, VideoTaskContext, AgentResult

logger = logging.getLogger(__name__)


class AgentPipelineRunner:
    """
    에이전트 기반 파이프라인 실행기

    기존 run_automation_pipeline() 함수와 호환되는 인터페이스를 제공합니다.
    """

    def __init__(self, server_url: str = None):
        """
        Args:
            server_url: API 서버 URL (기본: 환경변수 또는 localhost:PORT)
        """
        # Render 환경에서는 PORT 환경변수 사용
        port = os.environ.get("PORT", "5059")
        default_url = f"http://localhost:{port}"

        self.server_url = server_url or os.environ.get(
            "API_SERVER_URL", default_url
        )
        print(f"[AgentPipeline] server_url = {self.server_url}")

        self.supervisor = VideoSupervisorAgent(
            server_url=self.server_url,
            budget=1.00
        )

    async def run(
        self,
        row_data: Dict[str, Any],
        row_number: int,
        sheet_name: str = "",
        **kwargs
    ) -> Tuple[Optional[str], Optional[str], float]:
        """
        파이프라인 실행

        Args:
            row_data: Google Sheets 행 데이터 (딕셔너리)
            row_number: 행 번호
            sheet_name: 시트 이름
            **kwargs: 추가 옵션

        Returns:
            (video_url, error_message, cost)
        """
        # 컨텍스트 생성
        context = self._create_context(row_data, row_number, sheet_name)

        logger.info(f"[AgentPipeline] 시작: 시트={sheet_name}, 행={row_number}")

        # 슈퍼바이저 실행
        result = await self.supervisor.execute(context, **kwargs)

        if result.success:
            logger.info(f"[AgentPipeline] 완료: URL={context.video_url}")
            return context.video_url, None, context.total_cost
        else:
            logger.error(f"[AgentPipeline] 실패: {result.error}")
            return None, result.error, context.total_cost

    def _create_context(
        self,
        row_data: Dict[str, Any],
        row_number: int,
        sheet_name: str
    ) -> VideoTaskContext:
        """
        Google Sheets 행 데이터에서 VideoTaskContext 생성

        Args:
            row_data: 행 데이터 딕셔너리
            row_number: 행 번호
            sheet_name: 시트 이름

        Returns:
            VideoTaskContext
        """
        # 필드 매핑 (Google Sheets 헤더 → Context 필드)
        script = row_data.get("대본", "") or ""
        title_input = row_data.get("제목(입력)", "") or row_data.get("제목", "") or ""
        thumbnail_text = row_data.get("썸네일문구(입력)", "") or ""
        channel_id = row_data.get("채널ID", "") or ""
        privacy = row_data.get("공개설정", "private") or "private"
        publish_at = row_data.get("예약시간", "") or None
        playlist_id = row_data.get("플레이리스트ID", "") or None
        voice = row_data.get("음성", "ko-KR-Neural2-C") or "ko-KR-Neural2-C"

        return VideoTaskContext(
            row_number=row_number,
            sheet_name=sheet_name,
            script=script,
            title_input=title_input,
            thumbnail_text_input=thumbnail_text,
            channel_id=channel_id,
            privacy_status=privacy,
            publish_at=publish_at,
            playlist_id=playlist_id,
            voice=voice,
        )

    def run_sync(
        self,
        row_data: Dict[str, Any],
        row_number: int,
        sheet_name: str = "",
        **kwargs
    ) -> Tuple[Optional[str], Optional[str], float]:
        """동기 실행"""
        return asyncio.run(self.run(row_data, row_number, sheet_name, **kwargs))


# 기본 인스턴스
_default_runner: Optional[AgentPipelineRunner] = None


def get_runner(server_url: str = None) -> AgentPipelineRunner:
    """기본 실행기 가져오기"""
    global _default_runner
    if _default_runner is None or server_url:
        _default_runner = AgentPipelineRunner(server_url)
    return _default_runner


async def run_agent_pipeline(
    row_data: Dict[str, Any],
    row_number: int,
    sheet_name: str = "",
    server_url: str = None,
    **kwargs
) -> Tuple[Optional[str], Optional[str], float]:
    """
    에이전트 기반 파이프라인 실행 (함수형 인터페이스)

    기존 run_automation_pipeline()과 호환되는 인터페이스입니다.

    사용법:
        from scripts.video_pipeline import run_agent_pipeline

        video_url, error, cost = await run_agent_pipeline(
            row_data={
                "대본": "대본 내용...",
                "제목(입력)": "영상 제목",
                ...
            },
            row_number=3,
            sheet_name="뉴스채널"
        )

    Args:
        row_data: Google Sheets 행 데이터
        row_number: 행 번호
        sheet_name: 시트 이름
        server_url: API 서버 URL (선택)
        **kwargs: 추가 옵션

    Returns:
        (video_url, error_message, cost)
    """
    runner = get_runner(server_url)
    return await runner.run(row_data, row_number, sheet_name, **kwargs)


def run_agent_pipeline_sync(
    row_data: Dict[str, Any],
    row_number: int,
    sheet_name: str = "",
    **kwargs
) -> Tuple[Optional[str], Optional[str], float]:
    """동기 버전"""
    return asyncio.run(run_agent_pipeline(row_data, row_number, sheet_name, **kwargs))


# ============================================================================
# 기존 파이프라인과의 통합을 위한 어댑터
# ============================================================================

async def integrate_with_existing_pipeline(
    run_automation_pipeline_func,
    row_data: Dict[str, Any],
    row_number: int,
    sheet_name: str,
    use_agent: bool = False,
    **kwargs
) -> Tuple[Optional[str], Optional[str], float]:
    """
    기존 파이프라인과 에이전트 파이프라인 선택적 실행

    환경변수 USE_AGENT_PIPELINE=1 또는 use_agent=True로 에이전트 파이프라인 사용

    Args:
        run_automation_pipeline_func: 기존 run_automation_pipeline 함수
        row_data: 행 데이터
        row_number: 행 번호
        sheet_name: 시트 이름
        use_agent: 에이전트 파이프라인 사용 여부
        **kwargs: 추가 옵션

    Returns:
        (video_url, error_message, cost)
    """
    use_agent = use_agent or os.environ.get("USE_AGENT_PIPELINE", "0") == "1"

    if use_agent:
        logger.info("[Pipeline] 에이전트 파이프라인 사용")
        return await run_agent_pipeline(row_data, row_number, sheet_name, **kwargs)
    else:
        logger.info("[Pipeline] 기존 파이프라인 사용")
        # 기존 함수 호출 (동기 또는 비동기)
        if asyncio.iscoroutinefunction(run_automation_pipeline_func):
            return await run_automation_pipeline_func(row_data, row_number, sheet_name, **kwargs)
        else:
            return run_automation_pipeline_func(row_data, row_number, sheet_name, **kwargs)
