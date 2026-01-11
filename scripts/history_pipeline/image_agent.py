"""
한국사 파이프라인 - Image Agent (이미지 에이전트)

## 역할
한국사 다큐멘터리 영상을 위한 이미지 프롬프트 생성
시대별 고증에 맞는 비주얼 스타일 적용

## 전문 분야
- 한국사 시대별 비주얼 스타일
- 역사적 고증 (복식, 건축, 무기 등)
- 다큐멘터리 분위기 연출
- AI 이미지 프롬프트 최적화

## 시대 구분
1. 고조선/삼한 (BC 2333 ~ AD 1)
2. 삼국시대 (1 ~ 668)
3. 남북국시대 (668 ~ 935)
4. 고려 (918 ~ 1392)
5. 조선 전기 (1392 ~ 1592)
6. 조선 후기 (1592 ~ 1897)
7. 대한제국/일제강점기 (1897 ~ 1945)
8. 현대 (1945 ~ )
"""

import re
from typing import Dict, Any, List, Optional


# =============================================================================
# 시대별 비주얼 테마
# =============================================================================
ERA_VISUAL_THEMES = {
    "고조선": {
        "name": "고조선/삼한",
        "period": "BC 2333 ~ AD 1",
        "palette": "bronze, earth tones, jade green, deep brown",
        "mood": "mysterious, ancient, shamanic, mythical",
        "environment": "ancient fortresses, dolmen stones, primitive villages, dense forests",
        "lighting": "mystical sunlight, sacred glow, bonfire light",
        "architecture": "thatched roof huts, wooden palisades, stone altars",
        "costume": "animal furs, bronze ornaments, simple cloth robes, jade accessories",
        "weapons": "bronze swords, bronze daggers, stone weapons, wooden shields",
        "keywords": ["bronze age", "shamanism", "dolmen", "ancient korea", "tribal"],
    },
    "삼국시대": {
        "name": "삼국시대",
        "period": "1 ~ 668",
        "palette": "royal gold, deep red, forest green, iron gray",
        "mood": "heroic, warlike, diplomatic, cultural flourishing",
        "environment": "mountain fortresses, royal palaces, battlefields, buddhist temples",
        "lighting": "dramatic sunlight, torch light, golden hour",
        "architecture": "traditional korean palaces, pagodas, fortress walls, tiled roofs",
        "costume": "armor with distinctive patterns, silk robes, royal crowns, warrior outfits",
        "weapons": "iron swords, cavalry spears, bows, war banners",
        "keywords": ["three kingdoms", "goguryeo warrior", "baekje elegance", "silla gold"],
    },
    "남북국시대": {
        "name": "남북국시대 (통일신라/발해)",
        "period": "668 ~ 935",
        "palette": "golden, royal purple, buddhist saffron, jade",
        "mood": "prosperous, cultural golden age, buddhist devotion, refined",
        "environment": "unified kingdom, grand temples, royal tombs, trade routes",
        "lighting": "warm golden light, temple candlelight, serene atmosphere",
        "architecture": "bulguksa temple style, seokguram grotto, royal palaces, pagodas",
        "costume": "elaborate silk robes, golden crowns, buddhist monk robes, noble attire",
        "weapons": "ceremonial swords, decorated armor, royal guards equipment",
        "keywords": ["unified silla", "balhae", "buddhist art", "golden age", "silk road"],
    },
    "고려": {
        "name": "고려시대",
        "period": "918 ~ 1392",
        "palette": "celadon green, buddhist gold, royal blue, elegant gray",
        "mood": "refined, artistic, buddhist, cosmopolitan, turbulent",
        "environment": "celadon workshops, buddhist temples, mongol invasions, coastal trading ports",
        "lighting": "soft diffused light, incense smoke atmosphere, dramatic war scenes",
        "architecture": "elegant wooden structures, intricate tile work, fortress walls",
        "costume": "flowing hanbok, official robes, monk attire, military uniforms",
        "weapons": "korean swords, composite bows, siege weapons, naval vessels",
        "keywords": ["goryeo celadon", "tripitaka koreana", "mongol invasion", "buddhist kingdom"],
    },
    "조선_전기": {
        "name": "조선 전기",
        "period": "1392 ~ 1592",
        "palette": "scholarly white, royal red, nature green, ink black",
        "mood": "confucian order, scholarly, royal authority, cultural development",
        "environment": "confucian academies, royal court, village squares, mountain retreats",
        "lighting": "clear daylight, study room candlelight, ceremonial atmosphere",
        "architecture": "gyeongbokgung style palaces, confucian shrines, traditional hanok",
        "costume": "scholarly robes, official uniforms with rank badges, royal ceremonial dress",
        "weapons": "ceremonial swords, royal guard equipment, traditional bows",
        "keywords": ["joseon dynasty", "confucian scholars", "hangul creation", "sejong the great"],
    },
    "조선_후기": {
        "name": "조선 후기",
        "period": "1592 ~ 1897",
        "palette": "war-torn browns, resilient green, folk art colors, muted tones",
        "mood": "turbulent, resilient, folk culture, reform movements",
        "environment": "war-damaged cities, rebuilding, marketplaces, foreign ships arriving",
        "lighting": "harsh war lighting, peaceful village scenes, dramatic contrasts",
        "architecture": "rebuilt palaces, defensive structures, village markets",
        "costume": "practical military uniforms, common folk clothing, yangban attire",
        "weapons": "turtle ships, cannons, matchlock rifles, traditional swords",
        "keywords": ["imjin war", "turtle ship", "silhak scholars", "western contact"],
    },
    "대한제국": {
        "name": "대한제국/일제강점기",
        "period": "1897 ~ 1945",
        "palette": "sepia tones, imperial gold and purple, resistance red, somber gray",
        "mood": "modernization struggle, colonial oppression, resistance, hope",
        "environment": "western-style buildings, trains, independence protests, prisons",
        "lighting": "early photography style, dramatic shadows, hope breaking through",
        "architecture": "mix of traditional and western buildings, modern infrastructure",
        "costume": "western suits mixed with hanbok, military uniforms, independence fighter attire",
        "weapons": "modern rifles, protest banners, bombs (independence fighters)",
        "keywords": ["korean empire", "japanese occupation", "independence movement", "march 1st"],
    },
    "현대": {
        "name": "현대 대한민국",
        "period": "1945 ~ present",
        "palette": "hopeful blue, reconstruction gray, economic miracle colors, democratic green",
        "mood": "division tragedy, rapid development, democratization, global presence",
        "environment": "war ruins to modern cities, factories, protest squares, global stage",
        "lighting": "documentary style, news footage atmosphere, modern cinematic",
        "architecture": "post-war reconstruction, industrial facilities, modern skyscrapers",
        "costume": "military uniforms, worker clothes, business suits, protest attire",
        "weapons": "modern military equipment, protest signs",
        "keywords": ["korean war", "economic miracle", "democratization", "modern korea"],
    },
}

