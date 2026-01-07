"""
blueprints 패키지
Flask Blueprint를 사용한 drama_server.py 모듈화

모듈 구성:
- gpt.py: GPT Chat API Blueprint (/api/gpt/*)
- ai_tools.py: AI 도구 API Blueprint (/api/ai-tools/*)
- sheets.py: Google Sheets API Blueprint (/api/sheets/*)
- youtube.py: YouTube API Blueprint (/api/youtube/*)

사용법:
    from blueprints.gpt import gpt_bp
    app.register_blueprint(gpt_bp)
"""

__version__ = '1.0.0'
