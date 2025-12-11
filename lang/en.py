# -*- coding: utf-8 -*-
"""
영어 설정 파일

영어 영상 생성에 필요한 모든 설정을 중앙 관리.
"""

# =============================================================================
# 1. 언어 기본 정보
# =============================================================================
LANG_CODE = 'en'
LANG_NAME = 'English'
LANG_NATIVE = 'English'

# 언어 감지: 한글/일본어가 없으면 영어로 판단 (기본값)
DETECTION_PATTERN = None  # 영어는 fallback이므로 별도 패턴 없음


# =============================================================================
# 2. 유튜브 메타데이터 생성 지침
# =============================================================================

# -----------------------------------------------------------------------------
# 2-1. 제목 규칙
# -----------------------------------------------------------------------------
YOUTUBE_TITLE = {
    'min_length': 40,           # 최소 글자수
    'max_length': 70,           # 최대 글자수
    'optimal_length': 55,       # 최적 글자수
    'must_include_number': True,  # 숫자 1개 이상 권장

    # 금지 단어
    'banned_words': [
        'subscribe', 'like', 'click',  # 광고성
        'shocking', 'insane', 'crazy',  # 과장
    ],

    # 가이드라인
    'guidelines': {
        'characteristics': [
            'Clear and concise',
            'Use power words',
            'Include numbers when relevant',
            'Create curiosity gap',
        ],
        'good_examples': [
            '5 Morning Habits That Changed My Life (Science-Backed)',
            'Why 90% of Small Businesses Fail in Year One',
            'The Real Reason You Can\'t Save Money (It\'s Not What You Think)',
        ],
        'bad_examples': [
            'OMG YOU WON\'T BELIEVE THIS INSANE THING!!!',  # 과장
            'Please Subscribe and Like This Video',          # 광고성
        ],
    },

    # 제목 스타일별 템플릿
    'styles': {
        'curiosity': 'The {adjective} Truth About {topic}',
        'number': '{number} {topic} That Will {benefit}',
        'question': 'Why {topic}? The Answer Will {reaction}',
        'how_to': 'How to {action} in {timeframe}',
    },
}

# -----------------------------------------------------------------------------
# 2-2. 설명란 규칙
# -----------------------------------------------------------------------------
YOUTUBE_DESCRIPTION = {
    'min_length': 300,          # 최소 글자수
    'max_length': 800,          # 최대 글자수
    'paragraph_count': (3, 5),  # 문단 수 (최소, 최대)

    # 설명란 구조 템플릿
    'structure': [
        '{hook}',               # 1. 후킹 문장 (1-2줄)
        '',                     # 빈 줄
        '{summary}',            # 2. 영상 요약 (3-5줄)
        '',                     # 빈 줄
        '{chapters}',           # 3. 챕터 (선택)
        '',                     # 빈 줄
        '{cta}',                # 4. CTA
        '',                     # 빈 줄
        '{hashtags}',           # 5. 해시태그
    ],

    # CTA 문구
    'cta_templates': [
        'If you found this helpful, please like and subscribe for more content!',
        'Don\'t forget to hit the bell icon to get notified of new uploads!',
        'Share your thoughts in the comments below!',
    ],
}

# -----------------------------------------------------------------------------
# 2-3. 태그 규칙
# -----------------------------------------------------------------------------
YOUTUBE_TAGS = {
    'count': (10, 20),          # 태그 개수 (최소, 최대)

    # 필수 태그 (항상 포함)
    'required': [
        'tips', 'advice', 'how to', 'tutorial',
        'explained', 'guide', 'lifestyle',
    ],

    # 카테고리별 추가 태그
    'by_category': {
        'health': ['health tips', 'wellness', 'fitness', 'healthy lifestyle'],
        'money': ['personal finance', 'money tips', 'saving money', 'budgeting'],
        'business': ['entrepreneur', 'business tips', 'startup', 'success'],
        'lifestyle': ['life hacks', 'productivity', 'self improvement'],
    },

    # 금지 태그
    'banned': ['ad', 'sponsored', 'promotion'],
}

# -----------------------------------------------------------------------------
# 2-4. 고정 댓글 규칙
# -----------------------------------------------------------------------------
YOUTUBE_PIN_COMMENT = {
    # 댓글 템플릿
    'templates': [
        'What would you have done in this situation? Let me know in the comments!',
        'Have you experienced something similar? Share your story below!',
        'What\'s your take on this? Drop a comment!',
    ],

    # CTA 키워드
    'cta_keywords': ['subscribe', 'like', 'notification', 'comment'],
}