# 시대 키워드 매핑 (대본에서 시대 감지용)
ERA_KEYWORDS = {
    "고조선": ["고조선", "단군", "위만", "삼한", "부여", "옥저", "동예", "청동기"],
    "삼국시대": ["고구려", "백제", "신라", "가야", "광개토대왕", "장수왕", "근초고왕", "진흥왕", "화랑", "삼국통일"],
    "남북국시대": ["통일신라", "발해", "신문왕", "원성왕", "대조영", "무왕", "불국사", "석굴암", "9주5소경"],
    "고려": ["고려", "왕건", "광종", "성종", "무신정권", "몽골", "삼별초", "고려청자", "팔만대장경"],
    "조선_전기": ["조선", "태조", "세종", "훈민정음", "집현전", "사림", "사화", "성리학"],
    "조선_후기": ["임진왜란", "병자호란", "이순신", "영조", "정조", "실학", "천주교", "세도정치"],
    "대한제국": ["대한제국", "고종", "을사조약", "일제", "3.1운동", "독립운동", "임시정부", "광복"],
    "현대": ["6.25", "한국전쟁", "4.19", "5.18", "민주화", "경제개발", "올림픽", "월드컵"],
}


# =============================================================================
# 역사 인물 비주얼 가이드 (주요 인물)
# =============================================================================
HISTORICAL_FIGURES = {
    # 삼국시대
    "광개토대왕": {
        "era": "삼국시대",
        "appearance": "powerful muscular build, commanding presence, fierce eyes",
        "costume": "elaborate goguryeo armor with gold accents, royal cape, iron crown",
        "attributes": ["war banner", "mounted on warhorse", "conquering pose"],
    },
    "장수왕": {
        "era": "삼국시대",
        "appearance": "tall dignified king, wise aged face, authoritative gaze",
        "costume": "goguryeo royal robes, ornate crown, ceremonial sword",
        "attributes": ["diplomatic scrolls", "territorial maps", "throne room"],
    },
    "근초고왕": {
        "era": "삼국시대",
        "appearance": "elegant noble bearing, sharp intelligent eyes",
        "costume": "baekje royal golden robes, refined crown, silk garments",
        "attributes": ["naval fleet", "trade goods", "diplomatic gifts"],
    },
    "김유신": {
        "era": "삼국시대",
        "appearance": "battle-hardened general, determined expression, scarred veteran",
        "costume": "silla warrior armor, general's helmet, command baton",
        "attributes": ["sword raised", "cavalry charge", "battle formation"],
    },

    # 남북국시대
    "신문왕": {
        "era": "남북국시대",
        "appearance": "young but resolute king, sharp political eyes, dignified bearing",
        "costume": "unified silla royal robes, golden crown with jade, ceremonial attire",
        "attributes": ["reform edicts", "administrative documents", "royal seal"],
    },
    "대조영": {
        "era": "남북국시대",
        "appearance": "fierce warrior king, goguryeo heritage, determined leader",
        "costume": "balhae founding king attire, military armor mixed with royal robes",
        "attributes": ["founding banner", "refugee followers", "new kingdom"],
    },

    # 고려
    "왕건": {
        "era": "고려",
        "appearance": "charismatic unifier, benevolent expression, military bearing",
        "costume": "goryeo founding king robes, military-royal hybrid attire",
        "attributes": ["unification map", "alliance documents", "goryeo banner"],
    },
    "강감찬": {
        "era": "고려",
        "appearance": "elderly but spirited general, wise tactical eyes, humble demeanor",
        "costume": "goryeo military official robes, simple armor, command flag",
        "attributes": ["battle strategy", "water dam trap", "victorious pose"],
    },

    # 조선
    "이성계": {
        "era": "조선_전기",
        "appearance": "powerful archer-warrior, ambitious eyes, commanding presence",
        "costume": "military general becoming king, transitional royal-military attire",
        "attributes": ["bow and arrows", "wihwado retreat", "new dynasty"],
    },
    "세종대왕": {
        "era": "조선_전기",
        "appearance": "scholarly wise king, gentle but determined eyes, intellectual bearing",
        "costume": "joseon royal scholarly robes, simple but dignified crown",
        "attributes": ["hangul documents", "scientific instruments", "books"],
    },
    "이순신": {
        "era": "조선_후기",
        "appearance": "stoic naval commander, weathered face, unwavering gaze",
        "costume": "joseon naval admiral armor, battle-worn, command attire",
        "attributes": ["turtle ship", "naval battle", "war diary"],
    },
    "정조": {
        "era": "조선_후기",
        "appearance": "reformist king, intelligent cultured eyes, dignified scholar-king",
        "costume": "joseon royal robes, scholarly accessories, reform documents",
        "attributes": ["suwon hwaseong", "gyujanggak library", "reform edicts"],
    },

    # 근현대
    "안중근": {
        "era": "대한제국",
        "appearance": "determined patriot, fierce righteous eyes, young but resolute",
        "costume": "early 20th century korean clothing, simple dignified attire",
        "attributes": ["independence declaration", "courtroom stance", "finger pledge"],
    },
    "유관순": {
        "era": "대한제국",
        "appearance": "young brave woman, defiant eyes, determined expression",
        "costume": "early 20th century korean hanbok, student uniform elements",
        "attributes": ["korean flag", "independence protest", "prison resistance"],
    },
}


