"""
ReviewAgent - 검수 에이전트

역할:
- 대본 품질 검수
- 이미지-대본 일치성 검수
- 개선 피드백 제공
"""

import os
import time
from typing import Any, Dict, List, Optional

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


class ReviewAgent(BaseAgent):
    """검수 에이전트"""

    # ★ person 검증용 제외 목록 (일반 명사, 호칭 등)
    INVALID_PERSON_NAMES = {
        # 가족/관계 호칭
        "엄마", "아빠", "아버지", "어머니", "아들", "딸", "남편", "아내",
        "언니", "오빠", "누나", "형", "동생", "할머니", "할아버지",
        "외계인", "슈퍼맘", "워킹맘", "육아",
        # 직함/역할
        "대통령", "네티즌", "시청자", "팬들", "관계자", "매니저", "기자",
        # 일반 명사
        "연예인", "아이돌", "배우", "가수", "코미디언", "개그맨",
        "선수", "감독", "코치", "심판",
        # 추상 명사
        "논란", "사건", "이슈", "문제", "상황", "결과", "영향",
    }

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
            "max_chars_per_line": 18,  # 자막 한 줄 최대 글자 수 (빠른 가독성)
            "max_line_duration": 2.5,  # 한 줄 자막 최대 노출 시간 (초)
            "min_line_duration": 0.8,  # 한 줄 자막 최소 노출 시간 (초)
        }

        # 상단 타이틀 스타일 기준
        self.title_criteria = {
            "required": True,  # 상단 타이틀 필수
            "max_chars": 25,  # 타이틀 최대 글자 수
            "position": "top",  # 상단 위치
            "style_required": ["bold", "shadow"],  # 필수 스타일
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
                "person_review": None,  # ★ person 검증 추가
                "script_review": None,
                "subtitle_review": None,
                "image_review": None,
                "passed": True,
                "needs_improvement": False,
                "improvement_targets": [],
                "feedback": "",
            }
            total_cost = 0

            # ★ person 검증 (가장 먼저 수행 - 기본 품질 보장)
            person_result = self._validate_person(context)
            results["person_review"] = person_result
            if not person_result.get("valid", False):
                results["passed"] = False
                results["needs_improvement"] = True
                results["improvement_targets"].append("person")
                results["feedback"] += f"\n[인물명 오류]\n{person_result.get('feedback', '')}"
                # person이 잘못되면 나머지 검수 의미 없음 - 바로 반환
                self.set_status(AgentStatus.SUCCESS)
                return AgentResult(
                    success=True,
                    data=results,
                    feedback=results["feedback"].strip(),
                    needs_improvement=True,
                    improvement_targets=["person"],
                    cost=0,
                    duration=time.time() - start_time,
                )

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
        """자막/TTS 검수 (규칙 기반 + 라인 분할 검사)"""
        self.log("자막 검수 시작")

        subtitle_data = context.subtitle_data or {}
        timeline = subtitle_data.get("timeline", [])
        duration_sec = subtitle_data.get("duration_sec", 0)
        audio_file = subtitle_data.get("audio_file", "")
        srt_file = subtitle_data.get("srt_file", "")
        title_data = subtitle_data.get("title", {})  # 상단 타이틀 정보

        issues = []
        warnings = []  # 경고 (통과는 가능하지만 개선 권장)

        # ===== 1. 기본 파일 존재 확인 =====
        if not audio_file:
            issues.append("오디오 파일이 생성되지 않았습니다")
        elif not os.path.exists(audio_file):
            issues.append(f"오디오 파일을 찾을 수 없습니다: {audio_file}")

        if not srt_file:
            issues.append("자막 파일이 생성되지 않았습니다")
        elif not os.path.exists(srt_file):
            issues.append(f"자막 파일을 찾을 수 없습니다: {srt_file}")

        # ===== 2. 재생 시간 체크 =====
        if duration_sec < self.subtitle_criteria["min_duration"]:
            issues.append(f"영상이 너무 짧습니다 ({duration_sec:.1f}초 < {self.subtitle_criteria['min_duration']}초)")
        elif duration_sec > self.subtitle_criteria["max_duration"]:
            issues.append(f"영상이 너무 깁니다 ({duration_sec:.1f}초 > {self.subtitle_criteria['max_duration']}초)")

        # ===== 3. 자막 개수 체크 =====
        subtitle_count = len(timeline)
        if subtitle_count < self.subtitle_criteria["min_subtitles"]:
            issues.append(f"자막이 부족합니다 ({subtitle_count}개 < {self.subtitle_criteria['min_subtitles']}개)")

        # ===== 4. 상단 타이틀 검수 =====
        title_issues = self._check_title_style(title_data, context)
        if title_issues:
            warnings.extend(title_issues)  # 타이틀은 경고로 처리

        # ===== 5. 자막 라인 분할 검수 (핵심!) =====
        line_issues = self._check_line_splitting(timeline)
        if line_issues["critical"]:
            issues.extend(line_issues["critical"])
        if line_issues["warnings"]:
            warnings.extend(line_issues["warnings"])

        # ===== 6. 자막 타이밍 검수 =====
        timing_issues = self._check_subtitle_timing(timeline)
        if timing_issues:
            warnings.extend(timing_issues)

        passed = len(issues) == 0

        self.log(f"자막 검수 완료: {duration_sec:.1f}초, 자막 {subtitle_count}개, 통과: {passed}")
        if warnings:
            self.log(f"경고 {len(warnings)}개: {warnings[:3]}...")

        # 피드백 생성
        feedback_parts = []
        if issues:
            feedback_parts.append("[필수 수정]\n" + "\n".join(f"- {i}" for i in issues))
        if warnings:
            feedback_parts.append("[개선 권장]\n" + "\n".join(f"- {w}" for w in warnings))

        return {
            "passed": passed,
            "duration_sec": duration_sec,
            "subtitle_count": subtitle_count,
            "issues": issues,
            "warnings": warnings,
            "line_check": line_issues.get("stats", {}),
            "feedback": "\n\n".join(feedback_parts) if feedback_parts else "자막 검수 통과",
            "cost": 0,  # 규칙 기반이므로 비용 없음
        }

    def _check_title_style(self, title_data: Dict, context: TaskContext) -> List[str]:
        """상단 타이틀 스타일 검수"""
        issues = []

        if not self.title_criteria["required"]:
            return issues

        # 타이틀이 없는 경우
        if not title_data:
            # 토픽에서 타이틀 추출 시도
            topic = context.topic or ""
            if len(topic) > self.title_criteria["max_chars"]:
                issues.append(f"상단 타이틀이 너무 깁니다 ({len(topic)}자 > {self.title_criteria['max_chars']}자)")
            return issues

        # 타이틀 텍스트 길이 검사
        title_text = title_data.get("text", "")
        if len(title_text) > self.title_criteria["max_chars"]:
            issues.append(f"상단 타이틀이 너무 깁니다 ({len(title_text)}자 > {self.title_criteria['max_chars']}자)")

        # 스타일 검사
        style = title_data.get("style", {})
        for required_style in self.title_criteria["style_required"]:
            if not style.get(required_style):
                issues.append(f"상단 타이틀에 '{required_style}' 스타일이 필요합니다")

        # 위치 검사
        position = title_data.get("position", "top")
        if position != self.title_criteria["position"]:
            issues.append(f"상단 타이틀 위치가 잘못되었습니다 ({position} → {self.title_criteria['position']})")

        return issues

    def _check_line_splitting(self, timeline: List[Dict]) -> Dict[str, Any]:
        """
        자막 라인 분할 검수

        TTS는 문장 단위이지만, 자막은 짧은 라인으로 분할되어야 함
        - 한 줄 최대 18자 (빠른 가독성)
        - 긴 문장은 여러 자막으로 분할
        """
        critical = []
        warnings = []
        stats = {
            "total_lines": len(timeline),
            "long_lines": 0,
            "avg_chars": 0,
            "max_chars": 0,
        }

        if not timeline:
            return {"critical": critical, "warnings": warnings, "stats": stats}

        max_chars = self.subtitle_criteria["max_chars_per_line"]
        total_chars = 0
        long_lines = []

        for i, item in enumerate(timeline):
            text = item.get("text", "")
            char_count = len(text)
            total_chars += char_count

            if char_count > stats["max_chars"]:
                stats["max_chars"] = char_count

            # 한 줄이 너무 긴 경우
            if char_count > max_chars:
                stats["long_lines"] += 1
                long_lines.append({
                    "index": i + 1,
                    "chars": char_count,
                    "text": text[:30] + "..." if len(text) > 30 else text
                })

        stats["avg_chars"] = total_chars / len(timeline) if timeline else 0

        # 결과 분석
        long_ratio = stats["long_lines"] / len(timeline) if timeline else 0

        if long_ratio > 0.5:
            # 50% 이상이 긴 라인이면 필수 수정
            critical.append(
                f"자막 {stats['long_lines']}/{len(timeline)}개가 너무 깁니다 "
                f"(최대 {max_chars}자 권장). 문장을 짧게 분할하세요."
            )
        elif long_ratio > 0.2:
            # 20% 이상이면 경고
            warnings.append(
                f"자막 {stats['long_lines']}개가 길어서 가독성이 떨어질 수 있습니다 "
                f"(평균 {stats['avg_chars']:.1f}자, 최대 {stats['max_chars']}자)"
            )

        # 가장 긴 라인 3개 샘플
        if long_lines:
            sample = long_lines[:3]
            sample_text = ", ".join(f"#{s['index']}({s['chars']}자)" for s in sample)
            warnings.append(f"긴 자막 샘플: {sample_text}")

        return {
            "critical": critical,
            "warnings": warnings,
            "stats": stats,
        }

    def _check_subtitle_timing(self, timeline: List[Dict]) -> List[str]:
        """자막 타이밍 검수 (노출 시간)"""
        warnings = []

        min_duration = self.subtitle_criteria["min_line_duration"]
        max_duration = self.subtitle_criteria["max_line_duration"]

        too_short = 0
        too_long = 0

        for item in timeline:
            start = item.get("start_sec", 0)
            end = item.get("end_sec", 0)
            duration = end - start

            if duration < min_duration:
                too_short += 1
            elif duration > max_duration:
                too_long += 1

        if too_short > 0:
            warnings.append(
                f"자막 {too_short}개가 너무 짧게 표시됩니다 "
                f"(최소 {min_duration}초 권장)"
            )

        if too_long > 0:
            warnings.append(
                f"자막 {too_long}개가 너무 오래 표시됩니다 "
                f"(최대 {max_duration}초 권장, 분할 필요)"
            )

        return warnings

    def _format_scenes(self, scenes: List[Dict[str, Any]]) -> str:
        """씬 목록을 포맷팅"""
        lines = []
        for scene in scenes:
            scene_num = scene.get("scene_number", 0)
            narration = scene.get("narration", "")
            duration = scene.get("duration", "")
            lines.append(f"씬{scene_num} ({duration}): {narration}")
        return "\n".join(lines)

    def _validate_person(self, context: TaskContext) -> Dict[str, Any]:
        """
        ★ person(인물명) 유효성 검증

        잘못된 인물명 패턴:
        1. INVALID_PERSON_NAMES에 포함된 일반 명사/호칭
        2. 너무 짧거나 긴 이름 (1글자 또는 10글자 초과)
        3. 빈 문자열

        Returns:
            {
                "valid": True/False,
                "person": "이시영",
                "issues": ["문제점..."],
                "feedback": "구체적 피드백"
            }
        """
        person = context.person or ""
        issues = []

        self.log(f"person 검증: '{person}'")

        # 1. 빈 문자열 체크
        if not person or not person.strip():
            issues.append("인물명이 비어있습니다")

        # 2. 길이 체크
        elif len(person) < 2:
            issues.append(f"인물명이 너무 짧습니다: '{person}' (최소 2글자)")
        elif len(person) > 10:
            issues.append(f"인물명이 너무 깁니다: '{person}' (최대 10글자)")

        # 3. 무효한 이름 체크 (일반 명사/호칭)
        elif person in self.INVALID_PERSON_NAMES:
            issues.append(
                f"'{person}'은(는) 실제 인물명이 아닙니다. "
                f"뉴스 제목에서 실제 연예인/인물 이름을 추출해야 합니다. "
                f"예: '엄마' → '이시영', '선수' → '손흥민'"
            )

        # 4. 숫자로만 구성된 경우
        elif person.isdigit():
            issues.append(f"'{person}'은(는) 유효한 인물명이 아닙니다 (숫자만)")

        # 검증 결과
        valid = len(issues) == 0

        if valid:
            self.log(f"person 검증 통과: '{person}'")
        else:
            self.log(f"person 검증 실패: {issues}", "warning")

        return {
            "valid": valid,
            "person": person,
            "issues": issues,
            "feedback": "\n".join(issues) if issues else "인물명 검증 통과",
        }
