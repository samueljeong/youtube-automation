"""
교회 교적 관리 시스템 (Church Registry)
AI 채팅 기반 교적 관리
"""
import os
import json
import base64
from datetime import datetime, date, timedelta
from flask import Flask, render_template, redirect, url_for, request, flash, jsonify, send_file
from flask_sqlalchemy import SQLAlchemy
from dotenv import load_dotenv
from openai import OpenAI
from werkzeug.utils import secure_filename

load_dotenv()

# OpenAI 클라이언트 (API 키가 있을 때만 초기화)
openai_api_key = os.getenv('OPENAI_API_KEY')
openai_client = OpenAI(api_key=openai_api_key) if openai_api_key else None

# Flask 앱 초기화
app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')

# DATABASE_URL 처리 (Render PostgreSQL용)
database_url = os.getenv('DATABASE_URL', 'sqlite:///church.db')
if database_url.startswith('postgres://'):
    database_url = database_url.replace('postgres://', 'postgresql://', 1)
app.config['SQLALCHEMY_DATABASE_URI'] = database_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# 사진 업로드 설정
UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static', 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB

# 데이터베이스 초기화
db = SQLAlchemy(app)

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

    # 사진
    photo_url = db.Column(db.String(500))  # 프로필 사진 URL

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
    # 검색 파라미터
    query = request.args.get('q', '')
    status_filter = request.args.get('status', '')
    group_filter = request.args.get('group', '')

    # 기본 쿼리
    members_query = Member.query

    # 이름 검색
    if query:
        members_query = members_query.filter(Member.name.contains(query))

    # 상태 필터
    if status_filter:
        members_query = members_query.filter(Member.status == status_filter)

    # 그룹 필터
    if group_filter:
        members_query = members_query.filter(Member.group_id == int(group_filter))

    members = members_query.order_by(Member.name).all()
    groups = Group.query.all()

    return render_template('members/list.html',
                         members=members,
                         groups=groups,
                         query=query,
                         status_filter=status_filter,
                         group_filter=group_filter)


@app.route('/members/new', methods=['GET', 'POST'])
def member_new():
    """교인 등록"""
    if request.method == 'POST':
        # 폼 데이터 수집
        name = request.form.get('name', '').strip()
        phone = request.form.get('phone', '').strip()
        email = request.form.get('email', '').strip()
        address = request.form.get('address', '').strip()
        gender = request.form.get('gender', '')
        status = request.form.get('status', 'active')
        group_id = request.form.get('group_id')
        notes = request.form.get('notes', '').strip()

        # 날짜 처리
        birth_date = None
        if request.form.get('birth_date'):
            birth_date = datetime.strptime(request.form.get('birth_date'), '%Y-%m-%d').date()

        baptism_date = None
        if request.form.get('baptism_date'):
            baptism_date = datetime.strptime(request.form.get('baptism_date'), '%Y-%m-%d').date()

        registration_date = None
        if request.form.get('registration_date'):
            registration_date = datetime.strptime(request.form.get('registration_date'), '%Y-%m-%d').date()
        else:
            registration_date = date.today()

        # 유효성 검사
        if not name:
            flash('이름은 필수 입력 항목입니다.', 'danger')
            return render_template('members/form.html', groups=Group.query.all())

        # 교인 생성
        member = Member(
            name=name,
            phone=phone,
            email=email,
            address=address,
            birth_date=birth_date,
            gender=gender,
            baptism_date=baptism_date,
            registration_date=registration_date,
            group_id=int(group_id) if group_id else None,
            status=status,
            notes=notes
        )

        db.session.add(member)
        db.session.commit()

        flash(f'{name} 교인이 등록되었습니다.', 'success')
        return redirect(url_for('member_detail', member_id=member.id))

    groups = Group.query.all()
    return render_template('members/form.html', groups=groups, member=None)


@app.route('/members/<int:member_id>')
def member_detail(member_id):
    """교인 상세 보기"""
    member = Member.query.get_or_404(member_id)
    return render_template('members/detail.html', member=member)


@app.route('/members/<int:member_id>/edit', methods=['GET', 'POST'])
def member_edit(member_id):
    """교인 수정"""
    member = Member.query.get_or_404(member_id)

    if request.method == 'POST':
        # 폼 데이터 수집
        member.name = request.form.get('name', '').strip()
        member.phone = request.form.get('phone', '').strip()
        member.email = request.form.get('email', '').strip()
        member.address = request.form.get('address', '').strip()
        member.gender = request.form.get('gender', '')
        member.status = request.form.get('status', 'active')
        member.notes = request.form.get('notes', '').strip()

        group_id = request.form.get('group_id')
        member.group_id = int(group_id) if group_id else None

        # 날짜 처리
        if request.form.get('birth_date'):
            member.birth_date = datetime.strptime(request.form.get('birth_date'), '%Y-%m-%d').date()
        else:
            member.birth_date = None

        if request.form.get('baptism_date'):
            member.baptism_date = datetime.strptime(request.form.get('baptism_date'), '%Y-%m-%d').date()
        else:
            member.baptism_date = None

        if request.form.get('registration_date'):
            member.registration_date = datetime.strptime(request.form.get('registration_date'), '%Y-%m-%d').date()

        # 유효성 검사
        if not member.name:
            flash('이름은 필수 입력 항목입니다.', 'danger')
            return render_template('members/form.html', groups=Group.query.all(), member=member)

        db.session.commit()

        flash(f'{member.name} 교인 정보가 수정되었습니다.', 'success')
        return redirect(url_for('member_detail', member_id=member.id))

    groups = Group.query.all()
    return render_template('members/form.html', groups=groups, member=member)


