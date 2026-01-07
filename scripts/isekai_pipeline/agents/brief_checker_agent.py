"""
혈영 이세계편 - BriefCheckerAgent (기획서 검증)

기획서가 Series Bible을 준수하는지 검증합니다.
- Series Bible 일관성
- 캐릭터 등장 시점
- 씬 구조 완성도
- 이전화 연속성
"""

from typing import Dict, Any, List, Optional
from .base import BaseAgent, EpisodeContext, AgentResult


# 파트별 캐릭터 등장 가이드
CHARACTER_APPEARANCE = {
    # 1부 (1~10화) - 적응, 각성
    "part1": {
        "range": (1, 10),
        "required": ["무영"],
        "allowed": ["무영", "설하", "카이든"],
        "forbidden": ["에이라", "이그니스", "마르쿠스"],
        "notes": "카이든은 2화부터 등장",
    },
    # 2부 (11~20화) - 성장, 소드마스터
    "part2": {
        "range": (11, 20),
        "required": ["무영", "카이든"],
        "allowed": ["무영", "설하", "카이든", "에이라"],
        "forbidden": ["이그니스", "마르쿠스"],
        "notes": "에이라는 12화부터 등장",
    },
    # 3부 (21~30화) - 이그니스, 명성
    "part3": {
        "range": (21, 30),
        "required": ["무영", "카이든", "에이라"],
        "allowed": ["무영", "설하", "카이든", "에이라", "이그니스"],
        "forbidden": ["마르쿠스"],
        "notes": "이그니스는 21화부터 등장",
    },
    # 4부 (31~40화) - 혈마 발견, 정치
    "part4": {
        "range": (31, 40),
        "required": ["무영", "카이든", "에이라"],
        "allowed": ["무영", "설하", "카이든", "에이라", "이그니스", "마르쿠스"],
        "forbidden": [],
        "notes": "마르쿠스는 31화부터 등장",
    },
    # 5부 (41~50화) - 전쟁
    "part5": {
        "range": (41, 50),
        "required": ["무영"],
        "allowed": ["무영", "설하", "카이든", "에이라", "이그니스", "마르쿠스", "혈마"],
        "forbidden": [],
        "notes": "혈마 부활",
    },
    # 6부 (51~60화) - 최종전, 귀환
    "part6": {
        "range": (51, 60),
        "required": ["무영", "설하"],
        "allowed": ["무영", "설하", "카이든", "에이라", "이그니스", "마르쿠스", "혈마"],
        "forbidden": [],
        "notes": "전원 등장 가능",
    },
}