# -----------------------------------------------------------------------------
# 2-5. 해시태그 규칙
# -----------------------------------------------------------------------------
YOUTUBE_HASHTAGS = {
    'count': (3, 5),            # 해시태그 개수 (설명란 상단)
    'max_length': 30,           # 해시태그 최대 길이

    # 기본 해시태그
    'default': ['#tips', '#howto', '#guide'],
}


# =============================================================================
# 3. 자막 설정
# =============================================================================
SUBTITLE = {
    # 자막 길이 설정
    'max_chars_per_line': 25,   # 한 줄 최대 글자 수 (영어는 단어가 길어서)
    'max_lines': 2,             # 최대 줄 수
    'max_chars_total': 60,      # 총 최대 글자 수 (GPT 분리용)

    # 자막 타이밍
    'min_duration': 1.0,        # 최소 표시 시간 (초)
    'max_duration': 5.0,        # 최대 표시 시간 (초)
    'chars_per_second': 15,     # 초당 글자 수 (영어는 빠르게)

    # 자막 스타일 (ASS 형식)
    'style': {
        'font_name': 'Arial',               # 기본 영어 폰트
        'font_size': 22,                    # ASS 크기
        'font_size_burn': 44,               # burn-in 크기
        'primary_color': '&H00FFFF',        # 노란색 (BGR)
        'outline_color': '&H00000000',      # 검은색 테두리
        'back_color': '&H80000000',         # 반투명 검은 배경
        'border_style': 1,                  # 테두리 + 그림자
        'outline': 4,                       # 테두리 두께
        'shadow': 2,                        # 그림자
        'margin_v': 40,                     # 하단 여백
        'bold': 1,                          # 볼드
    },

    # 문장 분할 패턴 (영어)
    'split_patterns': [
        ', ',     # 쉼표
        '. ',     # 마침표
        ' and ',  # 접속사
        ' but ',  # 접속사
        ' or ',   # 접속사
        ' so ',   # 접속사
        ' because ', # 접속사
        ' when ',    # 접속사
        ' if ',      # 접속사
    ],

    # 문장 종료 패턴
    'end_patterns': [
        '.', '!', '?', '...', '.',
    ],

    # 구두점 (자막 분리용)
    'punctuation': ',.!? ',
}


def get_subtitle_ass_style():
    """ASS 자막 스타일 문자열 반환 (FFmpeg에서 직접 사용)"""
    s = SUBTITLE['style']
    return (
        f"FontName={s['font_name']},FontSize={s['font_size']},"
        f"PrimaryColour={s['primary_color']},"
        f"OutlineColour={s['outline_color']},BackColour={s['back_color']},"
        f"BorderStyle={s['border_style']},Outline={s['outline']},"
        f"Shadow={s['shadow']},MarginV={s['margin_v']},Bold={s['bold']}"
    )


# =============================================================================
# 4. TTS 음성 설정
# =============================================================================
TTS = {
    'language_code': 'en-US',

    # 음성 선택
    'voices': {
        'male': 'en-US-Neural2-D',      # 남성 (고품질)
        'female': 'en-US-Neural2-F',    # 여성 (고품질)
    },
    'default_voice': 'en-US-Neural2-D',  # 기본: 남성
    'fallback_voice': 'en-US-Wavenet-D', # 대체 음성

    # 음성 설정
    'speaking_rate': 1.0,       # 말하기 속도 (표준)
    'pitch': 0.0,               # 음높이 조절

    # 비용 (100만 글자당)
    'cost_per_million_chars': {
        'neural2': 16.0,        # $16/100만 글자
        'wavenet': 4.0,         # $4/100만 글자
    },
}


# =============================================================================
# 5. 아웃트로 설정
# =============================================================================
OUTRO = {
    'duration': 5,              # 아웃트로 길이 (초)
    'resolution': (1280, 720),  # 해상도
    'fps': 24,                  # 프레임레이트

    # 배경 색상 (그라데이션)
    'background_color': '0x1a1a2e',

    # 텍스트 설정
    'texts': [
        {
            'text': 'Thanks for watching!',
            'font_size': 44,
            'color': 'white',
            'y_offset': -70,    # 중앙 기준 Y 오프셋
        },
        {
            'text': 'Like & Subscribe for more',
            'font_size': 34,
            'color': 'yellow',
            'y_offset': 15,
        },
        {
            'text': 'Hit the bell for notifications',
            'font_size': 28,
            'color': '#aaaaaa',
            'y_offset': 80,
        },
    ],

    # 페이드 효과
    'fade_in': 0.5,             # 페이드 인 (초)
    'fade_out': 0.5,            # 페이드 아웃 (초)
}


