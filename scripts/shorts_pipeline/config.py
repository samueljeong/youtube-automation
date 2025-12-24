"""
쇼츠 파이프라인 설정

연예 뉴스 기반 60초 쇼츠 영상 자동 생성
- 9:16 세로 비율
- 실루엣 기반 이미지 (초상권 회피)
"""

# ============================================================
# 시트 설정
# ============================================================

SHEET_NAME = "SHORTS"

# 수집 영역 헤더
COLLECT_HEADERS = [
    "run_id",           # 수집 날짜 (YYYY-MM-DD)
    "category",         # 연예인/운동선수/국뽕
    "person",           # 인물명 (연예인/운동선수 등)
    "issue_type",       # 논란/열애/컴백/사건/근황/성과/자랑
    "news_title",       # 뉴스 제목
    "news_url",         # 뉴스 URL
    "news_summary",     # 뉴스 요약 (3줄)
    "silhouette_desc",  # 실루엣 특징 (헤어스타일, 포즈 등)
    "hook_text",        # 훅 문장 (첫 3초)
]

# 영상 자동화 헤더 (공통)
VIDEO_AUTOMATION_HEADERS = [
    "상태",             # 대기/처리중/완료/실패
    "대본",             # 60초 대본 (약 450자)
    "제목(GPT생성)",    # GPT가 생성한 쇼츠 제목
    "제목(입력)",       # 사용자 입력 제목
    "썸네일문구(입력)", # 사용자 입력 썸네일 문구
    "공개설정",         # public/private/unlisted
    "예약시간",         # YouTube 예약 공개 시간
    "플레이리스트ID",   # YouTube 플레이리스트 ID
    "음성",             # TTS 음성 설정
    "영상URL",          # 업로드된 YouTube URL
    "비용",             # 생성 비용
    "에러메시지",       # 실패 시 에러
    "작업시간",         # 파이프라인 실행 시간
]

# 전체 헤더
ALL_HEADERS = COLLECT_HEADERS + VIDEO_AUTOMATION_HEADERS


# ============================================================
# 쇼츠 영상 설정
# ============================================================

# 영상 크기 (9:16 세로)
VIDEO_WIDTH = 720
VIDEO_HEIGHT = 1280
VIDEO_SIZE = f"{VIDEO_WIDTH}x{VIDEO_HEIGHT}"

# 영상 길이 (40-60초 권장)
MIN_DURATION_SECONDS = 40
MAX_DURATION_SECONDS = 60
TARGET_DURATION_SECONDS = 50  # 최적 길이

# 씬 설정
DEFAULT_SCENE_COUNT = 8  # 마지막 씬은 무한루프 연결용
SCENE_DURATION_SECONDS = TARGET_DURATION_SECONDS / DEFAULT_SCENE_COUNT  # 약 6.25초

# TTS 설정
# 한국어 기준: 약 7.5자/초 → 50초 = 375자
TARGET_SCRIPT_LENGTH = 380
MIN_SCRIPT_LENGTH = 300  # 40초
MAX_SCRIPT_LENGTH = 450  # 60초
CHARS_PER_SECOND = 7.5

# 훅 설정 (첫 3초)
HOOK_DURATION_SECONDS = 3
HOOK_MAX_CHARS = 25  # 첫 3초에 25자 이내


# ============================================================
# 카테고리 및 이슈 타입
# ============================================================

# 콘텐츠 카테고리
CONTENT_CATEGORIES = [
    "연예인",   # 연예인/아이돌/배우
    "운동선수", # 스포츠 선수
    "국뽕",     # 국가 자랑거리/한류/K-문화
]

# 이슈 타입 (카테고리별)
ISSUE_TYPES = {
    "연예인": [
        "논란",     # 갑질, 학폭, 사생활 등
        "열애",     # 열애설, 결혼, 이혼
        "컴백",     # 컴백, 신곡, 앨범
        "사건",     # 사고, 소송, 구속
        "근황",     # 근황, 활동, 복귀
    ],
    "운동선수": [
        "성과",     # 우승, 기록, 메달
        "부상",     # 부상, 복귀
        "이적",     # 이적, 계약
        "논란",     # 도핑, 승부조작 등
        "근황",     # 근황, 활동
    ],
    "국뽕": [
        "자랑",     # 세계 1등, 최초, 최고
        "성과",     # 수상, 인정
        "반응",     # 외국인 반응, 해외 반응
        "문화",     # K-문화, 한류
    ],
}

