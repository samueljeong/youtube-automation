"""
미스테리 파이프라인 설정

- 해외 미스테리 (영어 위키백과)
- 한국 미스테리 (나무위키) ★ 2025-12-22 추가
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

# 시트 이름 (기존 - 레거시)
MYSTERY_SHEET_NAME = "MYSTERY_OPUS_INPUT"

# 통합 시트 이름 (2024-12-20 신규)
UNIFIED_MYSTERY_SHEET = "MYSTERY"

# 준비 상태 유지 개수
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
    "status",           # 준비/작성중/완료
    "created_at",       # 생성 시간
]

# 통합 시트에 저장할 때 사용할 필드 순서
# ★ opus_row의 각 열과 정확히 일치해야 함
MYSTERY_OPUS_FIELDS = [
    "episode",          # [0] 에피소드 번호
    "category",         # [1] 카테고리
    "title_en",         # [2] 영문 제목
    "title_ko",         # [3] 한글 제목
    "wiki_url",         # [4] 위키백과 URL
    "summary",          # [5] 사건 요약
    "full_content",     # [6] 전체 내용
    "opus_prompt",      # [7] Opus 프롬프트
    "thumbnail_copy",   # [8] 썸네일 문구
    "상태",             # [9] "준비" → 상태 열에 저장
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
# 한국 미스테리 카테고리 정의 (나무위키 기반)
# ============================================================

KR_MYSTERY_CATEGORIES: Dict[str, Dict[str, Any]] = {
    "TOP3": {
        "name": "3대 미제사건",
        "description": "영화화된 대한민국 대표 미제사건",
        "priority": 1,
        "active": True,
    },
    "MURDER": {
        "name": "미해결 살인",
        "description": "범인 미검거 살인사건",
        "priority": 2,
        "active": True,
    },
    "SUSPICIOUS_DEATH": {
        "name": "의문사",
        "description": "사인 불명 또는 의혹 있는 사망",
        "priority": 3,
        "active": True,
    },
    "MISSING": {
        "name": "실종",
        "description": "미해결 실종 사건",
        "priority": 4,
        "active": True,
    },
    "MASS_INCIDENT": {
        "name": "집단 사건",
        "description": "집단 자살, 사이비 종교 등",
        "priority": 5,
        "active": True,
    },
    "DISASTER": {
        "name": "대형 참사",
        "description": "의혹 있는 대형 사고",
        "priority": 6,
        "active": True,
    },
    "SERIAL": {
        "name": "연쇄 살인",
        "description": "해결되었으나 미스테리 요소 있음",
        "priority": 7,
        "active": True,
    },
    "URBAN_LEGEND": {
        "name": "도시전설",
        "description": "괴담, 미스테리 장소",
        "priority": 8,
        "active": True,
    },
}


# ============================================================
# 한국 미스테리 사건 목록 (48개)
# ============================================================

FEATURED_KR_MYSTERIES: List[Dict[str, Any]] = [
    # ========== 3대 미제사건 (TOP3) ==========
    {
        "namu_title": "개구리 소년 실종 사건",
        "category": "TOP3",
        "title_ko": "개구리 소년 실종 사건",
        "year": 1991,
        "hook": "개구리 잡으러 간 5명의 소년, 11년 후 유골로 발견",
        "movie": "아이들...",
    },
    {
        "namu_title": "이형호 유괴 살인 사건",
        "category": "TOP3",
        "title_ko": "이형호 유괴 살인 사건",
        "year": 1991,
        "hook": "44통의 전화, 끝내 잡지 못한 그놈 목소리",
        "movie": "그놈 목소리",
    },
    {
        "namu_title": "화성 연쇄살인 사건",
        "category": "TOP3",
        "title_ko": "화성 연쇄살인 사건",
        "year": "1986-1991",
        "hook": "33년 만에 밝혀진 진실, 이미 복역 중이던 범인",
        "movie": "살인의 추억",
        "solved": True,  # 2019년 해결
    },
    # ========== 미해결 살인 (MURDER) ==========
    {
        "namu_title": "정인숙 피살 사건",
        "category": "MURDER",
        "title_ko": "정인숙 피살 사건",
        "year": 1970,
        "hook": "대한민국 최초의 성형외과 의사, 살해된 미모의 여의사",
    },
    {
        "namu_title": "부산 어린이 연쇄살인 사건",
        "category": "MURDER",
        "title_ko": "부산 어린이 연쇄살인 사건",
        "year": 1975,
        "hook": "한 달간 5명의 어린이가 같은 방식으로 사라졌다",
    },
    {
        "namu_title": "김훈 중위 피살 사건",
        "category": "MURDER",
        "title_ko": "김훈 중위 피살 사건",
        "year": 1988,
        "hook": "휴가 중 의문의 죽음, 5공 비리를 알고 있었나",
    },
    {
        "namu_title": "치과의사 모녀 살인 사건",
        "category": "MURDER",
        "title_ko": "치과의사 모녀 살인 사건",
        "year": 1995,
        "hook": "범인의 침착함, 완벽한 알리바이 공작",
    },
    {
        "namu_title": "포천 여중생 납치 살인 사건",
        "category": "MURDER",
        "title_ko": "포천 여중생 납치 살인 사건",
        "year": 2003,
        "hook": "CCTV에 잡힌 범인, 그러나 끝내 미검거",
    },
    {
        "namu_title": "가평 박윤미 살인 사건",
        "category": "MURDER",
        "title_ko": "가평 박윤미 살인 사건",
        "year": 2004,
        "hook": "예비 초등교사의 의문의 죽음, 강호순 여죄 의혹",
    },
    {
        "namu_title": "대전 법동 아파트 살인 사건",
        "category": "MURDER",
        "title_ko": "대전 법동 아파트 살인 사건",
        "year": 2006,
        "hook": "CCTV에 찍힌 용의자, 현장엔 단서가 없었다",
    },
    {
        "namu_title": "이태원 살인 사건",
        "category": "MURDER",
        "title_ko": "이태원 살인 사건",
        "year": 1997,
        "hook": "두 명의 용의자, 서로를 범인으로 지목하다",
        "movie": "이태원 살인사건",
    },
    {
        "namu_title": "약촌오거리 살인 사건",
        "category": "MURDER",
        "title_ko": "약촌오거리 살인 사건",
        "year": 2000,
        "hook": "택시기사 피살, 엉뚱한 사람이 누명을 쓰다",
    },
    {
        "namu_title": "수원 노숙자 연쇄살인 사건",
        "category": "MURDER",
        "title_ko": "수원 노숙자 연쇄살인 사건",
        "year": 1994,
        "hook": "12명의 노숙자가 같은 방식으로 살해됐다",
    },
    # ========== 의문사 (SUSPICIOUS_DEATH) ==========
    {
        "namu_title": "듀스 김성재 의문사 사건",
        "category": "SUSPICIOUS_DEATH",
        "title_ko": "듀스 김성재 의문사 사건",
        "year": 1995,
        "hook": "시신에서 검출된 동물 마취제, 무죄 판결받은 여자친구",
    },
    {
        "namu_title": "장자연 사건",
        "category": "SUSPICIOUS_DEATH",
        "title_ko": "장자연 사건",
        "year": 2009,
        "hook": "31명의 이름이 적힌 문건, 사라진 통화기록",
    },
    {
        "namu_title": "제종철 의문사 사건",
        "category": "SUSPICIOUS_DEATH",
        "title_ko": "제종철 의문사 사건",
        "year": 2003,
        "hook": "촛불집회를 이끌던 청년, 철로 위에서 발견되다",
    },
    {
        "namu_title": "이한영 피살 사건",
        "category": "SUSPICIOUS_DEATH",
        "title_ko": "이한영 피살 사건",
        "year": 1997,
        "hook": "김정일의 조카, 한국에서 피습당하다",
    },
    {
        "namu_title": "박원순 사망 사건",
        "category": "SUSPICIOUS_DEATH",
        "title_ko": "박원순 사망 사건",
        "year": 2020,
        "hook": "서울시장의 실종과 사망, 미투 의혹",
    },
    {
        "namu_title": "용산 철거민 참사",
        "category": "SUSPICIOUS_DEATH",
        "title_ko": "용산 철거민 참사",
        "year": 2009,
        "hook": "25시간의 대치, 6명의 죽음",
    },
    # ========== 실종 (MISSING) ==========
    {
        "namu_title": "우정선 실종 사건",
        "category": "MISSING",
        "title_ko": "우정선 실종 사건",
        "year": 2003,
        "hook": "5살 소녀의 실종, 20년 후 발견된 유골은 다른 사람",
    },
    {
        "namu_title": "송혜희 실종 사건",
        "category": "MISSING",
        "title_ko": "송혜희 실종 사건",
        "year": 1999,
        "hook": "졸업을 앞둔 고3 여학생, 흔적도 없이 사라지다",
    },
    {
        "namu_title": "윤영실 실종 사건",
        "category": "MISSING",
        "title_ko": "윤영실 실종 사건",
        "year": 1985,
        "hook": "전두환 정권의 희생양이라는 설",
    },
    {
        "namu_title": "조하늘 실종 사건",
        "category": "MISSING",
        "title_ko": "조하늘 실종 사건",
        "year": 1995,
        "hook": "서울 구로구에서 사라진 어린이",
    },
    {
        "namu_title": "안산 어린이 실종 사건",
        "category": "MISSING",
        "title_ko": "안산 어린이 실종 사건",
        "year": 2001,
        "hook": "집 앞에서 놀다 사라진 5살",
    },
    {
        "namu_title": "한강 의대생 실종 사건",
        "category": "MISSING",
        "title_ko": "한강 의대생 실종 사건",
        "year": 2021,
        "hook": "한강에서 발견된 의대생, CCTV 사각지대 논란",
    },
    {
        "namu_title": "합천 통닭집 부부 실종 사건",
        "category": "MISSING",
        "title_ko": "합천 통닭집 부부 실종 사건",
        "year": 2010,
        "hook": "부부가 동시에 사라졌다, 시신 없는 살인 의혹",
    },
    {
        "namu_title": "칠곡 모텔사장 신부 실종 사건",
        "category": "MISSING",
        "title_ko": "칠곡 모텔사장 신부 실종 사건",
        "year": 2009,
        "hook": "결혼 당일 사라진 신부",
    },
    # ========== 집단 사건 (MASS_INCIDENT) ==========
    {
        "namu_title": "오대양 집단자살 사건",
        "category": "MASS_INCIDENT",
        "title_ko": "오대양 집단 자살 사건",
        "year": 1987,
        "hook": "천장 위에서 발견된 32구의 시신, 타살 의혹",
    },
    {
        "namu_title": "안양 초등생 유괴 살인 사건",
        "category": "MASS_INCIDENT",
        "title_ko": "안양 초등생 유괴 살인 사건",
        "year": 2007,
        "hook": "학교 앞에서 사라진 두 소녀, 범인은 10년 후 잡혔다",
        "solved": True,
    },
    {
        "namu_title": "밀양 여중생 집단 성폭행 사건",
        "category": "MASS_INCIDENT",
        "title_ko": "밀양 여중생 집단 성폭행 사건",
        "year": 2004,
        "hook": "44명의 가해자, 처벌은 거의 없었다",
    },
    # ========== 대형 참사 (DISASTER) ==========
    {
        "namu_title": "청해진해운 세월호 침몰 사고",
        "category": "DISASTER",
        "title_ko": "세월호 참사",
        "year": 2014,
        "hook": "304명의 희생, 아직도 밝혀지지 않은 침몰 원인",
    },
    {
        "namu_title": "삼풍백화점 붕괴 사고",
        "category": "DISASTER",
        "title_ko": "삼풍백화점 붕괴 사고",
        "year": 1995,
        "hook": "502명 사망, 17일 만에 구조된 기적의 생존자",
    },
    {
        "namu_title": "성수대교 붕괴 사고",
        "category": "DISASTER",
        "title_ko": "성수대교 붕괴 사고",
        "year": 1994,
        "hook": "출근길에 무너진 다리, 32명의 희생",
    },
    {
        "namu_title": "대구 지하철 참사",
        "category": "DISASTER",
        "title_ko": "대구 지하철 참사",
        "year": 2003,
        "hook": "방화범의 휘발유, 192명이 불타 죽었다",
    },
    {
        "namu_title": "이태원 압사 사고",
        "category": "DISASTER",
        "title_ko": "이태원 참사",
        "year": 2022,
        "hook": "좁은 골목에서 159명이 압사, 누구의 책임인가",
    },
    # ========== 연쇄 살인 (SERIAL) - 해결되었으나 미스테리 요소 ==========
    {
        "namu_title": "유영철",
        "category": "SERIAL",
        "title_ko": "유영철 연쇄살인 사건",
        "year": "2003-2004",
        "hook": "20명을 살해한 '인면수심', 머리를 먹었다는 진술",
        "solved": True,
    },
    {
        "namu_title": "정남규(범죄자)",
        "category": "SERIAL",
        "title_ko": "정남규 연쇄살인 사건",
        "year": "2004-2006",
        "hook": "유영철로 오인받은 또 다른 연쇄살인마",
        "solved": True,
    },
    {
        "namu_title": "강호순",
        "category": "SERIAL",
        "title_ko": "강호순 연쇄살인 사건",
        "year": "2006-2008",
        "hook": "8명을 죽이고 시신을 불태운 남자",
        "solved": True,
    },
    {
        "namu_title": "김대두",
        "category": "SERIAL",
        "title_ko": "김대두 연쇄살인 사건",
        "year": 1975,
        "hook": "대한민국 최초의 연쇄살인마, 2개월간 17명 살해",
        "solved": True,
    },
    {
        "namu_title": "정두영(범죄자)",
        "category": "SERIAL",
        "title_ko": "정두영 연쇄살인 사건",
        "year": "2003-2006",
        "hook": "서울 강북 연쇄살인, 12명 살해",
        "solved": True,
    },
    # ========== 도시전설 (URBAN_LEGEND) ==========
    {
        "namu_title": "곤지암 남양정신병원",
        "category": "URBAN_LEGEND",
        "title_ko": "곤지암 정신병원",
        "year": 1996,
        "hook": "CNN 선정 세계 7대 소름끼치는 장소",
        "movie": "곤지암",
    },
    {
        "namu_title": "장산범",
        "category": "URBAN_LEGEND",
        "title_ko": "장산범",
        "year": None,
        "hook": "부산 장산에서 사람을 유인하는 정체불명의 존재",
        "movie": "장산범",
    },
    {
        "namu_title": "자유로 귀신",
        "category": "URBAN_LEGEND",
        "title_ko": "자유로 귀신 택시",
        "year": None,
        "hook": "늦은 밤 택시에 타는 여자, 뒷좌석에서 사라지다",
    },
    {
        "namu_title": "홍콩할매귀신",
        "category": "URBAN_LEGEND",
        "title_ko": "홍콩 할매 귀신",
        "year": "1990s",
        "hook": "'나 예뻐?' 물어보는 빨간 마스크의 여자",
    },
    {
        "namu_title": "분홍 신발 귀신",
        "category": "URBAN_LEGEND",
        "title_ko": "분홍 신발 귀신",
        "year": None,
        "hook": "분홍 신발만 신으면 쫓아온다",
    },
    {
        "namu_title": "곡성(영화)",
        "category": "URBAN_LEGEND",
        "title_ko": "곡성의 미스테리",
        "year": None,
        "hook": "전라남도 곡성에서 일어난 기이한 현상들",
        "movie": "곡성",
    },
    {
        "namu_title": "63빌딩",
        "category": "URBAN_LEGEND",
        "title_ko": "여의도 63빌딩 귀신",
        "year": None,
        "hook": "건설 중 사망한 노동자들의 원혼",
    },
    {
        "namu_title": "경성대학교",
        "category": "URBAN_LEGEND",
        "title_ko": "경성대 폐건물 괴담",
        "year": None,
        "hook": "학교 폐건물에서 목격되는 여학생 귀신",
    },
]


# ============================================================
# 한국 미스테리 Opus 프롬프트 템플릿
# ============================================================

KR_MYSTERY_OPUS_PROMPT_TEMPLATE = """당신은 한국 실화/기록 기반 미스테리 전문 유튜브 채널의 대본 작가입니다.
아래 입력값과 자료 URL을 기반으로 허구 없이 사실 기반 내레이션 대본을 작성하세요.