@app.route('/members/<int:member_id>/delete', methods=['POST'])
def member_delete(member_id):
    """교인 삭제"""
    member = Member.query.get_or_404(member_id)
    name = member.name

    db.session.delete(member)
    db.session.commit()

    flash(f'{name} 교인이 삭제되었습니다.', 'success')
    return redirect(url_for('member_list'))


@app.route('/health')
def health():
    """헬스 체크 (Render용)"""
    return {'status': 'ok'}


# =============================================================================
# 그룹 관리 라우트
# =============================================================================

@app.route('/groups')
def group_list():
    """그룹 목록"""
    groups = Group.query.order_by(Group.name).all()
    return render_template('groups/list.html', groups=groups)


@app.route('/groups/new', methods=['GET', 'POST'])
def group_new():
    """그룹 등록"""
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        group_type = request.form.get('group_type', '')
        leader_id = request.form.get('leader_id')

        if not name:
            flash('그룹명은 필수 입력 항목입니다.', 'danger')
            return render_template('groups/form.html', members=Member.query.all())

        group = Group(
            name=name,
            group_type=group_type,
            leader_id=int(leader_id) if leader_id else None
        )

        db.session.add(group)
        db.session.commit()

        flash(f'{name} 그룹이 생성되었습니다.', 'success')
        return redirect(url_for('group_list'))

    members = Member.query.order_by(Member.name).all()
    return render_template('groups/form.html', members=members, group=None)


@app.route('/groups/<int:group_id>')
def group_detail(group_id):
    """그룹 상세 보기"""
    group = Group.query.get_or_404(group_id)
    return render_template('groups/detail.html', group=group)


@app.route('/groups/<int:group_id>/edit', methods=['GET', 'POST'])
def group_edit(group_id):
    """그룹 수정"""
    group = Group.query.get_or_404(group_id)

    if request.method == 'POST':
        group.name = request.form.get('name', '').strip()
        group.group_type = request.form.get('group_type', '')
        leader_id = request.form.get('leader_id')
        group.leader_id = int(leader_id) if leader_id else None

        if not group.name:
            flash('그룹명은 필수 입력 항목입니다.', 'danger')
            return render_template('groups/form.html', members=Member.query.all(), group=group)

        db.session.commit()

        flash(f'{group.name} 그룹이 수정되었습니다.', 'success')
        return redirect(url_for('group_detail', group_id=group.id))

    members = Member.query.order_by(Member.name).all()
    return render_template('groups/form.html', members=members, group=group)


@app.route('/groups/<int:group_id>/delete', methods=['POST'])
def group_delete(group_id):
    """그룹 삭제"""
    group = Group.query.get_or_404(group_id)
    name = group.name

    # 소속 교인들의 그룹 해제
    for member in group.members:
        member.group_id = None

    db.session.delete(group)
    db.session.commit()

    flash(f'{name} 그룹이 삭제되었습니다.', 'success')
    return redirect(url_for('group_list'))


# =============================================================================
# 출석 관리 라우트
# =============================================================================

@app.route('/attendance')
def attendance_list():
    """출석 현황"""
    # 날짜 파라미터 (기본: 오늘)
    date_str = request.args.get('date')
    if date_str:
        selected_date = datetime.strptime(date_str, '%Y-%m-%d').date()
    else:
        selected_date = date.today()

    # 예배 종류 필터
    service_type = request.args.get('service', '주일예배')

    # 해당 날짜의 출석 기록
    attendance_records = Attendance.query.filter_by(
        date=selected_date,
        service_type=service_type
    ).all()

    # 출석한 교인 ID 목록
    attended_ids = {r.member_id for r in attendance_records if r.attended}

    # 전체 활동 교인
    members = Member.query.filter(Member.status.in_(['active', 'newcomer'])).order_by(Member.name).all()

    return render_template('attendance/list.html',
                         members=members,
                         attended_ids=attended_ids,
                         selected_date=selected_date,
                         service_type=service_type)


@app.route('/attendance/check', methods=['POST'])
def attendance_check():
    """출석 체크 처리"""
    selected_date = datetime.strptime(request.form.get('date'), '%Y-%m-%d').date()
    service_type = request.form.get('service_type', '주일예배')
    member_ids = request.form.getlist('member_ids')

    # 기존 출석 기록 삭제 (해당 날짜 + 예배 종류)
    Attendance.query.filter_by(date=selected_date, service_type=service_type).delete()

    # 새 출석 기록 생성
    for member_id in member_ids:
        attendance = Attendance(
            member_id=int(member_id),
            date=selected_date,
            service_type=service_type,
            attended=True
        )
        db.session.add(attendance)

    db.session.commit()

    flash(f'{selected_date.strftime("%Y-%m-%d")} {service_type} 출석이 저장되었습니다. ({len(member_ids)}명)', 'success')
    return redirect(url_for('attendance_list', date=selected_date.strftime('%Y-%m-%d'), service=service_type))