# 모든 이슈 타입 (flat list for backward compatibility)
ALL_ISSUE_TYPES = list(set(
    issue for types in ISSUE_TYPES.values() for issue in types
))


# ============================================================
# 이미지 프롬프트 템플릿
# ============================================================

# 씬별 배경 스타일
BACKGROUND_STYLES = {
    "hook": "Breaking news style dark red gradient background, shattered glass effect, dramatic spotlight, urgent atmosphere",
    "explain": "Modern studio background, soft blue lighting, professional news setting",
    "reveal": "Dark moody background, dramatic shadows, tension atmosphere",
    "reaction": "Social media style background, floating comment bubbles, digital glow",
    "impact": "Empty TV studio with turned off lights, melancholic atmosphere",
    "conclusion": "Broken mirror reflecting fragmented light, symbolic composition",
    "cta": "Subscribe button style, glowing red accent, clean dark background",
}

# 실루엣 프롬프트 템플릿
SILHOUETTE_TEMPLATE = """
{background_style},
black silhouette of {silhouette_desc},
dramatic spotlight from above casting long shadow,
Korean entertainment news style,
NO facial features visible - only dark shadow outline,
large empty space at top and bottom for Korean text overlay,
4K quality, cinematic lighting
"""

# 배경 전용 프롬프트 (실루엣 없는 씬용)
BACKGROUND_ONLY_TEMPLATE = """
{background_style},
NO people or human figures,
large empty space for Korean text overlay,
4K quality, cinematic composition,
Korean news broadcast style
"""


# ============================================================
# 실루엣 라이브러리 (카테고리별)
# ============================================================

# 연예인 실루엣 특징
CELEBRITY_SILHOUETTES = {
    "박나래": "female comedian with short wavy hair holding a microphone in energetic pose",
    "유재석": "tall slim male figure with signature hand gesture, wearing suit",
    "조세호": "slim male figure with glasses, formal attire, standing pose",
    "이영지": "young female figure with long straight hair, hip-hop style pose",
    "아이유": "petite female figure with long wavy hair, elegant standing pose",
    "뉴진스": "group of five young female figures in dynamic dance pose",
    "BTS": "group of male figures in synchronized dance formation",
    # 기본값
    "default_male": "male figure in casual standing pose",
    "default_female": "female figure in casual standing pose",
}

# 운동선수 실루엣 특징
ATHLETE_SILHOUETTES = {
    # 축구
    "손흥민": "athletic male soccer player in running pose with ball, spiky hair",
    "이강인": "young male soccer player in dribbling pose, short hair",
    "황희찬": "muscular male soccer player in celebration pose with arms raised",
    "김민재": "tall athletic male defender in standing pose",
    # 야구
    "류현진": "stocky male baseball pitcher in throwing motion",
    "오타니 쇼헤이": "tall male baseball player in batting stance",
    "이정후": "male baseball player in batting pose, helmet",
    # 배구
    "김연경": "tall athletic female volleyball player in spiking pose",
    # 피겨
    "김연아": "elegant female figure skater in graceful pose",
    # 골프
    "고진영": "female golfer in swing pose with club",
    "박인비": "female golfer in putting stance",
    # 기본값
    "default_athlete": "athletic figure in sports pose",
}

# 국뽕용 실루엣 (상징적 이미지)
KOREA_PRIDE_SILHOUETTES = {
    "default": "Korean traditional elements, Taegeuk pattern, modern Korea skyline silhouette",
    "technology": "futuristic Korean tech cityscape, semiconductor chip shapes",
    "culture": "traditional Korean hanbok silhouette mixed with modern K-pop stage",
    "sports": "Korean athlete with gold medal, national flag waving",
    "food": "Korean cuisine elements, bibimbap bowl, kimchi jar silhouettes",
}

# 통합 실루엣 라이브러리
ALL_SILHOUETTES = {
    **CELEBRITY_SILHOUETTES,
    **ATHLETE_SILHOUETTES,
}


# ============================================================
# 대본 구조 템플릿
# ============================================================

SCRIPT_STRUCTURE = """
[씬 1] 0-3초 - ⚡ 킬러 훅 (스크롤 멈추게)
[씬 2] 3-10초 - 상황 설명 (무슨 일?)
[씬 3] 10-18초 - 핵심 폭로 (가장 충격적인 내용)
[씬 4] 18-26초 - 반응 (본인/소속사)
[씬 5] 26-34초 - 여론 (네티즌 반응)
[씬 6] 34-42초 - 파장 (어떤 영향?)
[씬 7] 42-50초 - 반전/추가 정보 (새로운 사실)
[씬 8] 50-55초 - 🔄 루프 연결 (첫 씬과 자연스럽게 연결)

※ 무한루프: 마지막 씬이 첫 씬과 연결되어 시청자가 다시 보게 만듦
※ CTA 금지: 구독 유도하면 루프 끊김
"""

