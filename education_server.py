# education_server.py
# 교육 프로그램 설계 Blueprint

import os
import json
from flask import Blueprint, render_template, request, jsonify
from openai import OpenAI

education_bp = Blueprint("education", __name__)

# OpenAI 클라이언트 (sermon_server에서 초기화 후 주입)
_client = None

def init_education_api(client):
    """OpenAI 클라이언트 초기화"""
    global _client
    _client = client

# ===== 시스템 프롬프트 =====
EDUCATION_SYSTEM_PROMPT = """역할: 너는 '교회 교육 프로그램 기획자 + 커리큘럼 디자이너'다.
입력: 교회 교육 프로그램에 대한 JSON 하나를 입력으로 받는다.
출력: 입력을 분석하여, 교육 목적에 맞는 커리큘럼과 회차별 교육안을 설계한 뒤, 지정된 JSON 형식으로만 응답한다.

[중요 규칙]

1. 출력 형식
- 반드시 유효한 JSON만 출력한다.
- JSON 바깥에 설명, 마크다운, 주석, 자연어 문장을 넣지 않는다.
- key 순서는 아래 스키마 순서를 기본으로 유지한다.

2. 톤 & 맥락
- 한국 교회 현실을 전제로 한다.
- 실제 현장에서 바로 사용할 수 있는 구체적인 교육안을 만든다.
- 너무 학문적이거나 추상적으로 쓰지 말고, 참여자 눈높이에 맞춘다.
- program_basic.program_type, target_group, goals를 참고해 톤과 사례를 조정한다.

3. 구조 원칙
- 먼저 프로그램 전체를 한 문단으로 요약한다.
- 그 다음, 회차별 흐름이 한 눈에 보이도록 커리큘럼 개요를 만든다.
- 각 회차마다: 목표, 시간배분, 핵심 내용, 활동, 준비물, 숙제/적용, 리더 메모까지 설계한다.
- 요청된 경우에만 공지문/평가문항을 생성한다 (output_preferences 참고).

4. 출력 JSON 스키마

{
  "program_summary": {
    "title": string,
    "target_overview": string,
    "duration_overview": string,
    "purpose_statement": string,
    "key_outcomes": string[]
  },
  "curriculum_outline": {
    "sessions": [
      {
        "session_number": number,
        "title": string,
        "core_theme": string,
        "main_objective": string,
        "keywords": string[]
      }
    ]
  },
  "sessions_detail": [
    {
      "session_number": number,
      "title": string,
      "objective": string,
      "time_plan": [
        {
          "segment": string,
          "minutes": number
        }
      ],
      "key_contents": string[],
      "activities": string[],
      "materials": string[],
      "homework": string|null,
      "notes_for_leader": string
    }
  ],
  "announcements": {
    "kakao_short": string|null,
    "bulletin": string|null
  },
  "evaluation": {
    "feedback_questions": string[]
  }
}

- output_preferences를 반드시 존중하라:
  - need_curriculum_outline이 false이면 curriculum_outline.sessions는 빈 배열로 둔다.
  - need_detailed_session_plans가 false이면 sessions_detail은 빈 배열로 둔다.
  - need_announcement_text가 false이면 announcements의 값들을 null로 둔다.
  - need_homework_idea가 false이면 각 세션의 homework는 null로 둔다.
  - need_evaluation_items가 false이면 evaluation.feedback_questions는 빈 배열로 둔다.

5. 기타
- 총 회차 수(schedule.total_sessions)에 맞춰 sessions와 sessions_detail을 생성한다.
- detail_level이 simple일 때는 간단히, deep일 때는 더 풍부하게 작성하되, 구조는 유지한다.
- tone에 맞춰 표현을 조절하되, 너무 과한 구어체는 피하고, 예배/교육 현장에 적합한 자연스러운 한국어를 사용한다."""


# ===== 라우트 =====

@education_bp.route("/education")
def education_page():
    """교육 페이지 렌더링"""
    return render_template("education.html")


