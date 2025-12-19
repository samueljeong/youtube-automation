"""
해외 미스테리 파이프라인 설정

- 미스테리 카테고리 정의
- 위키백과 소스 URL
- TTS/영상 설정
"""

from typing import Dict, List, Any


# ============================================================
# 영상 설정
# ============================================================

# TTS 음성 (미스테리에 어울리는 깊은 남성 목소리)
MYSTERY_TTS_VOICE = "gemini:Charon"

# 영상 길이 (분)
MYSTERY_VIDEO_LENGTH_MINUTES = 20

# 예상 대본 글자 수 (910자/분 기준)
MYSTERY_SCRIPT_LENGTH = MYSTERY_VIDEO_LENGTH_MINUTES * 910  # 약 18,200자

# 이미지 개수 (20분 기준)
MYSTERY_IMAGE_COUNT = 12


# ============================================================
# Google Sheets 설정
# ============================================================

# 시트 이름
MYSTERY_SHEET_NAME = "MYSTERY_OPUS_INPUT"

# PENDING 유지 개수
PENDING_TARGET_COUNT = 5

# 시트 헤더
MYSTERY_SHEET_HEADERS = [
    "run_id",           # 실행 날짜
    "episode",          # 에피소드 번호
    "category",         # 카테고리 (disappearance/death/location/crime)
    "title_en",         # 영문 제목
    "title_ko",         # 한글 제목
    "wiki_url",         # 위키백과 URL
    "summary",          # 사건 요약
    "full_content",     # 전체 내용 (Opus용)
    "opus_prompt",      # Opus 프롬프트
    "status",           # PENDING/WRITING/DONE
    "created_at",       # 생성 시간
]


# ============================================================
# 미스테리 카테고리 정의
# ============================================================

MYSTERY_CATEGORIES: Dict[str, Dict[str, Any]] = {
    "DISAPPEARANCE": {
        "name": "미해결 실종",
        "name_en": "Unsolved Disappearances",
        "description": "흔적도 없이 사라진 사람들",
        "wiki_sources": [
            "List_of_people_who_disappeared_mysteriously",
            "List_of_people_who_disappeared_mysteriously:_pre-1970",
            "List_of_people_who_disappeared_mysteriously:_1970–1999",
            "List_of_people_who_disappeared_mysteriously:_2000–present",
        ],
        "priority": 1,
        "active": True,
    },
    "DEATH": {
        "name": "미해결 사망",
        "name_en": "Unsolved Deaths",
        "description": "의문의 죽음, 풀리지 않는 사인",
        "wiki_sources": [
            "List_of_unsolved_deaths",
            "List_of_unsolved_murders",
        ],
        "priority": 2,
        "active": True,
    },
    "LOCATION": {
        "name": "미스테리 장소",
        "name_en": "Mysterious Locations",
        "description": "기이한 현상이 일어나는 장소들",
        "wiki_sources": [
            "List_of_reportedly_haunted_locations",
            "List_of_reportedly_haunted_locations_in_the_United_States",
            "Bermuda_Triangle",
        ],
        "priority": 3,
        "active": True,
    },
    "CRIME": {
        "name": "미해결 사건",
        "name_en": "Unsolved Cases",
        "description": "아직도 범인을 찾지 못한 사건들",
        "wiki_sources": [
            "List_of_unsolved_murders",
            "List_of_serial_killers_by_number_of_victims",
            "List_of_unidentified_murder_victims_in_the_United_States",
        ],
        "priority": 4,
        "active": True,
    },
    "PHENOMENON": {
        "name": "미스테리 현상",
        "name_en": "Mysterious Phenomena",
        "description": "설명할 수 없는 기이한 현상들",
        "wiki_sources": [
            "Dyatlov_Pass_incident",
            "Tunguska_event",
            "Wow!_signal",
            "Voynich_manuscript",
            "Zodiac_Killer",
            "Tamam_Shud_case",
            "Hinterkaifeck_murders",
            "Lead_Masks_Case",
        ],
        "priority": 5,
        "active": True,
    },
}


