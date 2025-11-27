"""
sermon_modules/auth.py
인증 관련 함수, 데코레이터, 라우트
"""

from functools import wraps
from flask import Blueprint, render_template, request, jsonify, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash

from .db import get_db_connection, USE_POSTGRES, get_setting

# Blueprint 생성
auth_bp = Blueprint('auth', __name__)

# 기본 관리자 이메일
DEFAULT_ADMIN_EMAIL = 'zkvp17@naver.com'

# 인증 시스템 활성화/비활성화
AUTH_ENABLED = False


# ===== 크레딧 관련 함수 =====
def get_user_credits(user_id):
    """사용자 크레딧 조회"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        if USE_POSTGRES:
            cursor.execute('SELECT step3_credits FROM sermon_users WHERE id = %s', (user_id,))
        else:
            cursor.execute('SELECT step3_credits FROM sermon_users WHERE id = ?', (user_id,))
        result = cursor.fetchone()
        conn.close()
        return result['step3_credits'] if result else 0
    except:
        return 0


def use_credit(user_id):
    """크레딧 1회 차감"""
    try:
        credits = get_user_credits(user_id)
        if credits <= 0:
            return False

        conn = get_db_connection()
        cursor = conn.cursor()
        if USE_POSTGRES:
            cursor.execute('UPDATE sermon_users SET step3_credits = step3_credits - 1 WHERE id = %s AND step3_credits > 0', (user_id,))
        else:
            cursor.execute('UPDATE sermon_users SET step3_credits = step3_credits - 1 WHERE id = ? AND step3_credits > 0', (user_id,))
        conn.commit()
        affected = cursor.rowcount
        conn.close()
        return affected > 0
    except:
        return False


def add_credits(user_id, amount):
    """크레딧 추가"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        if USE_POSTGRES:
            cursor.execute('UPDATE sermon_users SET step3_credits = step3_credits + %s WHERE id = %s', (amount, user_id))
        else:
            cursor.execute('UPDATE sermon_users SET step3_credits = step3_credits + ? WHERE id = ?', (amount, user_id))
        conn.commit()
        conn.close()
        return True
    except:
        return False


def set_credits(user_id, amount):
    """크레딧 설정"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        if USE_POSTGRES:
            cursor.execute('UPDATE sermon_users SET step3_credits = %s WHERE id = %s', (amount, user_id))
        else:
            cursor.execute('UPDATE sermon_users SET step3_credits = ? WHERE id = ?', (amount, user_id))
        conn.commit()
        conn.close()
        return True
    except:
        return False


# ===== 데코레이터 =====
def login_required(f):
    """로그인 필수 데코레이터"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not AUTH_ENABLED:
            return f(*args, **kwargs)
        if 'user_id' not in session:
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated_function


def admin_required(f):
    """관리자 권한 필수 데코레이터"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('auth.login'))

        conn = get_db_connection()
        cursor = conn.cursor()
        if USE_POSTGRES:
            cursor.execute('SELECT is_admin FROM sermon_users WHERE id = %s', (session['user_id'],))
        else:
            cursor.execute('SELECT is_admin FROM sermon_users WHERE id = ?', (session['user_id'],))
        user = cursor.fetchone()
        conn.close()

        if not user or not user['is_admin']:
            flash('관리자 권한이 필요합니다.', 'error')
            return redirect(url_for('main.home'))

        return f(*args, **kwargs)
    return decorated_function


def api_login_required(f):
    """API용 로그인 필수 데코레이터"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not AUTH_ENABLED:
            return f(*args, **kwargs)
        if 'user_id' not in session:
            return jsonify({'ok': False, 'error': '로그인이 필요합니다.'}), 401
        return f(*args, **kwargs)
    return decorated_function


