"""
sermon_modules/styles 패키지
설교 스타일별 프롬프트 및 구조 정의

지원 스타일 (2025-12-26 통합):
- three_points (3대지): 3포인트 설교 (주제설교 기능 통합)
- expository (강해설교): 본문 해설 중심 설교

※ topical(주제설교)는 three_points에 통합됨
"""

# ═══════════════════════════════════════════════════════════════
# 공통 가독성 가이드 (모든 스타일에 적용)
# ═══════════════════════════════════════════════════════════════

READABILITY_GUIDE = """
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
【 가독성 필수 지침 - 반드시 따르세요 】
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

▶ 성경 구절 인용 형식 (필수)

본문 말씀과 보충 성경구절을 인용할 때 반드시 아래 형식을 따르세요:

(줄바꿈)
창1:1
태초에 하나님이 천지를 창조하시니라
(줄바꿈)

예시:
~~~설명글~~~

요3:16
하나님이 세상을 이처럼 사랑하사 독생자를 주셨으니
이는 그를 믿는 자마다 멸망하지 않고 영생을 얻게 하려 하심이라

~~~설명글 계속~~~

▶ 문장 작성 원칙

1. 한 문장은 최대 2줄 이내
2. 핵심 내용은 짧게 끊어서 작성
3. 긴 설명은 여러 문장으로 나누기
4. 단락 사이에 적절한 줄바꿈

▶ 피해야 할 것

✗ 5줄 이상 이어지는 긴 문장
✗ 성경 구절을 문장 중간에 삽입
✗ 줄바꿈 없이 계속되는 설명
✗ 구절 번호만 쓰고 본문 생략

▶ 권장 패턴

설명글...
설명글...

(성경구절)
구절번호
구절 내용

설명글 계속...
적용...

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

from .three_points import ThreePointsStyle
from .topical import TopicalStyle
from .expository import ExpositoryStyle

# 스타일 ID → 클래스 매핑 (2025-12-26: topical → ThreePointsStyle 통합)
STYLE_CLASSES = {
    "three_points": ThreePointsStyle,
    "3대지": ThreePointsStyle,
    "topical": ThreePointsStyle,    # 통합 (하위 호환)
    "주제설교": ThreePointsStyle,   # 통합
    "주제": ThreePointsStyle,       # 통합
    "expository": ExpositoryStyle,
    "강해설교": ExpositoryStyle,
    "강해": ExpositoryStyle,
}


def get_style(style_id: str):
    """
    스타일 ID로 스타일 클래스 인스턴스 반환

    Args:
        style_id: 스타일 식별자 (예: "three_points", "3대지", "topical")

    Returns:
        스타일 클래스 인스턴스 (없으면 ThreePointsStyle 기본값)
    """
    style_class = STYLE_CLASSES.get(style_id, ThreePointsStyle)
    return style_class()


def get_style_info(style_id: str) -> dict:
    """스타일 정보 반환"""
    style = get_style(style_id)
    return {
        "id": style.id,
        "name": style.name,
        "description": style.description,
        "structure_type": style.structure_type,
    }


def get_available_styles() -> list:
    """사용 가능한 스타일 목록 반환 (2025-12-26: 2개로 통합)"""
    return [
        {"id": "three_points", "name": "3대지", "description": "3포인트 설교 (주제설교 기능 통합)"},
        {"id": "expository", "name": "강해설교", "description": "본문 해설 중심 설교"},
    ]


__all__ = [
    'ThreePointsStyle',
    'TopicalStyle',
    'ExpositoryStyle',
    'get_style',
    'get_style_info',
    'get_available_styles',
    'get_readability_guide',
    'STYLE_CLASSES',
    'READABILITY_GUIDE',
]


def get_readability_guide() -> str:
    """가독성 가이드 반환"""
    return READABILITY_GUIDE
