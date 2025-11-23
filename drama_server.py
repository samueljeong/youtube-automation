import os
import re
import json
import sqlite3
from flask import Flask, render_template, request, jsonify
from openai import OpenAI

app = Flask(__name__)

def get_client():
    key = (os.getenv("OPENAI_API_KEY") or "").strip()
    if not key:
        raise RuntimeError("OPENAI_API_KEY가 비어 있습니다.")
    return OpenAI(api_key=key)

client = get_client()

# OpenRouter 클라이언트 (Step3 Claude용)
def get_openrouter_client():
    key = (os.getenv("OPENROUTER_API_KEY") or "").strip()
    if not key:
        print("[OPENROUTER] API 키가 설정되지 않았습니다.")
        return None
    try:
        return OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=key
        )
    except Exception as e:
        print(f"[OPENROUTER] 클라이언트 초기화 실패: {e}")
        return None

openrouter_client = get_openrouter_client()

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
    DB_PATH = os.path.join(os.path.dirname(__file__), 'drama_data.db')

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
            CREATE TABLE IF NOT EXISTS benchmark_analyses (
                id SERIAL PRIMARY KEY,
                script_text TEXT NOT NULL,
                script_hash VARCHAR(100) UNIQUE,
                upload_date VARCHAR(50),
                view_count INTEGER,
                category VARCHAR(100),
                analysis_result TEXT NOT NULL,
                story_structure TEXT,
                character_elements TEXT,
                dialogue_style TEXT,
                success_factors TEXT,
                ai_model VARCHAR(50) DEFAULT 'gpt-5',
                analysis_tokens INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_benchmark_view_count
            ON benchmark_analyses(view_count DESC)
        ''')
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_benchmark_created_at
            ON benchmark_analyses(created_at DESC)
        ''')
    else:
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS benchmark_analyses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                script_text TEXT NOT NULL,
                script_hash TEXT UNIQUE,
                upload_date TEXT,
                view_count INTEGER,
                category TEXT,
                analysis_result TEXT NOT NULL,
                story_structure TEXT,
                character_elements TEXT,
                dialogue_style TEXT,
                success_factors TEXT,
                ai_model TEXT DEFAULT 'gpt-5',
                analysis_tokens INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_benchmark_view_count
            ON benchmark_analyses(view_count DESC)
        ''')
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_benchmark_created_at
            ON benchmark_analyses(created_at DESC)
        ''')

    conn.commit()
    cursor.close()
    conn.close()
    print("[DRAMA-DB] Database initialized")

# 앱 시작 시 DB 초기화
init_db()

# ===== DB 가이드 조회 함수 =====
def get_relevant_guide_from_db(box_name, category="", limit=5):
    """
    Step 박스 이름에 따라 DB에서 관련 가이드를 가져옴

    Args:
        box_name: Step 박스 이름 (예: "캐릭터 설정", "스토리 구성")
        category: 영상 시간/카테고리 (선택적)
        limit: 가져올 분석 결과 개수

    Returns:
        str: 관련 가이드 텍스트
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Step 타입에 따른 필드 매핑
        field_mapping = {
            '캐릭터': 'character_elements',
            '인물': 'character_elements',
            '스토리': 'story_structure',
            '줄거리': 'story_structure',
            '구성': 'story_structure',
            '대사': 'dialogue_style',
            '분석': 'analysis_result',
            '성공': 'success_factors'
        }

        # box_name에서 해당하는 필드 찾기
        target_field = 'analysis_result'  # 기본값
        for keyword, field in field_mapping.items():
            if keyword in box_name:
                target_field = field
                break

        # 고조회수 대본들의 분석 결과 조회
        if USE_POSTGRES:
            query = f"""
                SELECT {target_field}, view_count, upload_date
                FROM benchmark_analyses
                WHERE {target_field} IS NOT NULL AND {target_field} != ''
                ORDER BY view_count DESC
                LIMIT %s
            """
            cursor.execute(query, (limit,))
        else:
            query = f"""
                SELECT {target_field}, view_count, upload_date
                FROM benchmark_analyses
                WHERE {target_field} IS NOT NULL AND {target_field} != ''
                ORDER BY view_count DESC
                LIMIT ?
            """
            cursor.execute(query, (limit,))

        results = cursor.fetchall()
        conn.close()

        if not results:
            print(f"[DRAMA-DB-GUIDE] DB에 축적된 데이터 없음 (필드: {target_field})")
            return None

        # 결과를 가이드 형식으로 포맷팅
        guide_parts = [f"【 축적된 성공 사례 분석 - {box_name} 】\n"]
        guide_parts.append(f"고조회수 대본 {len(results)}개의 분석 결과를 바탕으로 한 가이드:\n")

        for idx, row in enumerate(results, 1):
            if USE_POSTGRES:
                content = row[target_field]
                view_count = row['view_count']
            else:
                content = row[0]
                view_count = row[1]

            if content:
                view_str = f"{view_count:,}회" if view_count else "정보없음"
                guide_parts.append(f"\n━━━ 사례 {idx} (조회수: {view_str}) ━━━")
                guide_parts.append(content.strip())

        guide_text = "\n".join(guide_parts)
        print(f"[DRAMA-DB-GUIDE] {len(results)}개 사례 가져옴 (필드: {target_field})")
        return guide_text

    except Exception as e:
        print(f"[DRAMA-DB-GUIDE][ERROR] {str(e)}")
        return None

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
    드라마 단계별로 최적화된 system prompt 반환
    mini는 개요와 자료만 생성, 완성된 대본 작성 금지
    """
    step_lower = step_name.lower()

    # 캐릭터 설정 단계
    if '캐릭터' in step_name or 'character' in step_lower:
        return f"""당신은 gpt-4o-mini로서 드라마 '캐릭터 설정 자료'만 준비하는 역할입니다.

현재 단계: {step_name}

기본 역할:
- 캐릭터의 기본 정보와 성격만 정리하세요
- 완성된 대본이나 대사는 작성하지 마세요
- 캐릭터 설정 자료만 제공하세요
- 사용자가 제공하는 세부 지침을 최우선으로 따름

⚠️ 중요: 사용자의 세부 지침이 제공되면 그것을 절대적으로 우선하여 따라야 합니다."""

    # 스토리라인 / 줄거리 단계
    elif '스토리' in step_name or '줄거리' in step_name or 'storyline' in step_lower or 'plot' in step_lower:
        return f"""당신은 gpt-4o-mini로서 드라마 '스토리라인 자료'만 준비하는 역할입니다.

현재 단계: {step_name}

기본 역할:
- 스토리의 구조와 전개만 정리하세요
- 완성된 대본이나 상세한 대사는 작성하지 마세요
- 스토리 개요와 구조만 제공하세요
- 사용자가 제공하는 세부 지침을 최우선으로 따름

⚠️ 중요: 사용자의 세부 지침이 제공되면 그것을 절대적으로 우선하여 따라야 합니다."""

    # 장면 구성 단계
    elif '장면' in step_name or 'scene' in step_lower:
        return f"""당신은 gpt-4o-mini로서 드라마 '장면 구성 자료'만 준비하는 역할입니다.

현재 단계: {step_name}

기본 역할:
- 장면의 구조와 목적만 정리하세요
- 완성된 대본이나 대사는 작성하지 마세요
- 장면 개요만 제공하세요
- 사용자가 제공하는 세부 지침을 최우선으로 따름

⚠️ 중요: 사용자의 세부 지침이 제공되면 그것을 절대적으로 우선하여 따라야 합니다."""

    # 대사 / 대본 작성 단계
    elif '대사' in step_name or '대본' in step_name or 'dialogue' in step_lower or 'script' in step_lower:
        return f"""당신은 gpt-4o-mini로서 드라마 '대사 작성 자료'만 준비하는 역할입니다.

⚠️ 중요: 완성된 대본은 작성하지 마세요!

현재 단계: {step_name}

기본 역할:
- 이 단계는 GPT-5.1에서 최종 작성될 부분입니다
- 대사의 톤, 스타일, 핵심 메시지만 제공하세요
- 완성된 대사나 대본은 작성하지 마세요
- 사용자가 제공하는 세부 지침을 최우선으로 따름

⚠️ 중요: 사용자의 세부 지침이 제공되면 그것을 절대적으로 우선하여 따라야 합니다."""

    # 기타 단계
    else:
        return f"""당신은 gpt-4o-mini로서 드라마 '초안 자료'만 준비하는 역할입니다.

현재 단계: {step_name}

기본 역할:
- 완성된 대본이 아닌, 자료와 구조만 제공
- 사용자가 제공하는 세부 지침을 최우선으로 따름
- 지침이 없는 경우에만 일반적인 드라마 자료 형식 사용

⚠️ 중요: 사용자의 세부 지침이 제공되면 그것을 절대적으로 우선하여 따라야 합니다."""