==================================================
[INPUT — 사건 정보]
	•	제목: {title_ko}
	•	카테고리: {category}
	•	발생 연도: {year}
	•	한 줄 후킹 포인트(충격적 사실 1문장): {hook}

==================================================
[INPUT — 자료 수집 URL]  ★필수

아래 URL을 직접 열어 끝까지 읽고, 사실을 수집하세요.
	•	메인 자료(필수): {namu_url}

※ URL에 없는 내용은 절대 추가하지 마세요. 불확실하면 "자료에 명확히 나오지 않는다"라고 쓰세요.

==================================================
[자료 수집 항목]  (대본에 반드시 반영)
	1.	사건 전체 경위(시간순): 발생/발견/수사/결과
	2.	등장인물: 이름, 나이, 신분/직업, 역할
	3.	발견 증거: 현장 상태, 증거물, 단서
	4.	수사 과정과 결과: 조사 주체, 결론, 핵심 쟁점
	5.	제기된 이론들: 대표 가설 3~6개(각 가설의 근거/한계)
	6.	현재 상태: 해결/미해결 + 이후 재조사가 있다면 그 범위

==================================================
[작성 지침]

[톤/문체]
	•	미스터리/스릴러 분위기(과장·공포 조장 금지).
	•	자연스러운 한국어.
	•	팩트(인명/지명/날짜/수치)는 자료와 완전히 동일하게 유지.

