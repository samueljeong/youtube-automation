"""
한국사 자동화 파이프라인 설정

시대 흐름형 시리즈를 위한 설정 파일
- 고조선부터 대한제국까지 시대별 트랙 정의
- 각 시대별 수집 키워드 관리
- 시트 구조 및 제한 설정
"""

from typing import Dict, List, Any


# ============================================================
# 시대 트랙 설정 (순서 고정)
# ============================================================

# 시대 순서 (영문 키 사용) - 현대사까지 확장
ERA_ORDER: List[str] = [
    "GOJOSEON",      # 고조선
    "BUYEO",         # 부여/옥저/동예
    "SAMGUK",        # 삼국시대
    "NAMBUK",        # 남북국시대
    "GORYEO",        # 고려
    "JOSEON_EARLY",  # 조선 전기
    "JOSEON_LATE",   # 조선 후기
    "DAEHAN",        # 대한제국
    "JAPANESE_RULE", # 일제강점기
    "DIVISION",      # 분단과 한국전쟁
    "MODERN",        # 현대 대한민국
]

# 시대 메타데이터
ERAS: Dict[str, Dict[str, Any]] = {
    "GOJOSEON": {
        "name": "고조선",
        "name_en": "Gojoseon",
        "period": "BC 2333 ~ BC 108",
        "description": "한반도 최초의 국가, 단군조선과 위만조선",
        "active": True,
    },
    "BUYEO": {
        "name": "부여/옥저/동예",
        "name_en": "Buyeo Period",
        "period": "BC 2세기 ~ AD 494",
        "description": "고조선 멸망 후 등장한 여러 나라",
        "active": True,
    },
    "SAMGUK": {
        "name": "삼국시대",
        "name_en": "Three Kingdoms",
        "period": "BC 57 ~ AD 668",
        "description": "고구려, 백제, 신라의 경쟁과 발전",
        "active": True,
    },
    "NAMBUK": {
        "name": "남북국시대",
        "name_en": "North-South States",
        "period": "AD 698 ~ AD 926",
        "description": "통일신라와 발해의 병존",
        "active": True,
    },
    "GORYEO": {
        "name": "고려",
        "name_en": "Goryeo Dynasty",
        "period": "AD 918 ~ AD 1392",
        "description": "왕건의 건국부터 조선 건국까지",
        "active": True,
    },
    "JOSEON_EARLY": {
        "name": "조선 전기",
        "name_en": "Early Joseon",
        "period": "AD 1392 ~ AD 1592",
        "description": "조선 건국부터 임진왜란 이전",
        "active": True,
    },
    "JOSEON_LATE": {
        "name": "조선 후기",
        "name_en": "Late Joseon",
        "period": "AD 1592 ~ AD 1897",
        "description": "임진왜란 이후부터 대한제국 선포 이전",
        "active": True,
    },
    "DAEHAN": {
        "name": "대한제국",
        "name_en": "Korean Empire",
        "period": "AD 1897 ~ AD 1910",
        "description": "근대화 시도와 국권 상실",
        "active": True,
    },
    "JAPANESE_RULE": {
        "name": "일제강점기",
        "name_en": "Japanese Colonial Period",
        "period": "AD 1910 ~ AD 1945",
        "description": "일본 식민 지배와 독립운동",
        "active": True,
    },
    "DIVISION": {
        "name": "분단과 한국전쟁",
        "name_en": "Division and Korean War",
        "period": "AD 1945 ~ AD 1953",
        "description": "해방, 분단, 한국전쟁",
        "active": True,
    },
    "MODERN": {
        "name": "현대 대한민국",
        "name_en": "Modern South Korea",
        "period": "AD 1953 ~ 현재",
        "description": "산업화, 민주화, 경제 발전",
        "active": True,
    },
}


# ============================================================
# 시대별 수집 키워드
# ============================================================

ERA_KEYWORDS: Dict[str, Dict[str, List[str]]] = {
    "GOJOSEON": {
        "primary": [
            "고조선", "단군", "단군왕검", "아사달", "위만조선", "위만",
            "기자조선", "조선", "요동", "왕검성", "고조선 멸망",
        ],
        "secondary": [
            "청동기", "비파형동검", "고인돌", "미송리식토기",
            "한사군", "낙랑군", "8조법", "팔조법금",
        ],
        "exclude": [
            "북한", "김정은", "조선일보", "조선시대",  # 현대 조선 관련 제외
        ],
    },
    "BUYEO": {
        "primary": [
            "부여", "동부여", "북부여", "옥저", "동예", "삼한",
            "마한", "진한", "변한", "예맥", "영고", "동맹", "무천",
        ],
        "secondary": [
            "철기문화", "순장", "형사취수", "1책12법", "제천행사",
            "소도", "천군", "별읍",
        ],
        "exclude": [],
    },
    "SAMGUK": {
        "primary": [
            "고구려", "백제", "신라", "가야", "삼국시대",
            "광개토대왕", "장수왕", "근초고왕", "진흥왕", "법흥왕",
            "을지문덕", "살수대첩", "계백", "김유신", "연개소문",
        ],
        "secondary": [
            "불교 수용", "삼국사기", "삼국유사", "고분벽화",
            "첨성대", "황룡사", "무령왕릉", "호우명그릇",
            "나제동맹", "삼국통일", "당나라",
        ],
        "exclude": [],
    },
    "NAMBUK": {
        "primary": [
            "통일신라", "발해", "남북국", "대조영", "무왕", "문왕",
            "원성왕", "신문왕", "경덕왕", "해동성국",
        ],
        "secondary": [
            "9주5소경", "골품제", "선종", "화엄종", "석굴암", "불국사",
            "장보고", "청해진", "호족", "6두품", "정혜쌍수",
        ],
        "exclude": [],
    },
    "GORYEO": {
        "primary": [
            "고려", "왕건", "광종", "성종", "현종", "문종",
            "공민왕", "무신정권", "최충헌", "삼별초",
            "몽골침입", "원간섭기", "권문세족",
        ],
        "secondary": [
            "과거제도", "팔만대장경", "직지심체요절", "고려청자",
            "상감청자", "개경", "벽란도", "대몽항쟁",
            "삼국사기", "삼국유사", "묘청의 난",
        ],
        "exclude": [],
    },
    "JOSEON_EARLY": {
        "primary": [
            "조선 건국", "이성계", "태조", "태종", "세종대왕",
            "세조", "성종", "연산군", "중종", "명종",
            "훈민정음", "집현전", "경국대전",
        ],
        "secondary": [
            "사림", "훈구", "사화", "무오사화", "갑자사화", "기묘사화",
            "을사사화", "향약", "서원", "성리학", "조광조",
            "경복궁", "창덕궁", "한양",
        ],
        "exclude": [],
    },
    "JOSEON_LATE": {
        "primary": [
            "임진왜란", "정유재란", "병자호란", "인조반정",
            "영조", "정조", "실학", "정약용", "김정희",
            "세도정치", "흥선대원군", "개화", "강화도조약",
        ],
        "secondary": [
            "이순신", "거북선", "한산도대첩", "명량해전",
            "탕평책", "규장각", "수원화성", "천주교 박해",
            "동학", "갑오개혁", "을미사변",
        ],
        "exclude": [],
    },
    "DAEHAN": {
        "primary": [
            "대한제국", "광무개혁", "고종", "순종",
            "을사조약", "헤이그 특사", "군대 해산",
            "안중근", "의병", "국권피탈", "경술국치",
        ],
        "secondary": [
            "독립협회", "만민공동회", "대한매일신보", "황성신문",
            "신민회", "애국계몽운동", "근대화", "철도", "전기",
            "이토 히로부미", "통감부", "일제강점",
        ],
        "exclude": [],
    },
    "JAPANESE_RULE": {
        "primary": [
            "일제강점기", "3.1운동", "대한민국임시정부", "독립운동",
            "김구", "안창호", "윤봉길", "이봉창", "유관순",
            "무단통치", "문화통치", "민족말살정책",
        ],
        "secondary": [
            "토지조사사업", "산미증식계획", "창씨개명", "징용", "위안부",
            "신간회", "광주학생운동", "봉오동전투", "청산리대첩",
            "한글학회", "브나로드운동",
        ],
        "exclude": [],
    },
    "DIVISION": {
        "primary": [
            "해방", "8.15", "미군정", "소군정", "38선",
            "대한민국 정부수립", "조선민주주의인민공화국",
            "한국전쟁", "6.25", "인천상륙작전", "흥남철수", "휴전",
        ],
        "secondary": [
            "이승만", "김일성", "김구", "여운형",
            "좌우합작", "반탁운동", "5.10 총선거",
            "낙동강방어선", "중국군참전", "유엔군", "판문점",
        ],
        "exclude": [],
    },
    "MODERN": {
        "primary": [
            "이승만", "4.19혁명", "박정희", "5.16", "유신",
            "전두환", "5.18", "광주민주화운동", "6월항쟁",
            "김영삼", "김대중", "노무현", "IMF", "촛불집회",
        ],
        "secondary": [
            "경제개발5개년계획", "새마을운동", "한강의기적",
            "88올림픽", "2002월드컵", "민주화", "대통령직선제",
            "금융위기", "IT강국", "K-POP", "한류",
        ],
        "exclude": [],
    },
}


