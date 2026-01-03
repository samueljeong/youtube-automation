"""
무협 파이프라인 설정
- 시리즈: 혈영 (Blood Shadow)
- 주인공: 무영
- 다중 음성 TTS 지원
"""

import os
from typing import Dict, List

# =====================================================
# 시리즈 설정
# =====================================================

SERIES_INFO = {
    "title": "혈영",
    "title_en": "Blood Shadow",
    "protagonist": "무영",
    "heroine": "설하",  # 절세미녀 여주인공
    "genre": "무협",
    "description": "노비 출신의 청년이 의문의 노인에게 절세무공을 전수받아 강호를 휩쓰는 이야기. 그의 곁에는 모두가 부러워하는 절세미녀 설하가 함께한다.",
    "youtube_channel_id": os.getenv("WUXIA_CHANNEL_ID", ""),
    "playlist_id": os.getenv("WUXIA_PLAYLIST_ID", ""),
}

# =====================================================
# 음성 매핑 (TTS Voice Map)
# =====================================================
# 형식: {태그명: TTS 음성 ID}
# 음성 종류:
#   - chirp3:* : Chirp3 모델 (기본)
#   - gemini:* : Gemini Flash 모델 (저렴)
#   - gemini:pro:* : Gemini Pro 모델 (고품질)

VOICE_MAP: Dict[str, str] = {
    # 나레이션 (남성, 깊고 차분한 톤)
    "나레이션": "chirp3:Charon",

    # 주인공들
    "무영": "gemini:Puck",           # 젊은 남성, 활기차고 친근한 톤
    "설하": "gemini:pro:Kore",       # ★ 절세미녀 여주인공, 부드럽고 우아한 톤 (Pro 고품질)
    "노인": "gemini:pro:Charon",     # 노인, 깊고 지혜로운 톤 (Pro 모델로 차별화)
    "각주": "chirp3:Fenrir",         # 남성 조연, 힘있고 웅장한 톤

    # 엑스트라 (성별 구분)
    "남자": "gemini:Charon",         # 남자 엑스트라
    "여자": "gemini:Kore",           # 여자 엑스트라

    # 특수 캐릭터 (확장용)
    "악역": "chirp3:Fenrir",         # 악역, 웅장하고 위협적
}

# 기본 음성 (태그가 없거나 매칭 안될 때)
DEFAULT_VOICE = "chirp3:Charon"

# =====================================================
# 스크립트 태그 형식
# =====================================================
# [태그] 대사 또는 나레이션
# 예: [나레이션] 무영이 고개를 들었다.
#     [무영] "이제 그만 가시죠."
#     [노인] "아직 멀었다, 젊은이."

SCRIPT_TAG_PATTERN = r'\[([^\]]+)\]\s*(.+?)(?=\[[^\]]+\]|$)'

# 주인공 태그 목록 (나레이터가 소개하는 캐릭터)
MAIN_CHARACTER_TAGS = ["무영", "설하", "노인", "각주", "악역"]

# 엑스트라 태그 목록 (나레이터 소개 없이 바로 대사)
EXTRA_TAGS = ["남자", "여자", "남자1", "남자2", "여자1", "여자2"]

# =====================================================
# 캐릭터 외모 설정 (이미지 프롬프트용)
# =====================================================
# ★ 씬 이미지 생성 시 캐릭터 일관성 유지를 위한 외모 설명
# ★ 영문으로 작성 (이미지 생성 모델용)

CHARACTER_APPEARANCES: Dict[str, str] = {
    # 주인공 - 무영
    "무영": (
        "young Korean man, 18 years old, sharp angular jawline, intense dark piercing eyes, "
        "messy black hair tied in a loose topknot, lean muscular build from hard labor, "
        "wearing worn gray hemp servant clothes (노비 복장), determined expression, "
        "subtle scars on hands from years of work"
    ),

    # 여주인공 - 설하 (절세미녀)
    "설하": (
        "breathtakingly beautiful Korean woman, early 20s, flawless porcelain skin, "
        "delicate graceful features, long flowing jet-black hair reaching her waist, "
        "elegant arched eyebrows, gentle almond-shaped eyes, "
        "wearing elegant white silk hanbok with subtle peach blossom embroidery, "
        "ethereal presence, moves with natural grace"
    ),

    # 스승 - 노인 (의문의 고수)
    "노인": (
        "elderly Korean martial arts master, 70s, long white beard flowing to mid-chest, "
        "wise penetrating eyes that seem to see through everything, deeply weathered face, "
        "wearing faded brown hemp martial arts robes, thin but radiates hidden power, "
        "calm serene expression, mysterious aura"
    ),

    # 각주 (조연 - 무영의 동료 노비)
    "각주": (
        "sturdy Korean man, mid 20s, broad shoulders, honest round face, "
        "short cropped black hair, friendly eyes, wearing worn servant clothes, "
        "calloused hands, loyal dependable appearance"
    ),

    # 악역 (일반 악역 템플릿)
    "악역": (
        "menacing martial artist, cold calculating eyes, sharp angular features, "
        "black or dark red martial arts robes with ornate patterns, "
        "arrogant stance, dangerous aura, carries a distinctive weapon"
    ),
}

# 이미지 스타일 설정 (일관된 화풍)
IMAGE_STYLE = {
    "base_style": (
        "Chinese martial arts wuxia illustration style, "
        "ink wash painting with vibrant accent colors, "
        "dramatic cinematic lighting, "
        "traditional East Asian aesthetic, "
        "16:9 aspect ratio, high detail"
    ),
    "action_style": (
        "dynamic action composition, motion blur effects, "
        "energy trails, dramatic poses"
    ),
    "emotional_style": (
        "intimate framing, soft lighting, "
        "focus on facial expressions and emotions"
    ),
    "landscape_style": (
        "wide panoramic shot, misty mountains, "
        "traditional Korean architecture, atmospheric perspective"
    ),
    "negative_prompt": (
        "text, letters, words, watermark, signature, "
        "modern elements, anime style, cartoon, "
        "low quality, blurry, deformed"
    ),
}