# =============================================================================
# 6. 화면 폰트 설정
# =============================================================================
FONTS = {
    # 기본 폰트 (영어 전체에서 사용)
    'default': 'Pretendard-Bold.ttf',
    'default_name': 'Arial',  # ASS 자막용 폰트 이름 (시스템 폰트)

    # 폰트 우선순위 (첫 번째부터 시도)
    'priority': [
        'Pretendard-Bold.ttf',              # 기본
        'Pretendard-SemiBold.ttf',          # 대체
    ],

    # 시스템 폰트 경로 (fonts/ 폴더에 없을 때)
    'system_paths': [
        '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf',
        '/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf',
    ],

    # 용도별 폰트 설정
    'subtitle': {
        'name': 'Arial',
        'file': 'Pretendard-Bold.ttf',
        'size': 22,
    },
    'thumbnail': {
        'name': 'Arial',
        'file': 'Pretendard-Bold.ttf',
        'size': 56,
    },
    'overlay': {
        'name': 'Arial',
        'file': 'Pretendard-Bold.ttf',
        'size': 36,
    },
    'outro': {
        'name': 'Arial',
        'file': 'Pretendard-Bold.ttf',
        'sizes': [44, 34, 28],
    },
    'lower_third': {
        'name': 'Arial',
        'file': 'Pretendard-Bold.ttf',
        'size': 28,
    },
    'news_ticker': {
        'name': 'Arial',
        'file': 'Pretendard-Bold.ttf',
        'size': 24,
    },
}


# =============================================================================
# 7. 썸네일 텍스트 설정
# =============================================================================
THUMBNAIL_TEXT = {
    'main': {
        'max_chars': 15,         # 메인 텍스트 최대 글자 (큰 글씨)
        'font_size': 72,
        'examples': ['THE MOMENT', 'SHOCKING TRUTH', 'GAME CHANGER'],
    },
    'sub': {
        'max_chars': 40,         # 서브 텍스트 최대 글자 (작은 글씨)
        'font_size': 36,
        'examples': ['One decision changed everything', 'You won\'t believe what happened next'],
    },

    # 가이드라인
    'guidelines': {
        'font_contrast': 'high',
        'avoid': [
            'too much text',
            'small font size',
            'low contrast colors',
        ],
        'good_examples': [
            'THE TRUTH',      # 9 chars
            'EXPOSED',        # 7 chars
            'FINALLY',        # 7 chars
        ],
        'bad_examples': [
            'THIS IS THE MOST SHOCKING THING EVER THAT YOU WILL NOT BELIEVE',  # too long
        ],
    },
}


# =============================================================================
# 8. 이미지 프롬프트 설정
# =============================================================================
IMAGE_PROMPT = {
    # 서양인 인물 프롬프트 프리픽스
    'person_prefix': (
        "Western person with Caucasian ethnicity, "
        "Western facial features"
    ),

    # 서양 배경 키워드
    'background_keywords': [
        'modern apartment', 'American street', 'European cafe',
        'office building', 'suburban house', 'city skyline',
    ],

    # 스타일 키워드
    'style_keywords': [
        'cinematic Western drama style',
        'professional photography',
        '8k resolution',
    ],

    # 웹툰/만화 스타일
    'webtoon_style': 'Western comic/illustration style',
    'character_nationality': 'Western',
    'character_desc': 'Western man or woman',
}


# =============================================================================
# 9. 뉴스 스타일 설정
# =============================================================================
NEWS_STYLE = {
    # 뉴스 프리픽스 (제목 앞에 붙는 키워드)
    'prefixes': [
        'Breaking:',    # 속보
        'Issue:',       # 이슈
        'Key:',         # 핵심
        'Spotlight:',   # 스포트라이트
        'Trending:',    # 트렌딩
    ],

    # 뉴스 스타일 이미지 프롬프트
    'thumbnail_prompt': (
        "Western TV news broadcast style, professional anchor setting, "
        "bold headline text, news studio background"
    ),
}


# =============================================================================
# 헬퍼 함수
# =============================================================================

def get_font_path(usage='subtitle'):
    """용도에 맞는 폰트 경로 반환"""
    import os

    font_info = FONTS.get(usage, FONTS['subtitle'])
    font_file = font_info.get('file', FONTS['default'])

    # 프로젝트 fonts 폴더에서 찾기
    project_path = f"fonts/{font_file}"
    if os.path.exists(project_path):
        return project_path

    # 우선순위 폰트에서 찾기
    for font in FONTS['priority']:
        path = f"fonts/{font}"
        if os.path.exists(path):
            return path

    # 시스템 경로에서 찾기
    for path in FONTS['system_paths']:
        if os.path.exists(path):
            return path

    return f"fonts/{FONTS['priority'][0]}"


def get_voice(gender='male'):
    """성별에 맞는 TTS 음성 반환"""
    return TTS['voices'].get(gender, TTS['default_voice'])
