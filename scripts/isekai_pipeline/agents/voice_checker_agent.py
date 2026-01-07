"""
혈영 이세계편 - VoiceCheckerAgent (말투 검증)

캐릭터 대사의 일관성을 검증합니다.
- 캐릭터별 말투 패턴
- 대사 스타일 일관성
"""

import re
from typing import Dict, Any, List
from .base import BaseAgent, EpisodeContext, AgentResult


# 캐릭터 말투 정의
CHARACTER_VOICES = {
    "무영": {
        "style": "짧고 건조한 독백체",
        "endings": ["했다", "이다", "군", "..."],
        "patterns": [r"'.*?'"],  # 독백 패턴
        "forbidden": ["요", "습니다", "~지!"],
        "description": "내면 독백 많음, 감정 절제, 짧은 문장",
    },
    "카이든": {
        "style": "밝고 친근한 반말",
        "endings": ["지!", "잖아", "거든", "다고!"],
        "patterns": [r'".*?!"'],
        "forbidden": ["하오", "소이다", "~옵니다"],
        "description": "활기참, 친근한 반말, 감탄사 많음",
    },
    "에이라": {
        "style": "고아체 존칭",
        "endings": ["하오", "이오", "소", "시오"],
        "patterns": [],
        "forbidden": ["~지!", "잖아", "거든"],
        "description": "정중한 고아체, 격식 있는 어투",
    },
    "설하": {
        "style": "부드럽고 걱정하는 존칭",
        "endings": ["요", "세요", "ㄹ게요"],
        "patterns": [r'"무영.*?"'],
        "forbidden": ["~지!", "하오", "잖아"],
        "description": "부드러운 존칭, 걱정 많음, 무영 부르기",
    },
    "이그니스": {
        "style": "위엄 있는 왕족 어투",
        "endings": ["하라", "이다", "도다"],
        "patterns": [],
        "forbidden": ["~지!", "잖아", "요"],
        "description": "위엄, 명령형, 권위적",
    },
}


class VoiceCheckerAgent(BaseAgent):
    """캐릭터 말투 검증 에이전트"""

    def __init__(self):
        super().__init__("VoiceChecker")

    async def execute(self, context: EpisodeContext, **kwargs) -> AgentResult:
        """BaseAgent의 추상 메서드 구현"""
        try:
            script = context.script or kwargs.get("script", "")
            if not script:
                return AgentResult(
                    success=False,
                    error="대본이 없습니다",
                )

            result = self.check(script)

            passed = result["grade"] in ["A", "B"]
            return AgentResult(
                success=passed,
                data=result,
                feedback=result.get("verdict"),
                needs_improvement=not passed,
            )
        except Exception as e:
            return AgentResult(
                success=False,
                error=str(e),
            )

    def extract_dialogues(self, script: str) -> List[Dict[str, Any]]:
        """대사 추출"""
        dialogues = []

        # "대사" 패턴
        quoted = re.findall(r'"([^"]+)"', script)
        for q in quoted:
            dialogues.append({"type": "quote", "text": q})

        return dialogues

    def identify_speaker(self, context: str, dialogue: str) -> str:
        """대사 화자 추정"""
        # 간단한 규칙 기반 추정
        for char_name in CHARACTER_VOICES.keys():
            if char_name in context:
                return char_name

        # 말투로 추정
        for char_name, voice in CHARACTER_VOICES.items():
            for ending in voice["endings"]:
                if dialogue.endswith(ending) or ending in dialogue:
                    return char_name

        return "unknown"

    def check_character_voice(self, character: str, dialogues: List[str]) -> Dict[str, Any]:
        """특정 캐릭터 말투 검증"""
        if character not in CHARACTER_VOICES:
            return {"valid": True, "score": 100, "issues": []}

        voice = CHARACTER_VOICES[character]
        result = {
            "valid": True,
            "score": 100,
            "issues": [],
            "stats": {
                "total_dialogues": len(dialogues),
                "consistent": 0,
                "inconsistent": 0,
            },
        }

        for dialogue in dialogues:
            # 금지 패턴 체크
            for forbidden in voice.get("forbidden", []):
                if forbidden in dialogue:
                    result["issues"].append({
                        "type": "forbidden",
                        "pattern": forbidden,
                        "dialogue": dialogue[:50],
                    })
                    result["stats"]["inconsistent"] += 1
                    result["score"] -= 5

            # 어미 패턴 체크 (권장)
            has_expected_ending = any(dialogue.endswith(e) or e in dialogue for e in voice.get("endings", []))
            if has_expected_ending:
                result["stats"]["consistent"] += 1

        result["valid"] = result["score"] >= 70
        return result

    def check(self, script: str) -> Dict[str, Any]:
        """말투 종합 검증"""

        # 전체 대사 추출
        all_dialogues = self.extract_dialogues(script)

        # 캐릭터별 검증 결과
        character_results = {}
        total_score = 0
        checked_count = 0

        for char_name in CHARACTER_VOICES.keys():
            # 해당 캐릭터 대사 필터링 (간단한 방식)
            char_dialogues = [d["text"] for d in all_dialogues if char_name in script]

            if char_dialogues:
                result = self.check_character_voice(char_name, char_dialogues[:20])  # 최대 20개
                character_results[char_name] = result
                total_score += result["score"]
                checked_count += 1

        # 평균 점수
        avg_score = total_score / checked_count if checked_count > 0 else 100

        # 등급 산정
        if avg_score >= 80:
            grade = "A"
            verdict = "일관성 우수"
        elif avg_score >= 60:
            grade = "B"
            verdict = "양호"
        else:
            grade = "C"
            verdict = "개선 필요"

        return {
            "total_score": avg_score,
            "grade": grade,
            "verdict": verdict,
            "characters_checked": list(character_results.keys()),
            "details": character_results,
            "total_dialogues": len(all_dialogues),
        }