# =============================================================================
# 이미지 타입별 템플릿
# =============================================================================
IMAGE_TYPE_TEMPLATES = {
    "establishing_shot": {
        "composition": "epic wide shot, panoramic view, landscape focus",
        "focus": "historical setting and atmosphere",
        "example": "vast ancient korean landscape, historical architecture panorama",
    },
    "portrait": {
        "composition": "3/4 view or front view, upper body focus, dignified pose",
        "focus": "historical figure with period-accurate costume",
        "example": "korean historical figure portrait, detailed traditional costume",
    },
    "battle_scene": {
        "composition": "dynamic angle, action poses, dramatic scale",
        "focus": "military conflict with historical accuracy",
        "example": "ancient korean battle scene, armies clashing, war banners",
    },
    "court_scene": {
        "composition": "formal arrangement, hierarchical positioning",
        "focus": "royal court or political gathering",
        "example": "joseon court assembly, officials in formal attire",
    },
    "daily_life": {
        "composition": "medium shot, natural activities",
        "focus": "common people and everyday scenes",
        "example": "traditional korean village life, marketplace, farming",
    },
    "architecture": {
        "composition": "architectural photography style, detail focus",
        "focus": "historical buildings and structures",
        "example": "traditional korean palace, buddhist temple, fortress",
    },
    "map_diagram": {
        "composition": "bird's eye view, strategic overview",
        "focus": "territorial changes, military movements",
        "example": "ancient korean territory map, battle strategy diagram",
    },
    "cultural_artifact": {
        "composition": "product photography style, detailed close-up",
        "focus": "historical objects and cultural items",
        "example": "goryeo celadon, silla gold crown, bronze artifacts",
    },
}


# =============================================================================
# 프롬프트 템플릿 (2025 트렌드 반영 - MrBeast 스타일)
# =============================================================================

# 썸네일용 프롬프트 템플릿 (2025 트렌드: 시네마틱 + 배경 있는 구도)
THUMBNAIL_PROMPT_TEMPLATE = """Create a cinematic YouTube thumbnail for Korean history documentary.

SCENE COMPOSITION:
{visual_description}

KOREAN TEXT:
Display "{title}" in bold Korean typography.
- Font style: Extra bold, modern sans-serif (like Black Han Sans)
- Text color: Bright {text_color} with thick black stroke outline
- Position: Bottom third of image, centered
- Size: Large and impactful, readable on mobile

VISUAL STYLE:
- Cinematic film look, like a movie poster or K-drama scene
- Rich, saturated colors with {accent_color} tones
- Dramatic lighting: rim light, volumetric rays, atmospheric haze
- Background should be visible and detailed (not blurred out)

CAMERA:
- Wide or medium shot (NOT close-up)
- 16:9 aspect ratio
- Cinematic depth of field
- Film grain for texture

MOOD: Epic, dramatic, makes viewer curious about the story"""

