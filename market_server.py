"""
Market Server - 스마트스토어 & 쿠팡 상품 관리 API
"""
import os
import json
import hmac
import hashlib
import time
import requests
from datetime import datetime
from flask import Blueprint, request, jsonify

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
def get_naver_access_token():
    """네이버 커머스 API OAuth 토큰 발급"""
    if not NAVER_CLIENT_ID or not NAVER_CLIENT_SECRET:
        return None

    timestamp = str(int(time.time() * 1000))
    password = f"{NAVER_CLIENT_ID}_{timestamp}"
    signature = hmac.new(
        NAVER_CLIENT_SECRET.encode('utf-8'),
        password.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()

    try:
        response = requests.post(
            f"{NAVER_API_BASE}/v1/oauth2/token",
            data={
                "client_id": NAVER_CLIENT_ID,
                "timestamp": timestamp,
                "client_secret_sign": signature,
                "grant_type": "client_credentials",
                "type": "SELF"
            }
        )
        if response.status_code == 200:
            return response.json().get('access_token')
    except Exception as e:
        print(f"[Naver API] Token error: {e}")
    return None

def call_naver_api(endpoint, method='GET', data=None):
    """네이버 커머스 API 호출"""
    token = get_naver_access_token()
    if not token:
        return None

    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json'
    }

    try:
        url = f"{NAVER_API_BASE}{endpoint}"
        if method == 'GET':
            response = requests.get(url, headers=headers)
        elif method == 'POST':
            response = requests.post(url, headers=headers, json=data)
        elif method == 'PUT':
            response = requests.put(url, headers=headers, json=data)

        if response.status_code == 200:
            return response.json()
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

    # Mock 데이터 기반 요약 (실제 연동 시 API에서 가져옴)
    all_products = MOCK_SMARTSTORE_PRODUCTS + MOCK_COUPANG_PRODUCTS

    summary = {
        "totalProducts": len(all_products),
        "smartstoreProducts": len(MOCK_SMARTSTORE_PRODUCTS),
        "coupangProducts": len(MOCK_COUPANG_PRODUCTS),
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
    category = request.args.get('category', '')
    status = request.args.get('status', '')
    search = request.args.get('search', '').lower()
    sort = request.args.get('sort', 'lastModified')
    order = request.args.get('order', 'desc')

    # API 연동 상태 확인
    api_status = check_api_status()

    # 실제 API가 연동된 경우 API에서 데이터 가져오기
    products = []

    if platform in ['all', 'smartstore']:
        if api_status['smartstore']['connected']:
            # 실제 네이버 API 호출
            result = call_naver_api('/v2/products')
            if result and 'contents' in result:
                for item in result['contents']:
                    products.append({
                        "id": item.get('originProductNo'),
                        "platform": "smartstore",
                        "name": item.get('name'),
                        "price": item.get('salePrice'),
                        "stock": item.get('stockQuantity', 0),
                        # ... 추가 필드 매핑
                    })
            else:
                products.extend(MOCK_SMARTSTORE_PRODUCTS)
        else:
            products.extend(MOCK_SMARTSTORE_PRODUCTS)

    if platform in ['all', 'coupang']:
        if api_status['coupang']['connected']:
            # 실제 쿠팡 API 호출
            result = call_coupang_api(f'/v2/providers/seller_api/apis/api/v1/marketplace/seller-products')
            if result and 'data' in result:
                for item in result['data']:
                    products.append({
                        "id": item.get('sellerProductId'),
                        "platform": "coupang",
                        "name": item.get('sellerProductName'),
                        "price": item.get('salePrice'),
                        "stock": item.get('maximumBuyCount', 0),
                        # ... 추가 필드 매핑
                    })
            else:
                products.extend(MOCK_COUPANG_PRODUCTS)
        else:
            products.extend(MOCK_COUPANG_PRODUCTS)

    # 필터링
    if category:
        products = [p for p in products if p.get('category') == category]
    if status:
        products = [p for p in products if p.get('status') == status]
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

    # Mock 분석 데이터
    all_products = MOCK_SMARTSTORE_PRODUCTS + MOCK_COUPANG_PRODUCTS

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
            "count": sum(p.get('salesCount', 0) for p in MOCK_SMARTSTORE_PRODUCTS),
            "revenue": sum(p.get('salesCount', 0) * p.get('salePrice', 0) for p in MOCK_SMARTSTORE_PRODUCTS)
        },
        "coupang": {
            "count": sum(p.get('salesCount', 0) for p in MOCK_COUPANG_PRODUCTS),
            "revenue": sum(p.get('salesCount', 0) * p.get('salePrice', 0) for p in MOCK_COUPANG_PRODUCTS)
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
