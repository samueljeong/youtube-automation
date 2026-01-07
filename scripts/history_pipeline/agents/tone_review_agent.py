"""
한국사 파이프라인 - Tone Review Agent (어투/톤 검증 에이전트)

## 성격 및 역할
방송작가 출신 톤/문체 전문가.
대본이 지침(40-60대 대상, TTS 최적화)을 준수하는지 검증.

## 철학
- "글자수를 채우려고 지침을 어기면 안 된다"
- 타겟 시청자(40-60대)에 맞는 톤 일관성
- TTS 음성 품질을 위한 문체 최적화

## 책임
- 대본 어투/톤의 지침 준수 여부 검증
- 40-60대 부적합 표현 탐지
- TTS 부적합 문장 구조 탐지
- 문체 일관성 검사

## 검증 항목
1. 타겟 적합성: 40-60대에 맞는 어투인가?
2. TTS 최적화: 문장 길이, 쉼표 사용, 호흡 단위
3. 종결어미: 지침에 맞는 대화체 사용
4. 금지 표현: 학술적 유보, 젊은 세대 표현
5. 일관성: 문체 톤의 일관성

## 결과
- COMPLIANT: 지침 준수 (통과)
- MINOR_ISSUE: 경미한 위반 (경고)
- MAJOR_ISSUE: 심각한 위반 (수정 필요)
- NON_COMPLIANT: 지침 미준수 (재작성 필요)
"""

import re
import time
from typing import Any, Dict, List, Optional

from .base import BaseAgent, AgentResult, AgentStatus, EpisodeContext


# 40-60대 부적합 표현 목록
INAPPROPRIATE_FOR_SENIOR = [
    # 젊은 세대 유행어
    ("진짜", "MAJOR", "젊은 세대 표현", "정말/참으로"),
    ("대박", "MAJOR", "젊은 세대 표현", "놀랍게도/대단하게도"),
    ("미쳤다", "MAJOR", "젊은 세대 표현", "놀라운/대단한"),
    ("쩔어", "MAJOR", "젊은 세대 표현", "대단합니다"),
    ("존잼", "MAJOR", "젊은 세대 표현", "매우 흥미롭습니다"),
    ("개꿀", "MAJOR", "젊은 세대 표현", "삭제 권장"),
    ("ㅋㅋ", "MAJOR", "인터넷 용어", "삭제"),
    ("ㅎㅎ", "MAJOR", "인터넷 용어", "삭제"),

    # 구어체/속어
    ("엄청", "MINOR", "구어체", "매우/상당히"),
    ("진짜로", "MINOR", "구어체", "정말로/실제로"),
    ("완전", "MINOR", "구어체", "완벽히/전적으로"),
    ("겁나", "MAJOR", "속어", "매우/상당히"),
    ("존나", "MAJOR", "비속어", "삭제"),

    # 방송 부적합
    ("클릭", "MINOR", "인터넷 용어", "확인/참고"),
    ("구독", "MINOR", "유튜브 용어", "시청/관심 (대본 본문에서는 자제)"),
]

# 권장 종결어미
RECOMMENDED_ENDINGS = [
    "습니다",
    "입니다",
    "었습니다",
    "였습니다",
    "이죠",
    "죠",
    "요",
]

# TTS 부적합 패턴
TTS_ISSUES = [
    # 문장이 너무 긴 경우
    (r"[^.!?]{80,}[.!?]", "LONG_SENTENCE", "80자 이상 문장 - TTS 끊김 위험"),

    # 괄호 안 설명이 긴 경우
    (r"\([^)]{30,}\)", "LONG_PARENTHESIS", "괄호 안 설명이 김 - TTS 어색"),

    # 숫자가 많은 문장
    (r"[^.!?]*\d+[^.!?]*\d+[^.!?]*\d+[^.!?]*[.!?]", "MANY_NUMBERS", "숫자 과다 - 한글 변환 권장"),

    # 한자어 병기
    (r"[가-힣]+\([一-龥]+\)", "HANJA_ANNOTATION", "한자 병기 - TTS 부자연스러움"),

    # 연속 쉼표
    (r",\s*,", "CONSECUTIVE_COMMA", "연속 쉼표 - 문장 구조 개선 필요"),
]