# ============================================================
# 🎯 주제 기반 에피소드 구조 (HISTORY_TOPICS)
# ============================================================
# 핵심: 각 시대를 명확한 주제로 분할
# - 중복 없이 각 에피소드가 다른 내용을 다룸
# - 각 주제에 맞는 검색 키워드와 참고 링크 포함

HISTORY_TOPICS: Dict[str, List[Dict[str, Any]]] = {
    "GOJOSEON": [
        {
            "episode": 1,
            "title": "단군, 최초의 나라를 세우다",
            "topic": "단군 건국 신화",
            "keywords": ["단군", "단군왕검", "아사달", "홍익인간", "환웅", "고조선 건국"],
            "reference_links": [
                "https://encykorea.aks.ac.kr/Article/E0003937",  # 고조선
                "https://encykorea.aks.ac.kr/Article/E0013554",  # 단군조선
            ],
            "description": "BC 2333년 단군왕검의 건국, 홍익인간 이념, 건국 신화의 의미",
        },
        {
            "episode": 2,
            "title": "비파형동검과 고인돌 - 고조선의 흔적",
            "topic": "청동기 문화",
            "keywords": ["비파형동검", "고인돌", "청동기", "미송리식토기", "탁자식고인돌"],
            "reference_links": [
                "https://encykorea.aks.ac.kr/Article/E0025256",  # 비파형동검
                "https://encykorea.aks.ac.kr/Article/E0003901",  # 고인돌
            ],
            "description": "고조선의 영역을 보여주는 청동기 유물, 고인돌 분포와 의미",
        },
        {
            "episode": 3,
            "title": "8조법 - 고조선은 어떤 사회였나",
            "topic": "8조법과 사회 구조",
            "keywords": ["8조법", "팔조법금", "범금8조", "고조선 사회", "고조선 법률"],
            "reference_links": [
                "https://encykorea.aks.ac.kr/Article/E0054321",  # 범금8조
            ],
            "description": "현재 전해지는 3개 조항, 고조선 사회의 법과 질서",
        },
        {
            "episode": 4,
            "title": "위만, 고조선을 탈취하다",
            "topic": "위만조선",
            "keywords": ["위만", "위만조선", "기자조선", "철기문화", "중계무역"],
            "reference_links": [
                "https://encykorea.aks.ac.kr/Article/E0062916",  # 위만조선
            ],
            "description": "위만의 집권 과정, 철기 문화 도입, 한과의 중계무역",
        },
        {
            "episode": 5,
            "title": "왕검성 함락, 고조선의 최후",
            "topic": "고조선 멸망과 한사군",
            "keywords": ["왕검성", "고조선 멸망", "한사군", "낙랑군", "BC 108년"],
            "reference_links": [
                "https://encykorea.aks.ac.kr/Article/E0003937",  # 고조선
                "https://encykorea.aks.ac.kr/Article/E0035086",  # 한사군
            ],
            "description": "한 무제의 침략, 왕검성 함락, 한사군 설치와 그 이후",
        },
    ],
    "BUYEO": [
        {
            "episode": 1,
            "title": "부여, 고조선을 잇다",
            "topic": "부여 건국과 성장",
            "keywords": ["부여", "동부여", "북부여", "부여 건국", "해모수"],
            "reference_links": [
                "https://encykorea.aks.ac.kr/Article/E0023904",  # 부여
            ],
            "description": "부여의 건국, 위치, 고조선 이후 만주의 새 강자",
        },
        {
            "episode": 2,
            "title": "영고 - 하늘에 제사를 지내다",
            "topic": "부여의 제천행사와 사회",
            "keywords": ["영고", "제천행사", "5부", "마가", "우가", "사출도"],
            "reference_links": [
                "https://encykorea.aks.ac.kr/Article/E0038206",  # 영고
            ],
            "description": "12월 영고 축제, 5부족 연맹체 구조, 부여의 사회 제도",
        },
        {
            "episode": 3,
            "title": "옥저와 동예 - 작은 나라들의 삶",
            "topic": "옥저, 동예, 삼한",
            "keywords": ["옥저", "동예", "삼한", "마한", "진한", "변한", "민며느리제", "책화"],
            "reference_links": [
                "https://encykorea.aks.ac.kr/Article/E0038898",  # 옥저
                "https://encykorea.aks.ac.kr/Article/E0014689",  # 동예
            ],
            "description": "옥저의 민며느리제, 동예의 책화, 삼한의 소도와 천군",
        },
        {
            "episode": 4,
            "title": "철기와 새로운 시대의 시작",
            "topic": "철기 문화와 삼국 태동",
            "keywords": ["철기문화", "철기시대", "삼한", "소도", "천군", "삼국 태동"],
            "reference_links": [
                "https://encykorea.aks.ac.kr/Article/E0055768",  # 철기문화
            ],
            "description": "철기 보급이 가져온 변화, 삼국시대로 이어지는 흐름",
        },
    ],
    "SAMGUK": [
        {
            "episode": 1,
            "title": "고구려, 동북아의 강자로 떠오르다",
            "topic": "고구려 건국과 성장",
            "keywords": ["고구려", "주몽", "동명성왕", "졸본", "국내성", "태조왕"],
            "reference_links": [
                "https://encykorea.aks.ac.kr/Article/E0003369",  # 고구려
            ],
            "description": "주몽의 건국, 졸본에서 국내성으로, 정복 국가로의 성장",
        },
        {
            "episode": 2,
            "title": "백제, 바다를 지배하다",
            "topic": "백제 건국과 전성기",
            "keywords": ["백제", "온조", "근초고왕", "칠지도", "해상왕국", "한성백제"],
            "reference_links": [
                "https://encykorea.aks.ac.kr/Article/E0021778",  # 백제
            ],
            "description": "온조의 건국, 근초고왕의 전성기, 해상 무역과 일본과의 관계",
        },
        {
            "episode": 3,
            "title": "신라, 늦게 출발한 승자",
            "topic": "신라 건국과 발전",
            "keywords": ["신라", "박혁거세", "화백회의", "골품제", "법흥왕", "진흥왕"],
            "reference_links": [
                "https://encykorea.aks.ac.kr/Article/E0031423",  # 신라
            ],
            "description": "박혁거세의 건국, 6부 체제, 불교 수용과 왕권 강화",
        },
        {
            "episode": 4,
            "title": "광개토대왕, 동북아를 호령하다",
            "topic": "광개토대왕의 정복 전쟁",
            "keywords": ["광개토대왕", "광개토왕릉비", "영락대왕", "고구려 전성기", "정복전쟁"],
            "reference_links": [
                "https://encykorea.aks.ac.kr/Article/E0004064",  # 광개토왕
            ],
            "description": "광개토대왕의 정복 전쟁, 64성 1400촌, 광개토왕릉비",
        },
        {
            "episode": 5,
            "title": "가야, 철의 왕국",
            "topic": "가야 연맹",
            "keywords": ["가야", "금관가야", "대가야", "철", "김수로왕", "가야연맹"],
            "reference_links": [
                "https://encykorea.aks.ac.kr/Article/E0000243",  # 가야
            ],
            "description": "가야 연맹의 형성, 철 생산과 무역, 신라에 병합되기까지",
        },
        {
            "episode": 6,
            "title": "을지문덕과 살수대첩",
            "topic": "고구려의 대외 전쟁",
            "keywords": ["을지문덕", "살수대첩", "수나라", "612년", "고구려 방어전"],
            "reference_links": [
                "https://encykorea.aks.ac.kr/Article/E0038279",  # 을지문덕
            ],
            "description": "수나라 113만 대군, 을지문덕의 전략, 살수대첩의 승리",
        },
        {
            "episode": 7,
            "title": "삼국 문화의 꽃",
            "topic": "삼국시대 문화",
            "keywords": ["삼국문화", "고분벽화", "황룡사", "첨성대", "무령왕릉", "불교미술"],
            "reference_links": [
                "https://encykorea.aks.ac.kr/Article/E0003369",  # 고구려
            ],
            "description": "고구려 고분벽화, 백제의 우아함, 신라의 금관과 첨성대",
        },
        {
            "episode": 8,
            "title": "삼국통일, 승자는 신라",
            "topic": "삼국 통일 전쟁",
            "keywords": ["삼국통일", "나당연합", "백제멸망", "고구려멸망", "김유신", "매소성전투"],
            "reference_links": [
                "https://encykorea.aks.ac.kr/Article/E0027269",  # 삼국통일
            ],
            "description": "나당연합, 백제와 고구려 멸망, 당 축출과 통일 완성",
        },
    ],
    "NAMBUK": [
        {
            "episode": 1,
            "title": "통일신라, 새로운 질서를 세우다",
            "topic": "통일신라 체제 정비",
            "keywords": ["통일신라", "신문왕", "9주5소경", "국학", "녹읍폐지"],
            "reference_links": [
                "https://encykorea.aks.ac.kr/Article/E0052917",  # 통일신라
            ],
            "description": "신문왕의 개혁, 9주 5소경 체제, 귀족 세력 억제",
        },
        {
            "episode": 2,
            "title": "발해, 고구려를 잇다",
            "topic": "발해 건국과 발전",
            "keywords": ["발해", "대조영", "해동성국", "무왕", "문왕", "상경용천부"],
            "reference_links": [
                "https://encykorea.aks.ac.kr/Article/E0021471",  # 발해
            ],
            "description": "대조영의 건국, 무왕과 문왕의 전성기, 해동성국",
        },
        {
            "episode": 3,
            "title": "장보고, 바다의 왕",
            "topic": "해상 무역과 장보고",
            "keywords": ["장보고", "청해진", "해상왕", "당나라무역", "신라방"],
            "reference_links": [
                "https://encykorea.aks.ac.kr/Article/E0046704",  # 장보고
            ],
            "description": "청해진 설치, 동아시아 해상 무역 장악, 장보고의 최후",
        },
        {
            "episode": 4,
            "title": "신라 말기, 흔들리는 질서",
            "topic": "신라 쇠퇴와 호족",
            "keywords": ["신라말기", "호족", "골품제모순", "6두품", "선종", "원종애노의난"],
            "reference_links": [
                "https://encykorea.aks.ac.kr/Article/E0031423",  # 신라
            ],
            "description": "골품제의 모순, 호족의 성장, 농민 반란과 사회 혼란",
        },
        {
            "episode": 5,
            "title": "후삼국, 새로운 주인을 찾아서",
            "topic": "후삼국 시대",
            "keywords": ["후삼국", "견훤", "후백제", "궁예", "후고구려", "왕건", "태봉"],
            "reference_links": [
                "https://encykorea.aks.ac.kr/Article/E0062191",  # 후삼국
            ],
            "description": "견훤의 후백제, 궁예의 후고구려, 왕건의 등장",
        },
    ],
    "GORYEO": [
        {
            "episode": 1,
            "title": "왕건, 고려를 세우다",
            "topic": "고려 건국",
            "keywords": ["왕건", "고려건국", "후삼국통일", "훈요십조", "호족연합"],
            "reference_links": [
                "https://encykorea.aks.ac.kr/Article/E0003508",  # 고려
            ],
            "description": "왕건의 등장, 후삼국 통일, 호족 연합 정책과 훈요십조",
        },
        {
            "episode": 2,
            "title": "광종, 왕권을 세우다",
            "topic": "광종의 개혁",
            "keywords": ["광종", "노비안검법", "과거제", "왕권강화", "호족억압"],
            "reference_links": [
                "https://encykorea.aks.ac.kr/Article/E0004156",  # 광종
            ],
            "description": "노비안검법, 과거제 도입, 호족 세력 억제와 왕권 강화",
        },
        {
            "episode": 3,
            "title": "거란과의 전쟁",
            "topic": "거란 침입과 항쟁",
            "keywords": ["거란침입", "서희", "강감찬", "귀주대첩", "강동6주"],
            "reference_links": [
                "https://encykorea.aks.ac.kr/Article/E0004780",  # 귀주대첩
            ],
            "description": "서희의 외교담판, 강감찬의 귀주대첩, 거란 격퇴",
        },
        {
            "episode": 4,
            "title": "무신정권, 100년의 혼란",
            "topic": "무신정권",
            "keywords": ["무신정권", "정중부", "최충헌", "최우", "만적의난", "무신정변"],
            "reference_links": [
                "https://encykorea.aks.ac.kr/Article/E0019591",  # 무신정권
            ],
            "description": "1170년 무신정변, 최씨 무신정권 60년, 민중 봉기",
        },
        {
            "episode": 5,
            "title": "몽골 침략과 대몽항쟁",
            "topic": "몽골 침입과 항쟁",
            "keywords": ["몽골침입", "대몽항쟁", "삼별초", "팔만대장경", "강화천도"],
            "reference_links": [
                "https://encykorea.aks.ac.kr/Article/E0020005",  # 몽골침입
            ],
            "description": "7차례 몽골 침입, 강화도 천도, 팔만대장경 조판, 삼별초 항쟁",
        },
        {
            "episode": 6,
            "title": "고려의 마지막, 새 시대를 향해",
            "topic": "고려 멸망",
            "keywords": ["공민왕", "신돈", "위화도회군", "이성계", "고려멸망"],
            "reference_links": [
                "https://encykorea.aks.ac.kr/Article/E0003508",  # 고려
            ],
            "description": "공민왕의 개혁, 신진사대부 등장, 위화도 회군과 조선 건국",
        },
    ],
    "JOSEON_EARLY": [
        {
            "episode": 1,
            "title": "이성계, 조선을 열다",
            "topic": "조선 건국",
            "keywords": ["이성계", "조선건국", "한양천도", "정도전", "경복궁"],
            "reference_links": [
                "https://encykorea.aks.ac.kr/Article/E0046210",  # 조선
            ],
            "description": "위화도 회군, 조선 건국, 한양 천도와 경복궁 건설",
        },
        {
            "episode": 2,
            "title": "세종, 조선의 황금시대",
            "topic": "세종대왕",
            "keywords": ["세종대왕", "훈민정음", "집현전", "장영실", "측우기", "해시계"],
            "reference_links": [
                "https://encykorea.aks.ac.kr/Article/E0029593",  # 세종
            ],
            "description": "훈민정음 창제, 집현전 학자들, 과학 기술의 발전",
        },
        {
            "episode": 3,
            "title": "경국대전, 조선의 법을 세우다",
            "topic": "조선의 통치 체제",
            "keywords": ["경국대전", "6조", "의정부", "과거제", "양반제도", "성종"],
            "reference_links": [
                "https://encykorea.aks.ac.kr/Article/E0002629",  # 경국대전
            ],
            "description": "경국대전 완성, 6조 체제, 과거제와 양반 사회 확립",
        },
        {
            "episode": 4,
            "title": "사화, 피로 물든 정치",
            "topic": "사화와 사림",
            "keywords": ["사화", "무오사화", "갑자사화", "기묘사화", "을사사화", "사림", "훈구"],
            "reference_links": [
                "https://encykorea.aks.ac.kr/Article/E0027012",  # 사화
            ],
            "description": "훈구파와 사림파의 대립, 4대 사화, 사림의 성장",
        },
        {
            "episode": 5,
            "title": "붕당의 시작",
            "topic": "붕당 정치",
            "keywords": ["붕당", "동인", "서인", "선조", "이황", "이이", "붕당정치"],
            "reference_links": [
                "https://encykorea.aks.ac.kr/Article/E0022714",  # 붕당
            ],
            "description": "동인과 서인의 분열, 붕당 정치의 시작, 공존과 갈등",
        },
        {
            "episode": 6,
            "title": "성리학, 조선의 사상",
            "topic": "성리학과 문화",
            "keywords": ["성리학", "이황", "이이", "서원", "향약", "유교문화"],
            "reference_links": [
                "https://encykorea.aks.ac.kr/Article/E0029705",  # 성리학
            ],
            "description": "이황과 이이, 조선 성리학의 발전, 서원과 향약",
        },
    ],
    "JOSEON_LATE": [
        {
            "episode": 1,
            "title": "임진왜란, 7년의 전쟁",
            "topic": "임진왜란",
            "keywords": ["임진왜란", "이순신", "한산도대첩", "거북선", "의병", "곽재우"],
            "reference_links": [
                "https://encykorea.aks.ac.kr/Article/E0045714",  # 임진왜란
            ],
            "description": "1592년 왜군 침략, 이순신의 해전, 의병의 활약, 전쟁의 상처",
        },
        {
            "episode": 2,
            "title": "병자호란, 삼전도의 굴욕",
            "topic": "병자호란",
            "keywords": ["병자호란", "인조", "삼전도", "남한산성", "소현세자", "청나라"],
            "reference_links": [
                "https://encykorea.aks.ac.kr/Article/E0022928",  # 병자호란
            ],
            "description": "1636년 청의 침략, 남한산성 항전, 삼전도 굴욕과 그 후유증",
        },
        {
            "episode": 3,
            "title": "영조와 정조, 개혁의 꿈",
            "topic": "영정조 시대",
            "keywords": ["영조", "정조", "탕평책", "규장각", "수원화성", "장용영"],
            "reference_links": [
                "https://encykorea.aks.ac.kr/Article/E0037774",  # 영조
                "https://encykorea.aks.ac.kr/Article/E0047490",  # 정조
            ],
            "description": "탕평책으로 붕당 완화, 정조의 규장각과 화성 건설",
        },
        {
            "episode": 4,
            "title": "실학, 새로운 학문의 물결",
            "topic": "실학",
            "keywords": ["실학", "정약용", "목민심서", "박지원", "열하일기", "김정희"],
            "reference_links": [
                "https://encykorea.aks.ac.kr/Article/E0031454",  # 실학
            ],
            "description": "실용을 추구한 학문, 정약용의 개혁론, 박지원의 북학",
        },
        {
            "episode": 5,
            "title": "세도정치, 부패의 시대",
            "topic": "세도정치",
            "keywords": ["세도정치", "안동김씨", "풍양조씨", "삼정문란", "홍경래의난", "민란"],
            "reference_links": [
                "https://encykorea.aks.ac.kr/Article/E0029633",  # 세도정치
            ],
            "description": "외척의 권력 독점, 삼정의 문란, 농민 봉기의 시대",
        },
        {
            "episode": 6,
            "title": "개항, 문이 열리다",
            "topic": "개항과 개화",
            "keywords": ["흥선대원군", "강화도조약", "개항", "위정척사", "개화파", "갑신정변"],
            "reference_links": [
                "https://encykorea.aks.ac.kr/Article/E0000437",  # 강화도조약
            ],
            "description": "흥선대원군의 쇄국정책, 강화도조약과 개항, 개화파의 등장",
        },
    ],
    "DAEHAN": [
        {
            "episode": 1,
            "title": "대한제국, 황제의 나라",
            "topic": "대한제국 선포",
            "keywords": ["대한제국", "고종", "광무개혁", "원수부", "황제즉위"],
            "reference_links": [
                "https://encykorea.aks.ac.kr/Article/E0012878",  # 대한제국
            ],
            "description": "1897년 대한제국 선포, 광무개혁, 근대화 시도",
        },
        {
            "episode": 2,
            "title": "을사조약, 빼앗긴 외교권",
            "topic": "을사조약과 저항",
            "keywords": ["을사조약", "을사늑약", "헤이그특사", "고종퇴위", "의병", "군대해산"],
            "reference_links": [
                "https://encykorea.aks.ac.kr/Article/E0038430",  # 을사조약
            ],
            "description": "1905년 을사조약, 헤이그 특사, 고종 강제 퇴위",
        },
        {
            "episode": 3,
            "title": "안중근, 총을 들다",
            "topic": "항일 의병과 의거",
            "keywords": ["안중근", "이토히로부미", "하얼빈", "의병", "항일투쟁"],
            "reference_links": [
                "https://encykorea.aks.ac.kr/Article/E0035195",  # 안중근
            ],
            "description": "전국적 의병 항쟁, 안중근의 하얼빈 의거, 동양평화론",
        },
        {
            "episode": 4,
            "title": "경술국치, 나라를 잃다",
            "topic": "국권 피탈",
            "keywords": ["경술국치", "한일합방", "국권피탈", "1910년", "일제강점"],
            "reference_links": [
                "https://encykorea.aks.ac.kr/Article/E0002605",  # 경술국치
            ],
            "description": "1910년 8월 29일, 대한제국 멸망과 일제 강점의 시작",
        },
    ],
    "JAPANESE_RULE": [
        {
            "episode": 1,
            "title": "무단통치, 총칼의 시대",
            "topic": "1910년대 무단통치",
            "keywords": ["무단통치", "조선총독부", "헌병경찰", "토지조사사업", "105인사건"],
            "reference_links": [
                "https://encykorea.aks.ac.kr/Article/E0019538",  # 무단통치
            ],
            "description": "헌병 경찰 통치, 토지조사사업, 조선인의 저항 탄압",
        },
        {
            "episode": 2,
            "title": "3.1운동, 대한독립만세",
            "topic": "3.1운동",
            "keywords": ["3.1운동", "기미독립선언", "유관순", "만세운동", "민족대표33인"],
            "reference_links": [
                "https://encykorea.aks.ac.kr/Article/E0027183",  # 3.1운동
            ],
            "description": "1919년 3월 1일, 전국적 만세운동, 유관순과 민중의 저항",
        },
        {
            "episode": 3,
            "title": "임시정부, 독립의 불씨",
            "topic": "대한민국 임시정부",
            "keywords": ["임시정부", "상하이", "김구", "이승만", "대한민국임시정부", "한인애국단"],
            "reference_links": [
                "https://encykorea.aks.ac.kr/Article/E0012884",  # 대한민국임시정부
            ],
            "description": "상하이 임시정부 수립, 독립운동의 구심점, 김구와 한인애국단",
        },
        {
            "episode": 4,
            "title": "무장투쟁, 총을 든 독립군",
            "topic": "무장독립운동",
            "keywords": ["봉오동전투", "청산리대첩", "김좌진", "홍범도", "독립군", "간도참변"],
            "reference_links": [
                "https://encykorea.aks.ac.kr/Article/E0055171",  # 청산리대첩
            ],
            "description": "봉오동 전투, 청산리 대첩, 만주 독립군의 활약",
        },
        {
            "episode": 5,
            "title": "민족말살정책, 지워지는 정체성",
            "topic": "민족말살정책",
            "keywords": ["민족말살", "창씨개명", "황국신민화", "신사참배", "조선어금지"],
            "reference_links": [
                "https://encykorea.aks.ac.kr/Article/E0055434",  # 창씨개명
            ],
            "description": "1930-40년대 황국신민화 정책, 창씨개명, 조선어 말살",
        },
        {
            "episode": 6,
            "title": "해방, 광복의 그날",
            "topic": "해방",
            "keywords": ["해방", "8.15", "광복", "1945년", "태평양전쟁종전"],
            "reference_links": [
                "https://encykorea.aks.ac.kr/Article/E0062025",  # 해방
            ],
            "description": "1945년 8월 15일, 35년 만의 해방, 그러나 분단의 시작",
        },
    ],
    "DIVISION": [
        {
            "episode": 1,
            "title": "해방, 그러나 분단",
            "topic": "해방과 분단",
            "keywords": ["해방", "미군정", "소군정", "38선", "분단", "신탁통치"],
            "reference_links": [
                "https://encykorea.aks.ac.kr/Article/E0062025",  # 해방
            ],
            "description": "해방의 기쁨과 38선 분단, 미소 군정, 좌우 대립",
        },
        {
            "episode": 2,
            "title": "두 개의 정부, 두 개의 길",
            "topic": "남북한 정부 수립",
            "keywords": ["대한민국", "조선민주주의인민공화국", "이승만", "김일성", "5.10총선"],
            "reference_links": [
                "https://encykorea.aks.ac.kr/Article/E0012874",  # 대한민국
            ],
            "description": "1948년 남북한 단독 정부 수립, 분단의 고착화",
        },
        {
            "episode": 3,
            "title": "6.25, 한반도를 휩쓴 전쟁",
            "topic": "한국전쟁",
            "keywords": ["한국전쟁", "6.25", "인천상륙작전", "맥아더", "낙동강", "중국군참전"],
            "reference_links": [
                "https://encykorea.aks.ac.kr/Article/E0060981",  # 한국전쟁
            ],
            "description": "1950년 6월 25일 북한 남침, 낙동강 방어선, 인천상륙작전, 중국군 개입",
        },
        {
            "episode": 4,
            "title": "휴전, 끝나지 않은 전쟁",
            "topic": "휴전과 그 후",
            "keywords": ["휴전", "판문점", "휴전협정", "1953년", "이산가족", "전쟁피해"],
            "reference_links": [
                "https://encykorea.aks.ac.kr/Article/E0060981",  # 한국전쟁
            ],
            "description": "1953년 휴전, 300만 사상자, 이산가족, 분단 고착화",
        },
    ],
    "MODERN": [
        {
            "episode": 1,
            "title": "이승만과 4.19혁명",
            "topic": "이승만 정권과 4.19",
            "keywords": ["이승만", "4.19혁명", "3.15부정선거", "학생혁명", "하야"],
            "reference_links": [
                "https://encykorea.aks.ac.kr/Article/E0054050",  # 4.19혁명
            ],
            "description": "이승만 장기집권, 3.15 부정선거, 학생혁명으로 무너진 정권",
        },
        {
            "episode": 2,
            "title": "박정희, 산업화의 빛과 그림자",
            "topic": "박정희 시대",
            "keywords": ["박정희", "5.16", "경제개발", "유신", "새마을운동", "한강의기적"],
            "reference_links": [
                "https://encykorea.aks.ac.kr/Article/E0021002",  # 박정희
            ],
            "description": "5.16 군사정변, 경제개발 5개년계획, 유신 체제, 10.26 최후",
        },
        {
            "episode": 3,
            "title": "5.18, 광주의 열흘",
            "topic": "광주민주화운동",
            "keywords": ["5.18", "광주민주화운동", "전두환", "12.12", "신군부", "계엄군"],
            "reference_links": [
                "https://encykorea.aks.ac.kr/Article/E0004146",  # 광주민주화운동
            ],
            "description": "1980년 5월 광주, 신군부의 폭력 진압, 민주화의 씨앗",
        },
        {
            "episode": 4,
            "title": "6월 항쟁, 민주주의를 외치다",
            "topic": "6월 민주항쟁",
            "keywords": ["6월항쟁", "민주화", "대통령직선제", "이한열", "박종철", "6.29선언"],
            "reference_links": [
                "https://encykorea.aks.ac.kr/Article/E0076061",  # 6월민주항쟁
            ],
            "description": "1987년 6월, 넥타이부대, 직선제 쟁취, 민주화의 승리",
        },
        {
            "episode": 5,
            "title": "IMF, 위기와 극복",
            "topic": "IMF 외환위기",
            "keywords": ["IMF", "외환위기", "금모으기", "구조조정", "1997년", "경제위기"],
            "reference_links": [
                "https://encykorea.aks.ac.kr/Article/E0073627",  # IMF
            ],
            "description": "1997년 외환위기, 국가부도 직전, 금모으기 운동, 구조조정의 아픔",
        },
        {
            "episode": 6,
            "title": "대한민국, 오늘을 향해",
            "topic": "21세기 대한민국",
            "keywords": ["2002월드컵", "촛불집회", "한류", "IT강국", "민주주의", "경제성장"],
            "reference_links": [
                "https://encykorea.aks.ac.kr/Article/E0012874",  # 대한민국
            ],
            "description": "2002 월드컵, 촛불시민혁명, K-문화, 세계 속의 대한민국",
        },
    ],
}


