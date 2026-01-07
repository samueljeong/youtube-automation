"""
한국사 파이프라인 - Script Agent (대본 에이전트)

## 성격 및 역할
세계에서 가장 유명한 작가.
40-60대 시청자가 좋아할 톤과 어체로 대본을 작성.
TTS 음성 합성에 최적화된 대본 작성.

## 철학
- "독자(시청자)가 왕이다" - 어려운 역사도 쉽고 재미있게
- 스토리텔링으로 몰입감 극대화
- TTS 음성 품질을 고려한 문장 구성
- 씬별로 명확하게 구분된 대본 작성

## 책임
- 12,000자 ±10% (10,800~13,200자) 분량의 역사 다큐멘터리 대본 작성
- **씬(Scene) 단위**로 구분된 대본 생성
- 40-60대 대상 차분하고 신뢰감 있는 톤
- TTS 최적화: 문장 길이, 호흡, 강조점 고려
- 검수 피드백 반영하여 개선

## 타겟 시청자
- 연령: 40-60대
- 관심사: 역사, 교양, 다큐멘터리
- 선호 톤: 차분하고 권위 있으면서도 친근한 설명

## TTS 최적화 원칙
1. 문장 길이: 20-50자 권장 (너무 길면 끊김)
2. 쉼표 활용: 자연스러운 호흡 단위로 구분
3. 강조점: 중요 단어 앞뒤 쉼표로 강조
4. 숫자: 한글로 풀어쓰기 (1392년 → 천삼백구십이년 또는 "일천 삼백 구십이 년")
5. 한자어 병기 지양 (TTS가 잘못 읽을 수 있음)

## 작업 프로세스
1. 웹서칭으로 주제 관련 최신 자료 수집
2. 타겟 시청자(40-60대)에 맞는 톤 연구
3. 씬 단위로 구조화된 대본 작성
4. TTS 최적화 검토 (문장 길이, 호흡 등)
5. 검수 에이전트 피드백 반영
"""

import time
from typing import Any, Dict, List, Optional

from .base import BaseAgent, AgentResult, AgentStatus, EpisodeContext


# 대본 스타일 가이드 (40-60대 대상, TTS 최적화)
SCRIPT_STYLE_GUIDE = """
## 문체 가이드 (한국사 다큐멘터리 - 40-60대 대상)

### 타겟 시청자
- 연령대: 40-60대
- 특징: 역사에 관심이 많고, 신뢰할 수 있는 정보를 원함
- 선호: 차분하고 권위 있으면서도 친근한 설명체

### 톤 & 어투
1. **차분한 신뢰감**: KBS/EBS 다큐멘터리 나레이션 스타일
2. **친근한 존댓말**: "~입니다", "~했습니다", "~이었죠"
3. **설명적 어투**: 교수가 학생에게 설명하듯이
4. **적절한 감탄**: "놀랍게도", "흥미롭게도", "중요한 점은"

### TTS 최적화 원칙
1. **문장 길이**: 20-50자 권장
   - 나쁜 예: "신라는 삼국을 통일한 뒤 새로운 행정체계를 구축하고 지방에 대한 통제력을 강화하기 위해 9주 5소경 체제를 시행했습니다."
   - 좋은 예: "신라는 삼국 통일 후, 새로운 행정체계를 만들었습니다. 바로 9주 5소경 체제였죠."

2. **호흡 단위 쉼표**:
   - "이 시기에, 중국에서는 당나라가 흥망성쇠를 겪고 있었습니다."
   - "흥미롭게도, 발해는 고구려 유민들이 세운 나라였습니다."

3. **강조점 표현**:
   - "이것이 바로, 해동성국이라 불린 이유입니다."
   - "여기서 주목할 점이 있습니다."

4. **숫자 표현** (TTS 가독성):
   - 연도: "서기 698년" 또는 "육백구십팔년"
   - 큰 숫자: "약 5만 명" → "약 오만 명"
   - 세기: "7세기" → "칠 세기"

### 권장 표현 (40-60대 친화)
- "자, 이제 본격적으로 살펴보겠습니다."
- "여기서 잠깐, 중요한 배경을 설명드리면..."
- "흥미로운 점은 바로 이것입니다."
- "그렇다면 왜 이런 일이 벌어졌을까요?"
- "결론부터 말씀드리면..."
- "이 부분이 핵심입니다."

### 금지 표현
- 학술적 유보: "~로 보기도 합니다" (전체에서 1-2회만)
- 불확실 표현: "단정하기 어렵습니다", "해석이 갈립니다"
- 젊은 세대 표현: "진짜", "대박", "미쳤다"
- 한자어 병기: "경주(慶州)" → 그냥 "경주"로

### 씬(Scene) 구조
- **씬 1 (인트로)**: 훅 + 주제 소개 (~1,200자)
- **씬 2 (배경)**: 역사적 맥락 (~2,400자)
- **씬 3 (본론1)**: 핵심 내용 전반 (~3,600자)
- **씬 4 (본론2)**: 핵심 내용 후반 (~3,600자)
- **씬 5 (마무리)**: 정리 + 다음화 예고 (~1,200자)

### 씬 전환 표현
- "자, 이제 다음으로 넘어가 보겠습니다."
- "이 부분을 이해했으니, 본격적인 이야기로 들어가 보죠."
- "그렇다면 이후에는 어떻게 되었을까요?"
"""

