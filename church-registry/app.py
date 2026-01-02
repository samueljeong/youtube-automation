"""
교회 교적 관리 시스템 (Church Registry)
AI 채팅 기반 교적 관리
"""
import os
import json
import base64
import requests
from datetime import datetime, date, timedelta
try:
    from zoneinfo import ZoneInfo
except ImportError:
    from backports.zoneinfo import ZoneInfo
from flask import Flask, render_template, redirect, url_for, request, flash, jsonify, send_file
from flask_sqlalchemy import SQLAlchemy
from dotenv import load_dotenv
from openai import OpenAI
from werkzeug.utils import secure_filename
import cloudinary
import cloudinary.uploader

load_dotenv()

# 서울 시간대 (KST)
SEOUL_TZ = ZoneInfo('Asia/Seoul')

def get_seoul_now():
    """서울 시간대 기준 현재 시각"""
    return datetime.now(SEOUL_TZ)

def get_seoul_today():
    """서울 시간대 기준 오늘 날짜"""
    return datetime.now(SEOUL_TZ).date()

# OpenAI 클라이언트 (API 키가 있을 때만 초기화)
openai_api_key = os.getenv('OPENAI_API_KEY')
openai_client = OpenAI(api_key=openai_api_key) if openai_api_key else None

# Cloudinary 설정 (환경변수가 있을 때만 초기화)
cloudinary_configured = False
if os.getenv('CLOUDINARY_CLOUD_NAME'):
    cloudinary.config(
        cloud_name=os.getenv('CLOUDINARY_CLOUD_NAME'),
        api_key=os.getenv('CLOUDINARY_API_KEY'),
        api_secret=os.getenv('CLOUDINARY_API_SECRET'),
        secure=True
    )
    cloudinary_configured = True

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
    registration_number = db.Column(db.String(20))  # 등록번호 (2025-43 형식)
    group_id = db.Column(db.Integer, db.ForeignKey('groups.id'))  # 셀/구역/목장

    # 이전 교회 정보
    previous_church = db.Column(db.String(100))  # 이전 교회명
    previous_church_address = db.Column(db.String(200))  # 이전 교회 주소

    # 교회 조직 정보
    district = db.Column(db.String(20))  # 교구 (1, 2, 3...)
    cell_group = db.Column(db.String(50))  # 속회
    mission_group = db.Column(db.String(50))  # 선교회 (14남선교회 등)
    barnabas = db.Column(db.String(50))  # 바나바 (담당 장로/권사)
    referrer = db.Column(db.String(50))  # 인도자/관계

    # 신급 (학습, 세례, 유아세례, 입교)
    faith_level = db.Column(db.String(20))

    # 가족 관계
    family_id = db.Column(db.Integer, db.ForeignKey('families.id'))
    family_role = db.Column(db.String(20))  # 가장, 배우자, 자녀 등

    # 상태
    status = db.Column(db.String(20), default='active')  # active, inactive, newcomer
    notes = db.Column(db.Text)  # 메모

    # 성도 구분
    member_type = db.Column(db.String(20))  # 장년: 성도, 집사, 권사, 장로, 전도사, 목사, 명예집사, 명예권사
    department = db.Column(db.String(20))   # 교회학교: 유아부, 유치부, 아동부, 청소년부, 청년부 (장년은 null)

    # 사진
    photo_url = db.Column(db.String(500))  # 프로필 사진 URL

    # 외부 시스템 연동
    external_id = db.Column(db.String(50))  # 외부 시스템 ID (god4u 교적번호 등)

    created_at = db.Column(db.DateTime, default=get_seoul_now)
    updated_at = db.Column(db.DateTime, default=get_seoul_now, onupdate=get_seoul_now)

    @property
    def age(self):
        """나이 자동 계산 (만 나이)"""
        if not self.birth_date:
            return None
        today = get_seoul_today()
        age = today.year - self.birth_date.year
        # 생일이 아직 안 지났으면 1살 빼기
        if (today.month, today.day) < (self.birth_date.month, self.birth_date.day):
            age -= 1
        return age

    @property
    def is_newcomer(self):
        """새가족 여부 (등록 후 2년 이내)"""
        if not self.registration_date:
            return False
        two_years_ago = get_seoul_today() - timedelta(days=730)  # 약 2년
        return self.registration_date > two_years_ago

    @property
    def display_name(self):
        """표시용 이름 (이명섭 집사(새가족) 형식)"""
        name = self.name
        if self.member_type:
            name = f"{self.name} {self.member_type}"
        if self.is_newcomer:
            name = f"{name}(새가족)"
        return name

    def __repr__(self):
        return f'<Member {self.name}>'


class Family(db.Model):
    """가족 모델"""
    __tablename__ = 'families'

    id = db.Column(db.Integer, primary_key=True)
    family_name = db.Column(db.String(100))  # 가족명 (예: 홍길동 가정)
    members = db.relationship('Member', backref='family', lazy=True)

    created_at = db.Column(db.DateTime, default=get_seoul_now)


class Group(db.Model):
    """그룹 모델 - 계층 구조 지원 (교구/선교회/직분/교회학교/새가족)"""
    __tablename__ = 'groups'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)  # 그룹명
    group_type = db.Column(db.String(50))  # district, mission, position, school, newcomer
    leader_id = db.Column(db.Integer)  # 리더 교인 ID
    parent_id = db.Column(db.Integer, db.ForeignKey('groups.id'), nullable=True)  # 상위 그룹
    level = db.Column(db.Integer, default=0)  # 계층 레벨 (0: 최상위)
    description = db.Column(db.String(200))  # 설명

    # 자기 참조 관계
    parent = db.relationship('Group', remote_side=[id], backref='children')
    members = db.relationship('Member', backref='group', lazy=True)

    created_at = db.Column(db.DateTime, default=get_seoul_now)

    def get_full_path(self):
        """전체 경로 반환 (예: 교구 > 1교구 > 1구역)"""
        if self.parent:
            return f"{self.parent.get_full_path()} > {self.name}"
        return self.name

    def get_all_children(self):
        """모든 하위 그룹 반환 (재귀)"""
        result = list(self.children)
        for child in self.children:
            result.extend(child.get_all_children())
        return result

    def get_member_count(self, include_children=True):
        """소속 인원 수 (하위 그룹 포함 옵션)"""
        count = len(self.members)
        if include_children:
            for child in self.get_all_children():
                count += len(child.members)
        return count


