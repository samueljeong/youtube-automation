from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3
import os
import re
import json
from functools import wraps
from openai import OpenAI
from urllib.parse import urlparse

app = Flask(__name__)
app.secret_key = os.urandom(24)  # Secret key for session management

# OpenAI client setup
def get_openai_client():
    key = (os.getenv("OPENAI_API_KEY") or "").strip()
    if not key:
        raise RuntimeError("OPENAI_API_KEY가 비어 있습니다.")
    return OpenAI(api_key=key)

try:
    openai_client = get_openai_client()
except RuntimeError:
    openai_client = None

# Database setup - support both PostgreSQL and SQLite
DATABASE_URL = os.getenv('DATABASE_URL')
USE_POSTGRES = DATABASE_URL is not None

if USE_POSTGRES:
    # PostgreSQL 사용
    import psycopg2
    from psycopg2.extras import RealDictCursor

    # Render의 postgres:// URL을 postgresql://로 변경
    if DATABASE_URL.startswith('postgres://'):
        DATABASE_URL = DATABASE_URL.replace('postgres://', 'postgresql://', 1)

    class PostgreSQLConnection:
        """PostgreSQL connection wrapper to match SQLite interface"""
        def __init__(self, conn):
            self.conn = conn
            self._cursor = None

        def execute(self, query, params=()):
            """Execute a query (converts ? to %s for PostgreSQL)"""
            self._cursor = self.conn.cursor()
            pg_query = query.replace('?', '%s')
            self._cursor.execute(pg_query, params)
            return self._cursor

        def commit(self):
            """Commit the transaction"""
            self.conn.commit()

        def close(self):
            """Close the connection"""
            if self._cursor:
                self._cursor.close()
            self.conn.close()

    def get_db_connection():
        """Create a PostgreSQL database connection"""
        conn = psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)
        return PostgreSQLConnection(conn)

else:
    # SQLite 사용 (로컬 개발용)
    DB_PATH = os.path.join(os.path.dirname(__file__), 'users.db')

    def get_db_connection():
        """Create a SQLite database connection"""
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        return conn

def login_required(f):
    """Decorator to require login for certain routes"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    """Decorator to require admin privileges"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))

        # Check if user is admin
        conn = get_db_connection()
        user = conn.execute('SELECT is_admin FROM users WHERE id = ?', (session['user_id'],)).fetchone()
        conn.close()

        if not user or not user['is_admin']:
            flash('관리자 권한이 필요합니다.', 'error')
            return redirect(url_for('index'))

        return f(*args, **kwargs)
    return decorated_function

# ===== Sermon Helper Functions =====
def format_json_result(json_data, indent=0):
    """JSON 데이터를 보기 좋은 텍스트 형식으로 변환 (재귀적 처리)"""
    result = []
    indent_str = "  " * indent

    # JSON의 각 키-값 쌍을 보기 좋게 포맷팅
    for key, value in json_data.items():
        # 키를 한국어로 변환 (필요시)
        key_display = key.replace('_', ' ').title()

        # 값이 리스트인 경우
        if isinstance(value, list):
            result.append(f"{indent_str}【 {key_display} 】")
            for item in value:
                if isinstance(item, dict):
                    # 리스트 안의 딕셔너리 재귀 처리
                    for sub_line in format_json_result(item, indent + 1).split('\n'):
                        if sub_line.strip():
                            result.append(f"  {indent_str}{sub_line}")
                else:
                    result.append(f"{indent_str}  - {item}")
            if indent == 0:
                result.append("")
        # 값이 딕셔너리인 경우 (재귀 처리)
        elif isinstance(value, dict):
            result.append(f"{indent_str}【 {key_display} 】")
            # 중첩 딕셔너리를 재귀적으로 처리
            for sub_key, sub_value in value.items():
                sub_key_display = sub_key.replace('_', ' ')
                if isinstance(sub_value, dict):
                    # 더 깊은 중첩 딕셔너리
                    result.append(f"{indent_str}  {sub_key_display}:")
                    for nested_line in format_json_result(sub_value, indent + 2).split('\n'):
                        if nested_line.strip() and not nested_line.strip().startswith('【'):
                            result.append(f"  {nested_line}")
                        elif nested_line.strip().startswith('【'):
                            # 섹션 헤더는 건너뛰기
                            pass
                elif isinstance(sub_value, list):
                    result.append(f"{indent_str}  {sub_key_display}:")
                    for item in sub_value:
                        result.append(f"{indent_str}    - {item}")
                else:
                    result.append(f"{indent_str}  {sub_key_display}: {sub_value}")
            if indent == 0:
                result.append("")
        # 값이 문자열 또는 기타인 경우
        else:
            result.append(f"{indent_str}【 {key_display} 】")
            result.append(f"{indent_str}{str(value)}")
            if indent == 0:
                result.append("")

    return "\n".join(result).strip()

def remove_markdown(text):
    """마크다운 기호 제거 (#, *, -, **, ###, 등)"""
    # 헤더 제거 (##, ###, #### 등)
    text = re.sub(r'^#+\s+', '', text, flags=re.MULTILINE)

    # 볼드 제거 (**, __)
    text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)
    text = re.sub(r'__(.+?)__', r'\1', text)

    # 이탤릭 제거 (*, _)
    text = re.sub(r'\*(.+?)\*', r'\1', text)
    text = re.sub(r'_(.+?)_', r'\1', text)

    # 리스트 마커 제거 (-, *, +)
    text = re.sub(r'^\s*[-*+]\s+', '', text, flags=re.MULTILINE)

    # 코드 블록 제거 (```)
    text = re.sub(r'```[\s\S]*?```', '', text)

    # 인라인 코드 제거 (`)
    text = re.sub(r'`(.+?)`', r'\1', text)

    return text.strip()

