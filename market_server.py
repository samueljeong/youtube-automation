"""
Market Server - 스마트스토어 & 쿠팡 상품 관리 API
"""
import os
import json
import hmac
import hashlib
import base64
import time
import requests
import bcrypt
from datetime import datetime
from flask import Blueprint, request, jsonify
from openai import OpenAI

# OpenAI 클라이언트
openai_client = OpenAI(api_key=os.getenv('OPENAI_API_KEY', ''))

market_bp = Blueprint('market', __name__)

# ===== API 설정 =====
# 네이버 스마트스토어 커머스 API
NAVER_CLIENT_ID = os.getenv('NAVER_CLIENT_ID', '')
NAVER_CLIENT_SECRET = os.getenv('NAVER_CLIENT_SECRET', '')
NAVER_API_BASE = 'https://api.commerce.naver.com/external'

# 쿠팡 파트너스 API
COUPANG_ACCESS_KEY = os.getenv('COUPANG_ACCESS_KEY', '')
COUPANG_SECRET_KEY = os.getenv('COUPANG_SECRET_KEY', '')
COUPANG_VENDOR_ID = os.getenv('COUPANG_VENDOR_ID', '')
COUPANG_API_BASE = 'https://api-gateway.coupang.com'

# ===== Mock 데이터 (API 연동 전 테스트용) =====
MOCK_SMARTSTORE_PRODUCTS = [
    {
        "id": "SS001",
        "platform": "smartstore",
        "name": "프리미엄 무선 이어폰 Pro",
        "category": "전자제품",
        "price": 89000,
        "salePrice": 79000,
        "stock": 150,
        "status": "SALE",
        "imageUrl": "https://via.placeholder.com/150/667eea/ffffff?text=Earphone",
        "options": [
            {"name": "색상", "values": ["화이트", "블랙", "네이비"]},
            {"name": "타입", "values": ["일반형", "스포츠형"]}
        ],
        "salesCount": 324,
        "reviewCount": 89,
        "rating": 4.7,
        "lastModified": "2025-11-25T10:30:00"
    },
    {
        "id": "SS002",
        "platform": "smartstore",
        "name": "고급 가죽 지갑 슬림형",
        "category": "패션잡화",
        "price": 45000,
        "salePrice": 39000,
        "stock": 80,
        "status": "SALE",
        "imageUrl": "https://via.placeholder.com/150/764ba2/ffffff?text=Wallet",
        "options": [
            {"name": "색상", "values": ["브라운", "블랙", "네이비"]}
        ],
        "salesCount": 156,
        "reviewCount": 42,
        "rating": 4.5,
        "lastModified": "2025-11-24T15:20:00"
    },
    {
        "id": "SS003",
        "platform": "smartstore",
        "name": "스마트 LED 무드등 RGB",
        "category": "생활용품",
        "price": 32000,
        "salePrice": 28000,
        "stock": 5,
        "status": "SALE",
        "imageUrl": "https://via.placeholder.com/150/f59e0b/ffffff?text=LED",
        "options": [],
        "salesCount": 89,
        "reviewCount": 28,
        "rating": 4.3,
        "lastModified": "2025-11-23T09:15:00"
    },
    {
        "id": "SS004",
        "platform": "smartstore",
        "name": "프리미엄 텀블러 보온보냉",
        "category": "생활용품",
        "price": 28000,
        "salePrice": 24000,
        "stock": 0,
        "status": "OUTOFSTOCK",
        "imageUrl": "https://via.placeholder.com/150/ef4444/ffffff?text=Tumbler",
        "options": [
            {"name": "용량", "values": ["350ml", "500ml", "750ml"]},
            {"name": "색상", "values": ["실버", "로즈골드", "블랙"]}
        ],
        "salesCount": 512,
        "reviewCount": 127,
        "rating": 4.8,
        "lastModified": "2025-11-22T11:45:00"
    },
    {
        "id": "SS005",
        "platform": "smartstore",
        "name": "미니 공기청정기 USB형",
        "category": "전자제품",
        "price": 55000,
        "salePrice": 49000,
        "stock": 45,
        "status": "SALE",
        "imageUrl": "https://via.placeholder.com/150/10b981/ffffff?text=AirPurifier",
        "options": [],
        "salesCount": 67,
        "reviewCount": 18,
        "rating": 4.2,
        "lastModified": "2025-11-21T14:30:00"
    }
]

MOCK_COUPANG_PRODUCTS = [
    {
        "id": "CP001",
        "platform": "coupang",
        "name": "프리미엄 무선 이어폰 Pro",
        "category": "전자제품",
        "price": 89000,
        "salePrice": 75000,
        "stock": 200,
        "status": "SALE",
        "imageUrl": "https://via.placeholder.com/150/667eea/ffffff?text=Earphone",
        "options": [
            {"name": "색상", "values": ["화이트", "블랙", "네이비"]}
        ],
        "salesCount": 567,
        "reviewCount": 234,
        "rating": 4.6,
        "rocketDelivery": True,
        "lastModified": "2025-11-25T11:00:00"
    },
    {
        "id": "CP002",
        "platform": "coupang",
        "name": "고급 가죽 지갑 슬림형",
        "category": "패션잡화",
        "price": 45000,
        "salePrice": 37000,
        "stock": 120,
        "status": "SALE",
        "imageUrl": "https://via.placeholder.com/150/764ba2/ffffff?text=Wallet",
        "options": [
            {"name": "색상", "values": ["브라운", "블랙"]}
        ],
        "salesCount": 289,
        "reviewCount": 98,
        "rating": 4.4,
        "rocketDelivery": True,
        "lastModified": "2025-11-24T16:30:00"
    },
    {
        "id": "CP003",
        "platform": "coupang",
        "name": "스마트 LED 무드등 RGB",
        "category": "생활용품",
        "price": 32000,
        "salePrice": 26500,
        "stock": 85,
        "status": "SALE",
        "imageUrl": "https://via.placeholder.com/150/f59e0b/ffffff?text=LED",
        "options": [],
        "salesCount": 156,
        "reviewCount": 45,
        "rating": 4.5,
        "rocketDelivery": False,
        "lastModified": "2025-11-23T10:00:00"
    },
    {
        "id": "CP004",
        "platform": "coupang",
        "name": "프리미엄 텀블러 보온보냉",
        "category": "생활용품",
        "price": 28000,
        "salePrice": 22000,
        "stock": 300,
        "status": "SALE",
        "imageUrl": "https://via.placeholder.com/150/ef4444/ffffff?text=Tumbler",
        "options": [
            {"name": "용량", "values": ["350ml", "500ml"]}
        ],
        "salesCount": 892,
        "reviewCount": 312,
        "rating": 4.7,
        "rocketDelivery": True,
        "lastModified": "2025-11-22T13:00:00"
    },
    {
        "id": "CP005",
        "platform": "coupang",
        "name": "휴대용 보조배터리 20000mAh",
        "category": "전자제품",
        "price": 35000,
        "salePrice": 29000,
        "stock": 60,
        "status": "SALE",
        "imageUrl": "https://via.placeholder.com/150/3b82f6/ffffff?text=Battery",
        "options": [
            {"name": "색상", "values": ["화이트", "블랙"]}
        ],
        "salesCount": 423,
        "reviewCount": 156,
        "rating": 4.4,
        "rocketDelivery": True,
        "lastModified": "2025-11-20T09:30:00"
    },
    {
        "id": "CP006",
        "platform": "coupang",
        "name": "고급 마우스패드 대형",
        "category": "전자제품",
        "price": 15000,
        "salePrice": 12000,
        "stock": 0,
        "status": "OUTOFSTOCK",
        "imageUrl": "https://via.placeholder.com/150/6366f1/ffffff?text=MousePad",
        "options": [],
        "salesCount": 234,
        "reviewCount": 67,
        "rating": 4.3,
        "rocketDelivery": False,
        "lastModified": "2025-11-19T15:00:00"
    }
]