class ToneReviewAgent(BaseAgent):
    """어투/톤 검증 에이전트"""

    def __init__(self):
        super().__init__("ToneReviewAgent")

        # 검증 설정
        self.inappropriate_expressions = INAPPROPRIATE_FOR_SENIOR
        self.recommended_endings = RECOMMENDED_ENDINGS
        self.tts_issues = TTS_ISSUES

        # 점수 기준
        self.pass_threshold = 70  # 70점 이상 통과
        self.warning_threshold = 50  # 50~69점 경고

    async def execute(self, context: EpisodeContext, **kwargs) -> AgentResult:
        """
        대본 어투/톤 검증 실행

        Args:
            context: 에피소드 컨텍스트 (script 필수)
            **kwargs:
                strict: 엄격 모드 (기본 True)

        Returns:
            AgentResult with tone review results
        """
        self.set_status(AgentStatus.RUNNING)
        start_time = time.time()

        strict = kwargs.get("strict", True)

        context.add_log(
            self.name,
            "어투/톤 검증 시작",
            "running",
            f"엄격 모드: {strict}"
        )

        try:
            # 대본 확인
            if not context.script:
                raise ValueError("대본(script)이 없습니다. ScriptAgent를 먼저 실행하세요.")

            script = context.script

            # 1. 부적합 표현 검사
            expression_issues = self._check_inappropriate_expressions(script)

            # 2. 종결어미 검사
            ending_issues = self._check_endings(script)

            # 3. TTS 적합성 검사
            tts_issues = self._check_tts_compatibility(script)

            # 4. 문체 일관성 검사
            consistency_issues = self._check_consistency(script)

            # 5. 학술적 유보 표현 검사
            academic_issues = self._check_academic_hedging(script)

            # 결과 종합
            all_issues = (
                expression_issues +
                ending_issues +
                tts_issues +
                consistency_issues +
                academic_issues
            )

            # 점수 계산
            score = self._calculate_score(all_issues, script)
            grade = self._get_grade(score)

            # 통과 여부 결정
            if strict:
                passed = score >= self.pass_threshold
            else:
                passed = score >= self.warning_threshold

            duration = time.time() - start_time

            result_status = "success" if passed else "warning"
            context.add_log(
                self.name,
                f"어투/톤 검증 완료: {grade}등급 ({score}점)",
                result_status,
                f"이슈 {len(all_issues)}건"
            )

            if passed:
                self.set_status(AgentStatus.SUCCESS)
            else:
                self.set_status(AgentStatus.WAITING_REVIEW)

            return AgentResult(
                success=True,
                data={
                    "passed": passed,
                    "score": score,
                    "grade": grade,
                    "total_issues": len(all_issues),
                    "issues": all_issues,
                    "issues_by_category": {
                        "expression": len(expression_issues),
                        "ending": len(ending_issues),
                        "tts": len(tts_issues),
                        "consistency": len(consistency_issues),
                        "academic": len(academic_issues),
                    },
                    "recommendation": self._generate_recommendation(all_issues, score, grade),
                },
                duration=duration,
            )

        except Exception as e:
            duration = time.time() - start_time
            error_msg = str(e)

            context.add_log(self.name, "어투/톤 검증 실패", "error", error_msg)
            self.set_status(AgentStatus.FAILED)

            return AgentResult(
                success=False,
                error=error_msg,
                duration=duration,
            )

    def _check_inappropriate_expressions(self, script: str) -> List[Dict[str, Any]]:
        """부적합 표현 검사"""
        issues = []

        for expr, severity, reason, suggestion in self.inappropriate_expressions:
            count = script.count(expr)
            if count > 0:
                issues.append({
                    "type": "EXPRESSION",
                    "severity": severity,
                    "text": expr,
                    "count": count,
                    "message": f"40-60대 부적합 표현: '{expr}' ({reason})",
                    "suggestion": f"→ '{suggestion}'으로 대체",
                })

        return issues

    def _check_endings(self, script: str) -> List[Dict[str, Any]]:
        """종결어미 검사"""
        issues = []

        # 문장 추출
        sentences = re.split(r'[.!?]', script)
        sentences = [s.strip() for s in sentences if s.strip()]

        # 종결어미 분석
        proper_endings = 0
        improper_sentences = []

        for sent in sentences:
            if len(sent) < 5:  # 너무 짧은 문장 스킵
                continue

            has_proper_ending = any(sent.endswith(ending) for ending in self.recommended_endings)
            if has_proper_ending:
                proper_endings += 1
            else:
                if len(improper_sentences) < 5:  # 최대 5개까지만 기록
                    improper_sentences.append(sent[-30:] if len(sent) > 30 else sent)

        # 적절한 종결어미 비율
        total = len([s for s in sentences if len(s) >= 5])
        if total > 0:
            proper_ratio = proper_endings / total
            if proper_ratio < 0.7:
                issues.append({
                    "type": "ENDING",
                    "severity": "MAJOR",
                    "text": f"적절한 종결어미 비율: {proper_ratio:.1%}",
                    "count": total - proper_endings,
                    "message": f"종결어미 지침 위반: {total - proper_endings}개 문장",
                    "suggestion": "~습니다, ~입니다, ~이죠 등 대화체 종결어미 사용",
                    "examples": improper_sentences[:3],
                })
            elif proper_ratio < 0.85:
                issues.append({
                    "type": "ENDING",
                    "severity": "MINOR",
                    "text": f"적절한 종결어미 비율: {proper_ratio:.1%}",
                    "count": total - proper_endings,
                    "message": f"종결어미 개선 권장: {total - proper_endings}개 문장",
                    "suggestion": "일관된 대화체 종결어미 사용 권장",
                })

        return issues

    def _check_tts_compatibility(self, script: str) -> List[Dict[str, Any]]:
        """TTS 적합성 검사"""
        issues = []

        for pattern, issue_type, message in self.tts_issues:
            matches = re.findall(pattern, script)
            if matches:
                for match in matches[:3]:  # 최대 3개만 표시
                    sample = match if len(match) <= 50 else match[:47] + "..."
                    issues.append({
                        "type": "TTS",
                        "severity": "MINOR" if issue_type in ["LONG_PARENTHESIS", "MANY_NUMBERS"] else "MAJOR",
                        "text": sample,
                        "message": message,
                        "suggestion": self._get_tts_suggestion(issue_type),
                    })

        return issues

    def _get_tts_suggestion(self, issue_type: str) -> str:
        """TTS 이슈 유형별 수정 제안"""
        suggestions = {
            "LONG_SENTENCE": "문장을 2-3개로 분리하세요 (권장: 50자 이하)",
            "LONG_PARENTHESIS": "괄호 내용을 별도 문장으로 분리하거나 삭제하세요",
            "MANY_NUMBERS": "숫자를 한글로 풀어쓰세요 (예: 698년 → 육백구십팔년)",
            "HANJA_ANNOTATION": "한자 병기를 삭제하세요 (TTS가 잘못 읽음)",
            "CONSECUTIVE_COMMA": "문장 구조를 개선하세요",
        }
        return suggestions.get(issue_type, "문장 구조 개선 필요")

    def _check_consistency(self, script: str) -> List[Dict[str, Any]]:
        """문체 일관성 검사"""
        issues = []

        # 존댓말/반말 혼용 체크
        formal_patterns = ["습니다", "입니다", "습니까"]
        informal_patterns = ["다\.", "냐\?", "니\?"]

        formal_count = sum(len(re.findall(p, script)) for p in formal_patterns)
        informal_count = sum(len(re.findall(p, script)) for p in informal_patterns)

        if formal_count > 0 and informal_count > 0:
            ratio = informal_count / (formal_count + informal_count)
            if ratio > 0.1:
                issues.append({
                    "type": "CONSISTENCY",
                    "severity": "MAJOR",
                    "text": f"존댓말/반말 혼용 (존댓말 {formal_count}회, 반말 {informal_count}회)",
                    "message": "문체 일관성 위반: 존댓말과 반말이 혼용됨",
                    "suggestion": "전체적으로 존댓말(~습니다, ~입니다)로 통일하세요",
                })

        return issues

    def _check_academic_hedging(self, script: str) -> List[Dict[str, Any]]:
        """학술적 유보 표현 검사"""
        issues = []

        hedging_patterns = [
            ("단정하기 어렵습니다", "MAJOR"),
            ("해석이 갈립니다", "MAJOR"),
            ("알 수 없습니다", "MAJOR"),
            ("추측입니다", "MAJOR"),
            ("~로 보입니다", "MINOR"),
            ("~로 추정됩니다", "MINOR"),
            ("~일 수도 있습니다", "MINOR"),
            ("~했을 것입니다", "MINOR"),
        ]

        total_hedging = 0
        for pattern, severity in hedging_patterns:
            count = script.count(pattern)
            if count > 0:
                total_hedging += count
                issues.append({
                    "type": "ACADEMIC",
                    "severity": severity,
                    "text": pattern,
                    "count": count,
                    "message": f"학술적 유보 표현 '{pattern}' {count}회 사용",
                    "suggestion": "확신 있는 서술로 수정 (단, 전체에서 1-2회는 허용)",
                })

        # 전체 유보 표현이 3회 이상이면 추가 경고
        if total_hedging >= 3:
            issues.append({
                "type": "ACADEMIC",
                "severity": "MAJOR",
                "text": f"학술적 유보 표현 총 {total_hedging}회",
                "message": "학술적 유보 표현 과다 사용 (지침: 전체에서 1-2회만)",
                "suggestion": "확신 있는 스토리텔러처럼 서술하세요",
            })

        return issues

    def _calculate_score(self, issues: List[Dict], script: str) -> int:
        """점수 계산 (100점 만점)"""
        score = 100

        for issue in issues:
            severity = issue.get("severity", "MINOR")
            count = issue.get("count", 1)

            if severity == "MAJOR":
                score -= 10 * min(count, 3)  # MAJOR당 최대 30점 감점
            elif severity == "MINOR":
                score -= 5 * min(count, 3)  # MINOR당 최대 15점 감점

        return max(0, min(100, score))

    def _get_grade(self, score: int) -> str:
        """등급 계산"""
        if score >= 90:
            return "S"
        elif score >= 80:
            return "A"
        elif score >= 70:
            return "B"
        elif score >= 50:
            return "C"
        else:
            return "D"

    def _generate_recommendation(self, issues: List[Dict], score: int, grade: str) -> str:
        """종합 권고사항 생성"""
        if grade in ["S", "A"]:
            return "✓ 어투/톤이 지침을 잘 준수하고 있습니다. 대본 진행 가능합니다."
        elif grade == "B":
            return f"⚠️ 경미한 수정이 필요합니다. {len(issues)}건의 이슈를 확인하세요."
        elif grade == "C":
            return f"⚠️ 상당한 수정이 필요합니다. 특히 40-60대 대상 어투를 점검하세요."
        else:
            return "❌ 지침 위반이 심각합니다. 문체 가이드를 참고하여 재작성을 권장합니다."


