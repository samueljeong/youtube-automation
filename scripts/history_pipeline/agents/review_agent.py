"""
한국사 파이프라인 - Review Agent (검수 에이전트)

## 성격 및 역할
깐깐하고 철저한 스타일.
대충 넘어가지 않고 문제를 파악해서 개선할 수 있는 능력 보유.

## 철학
- "타협 없는 품질" - 한 번 통과한 대본은 완벽해야 한다
- 작은 문제라도 놓치지 않음
- 비판이 아닌 개선을 위한 피드백

## 책임
- 대본 품질 검수 (길이, 문체, 역사적 정확성)
- 구체적이고 실행 가능한 피드백 생성
- 최종 승인/반려 결정 (S/A/B/C/D 등급)

## 검수 기준
- 길이: 12,000~15,000자 (30점)
- 구조: 5단계 구조 준수 (20점)
- 문체: 대화체, 질문 활용 (20점)
- 정확성: 연도, 숫자, 사례 (20점)
- 스토리텔링: 훅, 몰입도, 마무리 (10점)

## 통과 기준
- S등급 (90점+): 즉시 통과
- A등급 (80-89점): 사소한 수정 후 통과
- B등급 (70-79점): 수정 필요
- C/D등급: 재작성 필요
"""

import re
import time
from typing import Any, Dict, List, Optional, Tuple

from .base import BaseAgent, AgentResult, AgentStatus, EpisodeContext


# 검수 기준
REVIEW_CRITERIA = """
## 대본 검수 기준 (한국사 다큐멘터리)

### 1. 길이 (30점)
- 12,000~15,000자: 30점
- 11,000~12,000자 또는 15,000~16,000자: 20점
- 그 외: 10점

### 2. 구조 (20점)
- 인트로/배경/본론1/본론2/마무리 구조: 20점
- 일부 누락: 10점
- 구조 불분명: 5점

### 3. 문체 (20점)
- 대화체 종결어미 사용 (~거든요, ~었어요): 10점
- 가정법/질문 활용: 5점
- 학술적 유보 표현 최소화: 5점

### 4. 역사적 정확성 (20점)
- 구체적 연도/숫자 사용: 10점
- 역사적 인물/사건 명시: 10점

### 5. 스토리텔링 (10점)
- 훅이 명확한가: 3점
- 몰입도 있는 전개: 4점
- 다음 화 예고가 자연스러운가: 3점

### 등급
- S (90-100): 즉시 통과
- A (80-89): 사소한 수정 후 통과
- B (70-79): 수정 필요
- C (60-69): 대폭 수정 필요
- D (60 미만): 재작성 필요
"""