==================================================
[팩트 vs 가설 구분 규칙]  ★매우 중요
	•	확정된 사실은 "기록에 따르면 / 조사 기록에는 / 발견 당시에는" 같은 표현으로 서술.
	•	가설은 반드시 "가설/추정/논쟁"임을 드러내고 단정 금지.
	•	가설을 소개할 때는 최소한의 근거 + 반론/한계를 같이 제시(균형 유지).
	•	특정 개인/집단을 범인으로 단정하거나 음모론을 사실처럼 서술 금지.

==================================================
[구조]
	1.	인트로(후킹): 한 줄 후킹 포인트로 시작. 결론 스포 금지.
	2.	사건의 시작: 배경/인물/상황 정리.
	3.	사건 전개: 시간순으로 상세.
	4.	미스터리 포인트: 설명되지 않는 지점을 '질문' 형태로 강조.
	5.	이론과 추측: 대표 가설 3~6개 정리(근거/한계).
	6.	현재 상태: 해결/미해결 + 이후 조사/연구(자료 범위 내).
	7.	아웃트로: 여운 + 시청자에게 질문 1개(댓글 유도는 가능, 구독 멘트는 금지).

==================================================
[이탈 방지 문장 삽입 규칙]  ★반드시 적용
	•	대본 흐름 속에 60~90초마다 1번 자연스럽게 삽입하세요.
	•	아래 문장 유형을 번갈아 쓰되, 같은 문장 반복 금지.
