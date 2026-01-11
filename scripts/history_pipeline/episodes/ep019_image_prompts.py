"""
EP019 발해 - 이미지 프롬프트
대본 내용에 정확히 맞춘 이미지 생성용 프롬프트
"""

# 섹션 1: 훅 - 해동성국 소개 (4장)
SECTION_01_HOOK = [
    {
        "scene_index": 1,
        "description": "고구려 멸망 30년 후, 황폐한 만주 벌판",
        "prompt": "Vast Manchurian plains in winter, 7th century, abandoned Goguryeo fortress ruins in background, Tang dynasty soldiers patrolling distant horizon, desolate atmosphere, historical Korean art style, cinematic wide shot, muted colors"
    },
    {
        "scene_index": 2,
        "description": "당나라 조정에서 축배를 드는 장면",
        "prompt": "Tang dynasty imperial court celebration, Chinese officials in luxurious robes raising wine cups in toast, ornate palace hall with red pillars and golden decorations, victory celebration atmosphere, 7th century Chinese historical scene"
    },
    {
        "scene_index": 3,
        "description": "발해 해군이 등주를 공격하는 장면",
        "prompt": "Balhae naval fleet attacking Dengzhou port, ancient Korean warships with dragon figureheads, burning Tang Chinese harbor city, dramatic naval battle scene, flames reflecting on water, 8th century East Asian warfare"
    },
    {
        "scene_index": 4,
        "description": "해동성국 발해의 위엄 있는 모습",
        "prompt": "Majestic Balhae kingdom capital city Sanggyeong, grand palace complex inspired by Tang architecture but with Goguryeo elements, snow-capped mountains in background, prosperous East Asian kingdom, golden age atmosphere, aerial view"
    },
]

# 섹션 2: 고구려 멸망 후 상황 (4장)
SECTION_02_FALL = [
    {
        "scene_index": 5,
        "description": "평양성 함락 장면",
        "prompt": "Fall of Pyongyang fortress 668 AD, Tang and Silla allied forces breaching massive stone walls, Goguryeo defenders in last stand, siege warfare, smoke and chaos, dramatic historical battle scene, Korean ancient warfare"
    },
    {
        "scene_index": 6,
        "description": "보장왕이 당나라로 끌려가는 장면",
        "prompt": "King Bojang of Goguryeo being led away in chains, defeated Korean king in torn royal robes, Tang soldiers escorting prisoners, mournful Goguryeo people watching, emotional historical scene, 7th century"
    },
    {
        "scene_index": 7,
        "description": "고구려 유민 강제 이주",
        "prompt": "Goguryeo refugees forced march to China, thousands of Korean families walking with minimal belongings, Tang soldiers herding them, children crying, emotional exodus scene, dusty road stretching to horizon, 7th century tragedy"
    },
    {
        "scene_index": 8,
        "description": "검모잠의 고구려 부흥운동",
        "prompt": "Geommojam leading Goguryeo revival movement, Korean warrior general rallying troops with raised sword, restoration army with Goguryeo banners, fortress in background, defiant atmosphere, 670 AD rebellion scene"
    },
]

# 섹션 3: 대조영 등장 (4장)
SECTION_03_DAEJOYEONG = [
    {
        "scene_index": 9,
        "description": "젊은 대조영이 아버지에게 훈련받는 장면",
        "prompt": "Young Dae Joyeong training with his father Geolgeol Jungsang, Korean cavalry practice in Manchurian grassland, father teaching son horse archery, Goguryeo warrior tradition, sunrise, inspirational mentor scene"
    },
    {
        "scene_index": 10,
        "description": "걸걸중상 일가의 강제 이주",
        "prompt": "Geolgeol Jungsang family being forcibly relocated by Tang soldiers, proud Goguryeo general walking with dignity despite captivity, family members following, Manchurian landscape, somber atmosphere, 680s AD"
    },
    {
        "scene_index": 11,
        "description": "696년 거란족 반란",
        "prompt": "Khitan rebellion against Tang dynasty 696 AD, Khitan warriors on horseback attacking Tang garrison, fire and chaos at Yingzhou fortress, nomadic cavalry charge, dramatic night battle scene"
    },
    {
        "scene_index": 12,
        "description": "걸걸중상과 걸사비우가 동맹을 맺는 장면",
        "prompt": "Geolgeol Jungsang and Geolsabiu forming alliance, Goguryeo and Mohe tribal leaders shaking hands in tent, warriors from both groups watching, map on table, secret meeting atmosphere, torchlight"
    },
]