class Attendance(db.Model):
    """출석 기록 모델"""
    __tablename__ = 'attendance'

    id = db.Column(db.Integer, primary_key=True)
    member_id = db.Column(db.Integer, db.ForeignKey('members.id'), nullable=False)
    date = db.Column(db.Date, nullable=False)  # 출석 날짜
    service_type = db.Column(db.String(50))  # 주일예배, 수요예배, 금요기도회 등
    attended = db.Column(db.Boolean, default=True)

    member = db.relationship('Member', backref='attendance_records')

    created_at = db.Column(db.DateTime, default=get_seoul_now)


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

    created_at = db.Column(db.DateTime, default=get_seoul_now)


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

    created_at = db.Column(db.DateTime, default=get_seoul_now)


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
        try:
            members_query = members_query.filter(Member.group_id == int(group_filter))
        except ValueError:
            pass  # 잘못된 그룹 ID는 무시

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
        # 폼 데이터 수집 - 기본 정보
        name = request.form.get('name', '').strip()
        phone = request.form.get('phone', '').strip()
        email = request.form.get('email', '').strip()
        address = request.form.get('address', '').strip()
        gender = request.form.get('gender', '')
        status = request.form.get('status', 'active')
        group_id = request.form.get('group_id')
        notes = request.form.get('notes', '').strip()
        member_type = request.form.get('member_type', '')
        department = request.form.get('department', '')
        photo_url = request.form.get('photo_url', '')

        # 새 필드들
        registration_number = request.form.get('registration_number', '').strip()
        previous_church = request.form.get('previous_church', '').strip()
        previous_church_address = request.form.get('previous_church_address', '').strip()
        district = request.form.get('district', '').strip()
        cell_group = request.form.get('cell_group', '').strip()
        mission_group = request.form.get('mission_group', '').strip()
        barnabas = request.form.get('barnabas', '').strip()
        referrer = request.form.get('referrer', '').strip()
        faith_level = request.form.get('faith_level', '').strip()

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
            registration_date = get_seoul_today()

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
            registration_number=registration_number if registration_number else None,
            group_id=int(group_id) if group_id else None,
            status=status,
            notes=notes,
            member_type=member_type if member_type else None,
            department=department if department else None,
            photo_url=photo_url if photo_url else None,
            previous_church=previous_church if previous_church else None,
            previous_church_address=previous_church_address if previous_church_address else None,
            district=district if district else None,
            cell_group=cell_group if cell_group else None,
            mission_group=mission_group if mission_group else None,
            barnabas=barnabas if barnabas else None,
            referrer=referrer if referrer else None,
            faith_level=faith_level if faith_level else None
        )

        db.session.add(member)
        db.session.commit()

        flash(f'{member.display_name}이(가) 등록되었습니다.', 'success')
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
        # 폼 데이터 수집 - 기본 정보
        member.name = request.form.get('name', '').strip()
        member.phone = request.form.get('phone', '').strip()
        member.email = request.form.get('email', '').strip()
        member.address = request.form.get('address', '').strip()
        member.gender = request.form.get('gender', '')
        member.status = request.form.get('status', 'active')
        member.notes = request.form.get('notes', '').strip()

        group_id = request.form.get('group_id')
        member.group_id = int(group_id) if group_id else None

        # 성도 구분
        member_type = request.form.get('member_type', '')
        member.member_type = member_type if member_type else None
        department = request.form.get('department', '')
        member.department = department if department else None

        # 사진 URL
        photo_url = request.form.get('photo_url', '')
        member.photo_url = photo_url if photo_url else None

        # 새 필드들
        registration_number = request.form.get('registration_number', '').strip()
        member.registration_number = registration_number if registration_number else None

        previous_church = request.form.get('previous_church', '').strip()
        member.previous_church = previous_church if previous_church else None

        previous_church_address = request.form.get('previous_church_address', '').strip()
        member.previous_church_address = previous_church_address if previous_church_address else None

        district = request.form.get('district', '').strip()
        member.district = district if district else None

        cell_group = request.form.get('cell_group', '').strip()
        member.cell_group = cell_group if cell_group else None

        mission_group = request.form.get('mission_group', '').strip()
        member.mission_group = mission_group if mission_group else None

        barnabas = request.form.get('barnabas', '').strip()
        member.barnabas = barnabas if barnabas else None

        referrer = request.form.get('referrer', '').strip()
        member.referrer = referrer if referrer else None

        faith_level = request.form.get('faith_level', '').strip()
        member.faith_level = faith_level if faith_level else None

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

        flash(f'{member.display_name} 정보가 수정되었습니다.', 'success')
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
    """그룹 목록 - 계층 구조로 표시"""
    # 최상위 그룹만 조회 (parent_id가 None인 그룹)
    top_groups = Group.query.filter_by(parent_id=None).order_by(Group.name).all()
    return render_template('groups/list.html', top_groups=top_groups)


@app.route('/groups/new', methods=['GET', 'POST'])
def group_new():
    """그룹 등록"""
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        group_type = request.form.get('group_type', '')
        leader_id = request.form.get('leader_id')
        parent_id = request.form.get('parent_id')
        description = request.form.get('description', '').strip()

        if not name:
            flash('그룹명은 필수 입력 항목입니다.', 'danger')
            members = Member.query.order_by(Member.name).all()
            all_groups = Group.query.order_by(Group.name).all()
            return render_template('groups/form.html', members=members, all_groups=all_groups)

        # 상위 그룹이 있으면 레벨과 타입 결정
        level = 0
        if parent_id:
            parent = Group.query.get(int(parent_id))
            if parent:
                level = parent.level + 1
                if not group_type:
                    group_type = parent.group_type

        group = Group(
            name=name,
            group_type=group_type,
            leader_id=int(leader_id) if leader_id else None,
            parent_id=int(parent_id) if parent_id else None,
            level=level,
            description=description
        )

        db.session.add(group)
        db.session.commit()

        flash(f'{name} 그룹이 생성되었습니다.', 'success')
        return redirect(url_for('group_list'))

    members = Member.query.order_by(Member.name).all()
    all_groups = Group.query.order_by(Group.level, Group.name).all()
    parent_id = request.args.get('parent_id', type=int)
    parent_group = Group.query.get(parent_id) if parent_id else None
    return render_template('groups/form.html', members=members, group=None,
                         all_groups=all_groups, parent_group=parent_group)


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
        parent_id = request.form.get('parent_id')
        group.description = request.form.get('description', '').strip()
        group.leader_id = int(leader_id) if leader_id else None

        # 상위 그룹 변경
        new_parent_id = int(parent_id) if parent_id else None
        if new_parent_id != group.parent_id:
            group.parent_id = new_parent_id
            if new_parent_id:
                parent = Group.query.get(new_parent_id)
                group.level = parent.level + 1 if parent else 0
            else:
                group.level = 0

        if not group.name:
            flash('그룹명은 필수 입력 항목입니다.', 'danger')
            members = Member.query.order_by(Member.name).all()
            all_groups = Group.query.filter(Group.id != group.id).order_by(Group.name).all()
            return render_template('groups/form.html', members=members, group=group, all_groups=all_groups)

        db.session.commit()

        flash(f'{group.name} 그룹이 수정되었습니다.', 'success')
        return redirect(url_for('group_detail', group_id=group.id))

    members = Member.query.order_by(Member.name).all()
    # 자기 자신과 자식 그룹은 상위 그룹으로 선택 불가
    exclude_ids = [group.id] + [c.id for c in group.get_all_children()]
    all_groups = Group.query.filter(~Group.id.in_(exclude_ids)).order_by(Group.level, Group.name).all()
    return render_template('groups/form.html', members=members, group=group, all_groups=all_groups)


@app.route('/groups/<int:group_id>/delete', methods=['POST'])
def group_delete(group_id):
    """그룹 삭제 (하위 그룹 포함)"""
    group = Group.query.get_or_404(group_id)
    name = group.name

    # 재귀적으로 모든 하위 그룹과 소속 교인 해제
    def delete_group_recursive(g):
        # 하위 그룹 먼저 삭제
        for child in g.children:
            delete_group_recursive(child)
        # 소속 교인들의 그룹 해제
        for member in g.members:
            member.group_id = None
        db.session.delete(g)

    delete_group_recursive(group)
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
        selected_date = get_seoul_today()

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


@app.route('/visits/<int:visit_id>/edit', methods=['GET', 'POST'])
def visit_edit(visit_id):
    """심방 기록 수정"""
    visit = Visit.query.get_or_404(visit_id)

    if request.method == 'POST':
        visit.member_id = int(request.form.get('member_id'))
        visit.visit_date = datetime.strptime(request.form.get('visit_date'), '%Y-%m-%d').date()
        visit.visitor_name = request.form.get('visitor_name', '').strip()
        visit.purpose = request.form.get('purpose', '').strip()
        visit.notes = request.form.get('notes', '').strip()

        db.session.commit()

        flash('심방 기록이 수정되었습니다.', 'success')
        return redirect(url_for('visit_list'))

    members = Member.query.order_by(Member.name).all()
    return render_template('visits/form.html', members=members, visit=visit)


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

    current_month = get_seoul_today().month
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
        download_name=f'교인목록_{get_seoul_today().strftime("%Y%m%d")}.xlsx'
    )