MOCK_ORDERS = [
    {
        "id": "ORD001",
        "platform": "smartstore",
        "productId": "SS001",
        "productName": "프리미엄 무선 이어폰 Pro",
        "quantity": 2,
        "price": 158000,
        "status": "SHIPPING",
        "orderedAt": "2025-11-25T09:30:00",
        "buyerName": "김*민"
    },
    {
        "id": "ORD002",
        "platform": "coupang",
        "productId": "CP002",
        "productName": "고급 가죽 지갑 슬림형",
        "quantity": 1,
        "price": 37000,
        "status": "PREPARING",
        "orderedAt": "2025-11-25T10:15:00",
        "buyerName": "이*진"
    },
    {
        "id": "ORD003",
        "platform": "smartstore",
        "productId": "SS003",
        "productName": "스마트 LED 무드등 RGB",
        "quantity": 3,
        "price": 84000,
        "status": "DELIVERED",
        "orderedAt": "2025-11-24T14:00:00",
        "buyerName": "박*수"
    },
    {
        "id": "ORD004",
        "platform": "coupang",
        "productId": "CP004",
        "productName": "프리미엄 텀블러 보온보냉",
        "quantity": 5,
        "price": 110000,
        "status": "SHIPPING",
        "orderedAt": "2025-11-24T16:45:00",
        "buyerName": "정*영"
    },
    {
        "id": "ORD005",
        "platform": "coupang",
        "productId": "CP001",
        "productName": "프리미엄 무선 이어폰 Pro",
        "quantity": 1,
        "price": 75000,
        "status": "PREPARING",
        "orderedAt": "2025-11-25T11:30:00",
        "buyerName": "최*아"
    }
]

# ===== 네이버 스마트스토어 API 헬퍼 =====
def get_server_outbound_ip():
    """서버의 outbound IP 확인"""
    try:
        response = requests.get('https://api.ipify.org?format=json', timeout=5)
        if response.status_code == 200:
            return response.json().get('ip')
    except:
        pass
    return None

def get_naver_access_token():
    """네이버 커머스 API OAuth 토큰 발급 (bcrypt 서명 사용)"""
    print(f"[Naver API] 토큰 발급 시도...")
    print(f"[Naver API] CLIENT_ID 존재: {bool(NAVER_CLIENT_ID)}, SECRET 존재: {bool(NAVER_CLIENT_SECRET)}")

    # 서버 outbound IP 로깅
    outbound_ip = get_server_outbound_ip()
    print(f"[Naver API] 서버 Outbound IP: {outbound_ip}")

    if not NAVER_CLIENT_ID or not NAVER_CLIENT_SECRET:
        print("[Naver API] CLIENT_ID 또는 SECRET이 없음")
        return None

    timestamp = str(int(time.time() * 1000))

    # bcrypt 서명 생성 (네이버 커머스 API 공식 방식)
    # 1. password = client_id + "_" + timestamp
    # 2. bcrypt 해싱 (client_secret을 salt로 사용)
    # 3. base64 인코딩
    password = f"{NAVER_CLIENT_ID}_{timestamp}"

    try:
        # client_secret을 bcrypt salt 형식으로 사용
        # bcrypt salt는 "$2a$" 또는 "$2b$"로 시작해야 함
        hashed = bcrypt.hashpw(password.encode('utf-8'), NAVER_CLIENT_SECRET.encode('utf-8'))
        signature_base64 = base64.b64encode(hashed).decode('utf-8')
        print(f"[Naver API] bcrypt 서명 생성 완료")
    except Exception as e:
        print(f"[Naver API] bcrypt 서명 생성 실패: {e}")
        return None

    try:
        print(f"[Naver API] 토큰 요청 URL: {NAVER_API_BASE}/v1/oauth2/token")
        print(f"[Naver API] timestamp: {timestamp}")
        response = requests.post(
            f"{NAVER_API_BASE}/v1/oauth2/token",
            data={
                "client_id": NAVER_CLIENT_ID,
                "timestamp": timestamp,
                "client_secret_sign": signature_base64,
                "grant_type": "client_credentials",
                "type": "SELF"
            }
        )
        print(f"[Naver API] 토큰 응답 상태: {response.status_code}")
        print(f"[Naver API] 토큰 응답 내용: {response.text[:500]}")

        if response.status_code == 200:
            data = response.json()
            token = data.get('access_token')
            print(f"[Naver API] 토큰 발급 성공: {token[:20] if token else 'None'}...")
            return token
        else:
            print(f"[Naver API] 토큰 발급 실패: {response.status_code}")
            print(f"[Naver API] 에러 내용: {response.text}")
    except Exception as e:
        print(f"[Naver API] Token error: {e}")
    return None