# 씬 이미지용 프롬프트 템플릿 (일러스트/웹툰 스타일)
SCENE_PROMPT_TEMPLATE = """Create a scene for Korean history documentary in Korean webtoon illustration style.

SCENE:
{scene_description}

SETTING:
- Historical period: {era_name} ({era_period})
- Location: {environment}

ART STYLE:
- Korean webtoon/manhwa illustration style
- Soft, painterly brush strokes with clean linework
- NOT photorealistic - stylized illustration
- Warm, emotional, expressive characters
- Rich watercolor-like textures and gradients

COMPOSITION:
- Shot style: {composition}
- Lighting: {lighting}, soft glows, atmospheric depth
- Color palette: {color_palette}, harmonious and warm

MOOD: {mood}, emotionally engaging, storytelling feel

TECHNICAL:
- High quality digital illustration
- Aspect ratio: 16:9 (widescreen)
- Inspired by Korean historical manhwa and webtoons

DO NOT include any text, watermarks, UI elements, or modern objects."""

# 텍스트 색상 옵션 (고대비 조합)
TEXT_COLOR_OPTIONS = {
    "default": ("white", "orange"),      # 흰색 텍스트 + 주황 악센트
    "warm": ("yellow", "red"),           # 노랑 텍스트 + 빨강 악센트
    "cool": ("cyan", "blue"),            # 시안 텍스트 + 파랑 악센트
    "royal": ("gold", "purple"),         # 금색 텍스트 + 보라 악센트
    "fire": ("orange", "red"),           # 주황 텍스트 + 빨강 악센트
    "neon": ("lime green", "magenta"),   # 네온 그린 + 마젠타
}

# 네거티브 프롬프트 (씬 이미지용)
NEGATIVE_PROMPT_SCENE = (
    "text, words, letters, watermark, signature, logo, UI elements, "
    "modern objects, anachronistic items, anime, cartoon, illustration style, "
    "painting, drawing, sketch, low quality, blurry, deformed faces, "
    "extra limbs, bad anatomy, oversaturated, undersaturated"
)

# 네거티브 프롬프트 (썸네일용 - 한글 허용, 영어 제외)
NEGATIVE_PROMPT_THUMBNAIL = (
    "english text, latin letters, watermark, signature, logo, "
    "anime style, cartoon, illustration, painting style, "
    "low quality, blurry, deformed, bad anatomy, "
    "dull colors, flat lighting, boring composition"
)


# =============================================================================
# 핵심 함수들
# =============================================================================
def detect_era(script: str) -> str:
    """대본에서 시대 감지"""
    era_scores = {}

    for era, keywords in ERA_KEYWORDS.items():
        score = sum(1 for keyword in keywords if keyword in script)
        if score > 0:
            era_scores[era] = score

    if era_scores:
        return max(era_scores, key=era_scores.get)

    return "삼국시대"  # 기본값


def detect_historical_figures(script: str) -> List[str]:
    """대본에서 역사 인물 감지"""
    figures = []

    for name in HISTORICAL_FIGURES.keys():
        if name in script:
            figures.append(name)

    return figures


def get_era_theme(era: str) -> Dict[str, Any]:
    """시대별 테마 반환"""
    return ERA_VISUAL_THEMES.get(era, ERA_VISUAL_THEMES["삼국시대"])


def get_figure_visual(name: str) -> Optional[Dict[str, Any]]:
    """역사 인물 비주얼 반환"""
    return HISTORICAL_FIGURES.get(name)


def calculate_image_count(script: str) -> int:
    """대본 길이 기반 이미지 개수 계산"""
    chars_per_minute = 910  # 한국어 TTS 기준
    length = len(script)
    estimated_minutes = length / chars_per_minute

    if estimated_minutes < 8:
        return 8
    elif estimated_minutes < 10:
        return 10
    elif estimated_minutes < 15:
        return 12
    elif estimated_minutes < 20:
        return 15
    else:
        return 18


def generate_scene_prompt(
    scene_text: str,
    scene_index: int,
    era: str,
    image_type: str = "establishing_shot",
    figures: List[str] = None,
) -> Dict[str, Any]:
    """개별 씬 프롬프트 생성 (서술형)"""
    theme = get_era_theme(era)
    type_template = IMAGE_TYPE_TEMPLATES.get(image_type, IMAGE_TYPE_TEMPLATES["establishing_shot"])

    # 씬 설명 구성
    scene_parts = []

    # 인물 설명
    if figures:
        for fig_name in figures[:2]:
            fig = get_figure_visual(fig_name)
            if fig:
                scene_parts.append(
                    f"A {fig['appearance']}, wearing {fig['costume']}."
                )

    # 이미지 타입별 설명 추가
    scene_parts.append(type_template.get("example", type_template["focus"]))

    scene_description = " ".join(scene_parts) if scene_parts else type_template["focus"]

    # 서술형 프롬프트 생성
    prompt = SCENE_PROMPT_TEMPLATE.format(
        scene_description=scene_description,
        era_name=theme["name"],
        era_period=theme["period"],
        environment=theme["environment"],
        lighting=theme["lighting"],
        composition=type_template["composition"],
        color_palette=theme["palette"],
        mood=theme["mood"],
    )

    return {
        "scene_index": scene_index,
        "image_type": image_type,
        "prompt": prompt,
        "negative_prompt": NEGATIVE_PROMPT_SCENE,
        "era": era,
        "figures": figures or [],
        "aspect_ratio": "16:9",
    }