# 킬러 훅 템플릿 (첫 3초) - {person}은 인물명으로 대체됨
HOOK_TEMPLATES = {
    # 연예인용
    "논란": [
        "{person}, 결국 이렇게 됐습니다",
        "{person}의 충격적인 진실",
        "아무도 몰랐던 {person}의 실체",
        "{person}, 24시간 만에 모든 게 바뀌었습니다",
    ],
    "열애": [
        "{person}의 비밀 연인이 공개됐습니다",
        "{person}, 10년 만에 처음입니다",
        "팬들이 울었습니다. {person}가...",
    ],
    "컴백": [
        "{person}가 돌아옵니다. 이번엔 다릅니다",
        "업계가 발칵 뒤집혔습니다",
        "{person}의 역대급 컴백",
    ],
    "사건": [
        "{person}에게 무슨 일이 생겼습니다",
        "모두가 충격받았습니다",
        "{person}, 긴급 상황입니다",
    ],
    "근황": [
        "{person}, 요즘 이렇게 지냅니다",
        "오랜만에 나타난 {person}",
        "{person}의 놀라운 변화",
    ],
    # 운동선수용
    "성과": [
        "{person}, 역대급 기록 세웠습니다",
        "{person}이 해냈습니다",
        "전세계가 주목합니다. {person}의 위업",
        "{person}, 대한민국 최초입니다",
    ],
    "부상": [
        "{person}에게 안타까운 소식입니다",
        "{person}, 시즌 아웃 위기입니다",
        "충격... {person}이 쓰러졌습니다",
    ],
    "이적": [
        "{person}, 깜짝 이적 발표",
        "{person}의 새 팀이 공개됐습니다",
        "역대급 계약... {person}의 몸값",
    ],
    # 국뽕용
    "자랑": [
        "한국이 또 해냈습니다",
        "세계가 놀란 한국의 저력",
        "대한민국, 세계 1위 등극",
        "역시 한국... 전세계 1등",
    ],
    "반응": [
        "외국인들이 충격받았습니다",
        "한국에 온 외국인들... 이게 뭐죠?",
        "전세계가 주목하는 한국",
        "해외에서 난리 난 한국 소식",
    ],
    "문화": [
        "K-문화, 전세계를 접수했습니다",
        "한류, 이제 세계 표준입니다",
        "전세계가 따라하는 한국 트렌드",
    ],
}

# 무한루프 연결 문구 (마지막 씬)
LOOP_ENDINGS = [
    "그리고 결국... 이렇게 됐습니다",
    "그래서 지금... 상황은 이렇습니다",
    "그리고 이 사건은...",
    "결국 {person}는...",
]


# ============================================================
# 댓글 유도 기술 (Comment Engagement)
# ============================================================

# 댓글 유도 문구 템플릿 (대본에 자연스럽게 삽입)
COMMENT_TRIGGERS = {
    # 의견 요청형
    "opinion": [
        "여러분 생각은 어떠세요?",
        "이거 진짜일까요?",
        "여러분이라면 어떻게 하셨을까요?",
    ],
    # 투표형 (A vs B)
    "vote": [
        "찬성이면 👍, 반대면 👎",
        "믿는다면 1, 아니면 2",
        "응원하면 ❤️, 실망이면 💔",
    ],
    # 경험 공유형
    "share": [
        "비슷한 경험 있으신 분?",
        "혹시 직접 본 분 계신가요?",
    ],
    # 예측형
    "predict": [
        "앞으로 어떻게 될까요?",
        "결과가 어떻게 될지... 댓글로 예측해보세요",
    ],
    # 논쟁 유발형 (주의해서 사용)
    "debate": [
        "이건 좀 논란이 될 것 같은데...",
        "팬들 사이에서도 의견이 갈리고 있습니다",
    ],
}

# 댓글 유도 삽입 위치 (씬 번호)
COMMENT_TRIGGER_SCENES = [5, 7]  # 씬5(여론), 씬7(반전) 후에 삽입


# ============================================================
# 사실 검증 규칙 (Fact Check)
# ============================================================