# 섹션 4: 측천무후와 추격전 (4장)
SECTION_04_PURSUIT = [
    {
        "scene_index": 13,
        "description": "측천무후가 명령을 내리는 장면",
        "prompt": "Empress Wu Zetian on dragon throne issuing orders, powerful Chinese empress in elaborate golden robes, stern expression, Tang court officials bowing, imperial palace interior, authoritative atmosphere"
    },
    {
        "scene_index": 14,
        "description": "이해고가 대조영을 추격하는 장면",
        "prompt": "General Li Haigu leading Tang cavalry pursuit, elite Chinese horsemen galloping across Manchurian plains, dust clouds, urgent chase scene, 697 AD military pursuit"
    },
    {
        "scene_index": 15,
        "description": "걸걸중상과 걸사비우 전사",
        "prompt": "Deaths of Geolgeol Jungsang and Geolsabiu in battle, two leaders falling in combat against Tang forces, heroic last stand, dramatic battlefield scene, tragic moment, Manchurian wilderness"
    },
    {
        "scene_index": 16,
        "description": "아버지를 잃고 지도자가 된 대조영",
        "prompt": "Young Dae Joyeong mourning his father then rising as leader, 28-year-old Korean warrior standing before his people, grief transforming to determination, refugees looking to him for guidance, pivotal moment"
    },
]

# 섹션 5: 천문령 전투 (4장)
SECTION_05_TIANMENLING = [
    {
        "scene_index": 17,
        "description": "천문령 험준한 산악 지형",
        "prompt": "Tianmen Pass mountain terrain, narrow steep valley with rocky cliffs on both sides, strategic military chokepoint, misty mountains, Jilin province landscape, dramatic natural fortress"
    },
    {
        "scene_index": 18,
        "description": "대조영이 매복을 준비하는 장면",
        "prompt": "Dae Joyeong positioning troops for ambush at Tianmen Pass, Korean commander directing warriors to hide positions on cliff sides, strategic military planning, tense preparation scene"
    },
    {
        "scene_index": 19,
        "description": "천문령 전투 - 매복 공격",
        "prompt": "Battle of Tianmenling ambush attack, arrows raining down on trapped Tang cavalry in narrow gorge, rocks rolling down cliffs, Balhae warriors charging from above, decisive victory moment, chaotic battle"
    },
    {
        "scene_index": 20,
        "description": "당나라군 궤멸, 대조영의 승리",
        "prompt": "Dae Joyeong victorious after Tianmenling battle, Korean leader standing over defeated Tang forces, surviving Balhae warriors celebrating, mountain pass littered with fallen enemies, triumphant atmosphere"
    },
]

# 섹션 6: 발해 건국 (4장)
SECTION_06_FOUNDING = [
    {
        "scene_index": 21,
        "description": "698년 동모산에서 발해 건국",
        "prompt": "Founding of Balhae kingdom 698 AD at Dongmo Mountain, Dae Joyeong proclaiming new nation, Goguryeo refugees and Mohe tribes gathered, ceremonial scene, dawn breaking over mountains, historic moment"
    },
    {
        "scene_index": 22,
        "description": "발해 초기 국가 체제 정비",
        "prompt": "Early Balhae government formation, Dae Joyeong meeting with officials in wooden palace, organizing administrative system, scrolls and maps on table, building new nation atmosphere"
    },
    {
        "scene_index": 23,
        "description": "713년 당나라 책봉 장면",
        "prompt": "Tang Emperor Xuanzong officially recognizing Balhae 713 AD, Chinese envoy presenting royal seal to Dae Joyeong, diplomatic ceremony, both sides in formal attire, political recognition scene"
    },
    {
        "scene_index": 24,
        "description": "대조영의 업적과 서거",
        "prompt": "Legacy of Dae Joyeong founder of Balhae, elderly king looking over his prosperous kingdom from palace, 22 years of reign, peaceful sunset scene, accomplished ruler reflecting on achievements"
    },
]