def generate_thumbnail_prompt(
    title: str,
    era: str,
    main_figure: str = None,
    include_korean_text: bool = True,
    color_style: str = "royal",  # default, warm, cool, royal, fire, neon
    scene_hook: str = None,  # 에피소드 핵심 장면/훅 설명
) -> Dict[str, Any]:
    """썸네일 프롬프트 생성 (시네마틱 구도 + 배경 포함)"""
    theme = get_era_theme(era)

    # 타이틀 처리 (짧게! 2-5글자 권장)
    display_title = title

    # 색상 선택
    text_color, accent_color = TEXT_COLOR_OPTIONS.get(color_style, TEXT_COLOR_OPTIONS["royal"])

    # 비주얼 설명 구성 (시네마틱 장면)
    visual_parts = []

    # 커스텀 훅 장면이 있으면 사용
    if scene_hook:
        visual_parts.append(scene_hook)
    # 메인 인물이 있으면 배경과 함께 구성
    elif main_figure and main_figure in HISTORICAL_FIGURES:
        fig = HISTORICAL_FIGURES[main_figure]
        visual_parts.append(
            f"Medium shot of {main_figure}, a Korean historical figure. "
            f"{fig['appearance']}. Wearing {fig['costume']}. "
            f"Standing or seated in {theme['environment']}. "
            f"Dramatic pose showing authority/tension. "
            f"Background clearly visible: ancient Korean palace, torches, guards in shadow."
        )
    else:
        # 인물 없으면 드라마틱한 배경 장면
        visual_parts.append(
            f"Epic wide shot of {theme['environment']}. "
            f"Cinematic composition with dramatic sky. "
            f"Atmosphere of {theme['mood']}. "
            f"Ancient Korean architecture, flags, atmospheric fog."
        )

    visual_description = "\n".join(visual_parts)

    # 프롬프트 생성
    if include_korean_text:
        prompt = THUMBNAIL_PROMPT_TEMPLATE.format(
            title=display_title,
            visual_description=visual_description,
            text_color=text_color,
            accent_color=accent_color,
        )
    else:
        # 텍스트 없는 버전
        prompt = f"""Create a cinematic YouTube thumbnail background for Korean history documentary.

SCENE:
{visual_description}

STYLE:
- Cinematic film look, K-drama quality
- Rich colors with {accent_color} accent lighting
- Dramatic atmosphere, volumetric light
- Leave space at bottom for text overlay

CAMERA: Wide or medium shot, 16:9, NOT close-up

DO NOT include any text."""

    return {
        "scene_index": 0,
        "image_type": "thumbnail",
        "prompt": prompt,
        "negative_prompt": NEGATIVE_PROMPT_THUMBNAIL if include_korean_text else NEGATIVE_PROMPT_SCENE,
        "era": era,
        "title": title,
        "aspect_ratio": "16:9",
        "priority": "highest",
        "korean_text": display_title if include_korean_text else None,
    }


def generate_image_prompts(
    script: str,
    title: str,
    era: str = None,
    image_count: int = None,
) -> Dict[str, Any]:
    """
    대본 기반 이미지 프롬프트 일괄 생성

    Args:
        script: 대본 텍스트
        title: 에피소드 타이틀
        era: 시대 (자동 감지 가능)
        image_count: 이미지 개수 (자동 계산 가능)

    Returns:
        {
            "era": str,
            "image_count": int,
            "thumbnail": {...},
            "scenes": [{...}, ...],
            "figures_detected": [...],
            "theme": {...},
        }
    """
    # 시대 감지
    if not era:
        era = detect_era(script)

    theme = get_era_theme(era)

    # 인물 감지
    figures = detect_historical_figures(script)

    # 이미지 개수 계산
    if not image_count:
        image_count = calculate_image_count(script)

    # 대본을 씬으로 분할
    scene_count = image_count - 1  # 썸네일 제외
    script_length = len(script)
    chunk_size = script_length // scene_count

    scenes_text = []
    for i in range(scene_count):
        start = i * chunk_size
        end = start + chunk_size if i < scene_count - 1 else script_length
        scenes_text.append(script[start:end])

    # 썸네일 프롬프트 - 타이틀에서 인물 우선 추출
    main_figure = None
    for fig_name in HISTORICAL_FIGURES.keys():
        if fig_name in title:
            main_figure = fig_name
            break
    # 타이틀에 없으면 대본에서 감지된 첫 번째 인물
    if not main_figure and figures:
        main_figure = figures[0]
    thumbnail = generate_thumbnail_prompt(title, era, main_figure)

    # 씬별 프롬프트
    scene_prompts = []
    image_types = _get_image_type_sequence(scene_count)

    for i, (scene_text, img_type) in enumerate(zip(scenes_text, image_types)):
        # 해당 씬에 언급된 인물 찾기
        scene_figures = [f for f in figures if f in scene_text]

        prompt = generate_scene_prompt(
            scene_text=scene_text,
            scene_index=i + 1,
            era=era,
            image_type=img_type,
            figures=scene_figures,
        )
        scene_prompts.append(prompt)

    return {
        "era": era,
        "era_name": theme["name"],
        "image_count": image_count,
        "thumbnail": thumbnail,
        "scenes": scene_prompts,
        "figures_detected": figures,
        "theme": theme,
        "negative_prompt": NEGATIVE_PROMPT_SCENE,
    }