FACT_CHECK_RULES = """
## 사실 검증 규칙 (필수!)

1. **출처 명시**: 뉴스 기사 내용만 사용, 추측 금지
2. **확인된 사실만**: "~라고 한다", "~로 알려졌다" 등 불확실 표현 사용
3. **비방/명예훼손 금지**: 인신공격, 루머 확대 재생산 금지
4. **법적 리스크 회피**:
   - 유죄 확정 전 "혐의", "의혹" 표현 사용
   - "범인", "가해자" 단정 금지
   - 피해자 신상 노출 금지
5. **균형 잡힌 시각**: 한쪽 입장만 대변하지 않음

## 금지 표현
- "확실히 ~이다" (단정)
- "~임이 밝혀졌다" (확인 안 된 경우)
- "모든 사람들이 ~" (일반화)
- 비속어, 혐오 표현
"""


# ============================================================
# BGM 설정 (쇼츠용)
# ============================================================

# 이슈 타입별 기본 BGM 분위기
SHORTS_BGM_MOODS = {
    # 연예인
    "논란": "tense",       # 긴장감
    "열애": "romantic",    # 로맨틱
    "컴백": "upbeat",      # 신나는
    "사건": "dramatic",    # 극적
    "근황": "calm",        # 차분

    # 운동선수
    "성과": "epic",        # 웅장한
    "부상": "sad",         # 슬픈
    "이적": "inspiring",   # 영감

    # 국뽕
    "자랑": "epic",        # 웅장한
    "반응": "upbeat",      # 신나는
    "문화": "inspiring",   # 영감

    # 기본
    "default": "dramatic",
}

# BGM 볼륨 설정
SHORTS_BGM_CONFIG = {
    "volume": 0.15,        # 배경음악 볼륨 (TTS 대비)
    "fade_in": 1.0,        # 시작 페이드인 (초)
    "fade_out": 2.0,       # 끝 페이드아웃 (초)
    "ducking": True,       # TTS 구간에서 볼륨 낮추기
    "ducking_ratio": 0.5,  # 덕킹 시 볼륨 비율
}

# 사용 가능한 BGM 분위기 목록
BGM_MOOD_OPTIONS = [
    "hopeful",    # 희망적
    "sad",        # 슬픈
    "tense",      # 긴장감
    "dramatic",   # 극적
    "calm",       # 차분한
    "inspiring",  # 영감
    "mysterious", # 신비로운
    "nostalgic",  # 향수
    "epic",       # 웅장한
    "romantic",   # 로맨틱
    "comedic",    # 코믹
    "horror",     # 공포
    "upbeat",     # 신나는
]


# ============================================================
# 자막 스타일 (쇼츠용 - 세로 화면 최적화)
# ============================================================

SHORTS_SUBTITLE_STYLE = {
    # 기본 폰트 설정
    "font_name": "NanumSquareRoundEB",  # 나눔스퀘어라운드 ExtraBold
    "font_size": 48,                     # 큰 글씨 (모바일 가독성)
    "font_color": "#FFFFFF",             # 흰색

    # 테두리/외곽선 (가독성 향상)
    "outline_color": "#000000",          # 검정 테두리
    "outline_width": 3,                  # 두꺼운 테두리

    # 그림자 효과
    "shadow_enabled": True,
    "shadow_color": "#000000",
    "shadow_offset": 2,

    # 위치 (9:16 세로 화면 기준)
    "position": "bottom",                # 하단 배치
    "margin_bottom": 150,                # 바텀 여백 (네비게이션 바 피하기)
    "margin_horizontal": 40,             # 좌우 여백

    # 애니메이션
    "fade_in": 0.1,                      # 페이드인 (초)
    "fade_out": 0.1,                     # 페이드아웃 (초)

    # 한 줄 최대 글자 수 (자동 줄바꿈)
    "max_chars_per_line": 12,            # 세로 화면이라 짧게
}

# 강조 자막 스타일 (훅, 핵심 문장용)
SHORTS_EMPHASIS_STYLE = {
    "font_size": 56,                     # 더 큰 글씨
    "font_color": "#FFFF00",             # 노란색
    "outline_color": "#FF0000",          # 빨간 테두리
    "outline_width": 4,
    "position": "center",                # 중앙 배치
    "scale_effect": True,                # 확대 효과
}