# 동기 실행 래퍼
def review_tone(context: EpisodeContext, strict: bool = True) -> Dict[str, Any]:
    """
    대본 어투/톤 검증 (동기 버전)

    Args:
        context: 에피소드 컨텍스트 (script 필수)
        strict: 엄격 모드

    Returns:
        검증 결과
    """
    import asyncio

    agent = ToneReviewAgent()

    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    result = loop.run_until_complete(
        agent.execute(context, strict=strict)
    )

    if result.success:
        return result.data
    else:
        raise Exception(result.error)


def review_tone_strict(script: str) -> Dict[str, Any]:
    """
    대본 어투/톤 엄격 검증 (블로킹)

    D등급(50점 미만) 시 ValueError 발생 - 파이프라인 진행 차단

    Args:
        script: 대본 텍스트

    Returns:
        검증 결과 (통과 시)

    Raises:
        ValueError: D등급 시
    """
    agent = ToneReviewAgent()

    # 임시 컨텍스트 생성
    context = EpisodeContext(
        episode_id="temp",
        episode_number=0,
        era_name="",
        era_episode=0,
        title="",
        topic="",
    )
    context.script = script

    import asyncio

    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    result = loop.run_until_complete(agent.execute(context, strict=True))

    if not result.success:
        raise Exception(result.error)

    data = result.data

    if data["grade"] == "D":
        major_issues = [i for i in data["issues"] if i.get("severity") == "MAJOR"]
        issues_str = "\n".join(f"  - {i['text']}: {i['message']}" for i in major_issues[:5])
        raise ValueError(
            f"어투/톤 검증 실패 - D등급 ({data['score']}점, 진행 불가):\n{issues_str}\n"
            f"권장: 40-60대 대상 문체 가이드 참고하여 재작성"
        )

    # C등급 경고
    if data["grade"] == "C":
        print(f"[ToneReviewAgent] 경고 - C등급 ({data['score']}점): 수정 권장")
        warnings_str = "\n".join(f"  ⚠️ {i['message']}" for i in data["issues"][:5])
        print(warnings_str)

    print(f"[ToneReviewAgent] ✓ 어투/톤 검증 통과: {data['grade']}등급 ({data['score']}점)")
    return data