@app.route('/attendance/stats')
def attendance_stats():
    """출석 통계"""
    # 최근 4주 출석 통계
    from sqlalchemy import func

    stats = db.session.query(
        Attendance.date,
        Attendance.service_type,
        func.count(Attendance.id).label('count')
    ).filter(
        Attendance.attended == True
    ).group_by(
        Attendance.date,
        Attendance.service_type
    ).order_by(
        Attendance.date.desc()
    ).limit(20).all()

    return render_template('attendance/stats.html', stats=stats)


# =============================================================================
# 심방 기록 라우트
# =============================================================================

@app.route('/visits')
def visit_list():
    """심방 기록 목록"""
    visits = Visit.query.order_by(Visit.visit_date.desc()).limit(50).all()
    return render_template('visits/list.html', visits=visits)


@app.route('/visits/new', methods=['GET', 'POST'])
def visit_new():
    """심방 기록 등록"""
    if request.method == 'POST':
        member_id = request.form.get('member_id')
        visit_date = datetime.strptime(request.form.get('visit_date'), '%Y-%m-%d').date()
        visitor_name = request.form.get('visitor_name', '').strip()
        purpose = request.form.get('purpose', '').strip()
        notes = request.form.get('notes', '').strip()

        visit = Visit(
            member_id=int(member_id),
            visit_date=visit_date,
            visitor_name=visitor_name,
            purpose=purpose,
            notes=notes
        )

        db.session.add(visit)
        db.session.commit()

        flash('심방 기록이 저장되었습니다.', 'success')
        return redirect(url_for('visit_list'))

    members = Member.query.order_by(Member.name).all()
    return render_template('visits/form.html', members=members, visit=None)


@app.route('/visits/<int:visit_id>/delete', methods=['POST'])
def visit_delete(visit_id):
    """심방 기록 삭제"""
    visit = Visit.query.get_or_404(visit_id)
    db.session.delete(visit)
    db.session.commit()
    flash('심방 기록이 삭제되었습니다.', 'success')
    return redirect(url_for('visit_list'))


# =============================================================================
# 헌금 기록 라우트
# =============================================================================

@app.route('/offerings')
def offering_list():
    """헌금 기록 목록"""
    # 날짜 필터
    month = request.args.get('month')
    if month:
        year, m = map(int, month.split('-'))
        start_date = date(year, m, 1)
        if m == 12:
            end_date = date(year + 1, 1, 1)
        else:
            end_date = date(year, m + 1, 1)
        offerings = Offering.query.filter(
            Offering.date >= start_date,
            Offering.date < end_date
        ).order_by(Offering.date.desc()).all()
    else:
        offerings = Offering.query.order_by(Offering.date.desc()).limit(100).all()

    # 월별 합계
    from sqlalchemy import func
    total = sum(o.amount for o in offerings)

    return render_template('offerings/list.html', offerings=offerings, total=total, month=month)


@app.route('/offerings/new', methods=['GET', 'POST'])
def offering_new():
    """헌금 기록 등록"""
    if request.method == 'POST':
        member_id = request.form.get('member_id')
        offering_date = datetime.strptime(request.form.get('date'), '%Y-%m-%d').date()
        amount = int(request.form.get('amount', 0))
        offering_type = request.form.get('offering_type', '').strip()
        notes = request.form.get('notes', '').strip()

        offering = Offering(
            member_id=int(member_id) if member_id else None,
            date=offering_date,
            amount=amount,
            offering_type=offering_type,
            notes=notes
        )

        db.session.add(offering)
        db.session.commit()

        flash('헌금 기록이 저장되었습니다.', 'success')
        return redirect(url_for('offering_list'))

    members = Member.query.order_by(Member.name).all()
    return render_template('offerings/form.html', members=members, offering=None)


@app.route('/offerings/<int:offering_id>/delete', methods=['POST'])
def offering_delete(offering_id):
    """헌금 기록 삭제"""
    offering = Offering.query.get_or_404(offering_id)
    db.session.delete(offering)
    db.session.commit()
    flash('헌금 기록이 삭제되었습니다.', 'success')
    return redirect(url_for('offering_list'))


# =============================================================================
# 새신자 관리 라우트
# =============================================================================

@app.route('/newcomers')
def newcomer_list():
    """새신자 목록"""
    newcomers = Member.query.filter_by(status='newcomer').order_by(Member.registration_date.desc()).all()
    return render_template('newcomers/list.html', newcomers=newcomers)


# =============================================================================
# 생일/기념일 알림 라우트
# =============================================================================

@app.route('/birthdays')
def birthday_list():
    """이번 달 생일자 목록"""
    from sqlalchemy import extract

    current_month = date.today().month
    birthdays = Member.query.filter(
        extract('month', Member.birth_date) == current_month,
        Member.status.in_(['active', 'newcomer'])
    ).order_by(extract('day', Member.birth_date)).all()

    return render_template('birthdays/list.html', birthdays=birthdays, month=current_month)