# ===== 라우트 =====
@auth_bp.route('/signup', methods=['GET', 'POST'])
def signup():
    """회원가입"""
    if request.method == 'GET':
        return render_template('signup.html')

    email = request.form.get('email', '').strip().lower()
    password = request.form.get('password', '')
    confirm_password = request.form.get('confirm_password', '')
    name = request.form.get('name', '').strip()
    phone = request.form.get('phone', '').strip()
    birth_date = request.form.get('birth_date', '').strip()

    # 유효성 검사
    if not email or not password or not name:
        flash('이메일, 비밀번호, 이름은 필수입니다.', 'error')
        return redirect(url_for('auth.signup'))

    if password != confirm_password:
        flash('비밀번호가 일치하지 않습니다.', 'error')
        return redirect(url_for('auth.signup'))

    if len(password) < 6:
        flash('비밀번호는 6자 이상이어야 합니다.', 'error')
        return redirect(url_for('auth.signup'))

    # 이메일 중복 확인
    conn = get_db_connection()
    cursor = conn.cursor()
    if USE_POSTGRES:
        cursor.execute('SELECT id FROM sermon_users WHERE email = %s', (email,))
    else:
        cursor.execute('SELECT id FROM sermon_users WHERE email = ?', (email,))

    if cursor.fetchone():
        conn.close()
        flash('이미 등록된 이메일입니다.', 'error')
        return redirect(url_for('auth.signup'))

    # 기본 크레딧 설정
    default_credits = int(get_setting('default_step3_credits', '3'))

    # 관리자 여부 확인
    is_admin = 1 if email == DEFAULT_ADMIN_EMAIL else 0

    # 사용자 생성
    password_hash = generate_password_hash(password)
    if USE_POSTGRES:
        cursor.execute('''
            INSERT INTO sermon_users (email, password_hash, name, phone, birth_date, is_admin, step3_credits)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            RETURNING id
        ''', (email, password_hash, name, phone, birth_date, is_admin, default_credits))
        user_id = cursor.fetchone()['id']
    else:
        cursor.execute('''
            INSERT INTO sermon_users (email, password_hash, name, phone, birth_date, is_admin, step3_credits)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (email, password_hash, name, phone, birth_date, is_admin, default_credits))
        user_id = cursor.lastrowid

    conn.commit()
    conn.close()

    # 자동 로그인
    session['user_id'] = user_id
    session['user_email'] = email
    session['user_name'] = name
    session['is_admin'] = is_admin

    flash(f'환영합니다, {name}님! Step3 크레딧 {default_credits}회가 지급되었습니다.', 'success')
    return redirect(url_for('main.sermon'))


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    """로그인"""
    if request.method == 'GET':
        return render_template('login.html')

    email = request.form.get('email', '').strip().lower()
    password = request.form.get('password', '')

    conn = get_db_connection()
    cursor = conn.cursor()
    if USE_POSTGRES:
        cursor.execute('SELECT * FROM sermon_users WHERE email = %s', (email,))
    else:
        cursor.execute('SELECT * FROM sermon_users WHERE email = ?', (email,))

    user = cursor.fetchone()
    conn.close()

    if not user or not check_password_hash(user['password_hash'], password):
        flash('이메일 또는 비밀번호가 올바르지 않습니다.', 'error')
        return redirect(url_for('auth.login'))

    if not user['is_active']:
        flash('비활성화된 계정입니다. 관리자에게 문의하세요.', 'error')
        return redirect(url_for('auth.login'))

    # 세션 설정
    session['user_id'] = user['id']
    session['user_email'] = user['email']
    session['user_name'] = user['name']
    session['is_admin'] = user['is_admin']

    flash(f'환영합니다, {user["name"]}님!', 'success')
    return redirect(url_for('main.sermon'))


@auth_bp.route('/logout')
def logout():
    """로그아웃"""
    session.clear()
    flash('로그아웃되었습니다.', 'info')
    return redirect(url_for('main.home'))


@auth_bp.route('/api/auth/status')
def auth_status():
    """인증 상태 확인 API"""
    if 'user_id' in session:
        return jsonify({
            'ok': True,
            'authenticated': True,
            'user': {
                'id': session['user_id'],
                'email': session.get('user_email'),
                'name': session.get('user_name'),
                'is_admin': session.get('is_admin', False)
            },
            'auth_enabled': AUTH_ENABLED
        })
    return jsonify({
        'ok': True,
        'authenticated': False,
        'auth_enabled': AUTH_ENABLED
    })


@auth_bp.route('/api/credits')
@api_login_required
def get_my_credits():
    """현재 사용자 크레딧 조회"""
    if not AUTH_ENABLED:
        return jsonify({'ok': True, 'credits': 999, 'auth_enabled': False})

    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'ok': False, 'error': '로그인이 필요합니다.'})

    credits = get_user_credits(user_id)
    return jsonify({'ok': True, 'credits': credits, 'auth_enabled': True})
