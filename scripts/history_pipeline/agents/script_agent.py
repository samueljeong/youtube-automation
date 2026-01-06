"""
한국사 파이프라인 - Script Agent (대본 에이전트)

## 성격 및 역할
세계에서 가장 유명한 작가.
사람들이 좋아할 만한 톤과 어체로 대본을 작성.
초반에 웹서칭으로 방향을 정립.

## 철학
- "독자(시청자)가 왕이다" - 어려운 역사도 쉽고 재미있게
- 스토리텔링으로 몰입감 극대화
- 학술적 정확성과 대중적 재미 모두 잡기

## 책임
- 12,000~15,000자 분량의 역사 다큐멘터리 대본 작성
- 기획서 기반 구조화된 대본 생성
- 대화체 문체로 친근하게 서술 (~거든요, ~었어요)
- YouTube 메타데이터 생성 (제목, 설명, 태그)
- 검수 피드백 반영하여 개선

## 작업 프로세스
1. 웹서칭으로 주제 관련 최신 자료 수집
2. 기획서 구조에 맞춰 대본 초안 작성
3. 스토리텔링 기법 적용 (훅, 질문, 가정법)
4. 검수 에이전트 피드백 반영하여 수정
"""

import time
from typing import Any, Dict, List, Optional

from .base import BaseAgent, AgentResult, AgentStatus, EpisodeContext


# 대본 스타일 가이드
SCRIPT_STYLE_GUIDE = """
## 문체 가이드 (한국사 다큐멘터리)

### 기본 원칙
- 확신 있는 스토리텔러처럼 서술
- 학술적 유보 표현 최소화 ("~로 보기도 합니다" 전체에서 1-2회만)
- 대화체 종결 (~거든요, ~었어요, ~죠)

### 권장 표현
- "서기 685년 겨울이었어요."
- "근데 문제가 있었거든요."
- "왜 그랬을까요?"
- "이게 핵심이었어요."

### 금지 표현
- "~라는 견해도 있습니다" (남발 금지)
- "단정하기 어렵습니다"
- "해석이 갈립니다"

### 구조
- 인트로: 훅 + 주제 소개 (~1,500자)
- 배경: 역사적 맥락 (~2,500자)
- 본론1: 핵심 내용 전반 (~4,000자)
- 본론2: 핵심 내용 후반 (~4,500자)
- 마무리: 정리 + 다음화 예고 (~2,500자)

### 스토리텔링 기법
- 구체적인 시점/상황으로 시작
- 인물의 시선에서 상황 묘사
- 가정법으로 몰입 유도 ("~했을까요?")
- 중간중간 시청자에게 질문
- 숫자와 구체적 사례 활용
"""