# 섹션 7: 무왕 - 등주 공격 (4장)
SECTION_07_MUWANG = [
    {
        "scene_index": 25,
        "description": "무왕 대무예",
        "prompt": "King Mu of Balhae (Dae Muye), warrior king in military armor on throne, aggressive and ambitious expression, Balhae royal court, military banners, strong leadership presence"
    },
    {
        "scene_index": 26,
        "description": "흑수말갈 분쟁",
        "prompt": "Balhae conflict over Heishui Mohe, King Mu angry at Tang interference, heated court debate scene, Balhae officials discussing northern territory dispute, tense diplomatic crisis"
    },
    {
        "scene_index": 27,
        "description": "장문휴의 해군 출정",
        "prompt": "General Jang Munhyu leading Balhae naval expedition, Korean warship fleet sailing across Bohai Sea, commander on flagship deck, 732 AD maritime military campaign, dramatic ocean scene"
    },
    {
        "scene_index": 28,
        "description": "등주 기습 공격",
        "prompt": "Balhae surprise attack on Dengzhou 732 AD, Korean marines storming Tang Chinese port city, chaos in harbor, Governor Wei Jun falling in battle, shocking assault on Tang mainland"
    },
]

# 섹션 8: 문왕 - 해동성국 전성기 (4장)
SECTION_08_MUNWANG = [
    {
        "scene_index": 29,
        "description": "문왕 대흠무",
        "prompt": "King Mun of Balhae (Dae Heummu), wise scholarly king in elegant robes, peaceful expression, surrounded by books and scrolls, cultured ruler atmosphere, 57-year reign"
    },
    {
        "scene_index": 30,
        "description": "상경용천부 전경",
        "prompt": "Sanggyeong Yongcheonbu capital city of Balhae, magnificent city layout modeled after Tang Chang'an, grid street pattern, grand palace complex, prosperous East Asian metropolis, aerial view"
    },
    {
        "scene_index": 31,
        "description": "5경 15부 62주 체제",
        "prompt": "Map of Balhae administrative system, 5 capitals marked on territory spanning Manchuria and northern Korea, organized government structure visualization, historical Korean kingdom at peak"
    },
    {
        "scene_index": 32,
        "description": "해동성국으로 인정받는 발해",
        "prompt": "Balhae recognized as Haedong Sungguk (Flourishing Nation East of Sea), Tang Chinese envoys acknowledging Balhae's greatness, cultural exchange scene, mutual respect between empires"
    },
]

# 섹션 9: 고구려 계승 증거 (4장)
SECTION_09_SUCCESSION = [
    {
        "scene_index": 33,
        "description": "무왕이 일본에 보낸 국서",
        "prompt": "Balhae diplomatic letter to Japan, ancient Korean scroll with 'King of Goryeo' signature, royal seal visible, historical document closeup, 8th century diplomatic correspondence"
    },
    {
        "scene_index": 34,
        "description": "발해 고분 - 고구려 양식",
        "prompt": "Balhae royal tomb interior, Goguryeo-style corbeled ceiling, mural paintings similar to Goguryeo tombs, Princess Jeonghye tomb, archaeological evidence of cultural continuity"
    },
    {
        "scene_index": 35,
        "description": "발해 온돌 유적",
        "prompt": "Balhae ondol heating system archaeological site, underfloor heating structure inherited from Goguryeo, excavation showing Korean heating technology, cultural heritage evidence"
    },
    {
        "scene_index": 36,
        "description": "발해 기와 - 고구려 연꽃 무늬",
        "prompt": "Balhae roof tiles with lotus patterns, comparison with Goguryeo tile designs, archaeological artifacts showing cultural continuity, museum display of historical Korean craftsmanship"
    },
]

