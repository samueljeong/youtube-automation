# -*- coding: utf-8 -*-
"""카테고리별 프롬프트 규칙"""

from .health import HEALTH_RULES, get_health_prompt
from .news import NEWS_RULES, get_news_prompt
from .story import STORY_RULES, get_story_prompt
from .education import EDUCATION_RULES, get_education_prompt
from .faith import FAITH_RULES, get_faith_prompt
from .history import HISTORY_RULES, get_history_prompt
from .cooking import COOKING_RULES, get_cooking_prompt
from .finance import FINANCE_RULES, get_finance_prompt
from .motivation import MOTIVATION_RULES, get_motivation_prompt
from .mystery import MYSTERY_RULES, get_mystery_prompt
from .styles import CATEGORY_IMAGE_STYLES, get_category_style

CATEGORY_PROMPTS = {
    'health': get_health_prompt,
    'news': get_news_prompt,
    'story': get_story_prompt,
    'education': get_education_prompt,
    'faith': get_faith_prompt,
    'history': get_history_prompt,
    'cooking': get_cooking_prompt,
    'finance': get_finance_prompt,
    'motivation': get_motivation_prompt,
    'mystery': get_mystery_prompt,
}