class BriefCheckerAgent(BaseAgent):
    """기획서 검증 에이전트"""

    def __init__(self, series_bible: str = None):
        super().__init__("BriefChecker")
        self.series_bible = series_bible or ""

    async def execute(self, context: EpisodeContext, **kwargs) -> AgentResult:
        """BaseAgent의 추상 메서드 구현"""
        try:
            episode = context.episode_number
            brief = context.brief or kwargs.get("brief", {})
            prev_brief = kwargs.get("prev_brief")

            result = self.check(episode, brief, prev_brief)

            passed = result["grade"] == "PASS"
            return AgentResult(
                success=passed,
                data=result,
                feedback=result.get("verdict"),
                needs_improvement=not passed,
                improvement_targets=result.get("errors", []),
            )
        except Exception as e:
            return AgentResult(
                success=False,
                error=str(e),
            )

    def get_part_info(self, episode: int) -> Dict[str, Any]:
        """에피소드 번호로 파트 정보 조회"""
        for part_name, info in CHARACTER_APPEARANCE.items():
            start, end = info["range"]
            if start <= episode <= end:
                return {**info, "part": part_name}
        return CHARACTER_APPEARANCE["part1"]

    def check_characters(self, episode: int, characters: List[str]) -> Dict[str, Any]:
        """캐릭터 등장 검증"""
        part_info = self.get_part_info(episode)
        result = {
            "valid": True,
            "score": 20,
            "errors": [],
            "warnings": [],
        }

        # 필수 캐릭터 체크
        for char in part_info["required"]:
            if char not in characters:
                result["errors"].append(f"필수 캐릭터 '{char}' 누락")
                result["score"] -= 5

        # 금지 캐릭터 체크
        for char in characters:
            if char in part_info.get("forbidden", []):
                result["errors"].append(f"'{char}'는 {part_info['part']}에서 등장 불가")
                result["score"] -= 10

        # 특수 조건 체크
        if episode == 1 and "카이든" in characters:
            result["warnings"].append("카이든은 2화부터 등장 권장")
            result["score"] -= 2

        if episode < 12 and "에이라" in characters:
            result["errors"].append("에이라는 12화부터 등장")
            result["score"] -= 10

        result["valid"] = result["score"] >= 15
        return result

    def check_scene_structure(self, brief: Dict[str, Any]) -> Dict[str, Any]:
        """씬 구조 검증"""
        result = {
            "valid": True,
            "score": 25,
            "errors": [],
        }

        scenes = brief.get("scenes", [])
        required_scenes = ["오프닝", "전개", "클라이맥스", "해결", "엔딩"]

        if len(scenes) < 5:
            result["errors"].append(f"씬 {len(scenes)}개, 최소 5개 필요")
            result["score"] -= (5 - len(scenes)) * 5

        for scene_name in required_scenes:
            found = any(scene_name in str(s) for s in scenes)
            if not found:
                result["errors"].append(f"'{scene_name}' 씬 누락")
                result["score"] -= 3

        result["valid"] = result["score"] >= 20
        return result

    def check_series_bible_compliance(self, brief: Dict[str, Any]) -> Dict[str, Any]:
        """Series Bible 준수 검증"""
        result = {
            "valid": True,
            "score": 25,
            "errors": [],
            "warnings": [],
        }

        # 세계관 키워드 체크
        worldbuilding_keywords = ["이세계", "무림", "내공", "검술", "마법"]
        brief_text = str(brief).lower()

        keyword_count = sum(1 for kw in worldbuilding_keywords if kw in brief_text)
        if keyword_count < 2:
            result["warnings"].append("세계관 키워드 부족")
            result["score"] -= 5

        # 주인공 설정 체크
        if "무영" not in brief_text:
            result["errors"].append("주인공 '무영' 언급 없음")
            result["score"] -= 10

        result["valid"] = result["score"] >= 20
        return result

    def check_continuity(self, episode: int, brief: Dict[str, Any], prev_brief: Dict[str, Any] = None) -> Dict[str, Any]:
        """이전화 연속성 검증"""
        result = {
            "valid": True,
            "score": 15,
            "errors": [],
            "warnings": [],
        }

        if episode == 1:
            # 1화는 연속성 검증 불필요
            return result

        if prev_brief is None:
            result["warnings"].append("이전화 기획서 없음, 연속성 검증 스킵")
            return result

        # TODO: 이전화와의 연속성 검증 로직
        # - 스토리 연결
        # - 캐릭터 상태 일관성
        # - 위치/시간 연속성

        return result

    def check_cliffhanger(self, brief: Dict[str, Any]) -> Dict[str, Any]:
        """클리프행어/다음화 훅 검증"""
        result = {
            "valid": True,
            "score": 15,
            "errors": [],
        }

        hook = brief.get("next_episode_hook", "")
        if not hook or len(hook) < 10:
            result["errors"].append("다음화 훅 없음 또는 너무 짧음")
            result["score"] -= 10

        result["valid"] = result["score"] >= 10
        return result

    def check(self, episode: int, brief: Dict[str, Any], prev_brief: Dict[str, Any] = None) -> Dict[str, Any]:
        """기획서 종합 검증"""
        characters = brief.get("characters", [])

        # 각 항목 검증
        char_result = self.check_characters(episode, characters)
        scene_result = self.check_scene_structure(brief)
        bible_result = self.check_series_bible_compliance(brief)
        cont_result = self.check_continuity(episode, brief, prev_brief)
        hook_result = self.check_cliffhanger(brief)

        # 총점 계산
        total_score = (
            char_result["score"] +
            scene_result["score"] +
            bible_result["score"] +
            cont_result["score"] +
            hook_result["score"]
        )

        # 등급 산정
        if total_score >= 80:
            grade = "PASS"
            verdict = "통과"
        elif total_score >= 60:
            grade = "REVISION"
            verdict = "수정 필요"
        else:
            grade = "REJECT"
            verdict = "재작성"

        # 모든 에러/경고 수집
        all_errors = (
            char_result.get("errors", []) +
            scene_result.get("errors", []) +
            bible_result.get("errors", []) +
            cont_result.get("errors", []) +
            hook_result.get("errors", [])
        )

        all_warnings = (
            char_result.get("warnings", []) +
            bible_result.get("warnings", []) +
            cont_result.get("warnings", [])
        )

        return {
            "episode": episode,
            "total_score": total_score,
            "grade": grade,
            "verdict": verdict,
            "details": {
                "characters": char_result,
                "scene_structure": scene_result,
                "series_bible": bible_result,
                "continuity": cont_result,
                "cliffhanger": hook_result,
            },
            "errors": all_errors,
            "warnings": all_warnings,
            "part_info": self.get_part_info(episode),
        }
