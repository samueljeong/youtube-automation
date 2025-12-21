"""
교회 교적 관리 시스템 (Church Registry)
"""
import os
from flask import Flask, render_template, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from dotenv import load_dotenv

load_dotenv()

# Flask 앱 초기화
app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'sqlite:///church.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# 데이터베이스 초기화
db = SQLAlchemy(app)

# 로그인 매니저 초기화
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# =============================================================================
# 모델 임포트 (나중에 models/ 폴더로 분리)
# =============================================================================

class Member(db.Model):
    """교인 모델"""
    __tablename__ = 'members'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)  # 이름
    phone = db.Column(db.String(20))  # 전화번호
    email = db.Column(db.String(120))  # 이메일
    address = db.Column(db.String(200))  # 주소
    birth_date = db.Column(db.Date)  # 생년월일
    gender = db.Column(db.String(10))  # 성별

    # 교회 관련 정보
    baptism_date = db.Column(db.Date)  # 세례일
    registration_date = db.Column(db.Date)  # 등록일
    group_id = db.Column(db.Integer, db.ForeignKey('groups.id'))  # 셀/구역/목장

    # 가족 관계
    family_id = db.Column(db.Integer, db.ForeignKey('families.id'))
    family_role = db.Column(db.String(20))  # 가장, 배우자, 자녀 등

    # 상태
    status = db.Column(db.String(20), default='active')  # active, inactive, newcomer
    notes = db.Column(db.Text)  # 메모

    created_at = db.Column(db.DateTime, default=db.func.now())
    updated_at = db.Column(db.DateTime, default=db.func.now(), onupdate=db.func.now())

    def __repr__(self):
        return f'<Member {self.name}>'


class Family(db.Model):
    """가족 모델"""
    __tablename__ = 'families'

    id = db.Column(db.Integer, primary_key=True)
    family_name = db.Column(db.String(100))  # 가족명 (예: 홍길동 가정)
    members = db.relationship('Member', backref='family', lazy=True)

    created_at = db.Column(db.DateTime, default=db.func.now())


class Group(db.Model):
    """셀/구역/목장 그룹 모델"""
    __tablename__ = 'groups'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)  # 그룹명
    group_type = db.Column(db.String(50))  # cell, district, mokjang 등
    leader_id = db.Column(db.Integer)  # 리더 교인 ID

    members = db.relationship('Member', backref='group', lazy=True)

    created_at = db.Column(db.DateTime, default=db.func.now())


class Attendance(db.Model):
    """출석 기록 모델"""
    __tablename__ = 'attendance'

    id = db.Column(db.Integer, primary_key=True)
    member_id = db.Column(db.Integer, db.ForeignKey('members.id'), nullable=False)
    date = db.Column(db.Date, nullable=False)  # 출석 날짜
    service_type = db.Column(db.String(50))  # 주일예배, 수요예배, 금요기도회 등
    attended = db.Column(db.Boolean, default=True)

    member = db.relationship('Member', backref='attendance_records')

    created_at = db.Column(db.DateTime, default=db.func.now())


class Visit(db.Model):
    """심방 기록 모델"""
    __tablename__ = 'visits'

    id = db.Column(db.Integer, primary_key=True)
    member_id = db.Column(db.Integer, db.ForeignKey('members.id'), nullable=False)
    visit_date = db.Column(db.Date, nullable=False)
    visitor_name = db.Column(db.String(100))  # 심방자
    purpose = db.Column(db.String(100))  # 심방 목적
    notes = db.Column(db.Text)  # 심방 내용

    member = db.relationship('Member', backref='visit_records')

    created_at = db.Column(db.DateTime, default=db.func.now())


class Offering(db.Model):
    """헌금 기록 모델"""
    __tablename__ = 'offerings'

    id = db.Column(db.Integer, primary_key=True)
    member_id = db.Column(db.Integer, db.ForeignKey('members.id'))
    date = db.Column(db.Date, nullable=False)
    amount = db.Column(db.Integer, nullable=False)  # 금액 (원)
    offering_type = db.Column(db.String(50))  # 십일조, 감사헌금, 건축헌금 등
    notes = db.Column(db.Text)

    member = db.relationship('Member', backref='offering_records')

    created_at = db.Column(db.DateTime, default=db.func.now())


# =============================================================================
# 라우트
# =============================================================================

@app.route('/')
def index():
    """메인 페이지"""
    return render_template('index.html')


@app.route('/members')
def member_list():
    """교인 목록"""
    members = Member.query.all()
    return render_template('members/list.html', members=members)


@app.route('/health')
def health():
    """헬스 체크 (Render용)"""
    return {'status': 'ok'}


# =============================================================================
# 데이터베이스 초기화
# =============================================================================

with app.app_context():
    db.create_all()


if __name__ == '__main__':
    app.run(debug=True, port=5000)