@app.route('/import/members', methods=['GET', 'POST'])
def import_members():
    """교인 목록 엑셀 가져오기 (헤더 기반 동적 매핑)"""
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

            # 헤더 매핑 (한글 헤더 → 필드명)
            HEADER_MAP = {
                '이름': 'name',
                '성명': 'name',
                'ID': 'registration_number',
                '등록번호': 'registration_number',
                '직분': 'member_type',
                '교구': 'district',
                '구역': 'cell_group',  # 구역도 cell_group으로 저장
                '속회': 'cell_group',
                '핸드폰': 'phone',
                '전화번호': 'phone',
                '연락처': 'phone',
                '생년월일': 'birth_date',
                '생일': 'birth_date',
                '주소': 'address',
                '이메일': 'email',
                '성별': 'gender',
                '세례일': 'baptism_date',
                '등록일': 'registration_date',
                '상태': 'status',
                '메모': 'notes',
                '비고': 'notes',
                '배우자': 'spouse_name',  # 임시 필드로 저장 후 notes에 추가
                '가족전체': 'family_info',  # 임시 필드
                '선교회': 'mission_group',
                '바나바': 'barnabas',
                '인도자': 'referrer',
            }

            # 1행에서 헤더 읽기
            headers = []
            for cell in ws[1]:
                header_name = str(cell.value).strip() if cell.value else ''
                headers.append(header_name)

            # 헤더 → 열 인덱스 매핑
            col_map = {}
            for idx, header in enumerate(headers):
                if header in HEADER_MAP:
                    field = HEADER_MAP[header]
                    if field not in col_map:  # 첫 번째 매칭만 사용
                        col_map[field] = idx

            count = 0
            skipped = 0
            for row in ws.iter_rows(min_row=2, values_only=True):
                # 이름 필드 확인
                name_idx = col_map.get('name')
                if name_idx is None or not row[name_idx]:
                    continue

                name = str(row[name_idx]).strip()

                # 전화번호 가져오기
                phone = None
                phone_idx = col_map.get('phone')
                if phone_idx is not None and row[phone_idx]:
                    phone = str(row[phone_idx]).strip()

                # 기존 교인 확인 (이름 + 전화번호로 중복 체크)
                existing = Member.query.filter_by(name=name, phone=phone).first()
                if existing:
                    skipped += 1
                    continue

                # Member 객체 생성
                member = Member(name=name, phone=phone, status='active')

                # 등록번호
                if 'registration_number' in col_map and row[col_map['registration_number']]:
                    member.registration_number = str(row[col_map['registration_number']]).strip()

                # 직분 (member_type)
                if 'member_type' in col_map and row[col_map['member_type']]:
                    member.member_type = str(row[col_map['member_type']]).strip()

                # 교구
                if 'district' in col_map and row[col_map['district']]:
                    district_val = str(row[col_map['district']]).strip()
                    # "2교구" → "2"
                    member.district = district_val.replace('교구', '').strip()

                # 속회/구역
                if 'cell_group' in col_map and row[col_map['cell_group']]:
                    member.cell_group = str(row[col_map['cell_group']]).strip()

                # 선교회
                if 'mission_group' in col_map and row[col_map['mission_group']]:
                    member.mission_group = str(row[col_map['mission_group']]).strip()

                # 바나바
                if 'barnabas' in col_map and row[col_map['barnabas']]:
                    member.barnabas = str(row[col_map['barnabas']]).strip()

                # 인도자
                if 'referrer' in col_map and row[col_map['referrer']]:
                    member.referrer = str(row[col_map['referrer']]).strip()

                # 주소
                if 'address' in col_map and row[col_map['address']]:
                    member.address = str(row[col_map['address']]).strip()

                # 이메일
                if 'email' in col_map and row[col_map['email']]:
                    member.email = str(row[col_map['email']]).strip()

                # 성별
                if 'gender' in col_map and row[col_map['gender']]:
                    member.gender = str(row[col_map['gender']]).strip()

                # 상태
                if 'status' in col_map and row[col_map['status']]:
                    status_val = str(row[col_map['status']]).strip()
                    if status_val in ['active', 'inactive', 'newcomer']:
                        member.status = status_val
                    elif status_val in ['활동', '재적']:
                        member.status = 'active'
                    elif status_val in ['비활동', '휴적']:
                        member.status = 'inactive'
                    elif status_val in ['새신자', '새가족']:
                        member.status = 'newcomer'

                # 메모 구성
                notes_parts = []
                if 'notes' in col_map and row[col_map['notes']]:
                    notes_parts.append(str(row[col_map['notes']]).strip())
                if 'spouse_name' in col_map and row[col_map['spouse_name']]:
                    notes_parts.append(f"배우자: {row[col_map['spouse_name']]}")
                if 'family_info' in col_map and row[col_map['family_info']]:
                    notes_parts.append(f"가족: {row[col_map['family_info']]}")
                if notes_parts:
                    member.notes = '\n'.join(notes_parts)

                # 날짜 필드 파싱 함수
                def parse_date(value):
                    if not value:
                        return None
                    if isinstance(value, date):
                        return value
                    if isinstance(value, datetime):
                        return value.date()
                    try:
                        value_str = str(value).strip()
                        # 다양한 형식 시도
                        for fmt in ['%Y-%m-%d', '%Y/%m/%d', '%y/%m/%d', '%m/%d/%y', '%Y.%m.%d']:
                            try:
                                return datetime.strptime(value_str, fmt).date()
                            except ValueError:
                                continue
                    except:
                        pass
                    return None

                # 생년월일
                if 'birth_date' in col_map:
                    member.birth_date = parse_date(row[col_map['birth_date']])

                # 세례일
                if 'baptism_date' in col_map:
                    member.baptism_date = parse_date(row[col_map['baptism_date']])

                # 등록일
                if 'registration_date' in col_map:
                    member.registration_date = parse_date(row[col_map['registration_date']])

                db.session.add(member)
                count += 1

            db.session.commit()
            msg = f'{count}명의 교인이 등록되었습니다.'
            if skipped > 0:
                msg += f' ({skipped}명 중복으로 건너뜀)'
            flash(msg, 'success')
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
            "description": "새 교인을 등록하거나 기존 교인 정보를 업데이트합니다. 동명이인이 있으면 확인 후 처리합니다.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "이름 (필수, 직분 포함 가능: 홍길동 집사)"},
                    "phone": {"type": "string", "description": "전화번호"},
                    "email": {"type": "string", "description": "이메일"},
                    "address": {"type": "string", "description": "주소"},
                    "birth_date": {"type": "string", "description": "생년월일 (YYYY-MM-DD)"},
                    "gender": {"type": "string", "enum": ["남", "여"], "description": "성별"},
                    "status": {"type": "string", "enum": ["active", "newcomer"], "description": "상태 (기본: active)"},
                    "notes": {"type": "string", "description": "메모/특이사항"},
                    "registration_number": {"type": "string", "description": "등록번호"},
                    "previous_church": {"type": "string", "description": "이전교회/출석교회"},
                    "previous_church_address": {"type": "string", "description": "이전교회 주소"},
                    "district": {"type": "string", "description": "교구 (숫자)"},
                    "cell_group": {"type": "string", "description": "속회"},
                    "mission_group": {"type": "string", "description": "선교회"},
                    "barnabas": {"type": "string", "description": "바나바 (담당 장로/권사)"},
                    "referrer": {"type": "string", "description": "인도자/관계"},
                    "faith_level": {"type": "string", "description": "신급 (학습/세례/유아세례/입교)"},
                    "update_existing_id": {"type": "integer", "description": "기존 교인 ID - 동명이인 중 특정 교인 정보를 업데이트할 때 사용"},
                    "force_new": {"type": "boolean", "description": "true이면 동명이인이 있어도 새 교인으로 등록 (이름에 번호 추가)"}
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
        # 직분 목록 (이름에서 분리)
        titles = ["목사", "장로", "권사", "집사", "전도사", "선교사", "성도"]

        # 이름에서 직분 분리
        input_name = arguments["name"].strip()
        base_name = input_name
        input_title = None
        for title in titles:
            if input_name.endswith(" " + title):
                base_name = input_name[:-len(title)-1].strip()
                input_title = title
                break
            elif input_name.endswith(title):
                base_name = input_name[:-len(title)].strip()
                input_title = title
                break

        # 동명이인 체크 - 기본 이름으로 검색 (직분 무관)
        all_members = Member.query.all()
        existing_members = []
        for m in all_members:
            member_base_name = m.name
            for title in titles:
                if m.name.endswith(" " + title):
                    member_base_name = m.name[:-len(title)-1].strip()
                    break
                elif m.name.endswith(title):
                    member_base_name = m.name[:-len(title)].strip()
                    break
            # 번호 접미사 제거 (홍길동(1) -> 홍길동)
            if "(" in member_base_name and member_base_name.endswith(")"):
                member_base_name = member_base_name[:member_base_name.rfind("(")].strip()

            if member_base_name == base_name:
                existing_members.append(m)

        # force_new가 True이면 동명이인으로 새로 등록 (이름에 번호 추가)
        if arguments.get("force_new") and existing_members:
            # 동명이인 번호 계산 - 기존 멤버들 중 최대 번호 찾기
            max_suffix = 0
            for m in existing_members:
                # 이미 번호가 붙은 경우 (홍길동(1), 홍길동(2) ...)
                if "(" in m.name and m.name.endswith(")"):
                    try:
                        suffix = int(m.name[m.name.rfind("(")+1:-1])
                        max_suffix = max(max_suffix, suffix + 1)
                    except:
                        max_suffix = max(max_suffix, 1)
                else:
                    max_suffix = max(max_suffix, 1)

            # 직분 유지하면서 번호 추가 (이명섭 집사 -> 이명섭(1) 집사)
            if input_title:
                new_name = f"{base_name}({max_suffix}) {input_title}"
            else:
                new_name = f"{base_name}({max_suffix})"
            arguments["name"] = new_name
            existing_members = []  # 새 이름으로 등록하므로 중복 없음

        # update_existing_id가 있으면 기존 교인 정보 업데이트
        if arguments.get("update_existing_id"):
            member = Member.query.get(arguments["update_existing_id"])
            if not member:
                return json.dumps({"error": "해당 교인을 찾을 수 없습니다."}, ensure_ascii=False)

            # 제공된 정보만 업데이트 - 기본 정보
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

            # 교회 관련 정보
            if arguments.get("registration_number"):
                member.registration_number = arguments["registration_number"]
            if arguments.get("previous_church"):
                member.previous_church = arguments["previous_church"]
            if arguments.get("previous_church_address"):
                member.previous_church_address = arguments["previous_church_address"]
            if arguments.get("district"):
                member.district = arguments["district"]
            if arguments.get("cell_group"):
                member.cell_group = arguments["cell_group"]
            if arguments.get("mission_group"):
                member.mission_group = arguments["mission_group"]
            if arguments.get("barnabas"):
                member.barnabas = arguments["barnabas"]
            if arguments.get("referrer"):
                member.referrer = arguments["referrer"]
            if arguments.get("faith_level"):
                member.faith_level = arguments["faith_level"]

            db.session.commit()
            return json.dumps({
                "success": True,
                "action": "updated",
                "message": f"'{member.display_name}' 교인 정보가 업데이트되었습니다.",
                "member_id": member.id
            }, ensure_ascii=False)

        # 동명이인이 있는 경우 사용자에게 확인 요청
        if existing_members:
            existing_info = []
            for m in existing_members:
                info = {
                    "id": m.id,
                    "name": m.name,
                    "display_name": m.display_name,
                    "phone": m.phone or "연락처 없음",
                    "birth_date": m.birth_date.strftime("%Y-%m-%d") if m.birth_date else "생년월일 없음",
                    "status": m.status,
                    "registration_date": m.registration_date.strftime("%Y-%m-%d") if m.registration_date else ""
                }
                existing_info.append(info)

            return json.dumps({
                "duplicate_found": True,
                "message": f"'{arguments['name']}' 이름의 교인이 이미 {len(existing_members)}명 등록되어 있습니다.",
                "existing_members": existing_info,
                "suggestion": "기존 교인 정보를 업데이트하려면 update_existing_id에 해당 교인 ID를 지정하세요. 동명이인으로 새로 등록하려면 force_new=true를 사용하세요.",
                "pending_data": {
                    "name": arguments.get("name"),
                    "phone": arguments.get("phone"),
                    "email": arguments.get("email"),
                    "address": arguments.get("address"),
                    "birth_date": arguments.get("birth_date"),
                    "gender": arguments.get("gender"),
                    "status": arguments.get("status"),
                    "notes": arguments.get("notes"),
                    "registration_number": arguments.get("registration_number"),
                    "previous_church": arguments.get("previous_church"),
                    "previous_church_address": arguments.get("previous_church_address"),
                    "district": arguments.get("district"),
                    "cell_group": arguments.get("cell_group"),
                    "mission_group": arguments.get("mission_group"),
                    "barnabas": arguments.get("barnabas"),
                    "referrer": arguments.get("referrer"),
                    "faith_level": arguments.get("faith_level")
                }
            }, ensure_ascii=False)

        # 새 교인 등록
        member = Member(
            name=arguments["name"],
            phone=arguments.get("phone"),
            email=arguments.get("email"),
            address=arguments.get("address"),
            gender=arguments.get("gender"),
            status=arguments.get("status", "active"),
            notes=arguments.get("notes"),
            registration_date=get_seoul_today(),
            # 교회 관련 정보
            registration_number=arguments.get("registration_number"),
            previous_church=arguments.get("previous_church"),
            previous_church_address=arguments.get("previous_church_address"),
            district=arguments.get("district"),
            cell_group=arguments.get("cell_group"),
            mission_group=arguments.get("mission_group"),
            barnabas=arguments.get("barnabas"),
            referrer=arguments.get("referrer"),
            faith_level=arguments.get("faith_level")
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
            "action": "created",
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
            cutoff = get_seoul_today() - timedelta(days=arguments["days"])
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
        month = arguments.get("month", get_seoul_today().month)

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
        cutoff = get_seoul_today() - timedelta(weeks=weeks)

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
        cutoff = get_seoul_today() - timedelta(weeks=3)
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

        visit_date = get_seoul_today()
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
            four_weeks_ago = get_seoul_today() - timedelta(weeks=4)

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

동명이인 처리:
register_member 호출 시 동명이인이 있으면 duplicate_found: true 응답이 옵니다.
이 경우 사용자에게 기존 교인 목록을 보여주고 다음을 물어보세요:
1. 기존 교인 정보 업데이트: "홍길동 생년월일 추가해줘" → update_existing_id 사용
2. 동명이인으로 새로 등록: "새 홍길동으로 등록해줘" → force_new=true 사용

예시 응답:
"'홍길동' 이름의 교인이 이미 등록되어 있습니다:
1. 홍길동 집사 (010-1234-5678, 1985-03-15생)
2. 홍길동 성도 (연락처 없음, 생년월일 없음)

기존 교인 정보를 업데이트할까요, 아니면 동명이인으로 새로 등록할까요?"

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
    """사진 업로드 API - Cloudinary 또는 로컬 저장소 사용"""
    if 'photo' not in request.files:
        return jsonify({"error": "파일이 없습니다."}), 400

    file = request.files['photo']
    member_id = request.form.get('member_id')

    if file.filename == '':
        return jsonify({"error": "파일이 선택되지 않았습니다."}), 400

    if file:
        try:
            # Cloudinary가 설정되어 있으면 클라우드에 업로드
            if cloudinary_configured:
                # 고유 public_id 생성
                public_id = f"church-registry/member_{member_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}"

                # Cloudinary에 업로드
                result = cloudinary.uploader.upload(
                    file,
                    public_id=public_id,
                    folder="church-registry",
                    transformation=[
                        {"width": 400, "height": 400, "crop": "fill", "gravity": "face"}
                    ]
                )

                photo_url = result['secure_url']

                # 교인 사진 URL 업데이트
                if member_id:
                    member = Member.query.get(int(member_id))
                    if member:
                        member.photo_url = photo_url
                        db.session.commit()

                return jsonify({
                    "success": True,
                    "url": photo_url,
                    "storage": "cloudinary"
                })

            else:
                # Cloudinary가 없으면 로컬에 저장 (개발용)
                ext = file.filename.rsplit('.', 1)[1].lower() if '.' in file.filename else 'jpg'
                filename = f"member_{member_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}.{ext}"
                filename = secure_filename(filename)

                filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                file.save(filepath)

                photo_url = f"/static/uploads/{filename}"

                # 교인 사진 URL 업데이트
                if member_id:
                    member = Member.query.get(int(member_id))
                    if member:
                        member.photo_url = photo_url
                        db.session.commit()

                return jsonify({
                    "success": True,
                    "url": photo_url,
                    "storage": "local"
                })

        except Exception as e:
            return jsonify({"error": f"업로드 실패: {str(e)}"}), 500

    return jsonify({"error": "업로드 실패"}), 500


@app.route('/api/analyze-excel', methods=['POST'])
def api_analyze_excel():
    """엑셀 파일 분석 API - AI가 열 매핑을 자동 분석"""
    if 'file' not in request.files:
        return jsonify({"error": "파일이 없습니다."}), 400

    file = request.files['file']
    if not file.filename.endswith(('.xlsx', '.xls')):
        return jsonify({"error": "엑셀 파일(.xlsx, .xls)만 지원합니다."}), 400

    try:
        from openpyxl import load_workbook

        wb = load_workbook(file)
        ws = wb.active

        # 첫 10행 정도만 샘플로 추출
        rows = []
        for i, row in enumerate(ws.iter_rows(values_only=True)):
            if i >= 15:  # 헤더 + 14개 샘플
                break
            rows.append([str(cell) if cell is not None else "" for cell in row])

        if not rows:
            return jsonify({"error": "빈 엑셀 파일입니다."}), 400

        # AI에게 분석 요청
        if not openai_client:
            return jsonify({"error": "OpenAI API 키가 설정되지 않았습니다."}), 500

        # 엑셀 데이터를 텍스트로 변환
        excel_text = "엑셀 데이터 샘플:\n"
        for i, row in enumerate(rows):
            excel_text += f"행 {i+1}: {' | '.join(row)}\n"

        response = openai_client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "system",
                    "content": """당신은 교회 교적 데이터 분석 전문가입니다.
엑셀 파일의 열을 분석하여 교인 정보와 매핑해주세요.

분석 결과를 다음 JSON 형식으로 반환하세요:
{
    "header_row": 1,  // 헤더가 있는 행 번호 (1부터 시작)
    "mapping": {
        "name": 0,  // 이름 열 인덱스 (0부터 시작, 없으면 null)
        "phone": 1,
        "email": null,
        "address": 2,
        "birth_date": 3,
        "gender": 4,
        "registration_date": null,
        "baptism_date": null,
        "status": null,
        "notes": null
    },
    "sample_data": [
        {"name": "홍길동", "phone": "010-1234-5678", ...},
        {"name": "김영희", "phone": "010-9876-5432", ...}
    ],
    "total_rows": 100,  // 추정 데이터 행 수
    "analysis": "이 엑셀은 교인 명부로 보입니다. 이름, 연락처, 주소, 생년월일, 성별 정보가 있습니다."
}

주의:
- 헤더 행을 정확히 파악하세요
- 이름 열은 필수입니다
- 날짜 형식이 다양할 수 있습니다 (예: 1990-01-01, 1990.01.01, 90/1/1)
- 성별은 남/여, M/F, 남자/여자 등 다양할 수 있습니다"""
                },
                {"role": "user", "content": excel_text}
            ],
            response_format={"type": "json_object"},
            max_tokens=2000
        )

        analysis = json.loads(response.choices[0].message.content)

        # 전체 데이터 행 수 계산
        total_rows = sum(1 for row in ws.iter_rows(values_only=True)) - analysis.get("header_row", 1)
        analysis["total_rows"] = total_rows

        return jsonify({
            "success": True,
            "analysis": analysis,
            "raw_headers": rows[analysis.get("header_row", 1) - 1] if rows else []
        })

    except Exception as e:
        return jsonify({"error": f"엑셀 분석 중 오류: {str(e)}"}), 500