# =============================================================================
# 엑셀 내보내기/가져오기 라우트
# =============================================================================

@app.route('/export/members')
def export_members():
    """교인 목록 엑셀 내보내기"""
    from openpyxl import Workbook
    from io import BytesIO
    from flask import send_file

    wb = Workbook()
    ws = wb.active
    ws.title = "교인 목록"

    # 헤더
    headers = ['이름', '전화번호', '이메일', '주소', '생년월일', '성별', '등록일', '세례일', '소속그룹', '상태', '메모']
    ws.append(headers)

    # 데이터
    members = Member.query.order_by(Member.name).all()
    for m in members:
        ws.append([
            m.name,
            m.phone or '',
            m.email or '',
            m.address or '',
            m.birth_date.strftime('%Y-%m-%d') if m.birth_date else '',
            m.gender or '',
            m.registration_date.strftime('%Y-%m-%d') if m.registration_date else '',
            m.baptism_date.strftime('%Y-%m-%d') if m.baptism_date else '',
            m.group.name if m.group else '',
            m.status or '',
            m.notes or ''
        ])

    # 파일로 저장
    output = BytesIO()
    wb.save(output)
    output.seek(0)

    return send_file(
        output,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        as_attachment=True,
        download_name=f'교인목록_{date.today().strftime("%Y%m%d")}.xlsx'
    )


@app.route('/import/members', methods=['GET', 'POST'])
def import_members():
    """교인 목록 엑셀 가져오기"""
    if request.method == 'POST':
        if 'file' not in request.files:
            flash('파일을 선택해주세요.', 'danger')
            return redirect(request.url)

        file = request.files['file']
        if file.filename == '':
            flash('파일을 선택해주세요.', 'danger')
            return redirect(request.url)

        if file and file.filename.endswith('.xlsx'):
            from openpyxl import load_workbook

            wb = load_workbook(file)
            ws = wb.active

            count = 0
            for row in ws.iter_rows(min_row=2, values_only=True):
                if row[0]:  # 이름이 있는 경우만
                    # 기존 교인 확인 (이름 + 전화번호로 중복 체크)
                    existing = Member.query.filter_by(name=row[0], phone=row[1] if row[1] else None).first()
                    if existing:
                        continue

                    member = Member(
                        name=row[0],
                        phone=row[1] if len(row) > 1 else None,
                        email=row[2] if len(row) > 2 else None,
                        address=row[3] if len(row) > 3 else None,
                        gender=row[5] if len(row) > 5 else None,
                        status=row[9] if len(row) > 9 and row[9] in ['active', 'inactive', 'newcomer'] else 'active',
                        notes=row[10] if len(row) > 10 else None
                    )

                    # 날짜 파싱
                    if len(row) > 4 and row[4]:
                        try:
                            if isinstance(row[4], str):
                                member.birth_date = datetime.strptime(row[4], '%Y-%m-%d').date()
                            else:
                                member.birth_date = row[4]
                        except:
                            pass

                    if len(row) > 6 and row[6]:
                        try:
                            if isinstance(row[6], str):
                                member.registration_date = datetime.strptime(row[6], '%Y-%m-%d').date()
                            else:
                                member.registration_date = row[6]
                        except:
                            pass

                    db.session.add(member)
                    count += 1

            db.session.commit()
            flash(f'{count}명의 교인이 등록되었습니다.', 'success')
            return redirect(url_for('member_list'))

        flash('xlsx 파일만 업로드 가능합니다.', 'danger')
        return redirect(request.url)

    return render_template('import/members.html')


# =============================================================================
# AI 채팅 API
# =============================================================================