# ============================================================
# 인기 미스테리 사건 목록 (초기 콘텐츠용)
# ============================================================

FEATURED_MYSTERIES: List[Dict[str, Any]] = [
    {
        "title": "Dyatlov_Pass_incident",
        "category": "PHENOMENON",
        "title_ko": "댜틀로프 고개 사건",
        "year": 1959,
        "country": "소련 (러시아)",
        "hook": "9명의 대학생이 영하 40도에 맨발로 텐트를 찢고 도망쳤다",
    },
    {
        "title": "D._B._Cooper",
        "category": "DISAPPEARANCE",
        "title_ko": "D.B. 쿠퍼 하이재킹",
        "year": 1971,
        "country": "미국",
        "hook": "비행기를 납치하고 20만 달러와 함께 사라진 남자",
    },
    {
        "title": "Zodiac_Killer",
        "category": "CRIME",
        "title_ko": "조디악 킬러",
        "year": "1968-1969",
        "country": "미국",
        "hook": "암호문을 보내며 경찰을 조롱한 연쇄살인범",
    },
    {
        "title": "Tamam_Shud_case",
        "category": "DEATH",
        "title_ko": "타만 슈드 사건",
        "year": 1948,
        "country": "호주",
        "hook": "신원 불명의 남자와 '끝났다'는 메모",
    },
    {
        "title": "Hinterkaifeck_murders",
        "category": "CRIME",
        "title_ko": "힌터카이펙 살인 사건",
        "year": 1922,
        "country": "독일",
        "hook": "살인범이 며칠간 피해자 집에서 생활했다",
    },
    {
        "title": "Lead_Masks_Case",
        "category": "DEATH",
        "title_ko": "납 가면 사건",
        "year": 1966,
        "country": "브라질",
        "hook": "눈을 가린 납 가면과 수수께끼의 메모",
    },
    {
        "title": "Elisa_Lam_death",
        "category": "DEATH",
        "title_ko": "엘리사 램 사건",
        "year": 2013,
        "country": "미국",
        "hook": "물탱크에서 발견된 여대생과 기이한 엘리베이터 영상",
    },
    {
        "title": "Mary_Celeste",
        "category": "DISAPPEARANCE",
        "title_ko": "메리 셀레스트호",
        "year": 1872,
        "country": "대서양",
        "hook": "승무원 전원이 사라진 유령선",
    },
    {
        "title": "Flannan_Isles_Lighthouse",
        "category": "DISAPPEARANCE",
        "title_ko": "플래넌 등대 실종 사건",
        "year": 1900,
        "country": "스코틀랜드",
        "hook": "세 명의 등대지기가 흔적도 없이 사라졌다",
    },
    {
        "title": "Jack_the_Ripper",
        "category": "CRIME",
        "title_ko": "잭 더 리퍼",
        "year": 1888,
        "country": "영국",
        "hook": "빅토리아 시대 런던을 공포에 떨게 한 연쇄살인범",
    },
    {
        "title": "Bermuda_Triangle",
        "category": "LOCATION",
        "title_ko": "버뮤다 삼각지대",
        "year": "-",
        "country": "대서양",
        "hook": "배와 비행기가 사라지는 죽음의 바다",
    },
    {
        "title": "Roanoke_Colony",
        "category": "DISAPPEARANCE",
        "title_ko": "로어노크 식민지",
        "year": 1590,
        "country": "미국",
        "hook": "117명이 사라지고 남은 건 'CROATOAN'이라는 글자뿐",
    },
    {
        "title": "Voynich_manuscript",
        "category": "PHENOMENON",
        "title_ko": "보이니치 필사본",
        "year": "15세기",
        "country": "알 수 없음",
        "hook": "600년간 아무도 해독하지 못한 책",
    },
    {
        "title": "Tunguska_event",
        "category": "PHENOMENON",
        "title_ko": "퉁구스카 대폭발",
        "year": 1908,
        "country": "러시아",
        "hook": "히로시마 원폭의 1000배 위력, 충돌체는 발견되지 않았다",
    },
    {
        "title": "Cicada_3301",
        "category": "PHENOMENON",
        "title_ko": "시카다 3301",
        "year": 2012,
        "country": "인터넷",
        "hook": "인터넷에 등장한 수수께끼의 퍼즐, 출제자는 누구인가",
    },
    {
        "title": "The_Somerton_Man",
        "category": "DEATH",
        "title_ko": "서머튼 맨",
        "year": 1948,
        "country": "호주",
        "hook": "타만 슈드 사건의 주인공, 75년 만에 신원이 밝혀졌다",
    },
    {
        "title": "Disappearance_of_Madeleine_McCann",
        "category": "DISAPPEARANCE",
        "title_ko": "매들린 맥캔 실종 사건",
        "year": 2007,
        "country": "포르투갈",
        "hook": "휴가지에서 사라진 세 살 소녀",
    },
    {
        "title": "MH370",
        "category": "DISAPPEARANCE",
        "title_ko": "말레이시아 항공 370편",
        "year": 2014,
        "country": "인도양",
        "hook": "239명을 태우고 사라진 비행기",
    },
    {
        "title": "Black_Dahlia",
        "category": "CRIME",
        "title_ko": "블랙 달리아 사건",
        "year": 1947,
        "country": "미국",
        "hook": "할리우드를 뒤흔든 잔혹한 살인",
    },
    {
        "title": "JonBenét_Ramsey",
        "category": "CRIME",
        "title_ko": "존베넷 램지 사건",
        "year": 1996,
        "country": "미국",
        "hook": "크리스마스에 살해된 여섯 살 미인대회 우승자",
    },
]