@education_bp.route("/api/education/generate", methods=["POST"])
def education_generate():
    """교육 커리큘럼 생성 API"""
    global _client

    if not _client:
        return jsonify({"status": "error", "message": "OpenAI 클라이언트가 초기화되지 않았습니다."}), 500

    try:
        data = request.json
        if not data:
            return jsonify({"status": "error", "message": "입력 데이터가 없습니다."}), 400

        # 사용자 메시지 구성
        user_message = f"""다음은 교회 교육 프로그램에 대한 입력 JSON입니다. 위에서 정의한 규칙대로, 출력 JSON만 생성하세요.

입력 JSON:
{json.dumps(data, ensure_ascii=False, indent=2)}"""

        # OpenAI API 호출
        response = _client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": EDUCATION_SYSTEM_PROMPT},
                {"role": "user", "content": user_message}
            ],
            temperature=0.7,
            max_tokens=8000,
            response_format={"type": "json_object"}
        )

        result_text = response.choices[0].message.content
        result_json = json.loads(result_text)

        # 토큰 사용량
        usage = {
            "input_tokens": response.usage.prompt_tokens,
            "output_tokens": response.usage.completion_tokens,
            "total_tokens": response.usage.total_tokens
        }

        return jsonify({
            "status": "ok",
            "result": result_json,
            "usage": usage
        })

    except json.JSONDecodeError as e:
        return jsonify({"status": "error", "message": f"JSON 파싱 오류: {str(e)}"}), 500
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@education_bp.route("/api/education/save", methods=["POST"])
def education_save():
    """교육 결과 저장 API"""
    try:
        data = request.json
        if not data:
            return jsonify({"status": "error", "message": "저장할 데이터가 없습니다."}), 400

        # data/education 폴더 확인
        save_dir = os.path.join(os.path.dirname(__file__), "data", "education")
        os.makedirs(save_dir, exist_ok=True)

        # 파일명 생성 (타이틀 + 타임스탬프)
        from datetime import datetime
        title = data.get("program_basic", {}).get("title", "교육")
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{title}_{timestamp}.json"

        # 파일명에서 특수문자 제거
        import re
        filename = re.sub(r'[\\/*?:"<>|]', "", filename)

        filepath = os.path.join(save_dir, filename)

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        return jsonify({
            "status": "ok",
            "message": "저장되었습니다.",
            "filename": filename
        })

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@education_bp.route("/api/education/list", methods=["GET"])
def education_list():
    """저장된 교육 목록 조회"""
    try:
        save_dir = os.path.join(os.path.dirname(__file__), "data", "education")

        if not os.path.exists(save_dir):
            return jsonify({"status": "ok", "files": []})

        files = []
        for filename in os.listdir(save_dir):
            if filename.endswith(".json"):
                filepath = os.path.join(save_dir, filename)
                with open(filepath, "r", encoding="utf-8") as f:
                    data = json.load(f)

                files.append({
                    "filename": filename,
                    "title": data.get("program_basic", {}).get("title", "제목 없음"),
                    "program_type": data.get("program_basic", {}).get("program_type", ""),
                    "created_at": filename.split("_")[-2] if "_" in filename else ""
                })

        # 최신순 정렬
        files.sort(key=lambda x: x["filename"], reverse=True)

        return jsonify({"status": "ok", "files": files})

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@education_bp.route("/api/education/load/<filename>", methods=["GET"])
def education_load(filename):
    """저장된 교육 데이터 불러오기"""
    try:
        save_dir = os.path.join(os.path.dirname(__file__), "data", "education")
        filepath = os.path.join(save_dir, filename)

        if not os.path.exists(filepath):
            return jsonify({"status": "error", "message": "파일을 찾을 수 없습니다."}), 404

        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)

        return jsonify({"status": "ok", "data": data})

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@education_bp.route("/api/education/delete/<filename>", methods=["DELETE"])
def education_delete(filename):
    """저장된 교육 데이터 삭제"""
    try:
        save_dir = os.path.join(os.path.dirname(__file__), "data", "education")
        filepath = os.path.join(save_dir, filename)

        if not os.path.exists(filepath):
            return jsonify({"status": "error", "message": "파일을 찾을 수 없습니다."}), 404

        os.remove(filepath)

        return jsonify({"status": "ok", "message": "삭제되었습니다."})

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500
