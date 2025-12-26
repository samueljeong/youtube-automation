"""
PublishAgent - 배포 에이전트

역할:
- YouTube 영상 업로드
- 썸네일 설정 (업로드 시 함께 처리)
- 메타데이터 설정 (제목, 설명, 태그)
- 플레이리스트 추가 (업로드 시 함께 처리)
- 예약 공개 설정
- 쇼츠 업로드
"""

import asyncio
import time
import json
import base64
from typing import Any, Dict, List, Optional
from pathlib import Path

import httpx

from .base import BaseAgent, AgentResult, VideoTaskContext, AgentStatus


class PublishAgent(BaseAgent):
    """배포 에이전트 (YouTube 업로드)"""

    def __init__(self, server_url: str = "http://localhost:5059"):
        super().__init__("PublishAgent", max_retries=2)
        self.server_url = server_url
        self.upload_timeout = 300  # 5분

    async def execute(self, context: VideoTaskContext, **kwargs) -> AgentResult:
        """
        YouTube 업로드

        Args:
            context: 작업 컨텍스트
            **kwargs:
                skip_thumbnail: 썸네일 설정 스킵
                skip_playlist: 플레이리스트 추가 스킵

        Returns:
            AgentResult with video URL
        """
        start_time = time.time()
        self.set_status(AgentStatus.RUNNING)
        context.upload_attempts += 1

        try:
            if not context.video_path:
                return AgentResult(
                    success=False,
                    error="영상 파일 없음"
                )

            video_path = Path(context.video_path)
            if not video_path.exists():
                return AgentResult(
                    success=False,
                    error="영상 파일을 찾을 수 없음"
                )

            self.log(f"YouTube 업로드 시작: {video_path.name}")

            # 메타데이터 준비
            youtube = context.youtube_metadata or {}
            title = youtube.get("title", "Untitled")
            description = youtube.get("description", "")

            # description이 객체인 경우 문자열로 변환
            if isinstance(description, dict):
                # description 객체를 문자열로 변환
                desc_parts = []
                if description.get("summary"):
                    desc_parts.append(description.get("summary"))
                if description.get("main"):
                    desc_parts.append(description.get("main"))
                if description.get("tags"):
                    desc_parts.append(" ".join(f"#{t}" for t in description.get("tags", [])))
                description = "\n\n".join(desc_parts) if desc_parts else str(description)
            elif not isinstance(description, str):
                description = str(description) if description else ""

            tags = youtube.get("tags", [])

            # 업로드 요청 - API가 videoPath를 직접 받음
            # drama_server.py의 /api/youtube/upload 참조
            payload = {
                "videoPath": str(video_path),  # 영상 파일 경로 직접 전달
                "title": title,
                "description": description,
                "tags": tags,
                "privacyStatus": context.privacy_status or "private",
                "channelId": context.channel_id,
                "projectSuffix": context.project_suffix,  # YouTube 프로젝트 ('', '_2')
            }

            # 썸네일 경로 추가 (API가 처리)
            if context.thumbnail_path:
                payload["thumbnailPath"] = context.thumbnail_path

            # 플레이리스트 ID 추가 (API가 처리)
            if context.playlist_id:
                payload["playlistId"] = context.playlist_id

            # 예약 공개
            if context.publish_at:
                payload["publish_at"] = context.publish_at

            self.log(f"  - 제목: {title[:50]}...")
            self.log(f"  - 썸네일: {'있음' if context.thumbnail_path else '없음'}")
            self.log(f"  - 플레이리스트: {context.playlist_id or '없음'}")

            async with httpx.AsyncClient(timeout=self.upload_timeout) as client:
                response = await client.post(
                    f"{self.server_url}/api/youtube/upload",
                    json=payload
                )
                response.raise_for_status()
                result = response.json()

            if not result.get("ok"):
                return AgentResult(
                    success=False,
                    error=result.get("error", "업로드 실패")
                )

            # 응답에서 video_id 추출 (API 응답 형식에 맞춤)
            video_id = result.get("video_id") or result.get("videoId")
            video_url = result.get("video_url") or f"https://www.youtube.com/watch?v={video_id}"
            context.video_url = video_url

            duration = time.time() - start_time

            self.log(f"✅ 업로드 완료: {video_url}")

            context.add_log(
                self.name, "upload", "success",
                f"video_id={video_id}, url={video_url}"
            )

            self.set_status(AgentStatus.SUCCESS)

            return AgentResult(
                success=True,
                data={
                    "video_id": video_id,
                    "video_url": video_url,
                    "title": title,
                },
                cost=0.0,  # YouTube API는 무료
                duration=duration
            )

        except httpx.TimeoutException:
            self.set_status(AgentStatus.FAILED)
            return AgentResult(
                success=False,
                error="업로드 타임아웃 (5분 초과)"
            )
        except Exception as e:
            self.set_status(AgentStatus.FAILED)
            context.add_log(self.name, "upload", "error", str(e))
            return AgentResult(
                success=False,
                error=str(e)
            )

    async def upload_shorts(
        self,
        context: VideoTaskContext,
        shorts_path: str
    ) -> AgentResult:
        """
        쇼츠 업로드

        Args:
            context: 작업 컨텍스트
            shorts_path: 쇼츠 영상 경로

        Returns:
            AgentResult with shorts URL
        """
        path = Path(shorts_path)
        if not path.exists():
            return AgentResult(
                success=False,
                error="쇼츠 파일 없음"
            )

        self.log("쇼츠 업로드 시작")

        try:
            # 쇼츠 메타데이터
            shorts_config = context.video_effects.get("shorts", {}) if context.video_effects else {}
            title = shorts_config.get("title", "")
            if not title:
                main_title = context.youtube_metadata.get("title", "") if context.youtube_metadata else ""
                title = f"{main_title[:50]} #Shorts"

            # 메인 영상 링크 포함
            description = f"원본 영상: {context.video_url}\n\n#Shorts"

            payload = {
                "videoPath": str(path),
                "title": title,
                "description": description,
                "tags": ["shorts"],
                "privacyStatus": context.privacy_status or "private",
                "channelId": context.channel_id,
                "projectSuffix": context.project_suffix,  # YouTube 프로젝트 ('', '_2')
            }

            async with httpx.AsyncClient(timeout=self.upload_timeout) as client:
                response = await client.post(
                    f"{self.server_url}/api/youtube/upload",
                    json=payload
                )
                response.raise_for_status()
                result = response.json()

            if result.get("ok"):
                shorts_id = result.get("video_id") or result.get("videoId")
                shorts_url = f"https://www.youtube.com/shorts/{shorts_id}"
                context.shorts_url = shorts_url

                self.log(f"✅ 쇼츠 업로드 완료: {shorts_url}")

                return AgentResult(
                    success=True,
                    data={
                        "shorts_id": shorts_id,
                        "shorts_url": shorts_url,
                    }
                )
            else:
                return AgentResult(
                    success=False,
                    error=result.get("error", "쇼츠 업로드 실패")
                )

        except Exception as e:
            return AgentResult(
                success=False,
                error=str(e)
            )
