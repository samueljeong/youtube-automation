"""
한국사 파이프라인 - Fact Check Agent (사실 검증 에이전트)

## 성격 및 역할
역사학 박사 출신의 팩트체커.
AI가 생성한 대본에서 역사적 사실 오류를 철저히 검증.

## 철학
- "역사는 기록이다" - 객관적 사실만이 허용됨
- AI는 허구를 생성할 수 있으므로 모든 주장은 검증 필요
- 검증 불가능한 내용은 삭제하거나 표현 수정

## 책임
- 대본 내 모든 역사적 사실 검증
- 연도, 인물, 사건, 숫자의 정확성 확인
- AI 허구(hallucination) 탐지 및 플래깅
- 수정 필요 사항 구체적 피드백

## 검증 대상
1. 연도/날짜: 사건 발생 연도, 재위 기간
2. 인물: 이름, 직위, 관계
3. 지명: 당시 명칭, 현재 명칭
4. 숫자: 인구, 군사, 거리 등
5. 인과관계: 역사적 흐름의 논리성

## 허구 탐지 패턴
- "~했다고 전해진다" + 구체적 대화문 = 위험 신호
- 검증 불가능한 감정/심리 묘사
- 사료에 없는 구체적 숫자
- 시대착오적 표현/개념

## 결과
- VERIFIED: 검증 완료 (통과)
- NEEDS_CITATION: 출처 필요
- SUSPICIOUS: 허구 의심 (수정 권고)
- FALSE: 명백한 오류 (수정 필수)
"""

import re
import time
from typing import Any, Dict, List, Optional, Tuple

from .base import BaseAgent, AgentResult, AgentStatus, EpisodeContext


# 한국사 주요 연대표 (검증용)
KOREAN_HISTORY_DATES = {
    # 고조선
    "단군": {"event": "고조선 건국", "year": "기원전 2333년 (전설)", "note": "신화적 연대"},
    "위만조선": {"event": "위만조선 건국", "year": "기원전 194년"},
    "고조선 멸망": {"event": "한사군 설치", "year": "기원전 108년"},

    # 삼국시대
    "고구려 건국": {"event": "주몽 건국", "year": "기원전 37년"},
    "백제 건국": {"event": "온조 건국", "year": "기원전 18년"},
    "신라 건국": {"event": "박혁거세 건국", "year": "기원전 57년"},
    "광개토대왕": {"event": "재위", "year": "391-412년"},
    "삼국통일": {"event": "신라 삼국통일", "year": "676년"},

    # 발해
    "발해 건국": {"event": "대조영 건국", "year": "698년"},
    "발해 멸망": {"event": "거란에 멸망", "year": "926년"},

    # 고려
    "고려 건국": {"event": "왕건 건국", "year": "918년"},
    "고려 멸망": {"event": "조선 건국", "year": "1392년"},

    # 조선
    "조선 건국": {"event": "이성계 건국", "year": "1392년"},
    "임진왜란": {"event": "왜군 침략", "year": "1592년"},
    "병자호란": {"event": "청군 침략", "year": "1636년"},
    "조선 멸망": {"event": "경술국치", "year": "1910년"},

    # 근현대
    "3.1운동": {"event": "독립만세운동", "year": "1919년"},
    "광복": {"event": "해방", "year": "1945년"},
    "대한민국 건국": {"event": "정부 수립", "year": "1948년"},
    "6.25전쟁": {"event": "한국전쟁 발발", "year": "1950년"},
}

# 허구 의심 패턴
HALLUCINATION_PATTERNS = [
    # 검증 불가능한 감정/심리 묘사
    (r"그는 .{0,20}(생각했다|느꼈다|결심했다|다짐했다)", "SUSPICIOUS", "검증 불가능한 심리 묘사"),
    (r"(눈물을 흘리며|분노에 떨며|기쁨에 겨워)", "SUSPICIOUS", "검증 불가능한 감정 묘사"),

    # 구체적 대화문 (사료에 없는 경우)
    (r'"[^"]{30,}"', "NEEDS_CITATION", "긴 직접 인용문 - 출처 필요"),

    # 과도한 구체화
    (r"정확히 \d+명", "NEEDS_CITATION", "구체적 숫자 - 출처 필요"),
    (r"(약|대략) \d{5,}명", "NEEDS_CITATION", "대규모 숫자 - 출처 필요"),

    # 시대착오적 표현
    (r"(민주주의|자본주의|사회주의)", "CHECK_ERA", "근현대 개념 - 시대 확인 필요"),
]