def get_system_prompt_for_step(step_name):
    """
    단계별로 최적화된 system prompt 반환
    mini는 개요와 자료만 생성, 설교문 작성 금지
    JSON 형식으로 응답
    """
    step_lower = step_name.lower()

    # 제목 추천 단계
    if '제목' in step_name:
        return """당신은 gpt-4o-mini로서 설교 '제목 후보'만 제안하는 역할입니다.

CRITICAL RULES:
1. 정확히 3개의 제목만 제시하세요
2. 각 제목은 한 줄로 작성하세요
3. 번호, 기호, 마크다운 사용 금지
4. 제목만 작성하고 설명 추가 금지

출력 형식 예시:
하나님의 약속을 믿는 믿음
약속의 땅을 향한 여정
아브라함의 신앙 결단"""

    # 본문 분석 / 연구 단계
    elif '분석' in step_name or '연구' in step_name or '배경' in step_name:
        return f"""당신은 gpt-4o-mini로서 설교 '초안 자료'만 준비하는 역할입니다.

현재 단계: {step_name}

CRITICAL RULES:
1. 객관적인 성경 연구 자료만 제공하세요
2. 반드시 JSON 형식으로 응답하세요
3. 설교문 형식으로 작성하지 마세요
4. 감동적인 표현이나 적용 내용 금지
5. 순수한 연구 자료만 제공

응답은 반드시 다음 JSON 형식을 따르세요:
{{
  "background": "시대적/지리적/문화적 배경",
  "context_before": "본문 이전 맥락",
  "context_after": "본문 이후 맥락",
  "characters": "등장인물과 역할",
  "key_words": "핵심 단어 분석",
  "structure": "본문 구조 분석",
  "cross_references": "관련 성경구절",
  "theological_themes": "신학적 주제",
  "summary": "본문 요약"
}}

JSON만 출력하고 추가 설명은 하지 마세요."""

    # 개요 / 구조 단계
    elif '개요' in step_name or '구조' in step_name or 'outline' in step_lower:
        return f"""당신은 gpt-4o-mini로서 설교 '개요'만 작성하는 역할입니다.

현재 단계: {step_name}

CRITICAL RULES:
1. 설교의 뼈대만 제시하세요
2. 반드시 JSON 형식으로 응답하세요
3. 문단 형태의 설교문은 절대 작성하지 마세요
4. 구조와 주제 문장만 제시하세요

응답은 반드시 다음 JSON 형식을 따르세요:
{{
  "big_idea": "한 문장으로 핵심 메시지",
  "intro_points": ["서론 포인트 1", "서론 포인트 2"],
  "point1": {{
    "title": "1대지 주제 문장",
    "sub_points": ["소대지 1", "소대지 2"]
  }},
  "point2": {{
    "title": "2대지 주제 문장",
    "sub_points": ["소대지 1", "소대지 2"]
  }},
  "point3": {{
    "title": "3대지 주제 문장",
    "sub_points": ["소대지 1", "소대지 2"]
  }},
  "conclusion_direction": "결론 방향 키워드"
}}

JSON만 출력하고 추가 설명은 하지 마세요."""

    # 설교문 작성이 의심되는 단계 (경고)
    elif any(word in step_name for word in ['서론', '본론', '결론', '적용', '설교문']):
        return f"""당신은 gpt-4o-mini로서 설교 '자료'만 준비하는 역할입니다.

⚠️ 중요: 완성된 설교 문단은 작성하지 마세요!

현재 단계: {step_name}

CRITICAL RULES:
1. 이 단계는 GPT-5.1에서 최종 작성될 부분입니다
2. 당신은 자료와 포인트만 제공하세요
3. 반드시 JSON 형식으로 응답하세요
4. 자연스러운 설교 문장 작성 금지
5. 감동적인 표현 금지

응답은 반드시 다음 JSON 형식을 따르세요:
{{
  "core_message": "핵심 메시지 (한 문장)",
  "key_points": ["포인트 1", "포인트 2", "포인트 3"],
  "scripture_references": ["구절 1", "구절 2"],
  "emphasis": ["강조할 내용 1", "강조할 내용 2"]
}}

JSON만 출력하고 추가 설명은 하지 마세요."""

    # 기타 단계
    else:
        return f"""당신은 gpt-4o-mini로서 설교 '초안 자료'만 준비하는 역할입니다.

현재 단계: {step_name}

CRITICAL RULES:
1. 자료와 정보만 제공하세요
2. 완성된 설교문은 작성하지 마세요
3. 반드시 JSON 형식으로 응답하세요
4. 객관적 내용만 제시하세요

응답은 반드시 다음 JSON 형식을 따르세요:
{{
  "content": "자료 내용",
  "points": ["포인트 1", "포인트 2"],
  "references": ["참고 사항"]
}}

JSON만 출력하고 추가 설명은 하지 마세요."""

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    """Handle user signup"""
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        name = request.form.get('name')
        phone = request.form.get('phone')
        birth_date = request.form.get('birth_date')

        # Validation
        if not email or not password or not name:
            flash('이메일, 비밀번호, 이름은 필수 항목입니다.', 'error')
            return render_template('signup.html')

        # Check password length
        if len(password) < 6:
            flash('비밀번호는 최소 6자 이상이어야 합니다.', 'error')
            return render_template('signup.html')

        conn = get_db_connection()

        # Check if email already exists
        existing_user = conn.execute('SELECT * FROM users WHERE email = ?', (email,)).fetchone()
        if existing_user:
            flash('이미 존재하는 이메일입니다.', 'error')
            conn.close()
            return render_template('signup.html')

        # Hash password and create user
        password_hash = generate_password_hash(password)

        try:
            conn.execute(
                'INSERT INTO users (email, password_hash, name, phone, birth_date) VALUES (?, ?, ?, ?, ?)',
                (email, password_hash, name, phone if phone else None, birth_date if birth_date else None)
            )
            conn.commit()

            # Get the newly created user
            user = conn.execute('SELECT * FROM users WHERE email = ?', (email,)).fetchone()
            conn.close()

            # Auto login after signup
            session['user_id'] = user['id']
            session['user_email'] = user['email']
            session['user_name'] = user['name']
            session['is_admin'] = user['is_admin']

            flash('회원가입이 완료되었습니다!', 'success')
            return redirect(url_for('index'))

        except Exception as e:
            conn.close()
            flash(f'회원가입 중 오류가 발생했습니다: {str(e)}', 'error')
            return render_template('signup.html')

    return render_template('signup.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    """Handle user login"""
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')

        if not email or not password:
            flash('이메일과 비밀번호를 입력해주세요.', 'error')
            return render_template('login.html')

        conn = get_db_connection()
        user = conn.execute('SELECT * FROM users WHERE email = ?', (email,)).fetchone()
        conn.close()

        if user and check_password_hash(user['password_hash'], password):
            # Login successful
            session['user_id'] = user['id']
            session['user_email'] = user['email']
            session['user_name'] = user['name']
            session['is_admin'] = user['is_admin']

            flash(f'{user["name"]}님, 환영합니다!', 'success')
            return redirect(url_for('index'))
        else:
            flash('이메일 또는 비밀번호가 올바르지 않습니다.', 'error')
            return render_template('login.html')

    return render_template('login.html')

@app.route('/logout')
def logout():
    """Handle user logout"""
    session.clear()
    flash('로그아웃되었습니다.', 'success')
    return redirect(url_for('index'))

@app.route('/profile')
@login_required
def profile():
    """User profile page"""
    conn = get_db_connection()
    user = conn.execute('SELECT * FROM users WHERE id = ?', (session['user_id'],)).fetchone()
    conn.close()
    return render_template('profile.html', user=user)

# ===== Admin Routes =====
@app.route('/admin')
@admin_required
def admin_dashboard():
    """Admin dashboard - 관리자 전용"""
    conn = get_db_connection()
    users = conn.execute('SELECT id, email, name, phone, birth_date, is_admin, created_at FROM users ORDER BY created_at DESC').fetchall()
    conn.close()
    return render_template('admin.html', users=users)

@app.route('/admin/toggle-admin/<int:user_id>', methods=['POST'])
@admin_required
def toggle_admin(user_id):
    """Toggle admin status for a user"""
    # Prevent removing your own admin status
    if user_id == session['user_id']:
        flash('자신의 관리자 권한은 변경할 수 없습니다.', 'error')
        return redirect(url_for('admin_dashboard'))

    conn = get_db_connection()
    user = conn.execute('SELECT is_admin FROM users WHERE id = ?', (user_id,)).fetchone()

    if user:
        new_status = 0 if user['is_admin'] else 1
        conn.execute('UPDATE users SET is_admin = ? WHERE id = ?', (new_status, user_id))
        conn.commit()
        action = '부여' if new_status else '제거'
        flash(f'관리자 권한이 {action}되었습니다.', 'success')
    else:
        flash('사용자를 찾을 수 없습니다.', 'error')

    conn.close()
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/delete-user/<int:user_id>', methods=['POST'])
@admin_required
def delete_user(user_id):
    """Delete a user (admin only)"""
    # Prevent deleting yourself
    if user_id == session['user_id']:
        flash('자신의 계정은 삭제할 수 없습니다.', 'error')
        return redirect(url_for('admin_dashboard'))

    conn = get_db_connection()
    conn.execute('DELETE FROM users WHERE id = ?', (user_id,))
    conn.commit()
    conn.close()

    flash('사용자가 삭제되었습니다.', 'success')
    return redirect(url_for('admin_dashboard'))

@app.route('/')
@login_required
def index():
    """Home page - 비공개"""
    return render_template('index.html')

@app.route('/bible')
@login_required
def bible():
    """Bible page - 비공개"""
    return render_template('bible.html')

@app.route('/message')
@login_required
def message():
    """Message page - 비공개"""
    return render_template('message.html')

# ===== Sermon Routes =====
@app.route('/sermon')
def sermon():
    """Sermon page"""
    return render_template('sermon.html')

# ===== Drama Routes =====
@app.route('/drama')
@login_required
def drama():
    """Drama page - 비공개"""
    return render_template('drama.html')

@app.route('/health')
def health():
    """Health check endpoint"""
    return jsonify({"ok": True})

@app.route('/setup-admin', methods=['GET', 'POST'])
def setup_admin():
    """
    일회성 관리자 설정 엔드포인트
    사용법: /setup-admin?email=이메일&secret=비밀키
    """
    # 환경 변수에서 비밀 키 가져오기 (없으면 기본값)
    admin_secret = os.getenv('ADMIN_SETUP_SECRET', 'setup-admin-2024')

    # 쿼리 파라미터에서 값 가져오기
    email = request.args.get('email') or request.form.get('email')
    secret = request.args.get('secret') or request.form.get('secret')

    if not email or not secret:
        return jsonify({
            "ok": False,
            "error": "email과 secret 파라미터가 필요합니다.",
            "usage": "/setup-admin?email=이메일&secret=비밀키"
        }), 400

    # 비밀 키 확인
    if secret != admin_secret:
        return jsonify({
            "ok": False,
            "error": "잘못된 비밀 키입니다."
        }), 403

    # 사용자 찾기 및 관리자 권한 부여
    conn = get_db_connection()
    user = conn.execute('SELECT id, name, email, is_admin FROM users WHERE email = ?', (email,)).fetchone()

    if not user:
        conn.close()
        return jsonify({
            "ok": False,
            "error": f"이메일 '{email}'을 가진 사용자를 찾을 수 없습니다."
        }), 404

    if user['is_admin']:
        conn.close()
        return jsonify({
            "ok": True,
            "message": f"사용자 '{user['name']}' ({user['email']})는 이미 관리자입니다."
        })

    # 관리자 권한 부여
    conn.execute('UPDATE users SET is_admin = 1 WHERE id = ?', (user['id'],))
    conn.commit()
    conn.close()

    return jsonify({
        "ok": True,
        "message": f"✅ 사용자 '{user['name']}' ({user['email']})가 관리자로 승격되었습니다!",
        "user_id": user['id'],
        "email": user['email'],
        "name": user['name']
    })

@app.route('/api/sermon/process', methods=['POST'])
def api_process_step():
    """단일 처리 단계 실행 (gpt-4o-mini 사용)"""
    try:
        if not openai_client:
            return jsonify({"ok": False, "error": "OpenAI API key not configured"}), 500

        data = request.get_json()
        if not data:
            return jsonify({"ok": False, "error": "No data received"}), 400

        category = data.get("category", "")
        step_id = data.get("stepId", "")
        step_name = data.get("stepName", "")
        reference = data.get("reference", "")
        title = data.get("title", "")
        text = data.get("text", "")
        guide = data.get("guide", "")
        master_guide = data.get("masterGuide", "")
        previous_results = data.get("previousResults", {})

        print(f"[PROCESS] {category} - {step_name}")

        # 시스템 메시지 구성 (단계별 최적화)
        system_content = get_system_prompt_for_step(step_name)

        # 총괄 지침이 있으면 추가
        if master_guide:
            system_content += f"\n\n【 카테고리 총괄 지침 】\n{master_guide}\n\n"
            system_content += f"【 현재 단계 역할 】\n{step_name}\n\n"
            system_content += "위 총괄 지침을 참고하여, 현재 단계의 역할과 비중에 맞게 '자료만' 작성하세요."

        # 사용자 메시지 구성
        user_content = f"[성경구절]\n{reference}\n\n"

        # 제목이 있으면 추가 (제목 추천 단계가 아닐 때만)
        if title and '제목' not in step_name:
            user_content += f"[설교 제목]\n{title}\n\n"
            user_content += "위 제목을 염두에 두고 모든 내용을 작성해주세요.\n\n"

        if text:
            user_content += f"[성경 본문]\n{text}\n\n"

        # 이전 단계 결과 추가
        if previous_results:
            user_content += "[이전 단계 결과 (참고용)]\n"
            for prev_id, prev_data in previous_results.items():
                user_content += f"\n### {prev_data['name']}\n{prev_data['result']}\n"
            user_content += "\n"

        # 현재 단계 지침 추가
        if guide:
            user_content += f"[{step_name} 단계 세부 지침]\n{guide}\n\n"

        # 제목 추천 단계 특별 처리
        if '제목' in step_name:
            user_content += f"위 성경 본문({reference})에 적합한 설교 제목을 정확히 3개만 제안해주세요.\n"
            user_content += "각 제목은 한 줄로, 번호나 기호 없이 작성하세요."
        else:
            user_content += f"위 내용을 바탕으로 '{step_name}' 단계를 작성해주세요.\n"
            user_content += "⚠️ 중요: 완성된 설교 문단이 아닌, 자료와 구조만 제공하세요."

        if title and '제목' not in step_name:
            user_content += f"\n제목 '{title}'을 고려하여 작성하세요."

        # GPT 호출 (gpt-4o-mini)
        completion = openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": system_content
                },
                {
                    "role": "user",
                    "content": user_content
                }
            ],
            temperature=0.7,
            response_format={"type": "json_object"} if '제목' not in step_name else None,
        )

        result = completion.choices[0].message.content.strip()

        # 제목 추천 단계는 JSON 파싱하지 않고 그대로 반환
        if '제목' in step_name:
            result = remove_markdown(result)
            return jsonify({"ok": True, "result": result})

        # JSON 파싱 시도
        try:
            # JSON 코드 블록 제거 (```json ... ``` 형태)
            cleaned_result = result
            if cleaned_result.startswith('```'):
                # ```json 또는 ``` 로 시작하는 경우
                lines = cleaned_result.split('\n')
                # 첫 줄과 마지막 줄 제거
                if lines[0].startswith('```'):
                    lines = lines[1:]
                if lines and lines[-1].startswith('```'):
                    lines = lines[:-1]
                cleaned_result = '\n'.join(lines).strip()

            # JSON 파싱
            json_data = json.loads(cleaned_result)

            # JSON을 보기 좋은 텍스트로 변환
            formatted_result = format_json_result(json_data)

            print(f"[PROCESS][SUCCESS] JSON 파싱 성공")
            return jsonify({"ok": True, "result": formatted_result})

        except json.JSONDecodeError as je:
            # JSON 파싱 실패 시 원본 텍스트를 마크다운 제거하여 반환
            print(f"[PROCESS][WARNING] JSON 파싱 실패: {str(je)}")
            print(f"[PROCESS][WARNING] 원본 결과: {result[:200]}...")
            result = remove_markdown(result)
            return jsonify({"ok": True, "result": result, "warning": "JSON 형식이 아닌 결과가 반환되었습니다."})

    except Exception as e:
        print(f"[PROCESS][ERROR] {str(e)}")
        return jsonify({"ok": False, "error": str(e)}), 200

