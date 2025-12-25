"""
ScriptAgent - 기획/대본 생성 에이전트

역할:
- 쇼츠 대본 생성
- 검수 피드백 반영하여 개선
"""

import os
import sys
import time
import json
import re
from typing import Any, Dict, Optional

try:
    from .base import BaseAgent, AgentResult, AgentStatus, TaskContext
except ImportError:
    from base import BaseAgent, AgentResult, AgentStatus, TaskContext


# GPT-5.1 비용 (USD per 1K tokens)
GPT51_COSTS = {
    "input": 0.01,
    "output": 0.03,
}


def get_openai_client():
    """OpenAI 클라이언트 반환"""
    from openai import OpenAI
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY 환경변수가 설정되지 않았습니다")
    return OpenAI(api_key=api_key)


def extract_gpt51_response(response) -> str:
    """GPT-5.1 Responses API 응답에서 텍스트 추출"""
    if getattr(response, "output_text", None):
        return response.output_text.strip()

    text_chunks = []
    for item in getattr(response, "output", []) or []:
        for content in getattr(item, "content", []) or []:
            if getattr(content, "type", "") == "text":
                text_chunks.append(getattr(content, "text", ""))

    return "\n".join(text_chunks).strip()


def repair_json(text: str) -> str:
    """불완전한 JSON 수정 시도"""
    if "```" in text:
        match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', text)
        if match:
            text = match.group(1)
        else:
            text = re.sub(r'^```(?:json)?\s*', '', text)
            text = re.sub(r'\s*```$', '', text)

    text = re.sub(r',\s*([}\]])', r'\1', text)
    text = re.sub(r'"\s*\n\s*"(?=[a-zA-Z_가-힣])', '",\n"', text)
    text = re.sub(r'}\s*\n\s*{', '},\n{', text)
    text = re.sub(r']\s*\n\s*\[', '],\n[', text)

    return text.strip()


def safe_json_parse(text: str) -> Dict[str, Any]:
    """안전한 JSON 파싱"""
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    repaired = repair_json(text)
    return json.loads(repaired)


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
당신은 YouTube Shorts 대본 전문 작가입니다.
아래 정보를 바탕으로 30-40초 쇼츠 대본을 작성하세요.

## 정보
- 인물: {context.person}
- 주제: {context.topic}
- 이슈 타입: {context.issue_type}
- 카테고리: {context.category}

## 대본 규칙
1. 총 200-260자 (30-40초 TTS 기준)
2. 5개 씬으로 구성
3. 씬1: 킬러 훅 (스크롤 멈추게)
4. 씬2-4: 핵심 내용
5. 씬5: 결론 (훅 반복 금지)

## 출력 형식 (JSON만 반환)
{{
    "title": "쇼츠 제목 (30자 이내)",
    "scenes": [
        {{"scene_number": 1, "narration": "킬러 훅 문장", "image_prompt": "영어 이미지 프롬프트"}},
        {{"scene_number": 2, "narration": "...", "image_prompt": "..."}},
        {{"scene_number": 3, "narration": "...", "image_prompt": "..."}},
        {{"scene_number": 4, "narration": "...", "image_prompt": "..."}},
        {{"scene_number": 5, "narration": "결론", "image_prompt": "..."}}
    ],
    "hashtags": ["#태그1", "#태그2"]
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
