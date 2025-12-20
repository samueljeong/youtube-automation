"""
api_sermon.py
설교 처리 관련 API Blueprint

포함된 라우트:
- POST /api/sermon/process      - Step 처리 (Step1, Step2)
- POST /api/sermon/meditation   - 묵상메시지 생성
- POST /api/sermon/gpt-pro      - GPT PRO (Step3)
- POST /api/sermon/qa           - Q&A 질의응답
- POST /api/sermon/recommend-scripture - 본문 추천
- POST /api/sermon/chat         - 설교 챗봇

사용법:
    from sermon_modules.api_sermon import api_sermon_bp, init_sermon_api
    init_sermon_api(client)  # OpenAI 클라이언트 주입
    app.register_blueprint(api_sermon_bp)
"""

import json
import time
import hashlib
import threading
from flask import Blueprint, request, jsonify, session

from .db import get_db_connection, USE_POSTGRES
from .utils import (
    calculate_cost, format_json_result, remove_markdown,
    is_json_guide, parse_json_guide
)
from .auth import (
    api_login_required, AUTH_ENABLED,
    get_user_credits, use_credit
)
from .prompt import (
    get_system_prompt_for_step, build_prompt_from_json, build_step3_prompt_from_json
)
from .strongs import analyze_verse_strongs, format_strongs_for_prompt
from .commentary import (
    init_commentary_service, get_verse_commentary, format_commentary_for_prompt
)
from .context import get_current_context, format_context_for_prompt, init_context_service

api_sermon_bp = Blueprint('api_sermon', __name__, url_prefix='/api/sermon')

# OpenAI 클라이언트 (init_sermon_api에서 주입)
_client = None


def init_sermon_api(client):
    """OpenAI 클라이언트 주입"""
    global _client
    _client = client
    # Commentary 서비스 초기화 (GPT 기반 주석 생성용)
    init_commentary_service(client)
    # Context 서비스 초기화 (예화 검증용)
    init_context_service(client)


def get_client():
    """OpenAI 클라이언트 반환"""
    if _client is None:
        raise RuntimeError("OpenAI client not initialized. Call init_sermon_api() first.")
    return _client


# ===== 헬퍼 함수들 =====

