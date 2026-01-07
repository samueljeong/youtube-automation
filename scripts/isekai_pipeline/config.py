"""
혈영 이세계편 파이프라인 설정
- 시리즈: 혈영 이세계편 (시즌2)
- 주인공: 무영
- 60화 6부작
"""

import os
from typing import Dict, List

# =====================================================
# 프로젝트 경로
# =====================================================

_config_dir = os.path.dirname(os.path.abspath(__file__))
_project_root = os.path.dirname(os.path.dirname(_config_dir))

# =====================================================
# 시리즈 설정
# =====================================================

SERIES_INFO = {
    "title": "혈영 이세계편",
    "title_en": "Blood Shadow: Another World",
    "season": 2,
    "protagonist": "무영",
    "genre": "이세계 무협 판타지",
    "total_episodes": 60,
    "parts": 6,
    "episodes_per_part": 10,
    "description": (
        "무림 최강의 검객이 이세계로 떨어졌다. "
        "모든 내공을 잃었지만, 그의 검술과 심법 지식은 남아있다. "
        "마나라는 새로운 힘을 만난 그는, 다시 최강을 향해 나아간다."
    ),
    "youtube_channel_id": os.getenv("ISEKAI_CHANNEL_ID", ""),
    "playlist_id": os.getenv("ISEKAI_PLAYLIST_ID", ""),
}

# =====================================================
# 분량 설정
# =====================================================

SCRIPT_CONFIG = {
    # 에피소드당 목표 글자수 (약 13~16분 영상)
    # TTS 기준: 약 910자 ≈ 1분
    "target_chars": 14000,       # 15분 분량 (중간값)
    "min_chars": 12000,          # 최소 13분
    "max_chars": 15000,          # 최대 16분

    # 이미지 설정 (화당 1개 대표 이미지)
    "image_count": 1,

    # 챕터 구조
    "scenes_per_episode": 5,     # 에피소드당 씬 수 (4~6)

    # TTS 설정
    "speaking_rate": 0.95,
    "language": "ko-KR",

    # 스토리텔링 설정
    "storytelling_style": "novel",  # 소설체
    "dialogue_ratio": 0.35,         # 대사 비율 35%
    "cliffhanger": True,            # 에피소드 끝 긴장감
}

# =====================================================
# 6부작 구조
# =====================================================

PART_STRUCTURE = {
    1: {
        "title": "이방인",
        "episodes": (1, 10),
        "summary": "이세계 도착, 적응, 카이든 만남, 마나 각성",
        "key_events": ["전이", "카이든", "자유도시", "마나 각성"],
        "ending": "그래듀에이트 진입",
    },
    2: {
        "title": "검은 별",
        "episodes": (11, 20),
        "summary": "성장, 에이라 만남, 볼드릭, 소드마스터 등극",
        "key_events": ["에이라", "심법 교환", "볼드릭", "소드마스터"],
        "ending": "소드마스터 등극, '검은 별' 별명",
    },
    3: {
        "title": "용의 친구",
        "episodes": (21, 30),
        "summary": "이그니스, 명성, 레인, 마왕 존재 인지",
        "key_events": ["이그니스", "드래곤 친구", "레인", "마왕 소문"],
        "ending": "마왕의 존재 확인",
    },
    4: {
        "title": "대륙의 그림자",
        "episodes": (31, 40),
        "summary": "혈마 확인, 제국 정치, 에이라 과거, 첫 교전",
        "key_events": ["혈마 발견", "정치", "에이라 엘프", "첫 전투"],
        "ending": "전면전 불가피",
    },
    5: {
        "title": "전쟁의 서막",
        "episodes": (41, 50),
        "summary": "연합군, 대규모 전투, 조력자 성장",
        "key_events": ["연합군", "에이라 9서클", "카이든 소드마스터", "마왕성 결정"],
        "ending": "마왕성 진격 결정",
    },
    6: {
        "title": "혈영, 다시",
        "episodes": (51, 60),
        "summary": "마왕성 공략, 최종 대결, 귀환",
        "key_events": ["마왕성", "혈마 대결", "그랜드 소드마스터", "귀환"],
        "ending": "무림 귀환, 설하와 재회",
    },
}

# =====================================================
# 캐릭터 설정
# =====================================================