class ScriptAgent(BaseAgent):
    """대본 에이전트"""

    def __init__(self):
        super().__init__("ScriptAgent")

        # 대본 설정
        self.target_length = 13500  # 목표 글자수
        self.min_length = 12000
        self.max_length = 15000

    async def execute(self, context: EpisodeContext, **kwargs) -> AgentResult:
        """
        대본 생성 실행

        Args:
            context: 에피소드 컨텍스트 (brief 필수)
            **kwargs:
                feedback: 검수 피드백 (개선 시)

        Returns:
            AgentResult with script data
        """
        self.set_status(AgentStatus.RUNNING)
        start_time = time.time()

        feedback = kwargs.get("feedback")
        is_improvement = feedback is not None

        context.script_attempts += 1
        context.add_log(
            self.name,
            "대본 작성 시작" if not is_improvement else "대본 개선",
            "running",
            f"시도 {context.script_attempts}/{context.max_attempts}"
        )

        try:
            # 기획서 확인
            if not context.brief:
                raise ValueError("기획서(brief)가 없습니다. PlannerAgent를 먼저 실행하세요.")

            # 대본 작성 가이드 생성
            guide = self._generate_script_guide(context, feedback)

            # 메타데이터 템플릿 생성
            metadata = self._generate_metadata_template(context)

            duration = time.time() - start_time

            context.add_log(
                self.name,
                "대본 가이드 생성 완료",
                "success",
                f"{duration:.1f}초"
            )
            self.set_status(AgentStatus.WAITING_REVIEW)

            return AgentResult(
                success=True,
                data={
                    "guide": guide,
                    "metadata_template": metadata,
                    "style_guide": SCRIPT_STYLE_GUIDE,
                },
                duration=duration,
            )

        except Exception as e:
            duration = time.time() - start_time
            error_msg = str(e)

            context.add_log(self.name, "대본 생성 실패", "error", error_msg)
            self.set_status(AgentStatus.FAILED)

            return AgentResult(
                success=False,
                error=error_msg,
                duration=duration,
            )

    def _generate_script_guide(
        self,
        context: EpisodeContext,
        feedback: Optional[str] = None
    ) -> Dict[str, Any]:
        """대본 작성 가이드 생성"""

        brief = context.brief

        guide = {
            "episode_info": {
                "episode_id": context.episode_id,
                "episode_number": context.episode_number,
                "era": context.era_name,
                "title": context.title,
                "topic": context.topic,
            },

            "length_requirements": {
                "target": self.target_length,
                "min": self.min_length,
                "max": self.max_length,
                "estimated_duration": f"{self.target_length / 910:.0f}분",  # 910자/분
            },

            "structure": brief.get("structure", []),
            "hook": brief.get("hook", ""),
            "key_points": brief.get("key_points", []),
            "ending_hook": brief.get("ending_hook", ""),

            "reference_materials": {
                "keywords": context.keywords,
                "reference_links": context.reference_links,
                "collected_materials": context.collected_materials,
            },

            "episode_connections": {
                "prev_episode": context.prev_episode,
                "next_episode": context.next_episode,
            },

            "style_notes": [
                "확신 있는 스토리텔러처럼 서술",
                "대화체 종결 (~거든요, ~었어요)",
                "구체적인 숫자와 사례 활용",
                "가정법으로 몰입 유도",
                "학술적 유보 표현 최소화",
            ],

            "feedback_to_apply": feedback,
        }

        return guide

    def _generate_metadata_template(self, context: EpisodeContext) -> Dict[str, Any]:
        """YouTube 메타데이터 템플릿 생성"""

        # 제목 템플릿
        title_templates = [
            f"한국사 시리즈 {context.episode_number}화 | {context.title}",
            f"[한국사] {context.era_name} | {context.title}",
            f"{context.title} - {context.era_name} {context.era_episode}화",
        ]

        # 설명 템플릿
        description_template = f"""
{context.title}

{context.era_name} 시대의 이야기입니다.
{context.topic}에 대해 자세히 알아봅니다.

#한국사 #{context.era_name} #{context.title.replace(' ', '')}

📚 참고 자료:
{chr(10).join(['- ' + link for link in context.reference_links[:3]])}

⏰ 타임스탬프
00:00 인트로
(챕터별 타임스탬프 추가 필요)

🔔 구독과 좋아요는 큰 힘이 됩니다!
"""

        # 태그 생성
        tags = [
            "한국사", "역사", context.era_name,
            context.title.replace(" ", ""),
        ]
        tags.extend(context.keywords[:10])

        # 썸네일 문구 제안
        thumbnail_suggestions = [
            context.title.split(",")[0] if "," in context.title else context.title[:10],
            context.topic[:15] if context.topic else "",
            f"{context.era_name} {context.era_episode}화",
        ]

        return {
            "title_options": title_templates,
            "description_template": description_template.strip(),
            "tags": tags,
            "thumbnail_text_suggestions": thumbnail_suggestions,
            "category": "Education",
            "language": "ko",
        }

    def validate_script(self, script: str) -> Dict[str, Any]:
        """대본 유효성 검사"""

        length = len(script)
        issues = []
        warnings = []

        # 길이 검사
        if length < self.min_length:
            issues.append(f"대본이 너무 짧습니다 ({length:,}자 < {self.min_length:,}자)")
        elif length > self.max_length:
            warnings.append(f"대본이 약간 깁니다 ({length:,}자 > {self.max_length:,}자)")

        # 금지 표현 검사
        forbidden_phrases = [
            "단정하기 어렵습니다",
            "해석이 갈립니다",
            "알 수 없습니다",
        ]
        for phrase in forbidden_phrases:
            if phrase in script:
                warnings.append(f"학술적 유보 표현 발견: '{phrase}'")

        # 구조 검사 (대략적)
        if "거든요" not in script and "었어요" not in script:
            warnings.append("대화체 종결어미가 부족합니다")

        if "?" not in script:
            warnings.append("시청자에게 던지는 질문이 없습니다")

        return {
            "valid": len(issues) == 0,
            "length": length,
            "issues": issues,
            "warnings": warnings,
            "score": self._calculate_score(script, issues, warnings),
        }

    def _calculate_score(
        self,
        script: str,
        issues: List[str],
        warnings: List[str]
    ) -> int:
        """대본 점수 계산 (100점 만점)"""

        score = 100

        # 이슈당 -20점
        score -= len(issues) * 20

        # 경고당 -5점
        score -= len(warnings) * 5

        # 길이 보너스/감점
        length = len(script)
        if self.min_length <= length <= self.max_length:
            # 목표 길이에 가까울수록 보너스
            diff = abs(length - self.target_length)
            if diff < 500:
                score += 5
        else:
            score -= 10

        return max(0, min(100, score))


# 동기 실행 래퍼
def generate_script_guide(context: EpisodeContext, feedback: str = None) -> Dict[str, Any]:
    """
    대본 작성 가이드 생성 (동기 버전)

    Args:
        context: 에피소드 컨텍스트
        feedback: 검수 피드백

    Returns:
        대본 작성 가이드
    """
    import asyncio

    agent = ScriptAgent()

    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    result = loop.run_until_complete(
        agent.execute(context, feedback=feedback)
    )

    if result.success:
        return result.data
    else:
        raise Exception(result.error)


def validate_script(script: str) -> Dict[str, Any]:
    """대본 유효성 검사 (동기 버전)"""
    agent = ScriptAgent()
    return agent.validate_script(script)