@app.route('/api/sermon/gpt-pro', methods=['POST'])
def api_gpt_pro():
    """GPT-5.1 완성본 작성"""
    try:
        if not openai_client:
            return jsonify({"ok": False, "error": "OpenAI API key not configured"}), 500

        data = request.get_json()
        if not data:
            return jsonify({"ok": False, "error": "No data received"}), 400

        reference = data.get("reference", "")
        title = data.get("title", "")
        series_name = data.get("seriesName", "")
        style_name = data.get("styleName", "")
        category = data.get("category", "")
        draft_content = data.get("draftContent", "")
        style_description = data.get("styleDescription", "")

        print(f"[GPT-PRO] 처리 시작 - 스타일: {style_name}")

        # GPT-5.1 시스템 프롬프트 (스타일 동적 적용)
        system_content = (
            "당신은 GPT-5.1 기반의 한국어 설교 전문가입니다."
            " 자료는 참고용으로만 활용하고 문장은 처음부터 새로 구성하며,"
            " 묵직하고 명료한 어조로 신학적 통찰과 실제적 적용을 균형 있게 제시하세요."
            " 마크다운 기호 대신 순수 텍스트만 사용합니다."
        )

        # 사용자 메시지 구성
        meta_lines = []
        if category:
            meta_lines.append(f"- 카테고리: {category}")
        if style_name:
            meta_lines.append(f"- 설교 스타일: {style_name}")
        if style_description:
            meta_lines.append(f"- 스타일 설명: {style_description}")
        if reference:
            meta_lines.append(f"- 본문 성경구절: {reference}")
        if title:
            meta_lines.append(f"- 설교 제목: {title}")
        if series_name:
            meta_lines.append(f"- 시리즈명: {series_name}")

        meta_section = "\n".join(meta_lines)

        user_content = (
            "아래는 gpt-4o-mini가 정리한 연구·개요 자료입니다."
            " 참고만 하고, 문장은 처음부터 새로 작성해주세요."
        )
        if meta_section:
            user_content += f"\n\n[기본 정보]\n{meta_section}"
        user_content += "\n\n[설교 초안 자료]\n"
        user_content += draft_content

        # 설교 스타일별 요청 사항 결정
        user_content += "\n\n【요청 사항】\n"

        # 하몽서클 관련 스타일인지 확인
        is_harmonic_circle = any(keyword in style_name.lower() for keyword in ['하몽', 'harmonic'])

        # 3대지 관련 스타일인지 확인
        is_three_point = any(keyword in style_name.lower() for keyword in ['3대지', '주제', 'topical', '강해'])

        if is_harmonic_circle:
            # 하몽서클 스타일
            user_content += (
                "1. 하몽서클 5단계(Setup, Conflict, Turning Point, Realization, Call to Action)를 차례대로 구분해 주세요.\n"
                "   - 각 단계 제목은 영어-한국어 병기 형태로 표기합니다 (예: Setup — 서론).\n"
                "2. 각 단계마다 관련 배경 설명과 함께 적용을 제공하고, 반드시 보충 성경구절 2개를 인용구 형태로 제시하세요.\n"
                "3. 역사적 배경, 스토리텔링, 오늘의 적용을 골고루 담아 묵직하고 명확한 메시지를 만드세요.\n"
                "4. 결단(Call to Action) 단계에서는 이번 주 실천과 공동체 기도제목을 명확히 정리하세요.\n"
                "5. 마지막에 짧은 마무리 기도문과 축복 선언을 덧붙이세요.\n"
                "6. 마크다운, 불릿 기호 대신 순수 텍스트 단락과 번호를 사용하고, 중복되는 문장은 피하세요."
            )
        elif is_three_point:
            # 3대지 설교 스타일
            user_content += (
                "1. 3대지 구조로 설교문을 작성하세요:\n"
                "   - 서론: 본문 배경과 주요 메시지 소개\n"
                "   - 1대지, 2대지, 3대지: 각 대지마다 선포형 제목과 2개의 소대지 포함\n"
                "   - 결론: 실천과 적용\n"
                "2. 각 대지마다:\n"
                "   - 명확한 주제 문장으로 시작\n"
                "   - 소대지 2개를 포함하여 주제를 전개\n"
                "   - 관련 성경구절 2개를 인용구 형태로 제시\n"
                "   - 역사적 배경과 오늘의 적용을 연결\n"
                "3. 결론에서는 이번 주 실천 사항과 기도 제목을 제시하세요.\n"
                "4. 마크다운, 불릿 기호 대신 순수 텍스트 단락과 번호를 사용하고, 중복되는 문장은 피하세요."
            )
        else:
            # 기본 설교 스타일
            user_content += (
                "1. 제공된 설교 스타일에 맞춰 설교문을 작성하세요.\n"
                "2. 서론, 본론, 결론 구조를 명확히 하세요.\n"
                "3. 본론에서 핵심 메시지를 전개하고, 관련 성경구절을 인용하세요.\n"
                "4. 역사적 배경, 신학적 통찰, 실제 적용을 균형 있게 제시하세요.\n"
                "5. 결론에서는 실천 사항과 기도 제목을 제시하세요.\n"
                "6. 마크다운, 불릿 기호 대신 순수 텍스트 단락과 번호를 사용하고, 중복되는 문장은 피하세요."
            )

        # 최신 Responses API (gpt-5.1) 호출
        completion = openai_client.responses.create(
            model="gpt-5.1",
            input=[
                {
                    "role": "system",
                    "content": [
                        {
                            "type": "input_text",
                            "text": system_content
                        }
                    ]
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "input_text",
                            "text": user_content
                        }
                    ]
                }
            ],
            temperature=0.8,
            max_output_tokens=8000  # 더 긴 설교문을 위해 토큰 증가
        )

        if getattr(completion, "output_text", None):
            result = completion.output_text.strip()
        else:
            text_chunks = []
            for item in getattr(completion, "output", []) or []:
                for content in getattr(item, "content", []) or []:
                    if getattr(content, "type", "") == "text":
                        text_chunks.append(getattr(content, "text", ""))
            result = "\n".join(text_chunks).strip()

        if not result:
            raise RuntimeError("GPT-5.1 API로부터 결과를 받지 못했습니다.")

        # 결과 앞에 본문과 제목 추가 (제목이 있을 때만)
        final_result = ""

        # 제목 추가 (사용자가 선택한 제목이 있을 때만)
        if title and title.strip():
            final_result += f"설교 제목: {title}\n"

        # 본문 추가
        if reference:
            final_result += f"본문: {reference}\n"

        # 제목이나 본문이 있으면 구분선 추가
        if title or reference:
            final_result += "\n" + "="*50 + "\n\n"

        final_result += result

        print(f"[GPT-PRO] 완료")

        return jsonify({"ok": True, "result": final_result})

    except Exception as e:
        print(f"[GPT-PRO][ERROR] {str(e)}")
        return jsonify({"ok": False, "error": str(e)}), 200

