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

# 시트 이름 (기존 - 레거시)
MYSTERY_SHEET_NAME = "MYSTERY_OPUS_INPUT"

# 통합 시트 이름 (2024-12-20 신규)
UNIFIED_MYSTERY_SHEET = "MYSTERY"

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

# 통합 시트에 저장할 때 사용할 필드 순서
MYSTERY_OPUS_FIELDS = [
    "episode",          # 에피소드 번호
    "category",         # 카테고리
    "title_en",         # 영문 제목
    "title_ko",         # 한글 제목
    "wiki_url",         # 위키백과 URL
    "summary",          # 사건 요약
    "full_content",     # 전체 내용
    "opus_prompt",      # Opus 프롬프트
    "thumbnail_copy",   # 썸네일 문구
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

MYSTERY_OPUS_PROMPT_TEMPLATE = """당신은 해외 실화/기록 기반 미스터리 전문 유튜브 채널의 대본 작가입니다.
아래 입력값과 자료 URL을 기반으로 허구 없이 사실 기반 20분 분량 내레이션 대본을 작성하세요.

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

[분량]
	•	20분 분량(약 18,000자 내외).
	•	17,000자 미만이면: 수색/발견/부검/조사 파트를 더 촘촘히 확장하여 분량을 맞추세요.

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
