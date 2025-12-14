# -*- coding: utf-8 -*-
"""카테고리별 프롬프트 규칙"""

from .health import HEALTH_RULES, get_health_prompt
from .news import NEWS_RULES, get_news_prompt
from .story import STORY_RULES, get_story_prompt

CATEGORY_PROMPTS = {
    'health': get_health_prompt,
    'news': get_news_prompt,
    'story': get_story_prompt,
}
