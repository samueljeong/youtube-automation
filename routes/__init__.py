"""
Flask Blueprint 라우트 모듈

drama_server.py에서 분리된 API 라우트들
"""

from flask import Blueprint

# Blueprint 등록 함수
def register_blueprints(app):
    """모든 Blueprint를 Flask 앱에 등록"""
    from .products import products_bp

    app.register_blueprint(products_bp)

    print("[ROUTES] Blueprints registered: products")