# ============================================================
# 수집 소스 설정 (뉴스가 아닌 전문 자료)
# ============================================================

SOURCE_TYPES = {
    "university": {
        "name": "대학 연구",
        "weight": 2.0,  # 신뢰도 가중치
    },
    "museum": {
        "name": "박물관/문화재청",
        "weight": 2.0,
    },
    "journal": {
        "name": "학술지/논문",
        "weight": 1.8,
    },
    "long_form": {
        "name": "전문 칼럼/분석",
        "weight": 1.5,
    },
    "encyclopedia": {
        "name": "백과사전/위키",
        "weight": 1.0,
    },
}

# 검색 쿼리 템플릿 (Google Custom Search용)
SEARCH_QUERY_TEMPLATES = [
    "{era_name} 역사",
    "{era_name} 연구",
    "{era_name} 유물 발굴",
    "{era_name} 문화재",
    "{keyword} 역사적 의의",
    "{keyword} 연구 논문",
]


# ============================================================
# Google Sheets 시트 구조
# ============================================================

# 시대별 시트 접두사 (시대 키와 조합)
# RAW/CANDIDATES는 시대별로 분리
SHEET_PREFIXES = {
    "RAW": "원문 수집 데이터",
    "CANDIDATES": "점수화된 후보",
    "ARCHIVE": "아카이브",
}