A) "그런데 여기서 이상한 점이 하나 있습니다."
B) "이 지점에서 기록이 딱 끊깁니다."
C) "문제는, 이 단서가 다른 단서와 맞지 않는다는 겁니다."
D) "보통은 여기서 결론을 내리는데, 아직 한 조각이 남아 있습니다."
E) "이 다음 장면이, 사건을 완전히 뒤집습니다."

==================================================
[금지사항]
	•	허구 추가 금지(대사/심리/장면 창작 금지)
	•	피해자 비하/조롱 금지
	•	잔혹/고어 디테일 묘사 금지
	•	과도한 공포 조장 금지
	•	"구독/좋아요/알림" 멘트 금지
	•	씬 구분/소제목/메타데이터/출처 목록/각주 표시 금지

==================================================
[출력 형식]
	•	대본 본문만 출력하세요.
	•	줄바꿈은 자연스럽게 하되, 제목/소제목/번호/구분선은 넣지 마세요.
"""


# ============================================================
# Opus 프롬프트 템플릿 (해외 미스테리)
# ============================================================

MYSTERY_OPUS_PROMPT_TEMPLATE = """당신은 해외 실화/기록 기반 미스터리 전문 유튜브 채널의 대본 작가입니다.
아래 입력값과 자료 URL을 기반으로 허구 없이 사실 기반 내레이션 대본을 작성하세요.