# ===== Drama API Routes =====
@app.route('/api/drama/synopsis', methods=['POST'])
@login_required
def api_drama_synopsis():
    """Generate drama synopsis - 비공개"""
    try:
        if not openai_client:
            return jsonify({"ok": False, "error": "OpenAI API key not configured"}), 500

        data = request.get_json()
        if not data:
            return jsonify({"ok": False, "error": "No data received"}), 400

        title = data.get("title", "무제")
        genre = data.get("genre", "드라마")
        drama_type = data.get("type", "short")
        running_time = data.get("runningTime", 10)
        characters = data.get("characters", [])
        theme = data.get("theme", "")
        setting = data.get("setting", "")
        conflict = data.get("conflict", "")

        # Build character description
        char_desc = ""
        for char in characters:
            char_desc += f"- {char.get('name', '?')}: {char.get('description', '')}\n"

        # Create system prompt
        type_desc = {
            'short': '5-10분 분량의 단막극',
            'episode': '20-30분 분량의 에피소드',
            'series': '시리즈물 연속극',
            'musical': '음악이 포함된 뮤지컬'
        }

        system_prompt = f"""당신은 전문 드라마 작가입니다.
주어진 정보를 바탕으로 매력적이고 구조가 탄탄한 드라마 시놉시스를 작성해주세요.

형식: {type_desc.get(drama_type, '드라마')}
장르: {genre}
러닝타임: {running_time}분

시놉시스는 다음을 포함해야 합니다:
1. 흥미로운 도입부 (Hook)
2. 주요 인물 소개
3. 핵심 갈등/사건
4. 스토리 전개 방향
5. 예상되는 클라이맥스와 결말 암시

간결하면서도 임팩트 있게 작성하세요."""

        user_prompt = f"""다음 정보를 바탕으로 드라마 시놉시스를 작성해주세요:

제목: {title}
장르: {genre}

등장인물:
{char_desc}

주제/테마: {theme}

배경/시대: {setting}

주요 갈등/사건:
{conflict}

위 정보를 바탕으로 매력적인 시놉시스를 작성해주세요."""

        # Call GPT
        completion = openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.8,
        )

        synopsis = completion.choices[0].message.content.strip()
        return jsonify({"ok": True, "synopsis": synopsis})

    except Exception as e:
        print(f"[DRAMA-SYNOPSIS][ERROR] {str(e)}")
        return jsonify({"ok": False, "error": str(e)}), 500

