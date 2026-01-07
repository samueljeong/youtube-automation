"""
한국사 파이프라인 - YouTube Agent (유튜브 메타데이터 에이전트)

## 성격 및 역할
SEO 전문가이자 YouTube 알고리즘 마스터.
시청자의 클릭을 유도하는 제목, 설명, 태그를 생성.

## 철학
- "클릭되지 않으면 의미가 없다" - CTR 최적화 우선
- 정확한 정보와 호기심 유발의 균형
- 알고리즘과 시청자 모두를 만족시키는 메타데이터

## 책임
- SEO 최적화된 YouTube 제목 생성 (3가지 스타일)
- 검색 친화적인 설명 작성
- 관련 태그 생성 (최대 500자)
- 썸네일 텍스트 제안

## 제목 스타일
1. curiosity: 호기심 유발 (~의 비밀, 왜 ~했을까?)
2. solution: 정보 제공 (~하는 방법, ~의 진실)
3. authority: 권위 강조 ([역사 다큐] ~의 모든 것)

## SEO 원칙
- 제목: 핵심 키워드 앞배치, 50자 이내
- 설명: 첫 2줄에 핵심 정보, 해시태그 포함
- 태그: 대주제 → 세부주제 순서
"""

import re
import time
from typing import Any, Dict, List, Optional

from .base import BaseAgent, AgentResult, AgentStatus, EpisodeContext


# 제목 스타일 템플릿
TITLE_TEMPLATES = {
    "curiosity": [
        "{keyword}의 숨겨진 비밀",
        "왜 {keyword}였을까?",
        "{keyword}, 아무도 몰랐던 진실",
        "{keyword}의 충격적인 결말",
        "{era}의 미스터리, {keyword}",
    ],
    "solution": [
        "{keyword} 완벽 정리",
        "{keyword}의 모든 것",
        "5분만에 이해하는 {keyword}",
        "{keyword}, 이것만 알면 끝",
        "{era} {keyword} 총정리",
    ],
    "authority": [
        "[한국사] {era} | {keyword}",
        "[역사 다큐] {keyword}의 진실",
        "[KBS 스타일] {keyword}",
        "[역사 속으로] {era} {keyword}",
        "[한국사 시리즈] {keyword}",
    ],
}

# 시대별 인기 키워드
ERA_KEYWORDS = {
    "고조선": ["단군", "환웅", "청동기", "위만"],
    "삼국시대": ["광개토대왕", "삼국통일", "백제", "고구려", "신라"],
    "발해": ["대조영", "해동성국", "고구려 부흥", "만주"],
    "통일신라": ["불교", "경주", "골품제", "장보고"],
    "고려": ["왕건", "거란", "몽골", "팔만대장경"],
    "조선": ["세종대왕", "임진왜란", "이순신", "정조"],
    "일제강점기": ["독립운동", "3.1운동", "위안부", "강제징용"],
    "대한민국": ["6.25전쟁", "민주화", "경제성장", "IMF"],
}