# OPUS 입력은 단일 통합 시트 (시대 무관하게 누적)
HISTORY_OPUS_INPUT_SHEET = "HISTORY_OPUS_INPUT"

# 각 시트의 헤더 정의
SHEET_HEADERS = {
    "RAW": [
        "collected_at",      # 수집 시간 (ISO)
        "era",               # 시대 키
        "source_type",       # university/museum/journal/long_form
        "source_name",       # 출처명
        "title",             # 자료 제목
        "url",               # URL
        "content_summary",   # 내용 요약
        "keywords",          # 감지된 키워드
        "hash",              # 중복 방지용 해시
    ],
    "CANDIDATES": [
        "run_id",            # 실행 날짜 (YYYY-MM-DD)
        "rank",              # 순위
        "era",               # 시대
        "topic",             # 주제 분류
        "score_total",       # 총점
        "score_relevance",   # 관련도
        "score_quality",     # 자료 품질
        "score_freshness",   # 신선도 (발굴/연구 최신성)
        "title",             # 제목
        "url",               # URL
        "summary",           # 요약
        "why_selected",      # 선정 근거
    ],
    # HISTORY_OPUS_INPUT (단일 통합 시트) 헤더
    # ⚠️ 패러다임: episode_slot은 순서가 아닌 슬롯 번호
    # ⚠️ code는 정렬/연결/중복판단 하지 않음 - 사고 재료 전달만
    "OPUS_INPUT": [
        "era",               # 시대 (고조선, 부여·옥저·동예, ...)
        "episode_slot",      # ★ 슬롯 번호 (1~6) - 순서 의미 ❌
        "structure_role",    # 형성기/제도기/변동기/유산기/연결기
        "core_question",     # 이 슬롯의 핵심 질문 (누가/어떻게/왜)
        "facts",             # 관찰 가능한 사실 (연도/사건 섞여도 OK)
        "human_choices",     # 인간의 선택 가능 지점 (행동/판단)
        "impact_candidates", # 구조 변화 후보 (결론 ❌, 재료 ⭕)
        "source_url",        # 출처 URL
        "opus_prompt_pack",  # ★ Opus에 붙여넣을 완제품
        "thumbnail_copy",    # 썸네일 문구 추천
        "status",            # 준비/완료
        "created_at",        # 생성 시간 (ISO)
    ],
}