@app.route('/api/drama/scenes', methods=['POST'])
@login_required
def api_drama_scenes():
    """Generate scene structure - 비공개"""
    try:
        if not openai_client:
            return jsonify({"ok": False, "error": "OpenAI API key not configured"}), 500

        data = request.get_json()
        if not data:
            return jsonify({"ok": False, "error": "No data received"}), 400

        drama_type = data.get("type", "short")
        running_time = data.get("runningTime", 10)
        synopsis = data.get("synopsis", "")
        genre = data.get("genre", "드라마")
        characters = data.get("characters", [])

        # Build character list
        char_list = ", ".join([c.get('name', '?') for c in characters])

        system_prompt = f"""당신은 전문 드라마 작가입니다.
주어진 시놉시스를 바탕으로 구체적인 장면 구성을 작성해주세요.

러닝타임: {running_time}분
장르: {genre}

장면 구성 작성 시 포함할 내용:
1. 장면 번호와 제목
2. 장소 및 시간
3. 등장인물
4. 주요 사건/대화 내용
5. 장면의 목적 (스토리 전개, 캐릭터 성장 등)
6. 예상 분량 (초/분)

{running_time}분 분량에 적합하게 5-10개 정도의 장면으로 구성하세요."""

        user_prompt = f"""다음 시놉시스를 바탕으로 장면 구성을 작성해주세요:

【 시놉시스 】
{synopsis}

등장인물: {char_list}

각 장면을 구체적으로 구성해주세요."""

        # Call GPT
        completion = openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.7,
        )

        scenes = completion.choices[0].message.content.strip()
        return jsonify({"ok": True, "scenes": scenes})

    except Exception as e:
        print(f"[DRAMA-SCENES][ERROR] {str(e)}")
        return jsonify({"ok": False, "error": str(e)}), 500

