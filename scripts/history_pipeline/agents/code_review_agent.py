"""
한국사 파이프라인 - Code Review Agent (코드 리뷰 에이전트)

역할:
- 기획 에이전트 감시 및 검증
- 모든 에이전트 출력물 코드 리뷰
- 커밋 전 최종 검수
- 오류 및 잠재적 문제 식별

성격:
- 철저하고 꼼꼼함
- 어떤 것도 대충 넘어가지 않음
- 문제를 발견하면 반드시 보고
- 기획 에이전트도 예외 없이 검수
"""

import time
from typing import Any, Dict, List, Optional

from .base import BaseAgent, AgentResult, AgentStatus, EpisodeContext


# 검수 체크리스트
CODE_REVIEW_CHECKLIST = """
## 코드 리뷰 체크리스트

### 1. 기획 에이전트 출력물 검수
- [ ] 에피소드 구조가 완전한가?
- [ ] 모든 필수 필드가 채워졌는가?
- [ ] 시대/에피소드 정보가 정확한가?
- [ ] 참고 자료 링크가 유효한가?

### 2. 대본 에이전트 출력물 검수
- [ ] 대본 길이가 12,000~15,000자인가?
- [ ] 문체 가이드를 따르는가?
- [ ] 역사적 사실과 일치하는가?
- [ ] 금지 표현이 없는가?

### 3. 이미지 에이전트 출력물 검수
- [ ] 프롬프트가 시대에 맞는가?
- [ ] 이미지 개수가 적절한가?
- [ ] 금지 요소가 포함되지 않았는가?

### 4. 전체 파이프라인 검수
- [ ] 에이전트 간 데이터 일관성
- [ ] 누락된 단계가 없는가?
- [ ] 에러 처리가 적절한가?
"""


