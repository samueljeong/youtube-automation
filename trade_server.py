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

# 1688 제품 정보 추출
@app.route("/api/trade/parse-1688", methods=["POST"])
def parse_1688_link():
    data = request.json or {}
    url = data.get("url", "")
    
    if not url:
        return jsonify({"ok": False, "error": "URL을 입력해주세요."})
    
    # 1688 링크 체크
    if "1688.com" not in url and "taobao.com" not in url and "tmall.com" not in url:
        return jsonify({"ok": False, "error": "1688/타오바오/티몰 링크만 지원됩니다."})
    
    try:
        # User-Agent 설정 (봇 차단 우회)
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
        print(f"[1688] Fetching URL: {url}")
        response = requests.get(url, headers=headers, timeout=10)
        response.encoding = 'utf-8'
        html_content = response.text
        
        # HTML에서 제품 정보 추출 (간단한 파싱)
        # 제목 찾기
        import re
        title_match = re.search(r'<title[^>]*>(.*?)</title>', html_content, re.IGNORECASE)
        title = title_match.group(1) if title_match else ""
        
        # 가격 찾기 (선택적)
        price_match = re.search(r'price["\s:]+(\d+\.?\d*)', html_content, re.IGNORECASE)
        price = price_match.group(1) if price_match else ""
        
        # GPT에게 HTML 일부를 주고 제품 정보 추출 요청
        # (전체 HTML은 너무 길어서 일부만)
        html_snippet = html_content[:3000] if len(html_content) > 3000 else html_content
        
        completion = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": "You extract product information from Chinese e-commerce pages (1688, Taobao, Tmall). Extract product name, description, and recommend HS code."
                },
                {
                    "role": "user",
                    "content": f"""Analyze this Chinese product page:

URL: {url}
Page Title: {title}

HTML Snippet:
{html_snippet}

Please extract:
1. Product name (in Korean)
2. Product description (in Korean)
3. Recommended HS code
4. Estimated price if found

Respond in Korean in this format:
**제품명**: [Korean product name]
**제품 설명**: [Korean description]
**추천 HS코드**: [10-digit code]
**예상 가격**: [price if found, otherwise "확인 필요"]"""
                }
            ],
            temperature=0.3,
        )
        
        result = completion.choices[0].message.content
        print(f"[1688] Result: {result[:200]}")
        
        return jsonify({"ok": True, "result": result})
        
    except requests.Timeout:
        return jsonify({"ok": False, "error": "페이지 로딩 시간 초과. 다시 시도해주세요."})
    except requests.RequestException as e:
        return jsonify({"ok": False, "error": f"페이지를 가져올 수 없습니다: {str(e)}"})
    except Exception as e:
        print(f"[1688][ERROR] {str(e)}")
        return jsonify({"ok": False, "error": f"분석 중 오류 발생: {str(e)}"})

if __name__ == "__main__":
    import os
    app.run(host="127.0.0.1", port=int(os.environ.get("PORT", 5059)), debug=True)