==================================================
[INPUT — 사건 정보]
	•	제목(한글): {title_ko}
	•	원제(영문): {title_en}
	•	카테고리: {category}  (예: 미스테리 현상 / 미제 사건 / 실종 / 의문사 / 초자연 논란 등)
	•	발생 연도: {year}
	•	발생 국가/지역: {country}
	•	한 줄 후킹 포인트(충격적 사실 1문장): {hook}

==================================================
[INPUT — 자료 수집 URL]  ★필수

아래 URL을 직접 열어 끝까지 읽고, 사실을 수집하세요.
	•	메인 자료(필수): {wiki_url}

※ URL에 없는 내용은 절대 추가하지 마세요. 불확실하면 "자료에 명확히 나오지 않는다"라고 쓰세요.

==================================================
[자료 수집 항목]  (대본에 반드시 반영)
	1.	사건 전체 경위(시간순): 출발/마지막 확인/실종/수색/발견/부검/조사
	2.	등장인물: 이름, 나이, 신분/직업/소속, 역할(리더 등)
	3.	발견 증거: 현장 상태, 기록(일지/사진/문서), 시신 발견 상황, 물적 단서
	4.	수사 과정과 결과: 조사 주체, 결론, 핵심 쟁점
	5.	제기된 이론들: 대표 가설 3~6개(각 가설의 근거/한계)
	6.	현재 상태: 해결/미해결 + 이후 재조사/연구가 있다면 그 범위(자료에 있는 만큼만)

