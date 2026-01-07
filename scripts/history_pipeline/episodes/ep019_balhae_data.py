"""
한국사 19화: 발해, 고구려를 잇다 - 실행 데이터

영상 생성에 필요한 모든 데이터 포함:
- 에피소드 정보
- 대본
- 이미지 프롬프트 (11컷)
- YouTube 메타데이터
- 썸네일 정보
"""

from scripts.history_pipeline.episodes.ep019_balhae import SCRIPT as FULL_SCRIPT

# ============================================================
# 에피소드 정보
# ============================================================
EPISODE_INFO = {
    "episode_id": "ep019",
    "era": "NAMBUK",
    "era_name": "남북국시대",
    "episode_number": 19,
    "title": "발해, 고구려를 잇다",
    "subtitle": "해동성국의 228년",
    "keywords": ["발해", "대조영", "해동성국", "무왕", "문왕", "천문령전투", "고구려계승"],
}

# ============================================================
# 대본 (12,001자)
# ============================================================
SCRIPT = FULL_SCRIPT

# ============================================================
# 이미지 프롬프트 (11컷)
# 스타일: 한국 고대사 - 남북국시대 (7세기 말 ~ 10세기)
# ============================================================
IMAGE_PROMPTS = [
    {
        "scene_index": 1,
        "title": "고구려 멸망 후 폐허",
        "prompt": "Ancient Korean fortress ruins at sunset, 7th century Goguryeo style, broken stone walls overgrown with weeds, scattered weapons and armor on the ground, refugee families walking away in the distance, dramatic orange and purple sky, cinematic wide shot, historical documentary style, 16:9 aspect ratio",
        "narration_hint": "고구려가 멸망한 지 30년...",
    },
    {
        "scene_index": 2,
        "title": "당나라 안동도호부",
        "prompt": "Tang Dynasty military headquarters in Pyongyang, 7th century, Chinese officials in silk robes giving orders, Korean prisoners in chains being led away, soldiers with spears patrolling, imposing wooden government building with Chinese architecture, tense atmosphere, historical illustration style, 16:9 aspect ratio",
        "narration_hint": "당나라는 고구려 땅에 안동도호부를 설치했어요...",
    },
    {
        "scene_index": 3,
        "title": "대조영의 등장",
        "prompt": "Young Korean warrior general Dae Joyeong, 28 years old, wearing traditional Goguryeo armor with fur cape, standing on a mountain cliff overlooking vast Manchurian plains, determined expression, sunset golden light, eagles flying in background, heroic pose, cinematic lighting, 16:9 aspect ratio",
        "narration_hint": "대조영은 고구려 장군 걸걸중상의 아들이에요...",
    },
    {
        "scene_index": 4,
        "title": "천문령 전투",
        "prompt": "Epic mountain battle scene at Tianmenling Pass, Korean warriors ambushing Tang Chinese cavalry from cliff positions, arrows flying, horses rearing, narrow mountain gorge filled with combat, fog and dust, dramatic action shot, ancient Korean warfare, 16:9 aspect ratio",
        "narration_hint": "대조영은 매복을 준비했어요...",
    },
    {
        "scene_index": 5,
        "title": "발해 건국",
        "prompt": "Founding ceremony of Balhae Kingdom at Dongmo Mountain, King Dae Joyeong in royal robes raising ceremonial sword, crowd of Korean refugees and Mohe people cheering, first Balhae palace under construction in background, sunrise lighting, hopeful atmosphere, 698 AD, 16:9 aspect ratio",
        "narration_hint": "698년, 대조영은 동모산에서 나라를 세웠습니다...",
    },
    {
        "scene_index": 6,
        "title": "무왕의 등주 공격",
        "prompt": "Balhae naval fleet attacking Dengzhou port on Tang Dynasty coast, Korean warships with distinctive sails approaching Chinese harbor city, burning buildings, dramatic sea battle, 8th century naval warfare, stormy sky, cinematic wide shot, 16:9 aspect ratio",
        "narration_hint": "장문휴의 발해 해군이 등주에 도착했을 때...",
    },
    {
        "scene_index": 7,
        "title": "상경용천부 전경",
        "prompt": "Grand capital city of Sanggyeong Yongcheonbu, Balhae Kingdom, aerial view of grid-pattern streets inspired by Tang Chang'an but with Korean characteristics, magnificent palace complex with ondol heating smoke rising, bustling markets, snowy winter scene, 8th century, 16:9 aspect ratio",
        "narration_hint": "상경용천부. 이 도시가 어떻게 설계됐는지 아세요?",
    },
    {
        "scene_index": 8,
        "title": "발해 고분 내부",
        "prompt": "Interior of Balhae royal tomb showing Goguryeo-style corbeled ceiling, ancient Korean mural paintings on walls depicting hunting scenes, stone sarcophagus in center, torchlight illuminating the chamber, archaeological discovery atmosphere, 16:9 aspect ratio",
        "narration_hint": "발해 고분을 발굴해보면, 고구려 고분과 거의 똑같아요...",
    },
    {
        "scene_index": 9,
        "title": "발해-일본 외교",
        "prompt": "Balhae diplomatic mission arriving at Japanese imperial court, Korean envoys in elaborate ceremonial robes presenting gifts, Japanese nobles watching with interest, traditional Nara period architecture, cultural exchange scene, elegant atmosphere, 8th century, 16:9 aspect ratio",
        "narration_hint": "727년, 발해가 처음으로 일본에 사신을 보냈어요...",
    },
    {
        "scene_index": 10,
        "title": "거란 침공",
        "prompt": "Khitan cavalry charge attacking Balhae fortress, Yelu Abaoji leading massive nomadic army, dust clouds rising, desperate Korean defenders on castle walls, siege weapons, dramatic winter battle, 926 AD, historical war scene, 16:9 aspect ratio",
        "narration_hint": "925년 12월, 야율아보기가 직접 군대를 이끌고 발해를 침공했어요...",
    },
    {
        "scene_index": 11,
        "title": "발해 유민의 고려 귀순",
        "prompt": "Balhae refugees arriving at Goryeo Kingdom, Crown Prince Dae Gwanghyeon leading thousands of refugees, King Wang Geon of Goryeo welcoming them at palace gates, emotional reunion scene, Korean traditional architecture, hopeful sunrise lighting, 934 AD, 16:9 aspect ratio",
        "narration_hint": "934년, 발해의 세자 대광현이 수만 명의 유민을 이끌고 고려에 귀순했어요...",
    },
]

