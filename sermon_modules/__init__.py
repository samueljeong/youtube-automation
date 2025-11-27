"""
sermon_modules 패키지
Flask Blueprint를 사용한 Sermon 앱 모듈화

사용법:
    from sermon_modules import create_sermon_blueprints
    app.register_blueprint(sermon_bp)
"""

from flask import Blueprint

# Blueprint 생성
sermon_bp = Blueprint('sermon', __name__)

# 버전 정보
__version__ = '1.0.0'
