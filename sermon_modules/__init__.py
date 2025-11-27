"""
sermon_modules 패키지
Flask Blueprint를 사용한 Sermon 앱 모듈화

모듈 구성:
- db.py: 데이터베이스 연결 및 초기화
- utils.py: 유틸리티 함수들
- auth.py: 인증, 크레딧 관리, 데코레이터
- prompt.py: 프롬프트 빌더 함수들

사용법:
    from sermon_modules.db import get_db_connection, init_db
    from sermon_modules.utils import calculate_cost, format_json_result
    from sermon_modules.auth import auth_bp, login_required
    from sermon_modules.prompt import build_prompt_from_json
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

from .prompt import (
    get_system_prompt_for_step,
    build_prompt_from_json,
    build_step3_prompt_from_json
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
]
