"""
sermon_modules 패키지
Flask Blueprint를 사용한 Sermon 앱 모듈화

모듈 구성:
- db.py: 데이터베이스 연결 및 초기화
- utils.py: 유틸리티 함수들
- auth.py: 인증, 크레딧 관리, 데코레이터
- step3_prompt_builder.py: 프롬프트 빌더 함수들
- bible.py: 개역개정 성경 본문 검색 (오타 없는 원문)
- api_sermon.py: 설교 처리 API Blueprint (준비됨)
- api_banner.py: 배너 API Blueprint (준비됨)
- api_admin.py: 관리자 API Blueprint (준비됨)

사용법:
    from sermon_modules.db import get_db_connection, init_db
    from sermon_modules.utils import calculate_cost, format_json_result
    from sermon_modules.auth import auth_bp, login_required
    from sermon_modules.step3_prompt_builder import build_prompt_from_json

    # API Blueprints (아직 마이그레이션 전)
    from sermon_modules.api_sermon import api_sermon_bp
    from sermon_modules.api_banner import api_banner_bp
    from sermon_modules.api_admin import api_admin_bp
"""

from .db import (
    get_db_connection,
    init_db,
    get_setting,
    set_setting,
    USE_POSTGRES
)

from .utils import (
    calculate_cost,
    format_json_result,
    remove_markdown,
    is_json_guide,
    parse_json_guide,
    MODEL_PRICING
)

from .auth import (
    auth_bp,
    login_required,
    admin_required,
    api_login_required,
    get_user_credits,
    use_credit,
    add_credits,
    set_credits,
    AUTH_ENABLED
)

from .step3_prompt_builder import (
    get_system_prompt_for_step,
    build_prompt_from_json,
    build_step3_prompt_from_json,
    get_step2_prompt_for_style,
    get_step3_prompt_for_style,
    get_style_structure_template,
    get_style_checklist,
    get_style_illustration_guide
)

from .styles import (
    get_style,
    get_style_info,
    get_available_styles,
    READABILITY_GUIDE
)

from .strongs import (
    analyze_verse_strongs,
    format_strongs_for_prompt,
    get_strongs_lookup
)

from .commentary import (
    get_verse_commentary,
    format_commentary_for_prompt,
    init_commentary_service,
    COMMENTARY_STYLES
)

from .context import (
    get_current_context,
    format_context_for_prompt,
    get_audience_types,
    init_context_service,
    validate_illustration,
    suggest_illustrations,
    AUDIENCE_INTERESTS,
    CONTROVERSIAL_KEYWORDS
)

from .bible import (
    get_verses,
    get_verses_from_reference,
    format_verses,
    format_verses_for_prompt,
    parse_reference,
    get_book_info,
    search_verses,
    BOOK_MAP
)

__version__ = '1.0.0'
__all__ = [
    # db
    'get_db_connection', 'init_db', 'get_setting', 'set_setting', 'USE_POSTGRES',
    # utils
    'calculate_cost', 'format_json_result', 'remove_markdown',
    'is_json_guide', 'parse_json_guide', 'MODEL_PRICING',
    # auth
    'auth_bp', 'login_required', 'admin_required', 'api_login_required',
    'get_user_credits', 'use_credit', 'add_credits', 'set_credits', 'AUTH_ENABLED',
    # prompt
    'get_system_prompt_for_step', 'build_prompt_from_json', 'build_step3_prompt_from_json',
    'get_step2_prompt_for_style', 'get_step3_prompt_for_style',
    'get_style_structure_template', 'get_style_checklist', 'get_style_illustration_guide',
    # styles
    'get_style', 'get_style_info', 'get_available_styles', 'READABILITY_GUIDE',
    # strongs
    'analyze_verse_strongs', 'format_strongs_for_prompt', 'get_strongs_lookup',
    # commentary
    'get_verse_commentary', 'format_commentary_for_prompt', 'init_commentary_service', 'COMMENTARY_STYLES',
    # context
    'get_current_context', 'format_context_for_prompt', 'get_audience_types', 'AUDIENCE_INTERESTS',
    'init_context_service', 'validate_illustration', 'suggest_illustrations', 'CONTROVERSIAL_KEYWORDS',
    # bible
    'get_verses', 'get_verses_from_reference', 'format_verses', 'format_verses_for_prompt',
    'parse_reference', 'get_book_info', 'search_verses', 'BOOK_MAP',
]