# 준비 상태 유지 개수 (항상 이 개수만큼 '준비' 상태 유지)
# 매일 1개씩 영상 생성을 위해 1로 설정
PENDING_TARGET_COUNT = 1


# ============================================================
# 시트 제한 설정
# ============================================================

# 시트 행 제한
MAX_ROWS_PER_SHEET = 3000

# 아카이브 트리거 (이 비율 초과 시 아카이브)
ARCHIVE_THRESHOLD_RATIO = 0.9  # 90% = 2700행

# 아카이브 시 유지할 최신 행 수
ROWS_TO_KEEP_AFTER_ARCHIVE = 500


# ============================================================
# 점수화 설정
# ============================================================

# 관련도 점수 가중치
RELEVANCE_WEIGHTS = {
    "primary_keyword_in_title": 5,   # 제목에 주요 키워드
    "primary_keyword_in_content": 2, # 내용에 주요 키워드
    "secondary_keyword": 1,          # 보조 키워드
}

# 자료 품질 점수
QUALITY_WEIGHTS = {
    "university": 10,
    "museum": 10,
    "journal": 8,
    "long_form": 5,
    "encyclopedia": 3,
}

# TOP K 선정 수
DEFAULT_TOP_K = 5


# ============================================================
# LLM 설정
# ============================================================