==================================================
[작성 지침]

[톤/문체]
	•	미스터리/스릴러 분위기(과장·공포 조장 금지).
	•	한국 시청자가 듣기 편한 자연스러운 한국어(번역투 금지).
	•	팩트(인명/지명/날짜/수치)는 자료와 완전히 동일하게 유지.

[표기 규칙: 외국 인명/지명]
	•	첫 등장: 한글 음역 + (영문) 1회 병기
	•	이후: 한글만 사용
	•	예: 이고르 댜틀로프(Igor Dyatlov)

==================================================
[팩트 vs 가설 구분 규칙]  ★매우 중요
	•	확정된 사실은 "기록에 따르면 / 조사 기록에는 / 발견 당시에는" 같은 표현으로 서술.
	•	가설은 반드시 "가설/추정/논쟁"임을 드러내고 단정 금지.
	•	가설을 소개할 때는 최소한의 근거 + 반론/한계를 같이 제시(균형 유지).
	•	특정 개인/집단을 범인으로 단정하거나 음모론을 사실처럼 서술 금지.

==================================================
[구조]
	1.	인트로(후킹): 한 줄 후킹 포인트로 시작. 결론 스포 금지.
	2.	사건의 시작: 배경/인물/상황 정리.
	3.	사건 전개: 시간순(또는 발견순)으로 상세.
	4.	미스터리 포인트: 설명되지 않는 지점을 '질문' 형태로 강조.
	5.	이론과 추측: 대표 가설 3~6개 정리(근거/한계).
	6.	현재 상태: 해결/미해결 + 이후 조사/연구(자료 범위 내).
	7.	아웃트로: 여운 + 시청자에게 질문 1개(댓글 유도는 가능, 구독 멘트는 금지).

==================================================
[이탈 방지 문장 삽입 규칙]  ★반드시 적용
	•	대본 흐름 속에 60~90초마다 1번 자연스럽게 삽입하세요.
	•	아래 문장 유형을 번갈아 쓰되, 같은 문장 반복 금지.
A) "그런데 여기서 이상한 점이 하나 있습니다."
B) "이 지점에서 기록이 딱 끊깁니다."
C) "문제는, 이 단서가 다른 단서와 맞지 않는다는 겁니다."
D) "보통은 여기서 결론을 내리는데, 아직 한 조각이 남아 있습니다."
E) "이 다음 장면이, 사건을 완전히 뒤집습니다."
	•	삽입 문장은 자막/표시/라벨 없이, 그냥 내레이션 문장으로 녹이세요.

==================================================
[금지사항]
	•	허구 추가 금지(대사/심리/장면 창작 금지)
	•	피해자 비하/조롱 금지
	•	잔혹/고어 디테일 묘사 금지
	•	과도한 공포 조장 금지
	•	"구독/좋아요/알림" 멘트 금지
	•	씬 구분/소제목/메타데이터/출처 목록/각주 표시 금지

==================================================
[출력 형식]
	•	대본 본문만 출력하세요.
	•	줄바꿈은 자연스럽게 하되, 제목/소제목/번호/구분선은 넣지 마세요.
"""
