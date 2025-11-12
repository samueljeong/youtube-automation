import os
from flask import Flask, render_template, request, jsonify
from openai import OpenAI
import base64
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
    return render_template("content.html")

@app.route("/content")
def content():
    return render_template("content.html")

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

# 이미지 품질 분석
@app.route("/api/content/analyze-quality", methods=["POST"])
def analyze_image_quality():
    try:
        images = request.files.getlist('images')
        if not images or len(images) == 0:
            return jsonify({"ok": False, "error": "이미지를 업로드해주세요."})
        
        # 첫 번째 이미지만 품질 분석
        image_data = images[0].read()
        base64_image = base64.b64encode(image_data).decode('utf-8')
        
        ext = images[0].filename.rsplit('.', 1)[1].lower() if '.' in images[0].filename else 'jpg'
        mime_type = f"image/{ext}" if ext in ['jpg', 'jpeg', 'png', 'gif', 'webp'] else "image/jpeg"
        
        completion = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": "You are an expert photographer and e-commerce image consultant. Analyze product images for quality."
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": """이 제품 이미지의 품질을 분석해주세요:

**평가 항목**:
1. 해상도 (선명도)
2. 조명
3. 구도/각도
4. 배경
5. 제품 가시성

각 항목을 ⭐⭐⭐⭐⭐ (5점 만점)로 평가하고, 개선 방안을 제시해주세요.

형식:
### 이미지 품질 분석

**해상도**: ⭐⭐⭐⭐ (4/5)
- 평가: [내용]
- 개선: [내용]

**조명**: ⭐⭐⭐⭐⭐ (5/5)
- 평가: [내용]

... (나머지 항목)

**종합 평가**: [A/B/C/D]
**메인 썸네일 추천**: [Yes/No]"""
                        },
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:{mime_type};base64,{base64_image}"}
                        }
                    ]
                }
            ],
            temperature=0.3,
        )
        
        return jsonify({"ok": True, "result": completion.choices[0].message.content})
        
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)})

# 종합 콘텐츠 생성
@app.route("/api/content/generate-all", methods=["POST"])
def generate_all_content():
    try:
        # 이미지들 받기
        images_data = []
        if 'images' in request.files:
            images = request.files.getlist('images')
            for img in images[:5]:  # 최대 5장
                image_bytes = img.read()
                base64_img = base64.b64encode(image_bytes).decode('utf-8')
                ext = img.filename.rsplit('.', 1)[1].lower() if '.' in img.filename else 'jpg'
                mime_type = f"image/{ext}" if ext in ['jpg', 'jpeg', 'png', 'gif', 'webp'] else "image/jpeg"
                images_data.append({
                    "type": "image_url",
                    "image_url": {"url": f"data:{mime_type};base64,{base64_img}"}
                })
        
        # 텍스트 정보
        data = request.form
        product_name = data.get('product_name', '')
        product_desc = data.get('product_desc', '')
        price = data.get('price', '')
        target = data.get('target', '일반')
        style = data.get('style', '감성형')
        
        # GPT 메시지 구성
        content_parts = [
            {
                "type": "text",
                "text": f"""제품 판매를 위한 모든 콘텐츠를 생성해주세요.

**제품 정보**:
- 제품명: {product_name}
- 설명: {product_desc}
- 가격: {price}원
- 타겟: {target}
- 스타일: {style}

**생성할 콘텐츠**:

### 1. 네이버 스마트스토어용 제목 (3가지)
- 검색 최적화
- 클릭 유도
- 각 제목의 기대 효과 설명

### 2. 쿠팡용 제목 (3가지)
- 스펙 중심
- 가성비 강조
- 각 제목의 기대 효과 설명

### 3. 상세페이지 소개글
- {style} 스타일로 작성
- {target} 타겟 고객 맞춤
- 500자 내외

### 4. 주요 판매 포인트 (5개)
- 차별화된 특징
- 고객 혜택 중심

### 5. 검색 키워드 (20개)
- 네이버 쇼핑 검색용
- 쉼표로 구분

### 6. 예상 고객 질문 & 답변 (5개)
- 자주 물어볼 질문
- 답변 템플릿

### 7. 금지어 체크
- 사용하면 안 되는 표현 경고
- 과장광고 위험 문구

### 8. 필수 표기사항 체크리스트
- 제품 특성에 맞는 필수 정보

### 9. 가격 책정 제안
- 심리적 가격대
- 경쟁력 분석

### 10. 프로모션 문구 (3가지)
- 할인 이벤트용
- 긴급성 강조

모든 내용을 한국어로, 실제 바로 사용할 수 있는 수준으로 작성해주세요."""
            }
        ]
        
        # 이미지 추가
        content_parts.extend(images_data)
        
        completion = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": "You are an expert e-commerce content creator and marketing specialist for Korean online shopping platforms."
                },
                {
                    "role": "user",
                    "content": content_parts
                }
            ],
            temperature=0.7,
            max_tokens=3000
        )
        
        return jsonify({
            "ok": True,
            "result": completion.choices[0].message.content
        })
        
    except Exception as e:
        print(f"[GENERATE_ALL][ERROR] {str(e)}")
        return jsonify({"ok": False, "error": str(e)})

# 경쟁사 분석
@app.route("/api/content/competitor-analysis", methods=["POST"])
def competitor_analysis():
    try:
        data = request.json or {}
        product_name = data.get('product_name', '')
        price = data.get('price', 0)
        
        completion = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": "You are a market research expert specializing in Korean e-commerce platforms."
                },
                {
                    "role": "user",
                    "content": f"""제품명: {product_name}
