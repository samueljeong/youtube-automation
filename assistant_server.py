"""
Personal AI Assistant - 메인 대시보드 서버
Mac(iCloud) 일정/미리알림과 웹 서버(DB) 데이터를 통합 관리하는 허브
"""
import os
import json
from datetime import datetime, date, timedelta
from flask import Blueprint, request, jsonify, render_template

# OpenAI (GPT-4o-mini for parsing)
from openai import OpenAI

def get_openai_client():
    key = (os.getenv("OPENAI_API_KEY") or "").strip()
    if not key:
        return None
    return OpenAI(api_key=key)

assistant_bp = Blueprint('assistant', __name__)

# ===== 데이터베이스 설정 =====
DATABASE_URL = os.getenv('DATABASE_URL')
USE_POSTGRES = DATABASE_URL is not None

if USE_POSTGRES:
    import psycopg2
    from psycopg2.extras import RealDictCursor

    # Render의 postgres:// URL을 postgresql://로 변경
    if DATABASE_URL.startswith('postgres://'):
        DATABASE_URL = DATABASE_URL.replace('postgres://', 'postgresql://', 1)

    def get_db_connection():
        conn = psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)
        return conn
else:
    import sqlite3
    DB_PATH = os.path.join(os.path.dirname(__file__), 'assistant_data.db')

    def get_db_connection():
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        return conn