@app.route('/api/import-analyzed', methods=['POST'])
def api_import_analyzed():
    """분석된 매핑으로 엑셀 데이터 일괄 등록"""
    if 'file' not in request.files:
        return jsonify({"error": "파일이 없습니다."}), 400

    file = request.files['file']
    mapping_json = request.form.get('mapping')

    if not mapping_json:
        return jsonify({"error": "매핑 정보가 없습니다."}), 400

    try:
        mapping = json.loads(mapping_json)
        header_row = mapping.get('header_row', 1)
        col_mapping = mapping.get('mapping', {})

        from openpyxl import load_workbook
        wb = load_workbook(file)
        ws = wb.active

        imported = 0
        skipped = 0
        errors = []

        for i, row in enumerate(ws.iter_rows(values_only=True)):
            if i < header_row:  # 헤더 행까지 스킵
                continue

            row_data = list(row)

            # 이름 추출 (필수)
            name_idx = col_mapping.get('name')
            if name_idx is None or name_idx >= len(row_data) or not row_data[name_idx]:
                continue

            name = str(row_data[name_idx]).strip()
            if not name:
                continue

            # 중복 체크
            phone = None
            phone_idx = col_mapping.get('phone')
            if phone_idx is not None and phone_idx < len(row_data):
                phone = str(row_data[phone_idx]).strip() if row_data[phone_idx] else None

            existing = Member.query.filter_by(name=name, phone=phone).first()
            if existing:
                skipped += 1
                continue

            # 교인 생성
            member = Member(name=name, phone=phone, registration_date=get_seoul_today())

            # 나머지 필드 매핑
            for field in ['email', 'address', 'gender', 'notes']:
                idx = col_mapping.get(field)
                if idx is not None and idx < len(row_data) and row_data[idx]:
                    setattr(member, field, str(row_data[idx]).strip())

            # 날짜 필드 처리
            for date_field in ['birth_date', 'registration_date', 'baptism_date']:
                idx = col_mapping.get(date_field)
                if idx is not None and idx < len(row_data) and row_data[idx]:
                    try:
                        val = row_data[idx]
                        if isinstance(val, datetime):
                            setattr(member, date_field, val.date())
                        elif isinstance(val, date):
                            setattr(member, date_field, val)
                        elif isinstance(val, str):
                            # 다양한 날짜 형식 시도
                            for fmt in ['%Y-%m-%d', '%Y.%m.%d', '%Y/%m/%d', '%y-%m-%d', '%y.%m.%d']:
                                try:
                                    setattr(member, date_field, datetime.strptime(val.strip(), fmt).date())
                                    break
                                except:
                                    pass
                    except Exception as e:
                        pass

            # 상태 필드
            status_idx = col_mapping.get('status')
            if status_idx is not None and status_idx < len(row_data) and row_data[status_idx]:
                status_val = str(row_data[status_idx]).strip().lower()
                if '새신자' in status_val or 'new' in status_val:
                    member.status = 'newcomer'
                elif '비활동' in status_val or 'inactive' in status_val:
                    member.status = 'inactive'
                else:
                    member.status = 'active'

            try:
                db.session.add(member)
                db.session.commit()
                imported += 1
            except Exception as e:
                db.session.rollback()
                errors.append(f"행 {i+1}: {str(e)}")

        return jsonify({
            "success": True,
            "imported": imported,
            "skipped": skipped,
            "errors": errors[:10]  # 최대 10개 에러만
        })

    except Exception as e:
        return jsonify({"error": f"가져오기 중 오류: {str(e)}"}), 500