CHARACTERS = {
    "무영": {
        "name_display": "무영",
        "name_en": "Muyeong",
        "role": "protagonist",
        "species": "인간 (동양인)",
        "age": "20대 초반",
        "personality": ["쿨함", "어두움", "아싸", "의리"],
        "speech_style": "과묵, 짧은 문장",
        "speech_examples": [
            "...",
            "시끄럽다.",
            "상관없어.",
            "네가 알 필요 없다.",
        ],
        "appearance_en": (
            "Young East Asian man, early 20s, sharp angular features, "
            "intense dark eyes, messy black hair in a loose ponytail, "
            "lean muscular build, wearing simple traveler's clothes, "
            "subtle scars on hands, determined cold expression"
        ),
    },
    "에이라": {
        "name_display": "에이라",
        "name_en": "Eira",
        "role": "heroine",
        "species": "하프엘프",
        "age": "외모 20대 (실제 50대)",
        "personality": ["경계심", "외로움", "강인함", "따뜻함"],
        "speech_style": "차갑지만 점점 부드러워짐",
        "appearance_en": (
            "Half-elf woman, appears early 20s, silver-white hair, "
            "slightly pointed ears, cold beautiful features, "
            "pale blue eyes, slender build, "
            "wearing practical mage robes in blue and white"
        ),
    },
    "혈마": {
        "name_display": "혈마",
        "name_en": "Blood Demon",
        "role": "villain",
        "species": "인간 (동양인)",
        "age": "30대",
        "personality": ["야망", "잔인함", "집착"],
        "speech_style": "오만하고 위압적",
        "appearance_en": (
            "East Asian man, 30s, cruel handsome features, "
            "long black hair, eyes glowing with dark energy, "
            "wearing ornate black and red armor, "
            "dark magical aura, menacing presence"
        ),
    },
    "카이든": {
        "name_display": "카이든",
        "name_en": "Kaidein",
        "role": "ally",
        "species": "인간",
        "age": "20대 중반",
        "personality": ["우직함", "정의감", "덜렁거림"],
        "speech_style": "밝고 친근함",
        "speech_examples": [
            "야, 무! 이것 좀 봐!",
            "걱정 마, 내가 있잖아!",
        ],
        "appearance_en": (
            "Young Western man, mid 20s, honest round face, "
            "short brown hair, friendly eyes, sturdy build, "
            "wearing soldier's uniform or simple armor"
        ),
    },
    "볼드릭": {
        "name_display": "볼드릭",
        "name_en": "Voldric",
        "role": "ally",
        "species": "드워프",
        "age": "180세",
        "personality": ["까칠", "고집", "장인정신"],
        "speech_style": "퉁명스러움",
        "appearance_en": (
            "Dwarf male, appears middle-aged, long braided beard, "
            "muscular stocky build, weathered hands, "
            "wearing blacksmith's apron and tools"
        ),
    },
    "레인": {
        "name_display": "레인",
        "name_en": "Rain",
        "role": "ally",
        "species": "인간",
        "age": "30대",
        "personality": ["능글", "계산적", "신의"],
        "speech_style": "부드럽고 능글맞음",
        "appearance_en": (
            "Human man, 30s, average forgettable face, "
            "neat but unremarkable clothes, "
            "calculating eyes behind a friendly smile"
        ),
    },
    "이그니스": {
        "name_display": "이그니스",
        "name_en": "Ignis",
        "role": "ally",
        "species": "상급 드래곤",
        "age": "800세 (청소년기)",
        "personality": ["호기심", "장난기", "자존심"],
        "speech_style": "자존심 강하지만 장난기 있음",
        "speech_examples": [
            "흥, 이 위대한 이그니스님이...",
            "재밌는 인간이군!",
        ],
        "appearance_en": (
            "Young man appearance (human form), fiery red hair, "
            "golden reptilian eyes, sharp features, confident smirk, "
            "wearing red and gold clothes, subtle dragon scales on neck"
        ),
        "dragon_form_en": (
            "Massive red dragon, scales like molten metal, "
            "golden eyes, powerful wings, flame aura"
        ),
    },
    "설하": {
        "name_display": "설하",
        "name_en": "Seolha",
        "role": "love_interest_absent",
        "species": "인간 (동양인)",
        "age": "20대 초반",
        "personality": ["따뜻함", "강인함", "그리움"],
        "note": "무림에 남아있음. 회상/꿈으로만 등장",
        "appearance_en": (
            "Beautiful East Asian woman, early 20s, "
            "long flowing black hair, gentle almond eyes, "
            "elegant white hanbok with subtle embroidery"
        ),
    },
}