@app.route("/")
def home():
    return render_template("drama.html")

@app.route("/drama")
def drama():
    return render_template("drama.html")

@app.route("/health")
def health():
    return jsonify({"ok": True})

# ===== 처리 단계 실행 API (gpt-4o-mini) =====
@app.route("/api/drama/process", methods=["POST"])
def api_process_step():
    """단일 처리 단계 실행 (gpt-4o-mini 사용)"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"ok": False, "error": "No data received"}), 400

        category = data.get("category", "")
        step_id = data.get("stepId", "")
        step_name = data.get("stepName", "")
        benchmark_script = data.get("text", "")  # 벤치마킹 대본
        main_character = data.get("mainCharacter", "")  # 주인공 정보
        guide = data.get("guide", "")
        master_guide = data.get("masterGuide", "")
        previous_results = data.get("previousResults", {})

        print(f"[DRAMA-PROCESS] {category} - {step_name}")

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
        user_content = f"[영상 시간]\n{category}\n\n"

        if main_character:
            user_content += f"[주인공/대상]\n{main_character}\n\n"

        if benchmark_script:
            user_content += f"[벤치마킹 대본 (참고용)]\n{benchmark_script}\n\n"

        # 이전 단계 결과 추가
        if previous_results:
            user_content += "[이전 단계 결과 (참고용)]\n"
            for prev_id, prev_data in previous_results.items():
                user_content += f"\n### {prev_data['name']}\n{prev_data['result']}\n"
            user_content += "\n"

        user_content += f"위 내용을 바탕으로 '{step_name}' 단계를 작성해주세요.\n"
        user_content += "⚠️ 중요: 완성된 대본이 아닌, 자료와 구조만 제공하세요."

        # GPT 호출 (gpt-4o-mini)
        # JSON 형식 강제하지 않음 - guide에 따라 자유롭게 출력
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
            temperature=0.7,
        )

        result = completion.choices[0].message.content.strip()

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

            print(f"[DRAMA-PROCESS][SUCCESS] JSON 형식으로 응답받아 포맷팅 완료")
            return jsonify({"ok": True, "result": formatted_result})

        except json.JSONDecodeError as je:
            # JSON 파싱 실패 시 원본 텍스트를 반환 (정상 처리)
            # guide에서 텍스트 형식을 요구했을 수 있으므로 오류가 아님
            print(f"[DRAMA-PROCESS][INFO] 텍스트 형식으로 응답받음 (JSON 아님)")
            result = remove_markdown(result)
            return jsonify({"ok": True, "result": result})

    except Exception as e:
        print(f"[DRAMA-PROCESS][ERROR] {str(e)}")
        return jsonify({"ok": False, "error": str(e)}), 200


# ===== GPT PRO 처리 API (gpt-5.1) =====
@app.route("/api/drama/gpt-pro", methods=["POST"])
def api_gpt_pro():
    """GPT-5.1 드라마 대본 완성"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"ok": False, "error": "No data received"}), 400

        style_name = data.get("styleName", "")
        style_description = data.get("styleDescription", "")
        category = data.get("category", "")
        draft_content = data.get("draftContent", "")

        print(f"[DRAMA-GPT-PRO] 처리 시작 - 스타일: {style_name}")

        # GPT-5.1 시스템 프롬프트 (드라마 전용)
        system_content = (
            "당신은 GPT-5.1 기반의 전문 드라마 대본 작가입니다."
            " 자료는 참고용으로만 활용하고 대본은 처음부터 새로 구성하며,"
            " 자연스럽고 생동감 있는 대사와 지문으로 실제 촬영 가능한 완성도 높은 대본을 작성하세요."
            " 마크다운 기호 대신 순수 텍스트만 사용합니다."
        )

        # 사용자 메시지 구성
        meta_lines = []
        if category:
            meta_lines.append(f"- 드라마 유형: {category}")
        if style_name:
            meta_lines.append(f"- 드라마 스타일: {style_name}")
        if style_description:
            meta_lines.append(f"- 스타일 설명: {style_description}")

        meta_section = "\n".join(meta_lines)

        user_content = (
            "아래는 gpt-4o-mini가 정리한 드라마 기획 자료입니다."
            " 참고만 하고, 대본은 처음부터 새로 작성해주세요."
        )
        if meta_section:
            user_content += f"\n\n[기본 정보]\n{meta_section}"
        user_content += "\n\n[드라마 초안 자료]\n"
        user_content += draft_content

        # 드라마 대본 작성 요청
        user_content += "\n\n【요청 사항】\n"
        user_content += (
            "1. 실제 촬영이 가능한 형식으로 대본을 작성하세요:\n"
            "   - 장면 번호, 장소, 시간 명시\n"
            "   - 지문 (인물의 행동, 표정, 분위기 등)\n"
            "   - 대사 (인물명: 대사 형식)\n"
            "   - 필요시 (  ) 안에 감정이나 상황 묘사\n"
            "2. 자연스럽고 현실적인 대화를 작성하세요.\n"
            "3. 각 장면의 목적과 전개가 명확하도록 구성하세요.\n"
            "4. 캐릭터의 성격과 동기가 대사와 행동에 잘 드러나도록 하세요.\n"
            "5. 전체적인 흐름과 템포를 고려하여 작성하세요.\n"
            "6. 마크다운, 불릿 기호 대신 순수 텍스트로 작성하고, 중복되는 문장은 피하세요.\n"
            "7. 충분히 길고 상세하며 풍성한 내용으로 작성해주세요 (최대 16000 토큰)."
        )

        # 최신 Responses API (gpt-5.1) 호출
        completion = client.responses.create(
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

        if not result:
            raise RuntimeError("GPT-5.1 API로부터 결과를 받지 못했습니다.")

        # 마크다운 제거
        result = remove_markdown(result)

        # 결과 앞에 기본 정보 추가
        final_result = ""

        if style_name:
            final_result += f"드라마 스타일: {style_name}\n"

        if category:
            final_result += f"드라마 유형: {category}\n"

        if style_name or category:
            final_result += "\n" + "="*50 + "\n\n"

        final_result += result

        print(f"[DRAMA-GPT-PRO] 완료")

        return jsonify({"ok": True, "result": final_result})

    except Exception as e:
        print(f"[DRAMA-GPT-PRO][ERROR] {str(e)}")
        return jsonify({"ok": False, "error": str(e)}), 200


# ===== 벤치마킹 대본 분석 API =====
@app.route("/api/drama/analyze-benchmark", methods=["POST"])
def api_analyze_benchmark():
    """벤치마킹 대본 분석 및 저장"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"ok": False, "error": "No data received"}), 400

        benchmark_script = data.get("benchmarkScript", "")
        upload_date = data.get("uploadDate", "")
        view_count = data.get("viewCount", "")
        category = data.get("category", "")
        script_hash = data.get("scriptHash", "")

        if not benchmark_script:
            return jsonify({"ok": False, "error": "벤치마킹 대본이 없습니다."}), 400

        # DB 기반 중복 체크
        is_duplicate = False
        if script_hash:
            conn = get_db_connection()
            cursor = conn.cursor()
            if USE_POSTGRES:
                cursor.execute("SELECT id FROM benchmark_analyses WHERE script_hash = %s", (script_hash,))
            else:
                cursor.execute("SELECT id FROM benchmark_analyses WHERE script_hash = ?", (script_hash,))
            existing = cursor.fetchone()
            conn.close()

            if existing:
                is_duplicate = True
                print(f"[DRAMA-ANALYZE] 중복 대본 감지 (해시: {script_hash}) - 분석만 수행")

        print(f"[DRAMA-ANALYZE] 벤치마킹 대본 분석 시작 - {view_count} 조회수 - 중복: {is_duplicate}")

        # GPT로 대본 분석
        system_content = """당신은 드라마 대본 분석 전문가입니다.

제공된 벤치마킹 대본을 분석하여 다음 요소들을 추출하고 정리하세요:

1. **스토리 구조 패턴**
   - 도입, 전개, 위기, 절정, 결말의 구성 방식
   - 각 파트의 비중과 전환 타이밍

2. **캐릭터 구성 요소**
   - 주인공의 성격과 동기
   - 갈등의 원천과 해결 방식

3. **대사 스타일**
   - 톤과 분위기
   - 핵심 메시지 전달 방식

4. **시청자 반응 요소**
   - 공감을 유도하는 요소
   - 감정적 몰입 포인트

5. **성공 요인 분석**
   - 조회수 관점에서 본 강점
   - 차별화 포인트

분석 결과는 구조화되고 명확하게 작성하세요."""

        user_content = f"""[벤치마킹 대본 정보]
- 업로드 날짜: {upload_date}
- 조회수: {view_count}
- 영상 시간: {category}

[대본 내용]
{benchmark_script}

위 대본을 분석하여 핵심 패턴과 성공 요인을 추출해주세요."""

        completion = client.chat.completions.create(
            model="gpt-5",
            messages=[
                {"role": "system", "content": system_content},
                {"role": "user", "content": user_content}
            ]
        )

        analysis = completion.choices[0].message.content.strip()
        total_tokens = completion.usage.total_tokens if hasattr(completion, 'usage') else 0

        # 분석 결과를 섹션별로 파싱 (간단한 구조화)
        story_structure = ""
        character_elements = ""
        dialogue_style = ""
        success_factors = ""

        # 섹션별 추출 (간단한 패턴 매칭)
        sections = analysis.split('\n\n')
        for section in sections:
            if '스토리 구조' in section or '구조 패턴' in section:
                story_structure = section
            elif '캐릭터' in section:
                character_elements = section
            elif '대사' in section:
                dialogue_style = section
            elif '성공 요인' in section:
                success_factors = section

        # 중복이 아닌 경우에만 DB에 저장
        if not is_duplicate and script_hash:
            try:
                conn = get_db_connection()
                cursor = conn.cursor()

                # 조회수를 숫자로 변환 (예: "12만" -> 120000)
                view_count_num = 0
                if view_count:
                    view_count_str = view_count.replace(',', '').strip()
                    if '만' in view_count_str:
                        view_count_num = int(float(view_count_str.replace('만', '')) * 10000)
                    elif '천' in view_count_str:
                        view_count_num = int(float(view_count_str.replace('천', '')) * 1000)
                    else:
                        try:
                            view_count_num = int(view_count_str)
                        except:
                            view_count_num = 0

                if USE_POSTGRES:
                    cursor.execute('''
                        INSERT INTO benchmark_analyses
                        (script_text, script_hash, upload_date, view_count, category,
                         analysis_result, story_structure, character_elements,
                         dialogue_style, success_factors, ai_model, analysis_tokens)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ''', (benchmark_script, script_hash, upload_date, view_count_num, category,
                          analysis, story_structure, character_elements,
                          dialogue_style, success_factors, 'gpt-5', total_tokens))
                else:
                    cursor.execute('''
                        INSERT INTO benchmark_analyses
                        (script_text, script_hash, upload_date, view_count, category,
                         analysis_result, story_structure, character_elements,
                         dialogue_style, success_factors, ai_model, analysis_tokens)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (benchmark_script, script_hash, upload_date, view_count_num, category,
                          analysis, story_structure, character_elements,
                          dialogue_style, success_factors, 'gpt-5', total_tokens))

                conn.commit()
                conn.close()
                print(f"[DRAMA-ANALYZE] DB 저장 완료 (해시: {script_hash}, 토큰: {total_tokens})")
            except Exception as e:
                print(f"[DRAMA-ANALYZE] DB 저장 실패: {str(e)}")

        print(f"[DRAMA-ANALYZE] 분석 완료 - 저장 여부: {not is_duplicate}, 모델: gpt-5")

        return jsonify({"ok": True, "analysis": analysis, "isDuplicate": is_duplicate})

    except Exception as e:
        print(f"[DRAMA-ANALYZE][ERROR] {str(e)}")
        return jsonify({"ok": False, "error": str(e)}), 200


# ===== 개선 제안 API =====
@app.route("/api/drama/get-suggestions", methods=["POST"])
def api_get_suggestions():
    """현재 대본에 대한 개선 제안"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"ok": False, "error": "No data received"}), 400

        current_draft = data.get("currentDraft", "")
        category = data.get("category", "")

        if not current_draft:
            return jsonify({"ok": False, "error": "현재 작업 중인 대본이 없습니다."}), 400

        print(f"[DRAMA-SUGGEST] 개선 제안 생성 시작")

        # GPT로 개선 제안 생성
        system_content = """당신은 드라마 대본 컨설턴트입니다.

제공된 초안 대본을 분석하고, 다음 관점에서 구체적인 개선 제안을 제공하세요:

1. **스토리 흐름 개선**
   - 더 강력한 도입부 만들기
   - 긴장감을 높이는 방법
   - 결말의 임팩트 강화

2. **캐릭터 깊이 추가**
   - 주인공의 동기 명확화
   - 감정선 강화 방법

3. **시청자 몰입 요소**
   - 공감 포인트 강화
   - 예상을 뛰어넘는 전개

4. **대사와 연출**
   - 핵심 메시지 전달력 향상
   - 감정적 호소력 강화

각 제안은 구체적이고 실행 가능해야 합니다."""

        user_content = f"""[영상 시간]
{category}

[현재 작업 중인 초안]
{current_draft}

위 초안을 분석하고, 시청자 반응을 극대화할 수 있는 구체적인 개선 제안을 해주세요."""

        completion = client.chat.completions.create(
            model="gpt-5",
            messages=[
                {"role": "system", "content": system_content},
                {"role": "user", "content": user_content}
            ]
        )

        suggestions = completion.choices[0].message.content.strip()

        print(f"[DRAMA-SUGGEST] 제안 생성 완료 (모델: gpt-5)")

        return jsonify({"ok": True, "suggestions": suggestions})

    except Exception as e:
        print(f"[DRAMA-SUGGEST][ERROR] {str(e)}")
        return jsonify({"ok": False, "error": str(e)}), 200


# ===== 워크플로우 박스 실행 API =====
@app.route("/api/drama/workflow-execute", methods=["POST"])
def api_workflow_execute():
    """워크플로우 박스 실행 (선택된 입력 소스 기반)"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"ok": False, "error": "No data received"}), 400

        box_id = data.get("boxId", "")
        box_name = data.get("boxName", "")
        box_number = data.get("boxNumber", 0)
        step_type = data.get("stepType", "step1")  # step1 or step2
        guide = data.get("guide", "")
        inputs = data.get("inputs", {})  # dict with selected input sources
        category = data.get("category", "")
        main_character = data.get("mainCharacter", "")
        selected_model = data.get("model", "")  # 프론트엔드에서 선택한 모델

        # Step 타입에 따른 모델 선택 (프론트엔드에서 선택한 모델 우선)
        if selected_model:
            model_name = selected_model
            use_temperature = True  # 사용자가 모델을 선택한 경우 temperature 사용
        elif step_type == "step1":
            model_name = "gpt-5"
            use_temperature = False
        else:  # step2
            model_name = "gpt-4o-mini"
            use_temperature = True

        print(f"[DRAMA-WORKFLOW] Box [{box_number}] {box_name} 실행 시작 (모델: {model_name}, Step: {step_type})")

        # 선택된 입력 소스들을 조합
        input_content_parts = []

        # 벤치마킹 대본이 선택된 경우
        if inputs.get("benchmarkScript"):
            input_content_parts.append(f"[벤치마킹 대본]\n{inputs['benchmarkScript']}")

        # AI 분석 자료가 선택된 경우
        if inputs.get("aiAnalysis"):
            input_content_parts.append(f"[AI 대본 분석 자료]\n{inputs['aiAnalysis']}")

        # DB에서 관련 가이드 가져오기 (자동 추가)
        db_guide = get_relevant_guide_from_db(box_name, category, limit=3)
        if db_guide:
            input_content_parts.append(f"[축적된 성공 사례 가이드]\n{db_guide}")

        # 이전 박스 결과들이 선택된 경우
        for key, value in inputs.items():
            if key.startswith("box") and key.endswith("Result"):
                # box1Result, box2Result 등
                box_num = key.replace("box", "").replace("Result", "")
                input_content_parts.append(f"[박스 {box_num} 결과]\n{value}")

        # 입력이 없는 경우 오류 반환
        if not input_content_parts:
            return jsonify({"ok": False, "error": "선택된 입력 소스가 없습니다. 체크박스를 선택해주세요."}), 400

        # 시스템 프롬프트 구성
        system_content = f"""당신은 드라마 제작 워크플로우 시스템의 작업 박스 [{box_number}] '{box_name}'를 처리하는 AI 어시스턴트입니다.

사용자가 제공하는 작업 지침을 절대적으로 우선하여 따라야 합니다.
지침이 명확하면 그대로 수행하고, 지침이 없거나 불명확하면 일반적인 드라마 제작 원칙에 따라 처리하세요.

현재 작업: [{box_number}] {box_name}
영상 시간: {category}"""

        # 주인공 정보 추가
        if main_character:
            system_content += f"\n주인공 설정: {main_character}"
            system_content += "\n\n⚠️ 중요: 위에 지정된 주인공을 반드시 사용하여 대본을 구성하세요."

        # 작업 지침 추가
        if guide:
            system_content += f"""

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
【 작업 지침 (최우선) 】
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

{guide}

위 지침을 절대적으로 우선하여 따라야 합니다."""
        else:
            system_content += "\n\n⚠️ 작업 지침이 제공되지 않았습니다. 일반적인 드라마 제작 원칙에 따라 처리하세요."

        # 사용자 메시지 구성 (선택된 입력 소스들)
        user_content = "다음은 선택된 입력 자료들입니다:\n\n"
        user_content += "\n\n".join(input_content_parts)
        user_content += "\n\n위 자료를 바탕으로 작업 지침에 따라 처리해주세요."

        # GPT 호출 (모델 및 temperature 동적 설정)
        if use_temperature:
            completion = client.chat.completions.create(
                model=model_name,
                messages=[
                    {"role": "system", "content": system_content},
                    {"role": "user", "content": user_content}
                ],
                temperature=0.7,
            )
        else:
            completion = client.chat.completions.create(
                model=model_name,
                messages=[
                    {"role": "system", "content": system_content},
                    {"role": "user", "content": user_content}
                ]
            )

        result = completion.choices[0].message.content.strip()

        # 마크다운 제거
        result = remove_markdown(result)

        # 토큰 사용량 추출
        input_tokens = completion.usage.prompt_tokens if hasattr(completion, 'usage') and completion.usage else 0
        output_tokens = completion.usage.completion_tokens if hasattr(completion, 'usage') and completion.usage else 0

        print(f"[DRAMA-WORKFLOW] Box [{box_number}] {box_name} 실행 완료 (모델: {model_name}, 토큰: {input_tokens}/{output_tokens})")

        return jsonify({
            "ok": True,
            "result": result,
            "usage": {
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "model": model_name
            }
        })

    except Exception as e:
        print(f"[DRAMA-WORKFLOW][ERROR] {str(e)}")
        return jsonify({"ok": False, "error": str(e)}), 200


# ===== 축적된 작성 가이드 조회 API =====
@app.route("/api/drama/get-accumulated-guide", methods=["POST"])
def api_get_accumulated_guide():
    """축적된 대본 분석 결과를 기반으로 작성 가이드 제공"""
    try:
        data = request.get_json()
        category = data.get("category", "") if data else ""

        print(f"[DRAMA-GUIDE] 축적된 가이드 조회 시작")

        # DB에서 축적된 데이터 확인
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            if USE_POSTGRES:
                cursor.execute("SELECT COUNT(*) as cnt FROM benchmark_analyses")
                count_result = cursor.fetchone()
                db_count = count_result['cnt'] if count_result else 0
            else:
                cursor.execute("SELECT COUNT(*) FROM benchmark_analyses")
                db_count = cursor.fetchone()[0]
            conn.close()

            if db_count > 0:
                # DB에 데이터가 있으면 실제 분석 결과 기반 가이드 생성
                print(f"[DRAMA-GUIDE] DB에 {db_count}개 분석 데이터 발견 - 실제 데이터 기반 가이드 생성")

                # 각 카테고리별 TOP 분석 결과 가져오기
                guide_parts = ["【 축적된 대본 분석 기반 작성 가이드 】\n"]
                guide_parts.append(f"총 {db_count}개의 대본 분석 결과를 바탕으로 작성되었습니다.\n\n")

                # 1. 스토리 구조 가이드
                story_guide = get_relevant_guide_from_db("스토리 구성", category, limit=3)
                if story_guide:
                    guide_parts.append("━━━━━━━━━━━━━━━━━━━━━━━━━━")
                    guide_parts.append("📖 스토리 구조 성공 사례")
                    guide_parts.append("━━━━━━━━━━━━━━━━━━━━━━━━━━\n")
                    guide_parts.append(story_guide)
                    guide_parts.append("\n")

                # 2. 캐릭터 설계 가이드
                character_guide = get_relevant_guide_from_db("캐릭터 설정", category, limit=3)
                if character_guide:
                    guide_parts.append("━━━━━━━━━━━━━━━━━━━━━━━━━━")
                    guide_parts.append("👥 캐릭터 설계 성공 사례")
                    guide_parts.append("━━━━━━━━━━━━━━━━━━━━━━━━━━\n")
                    guide_parts.append(character_guide)
                    guide_parts.append("\n")

                # 3. 대사 작성 가이드
                dialogue_guide = get_relevant_guide_from_db("대사 작성", category, limit=3)
                if dialogue_guide:
                    guide_parts.append("━━━━━━━━━━━━━━━━━━━━━━━━━━")
                    guide_parts.append("💬 대사 작성 성공 사례")
                    guide_parts.append("━━━━━━━━━━━━━━━━━━━━━━━━━━\n")
                    guide_parts.append(dialogue_guide)
                    guide_parts.append("\n")

                # 4. 성공 요인 종합
                success_guide = get_relevant_guide_from_db("성공 요인", category, limit=5)
                if success_guide:
                    guide_parts.append("━━━━━━━━━━━━━━━━━━━━━━━━━━")
                    guide_parts.append("🏆 고조회수 대본의 성공 요인")
                    guide_parts.append("━━━━━━━━━━━━━━━━━━━━━━━━━━\n")
                    guide_parts.append(success_guide)

                guide = "\n".join(guide_parts)
                print(f"[DRAMA-GUIDE] DB 기반 가이드 생성 완료")
                return jsonify({"ok": True, "guide": guide, "source": "database"})

        except Exception as db_err:
            print(f"[DRAMA-GUIDE] DB 조회 실패, GPT 가이드로 폴백: {str(db_err)}")

        # DB에 데이터가 없거나 오류 시 GPT로 일반 가이드 생성
        print(f"[DRAMA-GUIDE] DB 데이터 없음 - GPT 일반 가이드 생성")

        system_content = """당신은 드라마 대본 작성 전문가입니다.

수많은 성공적인 드라마 대본들을 분석하여 얻은 보편적인 작성 가이드를 제공하세요.

다음 요소들을 포함하여 구조화된 가이드를 작성하세요:

1. **스토리 구조 모범 사례**
   - 효과적인 도입부 구성법
   - 긴장감을 유지하는 전개 방식
   - 강렬한 클라이맥스 만들기
   - 여운 남는 결말 작성법

2. **캐릭터 설계 원칙**
   - 공감 가는 주인공 만들기
   - 명확한 동기와 목표 설정
   - 성장 아크 디자인
   - 갈등의 원천 설정

3. **대사 작성 기법**
   - 자연스러운 대화 만들기
   - 캐릭터 개성 드러내기
   - 핵심 메시지 전달 방법
   - 감정적 호소력 강화

4. **시청자 몰입 전략**
   - 공감 포인트 배치
   - 예상을 뛰어넘는 전개
   - 감정적 카타르시스 제공
   - 보편적 주제 다루기

5. **장르별 차별화 요소**
   - 기독교 드라마의 특성
   - 감동 드라마의 핵심
   - 멜로/로맨스의 포인트
   - 스릴러/서스펜스의 긴장감

각 항목은 실전에서 바로 적용 가능하도록 구체적이고 명확하게 작성하세요."""

        user_content = "드라마 대본 작성 시 참고할 수 있는 보편적이고 실용적인 가이드를 제공해주세요."

        if category:
            user_content += f"\n\n특히 '{category}' 길이의 드라마에 적합한 가이드를 포함해주세요."

        completion = client.chat.completions.create(
            model="gpt-5",
            messages=[
                {"role": "system", "content": system_content},
                {"role": "user", "content": user_content}
            ]
        )

        guide = completion.choices[0].message.content.strip()

        print(f"[DRAMA-GUIDE] GPT 일반 가이드 생성 완료 (모델: gpt-5)")

        return jsonify({"ok": True, "guide": guide, "source": "gpt"})

    except Exception as e:
        print(f"[DRAMA-GUIDE][ERROR] {str(e)}")
        return jsonify({"ok": False, "error": str(e)}), 200


# ===== Step3: OpenRouter를 통한 Claude 대본 완성 =====
@app.route('/api/drama/step3-test', methods=['GET'])
def api_drama_step3_test():
    """Step3 테스트 엔드포인트"""
    return jsonify({
        "ok": True,
        "openrouter_configured": openrouter_client is not None,
        "message": "Step3 endpoint is reachable"
    })


@app.route('/api/drama/claude-step3', methods=['POST'])
def api_drama_claude_step3():
    """Step3: OpenRouter를 통한 드라마 대본 완성"""
    try:
        print("[DRAMA-STEP3] 요청 받음")

        if not openrouter_client:
            print("[DRAMA-STEP3] OpenRouter 클라이언트 없음")
            return jsonify({"ok": False, "error": "OpenRouter API key not configured. Render 환경변수에 OPENROUTER_API_KEY를 설정해주세요."}), 200

        data = request.get_json()
        if not data:
            print("[DRAMA-STEP3] 데이터 없음")
            return jsonify({"ok": False, "error": "No data received"}), 200

        category = data.get("category", "")
        style_name = data.get("styleName", "")
        style_description = data.get("styleDescription", "")
        draft_content = data.get("draftContent", "")
        main_character = data.get("mainCharacter", {})
        benchmark_script = data.get("benchmarkScript", "")
        ai_analysis = data.get("aiAnalysis", "")
        step3_guide = data.get("step3Guide", "")
        selected_model = data.get("model", "anthropic/claude-3.5-sonnet")

        print(f"[DRAMA-STEP3-OPENROUTER] 처리 시작 - 카테고리: {category}, 모델: {selected_model}")
        print(f"[DRAMA-STEP3-DEBUG] step3_guide 길이: {len(step3_guide)}, 내용: {step3_guide[:100] if step3_guide else '(없음)'}...")
        print(f"[DRAMA-STEP3-DEBUG] draft_content 길이: {len(draft_content)}, 내용: {draft_content[:300] if draft_content else '(없음)'}...")

        # Claude Step3 시스템 프롬프트 (드라마 대본 완성 전용)
        # 사용자 지침이 있으면 유연하게 대응, 없으면 기본 형식 사용
        if step3_guide:
            # 사용자 지침이 있는 경우: 유연한 시스템 프롬프트
            system_content = """당신은 전문 드라마/스토리 작가입니다.

【 핵심 역할 】
- Step1, Step2에서 생성된 자료와 분석을 바탕으로 최종 콘텐츠를 완성합니다.
- 자료는 참고용으로만 활용하고, 콘텐츠는 처음부터 새로 구성합니다.

【 중요: 사용자 지침 최우선 】
⚠️ 사용자가 제공하는 '작성 지침'이 있다면, 해당 지침의 형식과 규칙을 반드시 따르세요.
⚠️ 기본 대본 형식보다 사용자 지침이 우선합니다.
⚠️ 사용자 지침에서 금지하는 표현(예: 캐릭터명:, 장면번호, 괄호 감정지시 등)은 절대 사용하지 마세요.

【 기본 원칙 】
1. 자연스럽고 몰입감 있는 콘텐츠 작성
2. 감정선이 점진적으로 발전하도록 구성
3. 마크다운 기호(#, *, -, **) 사용 금지, 순수 텍스트만
4. 중복되는 문장이나 설명 피하기"""
        else:
            # 사용자 지침이 없는 경우: 기존 드라마 대본 형식
            system_content = """당신은 Claude Sonnet 기반의 전문 드라마 대본 작가입니다.

【 핵심 역할 】
- Step1, Step2에서 생성된 자료와 분석을 바탕으로 최종 대본을 완성합니다.
- 자료는 참고용으로만 활용하고, 대본은 처음부터 새로 구성합니다.
- 자연스럽고 생동감 있는 대사와 지문으로 실제 촬영 가능한 완성도 높은 대본을 작성합니다.

【 대본 작성 원칙 】
1. 장면 구성: 장면 번호, 장소, 시간을 명확히 표시
2. 지문: 인물의 행동, 표정, 분위기를 구체적으로 묘사
3. 대사: "인물명: 대사" 형식으로 작성, 필요시 (감정/상황) 추가
4. 흐름: 각 장면의 목적과 전개가 명확하도록 구성
5. 캐릭터: 성격과 동기가 대사와 행동에 자연스럽게 드러나도록
6. 형식: 마크다운 기호(#, *, -, **) 사용 금지, 순수 텍스트만

【 대본 형식 예시 】
S#1. 카페 내부 / 낮

(세련된 인테리어의 카페. 창가 자리에 민수가 앉아 커피를 마시며 창밖을 바라보고 있다.)

민수: (혼잣말) 오늘은 꼭 말해야 해...

(문이 열리며 지현이 들어온다. 민수를 발견하고 환하게 미소 짓는다.)

지현: 오빠, 오래 기다렸어?
민수: (자리에서 일어나며) 아니, 방금 왔어.

---

위와 같은 형식으로 완성도 높은 대본을 작성하세요."""

        # 사용자 메시지 구성
        user_content = ""

        # 메타 정보 추가
        meta_lines = []
        if category:
            meta_lines.append(f"- 드라마 유형/영상 시간: {category}")
        if style_name:
            meta_lines.append(f"- 드라마 스타일: {style_name}")
        if style_description:
            meta_lines.append(f"- 스타일 설명: {style_description}")

        # 주인공 정보 추가
        if main_character:
            char_info = []
            if main_character.get("name"):
                char_info.append(f"이름: {main_character['name']}")
            if main_character.get("age"):
                char_info.append(f"나이: {main_character['age']}")
            if main_character.get("personality"):
                char_info.append(f"성격: {main_character['personality']}")
            if char_info:
                meta_lines.append(f"- 주인공: {', '.join(char_info)}")

        if meta_lines:
            user_content += "【 기본 정보 】\n"
            user_content += "\n".join(meta_lines)
            user_content += "\n\n"

        # 벤치마킹 대본 (있다면)
        if benchmark_script:
            user_content += "【 벤치마킹 대본 (참고용) 】\n"
            user_content += benchmark_script[:3000] + ("..." if len(benchmark_script) > 3000 else "")
            user_content += "\n\n"

        # AI 분석 결과 (있다면)
        if ai_analysis:
            user_content += "【 AI 분석 결과 】\n"
            user_content += ai_analysis[:2000] + ("..." if len(ai_analysis) > 2000 else "")
            user_content += "\n\n"

        # Step2 결과 (드라마 초안 자료)
        if draft_content:
            user_content += "【 Step2 작업 결과 (참고 자료) 】\n"
            user_content += draft_content
            user_content += "\n\n"

        # Step3 사용자 지침 (있다면)
        if step3_guide:
            user_content += "【 ⭐ 작성 지침 (최우선 적용) 】\n"
            user_content += step3_guide
            user_content += "\n\n위 지침을 반드시 우선적으로 따라 대본을 작성해주세요.\n\n"

        # 대본 작성 요청 - 카테고리 기반 분량 지시 추가
        length_guide = ""
        if "10분" in category:
            length_guide = "약 3000~4000자 분량으로"
        elif "20분" in category:
            length_guide = "약 6000~8000자 분량으로"
        elif "30분" in category:
            length_guide = "약 9000~12000자 분량으로"
        else:
            length_guide = "충분히 길고 상세하게"

        user_content += f"""【 요청 사항 】
위 자료를 참고하여 완성된 콘텐츠를 작성해주세요.

⚠️ 분량: {length_guide} 작성하세요. 너무 짧게 끝내지 마세요!

작성 시 주의사항:
1. 자료는 참고만 하고, 콘텐츠는 처음부터 새로 구성하세요.
2. 자연스럽고 몰입감 있게 작성하세요.
3. 감정선이 점진적으로 발전하도록 구성하세요.
4. 인트로 → 갈등/전개 → 터닝포인트 → 회복/결말 구조를 따르세요.
5. 마크다운 기호(#, *, -, **) 대신 순수 텍스트로 작성하세요.
6. 중복되는 문장이나 설명은 피하세요.
7. 지정된 분량을 채울 때까지 풍성하게 내용을 전개하세요."""

        # OpenRouter API 호출 (OpenAI 호환)
        response = openrouter_client.chat.completions.create(
            model=selected_model,
            max_tokens=8000,
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
            temperature=0.8
        )

        # 응답 추출
        result = response.choices[0].message.content if response.choices else ""
        result = result.strip()

        if not result:
            raise RuntimeError("OpenRouter API로부터 결과를 받지 못했습니다.")

        # 마크다운 제거
        result = remove_markdown(result)

        # 결과 앞에 기본 정보 추가
        final_result = ""

        if style_name:
            final_result += f"드라마 스타일: {style_name}\n"

        if category:
            final_result += f"드라마 유형: {category}\n"

        if style_name or category:
            final_result += "\n" + "="*50 + "\n\n"

        final_result += result

        # 토큰 사용량 추출
        input_tokens = response.usage.prompt_tokens if response.usage else 0
        output_tokens = response.usage.completion_tokens if response.usage else 0

        print(f"[DRAMA-STEP3-OPENROUTER] 완료 - 토큰: {input_tokens} / {output_tokens}")

        return jsonify({
            "ok": True,
            "result": final_result,
            "usage": {
                "input_tokens": input_tokens,
                "output_tokens": output_tokens
            }
        })

    except Exception as e:
        print(f"[DRAMA-STEP3-OPENROUTER][ERROR] {str(e)}")
        return jsonify({"ok": False, "error": str(e)}), 200


# ===== AI 챗봇 API =====
@app.route('/api/drama/chat', methods=['POST'])
def api_drama_chat():
    """드라마 페이지 AI 챗봇 - 현재 작업 상황에 대해 질문/답변"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"ok": False, "error": "No data received"}), 400

        question = data.get("question", "")
        context = data.get("context", {})  # 현재 작업 상태
        selected_model = data.get("model", "gpt-4o-mini")  # 선택된 모델

        # 허용된 모델 목록
        allowed_models = ["gpt-4o-mini", "gpt-4o", "gpt-5"]
        if selected_model not in allowed_models:
            selected_model = "gpt-4o-mini"

        if not question:
            return jsonify({"ok": False, "error": "질문을 입력해주세요."}), 400

        print(f"[DRAMA-CHAT] 모델: {selected_model}, 질문: {question[:100]}...")

        # 컨텍스트 구성
        context_text = ""

        # 워크플로우 박스 결과들
        if context.get("workflowResults"):
            context_text += "【현재 작업 상태】\n"
            for box in context.get("workflowResults", []):
                if box.get("result"):
                    context_text += f"\n## {box.get('name', '작업 박스')}\n{box.get('result', '')[:2000]}\n"

        # Step3 결과
        if context.get("step3Result"):
            context_text += f"\n【Step3 최종 결과】\n{context.get('step3Result', '')[:3000]}\n"

        # 벤치마크 스크립트
        if context.get("benchmarkScript"):
            context_text += f"\n【벤치마크 대본 (참고용)】\n{context.get('benchmarkScript', '')[:1500]}\n"

        # 오류 정보
        if context.get("lastError"):
            context_text += f"\n【최근 오류】\n{context.get('lastError', '')}\n"

        # 시스템 프롬프트
        system_prompt = """당신은 드라마 대본 작성을 돕는 AI 어시스턴트입니다.
사용자가 현재 작업 중인 드라마 대본에 대해 질문하면, 주어진 컨텍스트를 바탕으로 도움이 되는 답변을 제공합니다.

역할:
1. 현재 작업 상황 분석 및 설명
2. 개선 제안 및 아이디어 제공
3. 오류나 문제점 해결 도움
4. 스토리, 캐릭터, 대사 등에 대한 피드백
5. 다음 단계 진행 가이드

답변 시 유의사항:
- 간결하고 실용적인 답변을 제공하세요
- 구체적인 예시나 제안을 포함하세요
- 한국어로 친절하게 답변하세요
- 현재 작업 상태를 고려하여 맥락에 맞는 답변을 하세요"""

        # 사용자 메시지 구성
        user_content = ""
        if context_text:
            user_content += f"{context_text}\n\n"
        user_content += f"【질문】\n{question}"

        # GPT 호출 (선택된 모델 사용)
        completion = client.chat.completions.create(
            model=selected_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content}
            ],
            temperature=0.7,
            max_tokens=4000 if selected_model in ["gpt-4o", "gpt-5"] else 2000
        )

        answer = completion.choices[0].message.content.strip()

        # 토큰 사용량
        usage = {
            "input_tokens": completion.usage.prompt_tokens,
            "output_tokens": completion.usage.completion_tokens,
            "model": selected_model
        }

        print(f"[DRAMA-CHAT][SUCCESS] {selected_model}로 답변 생성 완료")
        return jsonify({"ok": True, "answer": answer, "usage": usage})

    except Exception as e:
        print(f"[DRAMA-CHAT][ERROR] {str(e)}")
        return jsonify({"ok": False, "error": str(e)}), 500


# ===== Step4: 이미지 프롬프트 생성 API =====
@app.route('/api/drama/generate-image-prompts', methods=['POST'])
def api_generate_image_prompts():
    """대본을 분석하여 인물/배경/통합 이미지 프롬프트 생성"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"ok": False, "error": "No data received"}), 400

        script = data.get("script", "")
        main_character = data.get("mainCharacter", "")

        if not script:
            return jsonify({"ok": False, "error": "대본이 없습니다."}), 400

        print(f"[DRAMA-STEP4-PROMPT] 이미지 프롬프트 생성 시작")

        # GPT를 사용하여 이미지 프롬프트 생성
        system_content = """당신은 드라마 대본을 분석하여 DALL-E 3 이미지 생성을 위한 프롬프트를 작성하는 전문가입니다.

대본을 읽고 다음 세 가지 프롬프트를 영어로 작성해주세요:

1. 인물 프롬프트 (Character Prompt)
   - 주인공의 외모, 표정, 의상, 자세를 묘사
   - 나이, 성별, 분위기를 포함
   - 예: "A Korean woman in her late 20s, gentle and warm expression, wearing a soft beige cardigan over a white blouse, sitting gracefully"

2. 배경 프롬프트 (Background Prompt)
   - 장면의 배경, 장소, 시간대, 분위기를 묘사
   - 조명, 색감, 분위기를 포함
   - 예: "A cozy Korean cafe interior, warm afternoon sunlight streaming through large windows, wooden furniture, soft ambient lighting"

3. 통합 장면 프롬프트 (Combined Scene Prompt)
   - 인물이 배경에 자연스럽게 어울리는 완전한 장면 묘사
   - 영화적이고 시각적으로 매력적인 구도
   - 예: "A Korean woman in her late 20s sitting by the window in a cozy cafe, warm afternoon sunlight illuminating her gentle smile, holding a cup of coffee, cinematic composition, soft bokeh background"

응답 형식:
CHARACTER_PROMPT: [인물 프롬프트]
BACKGROUND_PROMPT: [배경 프롬프트]
COMBINED_PROMPT: [통합 프롬프트]

중요:
- 모든 프롬프트는 영어로 작성
- DALL-E 3에 최적화된 상세하고 시각적인 묘사
- 부정적이거나 폭력적인 내용 제외
- 사실적이고 고품질의 이미지를 생성할 수 있도록 작성"""

        user_content = f"""다음 드라마 대본을 분석하여 이미지 프롬프트를 생성해주세요.

[주인공 정보]
{main_character if main_character else '(별도 정보 없음 - 대본에서 추출)'}

[드라마 대본]
{script[:4000]}

위 대본의 핵심 장면에 대한 이미지 프롬프트를 생성해주세요."""

        completion = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_content},
                {"role": "user", "content": user_content}
            ],
            temperature=0.7
        )

        result = completion.choices[0].message.content.strip()

        # 프롬프트 파싱
        character_prompt = ""
        background_prompt = ""
        combined_prompt = ""

        lines = result.split('\n')
        current_type = None

        for line in lines:
            line = line.strip()
            if line.startswith('CHARACTER_PROMPT:'):
                current_type = 'character'
                character_prompt = line.replace('CHARACTER_PROMPT:', '').strip()
            elif line.startswith('BACKGROUND_PROMPT:'):
                current_type = 'background'
                background_prompt = line.replace('BACKGROUND_PROMPT:', '').strip()
            elif line.startswith('COMBINED_PROMPT:'):
                current_type = 'combined'
                combined_prompt = line.replace('COMBINED_PROMPT:', '').strip()
            elif current_type and line:
                # 여러 줄에 걸친 프롬프트 처리
                if current_type == 'character':
                    character_prompt += ' ' + line
                elif current_type == 'background':
                    background_prompt += ' ' + line
                elif current_type == 'combined':
                    combined_prompt += ' ' + line

        print(f"[DRAMA-STEP4-PROMPT] 프롬프트 생성 완료")

        return jsonify({
            "ok": True,
            "characterPrompt": character_prompt,
            "backgroundPrompt": background_prompt,
            "combinedPrompt": combined_prompt
        })

    except Exception as e:
        print(f"[DRAMA-STEP4-PROMPT][ERROR] {str(e)}")
        return jsonify({"ok": False, "error": str(e)}), 200


# ===== Step4: DALL-E 3 이미지 생성 API =====
@app.route('/api/drama/generate-image', methods=['POST'])
def api_generate_image():
    """DALL-E 3를 사용하여 이미지 생성"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"ok": False, "error": "No data received"}), 400

        prompt = data.get("prompt", "")
        size = data.get("size", "1024x1024")

        if not prompt:
            return jsonify({"ok": False, "error": "프롬프트가 없습니다."}), 400

        # 허용된 사이즈 검증
        allowed_sizes = ["1024x1024", "1792x1024", "1024x1792"]
        if size not in allowed_sizes:
            size = "1024x1024"

        print(f"[DRAMA-STEP4-IMAGE] DALL-E 3 이미지 생성 시작 - 사이즈: {size}")

        # 프롬프트에 스타일 가이드 추가
        enhanced_prompt = f"{prompt}, high quality, photorealistic, cinematic lighting, professional photography, 8k resolution"

        # DALL-E 3 API 호출
        response = client.images.generate(
            model="dall-e-3",
            prompt=enhanced_prompt,
            size=size,
            quality="standard",
            n=1
        )

        image_url = response.data[0].url

        # DALL-E 3 비용 계산 (2024년 기준)
        # Standard quality: $0.040 (1024x1024), $0.080 (1792x1024, 1024x1792)
        # HD quality: $0.080 (1024x1024), $0.120 (1792x1024, 1024x1792)
        cost_usd = 0.04 if size == "1024x1024" else 0.08
        cost_krw = int(cost_usd * 1350)  # 대략적인 환율

        print(f"[DRAMA-STEP4-IMAGE] 이미지 생성 완료 - 비용: ${cost_usd}")

        return jsonify({
            "ok": True,
            "imageUrl": image_url,
            "cost": cost_krw,
            "costUsd": cost_usd
        })

    except Exception as e:
        error_msg = str(e)
        print(f"[DRAMA-STEP4-IMAGE][ERROR] {error_msg}")

        # DALL-E 관련 오류 메시지 개선
        if "content_policy" in error_msg.lower():
            return jsonify({"ok": False, "error": "이미지 생성이 콘텐츠 정책에 위배됩니다. 프롬프트를 수정해주세요."}), 200
        elif "rate_limit" in error_msg.lower():
            return jsonify({"ok": False, "error": "API 요청 한도를 초과했습니다. 잠시 후 다시 시도해주세요."}), 200

        return jsonify({"ok": False, "error": error_msg}), 200


# ===== Render 배포를 위한 설정 =====
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5059))
    app.run(host="0.0.0.0", port=port, debug=False)