class YouTubeAgent(BaseAgent):
    """유튜브 메타데이터 에이전트"""

    def __init__(self):
        super().__init__("YouTubeAgent")

        # SEO 설정
        self.max_title_length = 100  # YouTube 최대
        self.optimal_title_length = 50  # 권장
        self.max_description_length = 5000
        self.max_tags_length = 500

    async def execute(self, context: EpisodeContext, **kwargs) -> AgentResult:
        """
        YouTube 메타데이터 생성

        Args:
            context: 에피소드 컨텍스트 (script 필수)
            **kwargs:
                style: 제목 스타일 (curiosity/solution/authority)
                custom_keywords: 추가 키워드 목록

        Returns:
            AgentResult with YouTube metadata
        """
        self.set_status(AgentStatus.RUNNING)
        start_time = time.time()

        style = kwargs.get("style", "curiosity")
        custom_keywords = kwargs.get("custom_keywords", [])

        context.add_log(
            self.name,
            "메타데이터 생성 시작",
            "running",
            f"스타일: {style}"
        )

        try:
            # 대본 확인
            if not context.script:
                raise ValueError("대본(script)이 없습니다. ScriptAgent를 먼저 실행하세요.")

            script = context.script

            # 키워드 추출
            keywords = self._extract_keywords(script, context, custom_keywords)

            # 제목 생성 (3가지 스타일)
            titles = self._generate_titles(context, keywords)

            # 설명 생성
            description = self._generate_description(context, keywords, script)

            # 태그 생성
            tags = self._generate_tags(context, keywords)

            # 썸네일 텍스트 제안
            thumbnail_texts = self._generate_thumbnail_texts(context, keywords)

            # 타임스탬프 제안
            timestamps = self._suggest_timestamps(script, context)

            duration = time.time() - start_time

            context.add_log(
                self.name,
                "메타데이터 생성 완료",
                "success",
                f"제목 3개, 태그 {len(tags)}개"
            )
            self.set_status(AgentStatus.SUCCESS)

            return AgentResult(
                success=True,
                data={
                    "titles": titles,
                    "description": description,
                    "tags": tags,
                    "thumbnail_texts": thumbnail_texts,
                    "timestamps": timestamps,
                    "keywords": keywords,
                    "selected_style": style,
                },
                duration=duration,
            )

        except Exception as e:
            duration = time.time() - start_time
            error_msg = str(e)

            context.add_log(self.name, "메타데이터 생성 실패", "error", error_msg)
            self.set_status(AgentStatus.FAILED)

            return AgentResult(
                success=False,
                error=error_msg,
                duration=duration,
            )

    def _extract_keywords(
        self,
        script: str,
        context: EpisodeContext,
        custom_keywords: List[str]
    ) -> Dict[str, Any]:
        """대본에서 키워드 추출"""

        keywords = {
            "primary": "",  # 메인 키워드
            "secondary": [],  # 서브 키워드
            "era": context.era_name,
            "custom": custom_keywords,
        }

        # 1. 제목에서 메인 키워드
        if context.title:
            # 쉼표로 분리된 경우 첫 번째 사용
            keywords["primary"] = context.title.split(",")[0].strip()

        # 2. 시대별 인기 키워드에서 매칭
        era_kws = ERA_KEYWORDS.get(context.era_name, [])
        matched_era_kws = [kw for kw in era_kws if kw in script]
        keywords["secondary"].extend(matched_era_kws[:3])

        # 3. 대본에서 자주 등장하는 인명/지명 추출
        # 한글 이름 패턴 (2~4자)
        name_pattern = r"[가-힣]{2,4}(?:왕|제|공|대왕|황제|장군|대사)"
        names = re.findall(name_pattern, script)
        # 빈도순 정렬
        name_counts = {}
        for name in names:
            name_counts[name] = name_counts.get(name, 0) + 1
        sorted_names = sorted(name_counts.items(), key=lambda x: x[1], reverse=True)
        keywords["secondary"].extend([n[0] for n in sorted_names[:5]])

        # 중복 제거
        keywords["secondary"] = list(dict.fromkeys(keywords["secondary"]))

        return keywords

    def _generate_titles(
        self,
        context: EpisodeContext,
        keywords: Dict[str, Any]
    ) -> Dict[str, str]:
        """3가지 스타일의 제목 생성"""

        titles = {}
        primary = keywords["primary"] or context.title
        era = keywords["era"]

        for style, templates in TITLE_TEMPLATES.items():
            # 스타일별 첫 번째 템플릿 사용
            template = templates[0]
            title = template.format(
                keyword=primary,
                era=era,
            )

            # 길이 조정
            if len(title) > self.optimal_title_length:
                # 키워드만 사용
                title = primary

            titles[style] = title

        # 에피소드 번호가 있으면 authority에 추가
        if context.episode_number:
            ep_num = context.episode_number
            titles["authority"] = f"[한국사 {ep_num}화] {era} | {primary}"

        return titles

    def _generate_description(
        self,
        context: EpisodeContext,
        keywords: Dict[str, Any],
        script: str
    ) -> str:
        """SEO 최적화된 설명 생성"""

        primary = keywords["primary"] or context.title
        era = keywords["era"]
        secondary = keywords["secondary"]

        # 첫 2줄: 핵심 정보 (검색 결과에 표시됨)
        intro = f"{era} 시대의 {primary}에 대해 알아봅니다.\n"
        intro += f"{context.topic}" if context.topic else f"역사 속 숨겨진 이야기를 만나보세요."

        # 해시태그
        hashtags = [f"#한국사", f"#{era}", f"#{primary.replace(' ', '')}"]
        hashtags.extend([f"#{kw.replace(' ', '')}" for kw in secondary[:3]])
        hashtag_line = " ".join(hashtags)

        # 참고 자료
        refs = ""
        if context.reference_links:
            refs = "\n\n📚 참고 자료:\n"
            refs += "\n".join([f"- {link}" for link in context.reference_links[:3]])

        # 구독 유도
        cta = "\n\n🔔 구독과 좋아요는 영상 제작에 큰 힘이 됩니다!"

        # 타임스탬프 플레이스홀더
        timestamps = "\n\n⏰ 타임스탬프\n00:00 인트로\n(영상 업로드 후 추가)"

        description = f"{intro}\n\n{hashtag_line}{refs}{cta}{timestamps}"

        # 길이 제한
        if len(description) > self.max_description_length:
            description = description[:self.max_description_length - 3] + "..."

        return description

    def _generate_tags(
        self,
        context: EpisodeContext,
        keywords: Dict[str, Any]
    ) -> List[str]:
        """SEO 태그 생성 (대주제 → 세부주제 순)"""

        tags = []

        # 1. 대주제
        tags.append("한국사")
        tags.append("역사")
        tags.append("역사 다큐멘터리")

        # 2. 시대
        era = keywords["era"]
        if era:
            tags.append(era)
            tags.append(f"{era} 역사")

        # 3. 메인 키워드
        primary = keywords["primary"]
        if primary:
            tags.append(primary)
            tags.append(primary.replace(" ", ""))

        # 4. 서브 키워드
        for kw in keywords["secondary"]:
            if kw not in tags:
                tags.append(kw)

        # 5. 커스텀 키워드
        for kw in keywords.get("custom", []):
            if kw not in tags:
                tags.append(kw)

        # 6. 일반 인기 태그
        popular_tags = [
            "한국역사", "KBS역사", "역사스페셜", "역사채널",
            "역사공부", "역사이야기", "한국사능력검정",
        ]
        for tag in popular_tags:
            if len(",".join(tags)) < self.max_tags_length - 20:
                tags.append(tag)

        return tags

    def _generate_thumbnail_texts(
        self,
        context: EpisodeContext,
        keywords: Dict[str, Any]
    ) -> List[str]:
        """썸네일 텍스트 제안"""

        primary = keywords["primary"] or context.title
        era = keywords["era"]

        suggestions = []

        # 1. 짧은 키워드 (2줄용)
        if len(primary) <= 6:
            suggestions.append(primary)
        else:
            # 첫 6자
            suggestions.append(primary[:6])

        # 2. 시대 + 키워드
        if era and len(f"{era} {primary[:4]}") <= 10:
            suggestions.append(f"{era} {primary[:4]}")

        # 3. 호기심 유발
        suggestions.append("이것이 진실?")
        suggestions.append(f"{era}의 비밀")

        # 4. 에피소드 번호
        if context.episode_number:
            suggestions.append(f"{context.episode_number}화")

        return suggestions[:5]

    def _suggest_timestamps(
        self,
        script: str,
        context: EpisodeContext
    ) -> List[Dict[str, str]]:
        """타임스탬프 제안 (대략적인 구간)"""

        # 대본 길이 기준 예상 시간
        script_length = len(script)
        estimated_duration = script_length / 910  # 분

        timestamps = []

        # 기본 구조
        if context.brief and context.brief.get("structure"):
            structure = context.brief["structure"]
            current_time = 0

            for section in structure:
                part = section.get("part", "")
                length = section.get("length", 2000)

                # 시간 계산 (글자수 기준)
                duration_min = length / 910

                mm = int(current_time)
                ss = int((current_time - mm) * 60)
                time_str = f"{mm:02d}:{ss:02d}"

                timestamps.append({
                    "time": time_str,
                    "label": part,
                })

                current_time += duration_min
        else:
            # 기본 5단계
            default_sections = [
                ("00:00", "인트로"),
                (f"{int(estimated_duration * 0.1):02d}:00", "배경"),
                (f"{int(estimated_duration * 0.3):02d}:00", "본론1"),
                (f"{int(estimated_duration * 0.6):02d}:00", "본론2"),
                (f"{int(estimated_duration * 0.85):02d}:00", "마무리"),
            ]
            timestamps = [{"time": t, "label": l} for t, l in default_sections]

        return timestamps


