"""
blueprints 패키지
Flask Blueprint를 사용한 drama_server.py 모듈화

모듈 구성:
- gpt.py: GPT Chat API Blueprint (/api/gpt/*)
- ai_tools.py: AI 도구 API Blueprint (/api/ai-tools/*)
- shorts.py: Shorts Pipeline Blueprint (/api/shorts/*)
- isekai.py: Isekai Pipeline Blueprint (/api/isekai/*)
- bible.py: Bible Pipeline Blueprint (/api/bible/*, /api/sheets/create-bible)
- history.py: History Pipeline Blueprint (/api/history/*)

사용법:
    from blueprints.gpt import gpt_bp
    from blueprints.bible import bible_bp
    app.register_blueprint(gpt_bp)
    app.register_blueprint(bible_bp)
"""

__version__ = '1.0.0'