@app.route('/api/drama/script', methods=['POST'])
@login_required
def api_drama_script():
    """Generate detailed drama script - 비공개"""
    try:
        if not openai_client:
            return jsonify({"ok": False, "error": "OpenAI API key not configured"}), 500

        data = request.get_json()
        if not data:
            return jsonify({"ok": False, "error": "No data received"}), 400

        title = data.get("title", "무제")
        synopsis = data.get("synopsis", "")
        scenes = data.get("scenes", "")
        characters = data.get("characters", [])
        setting = data.get("setting", "")
        genre = data.get("genre", "드라마")

        # Build character description
        char_desc = ""
        for char in characters:
            char_desc += f"- {char.get('name', '?')}: {char.get('description', '')}\n"

        system_prompt = f"""당신은 전문 드라마 대본 작가입니다.
주어진 시놉시스와 장면 구성을 바탕으로 구체적인 대본 스크립트를 작성해주세요.

장르: {genre}

대본 작성 형식:
1. 장면 번호, 제목, 장소, 시간 명시
2. 지문 (인물의 행동, 표정, 분위기 등)
3. 대사 (인물명: 대사 형식)
4. 필요시 (  ) 안에 감정이나 상황 묘사
5. 자연스럽고 현실적인 대화

실제 촬영이 가능한 수준의 구체적인 대본을 작성하세요."""

        user_prompt = f"""다음 정보를 바탕으로 상세한 드라마 대본을 작성해주세요:

【 제목 】
{title}

【 등장인물 】
{char_desc}

【 시놉시스 】
{synopsis}

【 장면 구성 】
{scenes}

배경: {setting}

위 정보를 바탕으로 실제 촬영이 가능한 구체적인 대본 스크립트를 작성해주세요.
대사, 지문, 행동 등을 모두 포함하여 완성도 높은 대본을 만들어주세요."""

        # Call GPT with higher quality model
        completion = openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.8,
        )

        script = completion.choices[0].message.content.strip()

        # Generate production notes
        notes_prompt = f"""다음 드라마 대본에 대한 연출 노트를 작성해주세요:

제목: {title}
장르: {genre}

【 대본 】
{script[:1000]}... (일부)

연출 노트에 포함할 내용:
1. 전체적인 톤 앤 매너
2. 촬영 시 주의사항
3. 조명 및 음향 가이드
4. 주요 장면 연출 포인트
5. 캐릭터 연기 지도 방향

간단명료하게 작성해주세요."""

        notes_completion = openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "당신은 전문 드라마 연출가입니다."},
                {"role": "user", "content": notes_prompt}
            ],
            temperature=0.7,
        )

        notes = notes_completion.choices[0].message.content.strip()

        return jsonify({"ok": True, "script": script, "notes": notes})

    except Exception as e:
        print(f"[DRAMA-SCRIPT][ERROR] {str(e)}")
        return jsonify({"ok": False, "error": str(e)}), 500