# =====================================================
# 세계관 설정
# =====================================================

WORLD_SETTING = {
    "continent": "아르테시아",
    "continent_en": "Artesia",
    "mana_density": "무림의 10배",
    "nations": {
        "레온하르트 제국": {
            "location": "중앙",
            "type": "empire",
            "strength": "최강, 소드마스터 15명",
        },
        "카렌 왕국": {
            "location": "남서부",
            "type": "kingdom",
            "strength": "기사 왕국, 소드마스터 5명",
            "note": "카이든 출신지",
        },
        "자유도시연합": {
            "location": "남동부",
            "type": "republic",
            "strength": "모험가 길드 본부",
            "note": "무영 정착지",
        },
        "엘프 영역": {
            "location": "동부",
            "type": "council",
            "strength": "대마법사 다수",
            "note": "에이라 출신지 (추방)",
        },
        "드워프 산맥": {
            "location": "서부",
            "type": "clan",
            "strength": "최고의 대장장이",
            "note": "볼드릭 출신지",
        },
        "마왕군 영역": {
            "location": "북방",
            "type": "demon_army",
            "ruler": "혈마",
            "strength": "마족 + 언데드",
        },
    },
}

# =====================================================
# 경지 체계
# =====================================================

POWER_LEVELS = {
    "sword": {
        "일반 기사": {"count": "수십만", "equivalent": "후천지경"},
        "엑스퍼트": {"count": "수천", "equivalent": "선천지경"},
        "그래듀에이트": {"count": "300~500", "equivalent": "절정"},
        "소드마스터": {"count": "30~50", "equivalent": "화경"},
        "그랜드 소드마스터": {"count": "5 이하", "equivalent": "현경"},
        "소드 엠퍼러": {"count": "0 (전설)", "equivalent": "생사경"},
    },
    "magic": {
        "1~3서클": {"count": "수만"},
        "4~6서클": {"count": "수천"},
        "7~8서클": {"count": "수백"},
        "9서클": {"count": "10 이하", "title": "대마법사"},
    },
    "dragon": {
        "하급 드래곤": {"count": "수십", "equivalent": "소드마스터급"},
        "상급 드래곤": {"count": "5~10", "equivalent": "그랜드 소드마스터급"},
        "에이션트 드래곤": {"count": "2~3", "equivalent": "소드 엠퍼러급"},
        "드래곤 로드": {"count": "1", "equivalent": "대륙 최강"},
    },
}

# =====================================================
# 문체 설정 (웹소설 스타일 - 광마회귀 참고)
# =====================================================

WRITING_STYLE = {
    "format": "webnovel",  # 웹소설체
    "pov": "third_person_limited",  # 3인칭 제한적 (무영 중심)

    # 문장 스타일
    "sentence": {
        "length": (10, 25),      # 짧은 문장 (10~25자)
        "max": 35,               # 최대 35자
        "one_line_break": True,  # 한 문장 = 한 줄 (줄바꿈)
    },

    # 문단 스타일
    "paragraph": {
        "sentences": (1, 3),     # 문단당 1~3문장 (짧게)
        "action_single": True,   # 액션/심리는 한 문장씩
    },

    # 대화 비율
    "dialogue_ratio": (0.45, 0.55),  # 대사 비율 45~55% (높임)

    # 내면 독백 스타일
    "inner_monologue": {
        "style": "cynical_humor",     # 냉소적 유머
        "muhyup_terms": True,         # 무협 용어로 현대/판타지 해석
        "culture_shock": True,        # 이세계 문화 당황 표현
        "format": "single_quote",     # '이런 식으로' 표현
    },

    # 완급 조절
    "pacing": {
        "serious_to_humor": True,     # 진지 → 유머 전환
        "rhythm_variation": True,     # 단문-중문-장문 리듬
        "cliffhanger_per_scene": True,  # 씬마다 작은 훅
    },

    # 효과 표현
    "effects": {
        "onomatopoeia_solo": True,    # 효과음 단독 줄 ("쾅.", "철컥.")
        "ellipsis_emotion": True,     # 말줄임표로 감정 표현
        "silence_dots": "......",     # 침묵 표현
    },

    # 금지 사항
    "forbidden": [
        "태그 사용 ([나레이션], [무영] 등)",
        "미사여구 반복",
        "설명조 서술 (장황한 배경 설명)",
        "장문 남발 (40자 이상)",
        "인터넷 밈/드립 직접 사용",  # 무영 캐릭터에 안 맞음
    ],

    # 권장 사항
    "recommended": [
        "짧고 임팩트 있는 문장",
        "대화만 읽어도 상황 파악 가능",
        "무영의 냉소적 내면 독백",
        "무협 용어를 이세계에 적용하는 유머",
        "액션씬은 짧은 문장으로 속도감",
    ],
}