# AI 도구 정의 (Function Calling)
AI_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search_members",
            "description": "교인을 검색합니다. 이름, 상태, 그룹 등으로 검색할 수 있습니다.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "교인 이름 (부분 일치)"},
                    "status": {"type": "string", "enum": ["active", "inactive", "newcomer"], "description": "상태"},
                    "group_name": {"type": "string", "description": "소속 그룹명"},
                    "gender": {"type": "string", "enum": ["남", "여"], "description": "성별"}
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "register_member",
            "description": "새 교인을 등록합니다.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "이름 (필수)"},
                    "phone": {"type": "string", "description": "전화번호"},
                    "email": {"type": "string", "description": "이메일"},
                    "address": {"type": "string", "description": "주소"},
                    "birth_date": {"type": "string", "description": "생년월일 (YYYY-MM-DD)"},
                    "gender": {"type": "string", "enum": ["남", "여"], "description": "성별"},
                    "status": {"type": "string", "enum": ["active", "newcomer"], "description": "상태 (기본: active)"},
                    "notes": {"type": "string", "description": "메모"}
                },
                "required": ["name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "update_member",
            "description": "기존 교인 정보를 수정합니다.",
            "parameters": {
                "type": "object",
                "properties": {
                    "member_id": {"type": "integer", "description": "교인 ID"},
                    "name": {"type": "string", "description": "이름"},
                    "phone": {"type": "string", "description": "전화번호"},
                    "email": {"type": "string", "description": "이메일"},
                    "address": {"type": "string", "description": "주소"},
                    "birth_date": {"type": "string", "description": "생년월일 (YYYY-MM-DD)"},
                    "gender": {"type": "string", "enum": ["남", "여"], "description": "성별"},
                    "status": {"type": "string", "enum": ["active", "inactive", "newcomer"], "description": "상태"},
                    "notes": {"type": "string", "description": "메모"}
                },
                "required": ["member_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_member_detail",
            "description": "특정 교인의 상세 정보를 조회합니다.",
            "parameters": {
                "type": "object",
                "properties": {
                    "member_id": {"type": "integer", "description": "교인 ID"},
                    "name": {"type": "string", "description": "교인 이름 (정확히 일치)"}
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_newcomers",
            "description": "새신자 목록을 조회합니다.",
            "parameters": {
                "type": "object",
                "properties": {
                    "days": {"type": "integer", "description": "최근 N일 이내 등록자 (기본: 전체)"}
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_birthdays",
            "description": "생일자 목록을 조회합니다.",
            "parameters": {
                "type": "object",
                "properties": {
                    "month": {"type": "integer", "description": "월 (1-12, 기본: 이번 달)"}
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_absent_members",
            "description": "장기 결석자 목록을 조회합니다.",
            "parameters": {
                "type": "object",
                "properties": {
                    "weeks": {"type": "integer", "description": "N주 이상 결석 (기본: 3)"}
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "recommend_visits",
            "description": "심방 우선순위를 추천합니다. 새신자, 장기결석자, 심방 안 간 분 등을 분석합니다.",
            "parameters": {
                "type": "object",
                "properties": {
                    "limit": {"type": "integer", "description": "추천 인원 수 (기본: 5)"}
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "record_visit",
            "description": "심방 기록을 등록합니다.",
            "parameters": {
                "type": "object",
                "properties": {
                    "member_name": {"type": "string", "description": "심방 대상 교인 이름"},
                    "member_id": {"type": "integer", "description": "심방 대상 교인 ID"},
                    "visit_date": {"type": "string", "description": "심방 날짜 (YYYY-MM-DD, 기본: 오늘)"},
                    "visitor_name": {"type": "string", "description": "심방자 이름"},
                    "purpose": {"type": "string", "description": "심방 목적"},
                    "notes": {"type": "string", "description": "심방 내용"}
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_statistics",
            "description": "교적 통계를 조회합니다.",
            "parameters": {
                "type": "object",
                "properties": {
                    "type": {"type": "string", "enum": ["overview", "attendance", "offering", "group"], "description": "통계 유형"}
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "manage_group",
            "description": "그룹(셀/구역/목장)을 관리합니다.",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {"type": "string", "enum": ["list", "create", "add_member", "remove_member"], "description": "작업 유형"},
                    "group_name": {"type": "string", "description": "그룹명"},
                    "group_type": {"type": "string", "enum": ["cell", "district", "mokjang"], "description": "그룹 유형"},
                    "member_name": {"type": "string", "description": "교인 이름 (add_member/remove_member 시)"}
                }
            }
        }
    }
]


def execute_ai_function(function_name: str, arguments: dict) -> str:
    """AI 함수 호출 실행"""

    if function_name == "search_members":
        query = Member.query
        if arguments.get("name"):
            query = query.filter(Member.name.contains(arguments["name"]))
        if arguments.get("status"):
            query = query.filter(Member.status == arguments["status"])
        if arguments.get("gender"):
            query = query.filter(Member.gender == arguments["gender"])
        if arguments.get("group_name"):
            group = Group.query.filter(Group.name.contains(arguments["group_name"])).first()
            if group:
                query = query.filter(Member.group_id == group.id)

        members = query.order_by(Member.name).limit(20).all()
        if not members:
            return json.dumps({"result": "검색 결과가 없습니다.", "count": 0}, ensure_ascii=False)

        result = []
        for m in members:
            result.append({
                "id": m.id,
                "name": m.name,
                "phone": m.phone or "",
                "status": m.status,
                "group": m.group.name if m.group else "",
                "gender": m.gender or ""
            })
        return json.dumps({"members": result, "count": len(result)}, ensure_ascii=False)

    elif function_name == "register_member":
        # 중복 체크
        existing = Member.query.filter_by(name=arguments["name"]).first()
        if existing and arguments.get("phone") == existing.phone:
            return json.dumps({"error": f"이미 '{arguments['name']}' 교인이 등록되어 있습니다. (ID: {existing.id})"}, ensure_ascii=False)

        member = Member(
            name=arguments["name"],
            phone=arguments.get("phone"),
            email=arguments.get("email"),
            address=arguments.get("address"),
            gender=arguments.get("gender"),
            status=arguments.get("status", "active"),
            notes=arguments.get("notes"),
            registration_date=date.today()
        )

        if arguments.get("birth_date"):
            try:
                member.birth_date = datetime.strptime(arguments["birth_date"], "%Y-%m-%d").date()
            except:
                pass

        db.session.add(member)
        db.session.commit()

        return json.dumps({
            "success": True,
            "message": f"'{member.name}' 교인이 등록되었습니다.",
            "member_id": member.id,
            "member": {
                "id": member.id,
                "name": member.name,
                "phone": member.phone,
                "status": member.status
            }
        }, ensure_ascii=False)

    elif function_name == "update_member":
        member = Member.query.get(arguments["member_id"])
        if not member:
            return json.dumps({"error": "해당 교인을 찾을 수 없습니다."}, ensure_ascii=False)

        if arguments.get("name"):
            member.name = arguments["name"]
        if arguments.get("phone"):
            member.phone = arguments["phone"]
        if arguments.get("email"):
            member.email = arguments["email"]
        if arguments.get("address"):
            member.address = arguments["address"]
        if arguments.get("gender"):
            member.gender = arguments["gender"]
        if arguments.get("status"):
            member.status = arguments["status"]
        if arguments.get("notes"):
            member.notes = arguments["notes"]
        if arguments.get("birth_date"):
            try:
                member.birth_date = datetime.strptime(arguments["birth_date"], "%Y-%m-%d").date()
            except:
                pass

        db.session.commit()
        return json.dumps({"success": True, "message": f"'{member.name}' 교인 정보가 수정되었습니다."}, ensure_ascii=False)

    elif function_name == "get_member_detail":
        member = None
        if arguments.get("member_id"):
            member = Member.query.get(arguments["member_id"])
        elif arguments.get("name"):
            member = Member.query.filter_by(name=arguments["name"]).first()

        if not member:
            return json.dumps({"error": "해당 교인을 찾을 수 없습니다."}, ensure_ascii=False)

        # 최근 출석
        recent_attendance = Attendance.query.filter_by(member_id=member.id, attended=True).order_by(Attendance.date.desc()).first()
        # 최근 심방
        recent_visit = Visit.query.filter_by(member_id=member.id).order_by(Visit.visit_date.desc()).first()

        return json.dumps({
            "id": member.id,
            "name": member.name,
            "phone": member.phone or "",
            "email": member.email or "",
            "address": member.address or "",
            "birth_date": member.birth_date.strftime("%Y-%m-%d") if member.birth_date else "",
            "gender": member.gender or "",
            "status": member.status,
            "group": member.group.name if member.group else "",
            "registration_date": member.registration_date.strftime("%Y-%m-%d") if member.registration_date else "",
            "baptism_date": member.baptism_date.strftime("%Y-%m-%d") if member.baptism_date else "",
            "notes": member.notes or "",
            "photo_url": member.photo_url or "",
            "last_attendance": recent_attendance.date.strftime("%Y-%m-%d") if recent_attendance else "기록 없음",
            "last_visit": recent_visit.visit_date.strftime("%Y-%m-%d") if recent_visit else "기록 없음"
        }, ensure_ascii=False)

    elif function_name == "get_newcomers":
        query = Member.query.filter_by(status="newcomer")
        if arguments.get("days"):
            cutoff = date.today() - timedelta(days=arguments["days"])
            query = query.filter(Member.registration_date >= cutoff)

        newcomers = query.order_by(Member.registration_date.desc()).all()
        result = []
        for m in newcomers:
            # 심방 여부 확인
            visited = Visit.query.filter_by(member_id=m.id).first() is not None
            result.append({
                "id": m.id,
                "name": m.name,
                "phone": m.phone or "",
                "registration_date": m.registration_date.strftime("%Y-%m-%d") if m.registration_date else "",
                "visited": visited
            })

        return json.dumps({"newcomers": result, "count": len(result)}, ensure_ascii=False)

    elif function_name == "get_birthdays":
        from sqlalchemy import extract
        month = arguments.get("month", date.today().month)

        birthdays = Member.query.filter(
            extract('month', Member.birth_date) == month,
            Member.status.in_(['active', 'newcomer'])
        ).order_by(extract('day', Member.birth_date)).all()

        result = []
        for m in birthdays:
            result.append({
                "id": m.id,
                "name": m.name,
                "birth_date": m.birth_date.strftime("%m월 %d일") if m.birth_date else "",
                "phone": m.phone or ""
            })

        return json.dumps({"birthdays": result, "count": len(result), "month": month}, ensure_ascii=False)

    elif function_name == "get_absent_members":
        weeks = arguments.get("weeks", 3)
        cutoff = date.today() - timedelta(weeks=weeks)

        # 최근 출석 기록이 있는 교인 ID
        recent_attended = db.session.query(Attendance.member_id).filter(
            Attendance.date >= cutoff,
            Attendance.attended == True
        ).distinct().subquery()

        # 활동 교인 중 최근 출석 안 한 사람
        absent = Member.query.filter(
            Member.status == 'active',
            ~Member.id.in_(db.session.query(recent_attended))
        ).all()

        result = []
        for m in absent:
            last_attendance = Attendance.query.filter_by(member_id=m.id, attended=True).order_by(Attendance.date.desc()).first()
            result.append({
                "id": m.id,
                "name": m.name,
                "phone": m.phone or "",
                "last_attendance": last_attendance.date.strftime("%Y-%m-%d") if last_attendance else "기록 없음"
            })

        return json.dumps({"absent_members": result, "count": len(result), "weeks": weeks}, ensure_ascii=False)

    elif function_name == "recommend_visits":
        limit = arguments.get("limit", 5)
        recommendations = []

        # 1. 새신자 중 심방 안 간 분
        newcomers = Member.query.filter_by(status="newcomer").all()
        for m in newcomers:
            if not Visit.query.filter_by(member_id=m.id).first():
                recommendations.append({
                    "id": m.id,
                    "name": m.name,
                    "phone": m.phone or "",
                    "reason": "새신자 - 아직 심방 전",
                    "priority": 1
                })

        # 2. 장기 결석자 (3주 이상)
        cutoff = date.today() - timedelta(weeks=3)
        recent_attended = db.session.query(Attendance.member_id).filter(
            Attendance.date >= cutoff,
            Attendance.attended == True
        ).distinct().subquery()

        absent = Member.query.filter(
            Member.status == 'active',
            ~Member.id.in_(db.session.query(recent_attended))
        ).all()

        for m in absent:
            if not any(r["id"] == m.id for r in recommendations):
                recommendations.append({
                    "id": m.id,
                    "name": m.name,
                    "phone": m.phone or "",
                    "reason": "3주 이상 출석 안 함",
                    "priority": 2
                })

        # 우선순위 정렬 후 제한
        recommendations.sort(key=lambda x: x["priority"])
        recommendations = recommendations[:limit]

        return json.dumps({"recommendations": recommendations, "count": len(recommendations)}, ensure_ascii=False)

    elif function_name == "record_visit":
        # 교인 찾기
        member = None
        if arguments.get("member_id"):
            member = Member.query.get(arguments["member_id"])
        elif arguments.get("member_name"):
            member = Member.query.filter_by(name=arguments["member_name"]).first()

        if not member:
            return json.dumps({"error": "해당 교인을 찾을 수 없습니다."}, ensure_ascii=False)

        visit_date = date.today()
        if arguments.get("visit_date"):
            try:
                visit_date = datetime.strptime(arguments["visit_date"], "%Y-%m-%d").date()
            except:
                pass

        visit = Visit(
            member_id=member.id,
            visit_date=visit_date,
            visitor_name=arguments.get("visitor_name", ""),
            purpose=arguments.get("purpose", ""),
            notes=arguments.get("notes", "")
        )

        db.session.add(visit)
        db.session.commit()

        return json.dumps({
            "success": True,
            "message": f"'{member.name}' 교인 심방 기록이 등록되었습니다.",
            "visit_id": visit.id
        }, ensure_ascii=False)

    elif function_name == "get_statistics":
        stat_type = arguments.get("type", "overview")

        if stat_type == "overview":
            total = Member.query.count()
            active = Member.query.filter_by(status="active").count()
            newcomer = Member.query.filter_by(status="newcomer").count()
            inactive = Member.query.filter_by(status="inactive").count()
            groups = Group.query.count()

            return json.dumps({
                "type": "overview",
                "total_members": total,
                "active": active,
                "newcomer": newcomer,
                "inactive": inactive,
                "groups": groups
            }, ensure_ascii=False)

        elif stat_type == "attendance":
            # 최근 4주 출석 통계
            from sqlalchemy import func
            four_weeks_ago = date.today() - timedelta(weeks=4)

            stats = db.session.query(
                Attendance.date,
                func.count(Attendance.id).label('count')
            ).filter(
                Attendance.date >= four_weeks_ago,
                Attendance.attended == True
            ).group_by(Attendance.date).order_by(Attendance.date.desc()).all()

            result = [{"date": s.date.strftime("%Y-%m-%d"), "count": s.count} for s in stats]
            return json.dumps({"type": "attendance", "stats": result}, ensure_ascii=False)

        elif stat_type == "group":
            groups = Group.query.all()
            result = []
            for g in groups:
                result.append({
                    "name": g.name,
                    "type": g.group_type or "",
                    "member_count": len(g.members)
                })
            return json.dumps({"type": "group", "groups": result}, ensure_ascii=False)

        return json.dumps({"error": "지원하지 않는 통계 유형입니다."}, ensure_ascii=False)

    elif function_name == "manage_group":
        action = arguments.get("action", "list")

        if action == "list":
            groups = Group.query.all()
            result = []
            for g in groups:
                leader = Member.query.get(g.leader_id) if g.leader_id else None
                result.append({
                    "id": g.id,
                    "name": g.name,
                    "type": g.group_type or "",
                    "leader": leader.name if leader else "",
                    "member_count": len(g.members)
                })
            return json.dumps({"groups": result, "count": len(result)}, ensure_ascii=False)

        elif action == "create":
            if not arguments.get("group_name"):
                return json.dumps({"error": "그룹명이 필요합니다."}, ensure_ascii=False)

            group = Group(
                name=arguments["group_name"],
                group_type=arguments.get("group_type", "cell")
            )
            db.session.add(group)
            db.session.commit()

            return json.dumps({
                "success": True,
                "message": f"'{group.name}' 그룹이 생성되었습니다.",
                "group_id": group.id
            }, ensure_ascii=False)

        elif action == "add_member":
            group = Group.query.filter_by(name=arguments.get("group_name")).first()
            member = Member.query.filter_by(name=arguments.get("member_name")).first()

            if not group:
                return json.dumps({"error": "해당 그룹을 찾을 수 없습니다."}, ensure_ascii=False)
            if not member:
                return json.dumps({"error": "해당 교인을 찾을 수 없습니다."}, ensure_ascii=False)

            member.group_id = group.id
            db.session.commit()

            return json.dumps({
                "success": True,
                "message": f"'{member.name}' 교인이 '{group.name}' 그룹에 추가되었습니다."
            }, ensure_ascii=False)

        return json.dumps({"error": "지원하지 않는 작업입니다."}, ensure_ascii=False)

    return json.dumps({"error": "알 수 없는 함수입니다."}, ensure_ascii=False)


def process_ai_chat(user_message: str, image_data: str = None) -> str:
    """AI 채팅 처리"""

    if not openai_client:
        return "OpenAI API 키가 설정되지 않았습니다. 환경변수 OPENAI_API_KEY를 설정해주세요."

    messages = [
        {
            "role": "system",
            "content": """당신은 교회 교적 관리 AI 어시스턴트입니다.

교인 등록, 검색, 수정, 심방 기록, 출석 관리 등을 도와드립니다.

사용자가 자연어로 요청하면 적절한 도구를 사용하여 작업을 수행하세요.

예시:
- "홍길동 집사님 등록해줘, 전화번호 010-1234-5678" → register_member 호출
- "김영희 권사님 정보 알려줘" → get_member_detail 호출
- "새신자 목록 보여줘" → get_newcomers 호출
- "이번 주 심방 갈 분 추천해줘" → recommend_visits 호출
- "지난 3주간 안 나온 분들" → get_absent_members 호출
- "이번 달 생일자" → get_birthdays 호출
- "전체 교인 수" → get_statistics 호출

사진이 첨부되면:
- 명함/등록카드 사진: 정보를 추출하여 등록 제안
- 인물 사진: 어떤 교인의 프로필 사진으로 등록할지 확인

응답은 친절하고 자연스럽게 해주세요. 한국어로 응답합니다."""
        }
    ]

    # 이미지가 있으면 Vision API 사용
    if image_data:
        messages.append({
            "role": "user",
            "content": [
                {"type": "text", "text": user_message if user_message else "이 사진을 분석해주세요. 명함이나 등록카드면 정보를 추출하고, 인물 사진이면 알려주세요."},
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_data}"}}
            ]
        })
    else:
        messages.append({"role": "user", "content": user_message})

    try:
        response = openai_client.chat.completions.create(
            model="gpt-4o",
            messages=messages,
            tools=AI_TOOLS,
            tool_choice="auto",
            max_tokens=2000
        )

        assistant_message = response.choices[0].message

        # 도구 호출이 있는 경우
        if assistant_message.tool_calls:
            # 도구 실행 결과 수집
            tool_results = []
            for tool_call in assistant_message.tool_calls:
                function_name = tool_call.function.name
                arguments = json.loads(tool_call.function.arguments)
                result = execute_ai_function(function_name, arguments)
                tool_results.append({
                    "tool_call_id": tool_call.id,
                    "role": "tool",
                    "content": result
                })

            # 도구 결과를 포함하여 다시 요청
            messages.append(assistant_message)
            messages.extend(tool_results)

            final_response = openai_client.chat.completions.create(
                model="gpt-4o",
                messages=messages,
                max_tokens=2000
            )

            return final_response.choices[0].message.content

        return assistant_message.content

    except Exception as e:
        return f"죄송합니다, 오류가 발생했습니다: {str(e)}"


@app.route('/api/chat', methods=['POST'])
def api_chat():
    """AI 채팅 API"""
    data = request.get_json()
    message = data.get('message', '')
    image_data = data.get('image')  # base64 encoded image

    if not message and not image_data:
        return jsonify({"error": "메시지 또는 이미지가 필요합니다."}), 400

    response = process_ai_chat(message, image_data)
    return jsonify({"response": response})


@app.route('/api/upload-photo', methods=['POST'])
def api_upload_photo():
    """사진 업로드 API"""
    if 'photo' not in request.files:
        return jsonify({"error": "파일이 없습니다."}), 400

    file = request.files['photo']
    member_id = request.form.get('member_id')

    if file.filename == '':
        return jsonify({"error": "파일이 선택되지 않았습니다."}), 400

    if file:
        # 파일명 생성
        ext = file.filename.rsplit('.', 1)[1].lower() if '.' in file.filename else 'jpg'
        filename = f"member_{member_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}.{ext}"
        filename = secure_filename(filename)

        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)

        # 교인 사진 URL 업데이트
        if member_id:
            member = Member.query.get(int(member_id))
            if member:
                member.photo_url = f"/static/uploads/{filename}"
                db.session.commit()

        return jsonify({
            "success": True,
            "url": f"/static/uploads/{filename}"
        })

    return jsonify({"error": "업로드 실패"}), 500


# =============================================================================
# 데이터베이스 초기화
# =============================================================================

with app.app_context():
    db.create_all()


if __name__ == '__main__':
    app.run(debug=True, port=5000)
