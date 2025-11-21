import os
import re
import json
import sqlite3
import hashlib
from flask import Flask, render_template, request, jsonify
from openai import OpenAI

app = Flask(__name__)

def get_client():
    key = (os.getenv("OPENAI_API_KEY") or "").strip()
    if not key:
        raise RuntimeError("OPENAI_API_KEY가 비어 있습니다.")
    # GPT-5 긴 처리 시간을 위한 타임아웃 설정 (10분)
    return OpenAI(api_key=key, timeout=600.0)

client = get_client()

# Database setup
DATABASE_URL = os.getenv('DATABASE_URL')
USE_POSTGRES = DATABASE_URL is not None

if USE_POSTGRES:
    # PostgreSQL 사용
    import psycopg2
    from psycopg2.extras import RealDictCursor

    # Render의 postgres:// URL을 postgresql://로 변경
    if DATABASE_URL.startswith('postgres://'):
        DATABASE_URL = DATABASE_URL.replace('postgres://', 'postgresql://', 1)

    def get_db_connection():
        """Create a PostgreSQL database connection"""
        conn = psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)
        return conn
else:
    # SQLite 사용 (로컬 개발용)
    DB_PATH = os.path.join(os.path.dirname(__file__), 'sermon_data.db')

    def get_db_connection():
        """Create a SQLite database connection"""
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        return conn

# DB 초기화
def init_db():
    """Initialize database tables"""
    conn = get_db_connection()
    cursor = conn.cursor()

    if USE_POSTGRES:
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS sermon_benchmark_analyses (
                id SERIAL PRIMARY KEY,
                sermon_text TEXT NOT NULL,
                sermon_hash VARCHAR(100) UNIQUE,
                reference VARCHAR(200),
                sermon_title TEXT,
                category VARCHAR(100),
                style_name VARCHAR(100),
                analysis_result TEXT NOT NULL,
                sermon_structure TEXT,
                theological_depth TEXT,
                application_elements TEXT,
                illustration_style TEXT,
                language_style TEXT,
                success_factors TEXT,
                ai_model VARCHAR(50) DEFAULT 'gpt-5',
                analysis_tokens INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_sermon_benchmark_category
            ON sermon_benchmark_analyses(category)
        ''')

        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_sermon_benchmark_style
            ON sermon_benchmark_analyses(style_name)
        ''')

        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_sermon_benchmark_created_at
            ON sermon_benchmark_analyses(created_at DESC)
        ''')

        # step1_analyses 테이블 생성
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS step1_analyses (
                id SERIAL PRIMARY KEY,
                reference VARCHAR(200) NOT NULL,
                sermon_text TEXT,
                analysis_text TEXT NOT NULL,
                analysis_hash VARCHAR(100) UNIQUE,
                category VARCHAR(100),
                style_name VARCHAR(100),
                step_name VARCHAR(100),
                quality_score INTEGER,
                theological_depth_score INTEGER,
                practical_application_score INTEGER,
                ai_model VARCHAR(50) DEFAULT 'gpt-5',
                analysis_tokens INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_step1_reference
            ON step1_analyses(reference)
        ''')

        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_step1_category
            ON step1_analyses(category)
        ''')

        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_step1_quality
            ON step1_analyses(quality_score DESC)
        ''')

        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_step1_created_at
            ON step1_analyses(created_at DESC)
        ''')
    else:
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS sermon_benchmark_analyses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sermon_text TEXT NOT NULL,
                sermon_hash TEXT UNIQUE,
                reference TEXT,
                sermon_title TEXT,
                category TEXT,
                style_name TEXT,
                analysis_result TEXT NOT NULL,
                sermon_structure TEXT,
                theological_depth TEXT,
                application_elements TEXT,
                illustration_style TEXT,
                language_style TEXT,
                success_factors TEXT,
                ai_model TEXT DEFAULT 'gpt-5',
                analysis_tokens INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_sermon_benchmark_category
            ON sermon_benchmark_analyses(category)
        ''')

        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_sermon_benchmark_style
            ON sermon_benchmark_analyses(style_name)
        ''')

        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_sermon_benchmark_created_at
            ON sermon_benchmark_analyses(created_at DESC)
        ''')

        # step1_analyses 테이블 생성
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS step1_analyses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                reference TEXT NOT NULL,
                sermon_text TEXT,
                analysis_text TEXT NOT NULL,
                analysis_hash TEXT UNIQUE,
                category TEXT,
                style_name TEXT,
                step_name TEXT,
                quality_score INTEGER,
                theological_depth_score INTEGER,
                practical_application_score INTEGER,
                ai_model TEXT DEFAULT 'gpt-5',
                analysis_tokens INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_step1_reference
            ON step1_analyses(reference)
        ''')

        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_step1_category
            ON step1_analyses(category)
        ''')

        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_step1_quality
            ON step1_analyses(quality_score DESC)
        ''')

        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_step1_created_at
            ON step1_analyses(created_at DESC)
        ''')

    conn.commit()
    conn.close()

