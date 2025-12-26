"""
PublishAgent - 배포 에이전트

역할:
- YouTube 영상 업로드
- 썸네일 설정 (업로드 시 함께 처리)
- 메타데이터 설정 (제목, 설명, 태그)
- 플레이리스트 추가 (업로드 시 함께 처리)
- 예약 공개 설정
- 쇼츠 업로드
- SEO 최적화 (챕터, 해시태그, CTA)
"""

import asyncio
import re
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
            hashtags = youtube.get("hashtags", [])
            tags = youtube.get("tags", [])
            pin_comment = youtube.get("pin_comment", "")  # ★ 고정 댓글

            # description이 객체인 경우 문자열로 변환 (원본 파이프라인과 동일)
            if isinstance(description, dict):
                desc_dict = description  # 원본 dict 보존
                # ★ 원본 파이프라인 구조: full_text, chapters, preview_2_lines
                description = desc_dict.get("full_text", "")
                if not description:
                    # 폴백: 다른 구조 시도 (summary, main, tags)
                    desc_parts = []
                    if desc_dict.get("summary"):
                        desc_parts.append(desc_dict.get("summary"))
                    if desc_dict.get("main"):
                        desc_parts.append(desc_dict.get("main"))
                    if desc_dict.get("tags"):
                        desc_parts.append(" ".join(f"#{t}" for t in desc_dict.get("tags", [])))
                    description = "\n\n".join(desc_parts) if desc_parts else ""
            elif not isinstance(description, str):
                description = str(description) if description else ""

            # ★ 설명이 비어있으면 기본 설명 추가
            if not description.strip():
                description = f"📺 {title}\n\n영상을 시청해 주셔서 감사합니다."
                self.log("description이 비어있어 기본 설명 사용", "warning")

            # ★ GPT 예상 챕터 제거 (실제 duration 기반으로 재생성)
            description = self._remove_gpt_chapters(description)

            # ★ 자동 챕터 생성 (씬별 duration 기반)
            chapters_text = self._generate_chapters(context.scenes)
            if chapters_text:
                description = description + chapters_text
                self.log(f"자동 챕터 생성 완료")

            # ★ 해시태그 추가
            if hashtags:
                hashtags_text = "\n\n" + " ".join(hashtags)
                description = description + hashtags_text
                self.log(f"해시태그 {len(hashtags)}개 추가")

            # ★ CTA 추가 (구독/좋아요 유도)
            description = self._add_cta(description, title)

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

            # ★ 고정 댓글 추가 (GPT가 생성한 pin_comment)
            if pin_comment and pin_comment.strip():
                payload["firstComment"] = pin_comment
                self.log(f"  - 고정 댓글: {pin_comment[:50]}...")
            else:
                self.log(f"  - 고정 댓글: 없음")

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

            # ★ 댓글 작성 결과 확인
            comment_posted = result.get("commentPosted", False)
            comment_id = result.get("commentId")
            if pin_comment:
                if comment_posted:
                    self.log(f"✅ 고정 댓글 작성 완료 (YouTube Studio에서 고정 필요)")
                else:
                    self.log(f"⚠️ 고정 댓글 작성 실패 (댓글 비활성화 또는 권한 문제)", "warning")

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
                    "comment_posted": comment_posted,  # ★ 댓글 작성 여부
                    "comment_id": comment_id,  # ★ 댓글 ID
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

    def _remove_gpt_chapters(self, description: str) -> str:
        """
        GPT가 예상으로 생성한 챕터 제거 (원본 파이프라인과 동일)

        GPT가 추정한 duration 기반 챕터는 실제와 다를 수 있으므로 제거하고
        실제 TTS duration 기반으로 재생성합니다.
        """
        if not description:
            return ""

        try:
            lines = description.split('\n')
            cleaned_lines = []
            in_chapter_section = False
            consecutive_timestamps = 0
            timestamp_pattern = re.compile(r'^\d{1,2}:\d{2}(?::\d{2})?\s')

            for line in lines:
                stripped = line.strip()

                # 타임스탬프 패턴 감지 (0:00, 1:23, 12:34:56)
                if timestamp_pattern.match(stripped):
                    consecutive_timestamps += 1
                    # 2개 이상 연속 타임스탬프면 챕터 섹션으로 간주
                    if consecutive_timestamps >= 2:
                        in_chapter_section = True
                    # 챕터 섹션이면 해당 줄 스킵
                    if in_chapter_section or consecutive_timestamps >= 2:
                        continue
                    else:
                        cleaned_lines.append(line)
                else:
                    consecutive_timestamps = 0
                    if in_chapter_section:
                        # 빈 줄이면 챕터 섹션 종료
                        if not stripped:
                            in_chapter_section = False
                        # 타임스탬프가 아닌 줄이 오면 챕터 섹션 종료
                        else:
                            in_chapter_section = False
                            cleaned_lines.append(line)
                    else:
                        cleaned_lines.append(line)

            return '\n'.join(cleaned_lines)
        except Exception:
            return description

    def _generate_chapters(self, scenes: List[Dict[str, Any]]) -> str:
        """
        자동 챕터 생성 (씬별 duration 기반, 원본 파이프라인과 동일)

        YouTube 챕터는 0:00부터 시작해야 하고, 최소 3개 이상이어야 합니다.
        """
        if not scenes:
            return ""

        try:
            chapters_text = "\n\n📑 챕터\n"
            current_time = 0
            has_chapters = False
            chapter_count = 0

            for idx, scene in enumerate(scenes):
                chapter_title = scene.get('chapter_title', '')
                scene_duration = scene.get('duration', 0)

                if chapter_title:
                    has_chapters = True
                    chapter_count += 1

                    # 타임스탬프 형식: M:SS 또는 H:MM:SS
                    minutes = int(current_time // 60)
                    seconds = int(current_time % 60)
                    if minutes >= 60:
                        hours = minutes // 60
                        minutes = minutes % 60
                        timestamp = f"{hours}:{minutes:02d}:{seconds:02d}"
                    else:
                        timestamp = f"{minutes}:{seconds:02d}"

                    chapters_text += f"{timestamp} {chapter_title}\n"

                current_time += scene_duration

            # YouTube는 최소 3개 챕터 필요
            if has_chapters and chapter_count >= 3:
                return chapters_text
            else:
                return ""
        except Exception:
            return ""

    def _add_cta(self, description: str, title: str) -> str:
        """
        CTA(Call to Action) 추가 - 구독/좋아요 유도 (원본 파이프라인과 동일)
        """
        if not description:
            description = ""

        # 이미 CTA가 있는지 확인
        cta_keywords = ['구독', '좋아요', '알림', '댓글', 'subscribe', 'like']
        has_cta = any(keyword.lower() in description.lower() for keyword in cta_keywords)

        # CTA가 없으면 추가
        if not has_cta:
            cta_text = "\n\n" + "=" * 30 + "\n"
            cta_text += "👍 이 영상이 도움이 되셨다면 좋아요와 구독 부탁드립니다!\n"
            cta_text += "🔔 알림 설정하시면 새로운 영상을 놓치지 않습니다.\n"
            cta_text += "💬 궁금한 점은 댓글로 남겨주세요!"
            description = description + cta_text

        return description
