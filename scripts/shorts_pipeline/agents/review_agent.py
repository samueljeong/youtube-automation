"""
ReviewAgent - 검수 에이전트

역할:
- 대본 품질 검수
- 이미지-대본 일치성 검수
- 개선 피드백 제공
"""

import os
import json
import re
import time
from typing import Any, Dict, List, Optional

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
    return text.strip()


def safe_json_parse(text: str) -> Dict[str, Any]:
    """안전한 JSON 파싱"""
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    repaired = repair_json(text)
    return json.loads(repaired)


class ReviewAgent(BaseAgent):
    """검수 에이전트"""

    def __init__(self):
        super().__init__("ReviewAgent")
        self.model = "gpt-5.1"

        # 검수 기준
        self.script_criteria = {
            "min_length": 180,
            "max_length": 300,
            "min_scenes": 5,
            "max_scenes": 9,
            "required_hook": True,  # 첫 씬에 훅 필수
        }

        self.image_criteria = {
            "min_success_rate": 0.8,  # 80% 이상 성공 필요
        }

        self.subtitle_criteria = {
            "min_duration": 25,  # 최소 25초
            "max_duration": 45,  # 최대 45초
            "min_subtitles": 3,  # 최소 자막 개수
        }

    async def execute(self, context: TaskContext, **kwargs) -> AgentResult:
        """
        검수 실행

        Args:
            context: 작업 컨텍스트
            **kwargs:
                review_type: "script" | "subtitle" | "image" | "all"

        Returns:
            AgentResult with review feedback
        """
        self.set_status(AgentStatus.RUNNING)
        start_time = time.time()

        review_type = kwargs.get("review_type", "all")

        try:
            results = {
                "script_review": None,
                "subtitle_review": None,
                "image_review": None,
                "passed": True,
                "needs_improvement": False,
                "improvement_targets": [],
                "feedback": "",
            }
            total_cost = 0

            # 대본 검수
            if review_type in ["script", "all"] and context.script:
                script_result = await self._review_script(context)
                results["script_review"] = script_result
                total_cost += script_result.get("cost", 0)

                if not script_result.get("passed", False):
                    results["passed"] = False
                    results["needs_improvement"] = True
                    results["improvement_targets"].append("script")
                    results["feedback"] += f"\n[대본 피드백]\n{script_result.get('feedback', '')}"

            # 자막 검수
            if review_type in ["subtitle", "all"] and context.subtitle_data:
                subtitle_result = await self._review_subtitle(context)
                results["subtitle_review"] = subtitle_result
                total_cost += subtitle_result.get("cost", 0)

                if not subtitle_result.get("passed", False):
                    results["passed"] = False
                    results["needs_improvement"] = True
                    results["improvement_targets"].append("subtitle")
                    results["feedback"] += f"\n[자막 피드백]\n{subtitle_result.get('feedback', '')}"

            # 이미지 검수
            if review_type in ["image", "all"] and context.images:
                image_result = await self._review_images(context)
                results["image_review"] = image_result
                total_cost += image_result.get("cost", 0)

                if not image_result.get("passed", False):
                    results["passed"] = False
                    results["needs_improvement"] = True
                    results["improvement_targets"].append("image")
                    results["feedback"] += f"\n[이미지 피드백]\n{image_result.get('feedback', '')}"

            duration = time.time() - start_time

            # 컨텍스트에 피드백 저장
            if "script" in results["improvement_targets"]:
                context.script_feedback = results["script_review"].get("feedback", "")
            if "subtitle" in results["improvement_targets"]:
                context.subtitle_feedback = results["subtitle_review"].get("feedback", "")
            if "image" in results["improvement_targets"]:
                context.image_feedback = results["image_review"].get("feedback", "")

            context.add_log(
                self.name,
                f"review_{review_type}",
                "passed" if results["passed"] else "needs_improvement",
                f"개선 필요: {results['improvement_targets']}"
            )

            self.set_status(AgentStatus.SUCCESS)

            return AgentResult(
                success=True,
                data=results,
                feedback=results["feedback"].strip(),
                needs_improvement=results["needs_improvement"],
                improvement_targets=results["improvement_targets"],
                cost=total_cost,
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

    async def _review_script(self, context: TaskContext) -> Dict[str, Any]:
        """대본 검수"""
        self.log("대본 검수 시작")

        script_data = context.script
        full_script = script_data.get("full_script", "")
        scenes = script_data.get("scenes", [])

        # 1. 기본 규칙 검사 (LLM 없이)
        basic_issues = []

        # 길이 체크
        script_length = len(full_script)
        if script_length < self.script_criteria["min_length"]:
            basic_issues.append(f"대본이 너무 짧습니다 ({script_length}자 < {self.script_criteria['min_length']}자)")
        elif script_length > self.script_criteria["max_length"]:
            basic_issues.append(f"대본이 너무 깁니다 ({script_length}자 > {self.script_criteria['max_length']}자)")

        # 씬 수 체크
        scene_count = len(scenes)
        if scene_count < self.script_criteria["min_scenes"]:
            basic_issues.append(f"씬이 부족합니다 ({scene_count}개 < {self.script_criteria['min_scenes']}개)")

        # 기본 규칙 실패 시 바로 반환 (LLM 비용 절약)
        if basic_issues:
            return {
                "passed": False,
                "feedback": "\n".join(basic_issues),
                "score": 0,
                "cost": 0,
            }

        # 2. LLM 품질 검수
        try:
            client = get_openai_client()

            review_prompt = f"""
당신은 YouTube Shorts 대본 전문 검수자입니다.
아래 대본의 품질을 평가하고 개선점을 제시하세요.

## 대본 정보
- 인물: {context.person}
- 이슈 타입: {context.issue_type}
- 총 길이: {script_length}자
- 씬 수: {scene_count}개

## 전체 대본
{full_script}

## 씬별 구성
{self._format_scenes(scenes)}

## 검수 기준
1. **훅 (씬1)**: 첫 3초에 시청자의 관심을 끄는가? (스크롤 멈춤 유도)
2. **스토리 흐름**: 씬 간 자연스러운 연결, 반복 없이 새로운 정보 제공
3. **결말**: 구체적이고 만족스러운 마무리 (훅 반복 금지)
4. **길이**: 30-40초 TTS에 적합한 200-260자
5. **사실 기반**: 추측/비방 없이 확인된 사실만 사용

## 출력 형식 (JSON만 반환)
{{
    "passed": true/false,
    "score": 1-10,
    "strengths": ["잘된 점 1", "잘된 점 2"],
    "issues": ["문제점 1", "문제점 2"],
    "feedback": "구체적인 개선 방향 (3문장 이내)",
    "priority": "high/medium/low"
}}
"""

            response = client.responses.create(
                model=self.model,
                input=[
                    {
                        "role": "system",
                        "content": [{"type": "input_text", "text": "대본 검수 전문가. JSON으로만 응답."}]
                    },
                    {
                        "role": "user",
                        "content": [{"type": "input_text", "text": review_prompt}]
                    }
                ],
                temperature=0.3  # 검수는 일관성 중요
            )

            result_text = extract_gpt51_response(response)
            result = safe_json_parse(result_text)

            # 비용 계산
            if hasattr(response, 'usage') and response.usage:
                input_tokens = getattr(response.usage, 'input_tokens', 0)
                output_tokens = getattr(response.usage, 'output_tokens', 0)
            else:
                input_tokens = len(review_prompt) // 2
                output_tokens = len(result_text) // 2

            cost = (input_tokens * GPT51_COSTS["input"] + output_tokens * GPT51_COSTS["output"]) / 1000

            # 점수 7점 이상이면 통과
            passed = result.get("passed", False) or result.get("score", 0) >= 7

            self.log(f"대본 검수 완료: 점수 {result.get('score', 0)}/10, 통과: {passed}")

            return {
                "passed": passed,
                "score": result.get("score", 0),
                "strengths": result.get("strengths", []),
                "issues": result.get("issues", []),
                "feedback": result.get("feedback", ""),
                "priority": result.get("priority", "medium"),
                "cost": cost,
            }

        except Exception as e:
            self.log(f"LLM 검수 실패, 기본 규칙만 적용: {e}", "warning")
            return {
                "passed": True,  # LLM 실패 시 기본 통과
                "score": 6,
                "feedback": "LLM 검수 실패, 기본 규칙은 통과",
                "cost": 0,
            }

    async def _review_images(self, context: TaskContext) -> Dict[str, Any]:
        """이미지 검수 (규칙 기반)"""
        self.log("이미지 검수 시작")

        images = context.images or []
        scenes = context.script.get("scenes", []) if context.script else []

        expected_count = len(scenes)
        actual_count = len(images)

        # 성공률 체크
        success_rate = actual_count / expected_count if expected_count > 0 else 0

        issues = []
        failed_scenes = []

        # 이미지 수 체크
        if success_rate < self.image_criteria["min_success_rate"]:
            issues.append(f"이미지 생성 성공률이 낮습니다 ({actual_count}/{expected_count} = {success_rate:.0%})")

            # 실패한 씬 찾기
            existing_scenes = set()
            for img_path in images:
                # scene_001.png 형식에서 씬 번호 추출
                try:
                    import os
                    filename = os.path.basename(img_path)
                    if "scene_" in filename:
                        scene_num = int(filename.split("scene_")[1].split(".")[0])
                        existing_scenes.add(scene_num)
                except:
                    pass

            for i in range(1, expected_count + 1):
                if i not in existing_scenes:
                    failed_scenes.append(i)

        passed = len(issues) == 0

        self.log(f"이미지 검수 완료: {actual_count}/{expected_count}개, 통과: {passed}")

        return {
            "passed": passed,
            "success_rate": success_rate,
            "issues": issues,
            "failed_scenes": failed_scenes,
            "feedback": "\n".join(issues) if issues else "이미지 검수 통과",
            "cost": 0,  # 규칙 기반이므로 비용 없음
        }

    async def _review_subtitle(self, context: TaskContext) -> Dict[str, Any]:
        """자막/TTS 검수 (규칙 기반)"""
        self.log("자막 검수 시작")

        subtitle_data = context.subtitle_data or {}
        timeline = subtitle_data.get("timeline", [])
        duration_sec = subtitle_data.get("duration_sec", 0)
        audio_file = subtitle_data.get("audio_file", "")
        srt_file = subtitle_data.get("srt_file", "")

        issues = []

        # 1. 오디오 파일 존재 확인
        if not audio_file:
            issues.append("오디오 파일이 생성되지 않았습니다")
        elif not os.path.exists(audio_file):
            issues.append(f"오디오 파일을 찾을 수 없습니다: {audio_file}")

        # 2. 자막 파일 존재 확인
        if not srt_file:
            issues.append("자막 파일이 생성되지 않았습니다")
        elif not os.path.exists(srt_file):
            issues.append(f"자막 파일을 찾을 수 없습니다: {srt_file}")

        # 3. 재생 시간 체크
        if duration_sec < self.subtitle_criteria["min_duration"]:
            issues.append(f"영상이 너무 짧습니다 ({duration_sec:.1f}초 < {self.subtitle_criteria['min_duration']}초)")
        elif duration_sec > self.subtitle_criteria["max_duration"]:
            issues.append(f"영상이 너무 깁니다 ({duration_sec:.1f}초 > {self.subtitle_criteria['max_duration']}초)")

        # 4. 자막 개수 체크
        subtitle_count = len(timeline)
        if subtitle_count < self.subtitle_criteria["min_subtitles"]:
            issues.append(f"자막이 부족합니다 ({subtitle_count}개 < {self.subtitle_criteria['min_subtitles']}개)")

        passed = len(issues) == 0

        self.log(f"자막 검수 완료: {duration_sec:.1f}초, 자막 {subtitle_count}개, 통과: {passed}")

        return {
            "passed": passed,
            "duration_sec": duration_sec,
            "subtitle_count": subtitle_count,
            "issues": issues,
            "feedback": "\n".join(issues) if issues else "자막 검수 통과",
            "cost": 0,  # 규칙 기반이므로 비용 없음
        }

    def _format_scenes(self, scenes: List[Dict[str, Any]]) -> str:
        """씬 목록을 포맷팅"""
        lines = []
        for scene in scenes:
            scene_num = scene.get("scene_number", 0)
            narration = scene.get("narration", "")
            duration = scene.get("duration", "")
            lines.append(f"씬{scene_num} ({duration}): {narration}")
        return "\n".join(lines)
