"""
한국사 파이프라인 - Image Agent (이미지 에이전트)

## 성격 및 역할
텍스트를 이미지화하는 전문가.
이미지만 봐도 내용이 이해될 수 있게 하는 능력 보유.

## 철학
- "한 장의 이미지가 천 마디 말을 대신한다"
- 역사적 정확성 + 시각적 임팩트 균형
- 시청자의 이해를 돕는 시각적 스토리텔링

## 책임
- 대본 기반 이미지 프롬프트 생성 (5~12개)
- 씬별 이미지 스타일 가이드 제공
- 시대별 색감/분위기 톤앤매너 설정
- 썸네일 문구 및 디자인 제안

## 이미지 유형
- establishing_shot: 전체 조망 (인트로)
- character_portrait: 인물 초상
- action_scene: 전투/사건 장면
- diagram_or_map: 지도/도식
- cultural_artifact: 유물/유적
- narrative_scene: 서사 장면
- closing_shot: 마무리 장면

## 시대별 스타일
- 고조선~삼국: 신화적, 웅장한 느낌
- 통일신라~고려: 불교 예술 영향
- 조선: 유교적 절제미 + 민화풍
- 근현대: 역사 사진 참조 스타일
"""

import re
import time
from typing import Any, Dict, List, Optional

from .base import BaseAgent, AgentResult, AgentStatus, EpisodeContext


# 이미지 스타일 가이드
IMAGE_STYLE_GUIDE = """
## 한국사 다큐멘터리 이미지 스타일 가이드

### 기본 스타일
- 한국 전통 수묵화 + 현대적 해석
- 색감: 차분한 갈색/청록색 계열
- 분위기: 역사적 무게감 + 드라마틱

### 시대별 특징
1. 고조선~삼국: 신화적/웅장한 느낌
2. 통일신라~고려: 불교 예술 영향
3. 조선 전기: 유교적 절제미
4. 조선 후기: 민화풍 생동감
5. 근현대: 역사 사진 참조 스타일

### 이미지 유형
- **인물 중심**: 역사적 인물 초상/장면
- **사건 중심**: 전투/회담/건축 등
- **지도/도식**: 영토/행정구역/무역로
- **유물/유적**: 문화재/건축물

### 금지 사항
- 현대적 요소 혼입
- 역사적으로 부정확한 복식/건축
- 폭력적/선정적 묘사
- 저작권 문제가 될 수 있는 유명 그림 모방

### 텍스트 오버레이 피하기
- 이미지 내 한글/한자 텍스트 최소화
- AI가 텍스트를 정확히 생성하지 못함
- 필요한 경우 후처리로 추가
"""


# 시대별 스타일 프리셋
ERA_STYLE_PRESETS = {
    "고조선": {
        "style": "mythological, ancient Korean, bronze age aesthetic",
        "color_palette": "earth tones, bronze, deep blue",
        "mood": "mysterious, legendary, primordial",
    },
    "삼국시대": {
        "style": "Three Kingdoms period Korea, traditional East Asian art",
        "color_palette": "gold, red, forest green",
        "mood": "heroic, dynamic, martial",
    },
    "통일신라": {
        "style": "Unified Silla period, Buddhist influenced art",
        "color_palette": "gold, jade green, royal purple",
        "mood": "refined, spiritual, prosperous",
    },
    "발해": {
        "style": "Balhae kingdom, northern Korean aesthetics",
        "color_palette": "dark blue, white, silver",
        "mood": "vast, powerful, frontier",
    },
    "고려": {
        "style": "Goryeo dynasty, Buddhist and aristocratic",
        "color_palette": "celadon green, gold, deep red",
        "mood": "elegant, spiritual, cultured",
    },
    "조선 전기": {
        "style": "early Joseon dynasty, Confucian aesthetics",
        "color_palette": "white, black, muted colors",
        "mood": "austere, dignified, scholarly",
    },
    "조선 중기": {
        "style": "mid Joseon dynasty, classical Korean painting",
        "color_palette": "ink wash, subtle colors",
        "mood": "contemplative, refined, literary",
    },
    "조선 후기": {
        "style": "late Joseon, folk painting (minhwa) style",
        "color_palette": "vibrant primary colors",
        "mood": "lively, expressive, populist",
    },
    "대한제국": {
        "style": "Korean Empire period, East-West fusion",
        "color_palette": "imperial yellow, western influences",
        "mood": "transitional, modernizing, proud",
    },
    "일제강점기": {
        "style": "Japanese colonial period, historical photography style",
        "color_palette": "sepia, muted, somber",
        "mood": "resistant, sorrowful, enduring",
    },
    "현대 대한민국": {
        "style": "modern Korea, documentary photography",
        "color_palette": "realistic, full color",
        "mood": "dynamic, progressive, hopeful",
    },
}


