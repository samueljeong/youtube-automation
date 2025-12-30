# -*- coding: utf-8 -*-
"""카테고리별 이미지 스타일 정의 (단일 소스)

모든 이미지 스타일 정의는 여기서만 관리합니다.
drama_server.py에서 이 파일을 import해서 사용합니다.
"""

CATEGORY_IMAGE_STYLES = {
    'history': {
        'name': 'Historical Webtoon with Vivid Colors',
        'style_prompt': '''Korean webtoon style illustration, [SCENE DESCRIPTION],

★★★ SCENE-SPECIFIC COLOR PALETTE (CRITICAL!) ★★★
Analyze the scene mood and apply ONE of these color schemes to the ENTIRE scene:

1. Battle/War/Anger → FIERY ORANGE-RED palette:
   - Orange sunset sky, red flames, yellow dust
   - NO blue, NO green, NO cold colors

2. Royal/Court/Authority → WARM GOLD-AMBER palette:
   - Golden light, orange-red pillars, amber candles
   - NO blue, NO cold tones

3. Tragedy/Sorrow/Loss → COLD BLUE-GRAY palette:
   - Steel gray sky, blue rain, slate fog
   - NO warm colors, desaturated

4. Victory/Hope/Success → BRIGHT GREEN-BLUE palette:
   - Clear blue sky, emerald valleys, golden sun
   - NO dark colors, high saturation

5. Conspiracy/Tension/Secret → DARK PURPLE-BLACK palette:
   - Purple moonlight, black shadows, indigo
   - NO bright colors, low brightness

Period-accurate Korean historical costume ([ERA] style),
Character in mid-ground (30-40% of frame),
Detailed historical background (50-60% of frame),
Bold black outlines, cinematic wide shot composition,
NO photorealistic, NO anime, NO modern elements,
NO text, NO watermark, 16:9 aspect ratio''',
        'forbidden': 'NO earth tone, NO sepia, NO brown base, NO monochrome, NO photorealistic, NO anime style, NO modern clothing, NO character taking more than 45% of frame',
        'required': 'Korean webtoon style, bold black outlines, SCENE-SPECIFIC vivid colors (orange-red for war, gold for court, blue-gray for tragedy, green-blue for victory, purple-black for conspiracy), period-accurate costumes, cinematic wide shot'
    },
    'news': {
        'name': 'Modern News Infographic',
        'style_prompt': '''Modern news explainer illustration, [SCENE DESCRIPTION],
clean professional style with subtle webtoon influence,
corporate color palette (navy blue, white, subtle orange accents),
clean geometric shapes, minimal shadows,
infographic-inspired composition,
professional lighting, sharp clean lines,
clearly illustration NOT photograph,
NO text, NO watermark, NO labels,
16:9 cinematic composition''',
        'forbidden': 'NO photorealistic, NO extreme expressions, NO cluttered backgrounds',
        'required': 'Clean professional aesthetic, corporate colors, infographic style'
    },
    'mystery': {
        'name': 'Dark Cinematic Thriller',
        'style_prompt': '''Dark cinematic thriller illustration, [SCENE DESCRIPTION],
film noir inspired lighting with deep shadows,
muted desaturated color palette (dark blues, grays, blacks),
high contrast dramatic lighting,
mysterious atmospheric fog or haze,
single spotlight or moonlight source,
suspenseful tense atmosphere,
clearly artistic illustration NOT photograph,
NO text, NO watermark, NO labels,
16:9 cinematic composition''',
        'forbidden': 'NO bright colors, NO cartoon style, NO gore, NO cheap horror clichés',
        'required': 'Dark moody atmosphere, film noir lighting, muted colors, suspenseful tension'
    },
    'story': {
        'name': 'Korean Webtoon Style',
        'style_prompt': '''Korean webtoon style illustration, [SCENE DESCRIPTION],
expressive character with exaggerated emotions,
clean bold outlines, vibrant flat colors,
manga-style expression marks (sweat drops, impact lines),
dynamic composition,
NO photorealistic, NO stickman, NO 3D render,
NO text, NO watermark,
16:9 aspect ratio''',
        'forbidden': 'NO photorealistic, NO stickman, NO calm/neutral expressions',
        'required': 'Korean webtoon style, exaggerated expressions, bold outlines'
    },
    'health': {
        'name': 'Medical Infographic Webtoon',
        'style_prompt': '''Korean webtoon style medical illustration, [SCENE DESCRIPTION],
clean professional medical aesthetic,
soft blue and white color palette with accent colors,
friendly approachable character design,
clear informative composition,
NO gore, NO disturbing imagery,
NO text, NO watermark,
16:9 aspect ratio''',
        'forbidden': 'NO gore, NO disturbing imagery, NO overly dramatic',
        'required': 'Clean medical aesthetic, friendly characters, informative layout'
    },
    'faith': {
        'name': 'Biblical Webtoon Style',
        'style_prompt': '''Korean webtoon style biblical illustration, [SCENE DESCRIPTION],
reverent warm atmosphere,
golden and earth tone palette with divine light effects,
period-accurate ancient Middle Eastern clothing,
spiritual peaceful composition,
NO text, NO watermark,
16:9 aspect ratio''',
        'forbidden': 'NO modern elements, NO disrespectful imagery',
        'required': 'Reverent atmosphere, warm golden tones, period-accurate costumes'
    }
}


def get_category_style(category: str) -> dict:
    """카테고리별 이미지 스타일 반환

    Args:
        category: 카테고리 이름 (history, news, mystery, story, health, faith)

    Returns:
        스타일 딕셔너리 (name, style_prompt, forbidden, required)
        없으면 None
    """
    return CATEGORY_IMAGE_STYLES.get(category)
