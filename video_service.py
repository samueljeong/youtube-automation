"""
비디오 생성 및 소셜 미디어 업로드 서비스
"""
import os
import json
import tempfile
from datetime import datetime
from typing import Dict, Optional, List
from PIL import Image, ImageDraw, ImageFont
from moviepy.editor import (
    ImageClip, TextClip, CompositeVideoClip,
    concatenate_videoclips, AudioFileClip
)
from moviepy.video.fx import fadein, fadeout
import requests


class VideoGenerator:
    """묵상메시지를 비디오로 변환하는 클래스"""

    def __init__(self, output_dir: str = "videos"):
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)

        # 세로형 비디오 설정 (9:16 비율)
        self.width = 1080
        self.height = 1920
        self.fps = 30

    def create_background_image(self, color: tuple = (30, 30, 50)) -> str:
        """배경 이미지 생성"""
        img = Image.new('RGB', (self.width, self.height), color)

        # 그라디언트 효과
        draw = ImageDraw.Draw(img)
        for i in range(self.height):
            alpha = i / self.height
            new_color = tuple(int(c * (1 - alpha * 0.3)) for c in color)
            draw.line([(0, i), (self.width, i)], fill=new_color)

        temp_path = os.path.join(self.output_dir, f"bg_{datetime.now().timestamp()}.png")
        img.save(temp_path)
        return temp_path

    def wrap_text(self, text: str, max_chars: int = 20) -> str:
        """텍스트 줄바꿈 처리"""
        words = text.split()
        lines = []
        current_line = []
        current_length = 0

        for word in words:
            if current_length + len(word) + 1 <= max_chars:
                current_line.append(word)
                current_length += len(word) + 1
            else:
                if current_line:
                    lines.append(' '.join(current_line))
                current_line = [word]
                current_length = len(word)

        if current_line:
            lines.append(' '.join(current_line))

        return '\n'.join(lines)

    def create_sermon_video(
        self,
        title: str,
        scripture_reference: str,
        content: str,
        duration: int = 15
    ) -> str:
        """
        묵상메시지 비디오 생성

        Args:
            title: 제목
            scripture_reference: 성경 구절 참조
            content: 본문 내용
            duration: 비디오 길이 (초)

        Returns:
            생성된 비디오 파일 경로
        """
        try:
            # 배경 이미지 생성
            bg_path = self.create_background_image()
            bg_clip = ImageClip(bg_path, duration=duration)

            clips = [bg_clip]

            # 제목 텍스트
            title_wrapped = self.wrap_text(title, 25)
            title_clip = TextClip(
                title_wrapped,
                fontsize=80,
                color='white',
                font='Arial-Bold',
                size=(self.width - 100, None),
                method='caption'
            ).set_position(('center', 200)).set_duration(duration)
            clips.append(title_clip)

            # 성경 구절
            ref_clip = TextClip(
                scripture_reference,
                fontsize=50,
                color='#FFD700',
                font='Arial',
                size=(self.width - 100, None)
            ).set_position(('center', 450)).set_duration(duration)
            clips.append(ref_clip)

            # 본문 내용 (요약)
            content_short = content[:200] + "..." if len(content) > 200 else content
            content_wrapped = self.wrap_text(content_short, 30)
            content_clip = TextClip(
                content_wrapped,
                fontsize=45,
                color='white',
                font='Arial',
                size=(self.width - 150, None),
                method='caption'
            ).set_position(('center', 700)).set_duration(duration)
            clips.append(content_clip)

            # 모든 클립 합성
            final_clip = CompositeVideoClip(clips, size=(self.width, self.height))

            # 페이드 인/아웃 효과
            final_clip = fadein(final_clip, 0.5)
            final_clip = fadeout(final_clip, 0.5)

            # 비디오 저장
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = os.path.join(self.output_dir, f"sermon_{timestamp}.mp4")

            final_clip.write_videofile(
                output_path,
                fps=self.fps,
                codec='libx264',
                audio=False,
                preset='medium',
                threads=4
            )

            # 임시 파일 정리
            if os.path.exists(bg_path):
                os.remove(bg_path)

            return output_path

        except Exception as e:
            raise Exception(f"비디오 생성 실패: {str(e)}")