# 씬 구조 템플릿
SCENE_STRUCTURE = [
    {
        "scene": 1,
        "name": "인트로",
        "target_length": 1200,
        "purpose": "시청자 주목 + 주제 소개",
        "tips": [
            "구체적인 상황이나 질문으로 시작",
            "시청자의 호기심 유발",
            "영상의 핵심 가치 제시",
        ],
    },
    {
        "scene": 2,
        "name": "배경",
        "target_length": 2400,
        "purpose": "역사적 맥락 설명",
        "tips": [
            "시대적 배경 차분히 설명",
            "이전 에피소드 연결 (있다면)",
            "핵심 인물/사건 소개",
        ],
    },
    {
        "scene": 3,
        "name": "본론1",
        "target_length": 3600,
        "purpose": "핵심 내용 전반부",
        "tips": [
            "구체적인 사건과 인물",
            "인과관계 명확히",
            "숫자와 사례로 뒷받침",
        ],
    },
    {
        "scene": 4,
        "name": "본론2",
        "target_length": 3600,
        "purpose": "핵심 내용 후반부 + 클라이맥스",
        "tips": [
            "절정 부분에서 긴장감",
            "의미 있는 결과 제시",
            "역사적 평가 포함",
        ],
    },
    {
        "scene": 5,
        "name": "마무리",
        "target_length": 1200,
        "purpose": "정리 + 다음화 예고",
        "tips": [
            "핵심 내용 간략히 정리",
            "현재와의 연결점",
            "다음 에피소드 호기심 유발",
        ],
    },
]