# 앱 시작 시 DB 초기화
init_db()

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
    단계별 기본 system prompt 반환
    사용자의 guide를 최우선으로 따르도록 설계
    """
    step_lower = step_name.lower()

    # 제목 추천 단계
    if '제목' in step_name:
        return """당신은 설교 '제목 후보'만 제안하는 역할입니다.

CRITICAL RULES:
1. 반드시 한국어로만 응답하세요
2. 정확히 3개의 제목만 제시하세요
3. 각 제목은 한 줄로 작성하세요
4. 번호, 기호, 마크다운 사용 금지
5. 제목만 작성하고 설명 추가 금지

출력 형식 예시:
하나님의 약속을 믿는 믿음
약속의 땅을 향한 여정
아브라함의 신앙 결단"""

    # 모든 다른 단계 - 기본 역할만 명시
    else:
        return f"""당신은 설교 '초안 자료'만 준비하는 역할입니다.

현재 단계: {step_name}

기본 역할:
- 반드시 한국어로만 응답하세요
- 완성된 설교 문단이 아닌, 자료와 구조만 제공
- 사용자가 제공하는 세부 지침을 최우선으로 따름
- 지침이 없는 경우에만 일반적인 설교 자료 형식 사용

⚠️ 중요: 사용자의 세부 지침이 제공되면 그것을 절대적으로 우선하여 따라야 합니다."""

@app.route("/")
def home():
    return render_template("sermon.html")

@app.route("/sermon")
def sermon():
    return render_template("sermon.html")

@app.route("/health")
def health():
    return jsonify({"ok": True})

# ===== 처리 단계 실행 API (gpt-4o-mini) =====
@app.route("/api/sermon/process", methods=["POST"])
def api_process_step():
    """단일 처리 단계 실행 (gpt-4o-mini 사용)"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"ok": False, "error": "No data received"}), 400
        
        category = data.get("category", "")
        step_id = data.get("stepId", "")
        step_name = data.get("stepName", "")
        step_type = data.get("stepType", "step1")
        reference = data.get("reference", "")
        title = data.get("title", "")
        text = data.get("text", "")
        guide = data.get("guide", "")
        master_guide = data.get("masterGuide", "")
        previous_results = data.get("previousResults", {})

        # 프론트엔드에서 전달받은 모델 사용 (없으면 기본값)
        model_name = data.get("model")
        if not model_name:
            # 기본값: stepType 기반 모델 선택
            if step_type == "step1":
                model_name = "gpt-5"
            else:  # step2
                model_name = "gpt-4o-mini"

        # temperature 설정 (gpt-4o-mini만 사용)
        use_temperature = (model_name == "gpt-4o-mini")

        print(f"[PROCESS] {category} - {step_name} (Step: {step_type}, 모델: {model_name})")

        # 시스템 메시지 구성 (단계별 최적화)
        system_content = get_system_prompt_for_step(step_name)

        # 총괄 지침이 있으면 추가
        if master_guide:
            system_content += f"\n\n【 카테고리 총괄 지침 】\n{master_guide}\n\n"
            system_content += f"【 현재 단계 역할 】\n{step_name}\n\n"
            system_content += "위 총괄 지침을 참고하여, 현재 단계의 역할과 비중에 맞게 '자료만' 작성하세요."

        # ★ 중요: 단계별 세부 지침을 시스템 프롬프트에 포함 (최우선 지침)
        if guide:
            system_content += f"\n\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            system_content += f"【 최우선 지침: {step_name} 단계 세부 지침 】\n"
            system_content += f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            system_content += guide
            system_content += f"\n\n위 지침을 절대적으로 우선하여 따라야 합니다."
            system_content += f"\n이 지침이 기본 역할과 충돌하면, 이 지침을 따르세요."

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

        # 제목 추천 단계 특별 처리
        if '제목' in step_name:
            user_content += f"위 성경 본문({reference})에 적합한 설교 제목을 정확히 3개만 제안해주세요.\n"
            user_content += "각 제목은 한 줄로, 번호나 기호 없이 작성하세요."
        else:
            user_content += f"위 내용을 바탕으로 '{step_name}' 단계를 작성해주세요.\n"

        if title and '제목' not in step_name:
            user_content += f"\n제목 '{title}'을 고려하여 작성하세요."

        # GPT 호출 (모델 동적 선택)
        # JSON 형식 강제하지 않음 - guide에 따라 자유롭게 출력
        if use_temperature:
            completion = client.chat.completions.create(
                model=model_name,
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
            )
        else:
            completion = client.chat.completions.create(
                model=model_name,
                messages=[
                    {
                        "role": "system",
                        "content": system_content
                    },
                    {
                        "role": "user",
                        "content": user_content
                    }
                ]
            )

        result = completion.choices[0].message.content.strip()

        # 제목 추천 단계는 JSON 파싱하지 않고 그대로 반환
        if '제목' in step_name:
            result = remove_markdown(result)
            return jsonify({"ok": True, "result": result})

        # JSON 파싱 시도 (선택적)
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

            print(f"[PROCESS][SUCCESS] JSON 형식으로 응답받아 포맷팅 완료")

            # Step1인 경우 백그라운드로 DB 저장
            if step_type == "step1" or step_id == "step1":
                try:
                    import threading
                    save_thread = threading.Thread(
                        target=save_step1_analysis,
                        args=(reference, text, formatted_result, category, data.get("styleName", ""), step_id)
                    )
                    save_thread.daemon = True
                    save_thread.start()
                    print(f"[PROCESS] Step1 분석 저장 백그라운드 시작")
                except Exception as e:
                    print(f"[PROCESS] Step1 저장 시작 실패 (무시): {str(e)}")

            return jsonify({"ok": True, "result": formatted_result})

        except json.JSONDecodeError as je:
            # JSON 파싱 실패 시 원본 텍스트를 반환 (정상 처리)
            # guide에서 텍스트 형식을 요구했을 수 있으므로 오류가 아님
            print(f"[PROCESS][INFO] 텍스트 형식으로 응답받음 (JSON 아님)")
            result = remove_markdown(result)

            # Step1인 경우 백그라운드로 DB 저장
            if step_type == "step1" or step_id == "step1":
                try:
                    import threading
                    save_thread = threading.Thread(
                        target=save_step1_analysis,
                        args=(reference, text, result, category, data.get("styleName", ""), step_id)
                    )
                    save_thread.daemon = True
                    save_thread.start()
                    print(f"[PROCESS] Step1 분석 저장 백그라운드 시작")
                except Exception as e:
                    print(f"[PROCESS] Step1 저장 시작 실패 (무시): {str(e)}")

            return jsonify({"ok": True, "result": result})
        
    except Exception as e:
        print(f"[PROCESS][ERROR] {str(e)}")
        return jsonify({"ok": False, "error": str(e)}), 200


