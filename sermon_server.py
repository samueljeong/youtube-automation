# sermon_server.py
import os
from flask import Flask, render_template, request, jsonify
from openai import OpenAI

app = Flask(__name__)

# 환경변수에 키 넣어두세요: export OPENAI_API_KEY=sk-xxxx
client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))


@app.route("/")
def index():
    return "서버 잘 뜸!"


@app.route("/sermon")
def sermon():
    # templates/sermon.html 렌더
    return render_template("sermon.html")


# ---------------------------
# 1) 본문 분석 API
# ---------------------------
@app.route("/api/sermon/analyze", methods=["POST"])
def api_sermon_analyze():
    data = request.json or {}

    guide = data.get("guide", "")          # 카테고리별 '본문 분석 지침'
    bible_text = data.get("text", "")      # 본문 내용
    ref = data.get("ref", "")              # 성경구절
    category = data.get("category", "")    # 새벽/수요/청년부 ...

    # GPT 호출
    # model 부분은 계정에 있는 모델명으로 바꾸세요.
    completion = client.chat.completions.create(
        model="gpt-4o-mini",   # 예시 모델
        messages=[
            {
                "role": "system",
                "content": (
                    "너는 한국인 목회자를 돕는 설교 본문 연구 보조자다. "
                    "사용자가 제공하는 '지침'을 1순위로 적용해서 답을 구성한다. "
                    "가능하면 한국어로 작성하라."
                )
            },
            {
                "role": "user",
                "content": (
                    f"[지침 1순위]\n{guide}\n\n"
                    f"[설교 카테고리]\n{category}\n\n"
                    f"[본문 표시]\n{ref}\n\n"
                    f"[본문 내용]\n{bible_text}\n\n"
                    "이 본문을 구조적으로 분석해줘. "
                    "1) 본문 배경/맥락, 2) 핵심 주제와 메시지, 3) 신학적/교리적 포인트, "
                    "4) 오늘 설교 적용 포인트(회중에게 말하듯) 순서로 작성해."
                )
            }
        ],
        temperature=0.7,
    )

    result_text = completion.choices[0].message.content
    return jsonify({"result": result_text})


# ---------------------------
# 2) 설교 제작 프롬포트 생성 API
# ---------------------------
@app.route("/api/sermon/prompt", methods=["POST"])
def api_sermon_prompt():
    data = request.json or {}

    guide = data.get("guide", "")      # 카테고리별 '설교 프롬포트 지침'
    ref = data.get("ref", "")          # 성경구절
    category = data.get("category", "")  # 새벽/수요/청년부 ...
    bible_text = data.get("text", "")  # (있으면 더 좋으니까 같이 보냄)

    completion = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "system",
                "content": (
                    "너는 목회자가 GPT에게 붙여넣어서 설교문을 쓰게 만들 수 있는 '프롬포트'를 대신 작성해주는 도우미다. "
                    "반드시 사용자의 지침을 프롬포트의 최상단에 그대로 넣고 시작한다."
                )
            },
            {
                "role": "user",
                "content": (
                    f"[지침 1순위]\n{guide}\n\n"
                    f"[설교 카테고리]\n{category}\n"
                    f"[본문]\n{ref}\n{bible_text}\n\n"
                    "위 정보를 사용해서, GPT에게 설교문을 쓰라고 시킬 수 있는 완성형 프롬포트를 작성해줘. "
                    "프롬포트 안에는 다음을 포함해라:\n"
                    "- 설교의 대상(위 카테고리에 맞게)\n"
                    "- 3대지 구조 요청\n"
                    "- 각 대지마다 소대지 2개씩 요청\n"
                    "- 적용/결단 파트 요청\n"
                    "- 필요하면 보충 성경구절 추가 요청\n"
                    "출력은 '사용자가 그대로 복사해서 GPT 대화창에 붙여넣을 수 있는' 형태로 만들어라."
                )
            }
        ],
        temperature=0.6,
    )

    result_text = completion.choices[0].message.content
    return jsonify({"result": result_text})


if __name__ == "__main__":
    # 개발 중에는 debug 켜두면 수정 시 자동 리로드 됩니다.
    app.run(debug=True)