class ReviewAgent(BaseAgent):
    """검수 에이전트"""

    def __init__(self):
        super().__init__("ReviewAgent")

        # 검수 설정
        self.min_length = 12000
        self.max_length = 15000
        self.target_length = 13500

        # 금지 표현
        self.forbidden_phrases = [
            "단정하기 어렵습니다",
            "해석이 갈립니다",
            "알 수 없습니다",
            "정확하지 않습니다",
            "추측입니다",
        ]

        # 권장 표현 패턴
        self.recommended_patterns = [
            r"거든요",
            r"었어요",
            r"죠[\.?]",
            r"\?",  # 질문
        ]

    async def execute(self, context: EpisodeContext, **kwargs) -> AgentResult:
        """
        대본 검수 실행

        Args:
            context: 에피소드 컨텍스트 (script 필수)
            **kwargs:
                strict: 엄격 모드 (기본 False)

        Returns:
            AgentResult with review data
        """
        self.set_status(AgentStatus.RUNNING)
        start_time = time.time()

        strict = kwargs.get("strict", False)

        context.add_log(
            self.name,
            "대본 검수 시작",
            "running",
            f"엄격 모드: {strict}"
        )

        try:
            # 대본 확인
            if not context.script:
                raise ValueError("대본(script)이 없습니다. ScriptAgent를 먼저 실행하세요.")

            script = context.script

            # 검수 항목별 점수 계산
            scores = self._evaluate_script(script, context)

            # 총점 및 등급 계산
            total_score = sum(scores.values())
            grade = self._calculate_grade(total_score)

            # 피드백 생성
            feedback = self._generate_feedback(script, scores, context)

            # 통과 여부 결정
            passed = self._determine_pass(grade, strict)

            duration = time.time() - start_time

            result_status = "success" if passed else "warning"
            context.add_log(
                self.name,
                f"검수 완료: {grade} ({total_score}점)",
                result_status,
                f"통과: {passed}"
            )

            if passed:
                self.set_status(AgentStatus.SUCCESS)
            else:
                self.set_status(AgentStatus.WAITING_REVIEW)

            return AgentResult(
                success=True,
                data={
                    "scores": scores,
                    "total_score": total_score,
                    "grade": grade,
                    "passed": passed,
                    "feedback": feedback,
                    "review_criteria": REVIEW_CRITERIA,
                },
                duration=duration,
            )

        except Exception as e:
            duration = time.time() - start_time
            error_msg = str(e)

            context.add_log(self.name, "검수 실패", "error", error_msg)
            self.set_status(AgentStatus.FAILED)

            return AgentResult(
                success=False,
                error=error_msg,
                duration=duration,
            )

    def _evaluate_script(
        self,
        script: str,
        context: EpisodeContext
    ) -> Dict[str, int]:
        """대본 평가"""

        scores = {}

        # 1. 길이 평가 (30점)
        scores["length"] = self._evaluate_length(script)

        # 2. 구조 평가 (20점)
        scores["structure"] = self._evaluate_structure(script, context)

        # 3. 문체 평가 (20점)
        scores["style"] = self._evaluate_style(script)

        # 4. 역사적 정확성 (20점)
        scores["accuracy"] = self._evaluate_accuracy(script, context)

        # 5. 스토리텔링 (10점)
        scores["storytelling"] = self._evaluate_storytelling(script, context)

        return scores

    def _evaluate_length(self, script: str) -> int:
        """길이 평가 (30점 만점)"""
        length = len(script)

        if self.min_length <= length <= self.max_length:
            return 30
        elif 11000 <= length < self.min_length or self.max_length < length <= 16000:
            return 20
        else:
            return 10

    def _evaluate_structure(self, script: str, context: EpisodeContext) -> int:
        """구조 평가 (20점 만점)"""
        score = 0

        # 기획서의 구조와 대본 비교
        if context.brief:
            structure = context.brief.get("structure", [])
            structure_count = len(structure)
            matched = 0

            for section in structure:
                section_title = section.get("part", "")
                # 대본에서 해당 섹션 키워드가 있는지 확인
                if section_title and any(keyword in script for keyword in section_title.split()):
                    matched += 1

            if structure_count > 0:
                match_ratio = matched / structure_count
                if match_ratio >= 0.8:
                    score = 20
                elif match_ratio >= 0.5:
                    score = 15
                else:
                    score = 10
            else:
                score = 15  # 기획서에 구조 없으면 기본점
        else:
            # 기획서 없으면 대본 자체 구조 평가
            # 최소 5개 단락 이상이면 구조 있다고 판단
            paragraphs = [p for p in script.split("\n\n") if len(p.strip()) > 100]
            if len(paragraphs) >= 5:
                score = 20
            elif len(paragraphs) >= 3:
                score = 15
            else:
                score = 10

        return score

    def _evaluate_style(self, script: str) -> int:
        """문체 평가 (20점 만점)"""
        score = 0

        # 대화체 종결어미 (10점)
        conversational_count = 0
        for pattern in [r"거든요", r"었어요", r"죠[\.?]", r"네요"]:
            conversational_count += len(re.findall(pattern, script))

        if conversational_count >= 20:
            score += 10
        elif conversational_count >= 10:
            score += 7
        elif conversational_count >= 5:
            score += 5
        else:
            score += 2

        # 질문 활용 (5점)
        question_count = script.count("?")
        if question_count >= 10:
            score += 5
        elif question_count >= 5:
            score += 3
        elif question_count >= 2:
            score += 2
        else:
            score += 1

        # 학술적 유보 표현 감점 (5점에서 차감)
        forbidden_count = 0
        for phrase in self.forbidden_phrases:
            forbidden_count += script.count(phrase)

        if forbidden_count == 0:
            score += 5
        elif forbidden_count <= 2:
            score += 3
        else:
            score += 1

        return score

    def _evaluate_accuracy(self, script: str, context: EpisodeContext) -> int:
        """역사적 정확성 평가 (20점 만점)"""
        score = 0

        # 연도 언급 (10점)
        year_pattern = r"(서기\s*)?\d{1,4}년"
        years = re.findall(year_pattern, script)
        if len(years) >= 10:
            score += 10
        elif len(years) >= 5:
            score += 7
        elif len(years) >= 2:
            score += 5
        else:
            score += 2

        # 숫자/구체적 사례 (10점)
        number_patterns = [
            r"\d+만\s*명",  # 인구수
            r"\d+개",  # 개수
            r"\d+세기",  # 세기
            r"\d+km",  # 거리
            r"제?\d+대",  # 왕/대통령
        ]
        number_count = 0
        for pattern in number_patterns:
            number_count += len(re.findall(pattern, script))

        if number_count >= 10:
            score += 10
        elif number_count >= 5:
            score += 7
        elif number_count >= 2:
            score += 5
        else:
            score += 2

        return score

    def _evaluate_storytelling(self, script: str, context: EpisodeContext) -> int:
        """스토리텔링 평가 (10점 만점)"""
        score = 0

        # 훅 (인트로 첫 500자) (3점)
        intro = script[:500]
        hook_indicators = ["상상해", "생각해", "어떤", "만약", "왜"]
        if any(indicator in intro for indicator in hook_indicators):
            score += 3
        elif "?" in intro:
            score += 2
        else:
            score += 1

        # 몰입도 있는 전개 (4점)
        # 대화/인용문 사용
        quote_count = script.count('"') // 2  # 쌍따옴표 쌍
        if quote_count >= 5:
            score += 4
        elif quote_count >= 2:
            score += 3
        else:
            score += 2

        # 다음 화 예고 (마지막 500자) (3점)
        outro = script[-500:]
        next_indicators = ["다음", "예고", "이어서", "계속", "다음 화"]
        if context.next_episode:
            if any(indicator in outro for indicator in next_indicators):
                score += 3
            else:
                score += 1
        else:
            # 마지막 화면 마무리 점수
            score += 3

        return score

    def _calculate_grade(self, total_score: int) -> str:
        """등급 계산"""
        if total_score >= 90:
            return "S"
        elif total_score >= 80:
            return "A"
        elif total_score >= 70:
            return "B"
        elif total_score >= 60:
            return "C"
        else:
            return "D"

    def _determine_pass(self, grade: str, strict: bool) -> bool:
        """통과 여부 결정"""
        if strict:
            return grade in ["S", "A"]
        else:
            return grade in ["S", "A", "B"]

    def _generate_feedback(
        self,
        script: str,
        scores: Dict[str, int],
        context: EpisodeContext
    ) -> Dict[str, Any]:
        """피드백 생성"""

        feedback = {
            "summary": "",
            "strengths": [],
            "improvements": [],
            "critical_issues": [],
        }

        length = len(script)

        # 길이 피드백
        if scores["length"] == 30:
            feedback["strengths"].append(f"길이 적절 ({length:,}자)")
        elif length < self.min_length:
            diff = self.min_length - length
            feedback["improvements"].append(f"대본이 {diff:,}자 부족합니다 (현재 {length:,}자)")
        else:
            diff = length - self.max_length
            feedback["improvements"].append(f"대본이 {diff:,}자 초과입니다 (현재 {length:,}자)")

        # 구조 피드백
        if scores["structure"] >= 18:
            feedback["strengths"].append("구조가 잘 잡혀 있습니다")
        elif scores["structure"] < 15:
            feedback["improvements"].append("인트로/배경/본론/마무리 구조를 명확히 해주세요")

        # 문체 피드백
        if scores["style"] >= 17:
            feedback["strengths"].append("대화체 문체가 자연스럽습니다")
        else:
            if scores["style"] < 10:
                feedback["improvements"].append("대화체 종결어미(~거든요, ~었어요)를 더 사용해주세요")

            # 금지 표현 체크
            for phrase in self.forbidden_phrases:
                if phrase in script:
                    feedback["critical_issues"].append(f"학술적 유보 표현 발견: '{phrase}'")

        # 정확성 피드백
        if scores["accuracy"] >= 17:
            feedback["strengths"].append("구체적인 숫자와 연도가 잘 활용되었습니다")
        else:
            feedback["improvements"].append("구체적인 연도, 숫자, 사례를 더 추가해주세요")

        # 스토리텔링 피드백
        if scores["storytelling"] >= 8:
            feedback["strengths"].append("스토리텔링이 흥미롭습니다")
        else:
            if "?" not in script[:500]:
                feedback["improvements"].append("인트로에 시청자를 끌어들이는 질문을 넣어주세요")

        # 요약 생성
        total = sum(scores.values())
        grade = self._calculate_grade(total)

        if grade == "S":
            feedback["summary"] = "훌륭한 대본입니다. 바로 제작 진행하세요."
        elif grade == "A":
            feedback["summary"] = "좋은 대본입니다. 사소한 부분만 다듬으면 됩니다."
        elif grade == "B":
            feedback["summary"] = "괜찮은 대본이지만, 개선 사항을 반영해주세요."
        elif grade == "C":
            feedback["summary"] = "수정이 필요합니다. 피드백을 참고하여 다시 작성해주세요."
        else:
            feedback["summary"] = "대폭 수정이 필요합니다. 구조와 문체를 다시 검토해주세요."

        return feedback


# 동기 실행 래퍼
def review_script(context: EpisodeContext, strict: bool = False) -> Dict[str, Any]:
    """
    대본 검수 (동기 버전)

    Args:
        context: 에피소드 컨텍스트 (script 필수)
        strict: 엄격 모드

    Returns:
        검수 결과
    """
    import asyncio

    agent = ReviewAgent()

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


def quick_review(script: str) -> Tuple[str, int, List[str]]:
    """
    간단 검수 (컨텍스트 없이)

    Args:
        script: 대본 텍스트

    Returns:
        (등급, 점수, 이슈 목록)
    """
    agent = ReviewAgent()

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

    result = loop.run_until_complete(agent.execute(context))

    if result.success:
        data = result.data
        issues = data["feedback"].get("critical_issues", [])
        issues.extend(data["feedback"].get("improvements", []))
        return data["grade"], data["total_score"], issues
    else:
        return "F", 0, [result.error]
