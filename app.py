from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3
import os
from functools import wraps

app = Flask(__name__)
app.secret_key = os.urandom(24)  # Secret key for session management

DB_PATH = os.path.join(os.path.dirname(__file__), 'users.db')

def get_db_connection():
    """Create a database connection"""
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

@app.route('/')
def index():
    """Home page"""
    return render_template('index.html')

@app.route('/bible')
def bible():
    """Bible page"""
    return render_template('bible.html')

@app.route('/message')
def message():
    """Message page"""
    return render_template('message.html')

if __name__ == '__main__':
    app.run(debug=True)