class ImageAgent(BaseAgent):
    """이미지 에이전트"""

    def __init__(self):
        super().__init__("ImageAgent")

        # 이미지 설정
        self.min_images = 5
        self.max_images = 12
        self.chars_per_minute = 910  # 한국어 TTS 기준

    async def execute(self, context: EpisodeContext, **kwargs) -> AgentResult:
        """
        이미지 프롬프트 생성 실행

        Args:
            context: 에피소드 컨텍스트 (script 필수)
            **kwargs:
                image_count: 생성할 이미지 수 (자동 계산됨)

        Returns:
            AgentResult with image prompts
        """
        self.set_status(AgentStatus.RUNNING)
        start_time = time.time()

        context.add_log(
            self.name,
            "이미지 프롬프트 생성 시작",
            "running",
            f"시대: {context.era_name}"
        )

        try:
            # 대본 확인
            if not context.script:
                raise ValueError("대본(script)이 없습니다. ScriptAgent를 먼저 실행하세요.")

            script = context.script

            # 이미지 개수 계산
            image_count = kwargs.get("image_count")
            if not image_count:
                image_count = self._calculate_image_count(script)

            # 시대별 스타일 가져오기
            era_style = self._get_era_style(context.era_name)

            # 씬 분할 가이드 생성
            scene_guide = self._generate_scene_guide(script, image_count, context)

            # 이미지 프롬프트 템플릿 생성
            prompt_templates = self._generate_prompt_templates(
                scene_guide, era_style, context
            )

            # 썸네일 가이드 생성
            thumbnail_guide = self._generate_thumbnail_guide(context, era_style)

            duration = time.time() - start_time

            context.add_log(
                self.name,
                f"이미지 가이드 생성 완료 ({image_count}개)",
                "success",
                f"{duration:.1f}초"
            )
            self.set_status(AgentStatus.WAITING_REVIEW)

            return AgentResult(
                success=True,
                data={
                    "image_count": image_count,
                    "era_style": era_style,
                    "scene_guide": scene_guide,
                    "prompt_templates": prompt_templates,
                    "thumbnail_guide": thumbnail_guide,
                    "style_guide": IMAGE_STYLE_GUIDE,
                },
                duration=duration,
            )

        except Exception as e:
            duration = time.time() - start_time
            error_msg = str(e)

            context.add_log(self.name, "이미지 가이드 생성 실패", "error", error_msg)
            self.set_status(AgentStatus.FAILED)

            return AgentResult(
                success=False,
                error=error_msg,
                duration=duration,
            )

    def _calculate_image_count(self, script: str) -> int:
        """대본 길이 기반 이미지 개수 계산"""
        length = len(script)
        estimated_minutes = length / self.chars_per_minute

        if estimated_minutes < 8:
            return 5
        elif estimated_minutes < 10:
            return 8
        elif estimated_minutes < 15:
            return 11
        else:
            return 12

    def _get_era_style(self, era_name: str) -> Dict[str, str]:
        """시대별 스타일 프리셋 가져오기"""
        # 시대명에서 매칭되는 프리셋 찾기
        for era_key, style in ERA_STYLE_PRESETS.items():
            if era_key in era_name:
                return style

        # 기본 스타일
        return {
            "style": "traditional Korean historical art",
            "color_palette": "earth tones, traditional colors",
            "mood": "historical, dignified",
        }

    def _generate_scene_guide(
        self,
        script: str,
        image_count: int,
        context: EpisodeContext
    ) -> List[Dict[str, Any]]:
        """씬 분할 가이드 생성"""

        scenes = []

        # 대본을 이미지 개수로 균등 분할
        script_length = len(script)
        chunk_size = script_length // image_count

        for i in range(image_count):
            start = i * chunk_size
            end = start + chunk_size if i < image_count - 1 else script_length

            chunk = script[start:end]

            # 씬 정보 추출
            scene = {
                "scene_index": i + 1,
                "estimated_duration": f"{chunk_size / self.chars_per_minute:.1f}분",
                "text_preview": chunk[:200] + "..." if len(chunk) > 200 else chunk,
                "suggested_type": self._suggest_image_type(chunk, i, image_count),
                "key_elements": self._extract_key_elements(chunk),
            }

            scenes.append(scene)

        return scenes

    def _suggest_image_type(self, chunk: str, index: int, total: int) -> str:
        """씬별 이미지 유형 제안"""

        # 첫 씬: 인트로 (전체 조망)
        if index == 0:
            return "establishing_shot"

        # 마지막 씬: 아웃트로 (마무리)
        if index == total - 1:
            return "closing_shot"

        # 전투/갈등 키워드
        battle_keywords = ["전투", "전쟁", "공격", "침략", "정벌", "저항"]
        if any(kw in chunk for kw in battle_keywords):
            return "action_scene"

        # 인물 키워드
        person_keywords = ["왕", "장군", "승려", "학자", "대신"]
        if any(kw in chunk for kw in person_keywords):
            return "character_portrait"

        # 제도/정책 키워드
        system_keywords = ["제도", "정책", "행정", "법", "관리"]
        if any(kw in chunk for kw in system_keywords):
            return "diagram_or_map"

        # 문화/예술 키워드
        culture_keywords = ["문화", "예술", "불교", "유교", "건축"]
        if any(kw in chunk for kw in culture_keywords):
            return "cultural_artifact"

        return "narrative_scene"

    def _extract_key_elements(self, chunk: str) -> List[str]:
        """텍스트에서 핵심 요소 추출"""
        elements = []

        # 인물명 추출 (한글 2-4글자 + 왕/장군/대신 등)
        person_patterns = [
            r"[가-힣]{2,4}왕",
            r"[가-힣]{2,4}\s*장군",
            r"[가-힣]{2,4}\s*대사",
        ]
        for pattern in person_patterns:
            matches = re.findall(pattern, chunk)
            elements.extend(matches[:2])  # 최대 2개

        # 장소명 추출
        place_patterns = [
            r"[가-힣]{2,6}성",
            r"[가-힣]{2,4}궁",
            r"[가-힣]{2,4}사\b",  # 절
        ]
        for pattern in place_patterns:
            matches = re.findall(pattern, chunk)
            elements.extend(matches[:2])

        # 연도 추출
        year_matches = re.findall(r"(\d{3,4}년)", chunk)
        elements.extend(year_matches[:2])

        return list(set(elements))[:5]

    def _generate_prompt_templates(
        self,
        scene_guide: List[Dict[str, Any]],
        era_style: Dict[str, str],
        context: EpisodeContext
    ) -> List[Dict[str, Any]]:
        """이미지 프롬프트 템플릿 생성"""

        templates = []

        for scene in scene_guide:
            image_type = scene["suggested_type"]
            key_elements = scene["key_elements"]

            # 기본 프롬프트 구조
            base_prompt = f"{era_style['style']}, {era_style['mood']} atmosphere"

            # 유형별 프롬프트 추가
            type_prompts = {
                "establishing_shot": "wide panoramic view, cinematic composition",
                "closing_shot": "reflective mood, symbolic imagery",
                "action_scene": "dynamic composition, movement, tension",
                "character_portrait": "dignified portrait, historical costume",
                "diagram_or_map": "illustrated map or diagram style, informative",
                "cultural_artifact": "detailed artifact or architecture, artistic",
                "narrative_scene": "storytelling composition, emotional",
            }

            type_prompt = type_prompts.get(image_type, "historical scene")

            # 핵심 요소 추가
            elements_str = ", ".join(key_elements) if key_elements else ""

            template = {
                "scene_index": scene["scene_index"],
                "image_type": image_type,
                "prompt_template": f"{base_prompt}, {type_prompt}",
                "key_elements": elements_str,
                "color_palette": era_style["color_palette"],
                "negative_prompt": "text, watermark, modern elements, anachronistic items",
                "aspect_ratio": "16:9",
            }

            templates.append(template)

        return templates

    def _generate_thumbnail_guide(
        self,
        context: EpisodeContext,
        era_style: Dict[str, str]
    ) -> Dict[str, Any]:
        """썸네일 가이드 생성"""

        # 제목에서 핵심 키워드 추출
        title_keywords = context.title.split()[:3] if context.title else []

        # 썸네일 문구 제안
        text_suggestions = []

        if context.title:
            # 짧은 버전
            short_title = context.title[:10] if len(context.title) > 10 else context.title
            text_suggestions.append({
                "line1": short_title,
                "line2": context.era_name,
                "style": "bold",
            })

            # 질문형
            text_suggestions.append({
                "line1": f"{context.era_name}",
                "line2": "그 진실은?",
                "style": "dramatic",
            })

        return {
            "recommended_style": era_style["style"],
            "color_scheme": era_style["color_palette"],
            "text_suggestions": text_suggestions,
            "composition_tips": [
                "중앙에 핵심 인물/상징 배치",
                "1/3 지점에 텍스트 영역 확보",
                "고대비 색상으로 가독성 확보",
            ],
            "avoid": [
                "복잡한 배경",
                "작은 글씨",
                "여러 인물 동시 등장",
            ],
        }


# 동기 실행 래퍼
def generate_image_guide(context: EpisodeContext, image_count: int = None) -> Dict[str, Any]:
    """
    이미지 가이드 생성 (동기 버전)

    Args:
        context: 에피소드 컨텍스트 (script 필수)
        image_count: 이미지 개수 (자동 계산)

    Returns:
        이미지 가이드
    """
    import asyncio

    agent = ImageAgent()

    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    result = loop.run_until_complete(
        agent.execute(context, image_count=image_count)
    )

    if result.success:
        return result.data
    else:
        raise Exception(result.error)


def calculate_image_count(script: str) -> int:
    """대본 기반 이미지 개수 계산"""
    agent = ImageAgent()
    return agent._calculate_image_count(script)