class ScriptAgent(BaseAgent):
    """대본 에이전트 (씬 기반, 40-60대 대상, TTS 최적화)"""

    def __init__(self):
        super().__init__("ScriptAgent")

        # 대본 설정 (12,000자 ±10%)
        self.target_length = 12000  # 목표 글자수
        self.min_length = 10800  # -10%
        self.max_length = 13200  # +10%

        # 씬 구조
        self.scene_structure = SCENE_STRUCTURE

        # TTS 최적화 설정
        self.tts_config = {
            "sentence_length_min": 15,
            "sentence_length_max": 60,
            "optimal_sentence_length": 35,
        }

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

            # 대본 작성 가이드 생성 (씬별)
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
                    "scene_structure": self.scene_structure,
                    "tts_config": self.tts_config,
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
        """씬별 대본 작성 가이드 생성"""

        brief = context.brief

        # 씬별 가이드 생성
        scene_guides = []
        for scene in self.scene_structure:
            scene_guide = {
                "scene": scene["scene"],
                "name": scene["name"],
                "target_length": scene["target_length"],
                "purpose": scene["purpose"],
                "tips": scene["tips"],
                "content_hint": self._get_scene_content_hint(scene["scene"], context),
            }
            scene_guides.append(scene_guide)

        guide = {
            "episode_info": {
                "episode_id": context.episode_id,
                "episode_number": context.episode_number,
                "era": context.era_name,
                "title": context.title,
                "topic": context.topic,
            },

            "target_audience": {
                "age_range": "40-60대",
                "interests": "역사, 교양, 다큐멘터리",
                "preferred_tone": "차분하고 권위 있으면서도 친근한 설명체",
                "reference_style": "KBS/EBS 역사 다큐멘터리 나레이션",
            },

            "length_requirements": {
                "target": self.target_length,
                "min": self.min_length,
                "max": self.max_length,
                "tolerance": "±10%",
                "estimated_duration": f"{self.target_length / 910:.0f}분",
            },

            "scene_guides": scene_guides,

            "tts_optimization": {
                "sentence_length": f"{self.tts_config['sentence_length_min']}-{self.tts_config['sentence_length_max']}자",
                "comma_usage": "자연스러운 호흡 단위로 쉼표 사용",
                "emphasis": "중요 단어 앞뒤에 쉼표로 강조",
                "numbers": "한글로 풀어쓰기 권장",
                "avoid": "한자어 병기, 긴 문장, 외래어 남발",
            },

            "reference_materials": {
                "keywords": context.keywords,
                "reference_links": context.reference_links,
                "collected_materials": context.collected_materials,
            },

            "episode_connections": {
                "prev_episode": context.prev_episode,
                "next_episode": context.next_episode,
            },

            "feedback_to_apply": feedback,
        }

        return guide

    def _get_scene_content_hint(self, scene_num: int, context: EpisodeContext) -> str:
        """씬별 콘텐츠 힌트 생성"""

        brief = context.brief or {}
        key_points = brief.get("key_points", [])
        hook = brief.get("hook", "")
        ending_hook = brief.get("ending_hook", "")

        if scene_num == 1:  # 인트로
            return f"훅: {hook}" if hook else f"{context.title}에 대한 흥미로운 질문으로 시작"
        elif scene_num == 2:  # 배경
            return f"{context.era_name} 시대의 역사적 맥락과 배경 설명"
        elif scene_num == 3:  # 본론1
            points = key_points[:len(key_points)//2] if key_points else []
            return f"핵심 포인트: {', '.join(points)}" if points else "주요 사건과 인물 상세 설명"
        elif scene_num == 4:  # 본론2
            points = key_points[len(key_points)//2:] if key_points else []
            return f"핵심 포인트: {', '.join(points)}" if points else "사건의 결과와 역사적 의의"
        elif scene_num == 5:  # 마무리
            return f"마무리 훅: {ending_hook}" if ending_hook else "핵심 정리 + 다음 에피소드 예고"

        return ""

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

        # 길이 검사 (12,000 ±10%)
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

        # 젊은 세대 표현 검사 (40-60대 대상이므로)
        young_expressions = ["진짜", "대박", "미쳤다", "쩔어", "존잼"]
        for expr in young_expressions:
            if expr in script:
                issues.append(f"40-60대 부적합 표현: '{expr}'")

        # 대화체 검사
        conversational_endings = ["습니다", "입니다", "죠", "요"]
        has_conversational = any(ending in script for ending in conversational_endings)
        if not has_conversational:
            warnings.append("대화체 종결어미가 부족합니다")

        # 질문 검사
        if "?" not in script:
            warnings.append("시청자에게 던지는 질문이 없습니다")

        # TTS 최적화 검사 (문장 길이)
        sentences = [s.strip() for s in script.replace("!", ".").replace("?", ".").split(".") if s.strip()]
        long_sentences = [s for s in sentences if len(s) > 80]
        if len(long_sentences) > 5:
            warnings.append(f"TTS 부적합: 80자 초과 문장 {len(long_sentences)}개 (권장: 50자 이하)")

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


def validate_script_strict(script: str) -> Dict[str, Any]:
    """
    대본 유효성 엄격 검사 (블로킹)

    기준 미달 시 ValueError 발생 - 파이프라인 진행 차단

    기준:
    - 글자수: 10,800~13,200자 (12,000 ±10%)
    - 40-60대 부적합 표현 금지
    - 학술적 유보 표현 최소화

    Raises:
        ValueError: 필수 기준 미충족 시
    """
    agent = ScriptAgent()
    result = agent.validate_script(script)

    if not result["valid"]:
        issues_str = "\n".join(f"  - {issue}" for issue in result["issues"])
        raise ValueError(
            f"대본 검증 실패 (진행 불가):\n{issues_str}\n"
            f"현재 길이: {result['length']:,}자\n"
            f"허용 범위: {agent.min_length:,}~{agent.max_length:,}자"
        )

    # 경고가 있어도 통과하지만 로깅
    if result["warnings"]:
        warnings_str = "\n".join(f"  ⚠️ {w}" for w in result["warnings"])
        print(f"[ScriptAgent] 경고 (통과하지만 개선 권장):\n{warnings_str}")

    print(f"[ScriptAgent] ✓ 대본 검증 통과: {result['length']:,}자, 점수 {result['score']}/100")
    return result
