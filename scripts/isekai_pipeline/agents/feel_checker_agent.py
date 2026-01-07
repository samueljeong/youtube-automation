"""
혈영 이세계편 - FeelCheckerAgent (감정 검증)

대본의 분위기/감정 흐름을 검증합니다.
- 감정 전환 자연스러움
- 긴장-이완 밸런스
- 클라이맥스 임팩트
"""

import re
from typing import Dict, Any, List
from .base import BaseAgent, EpisodeContext, AgentResult


# 감정 키워드
EMOTION_KEYWORDS = {
    "tension": ["긴장", "두근", "떨", "위험", "죽", "피", "검", "싸움", "공격", "방어"],
    "relief": ["안도", "숨", "살", "무사", "괜찮", "다행"],
    "sadness": ["슬", "눈물", "그리", "떠나", "죽음", "이별"],
    "hope": ["희망", "살", "돌아", "기다", "약속", "반드시"],
    "anger": ["분노", "화", "이를 악물", "복수", "죽여"],
    "calm": ["조용", "평화", "고요", "바람", "하늘"],
}

# 씬별 기대 감정
SCENE_EMOTIONS = {
    1: {"primary": "tension", "secondary": ["hope"], "name": "오프닝"},
    2: {"primary": "calm", "secondary": ["tension"], "name": "전개"},
    3: {"primary": "tension", "secondary": ["anger"], "name": "클라이맥스"},
    4: {"primary": "relief", "secondary": ["hope"], "name": "해결"},
    5: {"primary": "hope", "secondary": ["calm"], "name": "엔딩"},
}


class FeelCheckerAgent(BaseAgent):
    """감정/분위기 검증 에이전트"""

    def __init__(self):
        super().__init__("FeelChecker")

    async def execute(self, context: EpisodeContext, **kwargs) -> AgentResult:
        """BaseAgent의 추상 메서드 구현"""
        try:
            script = context.script or kwargs.get("script", "")
            scenes = context.scenes or kwargs.get("scenes", [])
            if not script:
                return AgentResult(
                    success=False,
                    error="대본이 없습니다",
                )

            result = self.check(script, scenes if scenes else None)

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

    def analyze_emotion(self, text: str) -> Dict[str, int]:
        """텍스트 감정 분석"""
        emotion_counts = {emotion: 0 for emotion in EMOTION_KEYWORDS.keys()}

        text_lower = text.lower()
        for emotion, keywords in EMOTION_KEYWORDS.items():
            for keyword in keywords:
                count = len(re.findall(keyword, text_lower))
                emotion_counts[emotion] += count

        return emotion_counts

    def get_dominant_emotion(self, emotion_counts: Dict[str, int]) -> str:
        """지배적 감정 반환"""
        if not emotion_counts or all(v == 0 for v in emotion_counts.values()):
            return "neutral"
        return max(emotion_counts, key=emotion_counts.get)

    def check_scene_emotion(self, scene_index: int, scene_text: str) -> Dict[str, Any]:
        """씬별 감정 검증"""
        expected = SCENE_EMOTIONS.get(scene_index, SCENE_EMOTIONS[1])
        emotion_counts = self.analyze_emotion(scene_text)
        dominant = self.get_dominant_emotion(emotion_counts)

        result = {
            "scene": scene_index,
            "scene_name": expected["name"],
            "expected_primary": expected["primary"],
            "actual_dominant": dominant,
            "emotion_counts": emotion_counts,
            "match": dominant == expected["primary"] or dominant in expected.get("secondary", []),
            "score": 20,
        }

        if not result["match"]:
            result["score"] -= 5
            result["issue"] = f"기대 감정 '{expected['primary']}', 실제 '{dominant}'"

        return result

    def check_emotion_flow(self, scenes: List[str]) -> Dict[str, Any]:
        """감정 흐름 검증"""
        result = {
            "valid": True,
            "score": 100,
            "flow": [],
            "issues": [],
        }

        prev_emotion = None
        for i, scene in enumerate(scenes, 1):
            emotion_counts = self.analyze_emotion(scene)
            dominant = self.get_dominant_emotion(emotion_counts)

            result["flow"].append({
                "scene": i,
                "emotion": dominant,
                "intensity": sum(emotion_counts.values()),
            })

            # 급격한 감정 변화 체크
            if prev_emotion:
                # 긴장 → 안도는 OK, 안도 → 긴장도 OK
                # 하지만 슬픔 → 분노는 부자연스러움
                if prev_emotion == "sadness" and dominant == "anger":
                    result["issues"].append(f"씬{i}: 슬픔→분노 급격한 전환")
                    result["score"] -= 10

            prev_emotion = dominant

        result["valid"] = result["score"] >= 70
        return result

    def check_climax_impact(self, scenes: List[str]) -> Dict[str, Any]:
        """클라이맥스 임팩트 검증"""
        result = {
            "valid": True,
            "score": 100,
            "issues": [],
        }

        if len(scenes) < 3:
            return result

        # 씬3 (클라이맥스) 분석
        climax = scenes[2] if len(scenes) > 2 else scenes[-1]
        climax_emotions = self.analyze_emotion(climax)
        climax_intensity = sum(climax_emotions.values())

        # 다른 씬들의 평균 강도
        other_intensities = []
        for i, scene in enumerate(scenes):
            if i != 2:
                other_intensities.append(sum(self.analyze_emotion(scene).values()))

        avg_other = sum(other_intensities) / len(other_intensities) if other_intensities else 0

        # 클라이맥스가 가장 강렬해야 함
        if avg_other > 0 and climax_intensity < avg_other * 1.2:
            result["issues"].append("클라이맥스 강도가 다른 씬보다 낮음")
            result["score"] -= 20

        result["climax_intensity"] = climax_intensity
        result["avg_other_intensity"] = avg_other
        result["valid"] = result["score"] >= 70
        return result

    def check(self, script: str, scenes: List[str] = None) -> Dict[str, Any]:
        """감정 종합 검증"""

        # 씬 분리가 없으면 전체 스크립트 분석
        if not scenes:
            scenes = [script]

        # 씬별 감정 검증
        scene_results = []
        for i, scene in enumerate(scenes, 1):
            scene_results.append(self.check_scene_emotion(i, scene))

        # 감정 흐름 검증
        flow_result = self.check_emotion_flow(scenes)

        # 클라이맥스 임팩트 검증
        climax_result = self.check_climax_impact(scenes)

        # 총점 계산
        scene_score = sum(r["score"] for r in scene_results) / len(scene_results) if scene_results else 100
        total_score = (scene_score + flow_result["score"] + climax_result["score"]) / 3

        # 등급 산정
        if total_score >= 80:
            grade = "A"
            verdict = "감정 흐름 우수"
        elif total_score >= 60:
            grade = "B"
            verdict = "양호"
        else:
            grade = "C"
            verdict = "개선 필요"

        return {
            "total_score": total_score,
            "grade": grade,
            "verdict": verdict,
            "scene_emotions": scene_results,
            "emotion_flow": flow_result,
            "climax_impact": climax_result,
        }