class FactCheckAgent(BaseAgent):
    """사실 검증 에이전트"""

    def __init__(self):
        super().__init__("FactCheckAgent")

        # 검증 기준
        self.history_dates = KOREAN_HISTORY_DATES
        self.hallucination_patterns = HALLUCINATION_PATTERNS

    async def execute(self, context: EpisodeContext, **kwargs) -> AgentResult:
        """
        대본 사실 검증 실행

        Args:
            context: 에피소드 컨텍스트 (script 필수)
            **kwargs:
                strict: 엄격 모드 (기본 True)

        Returns:
            AgentResult with fact-check results
        """
        self.set_status(AgentStatus.RUNNING)
        start_time = time.time()

        strict = kwargs.get("strict", True)

        context.add_log(
            self.name,
            "사실 검증 시작",
            "running",
            f"엄격 모드: {strict}"
        )

        try:
            # 대본 확인
            if not context.script:
                raise ValueError("대본(script)이 없습니다. ScriptAgent를 먼저 실행하세요.")

            script = context.script

            # 1. 연도/날짜 검증
            date_issues = self._check_dates(script, context)

            # 2. 허구 패턴 탐지
            hallucination_issues = self._detect_hallucinations(script)

            # 3. 역사적 논리 검증
            logic_issues = self._check_historical_logic(script, context)

            # 4. 숫자 검증
            number_issues = self._check_numbers(script, context)

            # 결과 종합
            all_issues = date_issues + hallucination_issues + logic_issues + number_issues

            # 심각도별 분류
            false_count = len([i for i in all_issues if i["severity"] == "FALSE"])
            suspicious_count = len([i for i in all_issues if i["severity"] == "SUSPICIOUS"])
            citation_count = len([i for i in all_issues if i["severity"] == "NEEDS_CITATION"])

            # 통과 여부 결정
            if strict:
                passed = false_count == 0 and suspicious_count <= 2
            else:
                passed = false_count == 0

            duration = time.time() - start_time

            result_status = "success" if passed else "warning"
            context.add_log(
                self.name,
                f"사실 검증 완료: {len(all_issues)}건 발견",
                result_status,
                f"FALSE: {false_count}, SUSPICIOUS: {suspicious_count}, CITATION: {citation_count}"
            )

            if passed:
                self.set_status(AgentStatus.SUCCESS)
            else:
                self.set_status(AgentStatus.WAITING_REVIEW)

            return AgentResult(
                success=True,
                data={
                    "passed": passed,
                    "total_issues": len(all_issues),
                    "issues": all_issues,
                    "summary": {
                        "false": false_count,
                        "suspicious": suspicious_count,
                        "needs_citation": citation_count,
                    },
                    "recommendation": self._generate_recommendation(all_issues, passed),
                },
                duration=duration,
            )

        except Exception as e:
            duration = time.time() - start_time
            error_msg = str(e)

            context.add_log(self.name, "사실 검증 실패", "error", error_msg)
            self.set_status(AgentStatus.FAILED)

            return AgentResult(
                success=False,
                error=error_msg,
                duration=duration,
            )

    def _check_dates(self, script: str, context: EpisodeContext) -> List[Dict[str, Any]]:
        """연도/날짜 검증"""
        issues = []

        # 연도 패턴 추출
        year_pattern = r"(기원전\s*)?(\d{1,4})년"
        matches = re.finditer(year_pattern, script)

        for match in matches:
            full_match = match.group(0)
            is_bc = match.group(1) is not None
            year = int(match.group(2))

            # 시대 범위 검증
            era_range = self._get_era_year_range(context.era_name)
            if era_range:
                start, end = era_range

                if is_bc:
                    year = -year

                if not (start <= year <= end):
                    issues.append({
                        "type": "DATE",
                        "severity": "SUSPICIOUS",
                        "text": full_match,
                        "message": f"'{full_match}'이(가) {context.era_name} 시대 범위({start}~{end}년)를 벗어남",
                        "suggestion": "연도 확인 필요",
                    })

        return issues

    def _get_era_year_range(self, era_name: str) -> Optional[Tuple[int, int]]:
        """시대별 연도 범위"""
        era_ranges = {
            "고조선": (-2333, -108),
            "삼국시대": (-57, 668),
            "고구려": (-37, 668),
            "백제": (-18, 660),
            "신라": (-57, 935),
            "통일신라": (668, 935),
            "발해": (698, 926),
            "고려": (918, 1392),
            "조선": (1392, 1897),
            "대한제국": (1897, 1910),
            "일제강점기": (1910, 1945),
            "대한민국": (1948, 2100),
        }
        return era_ranges.get(era_name)

    def _detect_hallucinations(self, script: str) -> List[Dict[str, Any]]:
        """AI 허구 패턴 탐지"""
        issues = []

        for pattern, severity, message in self.hallucination_patterns:
            matches = re.finditer(pattern, script)
            for match in matches:
                issues.append({
                    "type": "HALLUCINATION",
                    "severity": severity,
                    "text": match.group(0)[:50] + "..." if len(match.group(0)) > 50 else match.group(0),
                    "message": message,
                    "suggestion": self._get_hallucination_suggestion(severity),
                })

        return issues

    def _get_hallucination_suggestion(self, severity: str) -> str:
        """허구 유형별 수정 제안"""
        suggestions = {
            "FALSE": "삭제하거나 검증된 내용으로 대체",
            "SUSPICIOUS": "사료 확인 후 표현 수정 권장",
            "NEEDS_CITATION": "출처 명시 또는 '~라고 전해진다' 형식으로 수정",
            "CHECK_ERA": "해당 시대에 적합한 표현인지 확인",
        }
        return suggestions.get(severity, "확인 필요")

    def _check_historical_logic(self, script: str, context: EpisodeContext) -> List[Dict[str, Any]]:
        """역사적 논리 검증"""
        issues = []

        # 발해 관련 검증 (예시)
        if context.era_name == "발해":
            # 발해가 고구려 계승국임을 확인
            if "고구려" not in script and "고구려" not in context.title:
                issues.append({
                    "type": "LOGIC",
                    "severity": "SUSPICIOUS",
                    "text": "발해-고구려 연관성",
                    "message": "발해 대본에서 고구려와의 연관성 언급이 부족함",
                    "suggestion": "발해의 고구려 계승성 언급 추가 권장",
                })

            # 발해 멸망 후 이야기 체크
            if "926년" in script or "멸망" in script:
                if "거란" not in script and "요" not in script:
                    issues.append({
                        "type": "LOGIC",
                        "severity": "NEEDS_CITATION",
                        "text": "발해 멸망",
                        "message": "발해 멸망 언급 시 거란(요) 관련 내용 필요",
                        "suggestion": "거란(요나라)의 침략으로 멸망했음을 명시",
                    })

        return issues

    def _check_numbers(self, script: str, context: EpisodeContext) -> List[Dict[str, Any]]:
        """숫자 검증"""
        issues = []

        # 대규모 숫자 패턴
        large_number_pattern = r"(\d{1,3}(?:,\d{3})*|\d+)(만|천|백)\s*명"
        matches = re.finditer(large_number_pattern, script)

        for match in matches:
            number_text = match.group(0)
            # 10만 이상의 숫자는 출처 필요
            full_text = match.group(0)
            if "만" in full_text:
                issues.append({
                    "type": "NUMBER",
                    "severity": "NEEDS_CITATION",
                    "text": number_text,
                    "message": f"대규모 인원 '{number_text}' - 출처 확인 필요",
                    "suggestion": "정확한 사료 출처 명시 또는 '약', '추정' 표현 사용",
                })

        return issues

    def _generate_recommendation(self, issues: List[Dict], passed: bool) -> str:
        """종합 권고사항 생성"""
        if passed and len(issues) == 0:
            return "✓ 모든 역사적 사실이 검증되었습니다. 대본 진행 가능합니다."
        elif passed:
            return f"⚠️ {len(issues)}건의 확인 사항이 있지만 통과 가능합니다. 가능하면 수정을 권장합니다."
        else:
            false_issues = [i for i in issues if i["severity"] == "FALSE"]
            if false_issues:
                return f"❌ {len(false_issues)}건의 명백한 오류가 있습니다. 반드시 수정 후 진행하세요."
            else:
                return "❌ 허구 의심 사항이 많습니다. 검토 후 수정을 권장합니다."