def _get_image_type_sequence(count: int) -> List[str]:
    """씬 수에 맞는 이미지 타입 시퀀스 생성"""
    # 기본 패턴: 도입 → 전개 → 클라이맥스 → 마무리
    base_sequence = [
        "establishing_shot",  # 도입
        "portrait",           # 인물 소개
        "court_scene",        # 정치/회의
        "battle_scene",       # 갈등/전투
        "daily_life",         # 일상/배경
        "architecture",       # 건축/문화
        "battle_scene",       # 클라이맥스
        "portrait",           # 결과
        "establishing_shot",  # 마무리
    ]

    if count <= len(base_sequence):
        return base_sequence[:count]

    # 더 많은 이미지가 필요하면 패턴 반복
    result = []
    for i in range(count):
        result.append(base_sequence[i % len(base_sequence)])
    return result


# =============================================================================
# 시간 기반 10개 이미지 생성 (0-5분: 1분 간격, 5분+: 2-3분 간격)
# =============================================================================

# 10개 이미지 타임라인 (분 단위)
# 0-5분: 0, 1, 2, 3, 4분 (5개)
# 5분+: 5, 7, 9, 11, 13분 (5개) - 약 2분 간격
IMAGE_TIMESTAMPS_MINUTES = [0, 1, 2, 3, 4, 5, 7, 9, 11, 13]


def parse_script_scenes(script: str) -> List[Dict[str, Any]]:
    """
    대본에서 씬 구조 파싱

    Args:
        script: 마크다운 대본 (### [씬 X: ...] 형식)

    Returns:
        [{"scene_num": 1, "title": "인트로", "content": "..."}, ...]
    """
    scenes = []
    # 씬 헤더 패턴: ### [씬 1: 인트로] - 약 1,200자
    scene_pattern = r'###\s*\[씬\s*(\d+)[:\s]*([^\]]*)\].*?\n(.*?)(?=###\s*\[씬|\Z)'

    matches = re.findall(scene_pattern, script, re.DOTALL)

    for match in matches:
        scene_num = int(match[0])
        title = match[1].strip()
        content = match[2].strip()

        scenes.append({
            "scene_num": scene_num,
            "title": title,
            "content": content,
        })

    return scenes


def generate_scene_description_from_content(
    scene_content: str,
    scene_title: str,
    era: str,
    figures: List[str] = None,
) -> str:
    """
    씬 내용에서 이미지 설명 추출

    핵심 장면/상황을 찾아서 시각적 설명으로 변환
    """
    theme = get_era_theme(era)

    # 씬 타이틀에서 키워드 추출
    title_lower = scene_title.lower()

    # 인물 비주얼 추가
    figure_desc = ""
    if figures:
        for fig_name in figures[:2]:
            fig = get_figure_visual(fig_name)
            if fig:
                figure_desc += f"{fig_name} ({fig['appearance']}, wearing {fig['costume']}). "

    # 씬 타이틀 기반 장면 설명
    if "인트로" in scene_title or "도입" in scene_title:
        base_desc = f"Epic establishing shot of {theme['environment']}. Dramatic sky, atmospheric fog. {theme['mood']} atmosphere."
    elif "배경" in scene_title:
        base_desc = f"Wide panoramic view of ancient Korean kingdom. {theme['environment']}. Historical context scene."
    elif "반란" in scene_title or "난" in scene_title or "갈등" in scene_title:
        base_desc = f"Tense confrontation scene in royal court. Soldiers surrounding nobleman. Dramatic lighting, conflict atmosphere."
    elif "개혁" in scene_title or "정책" in scene_title:
        base_desc = f"King announcing reforms to officials in throne room. {theme['architecture']}. Formal court assembly."
    elif "결과" in scene_title or "마무리" in scene_title or "아웃트로" in scene_title:
        base_desc = f"Peaceful aftermath scene. Prosperous kingdom view. {theme['environment']}. Hopeful atmosphere."
    else:
        # 기본 씬
        base_desc = f"Cinematic scene from {theme['name']} era. {theme['environment']}. {theme['mood']} atmosphere."

    # 씬 내용에서 핵심 키워드 추출해서 추가
    content_hints = []
    if "전쟁" in scene_content or "전투" in scene_content:
        content_hints.append("military conflict, battle atmosphere")
    if "궁" in scene_content or "왕궁" in scene_content or "조정" in scene_content:
        content_hints.append("royal palace, throne room")
    if "백성" in scene_content or "농민" in scene_content:
        content_hints.append("common people, village life")
    if "불교" in scene_content or "절" in scene_content or "사찰" in scene_content:
        content_hints.append("buddhist temple, monks")

    hints_str = ", ".join(content_hints) if content_hints else ""

    full_desc = f"{figure_desc}{base_desc}"
    if hints_str:
        full_desc += f" Additional elements: {hints_str}."

    return full_desc