@app.route('/api/analyze-image', methods=['POST'])
def api_analyze_image():
    """이미지 분석 API - 명함/등록카드에서 정보 추출"""
    data = request.get_json()
    image_data = data.get('image')

    if not image_data:
        return jsonify({"error": "이미지가 없습니다."}), 400

    if not openai_client:
        return jsonify({"error": "OpenAI API 키가 설정되지 않았습니다."}), 500

    try:
        response = openai_client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "system",
                    "content": """이미지에서 사람 정보를 추출하세요.
명함, 교회 등록카드, 신분증 등에서 다음 정보를 찾아 JSON으로 반환하세요:

{
    "type": "namecard" | "registration_form" | "id_card" | "portrait" | "other",
    "extracted": {
        "name": "이름 (직분 포함, 예: 홍길동 집사)",
        "phone": "전화번호",
        "email": "이메일",
        "address": "주소",
        "birth_date": "생년월일 (YYYY-MM-DD 형식)",
        "gender": "남" | "여",
        "company": "소속/직장",
        "position": "직책",
        "registration_number": "등록번호",
        "previous_church": "이전교회/출석교회",
        "previous_church_address": "이전교회 주소",
        "district": "교구 (숫자만, 예: 1, 2, 3)",
        "cell_group": "속회",
        "mission_group": "선교회 (예: 14남선교회)",
        "barnabas": "바나바 (담당 장로/권사 이름)",
        "referrer": "인도자/관계 (예: 스스로, 지인소개)",
        "faith_level": "신급 (학습/세례/유아세례/입교 중 체크된 것)",
        "baptism_year": "세례연도",
        "baptism_church": "세례받은 교회",
        "registration_reason": "등록동기 (교회등록, 이사, 기타)",
        "notes": "기타 메모/특이사항 (여러 줄인 경우 모두 포함)"
    },
    "confidence": 0.9,
    "description": "이미지 설명"
}

찾을 수 없는 정보는 null로 설정하세요.
인물 사진만 있는 경우 type을 "portrait"로 설정하세요.
교회 등록 양식인 경우 모든 필드를 꼼꼼히 확인하세요."""
                },
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "이 이미지를 분석해주세요."},
                        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_data}"}}
                    ]
                }
            ],
            response_format={"type": "json_object"},
            max_tokens=1000
        )

        analysis = json.loads(response.choices[0].message.content)
        return jsonify({"success": True, "analysis": analysis})

    except Exception as e:
        return jsonify({"error": f"이미지 분석 중 오류: {str(e)}"}), 500


# =============================================================================
# 데이터베이스 마이그레이션
# =============================================================================

