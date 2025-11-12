import os
from flask import Flask, render_template, request, jsonify
from openai import OpenAI
import requests
from datetime import datetime

app = Flask(__name__)

def get_client():
    key = (os.getenv("OPENAI_API_KEY") or "").strip()
    if not key:
        raise RuntimeError("OPENAI_API_KEY가 비어 있습니다.")
    return OpenAI(api_key=key)

client = get_client()

@app.route("/")
def home():
    return render_template("trade.html")

@app.route("/trade")
def trade():
    return render_template("trade.html")

# 헬스체크
@app.route("/health")
def health():
    key = (os.getenv("OPENAI_API_KEY") or "").strip()
    masked = f"{key[:3]}***{key[-3:]}" if len(key) >= 7 else "(none)"
    return jsonify({
        "ok": True,
        "key_present": bool(key),
        "key_masked": masked,
    })

# 실시간 환율 가져오기
@app.route("/api/trade/exchange-rate", methods=["GET"])
def get_exchange_rate():
    try:
        # ExchangeRate-API (무료)
        response = requests.get("https://api.exchangerate-api.com/v4/latest/CNY")
        data = response.json()
        krw_rate = data['rates']['KRW']
        
        return jsonify({
            "ok": True,
            "rate": round(krw_rate, 2),
            "timestamp": datetime.now().isoformat()
        })
    except Exception as e:
        # 실패 시 기본값
        return jsonify({
            "ok": True,
            "rate": 180.0,
            "timestamp": datetime.now().isoformat(),
            "fallback": True
        })

# HS코드 추천
@app.route("/api/trade/hs-code", methods=["POST"])
def recommend_hs_code():
    data = request.json or {}
    product_name = data.get("product_name", "")
    description = data.get("description", "")

    try:
        completion = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": """You are a customs and HS code expert. Recommend HS codes for products imported to Korea.
Respond in Korean with this exact format:

### HS코드 추천

**추천 HS코드**: [10자리 코드]
**품목명**: [정확한 품목명]
**기본 관세율**: [X]%
**부가세**: 10%
**총 세율**: [X]%

**설명**: [간단한 설명]

**대체 HS코드**:
1. [코드] - [품목명] (관세율 X%)
2. [코드] - [품목명] (관세율 X%)"""
                },
                {
                    "role": "user",
                    "content": f"제품명: {product_name}\n설명: {description}\n\n이 제품에 맞는 HS코드를 추천해주세요."
                }
            ],
            temperature=0.3,
        )

        result = completion.choices[0].message.content
        return jsonify({"ok": True, "result": result})

    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 200

# 손익분기점 계산
@app.route("/api/trade/break-even", methods=["POST"])
def calculate_break_even():
    data = request.json or {}
    try:
        total_investment = float(data.get("total_investment", 0))
        profit_per_unit = float(data.get("profit_per_unit", 0))
        
        if profit_per_unit <= 0:
            return jsonify({"ok": False, "error": "개당 순이익은 0보다 커야 합니다."})
        
        break_even_qty = total_investment / profit_per_unit
        
        return jsonify({
            "ok": True,
            "break_even_qty": round(break_even_qty),
            "message": f"{round(break_even_qty)}개 판매 시 손익분기점 달성"
        })
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 200

if __name__ == "__main__":
    import os
    app.run(host="127.0.0.1", port=int(os.environ.get("PORT", 5059)), debug=True)