# LLM 사용 여부 (환경변수로 오버라이드 가능)
LLM_ENABLED_DEFAULT = False

# LLM 호출 최소 점수 (비용 절감)
LLM_MIN_SCORE_DEFAULT = 0

# 기본 모델
LLM_MODEL_DEFAULT = "gpt-4o-mini"


# ============================================================
# 대본 분량 설정 (문자수 기준)
# ============================================================

# 15~20분 분량 = 13,650~18,200자 (한국어 TTS 기준 약 910자/분)
SCRIPT_LEN_MIN = 13650
SCRIPT_LEN_MAX = 18200
SCRIPT_DURATION_MIN = 15  # 분
SCRIPT_DURATION_MAX = 20  # 분


# ============================================================
# 한국사 전용 대본 지시문 템플릿
# ============================================================

SCRIPT_BRIEF_TEMPLATE = """[OPUS SCRIPT BRIEF]

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🧠 사고방식 (가장 중요 - 내용보다 우선)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
- 이 프롬프트는 '무엇을 말할지'가 아니라 '어떻게 생각할지'를 지시한다
- 에피소드 번호(n/6 등)는 역할을 의미하지 않는다
  → 역할은 [STRUCTURE ROLE] 필드에서 별도 명시됨
- 아래 자료/사실은 '참고 범위'이지 '정답'이 아니다
  → "이 자료를 중심으로 서술" ❌
  → "이 자료를 활용 가능" ⭕

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📌 분량 (필수)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
- 시간: 15~20분
- 문자수: 13,650~18,200자 (한국어 기준) ← 반드시 준수
- TTS 속도: 약 910자/분

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📌 톤
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
- 차분하고 담담한 다큐멘터리 톤
- 인물 중심 스토리텔링
- 짧은 문장 (1문장 40자 이내)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🚫 금지
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
- 연도/사건 나열식 설명
- 교과서 문체
- 민족주의/국뽕 표현 ("위대한", "찬란한", "자랑스러운", "민족 저항", "외세 침략", "자주 정신")
- 가치 판단 표현 ("~을 의미한다", "역사적 종말", "정체성")
- 중간요약 ("정리하면", "핵심은", "결론적으로", "즉")
- 훈계형 마무리 ("~해야 합니다", "~를 기억합시다")
- 시청자 직접 호칭 ("여러분", "우리 모두", "궁금하지 않은가?")

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⚠️ 강제 규칙: 60% 분기점 (목적 포함)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

[0% ~ 60%] 전반부 (약 9,000자)
📎 목적: 정보 이해를 위한 '인식 단계'
✅ 허용: 사실, 맥락, 인과, 개념 설명
❌ 금지: 행동, 감정, 공감 멘트, 생활 장면 묘사
→ 시청자가 '무슨 일이 있었는지' 파악하는 구간

[60% ~ 90%] 후반부 (약 4,500자)
📎 목적: 정보가 인간 선택으로 이어지는 '전개 단계'
✅ 허용: 행동, 느낌, 생활 장면
✅ 스토리텔링 강화, 인물 심리 묘사 가능
❌ 금지: 과장, 미화
→ 시청자가 '그래서 사람들은 어떻게 했는지' 느끼는 구간

[90% ~ 100%] 엔딩 (약 1,500자)
📎 목적: 다음으로 넘어가는 '연결 단계'
✅ 다음 시대로 연결되는 질문으로 끝내기
✅ 다음 영상 예고 한 줄
❌ 금지: 갑자기 훈훈해지거나 착해지는 결론
→ 시청자가 '다음이 궁금해지는' 구간
"""


# ============================================================
# 유틸리티 함수
# ============================================================

def get_era_sheet_name(prefix: str, era: str) -> str:
    """시대별 시트 이름 생성"""
    return f"{era}_{prefix}"


def get_archive_sheet_name(era: str, year: int) -> str:
    """아카이브 시트 이름 생성"""
    return f"{era}_ARCHIVE_{year}"


def get_active_eras() -> List[str]:
    """활성화된 시대 목록 반환"""
    return [era for era in ERA_ORDER if ERAS.get(era, {}).get("active", False)]


def get_era_keywords(era: str) -> Dict[str, List[str]]:
    """시대별 키워드 반환"""
    return ERA_KEYWORDS.get(era, {"primary": [], "secondary": [], "exclude": []})


# ============================================================
# 🚨 시리즈 정합성 규칙 (GLOBAL_SERIES_RULE)
# ============================================================
# 패러다임: 각 화는 '시간의 조각'이 아니라 '질문의 조각'이다
# 앞 화는 존재하지 않는다. 모든 화는 독립된 사고 실험이다.