@app.route('/migrate-db')
def migrate_db():
    """데이터베이스 스키마 마이그레이션 (새 컬럼 추가)"""
    from sqlalchemy import text

    migrations = [
        # Member 테이블 새 컬럼들
        "ALTER TABLE members ADD COLUMN IF NOT EXISTS registration_number VARCHAR(20)",
        "ALTER TABLE members ADD COLUMN IF NOT EXISTS previous_church VARCHAR(100)",
        "ALTER TABLE members ADD COLUMN IF NOT EXISTS previous_church_address VARCHAR(200)",
        "ALTER TABLE members ADD COLUMN IF NOT EXISTS district VARCHAR(20)",
        "ALTER TABLE members ADD COLUMN IF NOT EXISTS cell_group VARCHAR(50)",
        "ALTER TABLE members ADD COLUMN IF NOT EXISTS mission_group VARCHAR(50)",
        "ALTER TABLE members ADD COLUMN IF NOT EXISTS barnabas VARCHAR(50)",
        "ALTER TABLE members ADD COLUMN IF NOT EXISTS referrer VARCHAR(50)",
        "ALTER TABLE members ADD COLUMN IF NOT EXISTS faith_level VARCHAR(20)",
        # Group 테이블 새 컬럼들 (계층 구조)
        "ALTER TABLE groups ADD COLUMN IF NOT EXISTS parent_id INTEGER REFERENCES groups(id)",
        "ALTER TABLE groups ADD COLUMN IF NOT EXISTS level INTEGER DEFAULT 0",
        "ALTER TABLE groups ADD COLUMN IF NOT EXISTS description VARCHAR(200)",
    ]

    results = []
    for sql in migrations:
        try:
            db.session.execute(text(sql))
            db.session.commit()
            results.append(f"OK: {sql[:50]}...")
        except Exception as e:
            db.session.rollback()
            results.append(f"SKIP: {sql[:50]}... ({str(e)[:50]})")

    return jsonify({
        "message": "마이그레이션 완료",
        "results": results
    })


@app.route('/seed-groups')
def seed_groups():
    """기본 그룹 계층 구조 생성"""
    created = []
    skipped = []

    # 상위 그룹 정의
    top_groups = [
        {"name": "교구", "type": "district", "desc": "교구별 조직"},
        {"name": "선교회", "type": "mission", "desc": "선교회 조직"},
        {"name": "직분", "type": "position", "desc": "직분별 분류"},
        {"name": "교회학교", "type": "school", "desc": "교회학교 조직"},
        {"name": "새가족", "type": "newcomer", "desc": "새가족 관리"},
    ]

    # 하위 그룹 정의
    sub_groups = {
        "교구": ["1교구", "2교구", "3교구", "미등록"],
        "선교회": ["남선교회", "여선교회"],
        "직분": ["목사", "장로", "권사", "집사", "성도"],
        "교회학교": ["청년부", "청소년부", "아동부", "유치부", "유아부"],
        "새가족": [],
    }

    # 상위 그룹 생성
    for tg in top_groups:
        existing = Group.query.filter_by(name=tg["name"], parent_id=None).first()
        if existing:
            skipped.append(tg["name"])
            parent = existing
        else:
            parent = Group(
                name=tg["name"],
                group_type=tg["type"],
                level=0,
                description=tg["desc"],
                parent_id=None
            )
            db.session.add(parent)
            db.session.flush()  # ID 생성
            created.append(tg["name"])

        # 하위 그룹 생성
        for sub_name in sub_groups.get(tg["name"], []):
            existing_sub = Group.query.filter_by(name=sub_name, parent_id=parent.id).first()
            if existing_sub:
                skipped.append(f"{tg['name']} > {sub_name}")
            else:
                sub = Group(
                    name=sub_name,
                    group_type=tg["type"],
                    level=1,
                    parent_id=parent.id
                )
                db.session.add(sub)
                created.append(f"{tg['name']} > {sub_name}")

    db.session.commit()

    return jsonify({
        "message": "그룹 시드 완료",
        "created": created,
        "skipped": skipped
    })


# =============================================================================
# REST API (외부 연동용)
# =============================================================================

@app.route('/api/members', methods=['GET'])
def api_list_members():
    """교인 목록 조회 API"""
    members = Member.query.all()
    return jsonify({
        "members": [_member_to_dict(m) for m in members],
        "total": len(members)
    })


@app.route('/api/members', methods=['POST'])
def api_create_member():
    """교인 등록 API (JSON)"""
    data = request.get_json()
    if not data:
        return jsonify({"error": "JSON 데이터가 필요합니다"}), 400

    if not data.get('name'):
        return jsonify({"error": "이름은 필수입니다"}), 400

    # 외부 ID 중복 체크
    if data.get('external_id'):
        existing = Member.query.filter_by(external_id=data['external_id']).first()
        if existing:
            return jsonify({
                "error": "이미 등록된 외부 ID입니다",
                "existing_id": existing.id
            }), 409

    member = Member(
        name=data.get('name'),
        phone=data.get('phone'),
        email=data.get('email'),
        address=data.get('address'),
        birth_date=_parse_date(data.get('birth_date')),
        gender=data.get('gender'),
        baptism_date=_parse_date(data.get('baptism_date')),
        registration_date=_parse_date(data.get('registration_date')) or get_seoul_today(),
        member_type=data.get('position') or data.get('member_type'),
        status=data.get('status', 'active'),
        notes=data.get('notes'),
        external_id=data.get('external_id'),
        photo_url=data.get('photo_url'),
    )

    db.session.add(member)
    db.session.commit()

    return jsonify({
        "success": True,
        "message": "교인이 등록되었습니다",
        "member": _member_to_dict(member)
    }), 201


@app.route('/api/members/<int:member_id>', methods=['GET'])
def api_get_member(member_id):
    """교인 상세 조회 API"""
    member = Member.query.get_or_404(member_id)
    return jsonify(_member_to_dict(member))


@app.route('/api/members/<int:member_id>', methods=['PUT'])
def api_update_member(member_id):
    """교인 수정 API (JSON)"""
    member = Member.query.get_or_404(member_id)
    data = request.get_json()
    if not data:
        return jsonify({"error": "JSON 데이터가 필요합니다"}), 400

    # 업데이트 가능한 필드들
    if 'name' in data:
        member.name = data['name']
    if 'phone' in data:
        member.phone = data['phone']
    if 'email' in data:
        member.email = data['email']
    if 'address' in data:
        member.address = data['address']
    if 'birth_date' in data:
        member.birth_date = _parse_date(data['birth_date'])
    if 'gender' in data:
        member.gender = data['gender']
    if 'baptism_date' in data:
        member.baptism_date = _parse_date(data['baptism_date'])
    if 'registration_date' in data:
        member.registration_date = _parse_date(data['registration_date'])
    if 'position' in data or 'member_type' in data:
        member.member_type = data.get('position') or data.get('member_type')
    if 'status' in data:
        member.status = data['status']
    if 'notes' in data:
        member.notes = data['notes']
    if 'external_id' in data:
        member.external_id = data['external_id']
    if 'photo_url' in data:
        member.photo_url = data['photo_url']

    db.session.commit()

    return jsonify({
        "success": True,
        "message": "교인 정보가 수정되었습니다",
        "member": _member_to_dict(member)
    })


@app.route('/api/members/by-external-id/<external_id>', methods=['GET'])
def api_get_member_by_external_id(external_id):
    """외부 ID로 교인 조회 API"""
    member = Member.query.filter_by(external_id=external_id).first()
    if not member:
        return jsonify({"error": "교인을 찾을 수 없습니다"}), 404
    return jsonify(_member_to_dict(member))


@app.route('/api/members/<int:member_id>/photo', methods=['POST'])
def api_upload_member_photo(member_id):
    """교인 사진 업로드 API (base64)"""
    member = Member.query.get_or_404(member_id)
    data = request.get_json()

    if not data or not data.get('photo'):
        return jsonify({"error": "photo (base64) 데이터가 필요합니다"}), 400

    try:
        photo_base64 = data['photo']

        # Cloudinary 사용 가능하면 업로드
        if cloudinary_configured:
            result = cloudinary.uploader.upload(
                f"data:image/jpeg;base64,{photo_base64}",
                folder="church-registry/members",
                public_id=f"member_{member_id}"
            )
            photo_url = result['secure_url']
        else:
            # 로컬 저장
            import base64 as b64
            photo_data = b64.b64decode(photo_base64)
            filename = f"member_{member_id}.jpg"
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            with open(filepath, 'wb') as f:
                f.write(photo_data)
            photo_url = f"/static/uploads/{filename}"

        member.photo_url = photo_url
        db.session.commit()

        return jsonify({
            "success": True,
            "photo_url": photo_url
        })

    except Exception as e:
        return jsonify({"error": f"사진 업로드 실패: {str(e)}"}), 500