def log_api_usage(step_name, model_name, input_tokens=0, output_tokens=0, style_name=None, category=None, user_id=None):
    """API 사용량을 DB에 기록"""
    try:
        total_tokens = input_tokens + output_tokens
        estimated_cost = calculate_cost(model_name, input_tokens, output_tokens)

        conn = get_db_connection()
        cursor = conn.cursor()
        if USE_POSTGRES:
            cursor.execute('''
                INSERT INTO api_usage_logs (step_name, model_name, style_name, category, input_tokens, output_tokens, total_tokens, estimated_cost_usd, user_id)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            ''', (step_name, model_name, style_name, category, input_tokens, output_tokens, total_tokens, estimated_cost, user_id))
        else:
            cursor.execute('''
                INSERT INTO api_usage_logs (step_name, model_name, style_name, category, input_tokens, output_tokens, total_tokens, estimated_cost_usd, user_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (step_name, model_name, style_name, category, input_tokens, output_tokens, total_tokens, estimated_cost, user_id))
        conn.commit()
        conn.close()
        print(f"[USAGE-LOG] {step_name} - {model_name}: {total_tokens} tokens, ${estimated_cost:.6f}")
        return True
    except Exception as e:
        print(f"[USAGE-LOG] 기록 실패: {e}")
        return False


def save_step1_analysis(reference, sermon_text, analysis_text, category="", style_name="", step_name="step1"):
    """
    Step1 본문 분석 결과를 자동으로 DB에 저장
    """
    try:
        client = get_client()

        # 분석 해시 생성 (중복 체크용)
        hash_content = f"{reference}|{analysis_text}"
        analysis_hash = hashlib.md5(hash_content.encode('utf-8')).hexdigest()

        # DB 기반 중복 체크
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
                print(f"[STEP1-SAVE] 중복 분석 감지 (해시: {analysis_hash[:8]}...) - 저장 건너뜀")
                return {"ok": True, "message": "중복 분석 - 저장 건너뜀", "isDuplicate": True}
        except Exception as e:
            print(f"[STEP1-SAVE] 중복 체크 실패: {str(e)}")

        print(f"[STEP1-SAVE] Step1 분석 저장 시작 - 본문: {reference[:30]}...")

        # GPT로 분석 품질 평가
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
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": evaluation_system},
                    {"role": "user", "content": evaluation_user}
                ],
                temperature=0.3
            )

            eval_result = eval_completion.choices[0].message.content.strip()
            # JSON 파싱
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


def analyze_sermon_for_benchmark(sermon_text, reference="", sermon_title="", category="", style_name=""):
    """
    생성된 설교문을 자동으로 분석하여 DB에 저장
    """
    try:
        client = get_client()

        # 설교문 해시 생성 (중복 체크용)
        sermon_hash = hashlib.md5(sermon_text.encode('utf-8')).hexdigest()

        # DB 기반 중복 체크
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


# ===== API 라우트들 =====

@api_sermon_bp.route('/process', methods=['POST'])
@api_login_required
def process_step():
    """단일 처리 단계 실행 (gpt-4o-mini 사용)"""
    try:
        client = get_client()
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
            if step_type == "step1":
                model_name = "gpt-5"
            else:
                model_name = "gpt-4o-mini"

        # temperature 설정 (gpt-4o-mini만 사용)
        use_temperature = (model_name == "gpt-4o-mini")

        print(f"[PROCESS] {category} - {step_name} (Step: {step_type}, 모델: {model_name})")

        # JSON 지침 여부 확인
        is_json = is_json_guide(guide)
        json_guide = None

        if is_json:
            json_guide = parse_json_guide(guide)
            if json_guide:
                print(f"[PROCESS] JSON 지침 감지됨 - style: {json_guide.get('style', 'unknown')}")
                system_content = build_prompt_from_json(json_guide, step_type)
            else:
                print(f"[PROCESS] JSON 파싱 실패 - 기존 텍스트 방식 사용")
                is_json = False

        if not is_json:
            # Step1인 경우: 본문 연구 전용 프롬프트 사용
            if step_type == "step1":
                from .prompt import build_step1_research_prompt
                system_content = build_step1_research_prompt()
                print(f"[PROCESS] Step1 연구 모드 프롬프트 적용")
            else:
                system_content = get_system_prompt_for_step(step_name)

                if master_guide:
                    system_content += f"\n\n【 카테고리 총괄 지침 】\n{master_guide}\n\n"
                    system_content += f"【 현재 단계 역할 】\n{step_name}\n\n"
                    system_content += "위 총괄 지침을 참고하여, 현재 단계의 역할과 비중에 맞게 '자료만' 작성하세요."

                if guide:
                    system_content += f"\n\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                    system_content += f"【 최우선 지침: {step_name} 단계 세부 지침 】\n"
                    system_content += f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                    system_content += guide
                    system_content += f"\n\n위 지침을 절대적으로 우선하여 따라야 합니다."
                    system_content += f"\n이 지침이 기본 역할과 충돌하면, 이 지침을 따르세요."

        # 사용자 메시지 구성
        user_content = f"[성경구절]\n{reference}\n\n"

        if title and '제목' not in step_name:
            user_content += f"[설교 제목]\n{title}\n\n"
            user_content += "위 제목을 염두에 두고 모든 내용을 작성해주세요.\n\n"

        if text:
            user_content += f"[성경 본문]\n{text}\n\n"

        # Step1인 경우: 원어 분석 및 주석 데이터 자동 추가
        if step_type == "step1" and reference:
            try:
                # 1. Strong's 원어 분석
                strongs_analysis = analyze_verse_strongs(reference, top_n=5)
                strongs_text = format_strongs_for_prompt(strongs_analysis)
                if strongs_text:
                    # Strong's 우선순위 강제 문구 추가
                    user_content += "\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                    user_content += "【 ⚠️ Strong's 원어 자료 (보조 참고용) 】\n"
                    user_content += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                    user_content += "※ 주의: Strong's는 참고로만 사용하며, 본문 구조/문맥/역사 배경 설명을 먼저 완료하라.\n"
                    user_content += "※ 원어 분석은 최대 5개 단어만 선택하고, 설교 적용은 쓰지 말라(관찰만).\n\n"
                    user_content += f"{strongs_text}\n"
                    print(f"[PROCESS] Step1 원어 분석 추가 (우선순위 강제): {len(strongs_analysis.get('key_words', []))}개 단어")

                # 2. 주석 참고 자료 (GPT 기반 생성)
                # 비용 절감을 위해 기본적으로 비활성화, 필요시 활성화
                enable_commentary = data.get("enableCommentary", False)
                if enable_commentary:
                    commentary_result = get_verse_commentary(
                        reference,
                        verse_text=text,
                        styles=["matthew_henry", "john_gill"]
                    )
                    commentary_text = format_commentary_for_prompt(commentary_result)
                    if commentary_text:
                        user_content += f"\n{commentary_text}\n"
                        print(f"[PROCESS] Step1 주석 참고 추가: {len(commentary_result.get('commentaries', []))}개 스타일")
            except Exception as e:
                print(f"[PROCESS] 원어/주석 분석 실패 (무시): {e}")

        # Step2인 경우: 시대 컨텍스트 자동 추가
        if step_type == "step2" or (step_id and "step2" in step_id.lower()):
            try:
                # 청중 유형 추출 (data에서 또는 기본값)
                audience_type = data.get("audienceType", "전체")
                enable_context = data.get("enableContext", True)  # 기본 활성화

                if enable_context:
                    context_result = get_current_context(audience_type=audience_type)
                    context_text = format_context_for_prompt(context_result, sermon_topic=title or "")
                    if context_text:
                        user_content += f"\n{context_text}\n"
                        news_count = sum(len(v) for v in context_result.get("news", {}).values())
                        print(f"[PROCESS] Step2 시대 컨텍스트 추가: {audience_type} 청중, {news_count}개 뉴스")
            except Exception as e:
                print(f"[PROCESS] 시대 컨텍스트 분석 실패 (무시): {e}")

        if previous_results:
            user_content += "[이전 단계 결과 (참고용)]\n"
            for prev_id, prev_data in previous_results.items():
                user_content += f"\n### {prev_data['name']}\n{prev_data['result']}\n"
            user_content += "\n"

        if '제목' in step_name:
            user_content += f"위 성경 본문({reference})에 적합한 설교 제목을 정확히 3개만 제안해주세요.\n"
            user_content += "각 제목은 한 줄로, 번호나 기호 없이 작성하세요."
        else:
            user_content += f"위 내용을 바탕으로 '{step_name}' 단계를 작성해주세요.\n"

        if title and '제목' not in step_name:
            user_content += f"\n제목 '{title}'을 고려하여 작성하세요."

        # GPT 호출
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

        # 토큰 사용량 추출
        usage_data = None
        if hasattr(completion, 'usage') and completion.usage:
            usage_data = {
                "input_tokens": completion.usage.prompt_tokens,
                "output_tokens": completion.usage.completion_tokens,
                "total_tokens": completion.usage.total_tokens
            }
            log_api_usage(
                step_name=step_id or step_type or 'step',
                model_name=model_name,
                input_tokens=usage_data['input_tokens'],
                output_tokens=usage_data['output_tokens'],
                style_name=data.get('styleName'),
                category=category
            )

        # 제목 추천 단계는 JSON 파싱하지 않고 그대로 반환
        if '제목' in step_name:
            result = remove_markdown(result)
            return jsonify({"ok": True, "result": result, "usage": usage_data})

        # Step1/Step2 추가 정보 수집 (Step4에서 사용)
        extra_info = {}

        # Step1인 경우: Strong's 원어 분석 정보 추가
        if step_type == "step1" and reference:
            try:
                strongs_analysis = analyze_verse_strongs(reference, top_n=5)
                if strongs_analysis and not strongs_analysis.get('error'):
                    extra_info['strongs_analysis'] = {
                        'reference': strongs_analysis.get('reference', ''),
                        'text': strongs_analysis.get('text', ''),
                        'key_words': strongs_analysis.get('key_words', [])
                    }
                    print(f"[PROCESS] Step1 extra_info: Strong's {len(strongs_analysis.get('key_words', []))}개 단어")
            except Exception as e:
                print(f"[PROCESS] Strong's 추가 정보 수집 실패 (무시): {e}")

        # Step2인 경우: 시대 컨텍스트 정보 추가
        if step_type == "step2" or (step_id and "step2" in step_id.lower()):
            try:
                audience_type = data.get("audienceType", "전체")
                context_result = get_current_context(audience_type=audience_type)
                if context_result:
                    extra_info['context_data'] = {
                        'audience': context_result.get('audience', '전체'),
                        'news': context_result.get('news', {}),
                        'indicators': context_result.get('indicators', {}),
                        'concerns': context_result.get('concerns', [])
                    }
                    news_count = sum(len(v) for v in context_result.get("news", {}).values())
                    print(f"[PROCESS] Step2 extra_info: 시대 컨텍스트 {news_count}개 뉴스")
            except Exception as e:
                print(f"[PROCESS] 시대 컨텍스트 추가 정보 수집 실패 (무시): {e}")

        # JSON 파싱 시도 (선택적)
        try:
            cleaned_result = result
            if cleaned_result.startswith('```'):
                lines = cleaned_result.split('\n')
                if lines[0].startswith('```'):
                    lines = lines[1:]
                if lines and lines[-1].startswith('```'):
                    lines = lines[:-1]
                cleaned_result = '\n'.join(lines).strip()

            json_data = json.loads(cleaned_result)
            formatted_result = format_json_result(json_data)

            print(f"[PROCESS][SUCCESS] JSON 형식으로 응답받아 포맷팅 완료")

            # Step1인 경우 백그라운드로 DB 저장
            if step_type == "step1" or step_id == "step1":
                try:
                    save_thread = threading.Thread(
                        target=save_step1_analysis,
                        args=(reference, text, formatted_result, category, data.get("styleName", ""), step_id)
                    )
                    save_thread.daemon = True
                    save_thread.start()
                    print(f"[PROCESS] Step1 분석 저장 백그라운드 시작")
                except Exception as e:
                    print(f"[PROCESS] Step1 저장 시작 실패 (무시): {str(e)}")

            response = {"ok": True, "result": formatted_result, "usage": usage_data}
            if extra_info:
                response["extraInfo"] = extra_info
            return jsonify(response)

        except json.JSONDecodeError:
            print(f"[PROCESS][INFO] 텍스트 형식으로 응답받음 (JSON 아님)")
            result = remove_markdown(result)

            if step_type == "step1" or step_id == "step1":
                try:
                    save_thread = threading.Thread(
                        target=save_step1_analysis,
                        args=(reference, text, result, category, data.get("styleName", ""), step_id)
                    )
                    save_thread.daemon = True
                    save_thread.start()
                    print(f"[PROCESS] Step1 분석 저장 백그라운드 시작")
                except Exception as e:
                    print(f"[PROCESS] Step1 저장 시작 실패 (무시): {str(e)}")

            response = {"ok": True, "result": result, "usage": usage_data}
            if extra_info:
                response["extraInfo"] = extra_info
            return jsonify(response)

    except Exception as e:
        print(f"[PROCESS][ERROR] {str(e)}")
        return jsonify({"ok": False, "error": str(e)}), 200


@api_sermon_bp.route('/meditation', methods=['POST'])
@api_login_required
def create_meditation():
    """묵상메시지 생성 (GPT-4o-mini 사용)"""
    try:
        client = get_client()
        data = request.get_json()
        if not data:
            return jsonify({"ok": False, "error": "No data received"}), 400

        reference = data.get("reference", "")
        verse = data.get("verse", "")
        template = data.get("template", "")
        date_str = data.get("dateStr", "")
        sender = data.get("sender", "")

        if not reference:
            return jsonify({"ok": False, "error": "성경구절을 입력해주세요."}), 400
        if not verse:
            return jsonify({"ok": False, "error": "본문말씀을 입력해주세요."}), 400

        print(f"[Meditation] 묵상메시지 생성 시작 - 구절: {reference}, 템플릿 사용: {'예' if template else '아니오'}")

        if template:
            # 템플릿에 placeholder가 있는지 확인
            has_placeholder = "{{" in template and "}}" in template

            if has_placeholder:
                # placeholder 방식: GPT는 묵상, 제목, 인용구만 생성
                system_content = """당신은 묵상메시지를 작성하는 전문가입니다.
사용자가 제공한 샘플 템플릿의 스타일(어조, 문단 구조, 길이)을 참고하여 묵상 내용을 작성합니다.

반드시 JSON 형식으로만 응답하세요:
{
  "제목": "말씀의 핵심을 담은 짧은 제목 (10자 이내)",
  "인용구": "본문에서 핵심 메시지를 요약한 짧은 문장",
  "묵상": "샘플과 비슷한 스타일의 묵상 내용"
}

주의사항:
- 샘플의 묵상 부분 스타일(문단 수, 문장 길이, 어조)을 따라하세요
- 마크다운 기호 사용 금지
- JSON 외의 다른 텍스트 출력 금지"""

                user_content = f"""[참고할 샘플]
{template}

[새 말씀 정보]
성경구절: {reference}
본문말씀: {verse}

위 샘플의 스타일을 참고하여 JSON으로 응답하세요."""
            else:
                # 기존 방식: GPT가 전체 메시지 생성
                system_content = """당신은 묵상메시지 양식을 정확히 복제하는 전문가입니다.

매우 중요: 사용자가 제공한 샘플 템플릿의 "전체 형식"을 완벽히 모방해야 합니다.
사용자가 제공하는 날짜, 성경구절, 본문말씀 값을 샘플 템플릿의 형식에 맞춰 대체하세요.

필수 준수 사항:
1. 샘플의 전체 구조(제목, 날짜 형식, 성경구절 표기 방식, 본문, 묵상 내용, 해시태그 등)를 동일하게 유지
2. 샘플의 문단 수, 문장 길이, 어조를 동일하게 유지
3. 샘플에 이모지, 해시태그, 특수 기호가 있으면 동일한 위치에 동일하게 사용
4. 샘플의 전체 글자 수와 비슷하게 작성 (±20% 이내)

절대 하지 말 것:
- 샘플과 다른 구조로 작성
- 마크다운 기호(#, *, - 등) 사용 (해시태그 제외)

전체 메시지를 작성하세요."""

                sender_info = f"\n보내는 사람: {sender}" if sender else ""

                user_content = f"""[복제할 샘플 양식]
{template}

---

[새로 작성할 내용의 값]
날짜: {date_str}
성경구절: {reference}
본문말씀: {verse}{sender_info}

위 샘플의 "전체 형식"을 완벽히 따라서 새 묵상메시지를 작성하세요."""
        else:
            system_content = """당신은 따뜻하고 은혜로운 묵상메시지를 작성하는 전문가입니다.
주어진 성경구절과 본문말씀을 바탕으로 깊이 있는 묵상메시지를 작성합니다.

작성 지침:
1. 첫 번째 문단: 성경 본문의 역사적/신학적 배경 설명 (3-4문장)
2. 두 번째 문단: 우리 일상에서의 적용과 성찰 (3-4문장)
3. 세 번째 문단: 따뜻한 권면과 축복의 말씀 (2-3문장)
4. 마지막: 짧은 기도문 (선택)
5. 따뜻하고 위로가 되는 어조 사용
6. 마크다운 기호 사용하지 않고 순수 텍스트로 작성
7. 날짜, 성경구절, 본문말씀은 제외하고 묵상 내용만 작성"""

            user_content = f"""성경구절: {reference}
본문말씀: {verse}

위 말씀을 바탕으로 오늘의 묵상메시지를 작성해주세요.
날짜, 성경구절, 본문말씀 부분은 제외하고 묵상 본문만 작성해주세요."""

        completion = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_content},
                {"role": "user", "content": user_content}
            ],
            temperature=0.7,
            max_tokens=1500
        )

        result = completion.choices[0].message.content.strip()
        print(f"[Meditation] 생성 완료 - 길이: {len(result)}자")

        # placeholder 모드일 때 JSON 파싱
        response_data = {
            "ok": True,
            "usage": {
                "input_tokens": completion.usage.prompt_tokens if hasattr(completion, 'usage') else 0,
                "output_tokens": completion.usage.completion_tokens if hasattr(completion, 'usage') else 0
            }
        }

        if template and "{{" in template and "}}" in template:
            # placeholder 모드: JSON 파싱 시도
            try:
                import json
                # JSON 블록 추출 (```json ... ``` 형식 처리)
                json_str = result
                if "```json" in result:
                    json_str = result.split("```json")[1].split("```")[0].strip()
                elif "```" in result:
                    json_str = result.split("```")[1].split("```")[0].strip()

                parsed = json.loads(json_str)
                response_data["mode"] = "placeholder"
                response_data["제목"] = parsed.get("제목", "")
                response_data["인용구"] = parsed.get("인용구", "")
                response_data["묵상"] = parsed.get("묵상", "")
                response_data["result"] = parsed.get("묵상", result)  # fallback
                print(f"[Meditation] placeholder 모드 - JSON 파싱 성공")
            except Exception as parse_err:
                print(f"[Meditation] JSON 파싱 실패, 원본 사용: {parse_err}")
                response_data["mode"] = "legacy"
                response_data["result"] = result
        else:
            response_data["mode"] = "legacy" if template else "default"
            response_data["result"] = result

        return jsonify(response_data)

    except Exception as e:
        print(f"[Meditation] 오류: {str(e)}")
        return jsonify({"ok": False, "error": str(e)}), 500


@api_sermon_bp.route('/gpt-pro', methods=['POST'])
@api_login_required
def gpt_pro():
    """GPT PRO 완성본 작성"""
    try:
        client = get_client()

        # 인증이 비활성화된 경우 크레딧 체크 건너뛰기
        if AUTH_ENABLED:
            user_id = session.get('user_id')
            current_credits = get_user_credits(user_id)

            is_admin = session.get('is_admin', 0)
            if not is_admin and current_credits <= 0:
                return jsonify({
                    "ok": False,
                    "error": "Step3 사용 크레딧이 부족합니다. 관리자에게 문의하세요.",
                    "credits": 0,
                    "needCredits": True
                }), 200
        else:
            user_id = None
            current_credits = -1
            is_admin = 0

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

        gpt_pro_model = data.get("model", "gpt-5")
        max_tokens = data.get("maxTokens", 16000)
        custom_prompt = data.get("customPrompt", "")

        # JSON 모드 데이터
        step1_result = data.get("step1Result")
        step2_result = data.get("step2Result")
        step3_guide = data.get("step3Guide")
        target_audience = data.get("target", "")
        worship_type = data.get("worshipType", "")
        duration = data.get("duration", "20분")
        special_notes = data.get("specialNotes", "")

        # 문단/줄바꿈 스타일 및 성경구절 인용 규칙 (프론트엔드에서 전달)
        writing_style = data.get("writingStyle")
        scripture_citation = data.get("scriptureCitation")

        # Step1/Step2 추가 정보 (Strong's 원어 분석, 시대 컨텍스트)
        step1_extra_info = data.get("step1ExtraInfo")
        step2_extra_info = data.get("step2ExtraInfo")

        # JSON 모드 여부 확인
        is_json_mode = (isinstance(step1_result, dict) and len(step1_result) > 0) or \
                       (isinstance(step2_result, dict) and len(step2_result) > 0)

        print(f"[GPT-PRO/Step3] JSON 모드: {is_json_mode}, step1_result 타입: {type(step1_result)}, step2_result 타입: {type(step2_result)}")
        print(f"[GPT-PRO/Step3] 처리 시작 - 스타일: {style_name}, 모델: {gpt_pro_model}, 토큰: {max_tokens}")
        print(f"[GPT-PRO/Step3] writing_style: {'있음' if writing_style else '없음'}, scripture_citation: {'있음' if scripture_citation else '없음'}")
        print(f"[GPT-PRO/Step3] step1_extra_info: {'있음' if step1_extra_info else '없음'}, step2_extra_info: {'있음' if step2_extra_info else '없음'}")

        has_title = bool(title and title.strip())

        # 시스템 프롬프트
        system_content = "당신은 한국어 설교 전문가입니다. 마크다운 기호 대신 순수 텍스트만 사용합니다."

        # 최우선 지침
        system_content += "\n\n" + "=" * 50
        system_content += "\n【 ★ 최우선 지침 - 반드시 준수 ★ 】"
        system_content += "\n" + "=" * 50
        if duration:
            system_content += f"\n\n🚨 분량 제한: 이 설교는 반드시 {duration} 분량으로 작성하세요."
            system_content += f"\n   - {duration} 분량을 절대 초과하지 마세요."
            system_content += "\n   - Step1, Step2의 구조가 길더라도 {duration} 안에 맞춰 압축하세요."
            system_content += "\n   - 이 분량 제한은 다른 모든 지침보다 우선합니다."
        if worship_type:
            system_content += f"\n\n🚨 예배/집회 유형: '{worship_type}'"
            system_content += f"\n   - 이 설교는 '{worship_type}'에 맞는 톤과 내용으로 작성하세요."
        if special_notes:
            system_content += f"\n\n🚨 특별 참고 사항:"
            system_content += f"\n   {special_notes}"
            system_content += f"\n   - 위 내용을 설교문 작성 시 반드시 고려하세요."
        system_content += "\n" + "=" * 50

        # 문단/줄바꿈 스타일 규칙 추가
        if writing_style and isinstance(writing_style, dict):
            system_content += "\n\n" + "=" * 50
            system_content += f"\n【 ★★★ {writing_style.get('label', '문단/줄바꿈 스타일')} ★★★ 】"
            system_content += "\n" + "=" * 50

            if writing_style.get('core_principle'):
                system_content += f"\n\n핵심 원칙: {writing_style['core_principle']}"

            if writing_style.get('must_do'):
                system_content += "\n\n✅ 반드시 해야 할 것:"
                for item in writing_style['must_do']:
                    system_content += f"\n  - {item}"

            if writing_style.get('must_not'):
                system_content += "\n\n❌ 절대 하지 말아야 할 것:"
                for item in writing_style['must_not']:
                    system_content += f"\n  - {item}"

            if writing_style.get('good_example'):
                system_content += f"\n\n✅ 올바른 예시:\n{writing_style['good_example']}"

            if writing_style.get('bad_example'):
                system_content += f"\n\n❌ 잘못된 예시 (이렇게 쓰지 마세요):\n{writing_style['bad_example']}"

            if writing_style.get('critical_warning'):
                system_content += f"\n\n⚠️ 경고: {writing_style['critical_warning']}"

        # 성경구절 인용 규칙 추가
        if scripture_citation and isinstance(scripture_citation, dict):
            system_content += "\n\n" + "=" * 50
            system_content += f"\n【 ★★★ {scripture_citation.get('label', '성경구절 인용 방식')} ★★★ 】"
            system_content += "\n" + "=" * 50

            if scripture_citation.get('core_principle'):
                system_content += f"\n\n핵심 원칙: {scripture_citation['core_principle']}"

            if scripture_citation.get('must_do'):
                system_content += "\n\n✅ 반드시 해야 할 것:"
                for item in scripture_citation['must_do']:
                    system_content += f"\n  - {item}"

            if scripture_citation.get('must_not'):
                system_content += "\n\n❌ 절대 하지 말아야 할 것:"
                for item in scripture_citation['must_not']:
                    system_content += f"\n  - {item}"

            if scripture_citation.get('good_examples'):
                system_content += "\n\n✅ 올바른 예시:"
                for example in scripture_citation['good_examples']:
                    system_content += f"\n  {example}"

            if scripture_citation.get('bad_examples'):
                system_content += "\n\n❌ 잘못된 예시 (이렇게 쓰지 마세요):"
                for example in scripture_citation['bad_examples']:
                    system_content += f"\n  {example}"

            if scripture_citation.get('usage_guide'):
                system_content += f"\n\n📌 {scripture_citation['usage_guide']}"

        if not has_title:
            system_content += (
                "\n\n⚠️ 제목 생성: 설교문 맨 앞에 '설교 제목: (제목 내용)' 형식으로 적절한 제목을 먼저 생성하세요."
                "\n그 다음 빈 줄을 넣고 바로 설교 내용을 시작하세요. 본문 성경구절은 출력하지 마세요."
            )
        else:
            system_content += "\n\n⚠️ 중요: 설교 제목과 본문 성경구절은 다시 출력하지 마세요. 바로 설교 내용부터 시작하세요."

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

        if is_json_mode:
            try:
                print(f"[GPT-PRO/Step3] JSON 모드 활성화")
                meta_data = {
                    "scripture": reference,
                    "title": title,
                    "target": target_audience,
                    "worship_type": worship_type,
                    "duration": duration,
                    "sermon_style": style_name,
                    "category": category,
                    "special_notes": special_notes
                }

                writing_spec = {}
                if step2_result and isinstance(step2_result, dict):
                    writing_spec = step2_result.get("writing_spec", {})
                    if "length" in writing_spec:
                        del writing_spec["length"]

                if writing_spec:
                    system_content += "\n\n【 작성 규격 】\n"
                    for key, value in writing_spec.items():
                        if isinstance(value, list):
                            system_content += f"- {key}: {', '.join(value)}\n"
                        else:
                            system_content += f"- {key}: {value}\n"

                user_content = build_step3_prompt_from_json(
                    json_guide=step3_guide,
                    meta_data=meta_data,
                    step1_result=step1_result,
                    step2_result=step2_result
                )

                if custom_prompt and custom_prompt.strip():
                    user_content += f"\n\n【추가 지침】\n{custom_prompt.strip()}"

            except Exception as json_err:
                print(f"[GPT-PRO/Step3] JSON 모드 오류, 텍스트 모드로 전환: {str(json_err)}")
                is_json_mode = False

        if not is_json_mode:
            user_content = (
                "아래는 gpt-4o-mini가 정리한 연구·개요 자료입니다."
                " 참고만 하고, 문장은 처음부터 새로 작성해주세요."
            )
            if meta_section:
                user_content += f"\n\n[기본 정보]\n{meta_section}"
            user_content += "\n\n[설교 초안 자료]\n"
            user_content += draft_content

            if custom_prompt and custom_prompt.strip():
                user_content += f"\n\n【지침】\n{custom_prompt.strip()}"
            else:
                user_content += "\n\n【지침】\n"
                user_content += (
                    "당신은 한국어 설교 전문가입니다.\n"
                    "step1,2 자료는 참고용으로만 활용하고 문장은 처음부터 새로 구성하며,\n"
                    "묵직하고 명료한 어조로 신학적 통찰과 실제적 적용을 균형 있게 제시하세요.\n\n"
                    "1. Step2의 설교 구조(서론, 본론, 결론)를 반드시 따라 작성하세요.\n"
                    "2. Step2의 대지(포인트) 구성을 유지하고 각 섹션의 핵심 메시지를 확장하세요.\n"
                    "3. 역사적 배경, 신학적 통찰, 실제 적용을 균형 있게 제시하세요.\n"
                    "4. 관련 성경구절을 적절히 인용하세요.\n"
                    "5. 가독성을 위해 각 섹션 사이에 빈 줄을 넣으세요.\n"
                    "6. 마크다운, 불릿 기호 대신 순수 텍스트 단락을 사용하세요.\n"
                    "7. 충분히 길고 상세하며 풍성한 내용으로 작성해주세요."
                )

        # Step1/Step2 추가 정보를 프롬프트에 포함
        if step1_extra_info or step2_extra_info:
            user_content += "\n\n" + "=" * 50
            user_content += "\n【 ★★★ 추가 분석 자료 (설교에 활용하세요) ★★★ 】"
            user_content += "\n" + "=" * 50

            # Strong's 원어 분석
            if step1_extra_info and step1_extra_info.get('strongs_analysis'):
                strongs = step1_extra_info['strongs_analysis']
                key_words = strongs.get('key_words', [])
                if key_words:
                    user_content += "\n\n▶ Strong's 원어 분석 (핵심 단어)"
                    if strongs.get('text'):
                        user_content += f"\n   영문 (KJV): {strongs['text']}"
                    for i, word in enumerate(key_words[:5], 1):
                        lemma = word.get('lemma', '')
                        translit = word.get('translit', '')
                        strongs_num = word.get('strongs', '')
                        definition = word.get('definition', '')[:150]
                        user_content += f"\n   {i}. {lemma} ({translit}, {strongs_num})"
                        if word.get('english'):
                            user_content += f" - {word['english']}"
                        if definition:
                            user_content += f"\n      → {definition}"

            # 시대 컨텍스트
            if step2_extra_info and step2_extra_info.get('context_data'):
                context = step2_extra_info['context_data']
                user_content += "\n\n▶ 현재 시대 컨텍스트 (도입부/예화/적용에 활용)"
                user_content += f"\n   청중 유형: {context.get('audience', '전체')}"

                # 주요 뉴스
                news = context.get('news', {})
                if news:
                    cat_names = {'economy': '경제', 'politics': '정치', 'society': '사회', 'world': '국제', 'culture': '문화'}
                    user_content += "\n   주요 시사 이슈:"
                    for cat, items in news.items():
                        if items:
                            for item in items[:1]:  # 카테고리당 1개만
                                title_text = item.get('title', '')[:50]
                                user_content += f"\n   - [{cat_names.get(cat, cat)}] {title_text}"

                # 청중 관심사
                concerns = context.get('concerns', [])
                if concerns:
                    user_content += f"\n   청중의 주요 관심사: {', '.join(concerns[:3])}"

            user_content += "\n" + "=" * 50

        if duration:
            user_content += f"\n\n⚠️ 매우 중요 - 분량 제한: {duration} 분량 안에서 충분히 상세하고 풍성한 내용으로 작성하세요!"
            user_content += f"\n{duration} 분량을 반드시 지키되, 그 안에서 최대한 깊이 있게 작성해주세요."
        else:
            user_content += f"\n\n⚠️ 중요: 충분히 길고 상세하며 풍성한 내용으로 작성해주세요."

        usage_data = None

        messages = [
            {"role": "system", "content": system_content},
            {"role": "user", "content": user_content}
        ]

        api_kwargs = {"model": gpt_pro_model, "messages": messages}
        if gpt_pro_model in ["gpt-5", "gpt-5.1"]:
            api_kwargs["max_completion_tokens"] = max_tokens
        elif gpt_pro_model.startswith("gpt-5"):
            api_kwargs["temperature"] = 0.8
            api_kwargs["max_completion_tokens"] = max_tokens
        else:
            api_kwargs["temperature"] = 0.8
            api_kwargs["max_tokens"] = max_tokens

        # API 호출 (최대 3회 재시도)
        max_retries = 3
        completion = None
        last_error = None

        for attempt in range(max_retries):
            try:
                completion = client.chat.completions.create(**api_kwargs)
                break
            except Exception as e:
                last_error = e
                if attempt < max_retries - 1:
                    wait_time = 2 ** attempt
                    print(f"[GPT-PRO/Step3] API 호출 실패 (시도 {attempt + 1}/{max_retries}), {wait_time}초 후 재시도: {str(e)}")
                    time.sleep(wait_time)
                else:
                    print(f"[GPT-PRO/Step3] API 호출 최종 실패 ({max_retries}회 시도): {str(e)}")
                    raise e

        if not completion:
            raise RuntimeError(f"{gpt_pro_model} API 호출 실패: {str(last_error)}")

        result = completion.choices[0].message.content.strip()

        if hasattr(completion, 'usage') and completion.usage:
            usage_data = {
                "input_tokens": getattr(completion.usage, 'prompt_tokens', 0),
                "output_tokens": getattr(completion.usage, 'completion_tokens', 0),
                "total_tokens": getattr(completion.usage, 'total_tokens', 0)
            }

        if not result:
            raise RuntimeError(f"{gpt_pro_model} API로부터 결과를 받지 못했습니다.")

        if usage_data:
            log_api_usage(
                step_name='step3',
                model_name=gpt_pro_model,
                input_tokens=usage_data.get('input_tokens', 0),
                output_tokens=usage_data.get('output_tokens', 0),
                style_name=style_name,
                category=category
            )

        result = remove_markdown(result)

        final_result = ""

        if has_title:
            final_result += f"설교 제목: {title}\n\n"
            if reference:
                final_result += f"본문: {reference}\n\n"
            final_result += result
        else:
            if reference:
                final_result += f"본문: {reference}\n\n"
            final_result += result

        print(f"[GPT-PRO] 완료")

        # 설교문 자동 분석 및 DB 저장
        try:
            extracted_title = title if has_title else ""
            if not has_title and "설교 제목:" in final_result:
                lines = final_result.split('\n')
                for line in lines:
                    if line.startswith("설교 제목:"):
                        extracted_title = line.replace("설교 제목:", "").strip()
                        break

            analysis_thread = threading.Thread(
                target=analyze_sermon_for_benchmark,
                args=(final_result, reference, extracted_title, category, style_name)
            )
            analysis_thread.daemon = True
            analysis_thread.start()
            print(f"[GPT-PRO] 벤치마크 분석 백그라운드 시작")
        except Exception as e:
            print(f"[GPT-PRO] 벤치마크 분석 시작 실패 (무시): {str(e)}")

        # 크레딧 차감
        remaining_credits = current_credits
        if AUTH_ENABLED and not is_admin and user_id:
            use_credit(user_id)
            remaining_credits = get_user_credits(user_id)
            print(f"[GPT-PRO/Step3] 크레딧 차감 - 사용자: {user_id}, 남은 크레딧: {remaining_credits}")

        print(f"[GPT-PRO/Step3] 완료 - 토큰: {usage_data}")
        return jsonify({
            "ok": True,
            "result": final_result,
            "usage": usage_data,
            "credits": remaining_credits if not is_admin else -1
        })

    except Exception as e:
        print(f"[GPT-PRO/Step3][ERROR] {str(e)}")
        return jsonify({"ok": False, "error": str(e)}), 200


@api_sermon_bp.route('/qa', methods=['POST'])
@api_login_required
def sermon_qa():
    """설교 준비 Q&A - 처리 단계 결과와 본문을 기반으로 질문에 답변"""
    try:
        client = get_client()
        data = request.get_json()
        if not data:
            return jsonify({"ok": False, "error": "No data received"}), 400

        question = data.get("question", "")
        reference = data.get("reference", "")
        step_results = data.get("stepResults", {})

        if not question:
            return jsonify({"ok": False, "error": "질문이 비어있습니다"}), 400

        print(f"[Q&A] 질문: {question}")

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

        user_content = ""

        if reference:
            user_content += f"【 현재 준비 중인 성경 본문 】\n{reference}\n\n"

        if step_results:
            user_content += "【 처리 단계 결과 】\n"
            for step_id, step_data in step_results.items():
                step_name = step_data.get("name", "")
                step_result = step_data.get("result", "")
                if step_result:
                    user_content += f"\n### {step_name}\n{step_result}\n"
            user_content += "\n"

        user_content += f"【 사용자 질문 】\n{question}\n\n"
        user_content += "위 맥락을 참고하여 질문에 답변해주세요."

        completion = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_content},
                {"role": "user", "content": user_content}
            ],
            temperature=0.7
        )

        answer = completion.choices[0].message.content

        print(f"[Q&A] 답변 완료")

        return jsonify({"ok": True, "answer": answer})

    except Exception as e:
        print(f"[Q&A][ERROR] {str(e)}")
        return jsonify({"ok": False, "error": str(e)}), 200


@api_sermon_bp.route('/recommend-scripture', methods=['POST'])
@api_login_required
def recommend_scripture():
    """상황에 맞는 성경 본문 추천 (단락 단위, 본문 포함)"""
    try:
        client = get_client()
        data = request.get_json()
        if not data:
            return jsonify({"ok": False, "error": "No data received"}), 400

        query = data.get("query", "")
        if not query:
            return jsonify({"ok": False, "error": "상황을 입력해주세요"}), 400

        print(f"[본문추천] 검색어: {query}")

        system_content = """당신은 설교 본문 선정 전문가입니다. 사용자가 제시하는 상황, 행사, 주제에 가장 적합한 성경 본문을 추천해주세요.

【 핵심 원칙 】
1. 단락(Pericope) 단위로 추천: 1-2절이 아닌, 하나의 완결된 이야기나 논증 단위로 추천하세요.
   - 좋은 예: 창세기 18:17-33 (아브라함의 중보기도), 요한복음 15:1-17 (포도나무 비유)
   - 나쁜 예: 창세기 18:17 (너무 짧음), 시편 23:1 (단절됨)
2. 새벽설교, 주일설교 등에 적합한 5-20절 분량의 본문을 추천하세요.
3. 실제 성경 본문 내용을 포함하세요 (개역개정 기준).

【 응답 형식 】
반드시 아래 JSON 형식으로만 응답하세요:
[
  {
    "scripture": "창세기 18:17-33",
    "title": "아브라함의 중보기도",
    "text": "여호와께서 이르시되 내가 하려는 것을 아브라함에게 숨기겠느냐... (핵심 구절 3-5개 발췌)",
    "reason": "이 본문이 해당 상황에 적합한 이유를 2-3문장으로 구체적으로 설명. 본문의 핵심 메시지와 상황의 연결점을 분석적으로 제시하세요."
  },
  ...
]

【 주의사항 】
- 정확히 5개의 추천을 제공하세요
- scripture: 한글 성경 표기법 + 단락 범위 (예: 창세기 18:17-33)
- title: 본문의 핵심 주제를 5-10자로
- text: 해당 본문의 핵심 구절 3-5개를 발췌 (... 으로 연결)
- reason: 50-100자로 상황과 본문의 연결점을 분석적으로 설명
- JSON 형식만 응답하세요"""

        user_content = f"""다음 상황/행사/주제에 적합한 설교 본문 5개를 추천해주세요.

상황: {query}

각 추천에 대해:
1. 단락 단위의 본문 범위 (5-20절)
2. 본문 제목
3. 핵심 성경 구절 발췌
4. 이 본문을 추천하는 구체적인 이유 (상황과의 연결점)

를 제공해주세요."""

        completion = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": system_content},
                {"role": "user", "content": user_content}
            ],
            temperature=0.7
        )

        response_text = completion.choices[0].message.content.strip()

        try:
            if response_text.startswith("```"):
                response_text = response_text.split("```")[1]
                if response_text.startswith("json"):
                    response_text = response_text[4:]
            recommendations = json.loads(response_text)
        except json.JSONDecodeError:
            print(f"[본문추천] JSON 파싱 실패: {response_text[:200]}")
            return jsonify({"ok": False, "error": "추천 결과 파싱 실패"}), 200

        print(f"[본문추천] 완료: {len(recommendations)}개 추천")

        return jsonify({"ok": True, "recommendations": recommendations})

    except Exception as e:
        print(f"[본문추천][ERROR] {str(e)}")
        return jsonify({"ok": False, "error": str(e)}), 200


@api_sermon_bp.route('/chat', methods=['POST'])
def sermon_chat():
    """설교 페이지 AI 챗봇 - 현재 작업 상황 및 오류에 대해 질문/답변"""
    try:
        client = get_client()
        data = request.get_json()
        if not data:
            return jsonify({"ok": False, "error": "No data received"}), 400

        question = data.get("question", "")
        context = data.get("context", {})
        selected_model = data.get("model", "gpt-4o-mini")

        allowed_models = ["gpt-4o-mini", "gpt-4o", "gpt-5"]
        if selected_model not in allowed_models:
            selected_model = "gpt-4o-mini"

        if not question:
            return jsonify({"ok": False, "error": "질문을 입력해주세요."}), 400

        print(f"[SERMON-CHAT] 모델: {selected_model}, 질문: {question[:100]}...")

        context_text = ""

        if context.get("step1Result"):
            context_text += f"【Step1 결과 (본문 연구)】\n{context.get('step1Result', '')[:2000]}\n\n"

        if context.get("step2Result"):
            context_text += f"【Step2 결과 (설교 구조)】\n{context.get('step2Result', '')[:2000]}\n\n"

        if context.get("step3Result"):
            context_text += f"【Step3 결과 (설교문)】\n{context.get('step3Result', '')[:3000]}\n\n"

        if context.get("bibleVerse"):
            context_text += f"【성경 본문】\n{context.get('bibleVerse', '')}\n\n"

        if context.get("sermonStyle"):
            context_text += f"【설교 스타일】\n{context.get('sermonStyle', '')}\n\n"

        if context.get("lastError"):
            context_text += f"【최근 오류】\n{context.get('lastError', '')}\n\n"

        if context.get("apiResponse"):
            context_text += f"【API 응답 정보】\n{context.get('apiResponse', '')}\n\n"

        system_prompt = """당신은 설교문 작성 도구의 AI 어시스턴트입니다.
사용자가 설교문 작성 과정에서 겪는 문제나 질문에 답변합니다.

역할:
1. 현재 설교문 작성 상황 분석 및 설명
2. Step1(본문 연구), Step2(설교 구조), Step3(설교문 작성) 단계별 도움
3. 오류 발생 시 원인 분석 및 해결 방법 안내
4. API 오류, 크레딧 문제, 네트워크 오류 등 기술적 문제 해결 도움
5. 설교 내용에 대한 피드백 및 개선 제안

일반적인 오류 유형:
- Step3 크레딧 부족: 관리자에게 크레딧 충전 요청 필요
- API 타임아웃: 입력 내용이 너무 길거나 서버 부하
- 네트워크 오류: 인터넷 연결 확인 필요
- 모델 오류: 다른 AI 모델로 시도 권장

답변 시 유의사항:
- 기술적 문제는 구체적인 해결 방법을 안내하세요
- 설교 내용 관련 질문은 신학적으로 적절한 답변을 제공하세요
- 한국어로 친절하고 이해하기 쉽게 답변하세요"""

        user_content = ""
        if context_text:
            user_content += f"{context_text}\n"
        user_content += f"【질문】\n{question}"

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

        usage = {
            "input_tokens": completion.usage.prompt_tokens,
            "output_tokens": completion.usage.completion_tokens,
            "model": selected_model
        }

        print(f"[SERMON-CHAT][SUCCESS] {selected_model}로 답변 생성 완료")
        return jsonify({"ok": True, "answer": answer, "usage": usage})

    except Exception as e:
        print(f"[SERMON-CHAT][ERROR] {str(e)}")
        return jsonify({"ok": False, "error": str(e)}), 500