# =====================================================
# 대본 설정
# =====================================================

SCRIPT_CONFIG = {
    # 에피소드당 목표 글자수 (약 15분 영상)
    # 한국어 TTS 기준: 약 900자 ≈ 1분
    "target_chars": 13500,
    "min_chars": 12000,
    "max_chars": 15000,

    # 씬 설정
    "scenes_per_episode": 10,  # 에피소드당 씬 수 (10장)
    "chars_per_scene": 1350,   # 씬당 평균 글자수 (13500 / 10)

    # TTS 설정
    "speaking_rate": 0.9,  # 음성 속도
    "language": "ko-KR",
}

# =====================================================
# 에피소드 템플릿 (혈영 시리즈)
# =====================================================

EPISODE_TEMPLATES = {
    1: {
        "title": "운명의 시작",
        "summary": "노비 출신 청년 무영이 의문의 노인을 만나 절세무공의 비밀을 전수받게 되는 첫 번째 이야기",
        "key_events": [
            "무영의 비천한 신분과 고된 일상",
            "의문의 노인과의 만남",
            "노인의 시험과 무영의 선택",
            "무공 전수의 시작"
        ],
        "characters": ["무영", "노인", "각주"],
    },
    2: {
        "title": "첫 번째 도약",
        "summary": "노인의 가르침 아래 무영이 첫 무공을 익히고 새로운 세계를 보게 되는 이야기",
        "key_events": [
            "기초 내공 수련",
            "첫 무공 습득의 어려움",
            "돌파의 순간",
            "새로운 능력의 자각"
        ],
        "characters": ["무영", "노인"],
    },
    3: {
        "title": "강호에 발을 딛다",
        "summary": "수련을 마친 무영이 처음으로 강호의 현실을 마주하게 되는 이야기",
        "key_events": [
            "노인과의 이별",
            "첫 강호 출두",
            "불의와의 조우",
            "첫 번째 결전"
        ],
        "characters": ["무영", "노인", "악역"],
    },
    4: {
        "title": "눈 속의 절세미인",
        "summary": "강호를 떠돌던 무영이 눈보라 속에서 쓰러진 절세미녀 설하를 구하게 되는 이야기",
        "key_events": [
            "눈보라 속 쓰러진 여인 발견",
            "설하와의 첫 만남",
            "설하를 노리는 자들의 습격",
            "무영의 실력 각성"
        ],
        "characters": ["무영", "설하", "악역"],
    },
    5: {
        "title": "빚진 은혜",
        "summary": "설하가 무영에게 목숨을 빚졌다며 따라다니기 시작하는 이야기. 무영은 무관심하지만 설하는 물러서지 않는다.",
        "key_events": [
            "설하의 신분 - 명문 세가의 영애",
            "설하의 결심 - 은혜를 갚을 때까지",
            "무영의 무관심과 냉담",
            "설하를 시기하는 강호인들"
        ],
        "characters": ["무영", "설하"],
    },
}

# =====================================================
# Google Sheets 설정
# =====================================================

SHEET_NAME = "혈영"  # 시트 탭 이름 (시리즈 제목)

# 수집 헤더 (무협 파이프라인 전용)
COLLECT_HEADERS = [
    "episode",          # EP001, EP002, ...
    "title",            # 에피소드 제목
    "summary",          # 에피소드 요약
    "characters",       # 등장 캐릭터 (쉼표 구분)
    "key_events",       # 주요 사건 (줄바꿈 구분)
    "prev_episode",     # 이전 에피소드 요약 (연결용)
    "next_preview",     # 다음 에피소드 예고
    "thumbnail_copy",   # 썸네일 문구
]

# 영상 자동화 헤더 (drama_server.py의 VIDEO_AUTOMATION_HEADERS와 동일)
VIDEO_AUTOMATION_HEADERS = [
    "상태",             # 대기/처리중/완료/실패
    "대본",             # 생성된 대본 (다중 음성 태그 포함)
    "인용링크",         # 유튜브 설명에 포함할 출처
    "제목(GPT생성)",    # 자동 생성 제목
    "제목(입력)",       # 수동 입력 제목
    "썸네일문구(입력)", # 수동 입력 썸네일
    "공개설정",         # public/private/unlisted
    "예약시간",         # YouTube 예약 공개 시간
    "플레이리스트ID",   # YouTube 플레이리스트
    "음성",             # TTS 음성 (다중 음성은 VOICE_MAP 자동 적용)
    "영상URL",          # 업로드된 URL
    "쇼츠URL",          # 쇼츠 URL
    "제목2",            # 대안 제목
    "제목3",            # 대안 제목
    "비용",             # 생성 비용
    "에러메시지",       # 에러 메시지
    "작업시간",         # 실행 시간
]

# 전체 헤더 (수집 + 영상 자동화)
SHEET_HEADERS = COLLECT_HEADERS + VIDEO_AUTOMATION_HEADERS

# =====================================================
# 환경변수
# =====================================================

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
CLAUDE_OPUS_MODEL = "anthropic/claude-opus-4-5-20251101"

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "")  # Gemini TTS용
GOOGLE_CLOUD_API_KEY = os.getenv("GOOGLE_CLOUD_API_KEY", "")  # Google Cloud TTS용