def generate_timed_image_prompts(
    script: str,
    title: str,
    era: str = None,
    video_duration_minutes: float = 13,
) -> Dict[str, Any]:
    """
    시간 기반 10개 이미지 프롬프트 생성

    - 0-5분: 1분 간격 (5개)
    - 5분 이후: 2분 간격 (5개)
    - 총 10개 이미지

    Args:
        script: 대본 텍스트 (마크다운)
        title: 에피소드 타이틀
        era: 시대 (자동 감지 가능)
        video_duration_minutes: 예상 영상 길이 (분)

    Returns:
        {
            "era": str,
            "thumbnail": {...},
            "scenes": [{"timestamp_min": 0, "prompt": ..., ...}, ...],
            "figures_detected": [...],
        }
    """
    # 시대 감지
    if not era:
        era = detect_era(script)

    theme = get_era_theme(era)
    figures = detect_historical_figures(script)

    # 대본 씬 파싱
    parsed_scenes = parse_script_scenes(script)

    # 영상 길이에 맞게 타임스탬프 조정
    timestamps = IMAGE_TIMESTAMPS_MINUTES[:10]
    if video_duration_minutes < 13:
        # 짧은 영상이면 타임스탬프 비율 조정
        ratio = video_duration_minutes / 13
        timestamps = [int(t * ratio) for t in timestamps]

    # 각 타임스탬프에 해당하는 씬 매핑
    # 대본 전체 길이 기준으로 비율 계산
    total_content_length = sum(len(s["content"]) for s in parsed_scenes)

    scene_prompts = []
    image_types = _get_image_type_sequence(10)

    for i, timestamp in enumerate(timestamps):
        # 타임스탬프 → 대본 위치 추정
        position_ratio = timestamp / max(video_duration_minutes, 1)
        target_position = int(position_ratio * total_content_length)

        # 해당 위치의 씬 찾기
        current_pos = 0
        matched_scene = parsed_scenes[0] if parsed_scenes else None

        for scene in parsed_scenes:
            scene_end = current_pos + len(scene["content"])
            if current_pos <= target_position < scene_end:
                matched_scene = scene
                break
            current_pos = scene_end

        if not matched_scene:
            matched_scene = parsed_scenes[-1] if parsed_scenes else {"title": "장면", "content": ""}

        # 해당 씬에서 언급된 인물
        scene_figures = [f for f in figures if f in matched_scene.get("content", "")]

        # 씬 설명 생성
        scene_desc = generate_scene_description_from_content(
            scene_content=matched_scene.get("content", ""),
            scene_title=matched_scene.get("title", ""),
            era=era,
            figures=scene_figures,
        )

        # 프롬프트 생성
        prompt_data = generate_scene_prompt(
            scene_text=scene_desc,
            scene_index=i + 1,
            era=era,
            image_type=image_types[i],
            figures=scene_figures,
        )

        prompt_data["timestamp_min"] = timestamp
        prompt_data["timestamp_sec"] = timestamp * 60
        prompt_data["scene_title"] = matched_scene.get("title", f"씬 {i+1}")

        scene_prompts.append(prompt_data)

    # 썸네일 프롬프트
    main_figure = None
    for fig_name in HISTORICAL_FIGURES.keys():
        if fig_name in title:
            main_figure = fig_name
            break
    if not main_figure and figures:
        main_figure = figures[0]

    thumbnail = generate_thumbnail_prompt(title, era, main_figure)

    return {
        "era": era,
        "era_name": theme["name"],
        "video_duration_minutes": video_duration_minutes,
        "image_count": 10,
        "thumbnail": thumbnail,
        "scenes": scene_prompts,
        "timestamps": timestamps,
        "figures_detected": figures,
        "parsed_scenes": [{"num": s["scene_num"], "title": s["title"]} for s in parsed_scenes],
    }


# =============================================================================
# 씬 기반 이미지 생성 (씬당 2-3개, 총 10-15개)
# =============================================================================

# 씬 타입별 이미지 개수
SCENE_IMAGE_COUNT = {
    "인트로": 2,
    "도입": 2,
    "배경": 2,
    "본론": 3,
    "전개": 3,
    "클라이맥스": 3,
    "마무리": 2,
    "아웃트로": 2,
    "결론": 2,
}


def get_scene_image_count(scene_title: str) -> int:
    """씬 타이틀에서 이미지 개수 결정"""
    for key, count in SCENE_IMAGE_COUNT.items():
        if key in scene_title:
            return count
    return 2  # 기본값