# ===== Video Service API Routes =====
from video_service import VideoService

video_service = VideoService()

@app.route('/api/video/create', methods=['POST'])
def api_create_video():
    """묵상메시지 비디오 생성"""
    try:
        data = request.json
        title = data.get('title', '')
        scripture_reference = data.get('scripture_reference', '')
        content = data.get('content', '')
        duration = data.get('duration', 15)

        if not title or not scripture_reference or not content:
            return jsonify({
                'ok': False,
                'error': '제목, 성경 구절, 내용은 필수입니다.'
            }), 400

        # 비디오 생성
        video_path = video_service.generator.create_sermon_video(
            title=title,
            scripture_reference=scripture_reference,
            content=content,
            duration=duration
        )

        # 데이터베이스에 저장
        user_id = session.get('user_id')
        conn = get_db_connection()
        cursor = conn.execute('''
            INSERT INTO videos (user_id, title, description, scripture_reference, content, video_path, duration)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (user_id, title, content[:500], scripture_reference, content, video_path, duration))

        video_id = cursor.lastrowid if hasattr(cursor, 'lastrowid') else cursor._cursor.lastrowid
        conn.commit()
        conn.close()

        return jsonify({
            'ok': True,
            'video_id': video_id,
            'video_path': video_path,
            'message': '비디오가 성공적으로 생성되었습니다.'
        })

    except Exception as e:
        print(f"[VIDEO-CREATE][ERROR] {str(e)}")
        return jsonify({'ok': False, 'error': str(e)}), 500


@app.route('/api/video/upload', methods=['POST'])
def api_upload_video():
    """비디오를 소셜 미디어 플랫폼에 업로드"""
    try:
        data = request.json
        video_id = data.get('video_id')
        platforms = data.get('platforms', [])  # ['youtube', 'instagram', 'tiktok']

        if not video_id or not platforms:
            return jsonify({
                'ok': False,
                'error': '비디오 ID와 플랫폼 정보가 필요합니다.'
            }), 400

        # 비디오 정보 조회
        conn = get_db_connection()
        video = conn.execute(
            'SELECT * FROM videos WHERE id = ?',
            (video_id,)
        ).fetchone()

        if not video:
            conn.close()
            return jsonify({'ok': False, 'error': '비디오를 찾을 수 없습니다.'}), 404

        # 플랫폼 인증 정보 조회
        user_id = session.get('user_id')
        credentials_map = {}

        for platform in platforms:
            cred = conn.execute(
                'SELECT credentials FROM platform_credentials WHERE user_id = ? AND platform = ? AND is_active = TRUE',
                (user_id, platform)
            ).fetchone()

            if cred:
                credentials_map[platform] = json.loads(cred['credentials'])
            else:
                return jsonify({
                    'ok': False,
                    'error': f'{platform} 인증 정보가 없습니다. 먼저 API 키를 설정해주세요.'
                }), 400

        # 업로드 수행
        sermon_data = {
            'title': video['title'],
            'scripture_reference': video['scripture_reference'],
            'content': video['content'],
            'duration': video['duration']
        }

        results = video_service.create_and_upload(
            sermon_data=sermon_data,
            platforms=platforms,
            credentials_map=credentials_map
        )

        # 업로드 이력 저장
        for platform, result in results['uploads'].items():
            conn.execute('''
                INSERT INTO video_uploads
                (video_id, platform, platform_video_id, upload_status, upload_url, uploaded_at, error_message)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                video_id,
                platform,
                result.get('video_id') or result.get('media_id'),
                result['status'],
                result.get('url'),
                'NOW()' if result['status'] == 'success' else None,
                result.get('error')
            ))

        conn.commit()
        conn.close()

        return jsonify({
            'ok': True,
            'results': results,
            'message': '업로드가 완료되었습니다.'
        })

    except Exception as e:
        print(f"[VIDEO-UPLOAD][ERROR] {str(e)}")
        return jsonify({'ok': False, 'error': str(e)}), 500