# ===== 데이터베이스 초기화 =====
def init_assistant_db():
    """Assistant DB 테이블 초기화"""
    conn = get_db_connection()
    cursor = conn.cursor()

    if USE_POSTGRES:
        # PostgreSQL 스키마
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS events (
                id SERIAL PRIMARY KEY,
                title VARCHAR(500) NOT NULL,
                start_time TIMESTAMP,
                end_time TIMESTAMP,
                category VARCHAR(100),
                location VARCHAR(200),
                notes TEXT,
                source VARCHAR(50) DEFAULT 'web',
                sync_status VARCHAR(50) DEFAULT 'pending_to_mac',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # 기존 테이블에 location, notes 컬럼 추가 (이미 존재하면 무시)
        try:
            cursor.execute('ALTER TABLE events ADD COLUMN IF NOT EXISTS location VARCHAR(200)')
            cursor.execute('ALTER TABLE events ADD COLUMN IF NOT EXISTS notes TEXT')
        except Exception:
            pass  # 컬럼이 이미 존재하면 무시

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS tasks (
                id SERIAL PRIMARY KEY,
                title VARCHAR(500) NOT NULL,
                due_date DATE,
                priority VARCHAR(20) DEFAULT 'medium',
                category VARCHAR(100),
                is_completed BOOLEAN DEFAULT FALSE,
                source VARCHAR(50) DEFAULT 'web',
                sync_status VARCHAR(50) DEFAULT 'pending_to_mac',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS attendance (
                id SERIAL PRIMARY KEY,
                name VARCHAR(200) NOT NULL,
                date DATE NOT NULL,
                status VARCHAR(20) DEFAULT 'present',
                source VARCHAR(50) DEFAULT 'web',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
    else:
        # SQLite 스키마
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                start_time DATETIME,
                end_time DATETIME,
                category TEXT,
                location TEXT,
                notes TEXT,
                source TEXT DEFAULT 'web',
                sync_status TEXT DEFAULT 'pending_to_mac',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # 기존 테이블에 location, notes 컬럼 추가 (SQLite는 IF NOT EXISTS 미지원)
        try:
            cursor.execute('ALTER TABLE events ADD COLUMN location TEXT')
        except Exception:
            pass
        try:
            cursor.execute('ALTER TABLE events ADD COLUMN notes TEXT')
        except Exception:
            pass

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                due_date DATE,
                priority TEXT DEFAULT 'medium',
                category TEXT,
                is_completed INTEGER DEFAULT 0,
                source TEXT DEFAULT 'web',
                sync_status TEXT DEFAULT 'pending_to_mac',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS attendance (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                date DATE NOT NULL,
                status TEXT DEFAULT 'present',
                source TEXT DEFAULT 'web',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')

    conn.commit()
    conn.close()
    print("[ASSISTANT-DB] 테이블 초기화 완료")


# ===== 메인 대시보드 라우트 =====
@assistant_bp.route('/assistant')
def assistant_dashboard():
    """메인 대시보드 페이지 렌더링"""
    return render_template('assistant.html')


# ===== 이벤트 API =====
@assistant_bp.route('/assistant/api/events', methods=['GET'])
def get_events():
    """이벤트 목록 조회"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # 오늘 날짜 기준으로 이번 주 이벤트 조회
        today = date.today()
        week_end = today + timedelta(days=7)

        if USE_POSTGRES:
            cursor.execute('''
                SELECT * FROM events
                WHERE DATE(start_time) >= %s AND DATE(start_time) <= %s
                ORDER BY start_time ASC
            ''', (today, week_end))
        else:
            cursor.execute('''
                SELECT * FROM events
                WHERE DATE(start_time) >= ? AND DATE(start_time) <= ?
                ORDER BY start_time ASC
            ''', (today.isoformat(), week_end.isoformat()))

        events = cursor.fetchall()
        conn.close()

        # Row 객체를 dict로 변환
        events_list = [dict(row) for row in events]

        # datetime 객체를 문자열로 변환
        for event in events_list:
            for key in ['start_time', 'end_time', 'created_at', 'updated_at']:
                if event.get(key) and not isinstance(event[key], str):
                    event[key] = event[key].isoformat()

        return jsonify({
            'success': True,
            'events': events_list,
            'today': today.isoformat(),
            'week_end': week_end.isoformat()
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@assistant_bp.route('/assistant/api/events', methods=['POST'])
def create_event():
    """새 이벤트 생성"""
    try:
        data = request.get_json()

        conn = get_db_connection()
        cursor = conn.cursor()

        if USE_POSTGRES:
            cursor.execute('''
                INSERT INTO events (title, start_time, end_time, category, source, sync_status)
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING id
            ''', (
                data.get('title'),
                data.get('start_time'),
                data.get('end_time'),
                data.get('category', ''),
                data.get('source', 'web'),
                'pending_to_mac'
            ))
            event_id = cursor.fetchone()['id']
        else:
            cursor.execute('''
                INSERT INTO events (title, start_time, end_time, category, source, sync_status)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                data.get('title'),
                data.get('start_time'),
                data.get('end_time'),
                data.get('category', ''),
                data.get('source', 'web'),
                'pending_to_mac'
            ))
            event_id = cursor.lastrowid

        conn.commit()
        conn.close()

        return jsonify({
            'success': True,
            'id': event_id,
            'message': '이벤트가 생성되었습니다.'
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# ===== 태스크 API =====
@assistant_bp.route('/assistant/api/tasks', methods=['GET'])
def get_tasks():
    """태스크 목록 조회"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        if USE_POSTGRES:
            cursor.execute('''
                SELECT * FROM tasks
                WHERE is_completed = FALSE
                ORDER BY due_date ASC NULLS LAST, priority DESC
            ''')
        else:
            cursor.execute('''
                SELECT * FROM tasks
                WHERE is_completed = 0
                ORDER BY due_date ASC, priority DESC
            ''')

        tasks = cursor.fetchall()
        conn.close()

        tasks_list = [dict(row) for row in tasks]

        # date 객체를 문자열로 변환
        for task in tasks_list:
            for key in ['due_date', 'created_at', 'updated_at']:
                if task.get(key) and not isinstance(task[key], str):
                    task[key] = task[key].isoformat() if hasattr(task[key], 'isoformat') else str(task[key])

        return jsonify({
            'success': True,
            'tasks': tasks_list
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@assistant_bp.route('/assistant/api/tasks', methods=['POST'])
def create_task():
    """새 태스크 생성"""
    try:
        data = request.get_json()

        conn = get_db_connection()
        cursor = conn.cursor()

        if USE_POSTGRES:
            cursor.execute('''
                INSERT INTO tasks (title, due_date, priority, category, source, sync_status)
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING id
            ''', (
                data.get('title'),
                data.get('due_date'),
                data.get('priority', 'medium'),
                data.get('category', ''),
                data.get('source', 'web'),
                'pending_to_mac'
            ))
            task_id = cursor.fetchone()['id']
        else:
            cursor.execute('''
                INSERT INTO tasks (title, due_date, priority, category, source, sync_status)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                data.get('title'),
                data.get('due_date'),
                data.get('priority', 'medium'),
                data.get('category', ''),
                data.get('source', 'web'),
                'pending_to_mac'
            ))
            task_id = cursor.lastrowid

        conn.commit()
        conn.close()

        return jsonify({
            'success': True,
            'id': task_id,
            'message': '태스크가 생성되었습니다.'
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@assistant_bp.route('/assistant/api/tasks/<int:task_id>/complete', methods=['POST'])
def complete_task(task_id):
    """태스크 완료 처리"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        if USE_POSTGRES:
            cursor.execute('''
                UPDATE tasks SET is_completed = TRUE, updated_at = CURRENT_TIMESTAMP
                WHERE id = %s
            ''', (task_id,))
        else:
            cursor.execute('''
                UPDATE tasks SET is_completed = 1, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            ''', (task_id,))

        conn.commit()
        conn.close()

        return jsonify({
            'success': True,
            'message': '태스크가 완료되었습니다.'
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# ===== Mac 연동 API (Shortcuts 호출용) =====
@assistant_bp.route('/assistant/api/sync/from-mac', methods=['POST'])
def sync_from_mac():
    """
    Mac 단축어에서 Calendar/Reminders 데이터를 받아 저장
    Body: { "events": [...], "tasks": [...] }
    """
    try:
        data = request.get_json()

        conn = get_db_connection()
        cursor = conn.cursor()

        events_added = 0
        tasks_added = 0

        # 이벤트 저장
        for event in data.get('events', []):
            if USE_POSTGRES:
                cursor.execute('''
                    INSERT INTO events (title, start_time, end_time, category, source, sync_status)
                    VALUES (%s, %s, %s, %s, %s, %s)
                ''', (
                    event.get('title'),
                    event.get('start_time'),
                    event.get('end_time'),
                    event.get('category', ''),
                    'mac_calendar',
                    'synced'
                ))
            else:
                cursor.execute('''
                    INSERT INTO events (title, start_time, end_time, category, source, sync_status)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (
                    event.get('title'),
                    event.get('start_time'),
                    event.get('end_time'),
                    event.get('category', ''),
                    'mac_calendar',
                    'synced'
                ))
            events_added += 1

        # 태스크 저장
        for task in data.get('tasks', []):
            if USE_POSTGRES:
                cursor.execute('''
                    INSERT INTO tasks (title, due_date, priority, category, source, sync_status)
                    VALUES (%s, %s, %s, %s, %s, %s)
                ''', (
                    task.get('title'),
                    task.get('due_date'),
                    task.get('priority', 'medium'),
                    task.get('category', ''),
                    'mac_reminders',
                    'synced'
                ))
            else:
                cursor.execute('''
                    INSERT INTO tasks (title, due_date, priority, category, source, sync_status)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (
                    task.get('title'),
                    task.get('due_date'),
                    task.get('priority', 'medium'),
                    task.get('category', ''),
                    'mac_reminders',
                    'synced'
                ))
            tasks_added += 1

        conn.commit()
        conn.close()

        return jsonify({
            'success': True,
            'message': f'Mac에서 동기화 완료: 이벤트 {events_added}개, 태스크 {tasks_added}개',
            'events_added': events_added,
            'tasks_added': tasks_added
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@assistant_bp.route('/assistant/api/sync/to-mac', methods=['GET'])
def sync_to_mac():
    """
    Mac 단축어가 가져갈 pending_to_mac 상태의 데이터 반환
    단축어가 이 데이터를 Calendar/Reminders에 추가

    쿼리 파라미터:
    - type: 'events' | 'tasks' | None (둘 다)
    - category: 특정 카테고리만 필터링 (선택)
    """
    try:
        sync_type = request.args.get('type')  # 'events', 'tasks', or None
        category_filter = request.args.get('category')  # 선택적 카테고리 필터

        conn = get_db_connection()
        cursor = conn.cursor()

        events = []
        tasks = []

        # 이벤트 조회 (type이 없거나 'events'일 때)
        if not sync_type or sync_type == 'events':
            if category_filter:
                if USE_POSTGRES:
                    cursor.execute('''
                        SELECT * FROM events WHERE sync_status = %s AND category = %s
                    ''', ('pending_to_mac', category_filter))
                else:
                    cursor.execute('''
                        SELECT * FROM events WHERE sync_status = ? AND category = ?
                    ''', ('pending_to_mac', category_filter))
            else:
                if USE_POSTGRES:
                    cursor.execute('''
                        SELECT * FROM events WHERE sync_status = %s
                    ''', ('pending_to_mac',))
                else:
                    cursor.execute('''
                        SELECT * FROM events WHERE sync_status = ?
                    ''', ('pending_to_mac',))
            events = [dict(row) for row in cursor.fetchall()]

        # 태스크 조회 (type이 없거나 'tasks'일 때)
        if not sync_type or sync_type == 'tasks':
            if category_filter:
                if USE_POSTGRES:
                    cursor.execute('''
                        SELECT * FROM tasks WHERE sync_status = %s AND category = %s
                    ''', ('pending_to_mac', category_filter))
                else:
                    cursor.execute('''
                        SELECT * FROM tasks WHERE sync_status = ? AND category = ?
                    ''', ('pending_to_mac', category_filter))
            else:
                if USE_POSTGRES:
                    cursor.execute('''
                        SELECT * FROM tasks WHERE sync_status = %s
                    ''', ('pending_to_mac',))
                else:
                    cursor.execute('''
                        SELECT * FROM tasks WHERE sync_status = ?
                    ''', ('pending_to_mac',))
            tasks = [dict(row) for row in cursor.fetchall()]

        conn.close()

        # datetime 객체를 문자열로 변환
        for event in events:
            for key in ['start_time', 'end_time', 'created_at', 'updated_at']:
                if event.get(key) and not isinstance(event[key], str):
                    event[key] = event[key].isoformat()

        for task in tasks:
            for key in ['due_date', 'created_at', 'updated_at']:
                if task.get(key) and not isinstance(task[key], str):
                    task[key] = task[key].isoformat() if hasattr(task[key], 'isoformat') else str(task[key])

        return jsonify({
            'success': True,
            'events': events,
            'tasks': tasks,
            'total_pending': len(events) + len(tasks)
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@assistant_bp.route('/assistant/api/sync/mark-synced', methods=['POST'])
def mark_synced():
    """
    Mac 단축어가 동기화 완료 후 호출하여 sync_status를 'synced'로 변경
    Body: { "event_ids": [...], "task_ids": [...] }
    """
    try:
        data = request.get_json()

        conn = get_db_connection()
        cursor = conn.cursor()

        event_ids = data.get('event_ids', [])
        task_ids = data.get('task_ids', [])

        if event_ids:
            if USE_POSTGRES:
                cursor.execute('''
                    UPDATE events SET sync_status = %s, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ANY(%s)
                ''', ('synced', event_ids))
            else:
                placeholders = ','.join('?' * len(event_ids))
                cursor.execute(f'''
                    UPDATE events SET sync_status = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE id IN ({placeholders})
                ''', ['synced'] + event_ids)

        if task_ids:
            if USE_POSTGRES:
                cursor.execute('''
                    UPDATE tasks SET sync_status = %s, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ANY(%s)
                ''', ('synced', task_ids))
            else:
                placeholders = ','.join('?' * len(task_ids))
                cursor.execute(f'''
                    UPDATE tasks SET sync_status = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE id IN ({placeholders})
                ''', ['synced'] + task_ids)

        conn.commit()
        conn.close()

        return jsonify({
            'success': True,
            'message': f'동기화 완료 처리: 이벤트 {len(event_ids)}개, 태스크 {len(task_ids)}개'
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# 단축어 B 호환용 별칭 (mark-synced와 동일)
@assistant_bp.route('/assistant/api/sync/confirm', methods=['POST'])
def sync_confirm():
    """Mac 단축어 B에서 사용하는 동기화 완료 확인 API (mark-synced 별칭)"""
    return mark_synced()


# ===== AI 파싱 API (GPT-4o-mini) =====
@assistant_bp.route('/assistant/api/parse', methods=['POST'])
def parse_input():
    """
    자유 형식 텍스트를 AI가 분석하여 이벤트/태스크로 구조화
    입력: { "text": "이번주 금요일 청년부 총회 오후 2시" }
    출력: { "events": [...], "tasks": [...] }
    """
    try:
        data = request.get_json()
        text = data.get('text', '').strip()

        if not text:
            return jsonify({'success': False, 'error': '텍스트가 비어있습니다.'}), 400

        client = get_openai_client()
        if not client:
            return jsonify({'success': False, 'error': 'OpenAI API 키가 설정되지 않았습니다.'}), 500

        today = date.today()
        default_category = data.get('default_category', None)

        # 상세 GPT 파싱 프롬프트
        system_prompt = f"""[역할]
너는 '개인 비서용 일정/할 일 파서'이다.
사용자가 붙여넣은 한국어/영어 텍스트를 읽고,
그 안에 있는 일정(events)과 할 일(tasks)을 구조화된 JSON으로 추출하는 것이 너의 유일한 역할이다.

[입력 컨텍스트]
- 오늘 날짜: {today.isoformat()} ({today.strftime('%A')})
- 기본 카테고리: {default_category or '없음'}

[출력]
반드시 다음 JSON 형식으로만 출력하라:
{{
  "events": [
    {{
      "title": "string",
      "date": "yyyy-MM-dd",
      "time": "HH:mm or null",
      "end_time": "HH:mm or null",
      "category": "교회 | 사업 | 유튜브 | 가정 | 공부 | 기타",
      "location": "string or null",
      "notes": "string or null"
    }}
  ],
  "tasks": [
    {{
      "title": "string",
      "due_date": "yyyy-MM-dd or null",
      "category": "교회 | 사업 | 유튜브 | 가정 | 공부 | 기타",
      "priority": "high | normal | low",
      "notes": "string or null"
    }}
  ]
}}

[규칙]
1. 날짜/시간 처리
   - 구체적인 날짜가 나오면 yyyy-MM-dd 형식으로 변환한다.
   - "이번 주 금요일", "다음 주일" 등 상대적 표현은 오늘 날짜를 기준으로 실제 날짜를 계산한다.
   - 시간이 없으면 time은 null로 둔다.

2. title 작성
   - 최대한 짧고 요약된 표현으로 작성한다.
   - 한 텍스트 안에 여러 일정이 있으면 각각 별도의 event로 나눈다.

3. events vs tasks 판단
   - 특정 시간/날짜에 실제로 '열리는 모임/행사/예배/회의'는 event로 처리한다.
   - 그 행사를 준비하기 위한 "해야 할 일" (자료 준비, 문자 발송, 설교 작성 등)은 task로 처리한다.

4. category 분류
   - 교회: 예배, 기도회, 총회, 구역모임, 출석, 심방, 교회 행사 등
   - 사업: 무역, 스마트스토어, 재고, 배송, 세금, 광고, 클라이언트 미팅 등
   - 유튜브: 촬영, 편집, 썸네일, 스크립트, 업로드 일정 등
   - 가정: 가족 모임, 아이 일정, 개인 건강/가사 관련 등
   - 공부: 코딩 공부, 강의 수강, 책 읽기 등의 학습 관련
   - 기타: 위 분류에 명확히 속하지 않는 경우

5. priority 설정
   - 남은 시간이 짧거나(3일 이내), 중요해 보이는 작업은 high로 설정한다.
   - 일반적인 준비/보조 작업은 normal.
   - 언제 해도 되는 장기적인 아이디어 수준이면 low.

6. 모호한 경우
   - 날짜/시간이 전혀 없지만 분명히 '해야 할 일'이면 task로 추가하되, due_date는 null로 둔다.
   - 이해가 불가능한 정보는 무시한다. 추측으로 일정이나 할 일을 만들어내지 마라.

JSON 외의 다른 텍스트(설명, 말투, 주석 등)는 절대로 출력하지 마라."""

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": text}
            ],
            temperature=0.3,
            response_format={"type": "json_object"}
        )

        result = json.loads(response.choices[0].message.content)

        # save_to_db 파라미터가 true면 DB에 저장
        save_to_db = data.get('save_to_db', False)
        saved_events = []
        saved_tasks = []

        if save_to_db:
            conn = get_db_connection()
            cursor = conn.cursor()

            # 이벤트 저장
            for event in result.get('events', []):
                start_time = None
                if event.get('date'):
                    time_str = event.get('time') or '00:00'
                    start_time = f"{event['date']}T{time_str}:00"

                end_time = None
                if event.get('date') and event.get('end_time'):
                    end_time = f"{event['date']}T{event['end_time']}:00"

                if USE_POSTGRES:
                    cursor.execute('''
                        INSERT INTO events (title, start_time, end_time, category, source, sync_status)
                        VALUES (%s, %s, %s, %s, %s, %s)
                        RETURNING id
                    ''', (
                        event.get('title'),
                        start_time,
                        end_time,
                        event.get('category', '기타'),
                        'gpt_parse',
                        'pending_to_mac'
                    ))
                    event_id = cursor.fetchone()['id']
                else:
                    cursor.execute('''
                        INSERT INTO events (title, start_time, end_time, category, source, sync_status)
                        VALUES (?, ?, ?, ?, ?, ?)
                    ''', (
                        event.get('title'),
                        start_time,
                        end_time,
                        event.get('category', '기타'),
                        'gpt_parse',
                        'pending_to_mac'
                    ))
                    event_id = cursor.lastrowid

                saved_events.append({'id': event_id, 'title': event.get('title')})

            # 태스크 저장
            for task in result.get('tasks', []):
                if USE_POSTGRES:
                    cursor.execute('''
                        INSERT INTO tasks (title, due_date, priority, category, source, sync_status)
                        VALUES (%s, %s, %s, %s, %s, %s)
                        RETURNING id
                    ''', (
                        task.get('title'),
                        task.get('due_date'),
                        task.get('priority', 'normal'),
                        task.get('category', '기타'),
                        'gpt_parse',
                        'pending_to_mac'
                    ))
                    task_id = cursor.fetchone()['id']
                else:
                    cursor.execute('''
                        INSERT INTO tasks (title, due_date, priority, category, source, sync_status)
                        VALUES (?, ?, ?, ?, ?, ?)
                    ''', (
                        task.get('title'),
                        task.get('due_date'),
                        task.get('priority', 'normal'),
                        task.get('category', '기타'),
                        'gpt_parse',
                        'pending_to_mac'
                    ))
                    task_id = cursor.lastrowid

                saved_tasks.append({'id': task_id, 'title': task.get('title')})

            conn.commit()
            conn.close()

        return jsonify({
            'success': True,
            'parsed': result,
            'original_text': text,
            'saved_to_db': save_to_db,
            'saved_events': saved_events,
            'saved_tasks': saved_tasks
        })
    except json.JSONDecodeError as e:
        return jsonify({'success': False, 'error': f'JSON 파싱 오류: {str(e)}'}), 500
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# ===== 출석 API =====
@assistant_bp.route('/assistant/api/attendance', methods=['POST'])
def upload_attendance():
    """
    출석 데이터 업로드 (파일 또는 JSON)
    Body: { "date": "YYYY-MM-DD", "records": [{"name": "홍길동", "status": "present"}, ...] }
    """
    try:
        data = request.get_json()

        attendance_date = data.get('date', date.today().isoformat())
        records = data.get('records', [])

        if not records:
            return jsonify({'success': False, 'error': '출석 데이터가 비어있습니다.'}), 400

        conn = get_db_connection()
        cursor = conn.cursor()

        added = 0
        for record in records:
            if USE_POSTGRES:
                cursor.execute('''
                    INSERT INTO attendance (name, date, status, source)
                    VALUES (%s, %s, %s, %s)
                ''', (
                    record.get('name'),
                    attendance_date,
                    record.get('status', 'present'),
                    'web'
                ))
            else:
                cursor.execute('''
                    INSERT INTO attendance (name, date, status, source)
                    VALUES (?, ?, ?, ?)
                ''', (
                    record.get('name'),
                    attendance_date,
                    record.get('status', 'present'),
                    'web'
                ))
            added += 1

        conn.commit()
        conn.close()

        return jsonify({
            'success': True,
            'message': f'{attendance_date} 출석 데이터 {added}건 저장 완료'
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@assistant_bp.route('/assistant/api/attendance', methods=['GET'])
def get_attendance():
    """특정 날짜의 출석 데이터 조회"""
    try:
        target_date = request.args.get('date', date.today().isoformat())

        conn = get_db_connection()
        cursor = conn.cursor()

        if USE_POSTGRES:
            cursor.execute('''
                SELECT * FROM attendance WHERE date = %s ORDER BY name
            ''', (target_date,))
        else:
            cursor.execute('''
                SELECT * FROM attendance WHERE date = ? ORDER BY name
            ''', (target_date,))

        records = [dict(row) for row in cursor.fetchall()]
        conn.close()

        # date 객체를 문자열로 변환
        for record in records:
            if record.get('date') and not isinstance(record['date'], str):
                record['date'] = record['date'].isoformat()
            if record.get('created_at') and not isinstance(record['created_at'], str):
                record['created_at'] = record['created_at'].isoformat()

        return jsonify({
            'success': True,
            'date': target_date,
            'records': records,
            'total': len(records)
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# ===== 대시보드 요약 API =====
@assistant_bp.route('/assistant/api/dashboard', methods=['GET'])
def get_dashboard():
    """대시보드용 요약 데이터"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        today = date.today()
        week_end = today + timedelta(days=7)

        # 오늘 이벤트
        if USE_POSTGRES:
            cursor.execute('''
                SELECT * FROM events WHERE DATE(start_time) = %s ORDER BY start_time
            ''', (today,))
        else:
            cursor.execute('''
                SELECT * FROM events WHERE DATE(start_time) = ? ORDER BY start_time
            ''', (today.isoformat(),))
        today_events = [dict(row) for row in cursor.fetchall()]

        # 이번 주 이벤트
        if USE_POSTGRES:
            cursor.execute('''
                SELECT * FROM events
                WHERE DATE(start_time) > %s AND DATE(start_time) <= %s
                ORDER BY start_time
            ''', (today, week_end))
        else:
            cursor.execute('''
                SELECT * FROM events
                WHERE DATE(start_time) > ? AND DATE(start_time) <= ?
                ORDER BY start_time
            ''', (today.isoformat(), week_end.isoformat()))
        week_events = [dict(row) for row in cursor.fetchall()]

        # 미완료 태스크
        if USE_POSTGRES:
            cursor.execute('''
                SELECT * FROM tasks WHERE is_completed = FALSE
                ORDER BY due_date ASC NULLS LAST
            ''')
        else:
            cursor.execute('''
                SELECT * FROM tasks WHERE is_completed = 0
                ORDER BY due_date ASC
            ''')
        pending_tasks = [dict(row) for row in cursor.fetchall()]

        # Pending sync 카운트
        if USE_POSTGRES:
            cursor.execute('''
                SELECT COUNT(*) as count FROM events WHERE sync_status = %s
            ''', ('pending_to_mac',))
        else:
            cursor.execute('''
                SELECT COUNT(*) as count FROM events WHERE sync_status = ?
            ''', ('pending_to_mac',))
        pending_events_count = cursor.fetchone()['count']

        if USE_POSTGRES:
            cursor.execute('''
                SELECT COUNT(*) as count FROM tasks WHERE sync_status = %s
            ''', ('pending_to_mac',))
        else:
            cursor.execute('''
                SELECT COUNT(*) as count FROM tasks WHERE sync_status = ?
            ''', ('pending_to_mac',))
        pending_tasks_count = cursor.fetchone()['count']

        conn.close()

        # datetime 변환
        def convert_datetime(items):
            for item in items:
                for key in ['start_time', 'end_time', 'due_date', 'created_at', 'updated_at']:
                    if item.get(key) and not isinstance(item[key], str):
                        item[key] = item[key].isoformat() if hasattr(item[key], 'isoformat') else str(item[key])
            return items

        return jsonify({
            'success': True,
            'today': today.isoformat(),
            'today_events': convert_datetime(today_events),
            'week_events': convert_datetime(week_events),
            'pending_tasks': convert_datetime(pending_tasks),
            'pending_sync': {
                'events': pending_events_count,
                'tasks': pending_tasks_count,
                'total': pending_events_count + pending_tasks_count
            }
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# 모듈 로드 시 DB 초기화
try:
    init_assistant_db()
except Exception as e:
    print(f"[ASSISTANT-DB] 초기화 오류: {e}")
