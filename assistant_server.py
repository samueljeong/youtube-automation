"""
Personal AI Assistant - 메인 대시보드 서버
Mac(iCloud) 일정/미리알림과 웹 서버(DB) 데이터를 통합 관리하는 허브
"""
import os
import io
import csv
import json
import re
from datetime import datetime, date, timedelta
from flask import Blueprint, request, jsonify, render_template


def parse_korean_date(date_str):
    """
    한국어 날짜 형식을 ISO 형식으로 변환
    예: "2025. 12. 4. 오전 12:00" -> "2025-12-04"
        "2025. 12. 4." -> "2025-12-04"
        "2025-12-04" -> "2025-12-04" (이미 ISO 형식)
    """
    if not date_str:
        return None

    # 이미 ISO 형식이면 그대로 반환
    if re.match(r'^\d{4}-\d{2}-\d{2}', date_str):
        return date_str[:10]

    # 한국어 날짜 형식 파싱: "2025. 12. 4. 오전 12:00" 또는 "2025. 12. 4."
    match = re.match(r'(\d{4})\.\s*(\d{1,2})\.\s*(\d{1,2})\.?', date_str)
    if match:
        year, month, day = match.groups()
        return f"{year}-{int(month):02d}-{int(day):02d}"

    # 다른 형식 시도: "12/4/2025" 등
    try:
        for fmt in ['%Y-%m-%d', '%Y/%m/%d', '%m/%d/%Y', '%d/%m/%Y']:
            try:
                parsed = datetime.strptime(date_str.split()[0], fmt)
                return parsed.strftime('%Y-%m-%d')
            except ValueError:
                continue
    except Exception:
        pass

    return None

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
                group_name VARCHAR(100),
                source VARCHAR(50) DEFAULT 'web',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # 기존 테이블에 group_name 컬럼 추가
        try:
            cursor.execute('ALTER TABLE attendance ADD COLUMN IF NOT EXISTS group_name VARCHAR(100)')
        except Exception:
            pass
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
                group_name TEXT,
                source TEXT DEFAULT 'web',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # 기존 테이블에 group_name 컬럼 추가 (SQLite는 IF NOT EXISTS 미지원)
        try:
            cursor.execute('ALTER TABLE attendance ADD COLUMN group_name TEXT')
        except Exception:
            pass

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
            # 한국어 날짜 형식을 ISO 형식으로 변환
            due_date = parse_korean_date(task.get('due_date'))

            if USE_POSTGRES:
                cursor.execute('''
                    INSERT INTO tasks (title, due_date, priority, category, source, sync_status)
                    VALUES (%s, %s, %s, %s, %s, %s)
                ''', (
                    task.get('title'),
                    due_date,
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
                    due_date,
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


@assistant_bp.route('/assistant/api/attendance/upload', methods=['POST'])
def upload_attendance_file():
    """
    CSV/XLSX 파일 업로드로 출석 데이터 일괄 저장

    CSV 형식 예시:
    name,date,status,group_name
    홍길동,2024-12-01,present,청년부
    김철수,2024-12-01,absent,청년부

    또는 단순 형식 (날짜/그룹은 파라미터로):
    name,status
    홍길동,present
    김철수,absent
    """
    try:
        # 파일 체크
        if 'file' not in request.files:
            return jsonify({'success': False, 'error': '파일이 없습니다.'}), 400

        file = request.files['file']
        if file.filename == '':
            return jsonify({'success': False, 'error': '파일이 선택되지 않았습니다.'}), 400

        # 추가 파라미터 (CSV에 날짜/그룹이 없을 경우 사용)
        default_date = request.form.get('date', date.today().isoformat())
        default_group = request.form.get('group_name', '')

        filename = file.filename.lower()
        records = []

        if filename.endswith('.csv'):
            # CSV 파싱
            content = file.read().decode('utf-8-sig')  # BOM 처리
            reader = csv.DictReader(io.StringIO(content))

            for row in reader:
                name = row.get('name', row.get('이름', '')).strip()
                if not name:
                    continue

                records.append({
                    'name': name,
                    'date': row.get('date', row.get('날짜', default_date)),
                    'status': row.get('status', row.get('상태', 'present')),
                    'group_name': row.get('group_name', row.get('그룹', default_group))
                })

        elif filename.endswith('.xlsx') or filename.endswith('.xls'):
            # XLSX 파싱 (openpyxl 필요)
            try:
                from openpyxl import load_workbook

                wb = load_workbook(filename=io.BytesIO(file.read()))
                ws = wb.active

                headers = [cell.value for cell in ws[1]]
                header_map = {}
                for idx, h in enumerate(headers):
                    if h:
                        h_lower = str(h).lower().strip()
                        if h_lower in ['name', '이름']:
                            header_map['name'] = idx
                        elif h_lower in ['date', '날짜']:
                            header_map['date'] = idx
                        elif h_lower in ['status', '상태']:
                            header_map['status'] = idx
                        elif h_lower in ['group_name', '그룹', 'group']:
                            header_map['group_name'] = idx

                for row in ws.iter_rows(min_row=2, values_only=True):
                    if not row or not any(row):
                        continue

                    name = ''
                    if 'name' in header_map and row[header_map['name']]:
                        name = str(row[header_map['name']]).strip()

                    if not name:
                        continue

                    record_date = default_date
                    if 'date' in header_map and row[header_map['date']]:
                        d = row[header_map['date']]
                        if hasattr(d, 'isoformat'):
                            record_date = d.isoformat()[:10]
                        else:
                            record_date = str(d)[:10]

                    status = 'present'
                    if 'status' in header_map and row[header_map['status']]:
                        status = str(row[header_map['status']]).strip().lower()
                        # 한글 상태 변환
                        if status in ['출석', '참석', 'o', '○']:
                            status = 'present'
                        elif status in ['결석', '불참', 'x', '×']:
                            status = 'absent'

                    group_name = default_group
                    if 'group_name' in header_map and row[header_map['group_name']]:
                        group_name = str(row[header_map['group_name']]).strip()

                    records.append({
                        'name': name,
                        'date': record_date,
                        'status': status,
                        'group_name': group_name
                    })

            except ImportError:
                return jsonify({
                    'success': False,
                    'error': 'XLSX 파일 처리를 위한 openpyxl 라이브러리가 설치되지 않았습니다.'
                }), 500
        else:
            return jsonify({
                'success': False,
                'error': '지원하지 않는 파일 형식입니다. CSV 또는 XLSX 파일을 업로드해주세요.'
            }), 400

        if not records:
            return jsonify({'success': False, 'error': '유효한 출석 데이터가 없습니다.'}), 400

        # DB에 저장
        conn = get_db_connection()
        cursor = conn.cursor()

        added = 0
        for record in records:
            if USE_POSTGRES:
                cursor.execute('''
                    INSERT INTO attendance (name, date, status, group_name, source)
                    VALUES (%s, %s, %s, %s, %s)
                ''', (
                    record['name'],
                    record['date'],
                    record['status'],
                    record['group_name'],
                    'file_upload'
                ))
            else:
                cursor.execute('''
                    INSERT INTO attendance (name, date, status, group_name, source)
                    VALUES (?, ?, ?, ?, ?)
                ''', (
                    record['name'],
                    record['date'],
                    record['status'],
                    record['group_name'],
                    'file_upload'
                ))
            added += 1

        conn.commit()
        conn.close()

        return jsonify({
            'success': True,
            'message': f'출석 데이터 {added}건 업로드 완료',
            'records_added': added,
            'sample': records[:3] if len(records) > 3 else records
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


@assistant_bp.route('/assistant/api/attendance/under-attending', methods=['GET'])
def get_under_attending():
    """
    부진자(지속 결석자) 조회 API

    쿼리 파라미터:
    - weeks: 연속 결석 기준 주 수 (기본: 2)
    - group: 특정 그룹만 필터링 (선택)

    응답:
    [{ name, absent_weeks, last_attended_date, group_name }]
    """
    try:
        weeks = int(request.args.get('weeks', 2))
        group_filter = request.args.get('group', None)

        conn = get_db_connection()
        cursor = conn.cursor()

        # 최근 N주간의 예배 날짜 조회 (일요일 기준)
        today = date.today()

        # 최근 예배 날짜들 조회 (출석 기록이 있는 날짜들)
        if group_filter:
            if USE_POSTGRES:
                cursor.execute('''
                    SELECT DISTINCT date FROM attendance
                    WHERE group_name = %s
                    ORDER BY date DESC
                    LIMIT %s
                ''', (group_filter, weeks + 2))  # 여유분 포함
            else:
                cursor.execute('''
                    SELECT DISTINCT date FROM attendance
                    WHERE group_name = ?
                    ORDER BY date DESC
                    LIMIT ?
                ''', (group_filter, weeks + 2))
        else:
            if USE_POSTGRES:
                cursor.execute('''
                    SELECT DISTINCT date FROM attendance
                    ORDER BY date DESC
                    LIMIT %s
                ''', (weeks + 2,))
            else:
                cursor.execute('''
                    SELECT DISTINCT date FROM attendance
                    ORDER BY date DESC
                    LIMIT ?
                ''', (weeks + 2,))

        recent_dates = [row['date'] if isinstance(row['date'], str) else row['date'].isoformat()
                       for row in cursor.fetchall()]

        if len(recent_dates) < weeks:
            conn.close()
            return jsonify({
                'success': True,
                'message': f'충분한 출석 데이터가 없습니다. (최소 {weeks}주 필요, 현재 {len(recent_dates)}주)',
                'under_attending': [],
                'recent_dates': recent_dates
            })

        # 최근 N주 날짜
        check_dates = recent_dates[:weeks]

        # 모든 멤버 조회
        if group_filter:
            if USE_POSTGRES:
                cursor.execute('''
                    SELECT DISTINCT name, group_name FROM attendance
                    WHERE group_name = %s
                ''', (group_filter,))
            else:
                cursor.execute('''
                    SELECT DISTINCT name, group_name FROM attendance
                    WHERE group_name = ?
                ''', (group_filter,))
        else:
            cursor.execute('''
                SELECT DISTINCT name, group_name FROM attendance
            ''')

        members = [dict(row) for row in cursor.fetchall()]

        under_attending = []

        for member in members:
            name = member['name']
            group_name = member.get('group_name', '')

            # 이 멤버의 최근 N주 출석 현황 확인
            if USE_POSTGRES:
                cursor.execute('''
                    SELECT date, status FROM attendance
                    WHERE name = %s AND date = ANY(%s)
                    ORDER BY date DESC
                ''', (name, check_dates))
            else:
                placeholders = ','.join('?' * len(check_dates))
                cursor.execute(f'''
                    SELECT date, status FROM attendance
                    WHERE name = ? AND date IN ({placeholders})
                    ORDER BY date DESC
                ''', [name] + check_dates)

            attendance_records = {
                (row['date'] if isinstance(row['date'], str) else row['date'].isoformat()): row['status']
                for row in cursor.fetchall()
            }

            # 연속 결석 횟수 계산
            absent_count = 0
            for check_date in check_dates:
                status = attendance_records.get(check_date, 'absent')  # 기록 없으면 결석으로 간주
                if status == 'absent':
                    absent_count += 1
                else:
                    break  # 출석 기록이 있으면 연속 결석 종료

            # 기준 이상 연속 결석인 경우 부진자로 분류
            if absent_count >= weeks:
                # 마지막 출석 날짜 조회
                if USE_POSTGRES:
                    cursor.execute('''
                        SELECT date FROM attendance
                        WHERE name = %s AND status = 'present'
                        ORDER BY date DESC
                        LIMIT 1
                    ''', (name,))
                else:
                    cursor.execute('''
                        SELECT date FROM attendance
                        WHERE name = ? AND status = 'present'
                        ORDER BY date DESC
                        LIMIT 1
                    ''', (name,))

                last_row = cursor.fetchone()
                last_attended = None
                if last_row:
                    last_attended = last_row['date'] if isinstance(last_row['date'], str) else last_row['date'].isoformat()

                under_attending.append({
                    'name': name,
                    'absent_weeks': absent_count,
                    'last_attended_date': last_attended,
                    'group_name': group_name
                })

        conn.close()

        # 결석 주수로 정렬 (많은 순)
        under_attending.sort(key=lambda x: x['absent_weeks'], reverse=True)

        return jsonify({
            'success': True,
            'under_attending': under_attending,
            'total': len(under_attending),
            'weeks_checked': weeks,
            'check_dates': check_dates,
            'group_filter': group_filter
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


# ===== 심방 문자 프롬프트 (프로필별) =====
def _get_youth_pastor_prompt(today, style):
    """청년부 전도사 톤 프롬프트"""
    style_guide = {
        '따뜻한': '위로와 안부를 중심으로 따뜻하게 작성한다. 요즘 어떻게 지내는지 진심으로 궁금해하는 느낌.',
        '격려': '용기와 소망을 주는 방향으로 작성한다. "함께 걸어가고 싶다", "응원한다"는 뉘앙스를 담는다.',
        '공식적인': '짧고 담백하게 안내/확인 말투로 작성한다. 너무 감성적이지 않게.'
    }

    return f"""[역할]
너는 청년부 전도사를 돕는 심방/안부 문자 작성 도우미이다.
청년부에서 연락이 뜸한 청년들에게 보낼 따뜻하고 친근한 안부 문자를 작성한다.

[오늘 날짜]
{today.isoformat()}

[대상]
10대 후반 ~ 20대 청년

[문체 스타일: {style}]
{style_guide.get(style, style_guide['따뜻한'])}

[규칙]
1. 반드시 한국어 존댓말을 사용하되, 친근하고 가볍게 작성한다. 무겁지 않게.
2. 각 사람마다 2~3문장으로 간결하게 작성한다.
3. 이름은 "OO님" 형태로 자연스럽게 포함한다.
4. 정죄, 비난, 눈치 주는 표현은 절대 사용하지 않는다.
5. "왜 안 나왔냐"보다는 "요즘 잘 지내는지 궁금해서 연락 드렸다"는 방향으로.
6. "함께 예배 드리고 싶다", "함께 있어주고 싶다"는 뉘앙스를 담는다.
7. 결석 주수를 직접적으로 언급하지 않는다 (예: "3주 동안 안 나오셨네요" X)
8. 이모티콘은 1개까지만 허용한다 (예: 😊, 🙌). 없어도 된다.
9. 혼자 감당하기 버거운 일이 있으면 알려달라는 제안을 자연스럽게 넣어도 좋다.

[출력 형식]
반드시 다음 JSON 형식으로만 출력한다:
{{"messages": [
  {{"name": "이름", "message": "문자 내용"}}
]}}

JSON 외의 다른 텍스트(설명, 주석 등)는 절대 출력하지 마라.

[예시 - 참고용]
"OO님, 요즘 잘 지내고 계신가요? 최근 예배에서 얼굴을 잘 뵙지 못해서 문득 생각이 났어요. 혹시 혼자 감당하기 버거운 일들이 있다면 언제든 편하게 알려 주세요. 청년부에서 함께 예배드리고, 같이 이야기 나눌 수 있으면 좋겠습니다. 😊"
"""


def _get_adult_pastor_prompt(today, style):
    """장년 목사 톤 프롬프트"""
    style_guide = {
        '따뜻한': '안부와 위로를 중심으로 작성한다. 요즘 어떻게 지내시는지, 건강은 어떠신지 묻는 따뜻한 마음.',
        '격려': '신앙, 기도, 소망에 대한 부드러운 격려를 한 문장 추가한다.',
        '공식적인': '안내성, 사실 전달 위주로 짧게 작성한다. 담백하고 공손하게.'
    }

    return f"""[역할]
너는 담임목사(또는 담당 목사)를 돕는 장년 성도 심방 문자 작성 도우미이다.
예배에 오랫동안 참석하지 못한 장년 성도님들에게 보낼 따뜻하고 공손한 안부 문자를 작성한다.

[오늘 날짜]
{today.isoformat()}

[대상]
장년 성도 (40~70대, 집사님/권사님/장로님 포함)

[문체 스타일: {style}]
{style_guide.get(style, style_guide['따뜻한'])}

[규칙]
1. 반드시 한국어 존댓말을 사용한다. 공손하고 목회자의 따뜻한 배려가 느껴지는 톤.
2. 각 사람마다 2~3문장으로 간결하게 작성한다.
3. 이름 앞에 적절한 호칭을 붙인다:
   - group_name이 "청년부"면 "OO님"
   - 그 외(장년부 등)면 "OO 집사님", "OO 성도님" 등 자연스럽게 선택
4. **절대로 "어르신"이라는 단어를 사용하지 마라.** 이 단어는 금지어이다.
5. 정죄, 비난, 압박 표현은 절대 사용하지 않는다.
6. "오랫동안 안 나오셨다"는 표현 대신 "최근에 예배에서 자주 뵙지 못했다" 정도로 부드럽게.
7. 결석 주수를 직접적으로 언급하지 않는다.
8. 건강과 안부를 묻고, 필요하면 "기도 제목 나누어 달라"는 제안을 포함한다.
9. 예배 자리를 부담 없이 다시 초대하는 뉘앙스를 담는다.
10. 이모티콘은 0~1개, 너무 가볍지 않게. 없어도 된다.

[출력 형식]
반드시 다음 JSON 형식으로만 출력한다:
{{"messages": [
  {{"name": "이름", "message": "문자 내용"}}
]}}

JSON 외의 다른 텍스트(설명, 주석 등)는 절대 출력하지 마라.

[예시 - 참고용]
"OO 집사님, 잘 지내고 계신지요? 최근 예배 자리에서 자주 뵙지 못해 안부가 궁금하여 연락을 드렸습니다. 혹시 기도 부탁하실 일이나 어려운 상황이 있으시면 언제든 말씀해 주시면 함께 기도하겠습니다."
"""


@assistant_bp.route('/assistant/api/attendance/messages', methods=['POST'])
def generate_care_messages():
    """
    부진자별 심방/안부 문자 GPT 생성 API

    Body:
    {
        "people": [{ "name": "홍길동", "absent_weeks": 3, "last_attended_date": "2024-11-10", "group_name": "청년부" }],
        "style": "따뜻한" | "격려" | "공식적인" (선택, 기본: 따뜻한),
        "profile": "youth" | "adult" (선택, 기본: adult)
    }

    응답:
    { "messages": [{ "name": "홍길동", "message": "..." }] }
    """
    try:
        data = request.get_json()
        people = data.get('people', [])
        style = data.get('style', '따뜻한')
        profile = data.get('profile', 'adult')  # youth 또는 adult

        if not people:
            return jsonify({'success': False, 'error': '대상자 목록이 비어있습니다.'}), 400

        client = get_openai_client()
        if not client:
            return jsonify({'success': False, 'error': 'OpenAI API 키가 설정되지 않았습니다.'}), 500

        today = date.today()

        # 프로필에 따른 system prompt 선택
        if profile == 'youth':
            system_prompt = _get_youth_pastor_prompt(today, style)
        else:
            system_prompt = _get_adult_pastor_prompt(today, style)

        # 대상자 정보 정리
        people_info = "\n".join([
            f"- {p['name']} ({p.get('group_name', '그룹 미지정')}): {p['absent_weeks']}주 연속 결석, 마지막 출석: {p.get('last_attended_date', '기록 없음')}"
            for p in people
        ])

        user_prompt = f"""다음 분들에게 보낼 안부 문자를 작성해주세요:

{people_info}"""

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.7,
            response_format={"type": "json_object"}
        )

        result = json.loads(response.choices[0].message.content)

        # 결과 형식 정규화
        messages = result if isinstance(result, list) else result.get('messages', result.get('data', []))

        return jsonify({
            'success': True,
            'messages': messages,
            'total': len(messages),
            'style': style,
            'profile': profile
        })
    except json.JSONDecodeError as e:
        return jsonify({'success': False, 'error': f'JSON 파싱 오류: {str(e)}'}), 500
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


@assistant_bp.route('/assistant/api/attendance/groups', methods=['GET'])
def get_attendance_groups():
    """출석부에 등록된 그룹 목록 조회"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute('''
            SELECT DISTINCT group_name FROM attendance
            WHERE group_name IS NOT NULL AND group_name != ''
            ORDER BY group_name
        ''')

        groups = [row['group_name'] for row in cursor.fetchall()]
        conn.close()

        return jsonify({
            'success': True,
            'groups': groups
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
