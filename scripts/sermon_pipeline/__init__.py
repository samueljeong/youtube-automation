"""
Sermon Pipeline - 설교문 작성 파이프라인

Google Sheets 기반으로 Claude Code가 직접 설교문을 작성하는 시스템

모듈 구성:
- config.py: 설정 (헤더, 분량 기준)
- sheets.py: Google Sheets CRUD
"""

from .config import (
    SERMON_HEADERS,
    SERMON_LENGTH_BY_TYPE,
    CHARS_PER_MINUTE,
)
from .sheets import (
    get_pending_requests,
    save_sermon,
    init_sheet,
    get_all_sheet_names,
)

__all__ = [
    # config
    'SERMON_HEADERS',
    'SERMON_LENGTH_BY_TYPE',
    'CHARS_PER_MINUTE',
    # sheets
    'get_pending_requests',
    'save_sermon',
    'init_sheet',
    'get_all_sheet_names',
]

__version__ = '1.0.0'