@app.route('/api/credentials/save', methods=['POST'])
def api_save_credentials():
    """플랫폼 API 인증 정보 저장"""
    try:
        data = request.json
        platform = data.get('platform')
        credentials = data.get('credentials')

        if not platform or not credentials:
            return jsonify({
                'ok': False,
                'error': '플랫폼과 인증 정보가 필요합니다.'
            }), 400

        user_id = session.get('user_id')

        # 기존 인증 정보 비활성화
        conn = get_db_connection()
        conn.execute(
            'UPDATE platform_credentials SET is_active = FALSE WHERE user_id = ? AND platform = ?',
            (user_id, platform)
        )

        # 새 인증 정보 저장
        conn.execute('''
            INSERT INTO platform_credentials (user_id, platform, credentials, is_active)
            VALUES (?, ?, ?, TRUE)
        ''', (user_id, platform, json.dumps(credentials)))

        conn.commit()
        conn.close()

        return jsonify({
            'ok': True,
            'message': f'{platform} 인증 정보가 저장되었습니다.'
        })

    except Exception as e:
        print(f"[CREDENTIALS-SAVE][ERROR] {str(e)}")
        return jsonify({'ok': False, 'error': str(e)}), 500


@app.route('/api/credentials/list', methods=['GET'])
def api_list_credentials():
    """사용자의 플랫폼 인증 정보 목록 조회"""
    try:
        user_id = session.get('user_id')

        conn = get_db_connection()
        credentials = conn.execute(
            'SELECT platform, is_active, created_at FROM platform_credentials WHERE user_id = ?',
            (user_id,)
        ).fetchall()
        conn.close()

        return jsonify({
            'ok': True,
            'credentials': [dict(c) for c in credentials]
        })

    except Exception as e:
        print(f"[CREDENTIALS-LIST][ERROR] {str(e)}")
        return jsonify({'ok': False, 'error': str(e)}), 500


@app.route('/api/video/list', methods=['GET'])
def api_list_videos():
    """사용자의 비디오 목록 조회"""
    try:
        user_id = session.get('user_id')

        conn = get_db_connection()
        videos = conn.execute(
            'SELECT * FROM videos WHERE user_id = ? ORDER BY created_at DESC',
            (user_id,)
        ).fetchall()
        conn.close()

        return jsonify({
            'ok': True,
            'videos': [dict(v) for v in videos]
        })

    except Exception as e:
        print(f"[VIDEO-LIST][ERROR] {str(e)}")
        return jsonify({'ok': False, 'error': str(e)}), 500


if __name__ == '__main__':
    app.run(debug=True)