@app.route('/api/members/bulk', methods=['POST'])
def api_bulk_create_members():
    """교인 일괄 등록 API"""
    data = request.get_json()
    if not data or not data.get('members'):
        return jsonify({"error": "members 배열이 필요합니다"}), 400

    results = {"created": 0, "updated": 0, "failed": 0, "errors": []}

    for member_data in data['members']:
        try:
            external_id = member_data.get('external_id')

            # 기존 회원 확인
            existing = None
            if external_id:
                existing = Member.query.filter_by(external_id=external_id).first()

            if existing:
                # 업데이트
                for key, value in member_data.items():
                    if key in ['birth_date', 'baptism_date', 'registration_date']:
                        value = _parse_date(value)
                    if hasattr(existing, key) and value:
                        setattr(existing, key, value)
                results["updated"] += 1
            else:
                # 새로 생성
                member = Member(
                    name=member_data.get('name'),
                    phone=member_data.get('phone'),
                    email=member_data.get('email'),
                    address=member_data.get('address'),
                    birth_date=_parse_date(member_data.get('birth_date')),
                    gender=member_data.get('gender'),
                    registration_date=_parse_date(member_data.get('registration_date')) or get_seoul_today(),
                    member_type=member_data.get('position') or member_data.get('member_type'),
                    status=member_data.get('status', 'active'),
                    notes=member_data.get('notes'),
                    external_id=member_data.get('external_id'),
                )
                db.session.add(member)
                results["created"] += 1

        except Exception as e:
            results["failed"] += 1
            results["errors"].append(f"{member_data.get('name', 'Unknown')}: {str(e)}")

    db.session.commit()

    return jsonify({
        "success": True,
        "results": results
    })


def _member_to_dict(member):
    """Member 객체를 딕셔너리로 변환"""
    return {
        "id": member.id,
        "name": member.name,
        "phone": member.phone,
        "email": member.email,
        "address": member.address,
        "birth_date": member.birth_date.isoformat() if member.birth_date else None,
        "gender": member.gender,
        "age": member.age,
        "baptism_date": member.baptism_date.isoformat() if member.baptism_date else None,
        "registration_date": member.registration_date.isoformat() if member.registration_date else None,
        "member_type": member.member_type,
        "status": member.status,
        "notes": member.notes,
        "external_id": member.external_id,
        "photo_url": member.photo_url,
        "created_at": member.created_at.isoformat() if member.created_at else None,
        "updated_at": member.updated_at.isoformat() if member.updated_at else None,
    }


def _parse_date(date_str):
    """날짜 문자열을 date 객체로 변환"""
    if not date_str:
        return None
    if isinstance(date_str, date):
        return date_str
    try:
        # 여러 형식 시도
        for fmt in ['%Y-%m-%d', '%Y/%m/%d', '%Y.%m.%d']:
            try:
                return datetime.strptime(date_str, fmt).date()
            except ValueError:
                continue
        return None
    except:
        return None


# =============================================================================
# god4u 연동 (양방향 동기화)
# =============================================================================

GOD4U_BASE_URL = "http://god4u.dimode.co.kr"
GOD4U_API_URL = f"{GOD4U_BASE_URL}/Handler/GetPersonListMobileJSon.asmx/GetPersonSearchListDefault"
GOD4U_UPDATE_URL = f"{GOD4U_BASE_URL}/WebMobile/WebChurch/PersonModifyDetailExecute.cshtml"
GOD4U_PHOTO_URL = f"{GOD4U_BASE_URL}/Handler/DisplayImage.ashx"


@app.route('/sync')
def sync_page():
    """동기화 페이지"""
    return render_template('sync.html')


@app.route('/api/sync/backup-god4u', methods=['POST'])
def api_backup_god4u():
    """god4u 데이터 백업 API - JSON 파일로 다운로드"""
    import time
    from flask import Response

    data = request.get_json() or {}
    cookies = data.get('cookies', {})

    if not cookies.get('ASP.NET_SessionId') or not cookies.get('pastorinfo'):
        return jsonify({"error": "god4u 쿠키가 필요합니다"}), 400

    try:
        session = requests.Session()
        session.cookies.update(cookies)

        headers = {
            "Content-Type": "application/json; charset=UTF-8",
            "Accept": "application/json, text/javascript, */*; q=0.01",
            "X-Requested-With": "XMLHttpRequest",
            "Origin": GOD4U_BASE_URL,
            "Referer": f"{GOD4U_BASE_URL}/WebMobile/WebChurch/RangeList.cshtml",
        }

        # 첫 페이지 조회
        payload = _create_god4u_payload(page=1, page_size=100)
        response = session.post(GOD4U_API_URL, json=payload, headers=headers, timeout=60)

        if response.status_code != 200:
            return jsonify({"error": f"god4u 연결 실패: {response.status_code}"}), 500

        result = response.json()
        if "d" in result:
            result = json.loads(result["d"])

        total_pages = int(result.get("totalpage", 1))
        all_persons = result.get("personInfo", [])

        # 모든 페이지 조회
        for page in range(2, total_pages + 1):
            time.sleep(0.3)
            payload = _create_god4u_payload(page=page, page_size=100)
            response = session.post(GOD4U_API_URL, json=payload, headers=headers, timeout=60)
            if response.status_code == 200:
                page_data = response.json()
                if "d" in page_data:
                    page_data = json.loads(page_data["d"])
                all_persons.extend(page_data.get("personInfo", []))

        # JSON 백업 파일 생성
        backup_data = {
            "backup_date": datetime.now().isoformat(),
            "total_count": len(all_persons),
            "source": "god4u.dimode.co.kr",
            "members": all_persons
        }

        json_str = json.dumps(backup_data, ensure_ascii=False, indent=2)

        return Response(
            json_str,
            mimetype='application/json',
            headers={'Content-Disposition': f'attachment;filename=god4u_backup_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'}
        )

    except Exception as e:
        return jsonify({"error": f"백업 실패: {str(e)}"}), 500


@app.route('/api/sync/god4u-to-registry', methods=['POST'])
def api_sync_god4u_to_registry():
    """god4u → church-registry 동기화 API"""
    import time

    data = request.get_json() or {}
    cookies = data.get('cookies', {})

    if not cookies.get('ASP.NET_SessionId') or not cookies.get('pastorinfo'):
        return jsonify({"error": "god4u 쿠키가 필요합니다 (ASP.NET_SessionId, pastorinfo)"}), 400

    try:
        session = requests.Session()
        session.cookies.update(cookies)

        results = {"created": 0, "updated": 0, "failed": 0, "total": 0}

        # 첫 페이지로 전체 개수 확인
        headers = {
            "Content-Type": "application/json; charset=UTF-8",
            "Accept": "application/json, text/javascript, */*; q=0.01",
            "X-Requested-With": "XMLHttpRequest",
            "Origin": GOD4U_BASE_URL,
            "Referer": f"{GOD4U_BASE_URL}/WebMobile/WebChurch/RangeList.cshtml",
        }

        payload = _create_god4u_payload(page=1, page_size=100)
        response = session.post(GOD4U_API_URL, json=payload, headers=headers, timeout=60)

        if response.status_code != 200:
            return jsonify({"error": f"god4u API 오류: {response.status_code}"}), 500

        data = response.json()
        if "d" in data:
            data = json.loads(data["d"])

        total_count = int(data.get("totalcount", 0))
        total_pages = int(data.get("totalpage", 1))
        results["total"] = total_count

        # 모든 페이지 크롤링 및 동기화
        all_persons = data.get("personInfo", [])

        for page in range(2, total_pages + 1):
            time.sleep(0.3)
            payload = _create_god4u_payload(page=page, page_size=100)
            response = session.post(GOD4U_API_URL, json=payload, headers=headers, timeout=60)
            if response.status_code == 200:
                page_data = response.json()
                if "d" in page_data:
                    page_data = json.loads(page_data["d"])
                all_persons.extend(page_data.get("personInfo", []))

        # church-registry에 저장
        for person in all_persons:
            try:
                external_id = person.get("id")
                existing = Member.query.filter_by(external_id=external_id).first() if external_id else None

                member_data = {
                    "name": person.get("name", ""),
                    "phone": person.get("handphone", "") or person.get("tel", ""),
                    "email": person.get("email", ""),
                    "address": person.get("addr", ""),
                    "birth_date": _parse_date(person.get("birth", "")),
                    "gender": "M" if person.get("sex") == "남" else "F" if person.get("sex") == "여" else None,
                    "registration_date": _parse_date(person.get("regday", "")),
                    "member_type": person.get("cvname1") or person.get("cvname", ""),
                    "status": "active" if person.get("state3") == "예배출석" else "inactive",
                    "external_id": external_id,
                    "notes": f"가족: {person.get('ran1', '')}\n차량: {person.get('carnum', '')}",
                }

                if existing:
                    for key, value in member_data.items():
                        if value is not None:
                            setattr(existing, key, value)
                    results["updated"] += 1
                else:
                    member = Member(**{k: v for k, v in member_data.items() if v is not None})
                    db.session.add(member)
                    results["created"] += 1

            except Exception as e:
                results["failed"] += 1

        db.session.commit()

        return jsonify({
            "success": True,
            "message": f"동기화 완료: {results['created']}명 생성, {results['updated']}명 업데이트",
            "results": results
        })

    except Exception as e:
        return jsonify({"error": f"동기화 실패: {str(e)}"}), 500


