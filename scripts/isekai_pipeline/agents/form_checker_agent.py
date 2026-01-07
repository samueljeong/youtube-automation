"""
혈영 이세계편 - FormCheckerAgent (문체 검증)

대본의 문체/형식 일관성을 검증합니다.
- 문장 길이 (50자 이하)
- 문단 길이 (5줄 이하)
- 문장부호 규칙
- 태그 없음
"""

import re
from typing import Dict, Any, List
from .base import BaseAgent, EpisodeContext, AgentResult


class FormCheckerAgent(BaseAgent):
    """문체/형식 검증 에이전트"""

    def __init__(self):
        super().__init__("FormChecker")

        # 검증 설정
        self.max_sentence_length = 50
        self.max_paragraph_lines = 5
        self.forbidden_patterns = [
            r'\[.*?\]',  # [태그]
            r'\(.*?설명.*?\)',  # (설명)
            r'<.*?>',  # <태그>
        ]

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

    def check_sentence_length(self, script: str) -> Dict[str, Any]:
        """문장 길이 검증"""
        result = {
            "valid": True,
            "score": 25,
            "long_sentences": [],
            "stats": {},
        }

        sentences = re.split(r'[.!?]\s*', script)
        sentence_lengths = [len(s.strip()) for s in sentences if s.strip()]

        if not sentence_lengths:
            return result

        result["stats"] = {
            "total": len(sentence_lengths),
            "avg_length": sum(sentence_lengths) / len(sentence_lengths),
            "max_length": max(sentence_lengths),
        }

        # 긴 문장 찾기
        for i, s in enumerate(sentences):
            if len(s.strip()) > self.max_sentence_length:
                result["long_sentences"].append({
                    "index": i,
                    "length": len(s.strip()),
                    "preview": s.strip()[:80] + "..." if len(s.strip()) > 80 else s.strip(),
                })

        # 점수 계산
        long_ratio = len(result["long_sentences"]) / len(sentence_lengths) if sentence_lengths else 0
        if long_ratio > 0.3:
            result["score"] -= 15
        elif long_ratio > 0.1:
            result["score"] -= 5

        result["valid"] = result["score"] >= 20
        return result

    def check_paragraph_length(self, script: str) -> Dict[str, Any]:
        """문단 길이 검증"""
        result = {
            "valid": True,
            "score": 25,
            "long_paragraphs": [],
        }

        paragraphs = script.split('\n\n')
        for i, para in enumerate(paragraphs):
            lines = [l for l in para.split('\n') if l.strip()]
            if len(lines) > self.max_paragraph_lines:
                result["long_paragraphs"].append({
                    "index": i,
                    "lines": len(lines),
                    "preview": para[:100] + "..." if len(para) > 100 else para,
                })

        # 점수 계산
        if len(result["long_paragraphs"]) > 10:
            result["score"] -= 15
        elif len(result["long_paragraphs"]) > 5:
            result["score"] -= 5

        result["valid"] = result["score"] >= 20
        return result

    def check_forbidden_patterns(self, script: str) -> Dict[str, Any]:
        """금지 패턴 검증"""
        result = {
            "valid": True,
            "score": 25,
            "violations": [],
        }

        for pattern in self.forbidden_patterns:
            matches = re.findall(pattern, script)
            if matches:
                result["violations"].extend(matches[:5])  # 최대 5개만

        # 점수 계산
        if len(result["violations"]) > 5:
            result["score"] -= 20
        elif len(result["violations"]) > 0:
            result["score"] -= len(result["violations"]) * 3

        result["valid"] = result["score"] >= 15
        return result

    def check_punctuation(self, script: str) -> Dict[str, Any]:
        """문장부호 규칙 검증"""
        result = {
            "valid": True,
            "score": 25,
            "issues": [],
        }

        # 마침표 뒤 공백
        no_space_after_period = re.findall(r'[.!?][가-힣]', script)
        if no_space_after_period:
            result["issues"].append(f"마침표 뒤 공백 없음 {len(no_space_after_period)}건")
            result["score"] -= min(len(no_space_after_period), 10)

        # 쉼표 뒤 공백
        no_space_after_comma = re.findall(r',[가-힣]', script)
        if len(no_space_after_comma) > 10:
            result["issues"].append(f"쉼표 뒤 공백 없음 {len(no_space_after_comma)}건")
            result["score"] -= 5

        result["valid"] = result["score"] >= 20
        return result

    def check(self, script: str) -> Dict[str, Any]:
        """문체 종합 검증"""

        # 각 항목 검증
        sentence_result = self.check_sentence_length(script)
        paragraph_result = self.check_paragraph_length(script)
        pattern_result = self.check_forbidden_patterns(script)
        punctuation_result = self.check_punctuation(script)

        # 총점 계산
        total_score = (
            sentence_result["score"] +
            paragraph_result["score"] +
            pattern_result["score"] +
            punctuation_result["score"]
        )

        # 등급 산정
        if total_score >= 80:
            grade = "A"
            verdict = "우수"
        elif total_score >= 60:
            grade = "B"
            verdict = "양호"
        elif total_score >= 40:
            grade = "C"
            verdict = "개선 필요"
        else:
            grade = "D"
            verdict = "수정 필요"

        return {
            "total_score": total_score,
            "grade": grade,
            "verdict": verdict,
            "details": {
                "sentence_length": sentence_result,
                "paragraph_length": paragraph_result,
                "forbidden_patterns": pattern_result,
                "punctuation": punctuation_result,
            },
            "script_stats": {
                "total_chars": len(script),
                "total_lines": len(script.split('\n')),
            },
        }