# ============================================================
# YouTube 메타데이터
# ============================================================
METADATA = {
    "title": "발해, 고구려를 잇다 | 해동성국 228년의 역사",
    "description": """고구려 멸망 30년 후, 대조영이 세운 발해.
당나라를 상대로 전쟁을 벌여 이기고, 바다를 건너 당나라 본토를 공격하고,
당나라마저 '해동성국'이라 인정한 동아시아의 강국.

📌 주요 내용
00:00 인트로 - 해동성국의 탄생
01:30 고구려 멸망 후 유민들의 고통
04:00 대조영의 등장과 천문령 전투
07:00 발해 건국 (698년)
09:00 무왕의 등주 공격
11:00 문왕과 해동성국의 전성기
14:00 발해가 고구려를 계승한 증거
17:00 일본과의 200년 외교
19:00 거란의 침공과 멸망
22:00 발해의 유산

#발해 #대조영 #해동성국 #한국사 #남북국시대 #고구려 #역사다큐""",
    "tags": [
        "발해", "대조영", "해동성국", "무왕", "문왕", "천문령전투",
        "고구려계승", "남북국시대", "한국사", "역사", "역사다큐",
        "거란", "야율아보기", "상경용천부", "일본외교"
    ],
}

# ============================================================
# 썸네일 정보
# ============================================================
THUMBNAIL = {
    "line1": "당나라도 인정한",
    "line2": "해동성국",
    "style": "dramatic",
    "background": "balhae_palace",
}

# ============================================================
# 실행용 함수
# ============================================================
def get_episode_data():
    """영상 생성에 필요한 모든 데이터 반환"""
    return {
        "episode_info": EPISODE_INFO,
        "script": SCRIPT,
        "image_prompts": IMAGE_PROMPTS,
        "metadata": METADATA,
        "thumbnail": THUMBNAIL,
    }


if __name__ == "__main__":
    data = get_episode_data()
    print(f"에피소드: {data['episode_info']['title']}")
    print(f"대본 길이: {len(data['script']):,}자")
    print(f"이미지 프롬프트: {len(data['image_prompts'])}개")