# ===== GPT PRO 처리 API (gpt-5.1) =====
@app.route("/api/sermon/gpt-pro", methods=["POST"])
def api_gpt_pro():
    """GPT PRO 완성본 작성"""
    try:
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
        completed_step_names = data.get("completedStepNames", [])

        # 프론트엔드에서 전달받은 모델 사용 (없으면 기본값 gpt-5.1)
        gpt_pro_model = data.get("model", "gpt-5.1")

        print(f"[GPT-PRO] 처리 시작 - 스타일: {style_name}, 모델: {gpt_pro_model}")

        # 제목 생성 여부 확인
        has_title = bool(title and title.strip())

        # GPT-5.1 시스템 프롬프트 (스타일 동적 적용)
        system_content = (
            "당신은 GPT-5.1 기반의 한국어 설교 전문가입니다."
            " 자료는 참고용으로만 활용하고 문장은 처음부터 새로 구성하며,"
            " 묵직하고 명료한 어조로 신학적 통찰과 실제적 적용을 균형 있게 제시하세요."
            " 마크다운 기호 대신 순수 텍스트만 사용합니다."
        )

        # 제목이 없으면 GPT가 생성하도록 지시
        if not has_title:
            system_content += (
                "\n\n⚠️ 제목 생성: 설교문 맨 앞에 '설교 제목: (제목 내용)' 형식으로 적절한 제목을 먼저 생성하세요."
                "\n그 다음 빈 줄을 넣고 바로 설교 내용(서론, 본론, 결론)을 시작하세요. 본문 성경구절은 출력하지 마세요."
            )
        else:
            system_content += "\n\n⚠️ 중요: 설교 제목과 본문 성경구절은 다시 출력하지 마세요. 바로 설교 내용(서론, 본론, 결론)부터 시작하세요."

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
                "6. 가독성을 위해 각 단계 사이에 빈 줄을 넣으세요.\n"
                "7. 마크다운, 불릿 기호 대신 순수 텍스트 단락을 사용하고, 중복되는 문장은 피하세요."
            )
        elif is_three_point:
            # 3대지 설교 스타일
            user_content += (
                "1. 3대지 구조로 설교문을 작성하세요:\n"
                "   - 서론: 본문 배경과 주요 메시지 소개 (넘버링 없이 '서론'이라고만)\n"
                "   - 본론: 1대지, 2대지, 3대지 (각 대지는 '1.', '2.', '3.' 형식으로 넘버링)\n"
                "   - 결론: 실천과 적용 (넘버링 없이 '결론'이라고만)\n"
                "2. 각 대지 형식:\n"
                "   - 대지 제목: '1. 하나님의 말씀을 다시 붙들라' 형식으로 작성\n"
                "   - 소대지 2개를 포함하여 주제를 전개\n"
                "   - 관련 성경구절 2개를 인용구 형태로 제시\n"
                "   - 역사적 배경과 오늘의 적용을 연결\n"
                "3. 결론에서는 이번 주 실천 사항과 기도 제목을 제시하세요.\n"
                "4. 가독성을 위해 각 섹션(서론, 대지, 결론) 사이에 빈 줄을 넣으세요.\n"
                "5. 마크다운, 불릿 기호 대신 순수 텍스트 단락을 사용하고, 중복되는 문장은 피하세요."
            )
        else:
            # 기본 설교 스타일 - 처리 단계 구조 따르기
            user_content += "1. 제공된 설교 스타일에 맞춰 설교문을 작성하세요.\n"

            # 완료된 처리 단계 정보 활용
            if completed_step_names and len(completed_step_names) > 0:
                steps_list = "', '".join(completed_step_names)
                user_content += (
                    f"2. 위 초안 자료는 '{steps_list}' 단계로 구성되어 있습니다.\n"
                    "   이 단계들의 분석 내용과 구조를 반영하여 설교문을 전개하세요.\n"
                )
            else:
                user_content += "2. 초안 자료의 분석 내용과 구조를 반영하여 설교문을 전개하세요.\n"

            user_content += (
                "3. 핵심 메시지를 전개하고, 관련 성경구절을 적절히 인용하세요.\n"
                "4. 역사적 배경, 신학적 통찰, 실제 적용을 균형 있게 제시하세요.\n"
                "5. 결론 부분에서는 실천 사항과 기도 제목을 제시하세요.\n"
                "6. 가독성을 위해 각 섹션 사이에 빈 줄을 넣으세요.\n"
                "7. 마크다운, 불릿 기호 대신 순수 텍스트 단락을 사용하고, 중복되는 문장은 피하세요."
            )

        # 공통 지침 추가
        user_content += "\n\n⚠️ 중요: 충분히 길고 상세하며 풍성한 내용으로 작성해주세요 (최대 16000 토큰)."

        # 모델에 따라 적절한 API 호출
        if gpt_pro_model == "gpt-5.1":
            # Responses API (gpt-5.1 전용)
            completion = client.responses.create(
                model=gpt_pro_model,
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
                max_output_tokens=16000
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
        else:
            # Chat Completions API (gpt-5, gpt-4o 등)
            completion = client.chat.completions.create(
                model=gpt_pro_model,
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
                temperature=0.8,
                max_tokens=16000
            )
            result = completion.choices[0].message.content.strip()

        if not result:
            raise RuntimeError(f"{gpt_pro_model} API로부터 결과를 받지 못했습니다.")

        # 마크다운 제거
        result = remove_markdown(result)

        # 결과 앞에 제목과 본문 추가
        final_result = ""

        # 제목 처리
        if has_title:
            # 사용자가 입력한 제목 사용
            final_result += f"설교 제목: {title}\n\n"
            # 본문 추가
            if reference:
                final_result += f"본문: {reference}\n\n"
            # GPT 결과 (제목 없이)
            final_result += result
        else:
            # GPT가 생성한 제목 포함된 결과 그대로 사용
            # 본문만 추가
            if reference:
                # GPT 결과 앞에 본문 삽입
                final_result += f"본문: {reference}\n\n"
            final_result += result

        print(f"[GPT-PRO] 완료")

        # 설교문 자동 분석 및 DB 저장 (백그라운드 처리 - 실패해도 사용자에게 영향 없음)
        try:
            # 제목 추출 (GPT가 생성한 경우)
            extracted_title = title if has_title else ""
            if not has_title and "설교 제목:" in final_result:
                # GPT가 생성한 제목 추출
                lines = final_result.split('\n')
                for line in lines:
                    if line.startswith("설교 제목:"):
                        extracted_title = line.replace("설교 제목:", "").strip()
                        break

            # 비동기적으로 분석 수행 (실패해도 무시)
            import threading
            analysis_thread = threading.Thread(
                target=analyze_sermon_for_benchmark,
                args=(final_result, reference, extracted_title, category, style_name)
            )
            analysis_thread.daemon = True  # 메인 프로세스 종료 시 함께 종료
            analysis_thread.start()
            print(f"[GPT-PRO] 벤치마크 분석 백그라운드 시작")
        except Exception as e:
            print(f"[GPT-PRO] 벤치마크 분석 시작 실패 (무시): {str(e)}")

        return jsonify({"ok": True, "result": final_result})

    except Exception as e:
        print(f"[GPT-PRO][ERROR] {str(e)}")
        return jsonify({"ok": False, "error": str(e)}), 200


@app.route("/api/sermon/qa", methods=["POST"])
def api_sermon_qa():
    """설교 준비 Q&A - 처리 단계 결과와 본문을 기반으로 질문에 답변"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"ok": False, "error": "No data received"}), 400

        question = data.get("question", "")
        reference = data.get("reference", "")
        step_results = data.get("stepResults", {})

        if not question:
            return jsonify({"ok": False, "error": "질문이 비어있습니다"}), 400

        print(f"[Q&A] 질문: {question}")

        # 시스템 메시지: Q&A 역할 정의
        system_content = """당신은 설교 준비를 돕는 성경 연구 도우미입니다.

당신의 역할:
- 사용자가 현재 준비 중인 성경 본문과 관련된 질문에 답변합니다
- 제공된 처리 단계 결과(배경 지식, 본문 분석, 개요 등)를 참고하여 답변합니다
- 질문이 모호한 경우, 현재 맥락(성경 본문, 처리 단계)을 기준으로 이해하고 답변합니다
- 간단하고 명확하게 답변하되, 필요시 성경적 배경이나 신학적 설명을 추가합니다

답변 원칙:
- 친절하고 이해하기 쉬운 톤으로 작성
- 불확실한 경우 "정확하지 않을 수 있습니다"라고 명시
- 필요시 관련 성경 구절이나 역사적 배경 언급"""

        # 사용자 메시지: 컨텍스트 + 질문
        user_content = ""

        # 성경 본문 정보
        if reference:
            user_content += f"【 현재 준비 중인 성경 본문 】\n{reference}\n\n"

        # 처리 단계 결과들
        if step_results:
            user_content += "【 처리 단계 결과 】\n"
            for step_id, step_data in step_results.items():
                step_name = step_data.get("name", "")
                step_result = step_data.get("result", "")
                if step_result:
                    user_content += f"\n### {step_name}\n{step_result}\n"
            user_content += "\n"

        # 사용자 질문
        user_content += f"【 사용자 질문 】\n{question}\n\n"
        user_content += "위 맥락을 참고하여 질문에 답변해주세요."

        # GPT 호출 (gpt-4o-mini)
        completion = client.chat.completions.create(
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
            temperature=0.7
        )

        answer = completion.choices[0].message.content

        print(f"[Q&A] 답변 완료")

        return jsonify({"ok": True, "answer": answer})

    except Exception as e:
        print(f"[Q&A][ERROR] {str(e)}")
        return jsonify({"ok": False, "error": str(e)}), 200


# ===== 설교문 벤치마크 분석 함수 =====
def analyze_sermon_for_benchmark(sermon_text, reference="", sermon_title="", category="", style_name=""):
    """
    생성된 설교문을 자동으로 분석하여 DB에 저장

    Args:
        sermon_text: 생성된 설교문 텍스트
        reference: 본문 성경구절
        sermon_title: 설교 제목
        category: 카테고리 (설교 유형)
        style_name: 설교 스타일

    Returns:
        dict: {"ok": True/False, "message": "..."}
    """
    try:
        # 설교문 해시 생성 (중복 체크용)
        sermon_hash = hashlib.md5(sermon_text.encode('utf-8')).hexdigest()

        # DB 기반 중복 체크
        is_duplicate = False
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            if USE_POSTGRES:
                cursor.execute("SELECT id FROM sermon_benchmark_analyses WHERE sermon_hash = %s", (sermon_hash,))
            else:
                cursor.execute("SELECT id FROM sermon_benchmark_analyses WHERE sermon_hash = ?", (sermon_hash,))
            existing = cursor.fetchone()
            conn.close()

            if existing:
                is_duplicate = True
                print(f"[SERMON-BENCHMARK] 중복 설교문 감지 (해시: {sermon_hash[:8]}...) - 분석 건너뜀")
                return {"ok": True, "message": "중복 설교문 - 분석 건너뜀", "isDuplicate": True}
        except Exception as e:
            print(f"[SERMON-BENCHMARK] 중복 체크 실패: {str(e)}")

        print(f"[SERMON-BENCHMARK] 설교문 분석 시작 - 스타일: {style_name}, 카테고리: {category}")

        # GPT로 설교문 분석
        system_content = """당신은 설교문 분석 전문가입니다.

제공된 설교문을 분석하여 다음 요소들을 추출하고 정리하세요:

1. **설교 구조 분석**
   - 서론, 본론, 결론의 구성 방식
   - 각 파트의 비중과 전환 흐름
   - 대지 구조 (있는 경우)

2. **신학적 깊이**
   - 성경 해석의 정확성과 깊이
   - 신학적 통찰의 수준
   - 복음 중심성

3. **적용 요소**
   - 실천 가능한 적용의 구체성
   - 청중 맥락에 대한 이해
   - 실생활 연결성

4. **예화 및 스토리텔링**
   - 예화 사용 방식과 효과
   - 스토리텔링 기법
   - 감정적 공감 유도 방법

5. **언어 스타일**
   - 문체와 어조
   - 문장 구조와 리듬
   - 명확성과 설득력

6. **성공 요인 분석**
   - 전반적인 설교의 강점
   - 청중 몰입 요소
   - 차별화 포인트

분석 결과는 구조화되고 명확하게 작성하세요."""

        user_content = f"""[설교문 정보]
- 본문 성경구절: {reference}
- 설교 제목: {sermon_title}
- 카테고리: {category}
- 스타일: {style_name}

[설교문 내용]
{sermon_text}

위 설교문을 분석하여 핵심 패턴과 성공 요인을 추출해주세요."""

        completion = client.chat.completions.create(
            model="gpt-5",
            messages=[
                {"role": "system", "content": system_content},
                {"role": "user", "content": user_content}
            ]
        )

        analysis = completion.choices[0].message.content.strip()
        total_tokens = completion.usage.total_tokens if hasattr(completion, 'usage') else 0

        # 분석 결과를 섹션별로 파싱
        sermon_structure = ""
        theological_depth = ""
        application_elements = ""
        illustration_style = ""
        language_style = ""
        success_factors = ""

        # 섹션별 추출 (간단한 패턴 매칭)
        sections = analysis.split('\n\n')
        for section in sections:
            if '설교 구조' in section or '구조 분석' in section:
                sermon_structure = section
            elif '신학적 깊이' in section or '신학' in section:
                theological_depth = section
            elif '적용' in section:
                application_elements = section
            elif '예화' in section or '스토리텔링' in section:
                illustration_style = section
            elif '언어' in section or '스타일' in section:
                language_style = section
            elif '성공 요인' in section:
                success_factors = section

        # DB에 저장
        try:
            conn = get_db_connection()
            cursor = conn.cursor()

            if USE_POSTGRES:
                cursor.execute('''
                    INSERT INTO sermon_benchmark_analyses
                    (sermon_text, sermon_hash, reference, sermon_title, category, style_name,
                     analysis_result, sermon_structure, theological_depth, application_elements,
                     illustration_style, language_style, success_factors, ai_model, analysis_tokens)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ''', (sermon_text, sermon_hash, reference, sermon_title, category, style_name,
                      analysis, sermon_structure, theological_depth, application_elements,
                      illustration_style, language_style, success_factors, 'gpt-5', total_tokens))
            else:
                cursor.execute('''
                    INSERT INTO sermon_benchmark_analyses
                    (sermon_text, sermon_hash, reference, sermon_title, category, style_name,
                     analysis_result, sermon_structure, theological_depth, application_elements,
                     illustration_style, language_style, success_factors, ai_model, analysis_tokens)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (sermon_text, sermon_hash, reference, sermon_title, category, style_name,
                      analysis, sermon_structure, theological_depth, application_elements,
                      illustration_style, language_style, success_factors, 'gpt-5', total_tokens))

            conn.commit()
            conn.close()
            print(f"[SERMON-BENCHMARK] DB 저장 완료 (해시: {sermon_hash[:8]}..., 토큰: {total_tokens})")
        except Exception as e:
            print(f"[SERMON-BENCHMARK] DB 저장 실패: {str(e)}")

        print(f"[SERMON-BENCHMARK] 분석 완료 - 모델: gpt-5")

        return {"ok": True, "message": "분석 완료 및 DB 저장됨", "isDuplicate": False}

    except Exception as e:
        print(f"[SERMON-BENCHMARK][ERROR] {str(e)}")
        return {"ok": False, "message": f"분석 실패: {str(e)}"}


# ===== Step1 분석 자동 저장 함수 =====
def save_step1_analysis(reference, sermon_text, analysis_text, category="", style_name="", step_name="step1"):
    """
    Step1 본문 분석 결과를 자동으로 DB에 저장

    Args:
        reference: 성경 본문 구절
        sermon_text: 성경 본문 텍스트
        analysis_text: 분석 결과 텍스트
        category: 카테고리
        style_name: 설교 스타일
        step_name: 단계 이름 (기본값: step1)

    Returns:
        dict: {"ok": True/False, "message": "..."}
    """
    try:
        # 분석 해시 생성 (중복 체크용 - reference + analysis_text 조합)
        hash_content = f"{reference}|{analysis_text}"
        analysis_hash = hashlib.md5(hash_content.encode('utf-8')).hexdigest()

        # DB 기반 중복 체크
        is_duplicate = False
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            if USE_POSTGRES:
                cursor.execute("SELECT id FROM step1_analyses WHERE analysis_hash = %s", (analysis_hash,))
            else:
                cursor.execute("SELECT id FROM step1_analyses WHERE analysis_hash = ?", (analysis_hash,))
            existing = cursor.fetchone()
            conn.close()

            if existing:
                is_duplicate = True
                print(f"[STEP1-SAVE] 중복 분석 감지 (해시: {analysis_hash[:8]}...) - 저장 건너뜀")
                return {"ok": True, "message": "중복 분석 - 저장 건너뜀", "isDuplicate": True}
        except Exception as e:
            print(f"[STEP1-SAVE] 중복 체크 실패: {str(e)}")

        print(f"[STEP1-SAVE] Step1 분석 저장 시작 - 본문: {reference[:30]}...")

        # GPT-5로 분석 품질 평가
        evaluation_system = """당신은 성경 본문 분석 평가 전문가입니다.

제공된 성경 본문 분석을 평가하여 다음 3가지 점수를 10점 만점으로 매기세요:

1. **전체 품질 (quality_score)**: 분석의 전반적인 완성도와 유용성
2. **신학적 깊이 (theological_depth_score)**: 신학적 통찰과 해석의 깊이
3. **실천 적용성 (practical_application_score)**: 실제 설교에 적용 가능한 정도

각 점수는 1-10 사이의 정수로 제시하세요.
JSON 형식으로 응답하세요: {"quality": 8, "theological_depth": 9, "practical_application": 7}"""

        evaluation_user = f"""[성경 구절]
{reference}

[분석 내용]
{analysis_text[:2000]}

위 분석의 품질을 평가해주세요."""

        try:
            eval_completion = client.chat.completions.create(
                model="gpt-4o-mini",  # 빠른 평가를 위해 mini 사용
                messages=[
                    {"role": "system", "content": evaluation_system},
                    {"role": "user", "content": evaluation_user}
                ],
                temperature=0.3
            )

            eval_result = eval_completion.choices[0].message.content.strip()
            # JSON 파싱
            import json
            # ```json 태그 제거
            if '```json' in eval_result:
                eval_result = eval_result.split('```json')[1].split('```')[0].strip()
            elif '```' in eval_result:
                eval_result = eval_result.split('```')[1].split('```')[0].strip()

            scores = json.loads(eval_result)
            quality_score = scores.get("quality", 5)
            theological_depth_score = scores.get("theological_depth", 5)
            practical_application_score = scores.get("practical_application", 5)

            print(f"[STEP1-SAVE] 평가 완료 - 품질:{quality_score}, 신학:{theological_depth_score}, 적용:{practical_application_score}")
        except Exception as e:
            print(f"[STEP1-SAVE] 품질 평가 실패 (기본값 사용): {str(e)}")
            quality_score = 5
            theological_depth_score = 5
            practical_application_score = 5

        # DB에 저장
        try:
            conn = get_db_connection()
            cursor = conn.cursor()

            # 토큰 수는 대략적으로 계산 (영어는 4자당 1토큰, 한글은 2자당 1토큰 정도)
            estimated_tokens = len(analysis_text) // 3

            if USE_POSTGRES:
                cursor.execute('''
                    INSERT INTO step1_analyses
                    (reference, sermon_text, analysis_text, analysis_hash, category, style_name, step_name,
                     quality_score, theological_depth_score, practical_application_score, ai_model, analysis_tokens)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ''', (reference, sermon_text, analysis_text, analysis_hash, category, style_name, step_name,
                      quality_score, theological_depth_score, practical_application_score, 'gpt-5', estimated_tokens))
            else:
                cursor.execute('''
                    INSERT INTO step1_analyses
                    (reference, sermon_text, analysis_text, analysis_hash, category, style_name, step_name,
                     quality_score, theological_depth_score, practical_application_score, ai_model, analysis_tokens)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (reference, sermon_text, analysis_text, analysis_hash, category, style_name, step_name,
                      quality_score, theological_depth_score, practical_application_score, 'gpt-5', estimated_tokens))

            conn.commit()
            conn.close()
            print(f"[STEP1-SAVE] DB 저장 완료 (해시: {analysis_hash[:8]}...)")
        except Exception as e:
            print(f"[STEP1-SAVE] DB 저장 실패: {str(e)}")

        return {"ok": True, "message": "Step1 분석 저장 완료", "isDuplicate": False}

    except Exception as e:
        print(f"[STEP1-SAVE][ERROR] {str(e)}")
        return {"ok": False, "message": f"저장 실패: {str(e)}"}


# ===== Render 배포를 위한 설정 =====
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5058))
    app.run(host="0.0.0.0", port=port, debug=False)