class CodeReviewAgent(BaseAgent):
    """코드 리뷰 에이전트 - 모든 에이전트의 감시자"""

    def __init__(self):
        super().__init__("CodeReviewAgent")

        # 검수 설정
        self.strict_mode = True  # 항상 엄격 모드
        self.review_history = []

    async def execute(self, context: EpisodeContext, **kwargs) -> AgentResult:
        """
        전체 파이프라인 검수 실행

        Args:
            context: 에피소드 컨텍스트
            **kwargs:
                agent_outputs: 각 에이전트의 출력물
                phase: 검수 단계 (planning/script/image/final)

        Returns:
            AgentResult with review findings
        """
        self.set_status(AgentStatus.RUNNING)
        start_time = time.time()

        agent_outputs = kwargs.get("agent_outputs", {})
        phase = kwargs.get("phase", "final")

        context.add_log(
            self.name,
            f"코드 리뷰 시작 ({phase})",
            "running",
            "엄격 모드: ON"
        )

        try:
            findings = {
                "critical": [],  # 반드시 수정 필요
                "warning": [],   # 수정 권장
                "info": [],      # 참고 사항
                "passed": [],    # 통과 항목
            }

            # 단계별 검수
            if phase in ["planning", "final"]:
                planning_findings = self._review_planning(context)
                self._merge_findings(findings, planning_findings)

            if phase in ["script", "final"]:
                script_findings = self._review_script(context)
                self._merge_findings(findings, script_findings)

            if phase in ["image", "final"]:
                image_findings = self._review_image(context, agent_outputs)
                self._merge_findings(findings, image_findings)

            # 에이전트 간 일관성 검수
            if phase == "final":
                consistency_findings = self._review_consistency(context, agent_outputs)
                self._merge_findings(findings, consistency_findings)

            # 최종 판정
            approval_status = self._determine_approval(findings)

            duration = time.time() - start_time

            # 리뷰 히스토리 저장
            self.review_history.append({
                "phase": phase,
                "approval": approval_status,
                "findings_count": {
                    "critical": len(findings["critical"]),
                    "warning": len(findings["warning"]),
                },
                "timestamp": time.time(),
            })

            status = "success" if approval_status == "approved" else "warning"
            context.add_log(
                self.name,
                f"코드 리뷰 완료: {approval_status}",
                status,
                f"Critical: {len(findings['critical'])}, Warning: {len(findings['warning'])}"
            )

            if approval_status == "approved":
                self.set_status(AgentStatus.SUCCESS)
            else:
                self.set_status(AgentStatus.WAITING_REVIEW)

            return AgentResult(
                success=True,
                data={
                    "approval_status": approval_status,
                    "findings": findings,
                    "phase": phase,
                    "can_commit": approval_status == "approved",
                    "review_checklist": CODE_REVIEW_CHECKLIST,
                },
                duration=duration,
            )

        except Exception as e:
            duration = time.time() - start_time
            error_msg = str(e)

            context.add_log(self.name, "코드 리뷰 실패", "error", error_msg)
            self.set_status(AgentStatus.FAILED)

            return AgentResult(
                success=False,
                error=error_msg,
                duration=duration,
            )

    def _review_planning(self, context: EpisodeContext) -> Dict[str, List[str]]:
        """기획 단계 검수"""
        findings = {"critical": [], "warning": [], "info": [], "passed": []}

        # 필수 정보 확인
        if not context.episode_id:
            findings["critical"].append("에피소드 ID가 없습니다")
        else:
            findings["passed"].append("에피소드 ID 확인")

        if not context.era_name:
            findings["critical"].append("시대 정보가 없습니다")
        else:
            findings["passed"].append("시대 정보 확인")

        if not context.title:
            findings["critical"].append("제목이 없습니다")
        else:
            findings["passed"].append("제목 확인")

        # 기획서 확인
        if context.brief:
            brief = context.brief

            # 구조 확인
            if "structure" not in brief or not brief["structure"]:
                findings["warning"].append("기획서에 구조(structure)가 없습니다")
            else:
                findings["passed"].append("기획서 구조 확인")

            # 훅 확인
            if "hook" not in brief or not brief["hook"]:
                findings["warning"].append("기획서에 훅(hook)이 없습니다")
            else:
                findings["passed"].append("기획서 훅 확인")

            # 핵심 포인트 확인
            if "key_points" not in brief or not brief["key_points"]:
                findings["warning"].append("기획서에 핵심 포인트가 없습니다")
            else:
                findings["passed"].append("기획서 핵심 포인트 확인")
        else:
            findings["warning"].append("기획서가 아직 생성되지 않았습니다")

        # 참고 자료 확인
        if not context.reference_links:
            findings["info"].append("참고 자료 링크가 없습니다")
        else:
            findings["passed"].append(f"참고 자료 {len(context.reference_links)}개 확인")

        return findings

    def _review_script(self, context: EpisodeContext) -> Dict[str, List[str]]:
        """대본 검수"""
        findings = {"critical": [], "warning": [], "info": [], "passed": []}

        if not context.script:
            findings["info"].append("대본이 아직 작성되지 않았습니다")
            return findings

        script = context.script
        length = len(script)

        # 길이 검수
        if length < 11000:
            findings["critical"].append(f"대본이 너무 짧습니다 ({length:,}자 < 11,000자)")
        elif length < 12000:
            findings["warning"].append(f"대본이 약간 짧습니다 ({length:,}자 < 12,000자)")
        elif length > 16000:
            findings["critical"].append(f"대본이 너무 깁니다 ({length:,}자 > 16,000자)")
        elif length > 15000:
            findings["warning"].append(f"대본이 약간 깁니다 ({length:,}자 > 15,000자)")
        else:
            findings["passed"].append(f"대본 길이 적절 ({length:,}자)")

        # 금지 표현 검수
        forbidden_phrases = [
            "단정하기 어렵습니다",
            "해석이 갈립니다",
            "알 수 없습니다",
        ]
        for phrase in forbidden_phrases:
            if phrase in script:
                findings["critical"].append(f"금지 표현 발견: '{phrase}'")

        # 문체 검수
        conversational_endings = ["거든요", "었어요", "죠"]
        ending_count = sum(script.count(e) for e in conversational_endings)

        if ending_count < 10:
            findings["warning"].append(f"대화체 종결어미 부족 ({ending_count}개)")
        else:
            findings["passed"].append(f"대화체 문체 사용 ({ending_count}개)")

        # 질문 사용 검수
        question_count = script.count("?")
        if question_count < 5:
            findings["warning"].append(f"질문이 부족합니다 ({question_count}개)")
        else:
            findings["passed"].append(f"질문 활용 ({question_count}개)")

        return findings

    def _review_image(
        self,
        context: EpisodeContext,
        agent_outputs: Dict[str, Any]
    ) -> Dict[str, List[str]]:
        """이미지 프롬프트 검수"""
        findings = {"critical": [], "warning": [], "info": [], "passed": []}

        if not context.image_prompts:
            findings["info"].append("이미지 프롬프트가 아직 생성되지 않았습니다")
            return findings

        prompts = context.image_prompts
        prompt_count = len(prompts)

        # 이미지 개수 검수
        if prompt_count < 5:
            findings["warning"].append(f"이미지가 너무 적습니다 ({prompt_count}개 < 5개)")
        elif prompt_count > 12:
            findings["warning"].append(f"이미지가 너무 많습니다 ({prompt_count}개 > 12개)")
        else:
            findings["passed"].append(f"이미지 개수 적절 ({prompt_count}개)")

        # 프롬프트 내용 검수
        forbidden_in_prompt = ["text", "words", "writing", "letters"]
        for i, prompt in enumerate(prompts):
            prompt_text = prompt.get("prompt", "").lower()
            for forbidden in forbidden_in_prompt:
                if forbidden in prompt_text:
                    findings["warning"].append(
                        f"이미지 {i+1}: 텍스트 요소 포함 ('{forbidden}')"
                    )
                    break
            else:
                # 모든 검사 통과
                if i < 3:  # 처음 3개만 로그
                    findings["passed"].append(f"이미지 {i+1} 프롬프트 확인")

        return findings

    def _review_consistency(
        self,
        context: EpisodeContext,
        agent_outputs: Dict[str, Any]
    ) -> Dict[str, List[str]]:
        """에이전트 간 일관성 검수"""
        findings = {"critical": [], "warning": [], "info": [], "passed": []}

        # 시대 정보 일관성
        if context.era_name and context.brief:
            brief_era = context.brief.get("era_name", "")
            if brief_era and brief_era != context.era_name:
                findings["critical"].append(
                    f"시대 정보 불일치: context({context.era_name}) vs brief({brief_era})"
                )
            else:
                findings["passed"].append("시대 정보 일관성 확인")

        # 에피소드 번호 일관성
        if context.episode_number and context.brief:
            brief_ep = context.brief.get("episode_number", 0)
            if brief_ep and brief_ep != context.episode_number:
                findings["warning"].append(
                    f"에피소드 번호 불일치: context({context.episode_number}) vs brief({brief_ep})"
                )
            else:
                findings["passed"].append("에피소드 번호 일관성 확인")

        # 로그 확인 (에러 있는지)
        error_logs = [log for log in context.logs if log.get("result") == "error"]
        if error_logs:
            for log in error_logs:
                findings["critical"].append(
                    f"에러 로그 발견 [{log.get('agent')}]: {log.get('details')}"
                )
        else:
            findings["passed"].append("에러 로그 없음")

        return findings

    def _merge_findings(
        self,
        target: Dict[str, List[str]],
        source: Dict[str, List[str]]
    ):
        """findings 병합"""
        for key in ["critical", "warning", "info", "passed"]:
            target[key].extend(source.get(key, []))

    def _determine_approval(self, findings: Dict[str, List[str]]) -> str:
        """최종 승인 상태 결정"""
        if findings["critical"]:
            return "rejected"  # 크리티컬 이슈 있으면 거부
        elif findings["warning"]:
            return "needs_revision"  # 경고 있으면 수정 필요
        else:
            return "approved"  # 모두 통과

    def review_before_commit(self, context: EpisodeContext) -> Dict[str, Any]:
        """
        커밋 전 최종 검수 (동기 버전)

        Returns:
            {
                "can_commit": bool,
                "issues": List[str],
                "summary": str
            }
        """
        import asyncio

        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        result = loop.run_until_complete(
            self.execute(context, phase="final")
        )

        if result.success:
            data = result.data
            issues = data["findings"]["critical"] + data["findings"]["warning"]

            return {
                "can_commit": data["can_commit"],
                "issues": issues,
                "summary": f"승인 상태: {data['approval_status']}, "
                          f"Critical: {len(data['findings']['critical'])}, "
                          f"Warning: {len(data['findings']['warning'])}"
            }
        else:
            return {
                "can_commit": False,
                "issues": [result.error],
                "summary": f"검수 실패: {result.error}"
            }


# 동기 실행 래퍼
def review_pipeline(context: EpisodeContext, phase: str = "final") -> Dict[str, Any]:
    """
    파이프라인 검수 (동기 버전)

    Args:
        context: 에피소드 컨텍스트
        phase: 검수 단계

    Returns:
        검수 결과
    """
    import asyncio

    agent = CodeReviewAgent()

    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    result = loop.run_until_complete(
        agent.execute(context, phase=phase)
    )

    if result.success:
        return result.data
    else:
        raise Exception(result.error)


def can_commit(context: EpisodeContext) -> bool:
    """커밋 가능 여부 확인"""
    agent = CodeReviewAgent()
    review = agent.review_before_commit(context)
    return review["can_commit"]
