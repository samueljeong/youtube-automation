"""
교회 교적 관리 시스템 (Church Registry)
"""
import os
from datetime import datetime, date
from flask import Flask, render_template, redirect, url_for, request, flash, jsonify, send_file
from flask_sqlalchemy import SQLAlchemy
from dotenv import load_dotenv

load_dotenv()

# Flask 앱 초기화
app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')

# DATABASE_URL 처리 (Render PostgreSQL용)
database_url = os.getenv('DATABASE_URL', 'sqlite:///church.db')
if database_url.startswith('postgres://'):
    database_url = database_url.replace('postgres://', 'postgresql://', 1)
app.config['SQLALCHEMY_DATABASE_URI'] = database_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

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
# 데이터베이스 초기화
# =============================================================================

with app.app_context():
    db.create_all()


if __name__ == '__main__':
    app.run(debug=True, port=5000)