# 이슈 타입별 자막 강조 색상
SUBTITLE_HIGHLIGHT_COLORS = {
    "논란": "#FF4444",      # 빨강
    "열애": "#FF69B4",      # 핑크
    "컴백": "#00FF00",      # 초록
    "사건": "#FF0000",      # 진한 빨강
    "성과": "#FFD700",      # 금색
    "자랑": "#0080FF",      # 파랑
    "반응": "#FFA500",      # 주황
    "default": "#FFFF00",   # 노랑
}

# 키워드 강조 설정
KEYWORD_HIGHLIGHT_CONFIG = {
    "enabled": True,
    "keywords": [
        # 감정/반응
        "충격", "폭로", "논란", "결국", "드디어", "역대급",
        # 숫자/시간
        "24시간", "10년", "처음", "최초", "1위",
        # 상태
        "확정", "공식", "긴급", "속보",
    ],
    "style": {
        "color": "#FF0000",
        "bold": True,
        "scale": 1.2,
    }
}


# ============================================================
# Ken Burns 효과 (이미지 확대/이동 애니메이션)
# ============================================================

SHORTS_KEN_BURNS = {
    "enabled": True,

    # 확대 설정
    "zoom": {
        "enabled": True,
        "start_scale": 1.0,     # 시작 크기 (1.0 = 100%)
        "end_scale": 1.15,      # 끝 크기 (1.15 = 115% - 15% 확대)
        "easing": "ease-out",   # 가속도: ease-in, ease-out, linear
    },

    # 이동 설정 (패닝)
    "pan": {
        "enabled": True,
        "max_offset_x": 50,     # 최대 좌우 이동 (픽셀)
        "max_offset_y": 30,     # 최대 상하 이동 (픽셀)
    },

    # 씬별 방향 패턴 (자연스러운 변화)
    # zoom_in: 확대, zoom_out: 축소, pan_left/right/up/down: 이동
    "scene_patterns": {
        1: "zoom_in",           # 훅: 긴장감 있게 확대
        2: "pan_right",         # 설명: 오른쪽으로 이동
        3: "zoom_in",           # 폭로: 집중 확대
        4: "pan_left",          # 반응: 왼쪽으로 이동
        5: "zoom_out",          # 여론: 전체 보기
        6: "pan_up",            # 파장: 위로 이동
        7: "zoom_in",           # 반전: 다시 집중
        8: "zoom_out",          # 루프: 축소하며 마무리
    },

    # 이슈 타입별 강도 조절
    "intensity_by_issue": {
        "논란": 1.2,            # 더 강하게 (긴장감)
        "사건": 1.2,
        "성과": 1.1,            # 약간 강하게
        "열애": 0.9,            # 부드럽게
        "근황": 0.8,            # 차분하게
        "default": 1.0,
    },
}

# FFmpeg zoompan 필터 프리셋
FFMPEG_ZOOMPAN_PRESETS = {
    "zoom_in": {
        # 1.0 → 1.15 확대
        "z": "'min(zoom+0.0015,1.15)'",
        "x": "'iw/2-(iw/zoom/2)'",
        "y": "'ih/2-(ih/zoom/2)'",
    },
    "zoom_out": {
        # 1.15 → 1.0 축소
        "z": "'if(eq(on,1),1.15,max(zoom-0.0015,1.0))'",
        "x": "'iw/2-(iw/zoom/2)'",
        "y": "'ih/2-(ih/zoom/2)'",
    },
    "pan_right": {
        "z": "1.1",
        "x": "'min(on*2,100)'",  # 왼쪽에서 오른쪽으로
        "y": "'ih/2-(ih/zoom/2)'",
    },
    "pan_left": {
        "z": "1.1",
        "x": "'max(100-on*2,0)'",  # 오른쪽에서 왼쪽으로
        "y": "'ih/2-(ih/zoom/2)'",
    },
    "pan_up": {
        "z": "1.1",
        "x": "'iw/2-(iw/zoom/2)'",
        "y": "'max(100-on*2,0)'",  # 아래에서 위로
    },
    "pan_down": {
        "z": "1.1",
        "x": "'iw/2-(iw/zoom/2)'",
        "y": "'min(on*2,100)'",  # 위에서 아래로
    },
}


# ============================================================
# GPT 프롬프트
# ============================================================

