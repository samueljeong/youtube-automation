"""
ScriptAgent - 기획/대본 생성 에이전트

역할:
- 쇼츠 대본 생성
- 검수 피드백 반영하여 개선
"""

import time
from typing import Any, Dict, Optional

try:
    from .base import BaseAgent, AgentResult, AgentStatus, TaskContext
    from .utils import (
        GPT51_COSTS,
        get_openai_client,
        extract_gpt51_response,
        safe_json_parse,
    )
except ImportError:
    from base import BaseAgent, AgentResult, AgentStatus, TaskContext
    from utils import (
        GPT51_COSTS,
        get_openai_client,
        extract_gpt51_response,
        safe_json_parse,
    )


class ScriptAgent(BaseAgent):
    """기획/대본 생성 에이전트"""

    def __init__(self):
        super().__init__("ScriptAgent")
        self.model = "gpt-5.1"

    async def execute(self, context: TaskContext, **kwargs) -> AgentResult:
        """
        대본 생성 실행

        Args:
            context: 작업 컨텍스트 (topic, category, issue_type, person 등)
            **kwargs:
                feedback: 검수 에이전트의 피드백 (개선 시)

        Returns:
            AgentResult with script data
        """
        self.set_status(AgentStatus.RUNNING)
        start_time = time.time()

        feedback = kwargs.get("feedback")
        is_improvement = feedback is not None

        try:
            if is_improvement:
                # 피드백 반영하여 개선
                result = await self._improve_script(context, feedback)
            else:
                # 새로 생성
                result = await self._generate_script(context)

            duration = time.time() - start_time

            if result.get("ok"):
                self.set_status(AgentStatus.SUCCESS)
                context.script = result
                context.script_attempts += 1
                context.add_log(
                    self.name,
                    "improve" if is_improvement else "generate",
                    "success",
                    f"{result.get('total_chars', 0)}자, ${result.get('cost', 0):.4f}"
                )

                return AgentResult(
                    success=True,
                    data=result,
                    cost=result.get("cost", 0),
                    duration=duration,
                )
            else:
                self.set_status(AgentStatus.FAILED)
                error_msg = result.get("error", "Unknown error")
                context.add_log(self.name, "generate", "failed", error_msg)

                return AgentResult(
                    success=False,
                    error=error_msg,
                    duration=duration,
                )

        except Exception as e:
            self.set_status(AgentStatus.FAILED)
            context.add_log(self.name, "execute", "exception", str(e))
            return AgentResult(
                success=False,
                error=str(e),
                duration=time.time() - start_time,
            )

    async def _generate_script(self, context: TaskContext) -> Dict[str, Any]:
        """새로운 대본 생성"""
        self.log(f"대본 생성 시작: {context.person} - {context.issue_type}")

        try:
            client = get_openai_client()

            prompt = f"""
당신은 **리텐션 85% 쇼츠 전문가**입니다.

## 🎯 목표 우선순위
1. **리텐션 85%+** - 끝까지 보게 (가장 중요!)
2. **댓글 유도** - "나도 한마디"
3. **반복 시청** - 다시 보게

## 📊 알고리즘 핵심
- 70% 스와이프 → 노출 중단
- 85%+ 시청률 → 추천 시작

## 정보
- 인물: {context.person}
- 주제: {context.topic}
- 이슈 타입: {context.issue_type}
- 카테고리: {context.category}

## 🔒 리텐션 이탈 방지 문구 (씬2, 씬3 필수!)
- "근데 이게 다가 아니야."
- "진짜는 지금부터야."

## 🔥 댓글 유도 기법 (씬4 필수!)
- **편가르기**: "{context.person} 잘못 vs 상대방 예민. 어느 쪽?"
- **경험 공유**: "이런 경험 있는 사람?"

## ⚡ 문장 규칙
- **한 문장 = 최대 12자**
- **씬당 4-6문장**, **총 300-400자**
- ❌ 금지: "여러분", "이게 사실이라면"

## 🎯 씬 구성 (5개, 300-400자)
- 씬1 (훅): "{context.person}. 갑질. 터졌다. 이번엔 진짜다."
- 씬2 (팩트 + 이탈방지): "폭언. 부당대우. 근데 이게 다가 아니야."
- 씬3 (클라이맥스): "진짜는 이거야. 불법 시술. 선 넘었다."
- 씬4 (댓글유도): "{context.person} 잘못 vs 상대방 예민. 어느 쪽이야? 댓글로."
- 씬5 (여운): "복귀? 힘들 듯. 근데 반전 있을 수도. 지켜보자."

## 출력 형식 (JSON만 반환)
{{
    "title": "쇼츠 제목 (20자)",
    "total_chars": 350,
    "retention_hooks": {{
        "scene2": "근데 이게 다가 아니야",
        "scene3": "진짜는 이거야"
    }},
    "comment_bait": {{
        "scene": 4,
        "type": "versus",
        "text": "{context.person} 잘못 vs 상대방 예민. 어느 쪽?"
    }},
    "scenes": [
        {{"scene_number": 1, "narration": "{context.person}. 갑질. 터졌다. 이번엔 진짜다. 큰일났다.", "image_prompt": "영어 프롬프트"}},
        {{"scene_number": 2, "narration": "매니저에게 폭언. 부당대우. 제보 폭주. 근데 이게 다가 아니야. 더 있어.", "image_prompt": "..."}},
        {{"scene_number": 3, "narration": "진짜는 이거야. 불법 시술. 주사 놔줬대. 면허도 없이. 선 넘었다.", "image_prompt": "..."}},
        {{"scene_number": 4, "narration": "{context.person} 잘못이다. vs 매니저 예민하다. 어느 쪽이야? 댓글로. 비슷한 상사 있었어?", "image_prompt": "..."}},
        {{"scene_number": 5, "narration": "복귀? 힘들 듯. 근데 반전 있을 수도. 3개월 뒤 어떨까? 지켜보자.", "image_prompt": "..."}}
    ],
    "hashtags": ["#{context.person}", "#이슈"]
}}
"""

            response = client.responses.create(
                model=self.model,
                input=[
                    {"role": "system", "content": [{"type": "input_text", "text": "쇼츠 대본 작가. JSON으로만 응답."}]},
                    {"role": "user", "content": [{"type": "input_text", "text": prompt}]}
                ],
                temperature=0.7
            )

            result_text = extract_gpt51_response(response)
            result = safe_json_parse(result_text)

            # 전체 대본 조합
            full_script = "\n".join([
                scene["narration"] for scene in result.get("scenes", [])
            ])

            # 비용 계산
            if hasattr(response, 'usage') and response.usage:
                input_tokens = getattr(response.usage, 'input_tokens', 0)
                output_tokens = getattr(response.usage, 'output_tokens', 0)
            else:
                input_tokens = len(prompt) // 2
                output_tokens = len(result_text) // 2

            cost = (input_tokens * GPT51_COSTS["input"] + output_tokens * GPT51_COSTS["output"]) / 1000

            self.log(f"대본 생성 완료: {len(full_script)}자, ${cost:.4f}")

            return {
                "ok": True,
                "title": result.get("title", f"{context.person} 이슈"),
                "scenes": result.get("scenes", []),
                "full_script": full_script,
                "total_chars": len(full_script),
                "hashtags": result.get("hashtags", []),
                "cost": round(cost, 4),
            }

        except Exception as e:
            self.log(f"대본 생성 실패: {e}", "error")
            return {"ok": False, "error": str(e)}

    async def _improve_script(self, context: TaskContext, feedback: str) -> Dict[str, Any]:
        """피드백 반영하여 대본 개선"""
        self.log(f"대본 개선 시작 (시도 #{context.script_attempts + 1})")
        self.log(f"피드백: {feedback[:100]}...")

        if not context.script:
            # 기존 대본이 없으면 새로 생성
            return await self._generate_script(context)

        try:
            client = get_openai_client()

            # 기존 대본 정보
            current_script = context.script.get("full_script", "")
            current_scenes = context.script.get("scenes", [])

            improvement_prompt = f"""
당신은 쇼츠 대본 전문 에디터입니다.
아래 대본을 검수 피드백에 따라 개선하세요.

## 현재 대본
{current_script}

## 검수 피드백
{feedback}

## 개선 규칙
1. 피드백에서 지적한 문제만 수정
2. 잘 된 부분은 유지
3. 전체 길이는 200-260자 유지
4. 5개 씬 구조 유지

## 출력 형식 (JSON만 반환)
{{
    "title": "개선된 제목",
    "scenes": [
        {{"scene_number": 1, "narration": "...", "image_prompt": "...", "text_overlay": "..."}},
        ...
    ],
    "improvement_summary": "개선한 내용 요약"
}}
"""

            response = client.responses.create(
                model=self.model,
                input=[
                    {
                        "role": "system",
                        "content": [{"type": "input_text", "text": "쇼츠 대본 에디터. JSON으로만 응답."}]
                    },
                    {
                        "role": "user",
                        "content": [{"type": "input_text", "text": improvement_prompt}]
                    }
                ],
                temperature=0.7
            )

            result_text = extract_gpt51_response(response)
            result = safe_json_parse(result_text)

            # 전체 대본 조합
            full_script = "\n".join([
                scene["narration"] for scene in result.get("scenes", [])
            ])

            # 비용 계산
            if hasattr(response, 'usage') and response.usage:
                input_tokens = getattr(response.usage, 'input_tokens', 0)
                output_tokens = getattr(response.usage, 'output_tokens', 0)
            else:
                input_tokens = len(improvement_prompt) // 2
                output_tokens = len(result_text) // 2

            cost = (input_tokens * GPT51_COSTS["input"] + output_tokens * GPT51_COSTS["output"]) / 1000

            self.log(f"대본 개선 완료: {len(full_script)}자")

            # 기존 데이터 유지하면서 업데이트
            improved_result = context.script.copy()
            improved_result.update({
                "ok": True,
                "title": result.get("title", improved_result.get("title")),
                "scenes": result.get("scenes", []),
                "full_script": full_script,
                "total_chars": len(full_script),
                "cost": improved_result.get("cost", 0) + cost,
                "improvement_summary": result.get("improvement_summary", ""),
            })

            return improved_result

        except Exception as e:
            self.log(f"대본 개선 실패: {e}", "error")
            return {"ok": False, "error": str(e)}

    def _get_silhouette_desc(self, person: str) -> str:
        """인물에 맞는 실루엣 설명 생성"""
        # 기본 실루엣 설명
        return f"person with distinctive silhouette, professional pose, {person} style"