# 섹션 10: 일본 외교 (4장)
SECTION_10_JAPAN = [
    {
        "scene_index": 37,
        "description": "727년 첫 발해 사신단 일본 도착",
        "prompt": "First Balhae embassy arriving in Japan 727 AD, Korean diplomats disembarking ship at Japanese port, formal delegation in traditional dress, historic first contact scene"
    },
    {
        "scene_index": 38,
        "description": "발해 사신들의 문화 교류",
        "prompt": "Balhae cultural envoys performing at Japanese court, Korean musicians playing traditional instruments, Japanese nobles watching in admiration, Balhaeak music performance, cultural diplomacy"
    },
    {
        "scene_index": 39,
        "description": "발해-일본 무역",
        "prompt": "Balhae-Japan trade scene, Korean merchants displaying furs ginseng and honey, Japanese traders offering silk and gold, busy trading port, 8th century East Asian commerce"
    },
    {
        "scene_index": 40,
        "description": "200년간의 우호 관계",
        "prompt": "Balhae and Japan 200 years of diplomacy, montage of 34 embassy visits, ships crossing East Sea, cultural exchange symbols, long-lasting friendship between kingdoms"
    },
]

# 섹션 11: 발해 멸망 (4장)
SECTION_11_FALL = [
    {
        "scene_index": 41,
        "description": "야율아보기와 거란의 부상",
        "prompt": "Yelü Abaoji founder of Khitan Liao dynasty, fierce nomadic emperor on horseback, Khitan cavalry army behind him, ambitious conqueror, 10th century Central Asian warrior"
    },
    {
        "scene_index": 42,
        "description": "925년 거란의 발해 침공",
        "prompt": "Khitan invasion of Balhae 925 AD, massive cavalry army sweeping across frozen Manchurian plains, surprise winter attack, overwhelming military force"
    },
    {
        "scene_index": 43,
        "description": "발해 수도 함락",
        "prompt": "Fall of Balhae capital Holhanseong, King Dae Inseon surrendering to Khitan forces, 15 days of war ending 228 years of kingdom, tragic defeat scene, 926 AD"
    },
    {
        "scene_index": 44,
        "description": "발해 멸망의 순간",
        "prompt": "End of Balhae kingdom, burning capital city, refugees fleeing, Khitan soldiers occupying, once-great Haedong Sungguk falling, emotional historical tragedy"
    },
]

# 섹션 12: 결론 - 남북국시대 (4장)
SECTION_12_CONCLUSION = [
    {
        "scene_index": 45,
        "description": "발해 유민들의 고려 귀순",
        "prompt": "Balhae refugees joining Goryeo, Crown Prince Dae Gwanghyeon leading thousands to King Wang Geon, Korean unification moment, welcoming ceremony, 934 AD"
    },
    {
        "scene_index": 46,
        "description": "왕건이 발해 유민을 받아들이는 장면",
        "prompt": "King Wang Geon of Goryeo welcoming Balhae refugees, Korean king granting royal surname to Dae Gwanghyeon, compassionate ruler, unifying Korean peoples, throne room scene"
    },
    {
        "scene_index": 47,
        "description": "남북국시대 - 신라와 발해",
        "prompt": "Map of North-South States Period, Silla in south and Balhae in north, unified Korean history concept, dual kingdoms of Korean peninsula and Manchuria, historical overview"
    },
    {
        "scene_index": 48,
        "description": "발해의 정신이 이어지다",
        "prompt": "Legacy of Balhae continuing through Goryeo to modern Korea, symbolic image of Goguryeo spirit passing through generations, national identity continuity, inspirational historical conclusion"
    },
]

# 전체 프롬프트 리스트
ALL_PROMPTS = (
    SECTION_01_HOOK +
    SECTION_02_FALL +
    SECTION_03_DAEJOYEONG +
    SECTION_04_PURSUIT +
    SECTION_05_TIANMENLING +
    SECTION_06_FOUNDING +
    SECTION_07_MUWANG +
    SECTION_08_MUNWANG +
    SECTION_09_SUCCESSION +
    SECTION_10_JAPAN +
    SECTION_11_FALL +
    SECTION_12_CONCLUSION
)

if __name__ == "__main__":
    print(f"총 {len(ALL_PROMPTS)}개 이미지 프롬프트")
    for i, p in enumerate(ALL_PROMPTS, 1):
        print(f"{i:02d}. {p['description']}")
