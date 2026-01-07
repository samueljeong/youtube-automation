"""
혈영 이세계편 - Base Agent

모든 에이전트의 기본 클래스와 이세계 전용 컨텍스트 정의
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

    혈영 이세계편 60화 시리즈 제작을 위한 모든 정보를 담습니다.
    """
    # 기본 정보
    task_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    episode_id: str = ""          # "EP001"
    episode_number: int = 0       # 1

    # 파트/스토리 정보
    part: int = 1                 # 파트 번호 (1~6)
    part_name: str = ""           # "적응, 각성"
    title: str = ""               # "전생, 이계에서의 첫 걸음"

    # Series Bible 참조
    series_bible: Optional[str] = None
    world_setting: Optional[Dict[str, Any]] = None

    # 이전/다음 에피소드 정보 (연결성)
    prev_episode: Optional[Dict[str, Any]] = None
    next_episode: Optional[Dict[str, Any]] = None

    # 캐릭터 정보
    characters: List[str] = field(default_factory=list)  # 등장 캐릭터
    character_profiles: Optional[Dict[str, Any]] = None

    # ===== 기획 에이전트 출력 =====
    brief: Optional[Dict[str, Any]] = None  # 기획서
    # brief 구조:
    # {
    #     "hook": "첫 문장 훅",
    #     "scenes": [
    #         {"name": "오프닝", "description": "...", "target_chars": 2100},
    #         {"name": "전개", "description": "...", "target_chars": 3100},
    #         {"name": "클라이맥스", "description": "...", "target_chars": 3900},
    #         {"name": "해결", "description": "...", "target_chars": 2800},
    #         {"name": "엔딩", "description": "...", "target_chars": 2100},
    #     ],
    #     "key_points": ["핵심 포인트 1", ...],
    #     "next_episode_hook": "다음화 예고 훅",
    # }

    # ===== 대본 에이전트 출력 =====
    script: Optional[str] = None  # 대본 본문 (12,000~15,000자)
    scenes: List[str] = field(default_factory=list)  # 씬별 분할 대본
    script_metadata: Optional[Dict[str, Any]] = None
    # script_metadata 구조:
    # {
    #     "youtube_title": "유튜브 제목",
    #     "youtube_description": "유튜브 설명",
    #     "youtube_tags": ["태그1", "태그2"],
    #     "thumbnail_text": "썸네일 문구",
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

    def get_part_info(self) -> Dict[str, Any]:
        """현재 파트 정보 반환"""
        PARTS = {
            1: {"range": (1, 10), "name": "적응, 각성", "focus": "무영의 이세계 적응과 능력 각성"},
            2: {"range": (11, 20), "name": "성장, 소드마스터", "focus": "소드마스터 성장과 에이라 등장"},
            3: {"range": (21, 30), "name": "이그니스, 명성", "focus": "이그니스 왕국과 명성 획득"},
            4: {"range": (31, 40), "name": "혈마 발견, 정치", "focus": "혈마 흔적 발견과 정치적 갈등"},
            5: {"range": (41, 50), "name": "전쟁", "focus": "혈마 부활과 대전쟁"},
            6: {"range": (51, 60), "name": "최종전, 귀환", "focus": "최종 결전과 귀환"},
        }
        return PARTS.get(self.part, PARTS[1])

    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리 변환"""
        return {
            "task_id": self.task_id,
            "episode_id": self.episode_id,
            "episode_number": self.episode_number,
            "part": self.part,
            "part_name": self.part_name,
            "title": self.title,
            "characters": self.characters,
            "prev_episode": self.prev_episode,
            "next_episode": self.next_episode,
            "brief": self.brief,
            "script": self.script[:500] + "..." if self.script and len(self.script) > 500 else self.script,
            "script_length": len(self.script) if self.script else 0,
            "scenes_count": len(self.scenes),
            "script_metadata": self.script_metadata,
            "image_prompts": self.image_prompts,
            "generated_images": self.generated_images,
            "brief_attempts": self.brief_attempts,
            "script_attempts": self.script_attempts,
            "image_attempts": self.image_attempts,
            "logs": self.logs[-10:],  # 최근 10개 로그만
        }

    @classmethod
    def from_episode(
        cls,
        episode_number: int,
        title: str = "",
        characters: List[str] = None,
        prev_episode_info: Optional[Dict[str, Any]] = None,
        next_episode_info: Optional[Dict[str, Any]] = None,
    ) -> "EpisodeContext":
        """에피소드 번호로부터 컨텍스트 생성"""
        # 파트 결정
        if episode_number <= 10:
            part = 1
        elif episode_number <= 20:
            part = 2
        elif episode_number <= 30:
            part = 3
        elif episode_number <= 40:
            part = 4
        elif episode_number <= 50:
            part = 5
        else:
            part = 6

        PART_NAMES = {
            1: "적응, 각성",
            2: "성장, 소드마스터",
            3: "이그니스, 명성",
            4: "혈마 발견, 정치",
            5: "전쟁",
            6: "최종전, 귀환",
        }

        return cls(
            episode_id=f"EP{episode_number:03d}",
            episode_number=episode_number,
            part=part,
            part_name=PART_NAMES.get(part, ""),
            title=title,
            characters=characters or [],
            prev_episode=prev_episode_info,
            next_episode=next_episode_info,
        )