def call_naver_api(endpoint, method='GET', data=None):
    """네이버 커머스 API 호출"""
    print(f"[Naver API] API 호출 시작: {method} {endpoint}")

    token = get_naver_access_token()
    if not token:
        print("[Naver API] 토큰 없음 - API 호출 중단")
        return None

    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json'
    }

    try:
        url = f"{NAVER_API_BASE}{endpoint}"
        print(f"[Naver API] 요청 URL: {url}")

        if method == 'GET':
            response = requests.get(url, headers=headers)
        elif method == 'POST':
            response = requests.post(url, headers=headers, json=data)
        elif method == 'PUT':
            response = requests.put(url, headers=headers, json=data)

        print(f"[Naver API] 응답 상태: {response.status_code}")
        print(f"[Naver API] 응답 내용: {response.text[:500]}")

        if response.status_code == 200:
            return response.json()
        else:
            print(f"[Naver API] API 호출 실패: {response.status_code}")
    except Exception as e:
        print(f"[Naver API] Error: {e}")
    return None

# ===== 쿠팡 API 헬퍼 =====
def get_coupang_signature(method, uri, query_params=''):
    """쿠팡 API HMAC 서명 생성"""
    if not COUPANG_SECRET_KEY:
        return None, None

    datetime_str = datetime.utcnow().strftime('%y%m%d') + 'T' + datetime.utcnow().strftime('%H%M%S') + 'Z'
    message = datetime_str + method + uri + query_params
    signature = hmac.new(
        COUPANG_SECRET_KEY.encode('utf-8'),
        message.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()

    authorization = f"CEA algorithm=HmacSHA256, access-key={COUPANG_ACCESS_KEY}, signed-date={datetime_str}, signature={signature}"
    return authorization, datetime_str

def call_coupang_api(endpoint, method='GET', data=None):
    """쿠팡 API 호출"""
    if not COUPANG_ACCESS_KEY or not COUPANG_SECRET_KEY:
        return None

    auth, datetime_str = get_coupang_signature(method, endpoint)
    if not auth:
        return None

    headers = {
        'Authorization': auth,
        'Content-Type': 'application/json;charset=UTF-8'
    }

    try:
        url = f"{COUPANG_API_BASE}{endpoint}"
        if method == 'GET':
            response = requests.get(url, headers=headers)
        elif method == 'POST':
            response = requests.post(url, headers=headers, json=data)
        elif method == 'PUT':
            response = requests.put(url, headers=headers, json=data)

        if response.status_code == 200:
            return response.json()
    except Exception as e:
        print(f"[Coupang API] Error: {e}")
    return None

# ===== API 연동 상태 확인 =====
def check_api_status():
    """API 연동 상태 확인"""
    return {
        "smartstore": {
            "connected": bool(NAVER_CLIENT_ID and NAVER_CLIENT_SECRET),
            "clientId": NAVER_CLIENT_ID[:8] + "..." if NAVER_CLIENT_ID else None
        },
        "coupang": {
            "connected": bool(COUPANG_ACCESS_KEY and COUPANG_SECRET_KEY),
            "vendorId": COUPANG_VENDOR_ID if COUPANG_VENDOR_ID else None
        }
    }

# ===== API 엔드포인트 =====

@market_bp.route('/api/market/status', methods=['GET'])
def get_market_status():
    """API 연동 상태 및 요약 정보"""
    api_status = check_api_status()

    # 실제 상품 데이터 가져오기 (내부 호출)
    ss_products = []
    cp_products = []

    # 스마트스토어 상품
    if api_status['smartstore']['connected']:
        result = call_naver_api('/v1/products/search', method='POST', data={"page": 1, "size": 100})
        if result and 'contents' in result:
            for item in result['contents']:
                channel_product = item.get('channelProducts', [{}])[0] if item.get('channelProducts') else item
                ss_products.append({
                    "stock": channel_product.get('stockQuantity') or 0,
                    "salePrice": channel_product.get('discountedPrice') or channel_product.get('salePrice') or 0
                })

    # 쿠팡 상품 (API 연동 시)
    if api_status['coupang']['connected']:
        # 쿠팡 API는 아직 Mock 데이터 사용
        pass

    # API가 연동되지 않은 경우 Mock 데이터 사용
    if not ss_products and not api_status['smartstore']['connected']:
        ss_products = MOCK_SMARTSTORE_PRODUCTS
    if not cp_products:
        cp_products = MOCK_COUPANG_PRODUCTS if not api_status['coupang']['connected'] else []

    all_products = ss_products + cp_products

    summary = {
        "totalProducts": len(all_products),
        "smartstoreProducts": len(ss_products),
        "coupangProducts": len(cp_products),
        "outOfStock": len([p for p in all_products if p.get('stock', 0) == 0]),
        "lowStock": len([p for p in all_products if 0 < p.get('stock', 0) <= 10]),
        "totalOrders": len(MOCK_ORDERS),
        "pendingOrders": len([o for o in MOCK_ORDERS if o['status'] in ['PREPARING', 'SHIPPING']]),
        "todaySales": sum(o['price'] for o in MOCK_ORDERS if o['orderedAt'].startswith('2025-11-25'))
    }

    return jsonify({
        "ok": True,
        "apiStatus": api_status,
        "summary": summary,
        "usingMockData": not (api_status['smartstore']['connected'] or api_status['coupang']['connected'])
    })

@market_bp.route('/api/market/products', methods=['GET'])
def get_products():
    """상품 목록 조회"""
    platform = request.args.get('platform', 'all')  # all, smartstore, coupang
    filter_category = request.args.get('category', '')
    filter_status = request.args.get('status', '')
    search = request.args.get('search', '').lower()
    sort = request.args.get('sort', 'lastModified')
    order = request.args.get('order', 'desc')

    # API 연동 상태 확인
    api_status = check_api_status()

    # 실제 API가 연동된 경우 API에서 데이터 가져오기
    products = []

    if platform in ['all', 'smartstore']:
        if api_status['smartstore']['connected']:
            # 실제 네이버 API 호출 - 상품 검색 API 사용
            search_data = {
                "searchKeywordType": "TITLE",
                "searchKeyword": search if search else None,
                "page": 1,
                "size": 100
            }
            # None 값 제거
            search_data = {k: v for k, v in search_data.items() if v is not None}

            result = call_naver_api('/v1/products/search', method='POST', data=search_data)
            print(f"[Naver API] 상품 검색 결과 타입: {type(result)}")

            if result and 'contents' in result:
                print(f"[Naver API] 상품 개수: {len(result['contents'])}")
                # 첫 번째 상품의 전체 구조 출력
                if result['contents']:
                    print(f"[Naver API] 첫 번째 상품 구조: {json.dumps(result['contents'][0], ensure_ascii=False, default=str)[:1000]}")

                for item in result['contents']:
                    # channelProducts 배열에서 첫 번째 상품 정보 가져오기
                    channel_product = item.get('channelProducts', [{}])[0] if item.get('channelProducts') else item

                    product_name = channel_product.get('name') or item.get('name') or '-'
                    product_id = item.get('originProductNo') or channel_product.get('originProductNo') or ''
                    sale_price = channel_product.get('salePrice') or 0
                    discounted_price = channel_product.get('discountedPrice') or sale_price
                    stock = channel_product.get('stockQuantity') or 0
                    category = channel_product.get('wholeCategoryName') or ''
                    status_type = channel_product.get('statusType') or 'SALE'

                    # 이미지 URL
                    image = channel_product.get('representativeImage', {})
                    if isinstance(image, dict):
                        image_url = image.get('url', '')
                    else:
                        image_url = str(image) if image else ''

                    products.append({
                        "id": str(product_id),
                        "platform": "smartstore",
                        "name": product_name,
                        "category": category.split('>')[-1].strip() if category else '기타',
                        "price": sale_price,
                        "salePrice": discounted_price,
                        "stock": stock,
                        "status": "OUTOFSTOCK" if stock == 0 or status_type == 'OUTOFSTOCK' else "SALE",
                        "imageUrl": image_url,
                        "salesCount": channel_product.get('saleCount', 0) or 0,
                        "reviewCount": channel_product.get('reviewCount', 0) or 0,
                        "rating": channel_product.get('reviewScore', 0) or 0,
                        "lastModified": channel_product.get('modifiedDate', '') or ''
                    })
                print(f"[Naver API] {len(products)}개 상품 로드 완료")
            else:
                print("[Naver API] 상품 데이터 없음 (Mock 데이터 미사용)")
            # API 연동 시 Mock 데이터 사용 안함
        else:
            # API 미연동 시에만 Mock 데이터 사용
            products.extend(MOCK_SMARTSTORE_PRODUCTS)

    if platform in ['all', 'coupang']:
        if api_status['coupang']['connected']:
            # 실제 쿠팡 API 호출
            print("[Coupang API] 상품 조회 시도...")
            result = call_coupang_api(f'/v2/providers/seller_api/apis/api/v1/marketplace/seller-products')
            if result and 'data' in result:
                print(f"[Coupang API] {len(result['data'])}개 상품 로드")
                for item in result['data']:
                    products.append({
                        "id": str(item.get('sellerProductId', '')),
                        "platform": "coupang",
                        "name": item.get('sellerProductName', ''),
                        "category": item.get('displayCategoryName', '기타'),
                        "price": item.get('salePrice', 0),
                        "salePrice": item.get('salePrice', 0),
                        "stock": item.get('maximumBuyCount', 0),
                        "status": "SALE",
                        "imageUrl": "",
                        "salesCount": 0,
                        "reviewCount": 0,
                        "rating": 0,
                        "lastModified": ""
                    })
            else:
                print("[Coupang API] 상품 데이터 없음 (Mock 데이터 미사용)")
            # API 연동 시 Mock 데이터 사용 안함
        else:
            # API 미연동 시에만 Mock 데이터 사용
            products.extend(MOCK_COUPANG_PRODUCTS)

    # 필터링
    if filter_category:
        products = [p for p in products if p.get('category') == filter_category]
    if filter_status:
        products = [p for p in products if p.get('status') == filter_status]
    if search:
        products = [p for p in products if search in p.get('name', '').lower()]

    # 정렬
    reverse = order == 'desc'
    if sort == 'price':
        products.sort(key=lambda x: x.get('salePrice', 0), reverse=reverse)
    elif sort == 'stock':
        products.sort(key=lambda x: x.get('stock', 0), reverse=reverse)
    elif sort == 'sales':
        products.sort(key=lambda x: x.get('salesCount', 0), reverse=reverse)
    elif sort == 'lastModified':
        products.sort(key=lambda x: x.get('lastModified', ''), reverse=reverse)

    return jsonify({
        "ok": True,
        "products": products,
        "total": len(products),
        "usingMockData": not (api_status['smartstore']['connected'] or api_status['coupang']['connected'])
    })

@market_bp.route('/api/market/products/<product_id>', methods=['GET'])
def get_product_detail(product_id):
    """상품 상세 정보"""
    all_products = MOCK_SMARTSTORE_PRODUCTS + MOCK_COUPANG_PRODUCTS
    product = next((p for p in all_products if p['id'] == product_id), None)

    if not product:
        return jsonify({"ok": False, "error": "상품을 찾을 수 없습니다."}), 404

    return jsonify({"ok": True, "product": product})

@market_bp.route('/api/market/products/<product_id>', methods=['PUT'])
def update_product(product_id):
    """상품 정보 수정"""
    data = request.get_json()

    # Mock 데이터에서 상품 찾기
    all_products = MOCK_SMARTSTORE_PRODUCTS + MOCK_COUPANG_PRODUCTS
    product = next((p for p in all_products if p['id'] == product_id), None)

    if not product:
        return jsonify({"ok": False, "error": "상품을 찾을 수 없습니다."}), 404

    # API 연동 상태 확인
    api_status = check_api_status()

    # 실제 API로 업데이트
    if product['platform'] == 'smartstore' and api_status['smartstore']['connected']:
        result = call_naver_api(f'/v2/products/{product_id}', method='PUT', data={
            "salePrice": data.get('salePrice'),
            "stockQuantity": data.get('stock')
        })
        if not result:
            return jsonify({"ok": False, "error": "스마트스토어 API 오류"}), 500

    elif product['platform'] == 'coupang' and api_status['coupang']['connected']:
        result = call_coupang_api(f'/v2/providers/seller_api/apis/api/v1/marketplace/seller-products/{product_id}',
                                   method='PUT', data=data)
        if not result:
            return jsonify({"ok": False, "error": "쿠팡 API 오류"}), 500

    # Mock 데이터 업데이트 (시뮬레이션)
    for key, value in data.items():
        if key in product:
            product[key] = value
    product['lastModified'] = datetime.now().isoformat()

    return jsonify({
        "ok": True,
        "message": "상품이 수정되었습니다.",
        "product": product
    })

@market_bp.route('/api/market/products', methods=['POST'])
def create_product():
    """새 상품 등록"""
    data = request.get_json()

    platform = data.get('platform', 'smartstore')
    api_status = check_api_status()

    # 필수 필드 검증
    required = ['name', 'price', 'stock', 'category']
    for field in required:
        if not data.get(field):
            return jsonify({"ok": False, "error": f"{field} 필드가 필요합니다."}), 400

    new_product = {
        "id": f"{'SS' if platform == 'smartstore' else 'CP'}{str(int(time.time()))[-6:]}",
        "platform": platform,
        "name": data['name'],
        "category": data['category'],
        "price": int(data['price']),
        "salePrice": int(data.get('salePrice', data['price'])),
        "stock": int(data['stock']),
        "status": "SALE" if int(data['stock']) > 0 else "OUTOFSTOCK",
        "imageUrl": data.get('imageUrl', ''),
        "options": data.get('options', []),
        "salesCount": 0,
        "reviewCount": 0,
        "rating": 0,
        "lastModified": datetime.now().isoformat()
    }

    if platform == 'coupang':
        new_product['rocketDelivery'] = data.get('rocketDelivery', False)

    # 실제 API로 등록
    if platform == 'smartstore' and api_status['smartstore']['connected']:
        result = call_naver_api('/v2/products', method='POST', data={
            "name": new_product['name'],
            "salePrice": new_product['salePrice'],
            "stockQuantity": new_product['stock'],
            # ... 추가 필드
        })
        if result:
            new_product['id'] = result.get('originProductNo', new_product['id'])

    elif platform == 'coupang' and api_status['coupang']['connected']:
        result = call_coupang_api('/v2/providers/seller_api/apis/api/v1/marketplace/seller-products',
                                   method='POST', data=data)
        if result:
            new_product['id'] = result.get('sellerProductId', new_product['id'])

    # Mock 데이터에 추가
    if platform == 'smartstore':
        MOCK_SMARTSTORE_PRODUCTS.append(new_product)
    else:
        MOCK_COUPANG_PRODUCTS.append(new_product)

    return jsonify({
        "ok": True,
        "message": "상품이 등록되었습니다.",
        "product": new_product
    })

@market_bp.route('/api/market/products/<product_id>', methods=['DELETE'])
def delete_product(product_id):
    """상품 삭제"""
    global MOCK_SMARTSTORE_PRODUCTS, MOCK_COUPANG_PRODUCTS

    # Mock 데이터에서 삭제
    MOCK_SMARTSTORE_PRODUCTS = [p for p in MOCK_SMARTSTORE_PRODUCTS if p['id'] != product_id]
    MOCK_COUPANG_PRODUCTS = [p for p in MOCK_COUPANG_PRODUCTS if p['id'] != product_id]

    return jsonify({"ok": True, "message": "상품이 삭제되었습니다."})

@market_bp.route('/api/market/products/bulk-update', methods=['POST'])
def bulk_update_products():
    """상품 일괄 수정 (가격, 재고 등)"""
    data = request.get_json()
    product_ids = data.get('productIds', [])
    updates = data.get('updates', {})

    if not product_ids:
        return jsonify({"ok": False, "error": "상품 ID가 필요합니다."}), 400

    updated = []
    all_products = MOCK_SMARTSTORE_PRODUCTS + MOCK_COUPANG_PRODUCTS

    for product in all_products:
        if product['id'] in product_ids:
            for key, value in updates.items():
                if key in product:
                    # 퍼센트 변경 처리
                    if key in ['price', 'salePrice'] and isinstance(value, str) and value.endswith('%'):
                        percent = float(value[:-1]) / 100
                        product[key] = int(product[key] * (1 + percent))
                    else:
                        product[key] = value
            product['lastModified'] = datetime.now().isoformat()
            updated.append(product['id'])

    return jsonify({
        "ok": True,
        "message": f"{len(updated)}개 상품이 수정되었습니다.",
        "updatedIds": updated
    })

@market_bp.route('/api/market/orders', methods=['GET'])
def get_orders():
    """주문 목록 조회"""
    platform = request.args.get('platform', 'all')
    status = request.args.get('status', '')

    orders = MOCK_ORDERS.copy()

    if platform != 'all':
        orders = [o for o in orders if o['platform'] == platform]
    if status:
        orders = [o for o in orders if o['status'] == status]

    # 최신순 정렬
    orders.sort(key=lambda x: x['orderedAt'], reverse=True)

    return jsonify({
        "ok": True,
        "orders": orders,
        "total": len(orders)
    })

@market_bp.route('/api/market/categories', methods=['GET'])
def get_categories():
    """카테고리 목록"""
    all_products = MOCK_SMARTSTORE_PRODUCTS + MOCK_COUPANG_PRODUCTS
    categories = list(set(p['category'] for p in all_products))

    return jsonify({
        "ok": True,
        "categories": sorted(categories)
    })

@market_bp.route('/api/market/price-compare', methods=['GET'])
def compare_prices():
    """스마트스토어 vs 쿠팡 가격 비교"""
    comparisons = []

    # 상품명으로 매칭
    for ss_product in MOCK_SMARTSTORE_PRODUCTS:
        for cp_product in MOCK_COUPANG_PRODUCTS:
            if ss_product['name'] == cp_product['name']:
                diff = ss_product['salePrice'] - cp_product['salePrice']
                diff_percent = (diff / cp_product['salePrice']) * 100 if cp_product['salePrice'] else 0

                comparisons.append({
                    "name": ss_product['name'],
                    "smartstore": {
                        "id": ss_product['id'],
                        "price": ss_product['salePrice'],
                        "stock": ss_product['stock']
                    },
                    "coupang": {
                        "id": cp_product['id'],
                        "price": cp_product['salePrice'],
                        "stock": cp_product['stock'],
                        "rocketDelivery": cp_product.get('rocketDelivery', False)
                    },
                    "priceDiff": diff,
                    "priceDiffPercent": round(diff_percent, 1)
                })

    return jsonify({
        "ok": True,
        "comparisons": comparisons
    })

@market_bp.route('/api/market/sync-prices', methods=['POST'])
def sync_prices():
    """플랫폼 간 가격 동기화"""
    data = request.get_json()
    source = data.get('source', 'smartstore')  # 기준 플랫폼
    target = data.get('target', 'coupang')
    adjustment = data.get('adjustment', 0)  # 가격 조정 (원 또는 %)

    synced = []
    source_products = MOCK_SMARTSTORE_PRODUCTS if source == 'smartstore' else MOCK_COUPANG_PRODUCTS
    target_products = MOCK_COUPANG_PRODUCTS if target == 'coupang' else MOCK_SMARTSTORE_PRODUCTS

    for src in source_products:
        for tgt in target_products:
            if src['name'] == tgt['name']:
                new_price = src['salePrice']
                if isinstance(adjustment, str) and adjustment.endswith('%'):
                    percent = float(adjustment[:-1]) / 100
                    new_price = int(new_price * (1 + percent))
                else:
                    new_price = int(new_price + adjustment)

                tgt['salePrice'] = new_price
                tgt['lastModified'] = datetime.now().isoformat()
                synced.append(tgt['id'])

    return jsonify({
        "ok": True,
        "message": f"{len(synced)}개 상품 가격이 동기화되었습니다.",
        "syncedIds": synced
    })

@market_bp.route('/api/market/analytics', methods=['GET'])
def get_analytics():
    """판매 분석 데이터"""
    period = request.args.get('period', '7d')  # 7d, 30d, 90d
    api_status = check_api_status()

    # 실제 데이터 또는 Mock 데이터 사용
    ss_products = []
    cp_products = []

    # 스마트스토어 상품
    if api_status['smartstore']['connected']:
        result = call_naver_api('/v1/products/search', method='POST', data={"page": 1, "size": 100})
        if result and 'contents' in result:
            for item in result['contents']:
                channel_product = item.get('channelProducts', [{}])[0] if item.get('channelProducts') else item
                ss_products.append({
                    "id": str(item.get('originProductNo', '')),
                    "platform": "smartstore",
                    "name": channel_product.get('name', ''),
                    "category": (channel_product.get('wholeCategoryName') or '').split('>')[-1].strip() or '기타',
                    "salePrice": channel_product.get('discountedPrice') or channel_product.get('salePrice') or 0,
                    "stock": channel_product.get('stockQuantity') or 0,
                    "salesCount": channel_product.get('saleCount', 0) or 0,
                    "rating": channel_product.get('reviewScore', 0) or 0
                })
    else:
        ss_products = MOCK_SMARTSTORE_PRODUCTS

    # 쿠팡 상품
    if not api_status['coupang']['connected']:
        cp_products = MOCK_COUPANG_PRODUCTS

    all_products = ss_products + cp_products

    total_sales = sum(p.get('salesCount', 0) for p in all_products)
    total_revenue = sum(p.get('salesCount', 0) * p.get('salePrice', 0) for p in all_products)
    avg_rating = sum(p.get('rating', 0) for p in all_products) / len(all_products) if all_products else 0

    # 카테고리별 판매
    category_sales = {}
    for p in all_products:
        cat = p.get('category', '기타')
        if cat not in category_sales:
            category_sales[cat] = {"count": 0, "revenue": 0}
        category_sales[cat]['count'] += p.get('salesCount', 0)
        category_sales[cat]['revenue'] += p.get('salesCount', 0) * p.get('salePrice', 0)

    # 플랫폼별 판매
    platform_sales = {
        "smartstore": {
            "count": sum(p.get('salesCount', 0) for p in ss_products),
            "revenue": sum(p.get('salesCount', 0) * p.get('salePrice', 0) for p in ss_products)
        },
        "coupang": {
            "count": sum(p.get('salesCount', 0) for p in cp_products),
            "revenue": sum(p.get('salesCount', 0) * p.get('salePrice', 0) for p in cp_products)
        }
    }

    # 베스트셀러 상품
    bestsellers = sorted(all_products, key=lambda x: x.get('salesCount', 0), reverse=True)[:5]

    return jsonify({
        "ok": True,
        "period": period,
        "analytics": {
            "totalSales": total_sales,
            "totalRevenue": total_revenue,
            "averageRating": round(avg_rating, 2),
            "categorySales": category_sales,
            "platformSales": platform_sales,
            "bestsellers": [{
                "id": p['id'],
                "name": p['name'],
                "platform": p['platform'],
                "sales": p.get('salesCount', 0),
                "revenue": p.get('salesCount', 0) * p.get('salePrice', 0)
            } for p in bestsellers]
        }
    })

# ===== 내부 헬퍼: 실제 상품 데이터 가져오기 =====
def fetch_products_for_ai():
    """AI 채팅용 실제 상품 데이터 가져오기"""
    api_status = check_api_status()
    products = []
    smartstore_count = 0
    coupang_count = 0

    # 스마트스토어 상품 가져오기
    if api_status['smartstore']['connected']:
        search_data = {"page": 1, "size": 100}
        result = call_naver_api('/v1/products/search', method='POST', data=search_data)
        if result and 'contents' in result:
            for item in result['contents']:
                channel_product = item.get('channelProducts', [{}])[0] if item.get('channelProducts') else item
                product_name = channel_product.get('name') or item.get('name') or '-'
                sale_price = channel_product.get('salePrice') or 0
                discounted_price = channel_product.get('discountedPrice') or sale_price
                stock = channel_product.get('stockQuantity') or 0
                category = channel_product.get('wholeCategoryName') or ''
                status_type = channel_product.get('statusType') or 'SALE'

                products.append({
                    "id": str(item.get('originProductNo', '')),
                    "platform": "smartstore",
                    "name": product_name,
                    "category": category.split('>')[-1].strip() if category else '기타',
                    "price": sale_price,
                    "salePrice": discounted_price,
                    "stock": stock,
                    "status": "OUTOFSTOCK" if stock == 0 or status_type == 'OUTOFSTOCK' else "SALE",
                    "salesCount": channel_product.get('saleCount', 0) or 0,
                    "reviewCount": channel_product.get('reviewCount', 0) or 0,
                    "rating": channel_product.get('reviewScore', 0) or 0
                })
                smartstore_count += 1
    else:
        products.extend(MOCK_SMARTSTORE_PRODUCTS)
        smartstore_count = len(MOCK_SMARTSTORE_PRODUCTS)

    # 쿠팡 상품 가져오기
    if api_status['coupang']['connected']:
        result = call_coupang_api(f'/v2/providers/seller_api/apis/api/v1/marketplace/seller-products')
        if result and 'data' in result:
            for item in result['data']:
                products.append({
                    "id": str(item.get('sellerProductId', '')),
                    "platform": "coupang",
                    "name": item.get('sellerProductName', ''),
                    "category": item.get('displayCategoryName', '기타'),
                    "price": item.get('salePrice', 0),
                    "salePrice": item.get('salePrice', 0),
                    "stock": item.get('maximumBuyCount', 0),
                    "status": "SALE",
                    "salesCount": 0,
                    "reviewCount": 0,
                    "rating": 0
                })
                coupang_count += 1
    else:
        products.extend(MOCK_COUPANG_PRODUCTS)
        coupang_count = len(MOCK_COUPANG_PRODUCTS)

    return products, smartstore_count, coupang_count

# ===== AI 채팅 =====
@market_bp.route('/api/market/ai-chat', methods=['POST'])
def market_ai_chat():
    """마켓 관련 AI 채팅 (HS 코드, 마진 계산, 상품 질문 등)"""
    data = request.get_json()
    user_message = data.get('message', '')

    if not user_message:
        return jsonify({"ok": False, "error": "메시지가 필요합니다."}), 400

    # 실제 상품 데이터 가져오기
    all_products, smartstore_count, coupang_count = fetch_products_for_ai()

    # 품절 상품
    out_of_stock = [p for p in all_products if p.get('stock', 0) == 0 or p.get('status') == 'OUTOFSTOCK']
    # 저재고 상품 (10개 이하)
    low_stock = [p for p in all_products if 0 < p.get('stock', 0) <= 10]
    # 베스트셀러 (판매량 기준 상위 5개)
    bestsellers = sorted(all_products, key=lambda x: x.get('salesCount', 0), reverse=True)[:5]
    # 평균 가격
    avg_price = sum(p.get('salePrice', 0) for p in all_products) / len(all_products) if all_products else 0

    product_summary = f"""
현재 등록된 상품 요약:
- 스마트스토어: {smartstore_count}개
- 쿠팡: {coupang_count}개
- 총 상품 수: {len(all_products)}개
- 품절 상품: {len(out_of_stock)}개
- 저재고 상품 (10개 이하): {len(low_stock)}개
- 평균 판매가: {avg_price:,.0f}원

베스트셀러 상품 (판매량 기준):
"""
    for i, p in enumerate(bestsellers, 1):
        product_summary += f"{i}. {p['name']}: {p.get('salePrice', 0):,}원, 판매 {p.get('salesCount', 0)}개\n"

    product_summary += "\n전체 상품 목록 (상위 20개):\n"
    for p in all_products[:20]:
        stock_status = "품절" if p.get('stock', 0) == 0 else f"재고 {p.get('stock', 0)}개"
        product_summary += f"- {p['name']} ({p['platform']}): {p.get('salePrice', 0):,}원, {stock_status}\n"

    system_prompt = f"""당신은 온라인 쇼핑몰 판매자를 돕는 전문 AI 어시스턴트입니다.

## 제공 가능한 서비스:

### 1. 상품 분석 및 최적화
- 현재 등록된 상품 분석 (가격, 재고, 판매량)
- 품절/저재고 상품 알림 및 재입고 우선순위 추천
- 베스트셀러 분석 및 성공 요인 파악
- 카테고리별 상품 분포 분석

### 2. 마진 계산
- 원가, 판매가, 수수료를 고려한 순마진 계산
- 스마트스토어 수수료: 약 5-10% (카테고리별 상이)
- 쿠팡 수수료: 약 10-15% (로켓/직배송 상이)
- 목표 마진율에 따른 적정 판매가 역산

### 3. 가격 전략 추천
- 경쟁 가격 분석 (같은 카테고리 평균가 비교)
- 가격 인상/인하 제안
- 번들/패키지 가격 전략

### 4. HS 코드 조회
- 상품의 관세 분류 코드 안내
- 수입 상품의 관세율 정보

### 5. 판매 팁
- 스마트스토어/쿠팡 알고리즘 최적화 방법
- 상품명/키워드 최적화 제안
- 리뷰 관리 및 고객 응대 팁

{product_summary}

## 응답 가이드:
- 구체적인 숫자와 데이터를 활용해서 분석해주세요
- 실행 가능한 액션 아이템을 제안해주세요
- 한국어로 답변하세요"""

    try:
        response = openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message}
            ],
            max_tokens=1000,
            temperature=0.7
        )

        ai_response = response.choices[0].message.content

        return jsonify({
            "ok": True,
            "response": ai_response
        })

    except Exception as e:
        print(f"[AI Chat Error] {e}")
        return jsonify({
            "ok": False,
            "error": "AI 응답 생성 중 오류가 발생했습니다.",
            "detail": str(e)
        }), 500