def generate_scene_based_prompts(
    script: str,
    title: str,
    era: str = None,
) -> Dict[str, Any]:
    """
    씬 기반 이미지 프롬프트 생성 (씬당 2-3개)

    Args:
        script: 대본 텍스트 (마크다운)
        title: 에피소드 타이틀
        era: 시대 (자동 감지 가능)

    Returns:
        {
            "era": str,
            "thumbnail": {...},
            "scenes": [{"scene_num": 1, "scene_title": "...", "images": [...]}],
            "total_images": int,
        }
    """
    # 시대 감지
    if not era:
        era = detect_era(script)

    theme = get_era_theme(era)
    figures = detect_historical_figures(script)

    # 대본 씬 파싱
    parsed_scenes = parse_script_scenes(script)

    all_image_prompts = []
    scene_data = []
    image_index = 1

    for scene in parsed_scenes:
        scene_num = scene["scene_num"]
        scene_title = scene["title"]
        scene_content = scene["content"]

        # 이 씬에 필요한 이미지 개수
        image_count = get_scene_image_count(scene_title)

        # 씬 내용을 이미지 개수만큼 분할
        paragraphs = [p.strip() for p in scene_content.split('\n\n') if p.strip() and len(p.strip()) > 30]

        if not paragraphs:
            paragraphs = [scene_content]

        # 문단을 이미지 개수에 맞게 그룹화
        chunk_size = max(1, len(paragraphs) // image_count)
        grouped_paragraphs = []

        for i in range(image_count):
            start = i * chunk_size
            end = start + chunk_size if i < image_count - 1 else len(paragraphs)
            group = "\n\n".join(paragraphs[start:end])
            grouped_paragraphs.append(group)

        # 각 그룹에 대해 이미지 프롬프트 생성
        scene_images = []
        for i, para_group in enumerate(grouped_paragraphs):
            # 해당 문단에서 언급된 인물
            scene_figures = [f for f in figures if f in para_group]

            # 이미지 타입 결정
            if i == 0:
                img_type = "establishing_shot"
            elif "전투" in para_group or "반란" in para_group or "전쟁" in para_group:
                img_type = "battle_scene"
            elif "왕" in para_group or "조정" in para_group or "귀족" in para_group:
                img_type = "court_scene"
            elif "백성" in para_group or "마을" in para_group:
                img_type = "daily_life"
            else:
                img_type = "portrait" if scene_figures else "establishing_shot"

            # 씬 설명 생성
            scene_desc = generate_scene_description_from_content(
                scene_content=para_group,
                scene_title=scene_title,
                era=era,
                figures=scene_figures,
            )

            # 프롬프트 생성
            prompt_data = generate_scene_prompt(
                scene_text=scene_desc,
                scene_index=image_index,
                era=era,
                image_type=img_type,
                figures=scene_figures,
            )

            prompt_data["scene_num"] = scene_num
            prompt_data["scene_title"] = scene_title
            prompt_data["sub_index"] = i + 1
            prompt_data["content_preview"] = para_group[:100] + "..." if len(para_group) > 100 else para_group

            scene_images.append(prompt_data)
            all_image_prompts.append(prompt_data)
            image_index += 1

        scene_data.append({
            "scene_num": scene_num,
            "scene_title": scene_title,
            "image_count": len(scene_images),
            "images": scene_images,
        })

    # 썸네일 프롬프트
    main_figure = None
    for fig_name in HISTORICAL_FIGURES.keys():
        if fig_name in title:
            main_figure = fig_name
            break
    if not main_figure and figures:
        main_figure = figures[0]

    thumbnail = generate_thumbnail_prompt(title, era, main_figure)

    return {
        "era": era,
        "era_name": theme["name"],
        "total_images": len(all_image_prompts),
        "thumbnail": thumbnail,
        "scenes": scene_data,
        "all_prompts": all_image_prompts,
        "figures_detected": figures,
    }


def enhance_prompt_with_era(prompt: str, era: str) -> str:
    """기존 프롬프트에 시대 스타일 강제 적용"""
    theme = get_era_theme(era)

    enhanced = f"""
{BASE_QUALITY_TAGS}, {BASE_STYLE},
{theme['period']} korean history,
{prompt},
{theme['environment']},
{theme['lighting']},
{theme['palette']} color palette,
{theme['mood']} atmosphere
""".strip().replace("\n", " ")

    return enhanced


# =============================================================================
# 편의 함수
# =============================================================================
def get_available_eras() -> List[str]:
    """사용 가능한 시대 목록"""
    return list(ERA_VISUAL_THEMES.keys())


def get_era_info(era: str) -> Dict[str, Any]:
    """시대 정보 조회"""
    theme = ERA_VISUAL_THEMES.get(era)
    if not theme:
        return None

    figures_in_era = [
        name for name, info in HISTORICAL_FIGURES.items()
        if info["era"] == era
    ]

    return {
        "name": theme["name"],
        "period": theme["period"],
        "palette": theme["palette"],
        "mood": theme["mood"],
        "figures": figures_in_era,
        "keywords": ERA_KEYWORDS.get(era, []),
    }


def validate_prompts(prompts: Dict[str, Any]) -> Dict[str, Any]:
    """프롬프트 검증"""
    issues = []
    warnings = []

    # 썸네일 확인
    if not prompts.get("thumbnail"):
        issues.append("썸네일 프롬프트 없음")

    # 씬 개수 확인
    scenes = prompts.get("scenes", [])
    if len(scenes) < 5:
        issues.append(f"씬 이미지 부족: {len(scenes)}개 (최소 5개)")

    # 시대 일관성 확인
    era = prompts.get("era")
    for scene in scenes:
        if scene.get("era") != era:
            warnings.append(f"씬 {scene['scene_index']}: 시대 불일치")

    return {
        "valid": len(issues) == 0,
        "issues": issues,
        "warnings": warnings,
        "scene_count": len(scenes),
    }


if __name__ == "__main__":
    print("history_pipeline/image_agent.py 로드 완료")
    print(f"지원 시대: {', '.join(get_available_eras())}")
    print(f"등록 인물: {len(HISTORICAL_FIGURES)}명")
