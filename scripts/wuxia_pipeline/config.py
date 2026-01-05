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

# ★ 단일 나레이션 음성으로 통일 (품질 일관성 + 자막 싱크 안정성)
VOICE_MAP: Dict[str, str] = {
    "나레이션": "chirp3:Charon",
    "무영": "chirp3:Charon",
    "설하": "chirp3:Charon",
    "노인": "chirp3:Charon",
    "각주": "chirp3:Charon",
    "악역": "chirp3:Charon",
    "남자": "chirp3:Charon",
    "여자": "chirp3:Charon",
}

# 캐릭터별 음성 속도 (단일 음성이므로 모두 동일)
CHARACTER_SPEAKING_RATE: Dict[str, float] = {
    # 모든 캐릭터 동일 속도
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
# ★ 2026-01 업데이트: 현대 의상 방지, 텍스트 삽입 방지 강화
IMAGE_STYLE = {
    "base_style": (
        "Traditional Korean historical wuxia manhwa illustration style, "
        "ink wash painting with vibrant accent colors, "
        "dramatic cinematic lighting, "
        "Joseon Dynasty era Korean aesthetic, "
        "MUST wear traditional Korean hanbok or martial arts robes, "
        "NO modern clothing NO hoodies NO jeans NO t-shirts, "
        "16:9 aspect ratio, high detail, masterpiece quality"
    ),
    "action_style": (
        "dynamic action composition, motion blur effects, "
        "energy trails, dramatic poses, sword fighting"
    ),
    "emotional_style": (
        "intimate framing, soft lighting, "
        "focus on facial expressions and emotions, "
        "traditional Korean interior setting"
    ),
    "landscape_style": (
        "wide panoramic shot, misty mountains, "
        "traditional Korean architecture with curved tile roofs, "
        "Joseon Dynasty buildings, atmospheric perspective"
    ),
    "negative_prompt": (
        # ★★★ 텍스트 삽입 방지 (최우선) ★★★
        "text, letters, words, writing, caption, subtitle, speech bubble, dialogue box, "
        "watermark, signature, logo, username, copyright, "
        # ★★★ 현대 의상 방지 (필수) ★★★
        "modern clothes, hoodie, jeans, t-shirt, sneakers, modern shoes, "
        "contemporary fashion, casual wear, sportswear, jacket, "
        # ★★★ 스타일 방지 ★★★
        "anime style, Japanese anime, cartoon, chibi, "
        "3D render, CGI, photorealistic, photograph, "
        # ★★★ 품질 방지 ★★★
        "low quality, blurry, deformed, ugly, bad anatomy, "
        "extra limbs, missing limbs, disfigured"
    ),
}

# =====================================================
# BGM 설정 (무협 전용)
# =====================================================
# ★ 씬 분위기에 따라 자동 선택되는 BGM 매핑
# ★ 12개의 무협 전용 BGM 파일

BGM_DIR = "static/audio/bgm"

# 씬 분위기 → BGM 파일 매핑
WUXIA_BGM_MAP: Dict[str, str] = {
    # 메인 테마 (오프닝, 엔딩)
    "main": "bgm_wuxia_main.mp3",

    # 전투/액션 씬
    "fight": "bgm_wuxia_fight.mp3",       # 무술 대결, 격투
    "tension": "bgm_wuxia_tension.mp3",   # 긴장감, 위기 직전
    "villain": "bgm_wuxia_villain.mp3",   # 악역 등장, 위협

    # 수련/성장 씬
    "training": "bgm_wuxia_training.mp3", # 무공 수련, 내공 연마
    "triumph": "bgm_wuxia_triumph.mp3",   # 성취, 돌파, 승리

    # 감정/드라마 씬
    "romance": "bgm_wuxia_romance.mp3",   # 로맨스, 설하와의 장면
    "sad": "bgm_wuxia_sad.mp3",           # 슬픔, 이별, 회상
    "nostalgia": "bgm_wuxia_nostalgia.mp3", # 향수, 과거 회상

    # 분위기/배경 씬
    "calm": "bgm_wuxia_calm.mp3",         # 평화로운 일상, 대화
    "mystery": "bgm_wuxia_mystery.mp3",   # 신비로움, 미스터리
    "journey": "bgm_wuxia_journey.mp3",   # 여정, 강호 방랑
}

# 기본 BGM (씬 분위기가 지정되지 않았을 때)
DEFAULT_BGM = "bgm_wuxia_main.mp3"

# BGM 설정
BGM_CONFIG = {
    "volume": 0.10,      # BGM 볼륨 10% (TTS 나레이션 우선)
    "fade_in": 2.0,      # 페이드인 (초)
    "fade_out": 3.0,     # 페이드아웃 (초)
}

# 씬 키워드 → 분위기 자동 감지
BGM_KEYWORD_MAP: Dict[str, List[str]] = {
    "fight": ["대결", "전투", "격투", "무공", "검", "창", "권", "피", "공격", "방어", "일합", "비무"],
    "tension": ["긴장", "위기", "습격", "포위", "위험", "노려", "살기", "기척"],
    "villain": ["악", "마", "흑", "암", "사", "독", "마교", "흑도", "악당", "적"],
    "training": ["수련", "연습", "내공", "운기", "단전", "호흡", "연마", "정진"],
    "triumph": ["성공", "돌파", "승리", "달성", "깨달음", "각성", "초월"],
    "romance": ["설하", "미소", "손", "눈", "마음", "가슴", "따뜻", "사랑", "그녀"],
    "sad": ["슬픔", "눈물", "이별", "죽음", "외로움", "그리움", "상심"],
    "nostalgia": ["과거", "어린", "추억", "예전", "그때", "노인", "스승"],
    "calm": ["평화", "고요", "일상", "밥", "잠", "아침", "햇살", "휴식"],
    "mystery": ["신비", "비밀", "의문", "이상한", "기이한", "알 수 없는", "숨겨진"],
    "journey": ["길", "여정", "방랑", "강호", "산", "숲", "마을", "떠나"],
}

# =====================================================
# 썸네일 설정 (시리즈 통일)
# =====================================================
# ★ 시리즈 전체에서 동일한 대표 이미지 사용
# ★ 에피소드마다 텍스트(화 번호, 부제목)만 변경

THUMBNAIL_CONFIG = {
    # 시리즈 대표 이미지 (1개 고정)
    "series_image_path": "static/images/wuxia/hyulyoung_series_thumb.png",

    # 시리즈 대표 이미지 프롬프트 (최초 1회만 생성)
    "series_image_prompt": (
        "Traditional Korean wuxia martial arts manhwa illustration, "
        "dramatic portrait of young Korean martial artist in flowing dark robes, "
        "intense piercing eyes, messy black hair in topknot, "
        "standing on misty mountain cliff at sunrise, "
        "ink wash painting style with vibrant red and gold accent colors, "
        "epic cinematic composition, 16:9 aspect ratio, "
        "NO text NO letters NO writing, masterpiece quality"
    ),

    # 썸네일 레이아웃
    "layout": {
        "series_logo_position": "top-left",     # 시리즈 로고 위치
        "channel_logo_position": "top-right",   # 채널 로고 위치
        "title_position": "bottom-center",      # 제목 위치
        "waveform_position": "bottom",          # 오디오 파형 위치
    },

    # 텍스트 스타일
    "text_style": {
        "series_title": "혈영 [血影]",          # 시리즈명 (한자 병기)
        "series_font_color": (255, 215, 0),     # 금색
        "episode_font_color": (255, 255, 255),  # 흰색
        "outline_color": (0, 0, 0),             # 검은 테두리
        "outline_width": 4,
    },
}

# =====================================================
# 대본 설정 (A안: 장편 오디오북 스타일)
# =====================================================
# ★ 2026-01 업데이트: 벤치마킹 결과 반영
# - 1개 고퀄리티 이미지 + 오디오 파형 오버레이
# - 50분 장편 오디오북 (몰입감 + 정주행 유도)

SCRIPT_CONFIG = {
    # 에피소드당 목표 글자수 (약 50분 영상)
    # 한국어 TTS 실측 기준: 약 500자 ≈ 1분
    "target_chars": 25000,       # 50분 분량
    "min_chars": 22000,          # 최소 44분
    "max_chars": 28000,          # 최대 56분

    # 이미지 설정 (A안: 1개 대표 이미지)
    "image_count": 1,            # ★ 1개 고퀄리티 대표 이미지
    "use_audio_waveform": True,  # ★ 오디오 파형 오버레이 사용

    # 챕터 구조 (장편용)
    "chapters_per_episode": 5,   # 에피소드당 챕터 수
    "chars_per_chapter": 5000,   # 챕터당 평균 글자수 (25000 / 5)

    # TTS 설정
    "speaking_rate": 0.95,       # 약간 빠르게 (장편이라 지루하지 않게)
    "language": "ko-KR",

    # 스토리텔링 설정
    "storytelling_style": "immersive",  # 몰입형 서술
    "dialogue_ratio": 0.4,              # 대사 비율 40% (긴장감 유지)
    "cliffhanger": True,                # 에피소드 끝 긴장감 유지
}

# =====================================================
# 에피소드 템플릿 (혈영 시리즈)
# =====================================================

EPISODE_TEMPLATES = {
    # ===== 1부: 운명의 시작 (1-5화) =====
    1: {
        "title": "운명의 시작",
        "summary": "노비 출신 청년 무영이 의문의 노인을 만나 절세무공의 비밀을 전수받게 되는 첫 번째 이야기",
        "key_events": ["무영의 비천한 신분과 고된 일상", "의문의 노인과의 만남", "노인의 시험과 무영의 선택", "무공 전수의 시작"],
        "characters": ["무영", "노인", "각주"],
    },
    2: {
        "title": "첫 번째 도약",
        "summary": "노인의 가르침 아래 무영이 첫 무공을 익히고 새로운 세계를 보게 되는 이야기",
        "key_events": ["기초 내공 수련", "첫 무공 습득의 어려움", "돌파의 순간", "새로운 능력의 자각"],
        "characters": ["무영", "노인"],
    },
    3: {
        "title": "강호에 발을 딛다",
        "summary": "수련을 마친 무영이 처음으로 강호의 현실을 마주하게 되는 이야기",
        "key_events": ["노인과의 이별", "첫 강호 출두", "불의와의 조우", "첫 번째 결전"],
        "characters": ["무영", "노인", "악역"],
    },
    4: {
        "title": "눈 속의 절세미인",
        "summary": "강호를 떠돌던 무영이 눈보라 속에서 쓰러진 절세미녀 설하를 구하게 되는 이야기",
        "key_events": ["눈보라 속 쓰러진 여인 발견", "설하와의 첫 만남", "설하를 노리는 자들의 습격", "무영의 실력 각성"],
        "characters": ["무영", "설하", "악역"],
    },
    5: {
        "title": "빚진 은혜",
        "summary": "설하가 무영에게 목숨을 빚졌다며 따라다니기 시작하는 이야기",
        "key_events": ["설하의 신분 - 명문 세가의 영애", "설하의 결심 - 은혜를 갚을 때까지", "무영의 무관심과 냉담", "설하를 시기하는 강호인들"],
        "characters": ["무영", "설하"],
    },
    # ===== 2부: 강호의 풍파 (6-10화) =====
    6: {
        "title": "첫 번째 원수",
        "summary": "무영의 과거가 드러나고, 그의 가족을 죽인 원수의 존재가 밝혀지는 이야기",
        "key_events": ["무영의 어린 시절 회상", "가족의 죽음과 원수", "복수를 향한 결심", "설하의 걱정과 지지"],
        "characters": ["무영", "설하", "악역"],
    },
    7: {
        "title": "흑풍채의 습격",
        "summary": "흑풍채 산적단이 마을을 습격하고, 무영이 처음으로 많은 이들 앞에서 실력을 드러내는 이야기",
        "key_events": ["흑풍채의 마을 습격", "무영의 결단", "압도적인 실력 공개", "강호에 퍼지는 소문"],
        "characters": ["무영", "설하", "악역"],
    },
    8: {
        "title": "명문정파의 초대",
        "summary": "무영의 소문을 들은 명문정파 화산파에서 초대장을 보내오는 이야기",
        "key_events": ["화산파의 초대", "설하의 과거와 연결", "정파와 사파의 경계", "무영의 거절"],
        "characters": ["무영", "설하"],
    },
    9: {
        "title": "그림자 속의 추격자",
        "summary": "무영을 쫓는 의문의 암살자 집단이 등장하는 이야기",
        "key_events": ["밤의 습격", "혈영검의 비밀", "노인이 남긴 단서", "숨겨진 무공의 정체"],
        "characters": ["무영", "설하", "악역"],
    },
    10: {
        "title": "피로 물든 보름달",
        "summary": "암살자들과의 결전에서 무영이 혈영검법의 진정한 힘을 각성하는 이야기",
        "key_events": ["암살자 두목과의 대결", "혈영검법 각성", "설하의 위기", "무영의 폭주와 각성"],
        "characters": ["무영", "설하", "악역"],
    },
    # ===== 3부: 사랑과 복수 (11-15화) =====
    11: {
        "title": "설하의 눈물",
        "summary": "설하의 과거와 그녀가 무영을 따르는 진짜 이유가 밝혀지는 이야기",
        "key_events": ["설하 가문의 비극", "정혼자의 배신", "무영에게서 본 희망", "두 사람의 마음이 가까워짐"],
        "characters": ["무영", "설하"],
    },
    12: {
        "title": "원수의 그림자",
        "summary": "무영의 원수가 천마교의 호법 중 한 명임이 밝혀지는 이야기",
        "key_events": ["천마교의 존재", "원수 '혈마' 등장", "무영의 분노", "아직 부족한 실력의 자각"],
        "characters": ["무영", "설하", "악역"],
    },
    13: {
        "title": "숨겨진 비급",
        "summary": "노인이 남긴 혈영비급의 나머지 절반을 찾아 여정을 떠나는 이야기",
        "key_events": ["비급의 단서 발견", "험난한 여정", "설하와의 동행", "새로운 적의 등장"],
        "characters": ["무영", "설하", "악역"],
    },
    14: {
        "title": "절벽 위의 고백",
        "summary": "위기 상황에서 설하가 무영에게 마음을 고백하는 이야기",
        "key_events": ["절벽 추락 위기", "설하의 고백", "무영의 동요", "함께하겠다는 약속"],
        "characters": ["무영", "설하"],
    },
    15: {
        "title": "비급의 완성",
        "summary": "혈영비급을 완성하고 무영이 한 단계 더 강해지는 이야기",
        "key_events": ["비급 획득", "수련의 고통", "설하의 헌신적 간호", "새로운 경지 도달"],
        "characters": ["무영", "설하"],
    },
    # ===== 4부: 최후의 결전 (16-20화) =====
    16: {
        "title": "천마교의 선전포고",
        "summary": "천마교가 강호 정복을 선언하고, 무영이 연합군에 합류하는 이야기",
        "key_events": ["천마교의 선전포고", "정사대전의 시작", "무영의 결심", "연합군 합류"],
        "characters": ["무영", "설하", "악역"],
    },
    17: {
        "title": "피의 전장",
        "summary": "천마교와의 첫 대규모 전투에서 무영이 영웅으로 부상하는 이야기",
        "key_events": ["첫 대전투", "무영의 활약", "수많은 희생", "영웅의 탄생"],
        "characters": ["무영", "설하", "악역"],
    },
    18: {
        "title": "최후의 관문",
        "summary": "천마교 본거지로 진격하며 혈마와의 결전을 앞두는 이야기",
        "key_events": ["천마교 본거지 진격", "설하와의 이별", "최후의 각오", "혈마와의 조우"],
        "characters": ["무영", "설하", "악역"],
    },
    19: {
        "title": "혈마와의 결전",
        "summary": "무영이 드디어 원수 혈마와 목숨을 건 최후의 대결을 펼치는 이야기",
        "key_events": ["혈마의 진짜 정체", "목숨을 건 대결", "혈영검법의 극의", "복수의 완성"],
        "characters": ["무영", "악역"],
    },
    20: {
        "title": "새로운 여명",
        "summary": "천마교를 멸하고 설하와 함께 새로운 삶을 시작하는 무영의 이야기",
        "key_events": ["천마교의 멸망", "강호의 평화", "설하와의 재회", "새로운 시작"],
        "characters": ["무영", "설하", "노인"],
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
CLAUDE_MODEL = "anthropic/claude-sonnet-4.5"  # Sonnet 4.5

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "")  # Gemini TTS용
GOOGLE_CLOUD_API_KEY = os.getenv("GOOGLE_CLOUD_API_KEY", "")  # Google Cloud TTS용