GLOBAL_SERIES_RULE = """
════════════════════════════════════════════════════════════════
🚨 [GLOBAL SERIES RULE] 가장 중요한 전제 (다른 모든 규칙보다 우선)
════════════════════════════════════════════════════════════════

■ 핵심 패러다임: 이것은 연대기가 아니다
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
이 시리즈의 각 화는:
  ❌ 시간 순서로 이어지는 '사건의 조각'이 아니다
  ⭕ 같은 대상을 다른 각도로 보는 '질문의 조각'이다

비유: 조각상을 6방향에서 찍은 사진
  - 1장은 정면, 2장은 측면, 3장은 후면...
  - 각 사진은 독립적이지만, 같은 조각상을 담고 있다
  - 순서를 바꿔도 조각상은 변하지 않는다

■ 절대 규칙: 앞 화는 존재하지 않는다
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
❌ "1화에서 다뤘으니까..."
❌ "앞에서 설명한 것처럼..."
❌ "이어서..."
❌ "점점 진행되어..."
❌ "이미 다룬 내용이므로..."

⭕ 모든 화는 독립된 사고 실험
⭕ 각 화는 처음부터 완결된 하나의 에세이
⭕ 같은 연도/사건이 여러 화에 등장해도 된다 (관점만 다르면)

■ 에피소드 = 질문 (시간 순서 ❌, 사고 순서 ⭕)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
| 화 | 질문 (사고 프레임)                           |
|----|----------------------------------------------|
| 1  | "국가는 어떻게 생겨나는가?"                   |
| 2  | "국가는 어떻게 다스리는가?"                   |
| 3  | "법은 왜 필요한가?"                          |
| 4  | "질서가 흔들리면 사람들은 어떻게 움직이는가?"  |
| 5  | "국가가 사라져도 남는 것은 무엇인가?"         |
| 6  | "다음 시대는 무엇을 이어받는가?"              |

👉 BC 2333도 나오고, BC 108도 나오고, 8조법도 나오는 게 정상
👉 단, 같은 '사고'(질문에 대한 답)를 반복하면 안 됨

■ 사고 반복 vs 소재 반복
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⭕ 허용: 같은 소재, 다른 질문
  - 2화: "8조법이 어떻게 통치에 쓰였는가?"
  - 3화: "8조법은 왜 필요해졌는가?"

❌ 금지: 같은 질문, 같은 답
  - 2화: "8조법으로 사회가 안정되었다"
  - 3화: "8조법으로 사회가 안정되었다" (반복!)

■ 이 화의 질문에만 집중하라
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
- 입력된 STRUCTURE POINTS가 이 화의 질문과 맞지 않으면:
  → 해당 소재를 이 화의 질문에 맞게 재해석하거나
  → 사용하지 않음
- 예: 5화(유산기)에 '건국 연도' 소재가 있으면
  → "BC 2333년에 건국" ❌ (1화 질문)
  → "건국 시 만든 제도가 멸망 후에도 유지" ⭕ (5화 질문)

■ 구조적 금지 패턴 (반드시 준수)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
아래 패턴이 감지되면 즉시 수정:
❌ 시간 흐름 ("초기에는", "이후에는", "점차")
❌ 이전/이후 ("기존에는", "새로운 체제", "더 이상")
❌ 역사 인과 ("한계에 도달", "그 결과")
❌ 다음 화 전제 ("다음 화에서는", "이후 어떤")
❌ 번호 의미화 ("1화이므로", "마무리 화")
❌ 국가 일생 서사 (탄생→운영→혼란→붕괴→유산)
❌ FACTS에 해석 ("기여했다", "영향을 미쳤다")

→ 상세 규칙: FORBIDDEN_PATTERNS 참조

════════════════════════════════════════════════════════════════
"""


# ============================================================
# 🚨 에피소드 질문 정의 (EPISODE_QUESTIONS)
# ============================================================
# 에피소드 번호가 아니라 '질문'이 역할을 정의함

EPISODE_QUESTIONS = {
    1: {
        "question": "국가는 어떻게 생겨나는가?",
        "focus": "형성 과정, 초기 구조, 지배층 등장",
        "allowed": ["건국", "위치", "초기 구조", "지배층", "영역"],
        "forbidden": ["멸망", "붕괴", "쇠퇴", "다음 시대"],
    },
    2: {
        "question": "국가는 어떻게 다스리는가?",
        "focus": "통치 방식, 행정 체계, 권력 구조",
        "allowed": ["통치", "행정", "권력", "위계", "관직"],
        "forbidden": ["건국 신화", "멸망", "전투"],
    },
    3: {
        "question": "법은 왜 필요한가?",
        "focus": "법의 등장 배경, 사회적 필요, 갈등 해결",
        "allowed": ["법", "규칙", "관습", "갈등", "분쟁", "질서"],
        "forbidden": ["건국", "멸망", "전쟁"],
    },
    4: {
        "question": "질서가 흔들리면 사람들은 어떻게 움직이는가?",
        "focus": "변화의 순간, 선택의 강요, 이동과 적응",
        "allowed": ["변화", "이동", "선택", "혼란", "적응"],
        "forbidden": ["건국", "초기 구조", "안정"],
    },
    5: {
        "question": "국가가 사라져도 남는 것은 무엇인가?",
        "focus": "유산, 지속되는 방식, 제도의 잔존",
        "allowed": ["유산", "지속", "방식", "흔적", "계승"],
        "forbidden": ["건국", "전투", "멸망 사건 자체"],
    },
    6: {
        "question": "다음 시대는 무엇을 이어받는가?",
        "focus": "연결, 계승, 단절이 아닌 것",
        "allowed": ["연결", "계승", "재활용", "공백", "전환"],
        "forbidden": ["전투", "전쟁", "침략", "멸망 서술"],
    },
}


# ============================================================
# 🚨 BODY1_FACTS_ONLY 정의 (해석/평가 금지)
# ============================================================

BODY1_FACTS_ONLY_DEFINITION = """
════════════════════════════════════════════════════════════════
📋 [BODY1_FACTS_ONLY] 사실의 정의 - 이것만 허용
════════════════════════════════════════════════════════════════

■ FACT (사실) = 관찰 가능한 것
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✅ 연도: "BC 108년", "AD 918년"
✅ 존재 여부: "8조법이 존재했다", "왕검성이 있었다"
✅ 구조/형태: "5부로 구성되었다", "위계가 있었다"
✅ 수량/위치: "3개 조항이 전해진다", "요동 지역에 위치했다"
✅ 행위 (관찰 가능): "군대가 포위했다", "사람들이 이동했다"

■ FACT가 아닌 것 (절대 금지)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
❌ 영향: "~에 영향을 미쳤다", "변화를 가져왔다"
❌ 의미: "~을 의미한다", "역사적 종말", "정체성"
❌ 결과 해석: "안정에 기여했다", "기초를 마련했다"
❌ 의도 추측: "~하려 했다", "~을 결심했다", "강화하려 했다"
❌ 가치 판단: "위대하다", "중요하다", "의미 있었다"

■ 변환 예시
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
❌ "8조법 제정은 사회 안정에 기여했다" (평가)
⭕ "8조법 중 3개 조항이 현재까지 전해진다" (관찰)

❌ "왕은 영토 확장을 결심했다" (의도)
⭕ "BC 108년 한나라 군대가 왕검성을 포위했다" (행위)

❌ "저항이 계속 이어졌다" (해석)
⭕ "일부 세력이 남쪽으로 이동했다" (관찰)

❌ "역사적 종말을 맞이했다" (가치 판단)
⭕ "왕검성이 함락되었다" (사건)

════════════════════════════════════════════════════════════════
"""


# ============================================================
# 🚨 최종화(연결기) 전용 규칙
# ============================================================

