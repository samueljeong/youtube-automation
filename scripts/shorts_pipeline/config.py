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
    "celebrity",        # 연예인명
    "issue_type",       # 논란/열애/컴백/사건/근황
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

# 영상 길이
MAX_DURATION_SECONDS = 60

# 씬 설정
DEFAULT_SCENE_COUNT = 9
SCENE_DURATION_SECONDS = 60 / DEFAULT_SCENE_COUNT  # 약 6.7초

# TTS 설정
# 한국어 기준: 약 7.5자/초 → 60초 = 450자
TARGET_SCRIPT_LENGTH = 450
CHARS_PER_SECOND = 7.5


# ============================================================
# 이슈 타입
# ============================================================

ISSUE_TYPES = [
    "논란",     # 갑질, 학폭, 사생활 등
    "열애",     # 열애설, 결혼, 이혼
    "컴백",     # 컴백, 신곡, 앨범
    "사건",     # 사고, 소송, 구속
    "근황",     # 근황, 활동, 복귀
]


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
# 연예인 실루엣 라이브러리
# ============================================================

# 유명 연예인 실루엣 특징
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


# ============================================================
# 대본 구조 템플릿
# ============================================================

SCRIPT_STRUCTURE = """
[씬 1] 0-5초 - 훅 (충격적인 첫 문장)
[씬 2] 5-12초 - 상황 설명
[씬 3] 12-20초 - 핵심 폭로/사건
[씬 4] 20-27초 - 반응/반격
[씬 5] 27-35초 - 여론/댓글 반응
[씬 6] 35-42초 - 영향/파장
[씬 7] 42-50초 - 업계/주변 반응
[씬 8] 50-55초 - 결론/전망
[씬 9] 55-60초 - CTA (구독 유도)
"""


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

ENTERTAINMENT_RSS_FEEDS = [
    {
        "name": "naver_entertain",
        "url": "https://news.google.com/rss/search?q=연예+뉴스&hl=ko&gl=KR&ceid=KR:ko",
    },
    {
        "name": "celebrity_issue",
        "url": "https://news.google.com/rss/search?q=연예인+논란&hl=ko&gl=KR&ceid=KR:ko",
    },
    {
        "name": "kpop_news",
        "url": "https://news.google.com/rss/search?q=아이돌+뉴스&hl=ko&gl=KR&ceid=KR:ko",
    },
]


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