# 동기 실행 래퍼
def generate_youtube_metadata(
    context: EpisodeContext,
    style: str = "curiosity"
) -> Dict[str, Any]:
    """
    YouTube 메타데이터 생성 (동기 버전)

    Args:
        context: 에피소드 컨텍스트 (script 필수)
        style: 제목 스타일 (curiosity/solution/authority)

    Returns:
        YouTube 메타데이터
    """
    import asyncio

    agent = YouTubeAgent()

    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    result = loop.run_until_complete(
        agent.execute(context, style=style)
    )

    if result.success:
        return result.data
    else:
        raise Exception(result.error)


def quick_metadata(
    title: str,
    era: str,
    script: str = "",
    style: str = "curiosity"
) -> Dict[str, Any]:
    """
    간단 메타데이터 생성 (컨텍스트 없이)

    Args:
        title: 에피소드 제목
        era: 시대명
        script: 대본 (선택)
        style: 제목 스타일

    Returns:
        {titles, description, tags, thumbnail_texts}
    """
    agent = YouTubeAgent()

    # 임시 컨텍스트 생성
    context = EpisodeContext(
        episode_id="temp",
        episode_number=0,
        era_name=era,
        era_episode=0,
        title=title,
        topic="",
    )
    context.script = script or f"{era} {title}에 대한 역사 이야기입니다."

    import asyncio

    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    result = loop.run_until_complete(agent.execute(context, style=style))

    if result.success:
        return result.data
    else:
        raise Exception(result.error)