FINAL_EPISODE_OVERRIDE = """
════════════════════════════════════════════════════════════════
🔒 [FINAL EPISODE OVERRIDE] 최종화 특수 규칙 (강제 적용)
════════════════════════════════════════════════════════════════

⚠️ 이 규칙은 다른 모든 규칙보다 우선함

■ 최종화(6번 슬롯)의 역할: 연결기
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
- 시대를 닫고, 다음 시대로 넘기는 슬롯
- 사건을 설명하지 않음 (이 슬롯의 질문은 "연결"이지 "사건"이 아님)
- 의미를 정리하고 방향을 남김

■ STRUCTURE POINTS 자동 필터링
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
입력된 STRUCTURE POINTS에 아래 단어 포함 시 → 해당 항목 무시:
❌ 전투, 전쟁, 침략, 포위, 함락, 멸망, 저항, 항쟁
❌ 군대, 공격, 방어, 점령

■ 최종화에서 허용되는 소재만 사용
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✅ 행정 공백: "중앙 통제가 사라진 후..."
✅ 지배 구조 해체: "기존 위계가 흩어지면서..."
✅ 사람들의 이동: "일부는 남쪽으로, 일부는..."
✅ 제도적 흔적: "그러나 통치 방식은 남았다..."
✅ 통치 감각 재활용: "이후 정치 집단들은 같은 방식을..."
✅ 다음 시대 자연 연결: "완전히 새로 시작된 것이 아니었다..."

■ 문장 형태 강제
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
모든 문장은 '상태 서술' 형태로 작성:
❌ "왕검성이 함락되었다" (사건)
⭕ "왕검성이 사라진 후, 행정 체계는 공백 상태가 되었다" (상태)

❌ "한나라가 침략했다" (사건)
⭕ "외부 세력이 들어온 후, 사람들은 선택을 해야 했다" (상태)

■ 최종화 금지 표현
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
❌ "그래서 우리는 배웠다"
❌ "의미 있었다"
❌ "역사에 남았다"
❌ "잊지 말아야 한다"
❌ "교훈을 준다"

⭕ "다음 시대는 이 위에서 시작되었다"
⭕ "완전한 단절은 아니었다"

════════════════════════════════════════════════════════════════
"""


# ============================================================
# 역할별 금지 키워드 (STRUCTURE POINTS 검증용)
# ============================================================

ROLE_FORBIDDEN_KEYWORDS = {
    "형성기": ["멸망", "붕괴", "함락", "패망", "쇠퇴", "한사군", "낙랑"],
    "제도기": ["건국", "단군", "신화", "멸망", "함락", "전투", "전쟁"],
    "변동기": ["건국", "탄생", "성립", "초기 구조", "위치 설명"],
    "유산기": ["건국", "탄생", "전투", "전쟁", "침략", "함락", "포위"],
    "연결기": ["전투", "전쟁", "침략", "포위", "함락", "멸망", "저항", "항쟁",
               "군대", "공격", "방어", "점령", "패배", "승리"],
}


# ============================================================
# 🚫 구조적 금지 패턴 (FORBIDDEN_PATTERNS)
# ============================================================
# AI가 가장 쉽게 사고를 망가뜨리는 지점들
# 이 패턴이 감지되면 즉시 수정 필요

FORBIDDEN_PATTERNS = """
════════════════════════════════════════════════════════════════
🚫 [FORBIDDEN PATTERNS] 구조적으로 절대 하면 안 되는 것들
════════════════════════════════════════════════════════════════

⚠️ 이 패턴들은 에피소드를 연대기로 오염시키는 구조적 결함임
⚠️ 감지 시 즉시 수정 필요

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1️⃣ 에피소드 내부에서 "시기·단계"를 전제로 서술
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
❌ 형성기 / 제도기 / 변동기라는 내부 시간 흐름처럼 서술
❌ "초기에는", "이후에는", "점차", "나중에" 같은 단계어 사용

이유: 에피소드는 시기 슬롯이 아니라 질문 슬롯
      '발전 단계' 인식이 들어가는 순간 연대기 오염

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

2️⃣ TURN·IMPACT가 "역사 진행"처럼 작동하는 구조
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
❌ TURN = 실제 역사적 전환점처럼 서술
❌ IMPACT = 다음 상태를 만들어낸 결과처럼 서술

위험 표현:
  ❌ "~하면서 한계에 도달했다"
  ❌ "그 결과 사회 구조가 바뀌었다"

이유: 이건 질문 전개가 아니라 역사 인과선
      에피소드 간 연결을 암시하게 됨

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

3️⃣ 같은 화 안에서 "이전/이후"가 존재하는 것처럼 말하기
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
❌ "기존에는", "이전 관습", "새로운 체제"
❌ "더 이상 ~로는 안 됐다"

이유: 화 내부에서도 before/after를 만들면 안 됨
      에피소드는 단면(slice)이어야 함, 타임라인이 아님

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

4️⃣ 질문이 아니라 "설명 과제"가 되는 구조
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
❌ "왜 필요했는가 → 그래서 만들어졌다"의 정답 구조
❌ 질문에 하나의 답을 수렴시키는 구성

이유: 에피소드 = 사고 실험
      열린 질문이어야지 결론 도출형이면 안 됨

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

5️⃣ 같은 질문에 같은 답을 다른 화에서 반복 가능하게 만드는 서술
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
❌ 1화·2화·3화에서 "인구 증가 → 분쟁 → 법 필요" 논리 반복

이유: 소재 중복은 허용, 사고 중복은 금지
      이 구조는 AI가 자동 취합할 때 가장 위험함

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

6️⃣ FACTS_ONLY 블록에 해석·평가가 섞이는 구조
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
❌ "기여했다 / 영향을 미쳤다 / 변화시켰다"
❌ "법치국가적 성격"

이유: 이건 문장 문제 이전에 블록 역할 붕괴
      BODY1이 '사실 레이어'가 아니라 '해석 레이어'가 됨

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

7️⃣ NEXT 질문이 "다음 화"를 전제하는 구조
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
❌ "다음 화에서는"
❌ "이후 어떤 영향을 미쳤는가"

이유: NEXT는 시청자 사고 연속 질문이지 서사 연결 고리 아님
      앞뒤 화가 있다는 암시 자체가 금지

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

8️⃣ 에피소드 번호를 의미 단위로 오해하게 만드는 장치
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
❌ "1/6화이므로 시작"
❌ "마무리 화이므로 정리"

이유: 1–6은 묶음 번호일 뿐
      번호는 인간에게만 보조 정보, 구조적 의미 없음

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

9️⃣ "국가의 일생"을 암묵적으로 전제하는 구조
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
❌ 탄생 → 운영 → 혼란 → 붕괴 → 유산

이유: 이건 가장 위험한 자동 서사
      시리즈 전체를 연대기로 착각하게 만드는 구조

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🔟 같은 화 안에서 질문이 두 개 이상 생기는 것
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
❌ "국가는 어떻게 생겨나는가?" + "왜 유지됐는가?"
❌ "어떻게 다스렸는가?" + "왜 무너졌는가?"

이유: 질문이 분산되면
      에피소드 = 에세이가 아니라 요약문이 됨

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🔒 요약 (핵심만)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
❌ 시간 흐름 만들기
❌ 이전·이후 암시
❌ 정답형 질문
❌ TURN/IMPACT의 역사화
❌ 에피소드 간 인과 연결
❌ 번호=시기 착각

════════════════════════════════════════════════════════════════
"""


# 금지 패턴 감지용 키워드 (코드에서 검증 시 사용)
FORBIDDEN_PATTERN_KEYWORDS = {
    "temporal_phases": ["초기에는", "이후에는", "점차", "나중에", "처음에는", "결국"],
    "before_after": ["기존에는", "이전 관습", "새로운 체제", "더 이상", "이전에는"],
    "historical_causation": ["한계에 도달", "그 결과", "이로 인해", "따라서", "그래서"],
    "next_episode": ["다음 화", "이후 어떤", "앞으로", "다음에는"],
    "episode_meaning": ["1화이므로", "마지막 화", "마무리 화", "시작 화"],
    "nation_lifecycle": ["탄생 → ", "운영 → ", "혼란 → ", "붕괴 → ", "유산"],
    "interpretation_in_facts": ["기여했다", "영향을 미쳤다", "변화시켰다", "의미한다", "보여준다"],
}
