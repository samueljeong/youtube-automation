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


# ===== 강의안 생성 시스템 프롬프트 =====
LESSON_PLAN_SYSTEM_PROMPT = """역할: 당신은 20년 경력의 교회 교육 전문가이자 강의안 작성 마스터입니다.
목표: 누구나 이 강의안만 보고도 훌륭하게 강의를 인도할 수 있도록, 실제 사용 가능한 완전한 강의 스크립트를 작성합니다.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
【핵심 원칙】
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1. "대본 수준"으로 작성
   - 강사가 읽기만 해도 강의가 되는 완전한 스크립트
   - 모든 말을 따옴표로 직접 제시: "여러분, 오늘 함께 나눌 주제는..."
   - 어색한 침묵이 없도록 전환 멘트도 포함

2. 참여자 반응 예측 및 대응
   - 예상 질문과 답변 예시
   - 분위기가 처질 때 활용할 수 있는 백업 활동
   - "만약 ~한 반응이 나오면, ~하게 대응하세요"

3. 시간 관리 구체화
   - 각 섹션별 정확한 시간 표기 (예: [10:00-10:15] 도입)
   - 시간 초과 시 줄일 수 있는 부분 표시 (⏱️생략가능)
   - 시간 여유 시 확장할 수 있는 부분 표시 (⏱️확장가능)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
【강의안 구조 템플릿】
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

■ 강의 개요
- 회차/제목
- 핵심 목표 (한 문장)
- 오늘의 핵심 메시지 (참가자가 기억할 한 문장)
- 준비물 체크리스트

■ 사전 준비 (강의 시작 전)
- 공간 세팅
- 자료 배치
- 참가자 맞이 준비

■ 도입부 [시간]
- 환영 인사 (정확한 멘트)
- 아이스브레이크 활동 (진행 방법 상세히)
- 지난 시간 연결 (있는 경우)
- 오늘 주제 소개 멘트

■ 본론 [시간]
- 각 핵심 포인트별로:
  · 도입 멘트
  · 성경 말씀 (본문 전체 기재)
  · 설명 스크립트
  · 예화/사례 (구체적으로)
  · 질문 & 나눔 포인트
  · 전환 멘트

■ 활동/나눔 [시간]
- 활동 명칭
- 진행 방법 (1, 2, 3 단계로)
- 강사 역할과 멘트
- 나눔 질문 (3-4개)
- 마무리 방법

■ 적용 & 결단 [시간]
- 삶 적용 포인트 제시
- 결단/다짐 시간 인도
- 기도 (기도문 전문 제공)

■ 마무리 [시간]
- 핵심 요약 멘트
- 과제/숙제 안내
- 다음 시간 예고
- 마무리 인사

■ 강사 노트
- 주의할 점
- 흔한 실수와 대처법
- 추가 참고 자료

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
【작성 스타일 가이드】
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

✅ 좋은 예시:
"자, 여러분 안녕하세요! 오늘도 이렇게 함께 모인 것 정말 감사합니다.
혹시 이번 한 주 어떻게 지내셨어요? (2-3명 짧게 나누도록 유도)
네, 감사합니다. 오늘 우리가 함께 나눌 주제는 바로 '예배자의 마음'입니다.
성경에서 다윗은 어떤 마음으로 하나님을 예배했을까요?"

❌ 나쁜 예시:
- 인사
- 지난 주 복습
- 오늘 주제 소개
(이렇게 개조식으로만 쓰면 강의 불가)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
【필수 포함 요소】
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1. 성경 본문: 관련 말씀 전문 기재 (장, 절 포함)
2. 기도문: 도입 기도, 마무리 기도 전문
3. 예화: 최소 2개 이상의 구체적인 사례/이야기
4. 나눔 질문: 최소 4개 이상의 토론 질문
5. 적용 포인트: 실생활에서 실천할 구체적인 행동 2-3가지

분량: 90분 강의 기준 A4 5-7페이지 분량으로 충분히 상세하게 작성하세요."""


# ===== 강의안 생성 (고급) 시스템 프롬프트 =====
LESSON_PLAN_ADVANCED_PROMPT = """당신은 최고 수준의 교회 교육 콘텐츠 개발자입니다.

【미션】
제공된 회차 정보를 바탕으로, 처음 강의하는 사람도 자신감 있게 인도할 수 있는
완벽한 강의 스크립트를 작성하세요.

【차별화 포인트】
이 강의안은 단순한 개요가 아닙니다. 다음을 반드시 포함해야 합니다:

1. 🎤 실제 말할 대사 (따옴표로 표시)
   예: "여러분, 혹시 이런 경험 있으신가요? 열심히 찬양을 준비했는데..."

2. 📖 성경 본문 전체 (개역개정 기준)
   단순히 "요한복음 15:5을 읽습니다"가 아닌, 본문 전체를 기재

3. 📚 풍성한 예화와 사례
   - 실제 교회 현장에서 있을 법한 에피소드
   - 역사적 인물이나 믿음의 선배들 이야기
   - 일상에서 공감할 수 있는 비유

4. ❓ 생각을 여는 질문들
   - 단답형이 아닌 열린 질문
   - 깊은 나눔을 이끌어내는 후속 질문
   - 조용한 참가자도 참여할 수 있는 가벼운 질문

5. 🙏 완전한 기도문
   - 시작 기도, 본문 묵상 기도, 마무리 기도 전문
   - 강사가 그대로 읽어도 자연스러운 기도

6. ⏱️ 정확한 시간 배분
   - 각 섹션 시작/종료 시간
   - 시간 조절이 필요할 때 가감할 부분 표시

7. 💡 강사 팁
   - "이 부분에서 참가자들이 어려워할 수 있습니다. 천천히..."
   - "분위기가 무거우면 여기서 잠깐 쉬어가세요"
   - "시간이 부족하면 이 활동은 생략 가능합니다"

【형식】
- 마크다운 없이 순수 텍스트
- 번호와 기호로 명확하게 구조화
- 【】로 섹션 구분
- 중요 포인트는 ★로 표시

【분량 기준】
- 30분 강의: 최소 2000자
- 60분 강의: 최소 4000자
- 90분 강의: 최소 6000자
- 120분 강의: 최소 8000자

절대로 개조식으로만 작성하지 마세요.
강사가 이 문서만 들고 가도 완벽하게 강의할 수 있어야 합니다."""


