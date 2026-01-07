"""
한국사 파이프라인 - Base Agent

모든 에이전트의 기본 클래스와 한국사 전용 컨텍스트 정의
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
import time
import uuid

# 공통 클래스 import
from scripts.common import AgentStatus, AgentResult, BaseAgent

# 하위 호환성을 위한 re-export
__all__ = ["AgentStatus", "AgentResult", "BaseAgent", "EpisodeContext"]


@dataclass
class EpisodeContext:
    """
    에피소드 컨텍스트 - 에이전트 간 공유 데이터

    한국사 다큐멘터리 에피소드 제작을 위한 모든 정보를 담습니다.
    """
    # 기본 정보
    task_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    episode_id: str = ""          # "ep018"
    episode_number: int = 0       # 18

    # 시대/주제 정보
    era: str = ""                 # "NAMBUK"
    era_name: str = ""            # "남북국시대"
    era_episode: int = 0          # 시대 내 에피소드 번호 (1)
    title: str = ""               # "통일신라, 새로운 질서를 세우다"
    topic: str = ""               # "통일신라 체제 정비"

    # 이전/다음 에피소드 정보 (연결성)
    prev_episode: Optional[Dict[str, Any]] = None
    next_episode: Optional[Dict[str, Any]] = None

    # 참고 자료
    reference_links: List[str] = field(default_factory=list)
    keywords: List[str] = field(default_factory=list)
    collected_materials: Optional[Dict[str, Any]] = None  # 수집된 자료

    # ===== 기획 에이전트 출력 =====
    brief: Optional[Dict[str, Any]] = None  # 기획서
    # brief 구조:
    # {
    #     "hook": "첫 문장 훅",
    #     "structure": [{"part": "인트로", "description": "...", "target_chars": 1500}, ...],
    #     "key_points": ["핵심 포인트 1", ...],
    #     "narrative_style": "스토리텔링 방식",
    #     "ending_hook": "다음화 예고 훅",
    # }

    # ===== 대본 에이전트 출력 =====
    script: Optional[str] = None  # 대본 본문 (12,000~15,000자)
    script_metadata: Optional[Dict[str, Any]] = None
    # script_metadata 구조:
    # {
    #     "youtube_title": "유튜브 제목",
    #     "youtube_description": "유튜브 설명",
    #     "youtube_tags": ["태그1", "태그2"],
    #     "thumbnail_text": "썸네일 문구",
    #     "chapters": [{"title": "챕터명", "start_char": 0}, ...],
    # }

    # ===== 이미지 에이전트 출력 =====
    image_prompts: List[Dict[str, Any]] = field(default_factory=list)
    # image_prompts 구조:
    # [
    #     {"scene_index": 0, "prompt": "썸네일 프롬프트 (영문)", "description": "한글 설명"},
    #     {"scene_index": 1, "prompt": "씬1 프롬프트", "description": "..."},
    # ]
    generated_images: List[str] = field(default_factory=list)  # 생성된 이미지 경로

    # ===== 검수 피드백 =====
    brief_feedback: Optional[str] = None
    script_feedback: Optional[str] = None
    image_feedback: Optional[str] = None

    # 시도 횟수
    brief_attempts: int = 0
    script_attempts: int = 0
    image_attempts: int = 0

    # 설정
    max_attempts: int = 3
    target_script_length: int = 13500  # 목표 글자수
    min_script_length: int = 12000
    max_script_length: int = 15000

    # 로그
    logs: List[Dict[str, Any]] = field(default_factory=list)

    def add_log(self, agent: str, action: str, result: str, details: str = ""):
        """로그 추가"""
        self.logs.append({
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "agent": agent,
            "action": action,
            "result": result,
            "details": details,
        })

    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리 변환"""
        return {
            "task_id": self.task_id,
            "episode_id": self.episode_id,
            "episode_number": self.episode_number,
            "era": self.era,
            "era_name": self.era_name,
            "era_episode": self.era_episode,
            "title": self.title,
            "topic": self.topic,
            "prev_episode": self.prev_episode,
            "next_episode": self.next_episode,
            "reference_links": self.reference_links,
            "keywords": self.keywords,
            "brief": self.brief,
            "script": self.script[:500] + "..." if self.script and len(self.script) > 500 else self.script,
            "script_length": len(self.script) if self.script else 0,
            "script_metadata": self.script_metadata,
            "image_prompts": self.image_prompts,
            "generated_images": self.generated_images,
            "brief_attempts": self.brief_attempts,
            "script_attempts": self.script_attempts,
            "image_attempts": self.image_attempts,
            "logs": self.logs[-10:],  # 최근 10개 로그만
        }

    @classmethod
    def from_topic(
        cls,
        episode_number: int,
        era: str,
        era_episode: int,
        topic_info: Dict[str, Any],
        era_info: Dict[str, Any],
        prev_episode_info: Optional[Dict[str, Any]] = None,
        next_episode_info: Optional[Dict[str, Any]] = None,
    ) -> "EpisodeContext":
        """HISTORY_TOPICS의 주제 정보로부터 컨텍스트 생성"""
        return cls(
            episode_id=f"ep{episode_number:03d}",
            episode_number=episode_number,
            era=era,
            era_name=era_info.get("name", era),
            era_episode=era_episode,
            title=topic_info.get("title", ""),
            topic=topic_info.get("topic", ""),
            reference_links=topic_info.get("reference_links", []),
            keywords=topic_info.get("keywords", []),
            prev_episode=prev_episode_info,
            next_episode=next_episode_info,
        )