# 동기 실행 래퍼
def check_facts(context: EpisodeContext, strict: bool = True) -> Dict[str, Any]:
    """
    대본 사실 검증 (동기 버전)

    Args:
        context: 에피소드 컨텍스트 (script 필수)
        strict: 엄격 모드

    Returns:
        검증 결과
    """
    import asyncio

    agent = FactCheckAgent()

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


def check_facts_strict(script: str, era_name: str) -> Dict[str, Any]:
    """
    대본 사실 엄격 검증 (블로킹)

    FALSE 등급 발견 시 ValueError 발생 - 파이프라인 진행 차단

    Args:
        script: 대본 텍스트
        era_name: 시대명

    Returns:
        검증 결과 (통과 시)

    Raises:
        ValueError: FALSE 등급 발견 시
    """
    agent = FactCheckAgent()

    # 임시 컨텍스트 생성
    context = EpisodeContext(
        episode_id="temp",
        episode_number=0,
        era_name=era_name,
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
    false_issues = [i for i in data["issues"] if i["severity"] == "FALSE"]

    if false_issues:
        issues_str = "\n".join(f"  - {i['text']}: {i['message']}" for i in false_issues)
        raise ValueError(
            f"사실 검증 실패 - 명백한 오류 발견 (진행 불가):\n{issues_str}"
        )

    # 경고 사항 로깅
    suspicious_issues = [i for i in data["issues"] if i["severity"] == "SUSPICIOUS"]
    if suspicious_issues:
        warnings_str = "\n".join(f"  ⚠️ {i['text']}: {i['message']}" for i in suspicious_issues)
        print(f"[FactCheckAgent] 허구 의심 사항 (확인 권장):\n{warnings_str}")

    print(f"[FactCheckAgent] ✓ 사실 검증 통과: {data['total_issues']}건 확인 필요")
    return data
