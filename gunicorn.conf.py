import os

# Server socket
bind = f"0.0.0.0:{os.environ.get('PORT', '10000')}"

# Worker processes
# ★ Race Condition 방지: 파이프라인 동시 실행 문제로 워커 1개로 제한
# threading.Lock()은 프로세스 간에 공유되지 않음
workers = int(os.environ.get('GUNICORN_WORKERS', '1'))
worker_class = 'sync'
worker_connections = 1000
timeout = int(os.environ.get('GUNICORN_TIMEOUT', '7200'))  # 환경변수 사용 (기본 2시간)
keepalive = 5
graceful_timeout = 300  # graceful shutdown 5분

# Logging
accesslog = '-'
errorlog = '-'
loglevel = 'info'

# Process naming
proc_name = 'drama_server'

# Server mechanics
daemon = False
preload_app = True