가격: {price}원

이 제품의 경쟁 상황을 분석해주세요:

### 경쟁사 분석

**유사 제품 가격대**:
- 최저가: [예상 가격]
- 평균가: [예상 가격]
- 최고가: [예상 가격]

**시장 경쟁도**: [상/중/하]
**이유**: [설명]

**인기 있는 제품 특징**:
1. [특징]
2. [특징]
3. [특징]

**고객들이 찾는 주요 키워드**:
- [키워드 1]
- [키워드 2]
- [키워드 3]

**차별화 전략 제안**:
1. [전략]
2. [전략]
3. [전략]

**권장 판매가**: [금액]원
**이유**: [설명]"""
                }
            ],
            temperature=0.5,
        )
        
        return jsonify({"ok": True, "result": completion.choices[0].message.content})
        
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)})

# 타겟별 맞춤 콘텐츠
@app.route("/api/content/target-content", methods=["POST"])
def generate_target_content():
    try:
        data = request.json or {}
        product_name = data.get('product_name', '')
        target = data.get('target', '')
        
        targets_desc = {
            '20대여성': '20대 여성 - 트렌디하고 감성적',
            '30대직장인': '30대 직장인 - 실용적이고 효율성 중시',
            '주부': '주부 - 가성비와 실용성 강조',
            '시니어': '시니어 - 편의성과 안전성 강조',
            '학생': '학생 - 가격과 기능 모두 중요'
        }
        
        target_desc = targets_desc.get(target, target)
        
        completion = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": f"You are a marketing copywriter specialized in {target_desc} target audience."
                },
                {
                    "role": "user",
                    "content": f"""제품: {product_name}
타겟: {target_desc}

이 타겟 고객에게 맞는 콘텐츠를 작성해주세요:

### 제목 (3가지)
1. [제목]
2. [제목]
3. [제목]

### 소개 문구
[타겟에 맞는 감성적 소개 200자]

### 주요 어필 포인트 (3가지)
1. [이 타겟이 중요하게 생각하는 특징]
2. [특징]
3. [특징]

### 추천 이미지 컨셉
[어떤 느낌의 이미지가 효과적인지]"""
                }
            ],
            temperature=0.7,
        )
        
        return jsonify({"ok": True, "result": completion.choices[0].message.content})
        
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)})

# 썸네일 추천
@app.route("/api/content/recommend-thumbnail", methods=["POST"])
def recommend_thumbnail():
    try:
        images = request.files.getlist('images')
        if len(images) < 2:
            return jsonify({"ok": False, "error": "비교할 이미지가 2장 이상 필요합니다."})
        
        # 모든 이미지를 base64로 변환
        images_data = []
        for idx, img in enumerate(images[:5]):
            image_bytes = img.read()
            base64_img = base64.b64encode(image_bytes).decode('utf-8')
            ext = img.filename.rsplit('.', 1)[1].lower() if '.' in img.filename else 'jpg'
            mime_type = f"image/{ext}" if ext in ['jpg', 'jpeg', 'png', 'gif', 'webp'] else "image/jpeg"
            images_data.append({
                "type": "image_url",
                "image_url": {"url": f"data:{mime_type};base64,{base64_img}"}
            })
        
        content_parts = [
            {
                "type": "text",
                "text": f"""업로드된 {len(images_data)}장의 이미지를 비교 분석해서:

### 썸네일 추천

**1순위 추천**: 이미지 [번호]
**이유**: 
- 제품이 명확하게 보임
- 시선을 끄는 구도
- 배경이 깔끔함
- 클릭을 유도하는 요소

**2순위**: 이미지 [번호]
**이유**: [설명]

**3순위**: 이미지 [번호]
**이유**: [설명]

**추천하지 않는 이미지**:
- 이미지 [번호]: [이유]

**종합 의견**:
[전체적인 평가와 개선 방안]"""
            }
        ]
        
        content_parts.extend(images_data)
        
        completion = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": "You are an e-commerce image consultant expert."
                },
                {
                    "role": "user",
                    "content": content_parts
                }
            ],
            temperature=0.3,
        )
        
        return jsonify({"ok": True, "result": completion.choices[0].message.content})
        
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)})

# 소셜미디어 콘텐츠 생성
@app.route("/api/content/social-media", methods=["POST"])
def generate_social_content():
    try:
        data = request.json or {}
        product_name = data.get('product_name', '')
        product_desc = data.get('product_desc', '')
        platform = data.get('platform', '인스타그램')
        
        completion = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": f"You are a social media content creator specialized in {platform}."
                },
                {
                    "role": "user",
                    "content": f"""제품: {product_name}
설명: {product_desc}
플랫폼: {platform}

{platform}용 콘텐츠를 작성해주세요:

### {platform} 게시물

**캡션**:
[감성적이고 공감가는 문구 150자]

**해시태그** (20개):
#제품명 #카테고리 #특징...

**게시 시간 추천**:
[가장 효과적인 시간대]

**추가 팁**:
- [인게이지먼트 높이는 방법]
- [스토리 활용법]"""
                }
            ],
            temperature=0.7,
        )
        
        return jsonify({"ok": True, "result": completion.choices[0].message.content})
        
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)})

if __name__ == "__main__":
    import os
    app.run(host="127.0.0.1", port=int(os.environ.get("PORT", 5060)), debug=True)