SCRIPT_GENERATION_PROMPT = """
당신은 연예 뉴스 쇼츠 전문 작가입니다.

다음 뉴스를 60초 쇼츠 대본으로 변환하세요.

## 뉴스 정보
- 연예인: {celebrity}
- 이슈 유형: {issue_type}
- 뉴스 제목: {news_title}
- 뉴스 요약: {news_summary}

## 대본 규칙
1. 총 450자 내외 (60초 TTS 기준)
2. 9개 씬으로 구성
3. 첫 문장은 충격적인 훅으로 시작
4. 마지막은 "구독과 좋아요" CTA로 마무리
5. 사실 기반, 추측/비방 금지
6. 짧고 임팩트 있는 문장

## 출력 형식 (JSON)
{{
    "title": "쇼츠 제목 (30자 이내, 이모지 포함)",
    "scenes": [
        {{
            "scene_number": 1,
            "duration": "0-5초",
            "narration": "훅 문장",
            "image_prompt": "이미지 생성 프롬프트 (영어)",
            "text_overlay": "화면에 표시할 텍스트"
        }},
        ...
    ],
    "total_chars": 450,
    "hashtags": ["#연예", "#이슈", ...]
}}
"""


# ============================================================
# RSS 피드 설정
# ============================================================

# 매일 수집할 뉴스 개수
DAILY_NEWS_LIMIT = 5

# 뉴스 선택 방식
# "hottest": 모든 카테고리에서 가장 핫한 뉴스 순으로 선택 (중복 제거)
# "balanced": 카테고리별 균등 분배
# "priority": 연예인 우선
NEWS_SELECTION_MODE = "hottest"

# 중복 판단 기준 (같은 인물 + 같은 이슈 = 중복)
DUPLICATE_CHECK_HOURS = 24  # 24시간 내 동일 인물 중복 제거

# 카테고리별 RSS 피드
RSS_FEEDS = {
    "연예인": [
        {
            "name": "celebrity_issue",
            "url": "https://news.google.com/rss/search?q=연예인+논란&hl=ko&gl=KR&ceid=KR:ko",
        },
        {
            "name": "celebrity_news",
            "url": "https://news.google.com/rss/search?q=연예인+뉴스&hl=ko&gl=KR&ceid=KR:ko",
        },
        {
            "name": "kpop_idol",
            "url": "https://news.google.com/rss/search?q=아이돌+이슈&hl=ko&gl=KR&ceid=KR:ko",
        },
    ],
    "운동선수": [
        {
            "name": "sports_star",
            "url": "https://news.google.com/rss/search?q=운동선수+이슈&hl=ko&gl=KR&ceid=KR:ko",
        },
        {
            "name": "kbl_kbo",
            "url": "https://news.google.com/rss/search?q=프로야구+프로농구+선수&hl=ko&gl=KR&ceid=KR:ko",
        },
        {
            "name": "soccer_player",
            "url": "https://news.google.com/rss/search?q=축구+선수+이적+활약&hl=ko&gl=KR&ceid=KR:ko",
        },
        {
            "name": "athlete_news",
            "url": "https://news.google.com/rss/search?q=손흥민+김연경+류현진&hl=ko&gl=KR&ceid=KR:ko",
        },
    ],
    "국뽕": [
        {
            "name": "korea_pride",
            "url": "https://news.google.com/rss/search?q=한국+세계+1위+최초&hl=ko&gl=KR&ceid=KR:ko",
        },
        {
            "name": "hallyu_kculture",
            "url": "https://news.google.com/rss/search?q=한류+K문화+해외반응&hl=ko&gl=KR&ceid=KR:ko",
        },
        {
            "name": "foreigner_reaction",
            "url": "https://news.google.com/rss/search?q=외국인+한국+반응&hl=ko&gl=KR&ceid=KR:ko",
        },
        {
            "name": "korea_recognition",
            "url": "https://news.google.com/rss/search?q=한국+해외+인정+수상&hl=ko&gl=KR&ceid=KR:ko",
        },
    ],
}

# 레거시 호환용 (이전 코드와의 호환성 유지)
ENTERTAINMENT_RSS_FEEDS = RSS_FEEDS["연예인"]


# ============================================================
# 비용 설정
# ============================================================

COSTS = {
    "gpt_script": 0.03,          # 대본 생성 (GPT-4o)
    "gemini_image": 0.05,        # 이미지 1장 (Gemini Pro)
    "tts_per_char": 0.000016,    # TTS (Google Neural2)
}

def estimate_cost(scene_count: int = 9, script_length: int = 450) -> float:
    """예상 비용 계산"""
    image_cost = scene_count * COSTS["gemini_image"]
    tts_cost = script_length * COSTS["tts_per_char"]
    total = COSTS["gpt_script"] + image_cost + tts_cost
    return round(total, 3)

# 예상 비용: $0.03 + (9 * $0.05) + (450 * $0.000016) = $0.487