# ===== 상품 분석 API =====
@market_bp.route('/api/market/analysis', methods=['GET'])
def get_product_analysis():
    """상품 데이터 종합 분석"""
    all_products, smartstore_count, coupang_count = fetch_products_for_ai()

    if not all_products:
        return jsonify({
            "ok": True,
            "analysis": {
                "summary": "등록된 상품이 없습니다.",
                "recommendations": []
            }
        })

    # 기본 통계
    total_products = len(all_products)
    out_of_stock = [p for p in all_products if p.get('stock', 0) == 0 or p.get('status') == 'OUTOFSTOCK']
    low_stock = [p for p in all_products if 0 < p.get('stock', 0) <= 10]

    # 가격 분석
    prices = [p.get('salePrice', 0) for p in all_products if p.get('salePrice', 0) > 0]
    avg_price = sum(prices) / len(prices) if prices else 0
    min_price = min(prices) if prices else 0
    max_price = max(prices) if prices else 0

    # 판매량 분석
    sales = [p.get('salesCount', 0) for p in all_products]
    total_sales = sum(sales)
    avg_sales = total_sales / len(sales) if sales else 0

    # 베스트셀러
    bestsellers = sorted(all_products, key=lambda x: x.get('salesCount', 0), reverse=True)[:5]

    # 카테고리별 분석
    category_stats = {}
    for p in all_products:
        cat = p.get('category', '기타')
        if cat not in category_stats:
            category_stats[cat] = {'count': 0, 'totalSales': 0, 'totalPrice': 0}
        category_stats[cat]['count'] += 1
        category_stats[cat]['totalSales'] += p.get('salesCount', 0)
        category_stats[cat]['totalPrice'] += p.get('salePrice', 0)

    category_analysis = []
    for cat, stats in category_stats.items():
        category_analysis.append({
            'category': cat,
            'productCount': stats['count'],
            'totalSales': stats['totalSales'],
            'avgPrice': stats['totalPrice'] / stats['count'] if stats['count'] > 0 else 0
        })
    category_analysis.sort(key=lambda x: x['totalSales'], reverse=True)

    # 추천 생성
    recommendations = []

    # 품절 상품 추천
    if out_of_stock:
        recommendations.append({
            'type': 'warning',
            'title': '품절 상품 재입고 필요',
            'message': f'{len(out_of_stock)}개 상품이 품절 상태입니다. 빠른 재입고가 필요합니다.',
            'products': [{'id': p['id'], 'name': p['name']} for p in out_of_stock[:5]]
        })

    # 저재고 상품 추천
    if low_stock:
        recommendations.append({
            'type': 'info',
            'title': '저재고 상품 주의',
            'message': f'{len(low_stock)}개 상품의 재고가 10개 이하입니다.',
            'products': [{'id': p['id'], 'name': p['name'], 'stock': p['stock']} for p in low_stock[:5]]
        })

    # 가격 이상치 추천
    if avg_price > 0:
        high_price_products = [p for p in all_products if p.get('salePrice', 0) > avg_price * 2]
        low_price_products = [p for p in all_products if 0 < p.get('salePrice', 0) < avg_price * 0.3]

        if high_price_products:
            recommendations.append({
                'type': 'tip',
                'title': '고가 상품 마케팅 강화',
                'message': f'평균 가격의 2배 이상인 {len(high_price_products)}개 상품은 프리미엄 마케팅이 필요합니다.',
                'products': [{'id': p['id'], 'name': p['name'], 'price': p['salePrice']} for p in high_price_products[:3]]
            })

        if low_price_products:
            recommendations.append({
                'type': 'tip',
                'title': '저가 상품 가격 검토',
                'message': f'평균 가격의 30% 미만인 {len(low_price_products)}개 상품의 마진을 점검하세요.',
                'products': [{'id': p['id'], 'name': p['name'], 'price': p['salePrice']} for p in low_price_products[:3]]
            })

    # 베스트셀러 분석 추천
    if bestsellers and bestsellers[0].get('salesCount', 0) > 0:
        recommendations.append({
            'type': 'success',
            'title': '베스트셀러 확장 기회',
            'message': f'"{bestsellers[0]["name"]}"이(가) 가장 많이 팔리고 있습니다. 유사 상품 추가를 고려하세요.',
            'products': [{'id': p['id'], 'name': p['name'], 'sales': p.get('salesCount', 0)} for p in bestsellers[:3]]
        })

    return jsonify({
        "ok": True,
        "analysis": {
            "summary": {
                "totalProducts": total_products,
                "smartstoreCount": smartstore_count,
                "coupangCount": coupang_count,
                "outOfStock": len(out_of_stock),
                "lowStock": len(low_stock),
                "totalSales": total_sales
            },
            "priceAnalysis": {
                "average": round(avg_price),
                "min": min_price,
                "max": max_price
            },
            "salesAnalysis": {
                "totalSales": total_sales,
                "averageSales": round(avg_sales, 1)
            },
            "bestsellers": [{
                "id": p['id'],
                "name": p['name'],
                "platform": p['platform'],
                "price": p.get('salePrice', 0),
                "sales": p.get('salesCount', 0)
            } for p in bestsellers],
            "categoryAnalysis": category_analysis[:10],
            "recommendations": recommendations
        }
    })