# =====================================================
# TTS 설정
# =====================================================

TTS_CONFIG = {
    "voice": "chirp3:Charon",
    "speed": 0.95,
    "language": "ko-KR",
    "emotions": [
        "calm", "tense", "sad", "angry",
        "confused", "excited", "whisper", "shout"
    ],
}

# =====================================================
# 이미지 설정
# =====================================================

IMAGE_STYLE = {
    "style": "western_fantasy_illustration",
    "aspect_ratio": "16:9",
    "quality": "masterpiece, high detail",
    "base_prompt": (
        "Western fantasy illustration style, "
        "dramatic cinematic lighting, "
        "detailed background, "
        "16:9 aspect ratio, masterpiece quality"
    ),
    "negative_prompt": (
        "text, letters, words, writing, watermark, signature, "
        "anime style, cartoon, chibi, "
        "low quality, blurry, deformed, "
        "modern clothes, contemporary fashion"
    ),
}

# =====================================================
# 썸네일 설정
# =====================================================

THUMBNAIL_CONFIG = {
    "layout": {
        "series_title": "혈영 이세계편",
        "episode_format": "제{n}화",
        "text_position": "right-third",
    },
    "style": {
        "series_font_color": (255, 215, 0),  # 금색
        "episode_font_color": (255, 255, 255),  # 흰색
        "outline_color": (0, 0, 0),
        "outline_width": 4,
    },
}

# =====================================================
# BGM 설정
# =====================================================

BGM_CONFIG = {
    "moods": {
        "calm": "평화, 일상",
        "tension": "긴장, 위기",
        "fight": "전투",
        "sad": "슬픔",
        "nostalgia": "향수, 회상",
        "mysterious": "신비",
        "triumph": "승리, 성취",
        "villain": "악역, 위협",
        "romance": "로맨스",
        "epic": "웅장함",
    },
    "default_volume": 0.10,
    "fade_in": 2.0,
    "fade_out": 3.0,
}

# =====================================================
# Google Sheets 설정
# =====================================================

SHEET_NAME = "혈영이세계"

SHEET_HEADERS = [
    # 수집/기획 영역 (에이전트가 생성)
    "episode",              # EP001
    "part",                 # 1~6부
    "title",                # 에피소드 제목
    "summary",              # 요약
    "scenes",               # 씬 구조 (JSON) - BGM/챕터용
    "image_prompt",         # 메인 이미지 프롬프트

    # 메타데이터 영역 (METADATA 에이전트가 생성)
    "youtube_title",        # YouTube 제목
    "youtube_description",  # YouTube 설명 (타임스탬프 포함)
    "youtube_tags",         # YouTube 태그 (JSON)
    "thumbnail_hook",       # 썸네일 훅 텍스트
    "cliffhanger",          # 클리프행어 (다음화 예고)
    "next_preview",         # 다음화 예고 문구

    # 영상 자동화 영역
    "상태",                 # 대기/처리중/완료/실패
    "대본",                 # 생성된 대본 (26,000자)
    "인용링크",
    "제목(입력)",           # 사용자 수정 제목 (없으면 youtube_title 사용)
    "썸네일문구(입력)",     # 사용자 수정 썸네일
    "공개설정",
    "예약시간",
    "플레이리스트ID",
    "음성",
    "영상URL",
    "쇼츠URL",
    "비용",
    "에러메시지",
    "작업시간",
]

# =====================================================
# API 설정 (Workers용)
# =====================================================

# TTS, 이미지 생성에 사용
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "")

# =====================================================
# 출력 디렉토리
# =====================================================

OUTPUT_BASE = os.path.join(_project_root, "outputs", "isekai")