class YouTubeUploader:
    """YouTube API를 사용한 비디오 업로드"""

    def __init__(self, credentials: Dict):
        """
        Args:
            credentials: {
                'client_id': str,
                'client_secret': str,
                'refresh_token': str
            }
        """
        self.credentials = credentials

    def upload(
        self,
        video_path: str,
        title: str,
        description: str,
        tags: List[str] = None,
        privacy_status: str = 'public'
    ) -> Dict:
        """
        YouTube Shorts로 비디오 업로드

        Returns:
            {'video_id': str, 'url': str, 'status': str}
        """
        try:
            from google.oauth2.credentials import Credentials
            from googleapiclient.discovery import build
            from googleapiclient.http import MediaFileUpload

            # OAuth2 인증
            creds = Credentials(
                None,
                refresh_token=self.credentials['refresh_token'],
                token_uri='https://oauth2.googleapis.com/token',
                client_id=self.credentials['client_id'],
                client_secret=self.credentials['client_secret']
            )

            youtube = build('youtube', 'v3', credentials=creds)

            # 비디오 메타데이터
            body = {
                'snippet': {
                    'title': title[:100],  # YouTube 제목 제한
                    'description': description,
                    'tags': tags or ['묵상', '성경', '말씀'],
                    'categoryId': '22'  # People & Blogs
                },
                'status': {
                    'privacyStatus': privacy_status,
                    'selfDeclaredMadeForKids': False
                }
            }

            # 비디오 업로드
            media = MediaFileUpload(
                video_path,
                chunksize=-1,
                resumable=True,
                mimetype='video/mp4'
            )

            request = youtube.videos().insert(
                part='snippet,status',
                body=body,
                media_body=media
            )

            response = request.execute()

            video_id = response['id']
            return {
                'video_id': video_id,
                'url': f'https://www.youtube.com/shorts/{video_id}',
                'status': 'success'
            }

        except Exception as e:
            return {
                'video_id': None,
                'url': None,
                'status': 'error',
                'error': str(e)
            }


class InstagramUploader:
    """Instagram Graph API를 사용한 릴스 업로드"""

    def __init__(self, credentials: Dict):
        """
        Args:
            credentials: {
                'access_token': str,
                'instagram_account_id': str
            }
        """
        self.credentials = credentials
        self.base_url = 'https://graph.facebook.com/v18.0'

    def upload(
        self,
        video_path: str,
        caption: str
    ) -> Dict:
        """
        Instagram 릴스로 비디오 업로드

        Returns:
            {'media_id': str, 'url': str, 'status': str}
        """
        try:
            access_token = self.credentials['access_token']
            account_id = self.credentials['instagram_account_id']

            # 1단계: 비디오를 공개 URL로 업로드 (별도 서버 필요)
            # 실제 구현시 S3, CloudFlare 등 사용
            # 여기서는 간단히 로컬 서버 URL 가정
            video_url = self._upload_to_temp_storage(video_path)

            # 2단계: 미디어 컨테이너 생성
            create_url = f'{self.base_url}/{account_id}/media'
            create_params = {
                'video_url': video_url,
                'media_type': 'REELS',
                'caption': caption,
                'access_token': access_token
            }

            create_response = requests.post(create_url, data=create_params)
            create_data = create_response.json()

            if 'id' not in create_data:
                raise Exception(f"미디어 컨테이너 생성 실패: {create_data}")

            container_id = create_data['id']

            # 3단계: 미디어 게시
            publish_url = f'{self.base_url}/{account_id}/media_publish'
            publish_params = {
                'creation_id': container_id,
                'access_token': access_token
            }

            publish_response = requests.post(publish_url, data=publish_params)
            publish_data = publish_response.json()

            if 'id' not in publish_data:
                raise Exception(f"미디어 게시 실패: {publish_data}")

            media_id = publish_data['id']

            return {
                'media_id': media_id,
                'url': f'https://www.instagram.com/reel/{media_id}',
                'status': 'success'
            }

        except Exception as e:
            return {
                'media_id': None,
                'url': None,
                'status': 'error',
                'error': str(e)
            }

    def _upload_to_temp_storage(self, video_path: str) -> str:
        """임시 스토리지에 비디오 업로드 (실제 구현 필요)"""
        # 실제로는 S3, CloudFlare R2 등에 업로드
        # 여기서는 플레이스홀더
        return f"https://your-storage.com/videos/{os.path.basename(video_path)}"