# ===== 마진 계산기 API =====
@market_bp.route('/api/market/calculate-margin', methods=['POST'])
def calculate_margin():
    """마진 계산기"""
    data = request.get_json()

    cost_price = data.get('costPrice', 0)  # 원가
    sale_price = data.get('salePrice', 0)  # 판매가
    platform = data.get('platform', 'smartstore')  # 플랫폼
    shipping_cost = data.get('shippingCost', 0)  # 배송비 (판매자 부담)

    # 플랫폼별 수수료율
    commission_rates = {
        'smartstore': 0.055,  # 네이버 기본 5.5%
        'coupang': 0.108,     # 쿠팡 기본 10.8%
        'coupang_rocket': 0.15  # 로켓배송 15%
    }

    commission_rate = commission_rates.get(platform, 0.1)

    # 계산
    commission = sale_price * commission_rate
    total_cost = cost_price + shipping_cost + commission
    profit = sale_price - total_cost
    margin_rate = (profit / sale_price * 100) if sale_price > 0 else 0

    return jsonify({
        "ok": True,
        "calculation": {
            "costPrice": cost_price,
            "salePrice": sale_price,
            "platform": platform,
            "commissionRate": f"{commission_rate * 100:.1f}%",
            "commission": round(commission),
            "shippingCost": shipping_cost,
            "totalCost": round(total_cost),
            "profit": round(profit),
            "marginRate": f"{margin_rate:.1f}%",
            "profitable": profit > 0
        }
    })