@app.route('/api/sync/registry-to-god4u', methods=['POST'])
def api_sync_registry_to_god4u():
    """church-registry → god4u 동기화 API"""
    import time

    data = request.get_json() or {}
    cookies = data.get('cookies', {})

    if not cookies.get('ASP.NET_SessionId') or not cookies.get('pastorinfo'):
        return jsonify({"error": "god4u 쿠키가 필요합니다"}), 400

    results = {"success": 0, "failed": 0, "skipped": 0}

    # external_id가 있는 회원만 동기화
    members = Member.query.filter(Member.external_id.isnot(None)).all()

    session = requests.Session()
    session.cookies.update(cookies)

    for member in members:
        try:
            success = _sync_member_to_god4u(session, member)
            if success:
                results["success"] += 1
            else:
                results["failed"] += 1
        except:
            results["failed"] += 1

        time.sleep(0.3)

    return jsonify({
        "success": True,
        "message": f"god4u 동기화 완료: {results['success']}명 성공",
        "results": results
    })


def _create_god4u_payload(page=1, page_size=100):
    """god4u API 페이로드 생성"""
    return {
        "paramName": "", "paramEName": "", "paramIds": "",
        "paramFree1": "", "paramFree2": "", "paramFree3": "", "paramFree4": "",
        "paramFree5": "", "paramFree6": "", "paramFree7": "", "paramFree8": "",
        "paramFree9": "", "paramFree10": "", "paramFree11": "", "paramFree12": "",
        "paramRange": "", "paramRange1": "", "paramRange2": "", "paramRange3": "",
        "paramRvname": "", "paramSection1": "", "paramSection2": "",
        "paramSection3": "", "paramSection4": "", "paramRvname2": "",
        "paramCoreChk": "", "paramCarNum": "", "paramGJeon": "",
        "paramLastSchool": "", "paramOffName": "", "paramGJeon1": "",
        "paramCvname": "", "paramCvname1": "", "paramState": "",
        "paramState1": "", "paramState3": "", "encryptOpt": "ALL",
        "rangeLimitUse": "false", "paramPage": str(page),
        "paramPageSize": str(page_size), "paramOrder": "NAME",
        "paramOrder2": "", "paramOrderAsc": "ASC", "paramOrder2Asc": "ASC",
        "paramPType": "P", "paramAddr": "", "paramRegDateS": "", "paramRegDateE": "",
    }


def _sync_member_to_god4u(session, member):
    """개별 회원을 god4u로 동기화"""
    if not member.external_id:
        return False

    # 주소 파싱
    address = member.address or ""
    parts = address.split() if address else []
    sido = parts[0] if len(parts) >= 1 else ""
    gugun = parts[1] if len(parts) >= 2 else ""
    dong = parts[2] if len(parts) >= 3 else ""
    bunji = " ".join(parts[3:]) if len(parts) >= 4 else ""

    gender = "남" if member.gender == "M" else "여" if member.gender == "F" else ""

    payload = {
        "mode": "mod",
        "hidIdM": member.external_id,
        "txtHidM": member.external_id,
        "txtNameM": member.name or "",
        "txtHandphoneM": member.phone or "",
        "txtTelM": "",
        "txtEmailM": member.email or "",
        "txtBirthDayM": member.birth_date.isoformat() if member.birth_date else "",
        "ddlGenderM": gender,
        "txtSidoM": sido,
        "txtGugunM": gugun,
        "txtDongM": dong,
        "txtBunjiM": bunji,
        "ddlState3": "예배출석" if member.status == "active" else "결석",
        "txtRegDayM": member.registration_date.isoformat() if member.registration_date else "",
        "hidcvname": member.member_type or "",
        "hidcvname1": "",
        "hidstate": "교인",
        "hidstate1": "장년",
        "hidRange": "", "hidRange1": "", "hidRange2": "", "hidRange3": "",
        "txtENameF": "", "txtENameM": "", "txtENameL": "",
        "ddlSolarM": "양", "txtAgeM": "",
        "txtCoreM": member.name or "",
        "ddlRelative": "본인",
        "txtZipcodeM": "", "txtZipcodeMOrg": "",
        "txtSidoMOrg": "", "txtGugunMOrg": "", "txtDongMOrg": "", "txtBunjiMOrg": "",
        "txtCityM": "", "txtStM": "", "txtCityMOrg": "", "txtStMOrg": "",
        "ddlGYear": "2026",
        "txtRangeOrg": "", "txtRange1Org": "", "txtRange2Org": "", "txtRange3Org": "",
        "ddlCvAct": "", "txtCvDay": "", "txtAppointChurch": "",
        "txtCvnameOrg": "", "txtCvname1Org": "", "txtCvActorg": "",
        "txtCvDayOrg": "", "txtAppointChurchOrg": "",
        "txtStateDay": "", "txtStateOrg": "교인", "txtState1Org": "장년",
        "txtState3Org": "예배출석", "txtStateDayOrg": "",
        "hidvaccinename": "", "hidvaccinenumber": "",
        "txtVaccineDate": "", "txtVaccineNameOrg": "", "txtVaccineNumberOrg": "",
        "txtVaccineDateOrg": "", "txtVaccineIndex": "0",
        "txtLeaderidM": "0", "txtLeaderM": "",
        "txtOffnameM": "", "txtOfftelM": "",
        "ddlGrade": "", "txtBaptday": "", "txtBaptchurch": "", "txtBaptist": "",
        "txtGradeOrg": "", "txtBaptdayOrg": "", "txtBaptchurchOrg": "", "txtBaptistOrg": "",
        "txtCarKind": "", "txtCarNum": "", "txtCarKind1": "", "txtCarNum1": "",
        "txPrechurchM": "", "txtEtcM": member.notes or "",
        "txtFree1": "", "txtFree2": "", "txtFree3": "", "txtFree4": "",
        "txtFree5": "", "txtFree6": "", "txtFree7": "", "txtFree8": "",
        "txtFree9": "", "txtFree10": "", "txtFree11": "", "txtFree12": "",
    }

    headers = {
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        "Accept": "text/html, */*; q=0.01",
        "X-Requested-With": "XMLHttpRequest",
        "Origin": GOD4U_BASE_URL,
        "Referer": f"{GOD4U_BASE_URL}/WebMobile/WebChurch/PersonModifyDetail.cshtml?id={member.external_id}",
    }

    try:
        response = session.post(GOD4U_UPDATE_URL, data=payload, headers=headers, timeout=30)
        return response.status_code == 200 and "정보수정 완료" in response.text
    except:
        return False


# =============================================================================
# 데이터베이스 초기화 및 마이그레이션
# =============================================================================

def run_migrations():
    """데이터베이스 스키마 마이그레이션 실행"""
    from sqlalchemy import text, inspect

    inspector = inspect(db.engine)

    # members 테이블 마이그레이션
    if 'members' in inspector.get_table_names():
        columns = [col['name'] for col in inspector.get_columns('members')]

        # external_id 컬럼 추가 (god4u 등 외부 시스템 연동용)
        if 'external_id' not in columns:
            db.session.execute(text(
                'ALTER TABLE members ADD COLUMN external_id VARCHAR(50)'
            ))
            print('[Migration] Added external_id column to members table')
            db.session.commit()

    # groups 테이블 마이그레이션
    if 'groups' in inspector.get_table_names():
        columns = [col['name'] for col in inspector.get_columns('groups')]

        # parent_id 컬럼 추가
        if 'parent_id' not in columns:
            db.session.execute(text(
                'ALTER TABLE groups ADD COLUMN parent_id INTEGER REFERENCES groups(id)'
            ))
            print('[Migration] Added parent_id column to groups table')

        # level 컬럼 추가
        if 'level' not in columns:
            db.session.execute(text(
                'ALTER TABLE groups ADD COLUMN level INTEGER DEFAULT 0'
            ))
            print('[Migration] Added level column to groups table')

        # description 컬럼 추가
        if 'description' not in columns:
            db.session.execute(text(
                'ALTER TABLE groups ADD COLUMN description VARCHAR(200)'
            ))
            print('[Migration] Added description column to groups table')

        db.session.commit()

with app.app_context():
    db.create_all()
    run_migrations()


if __name__ == '__main__':
    app.run(debug=True, port=5000)