class TikTokUploader:
    """TikTok API를 사용한 비디오 업로드"""

    def __init__(self, credentials: Dict):
        """
        Args:
            credentials: {
                'access_token': str,
                'open_id': str
            }
        """
        self.credentials = credentials
        self.base_url = 'https://open-api.tiktok.com'

    def upload(
        self,
        video_path: str,
        title: str,
        privacy_level: str = 'PUBLIC_TO_EVERYONE'
    ) -> Dict:
        """
        TikTok에 비디오 업로드

        Returns:
            {'video_id': str, 'url': str, 'status': str}
        """
        try:
            access_token = self.credentials['access_token']
            open_id = self.credentials['open_id']

            # 1단계: 업로드 URL 요청
            init_url = f'{self.base_url}/share/video/upload/'
            headers = {
                'Authorization': f'Bearer {access_token}',
                'Content-Type': 'application/json'
            }

            # 비디오 파일 읽기
            with open(video_path, 'rb') as video_file:
                video_data = video_file.read()

            # 2단계: 비디오 업로드
            upload_data = {
                'video': {
                    'title': title,
                    'privacy_level': privacy_level,
                    'disable_duet': False,
                    'disable_comment': False,
                    'disable_stitch': False,
                    'video_cover_timestamp_ms': 1000
                }
            }

            files = {
                'video': ('video.mp4', video_data, 'video/mp4')
            }

            response = requests.post(
                init_url,
                headers=headers,
                data={'post_info': json.dumps(upload_data)},
                files=files
            )

            result = response.json()

            if result.get('data', {}).get('error_code') == 0:
                share_id = result['data']['share_id']
                return {
                    'video_id': share_id,
                    'url': f'https://www.tiktok.com/@user/video/{share_id}',
                    'status': 'success'
                }
            else:
                raise Exception(f"TikTok 업로드 실패: {result}")

        except Exception as e:
            return {
                'video_id': None,
                'url': None,
                'status': 'error',
                'error': str(e)
            }


class VideoService:
    """비디오 생성 및 업로드를 통합 관리하는 서비스"""

    def __init__(self):
        self.generator = VideoGenerator()

    def create_and_upload(
        self,
        sermon_data: Dict,
        platforms: List[str],
        credentials_map: Dict[str, Dict]
    ) -> Dict:
        """
        비디오 생성 및 다중 플랫폼 업로드

        Args:
            sermon_data: {
                'title': str,
                'scripture_reference': str,
                'content': str,
                'duration': int (optional)
            }
            platforms: ['youtube', 'instagram', 'tiktok']
            credentials_map: {
                'youtube': {...},
                'instagram': {...},
                'tiktok': {...}
            }

        Returns:
            {
                'video_path': str,
                'uploads': {
                    'youtube': {...},
                    'instagram': {...},
                    'tiktok': {...}
                }
            }
        """
        # 비디오 생성
        video_path = self.generator.create_sermon_video(
            title=sermon_data['title'],
            scripture_reference=sermon_data['scripture_reference'],
            content=sermon_data['content'],
            duration=sermon_data.get('duration', 15)
        )

        results = {
            'video_path': video_path,
            'uploads': {}
        }

        # 각 플랫폼에 업로드
        for platform in platforms:
            if platform not in credentials_map:
                results['uploads'][platform] = {
                    'status': 'error',
                    'error': 'Credentials not provided'
                }
                continue

            try:
                if platform == 'youtube':
                    uploader = YouTubeUploader(credentials_map['youtube'])
                    result = uploader.upload(
                        video_path,
                        title=sermon_data['title'],
                        description=f"{sermon_data['scripture_reference']}\n\n{sermon_data['content'][:500]}"
                    )

                elif platform == 'instagram':
                    uploader = InstagramUploader(credentials_map['instagram'])
                    caption = f"{sermon_data['title']}\n{sermon_data['scripture_reference']}\n\n#묵상 #성경 #말씀"
                    result = uploader.upload(video_path, caption)

                elif platform == 'tiktok':
                    uploader = TikTokUploader(credentials_map['tiktok'])
                    result = uploader.upload(video_path, sermon_data['title'])

                else:
                    result = {
                        'status': 'error',
                        'error': f'Unknown platform: {platform}'
                    }

                results['uploads'][platform] = result

            except Exception as e:
                results['uploads'][platform] = {
                    'status': 'error',
                    'error': str(e)
                }

        return results