# ============================================================
# Opus 프롬프트 템플릿
# ============================================================

MYSTERY_OPUS_PROMPT_TEMPLATE = """당신은 해외 미스테리 전문 유튜브 채널의 대본 작가입니다.

## 사건 정보
- 제목: {title_ko}
- 원제: {title_en}
- 카테고리: {category}
- 발생 연도: {year}
- 발생 국가: {country}
- 후킹 포인트: {hook}

## ★ 자료 수집 (중요!)

아래 위키백과 URL을 직접 열어서 사건의 전체 내용을 읽으세요:

**위키백과 URL**: {wiki_url}

위 URL에서 다음 정보를 수집하세요:
1. 사건의 전체 경위 (시간순)
2. 등장인물 정보 (이름, 나이, 직업 등)
3. 발견된 증거들
4. 수사 과정과 결과
5. 제기된 이론들
6. 현재 상태 (해결/미해결)

## 작성 지침

### 스타일
- 20분 분량 (약 18,000자)
- 미스테리/스릴러 분위기로 몰입감 있게
- 한국 시청자가 듣기 편한 자연스러운 한국어
- 팩트(인물명, 장소명, 날짜, 수치)는 정확히 유지
- 외국 인명/지명은 한글 음역 + 괄호 안 영문 병기 (예: 이고르 댜틀로프(Igor Dyatlov))

### 구조
1. **인트로 (후킹)** - 가장 충격적인 사실로 시작, 시청자를 사로잡기
2. **사건의 시작** - 배경, 등장인물 소개
3. **사건 전개** - 시간순 또는 발견순으로 상세히
4. **미스테리 포인트** - 설명되지 않는 부분 강조
5. **이론과 추측** - 제기된 가설들
6. **현재 상태** - 해결/미해결 여부, 최신 정보
7. **아웃트로** - 여운 남기기, 질문 던지기

### 금지사항
- 허구 추가 금지 (있는 사실만)
- 과도한 공포 조장 금지
- 피해자 비하 금지
- "구독 좋아요" 멘트 금지

## 출력 형식
대본 본문만 출력하세요. 씬 구분이나 메타데이터는 포함하지 마세요.
"""