@education_bp.route("/api/education/generate-lesson-plan", methods=["POST"])
def education_generate_lesson_plan():
    """특정 회차 강의안 생성 API"""
    global _client

    if not _client:
        return jsonify({"status": "error", "message": "OpenAI 클라이언트가 초기화되지 않았습니다."}), 500

    try:
        data = request.json
        if not data:
            return jsonify({"status": "error", "message": "입력 데이터가 없습니다."}), 400

        program_info = data.get("program_info", {})
        curriculum_summary = data.get("curriculum_summary", {})
        session_info = data.get("session_info", {})
        model = data.get("model", "gpt-4o")
        quality = data.get("quality", "detailed")  # "basic" or "detailed"

        # 지원 모델 검증 - GPT-5.1 시리즈 포함
        supported_models = [
            "gpt-5.1", "gpt-5.1-mini",  # 최신 GPT-5.1 시리즈
            "gpt-4o", "gpt-4o-mini", "gpt-4.1", "gpt-4.1-mini",  # GPT-4 시리즈
            "o1", "o1-mini", "o3-mini"  # 추론 모델
        ]
        if model not in supported_models:
            model = "gpt-5.1"  # 기본값을 최신 모델로

        # 회당 시간 가져오기
        session_duration = program_info.get('schedule', {}).get('session_duration_min', 90)

        # 사용자 메시지 구성 - 더 상세하게
        user_message = f"""다음 정보를 바탕으로 {session_info.get('session_number', 1)}회차 강의안을 작성해주세요.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
【프로그램 정보】
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
• 교육명: {program_info.get('program_basic', {}).get('title', '교육 프로그램')}
• 프로그램 유형: {program_info.get('program_basic', {}).get('program_type', '')}
• 대상: {program_info.get('program_basic', {}).get('target_group', '')}
• 예상 인원: {program_info.get('program_basic', {}).get('participants_count', '미정')}명
• 참가자 연령대: {program_info.get('program_basic', {}).get('age_range', '')}
• 사역 맥락: {program_info.get('program_basic', {}).get('ministry_context', '')}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
【교육 목표】
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
• 핵심 목표: {program_info.get('goals', {}).get('main_goal', '')}
• 부목표: {', '.join(program_info.get('goals', {}).get('sub_goals', []))}
• 프로그램 목적: {curriculum_summary.get('purpose_statement', '')}
• 기대 성과: {', '.join(curriculum_summary.get('key_outcomes', []))}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
【참가자 현황】
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
• 참가자 수준: {program_info.get('current_status', {}).get('participants_level', '혼합')}
• 강점: {program_info.get('current_status', {}).get('strengths', '')}
• 해결할 문제: {program_info.get('current_status', {}).get('problems', '')}
• 특별 상황: {program_info.get('current_status', {}).get('special_context', '')}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
【{session_info.get('session_number', 1)}회차 상세 정보】
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
• 회차: {session_info.get('session_number', 1)}회차
• 제목: {session_info.get('title', '')}
• 이 회차 목표: {session_info.get('objective', '')}
• 강의 시간: {session_duration}분

• 시간 배분 계획:
{chr(10).join([f"  - {t.get('segment', '')}: {t.get('minutes', '')}분" for t in session_info.get('time_plan', [])])}

• 핵심 내용:
{chr(10).join([f"  - {c}" for c in session_info.get('key_contents', [])])}

• 활동/나눔:
{chr(10).join([f"  - {a}" for a in session_info.get('activities', [])])}

• 준비물: {', '.join(session_info.get('materials', []))}
• 숙제/적용: {session_info.get('homework', '')}
• 리더를 위한 메모: {session_info.get('notes_for_leader', '')}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
【요청사항】
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
위 정보를 바탕으로, {session_duration}분 분량의 완전한 강의 스크립트를 작성해주세요.
이 강의안만 있으면 누구나 강의를 훌륭하게 인도할 수 있어야 합니다.
개조식이 아닌, 실제로 말할 대사까지 포함된 상세한 강의안을 작성해주세요."""

        # 품질에 따른 프롬프트 선택
        system_prompt = LESSON_PLAN_ADVANCED_PROMPT if quality == "detailed" else LESSON_PLAN_SYSTEM_PROMPT

        # 모델별 파라미터 조정
        api_params = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message}
            ]
        }

        # o1 계열은 temperature, max_tokens 미지원
        if model.startswith("o1") or model.startswith("o3"):
            api_params["max_completion_tokens"] = 8000
        else:
            api_params["temperature"] = 0.7
            api_params["max_tokens"] = 8000

        # OpenAI API 호출
        response = _client.chat.completions.create(**api_params)

        lesson_plan = response.choices[0].message.content

        # 토큰 사용량
        usage = {
            "input_tokens": response.usage.prompt_tokens,
            "output_tokens": response.usage.completion_tokens,
            "total_tokens": response.usage.total_tokens,
            "model": model
        }

        return jsonify({
            "status": "ok",
            "lesson_plan": lesson_plan,
            "usage": usage
        })

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500
