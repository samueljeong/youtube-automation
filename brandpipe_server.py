"""
Brandpipe Server - AI 공급처 탐색 및 마진 분석 API
쿠팡/네이버 상품 URL 또는 키워드로 도매처 후보를 찾고 예상 마진을 계산
"""
import os
import re
import json
import time
import sqlite3
import requests
from datetime import datetime
from flask import Blueprint, request, jsonify, render_template
from bs4 import BeautifulSoup
from urllib.parse import urlparse, quote

# Blueprint 생성
brandpipe_bp = Blueprint('brandpipe', __name__)

# ===== Database 설정 =====
DATABASE_URL = os.getenv('DATABASE_URL')
USE_POSTGRES = DATABASE_URL is not None

if USE_POSTGRES:
    import psycopg2
    from psycopg2.extras import RealDictCursor

    if DATABASE_URL.startswith('postgres://'):
        DATABASE_URL = DATABASE_URL.replace('postgres://', 'postgresql://', 1)

def get_brandpipe_db():
    """브랜드파이프용 DB 연결"""
    if USE_POSTGRES:
        conn = psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)
        return conn
    else:
        db_path = os.path.join(os.path.dirname(__file__), 'brandpipe.db')
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        return conn

def init_brandpipe_db():
    """브랜드파이프 테이블 초기화"""
    conn = get_brandpipe_db()
    cursor = conn.cursor()

    if USE_POSTGRES:
        # brandpipe_searches 테이블
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS brandpipe_searches (
                id SERIAL PRIMARY KEY,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                input_url VARCHAR(500),
                input_keyword VARCHAR(200),
                product_title VARCHAR(300),
                product_brand VARCHAR(200),
                product_price INTEGER,
                result_json TEXT,
                is_favorite BOOLEAN DEFAULT FALSE,
                note VARCHAR(500)
            )
        ''')

        # 기존 테이블에 컬럼 추가 (마이그레이션)
        try:
            cursor.execute("ALTER TABLE brandpipe_searches ADD COLUMN IF NOT EXISTS is_favorite BOOLEAN DEFAULT FALSE")
            cursor.execute("ALTER TABLE brandpipe_searches ADD COLUMN IF NOT EXISTS note VARCHAR(500)")
        except Exception as e:
            print(f"[Brandpipe] 컬럼 추가 스킵 (이미 존재할 수 있음): {e}")

        # brandpipe_watchlist 테이블
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS brandpipe_watchlist (
                id SERIAL PRIMARY KEY,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                search_id INTEGER REFERENCES brandpipe_searches(id),
                product_title VARCHAR(300) NOT NULL,
                product_url VARCHAR(500),
                platform VARCHAR(50),
                target_margin_rate FLOAT,
                target_margin_amount INTEGER,
                last_checked_at TIMESTAMP,
                last_best_margin_rate FLOAT,
                last_best_margin_amount INTEGER
            )
        ''')
    else:
        # SQLite: brandpipe_searches 테이블
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS brandpipe_searches (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                input_url TEXT,
                input_keyword TEXT,
                product_title TEXT,
                product_brand TEXT,
                product_price INTEGER,
                result_json TEXT,
                is_favorite INTEGER DEFAULT 0,
                note TEXT
            )
        ''')

        # SQLite 마이그레이션: 기존 테이블에 컬럼 추가
        try:
            cursor.execute("ALTER TABLE brandpipe_searches ADD COLUMN is_favorite INTEGER DEFAULT 0")
        except Exception:
            pass  # 이미 존재
        try:
            cursor.execute("ALTER TABLE brandpipe_searches ADD COLUMN note TEXT")
        except Exception:
            pass  # 이미 존재

        # SQLite: brandpipe_watchlist 테이블
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS brandpipe_watchlist (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                search_id INTEGER,
                product_title TEXT NOT NULL,
                product_url TEXT,
                platform TEXT,
                target_margin_rate REAL,
                target_margin_amount INTEGER,
                last_checked_at TIMESTAMP,
                last_best_margin_rate REAL,
                last_best_margin_amount INTEGER,
                FOREIGN KEY (search_id) REFERENCES brandpipe_searches(id)
            )
        ''')

    conn.commit()
    conn.close()

# 서버 시작 시 테이블 초기화
try:
    init_brandpipe_db()
except Exception as e:
    print(f"[Brandpipe] DB 초기화 오류: {e}")


# ===== 공통 헤더 =====
COMMON_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    'Accept-Language': 'ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7',
    'Accept-Encoding': 'gzip, deflate, br',
    'Connection': 'keep-alive',
}


# ===== 도매 크롤러 설정 =====
"""
SupplierResult 공통 구조:
{
    "source": "domeggook" | "domeme" | "naver_shopping" | "mock" | ...,
    "name": "상품명",
    "url": "상품 상세 페이지 URL",
    "unit_price": 2500,      # 1개 기준 가격 (원)
    "original_price": 25000, # 묶음/박스 전체 가격 (있으면)
    "unit_desc": "10개/박스", # 단위/구성 설명
    "shipping_fee": 0,
    "moq": 10,               # 최소 주문 수량
    "currency": "KRW",
}

주의:
- robots.txt, 이용약관을 반드시 사전에 확인할 것
- 요청 빈도는 낮게 유지 (keyword당 1요청 + 0.5~1.0초 sleep)
- 상업적 사용 시 각 사이트 약관 확인 필요
"""

import math

# 공통 세션 (도매 크롤링용)
CRAWLER_SESSION = requests.Session()
CRAWLER_SESSION.headers.update({
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    'Accept-Language': 'ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7',
})

# 도매 사이트 URL
DOMEGGOOK_BASE_URL = "https://domeggook.com"
DOMEME_BASE_URL = "https://domeme.com"


def fetch_with_delay(url: str, delay: float = 0.6) -> str:
    """딜레이 적용 후 페이지 fetch"""
    time.sleep(delay)
    resp = CRAWLER_SESSION.get(url, timeout=10)
    resp.raise_for_status()
    return resp.text


def parse_price_to_int(text: str) -> int:
    """가격 문자열을 정수로 변환 (예: '25,000원' → 25000)"""
    if not text:
        return 0
    numbers = re.sub(r'[^\d]', '', text)
    return int(numbers) if numbers else 0


def extract_quantity_from_text(text: str) -> int:
    """
    텍스트에서 수량 추출
    예: "10개입" → 10, "1BOX(20개)" → 20, "30매" → 30
    """
    if not text:
        return 1

    patterns = [
        r'\((\d+)개\)',      # (20개)
        r'(\d+)개입',        # 10개입
        r'(\d+)개',          # 10개
        r'(\d+)매',          # 30매
        r'(\d+)장',          # 100장
        r'(\d+)ea',          # 10ea
        r'(\d+)EA',          # 10EA
        r'(\d+)p',           # 10p
        r'(\d+)P',           # 10P
        r'x(\d+)',           # x10
        r'X(\d+)',           # X10
    ]

    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return int(match.group(1))

    return 1


# ===== 도매꾹 크롤러 =====

def build_domeggook_search_url(keyword: str) -> str:
    """도매꾹 검색 URL 생성"""
    encoded = quote(keyword)
    return f"{DOMEGGOOK_BASE_URL}/main/searchProc.php?search={encoded}"


def search_from_domeggook(keywords: list) -> list:
    """
    도매꾹 검색 결과 크롤링

    주의:
    - robots.txt, 이용약관을 반드시 사전에 확인할 것
    - 요청 빈도는 낮게 유지 (keyword당 1요청 + 0.6초 delay)
    """
    results = []

    for kw in keywords[:2]:  # 최대 2개 키워드만 사용
        try:
            url = build_domeggook_search_url(kw)
            html = fetch_with_delay(url, delay=0.7)
            parsed = parse_domeggook_list_page(html)
            results.extend(parsed)
        except Exception as e:
            print(f"[Brandpipe] 도매꾹 검색 오류 ({kw}): {e}")
            continue

    # 중복 제거 (URL 기준)
    unique = {}
    for r in results:
        key = r.get("url")
        if key and key not in unique:
            unique[key] = r

    return list(unique.values())[:15]


def parse_domeggook_list_page(html: str) -> list:
    """도매꾹 검색 결과 페이지 파싱"""
    soup = BeautifulSoup(html, 'html.parser')
    results = []

    # 도매꾹 상품 리스트 selector (실제 구조에 맞게 조정 필요)
    # 일반적인 패턴: div.item, li.product, div.goods-item 등
    items = soup.select('div.item_box, div.goods_item, li.prd_item, div.product-item')

    # 대체 selector 시도
    if not items:
        items = soup.select('[class*="item"], [class*="product"], [class*="goods"]')

    for item in items[:20]:
        try:
            # 제목/링크 추출
            title_el = item.select_one('a[class*="name"], a[class*="title"], .item_name a, .goods_name a, a.prd_name')
            if not title_el:
                title_el = item.select_one('a')

            if not title_el:
                continue

            title = title_el.get_text(strip=True)
            if not title or len(title) < 2:
                continue

            link = title_el.get('href', '')
            if link and not link.startswith('http'):
                link = DOMEGGOOK_BASE_URL + ('/' if not link.startswith('/') else '') + link

            # 가격 추출
            price_el = item.select_one('[class*="price"], .item_price, .goods_price, .prd_price, span.price')
            if not price_el:
                price_el = item.select_one('strong, em, span')

            price_text = price_el.get_text(strip=True) if price_el else '0'
            total_price = parse_price_to_int(price_text)

            if total_price <= 0:
                continue

            # 수량/단위 추출
            unit_desc = ''
            unit_el = item.select_one('[class*="unit"], [class*="qty"], .item_unit')
            if unit_el:
                unit_desc = unit_el.get_text(strip=True)

            # 제목에서도 수량 추출 시도
            qty = extract_quantity_from_text(unit_desc) or extract_quantity_from_text(title)
            if qty <= 0:
                qty = 1

            unit_price = math.floor(total_price / qty)

            results.append({
                "source": "domeggook",
                "name": title[:120],
                "url": link,
                "unit_price": unit_price,
                "original_price": total_price,
                "unit_desc": unit_desc or f"{qty}개",
                "shipping_fee": 0,
                "moq": qty,
                "currency": "KRW"
            })

        except Exception as e:
            print(f"[Brandpipe] 도매꾹 아이템 파싱 오류: {e}")
            continue

    return results


# ===== 도매매 크롤러 =====

def build_domeme_search_url(keyword: str) -> str:
    """도매매 검색 URL 생성"""
    encoded = quote(keyword)
    return f"{DOMEME_BASE_URL}/search?keyword={encoded}"


def search_from_domeme(keywords: list) -> list:
    """
    도매매 검색 결과 크롤링

    주의:
    - robots.txt, 이용약관을 반드시 사전에 확인할 것
    - 요청 빈도는 낮게 유지 (keyword당 1요청 + 0.6초 delay)
    """
    results = []

    for kw in keywords[:2]:  # 최대 2개 키워드만 사용
        try:
            url = build_domeme_search_url(kw)
            html = fetch_with_delay(url, delay=0.7)
            parsed = parse_domeme_list_page(html)
            results.extend(parsed)
        except Exception as e:
            print(f"[Brandpipe] 도매매 검색 오류 ({kw}): {e}")
            continue

    # 중복 제거 (URL 기준)
    unique = {}
    for r in results:
        key = r.get("url")
        if key and key not in unique:
            unique[key] = r

    return list(unique.values())[:15]


def parse_domeme_list_page(html: str) -> list:
    """도매매 검색 결과 페이지 파싱"""
    soup = BeautifulSoup(html, 'html.parser')
    results = []

    # 도매매 상품 리스트 selector (실제 구조에 맞게 조정 필요)
    items = soup.select('div.item_box, div.goods_item, li.prd_item, div.product-item, .item-card')

    # 대체 selector 시도
    if not items:
        items = soup.select('[class*="item"], [class*="product"], [class*="goods"]')

    for item in items[:20]:
        try:
            # 제목/링크 추출
            title_el = item.select_one('a[class*="name"], a[class*="title"], .item_name a, .goods_name a')
            if not title_el:
                title_el = item.select_one('a')

            if not title_el:
                continue

            title = title_el.get_text(strip=True)
            if not title or len(title) < 2:
                continue

            link = title_el.get('href', '')
            if link and not link.startswith('http'):
                link = DOMEME_BASE_URL + ('/' if not link.startswith('/') else '') + link

            # 가격 추출
            price_el = item.select_one('[class*="price"], .item_price, .goods_price, span.price')
            if not price_el:
                price_el = item.select_one('strong, em, span')

            price_text = price_el.get_text(strip=True) if price_el else '0'
            total_price = parse_price_to_int(price_text)

            if total_price <= 0:
                continue

            # 수량/단위 추출
            unit_desc = ''
            unit_el = item.select_one('[class*="unit"], [class*="qty"], .item_unit')
            if unit_el:
                unit_desc = unit_el.get_text(strip=True)

            qty = extract_quantity_from_text(unit_desc) or extract_quantity_from_text(title)
            if qty <= 0:
                qty = 1

            unit_price = math.floor(total_price / qty)

            results.append({
                "source": "domeme",
                "name": title[:120],
                "url": link,
                "unit_price": unit_price,
                "original_price": total_price,
                "unit_desc": unit_desc or f"{qty}개",
                "shipping_fee": 0,
                "moq": qty,
                "currency": "KRW"
            })

        except Exception as e:
            print(f"[Brandpipe] 도매매 아이템 파싱 오류: {e}")
            continue

    return results


def get_source_label(source: str) -> str:
    """소스 코드를 한글 라벨로 변환"""
    labels = {
        "domeggook": "도매꾹",
        "domeme": "도매매",
        "naver_shopping": "네이버 쇼핑",
        "domemall_mock": "도매몰(테스트)",
        "naver_shopping_mock": "네이버(테스트)",
        "alibaba_mock": "알리바바(테스트)"
    }
    return labels.get(source, source)


# ===== 서비스 레이어 =====

def detect_platform(url: str) -> str:
    """URL에서 플랫폼 감지"""
    if not url:
        return "unknown"

    url_lower = url.lower()
    if "coupang.com" in url_lower:
        return "coupang"
    elif "smartstore.naver.com" in url_lower or "shopping.naver.com" in url_lower:
        return "naver"
    elif "11st.co.kr" in url_lower:
        return "11st"
    elif "gmarket.co.kr" in url_lower:
        return "gmarket"
    elif "auction.co.kr" in url_lower:
        return "auction"
    else:
        return "unknown"


def extract_og_meta(soup: BeautifulSoup) -> dict:
    """
    OpenGraph 메타 태그에서 정보 추출 (우선순위 1)

    Args:
        soup: BeautifulSoup 객체

    Returns:
        dict with title, image_url, price, description
    """
    result = {
        "title": None,
        "image_url": None,
        "price": None,
        "description": None
    }

    try:
        # og:title
        og_title = soup.select_one('meta[property="og:title"]')
        if og_title and og_title.get('content'):
            result["title"] = og_title['content'].strip()

        # og:image
        og_image = soup.select_one('meta[property="og:image"]')
        if og_image and og_image.get('content'):
            result["image_url"] = og_image['content'].strip()

        # og:description
        og_desc = soup.select_one('meta[property="og:description"]')
        if og_desc and og_desc.get('content'):
            result["description"] = og_desc['content'].strip()

        # product:price:amount (일부 사이트에서 사용)
        og_price = soup.select_one('meta[property="product:price:amount"]')
        if og_price and og_price.get('content'):
            try:
                result["price"] = int(float(og_price['content']))
            except (ValueError, TypeError):
                pass

    except Exception as e:
        print(f"[Brandpipe] OG 메타 추출 오류: {e}")

    return result


def extract_json_ld(soup: BeautifulSoup) -> dict:
    """
    JSON-LD 구조화 데이터에서 Product 정보 추출 (우선순위 2)

    Args:
        soup: BeautifulSoup 객체

    Returns:
        dict with title, image_url, price, brand, description
    """
    result = {
        "title": None,
        "image_url": None,
        "price": None,
        "brand": None,
        "description": None
    }

    try:
        script_tags = soup.find_all('script', type='application/ld+json')

        for script in script_tags:
            if not script.string:
                continue

            try:
                data = json.loads(script.string)
            except json.JSONDecodeError:
                continue

            # 단일 객체 또는 리스트 처리
            items = []
            if isinstance(data, dict):
                if data.get('@type') == 'Product':
                    items = [data]
                elif '@graph' in data:
                    items = [d for d in data['@graph'] if isinstance(d, dict) and d.get('@type') == 'Product']
            elif isinstance(data, list):
                items = [d for d in data if isinstance(d, dict) and d.get('@type') == 'Product']

            if not items:
                continue

            product = items[0]

            # name → title
            if product.get('name') and not result["title"]:
                result["title"] = str(product['name']).strip()

            # image → image_url
            if product.get('image') and not result["image_url"]:
                img = product['image']
                if isinstance(img, list) and img:
                    result["image_url"] = str(img[0])
                elif isinstance(img, str):
                    result["image_url"] = img
                elif isinstance(img, dict) and img.get('url'):
                    result["image_url"] = img['url']

            # offers → price
            if product.get('offers') and not result["price"]:
                offers = product['offers']
                if isinstance(offers, dict):
                    price_val = offers.get('price') or offers.get('lowPrice')
                    if price_val:
                        try:
                            result["price"] = int(float(str(price_val)))
                        except (ValueError, TypeError):
                            pass
                elif isinstance(offers, list) and offers:
                    price_val = offers[0].get('price') or offers[0].get('lowPrice')
                    if price_val:
                        try:
                            result["price"] = int(float(str(price_val)))
                        except (ValueError, TypeError):
                            pass

            # brand
            if product.get('brand') and not result["brand"]:
                brand = product['brand']
                if isinstance(brand, dict):
                    result["brand"] = brand.get('name', '')
                elif isinstance(brand, str):
                    result["brand"] = brand

            # description
            if product.get('description') and not result["description"]:
                result["description"] = str(product['description']).strip()[:500]

            # 하나 찾으면 종료
            if result["title"]:
                break

    except Exception as e:
        print(f"[Brandpipe] JSON-LD 추출 오류: {e}")

    return result


def parse_coupang_product(url: str) -> dict:
    """
    쿠팡 상품 페이지 파싱 (고도화 버전)

    우선순위:
    1. OpenGraph 메타 태그
    2. JSON-LD 구조화 데이터
    3. CSS Selector fallback
    """
    try:
        response = requests.get(url, headers=COMMON_HEADERS, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')

        # 결과 초기화
        title = None
        brand = None
        price = None
        image_url = None

        # 1단계: OG 메타 태그
        og_data = extract_og_meta(soup)
        if og_data["title"]:
            title = og_data["title"]
        if og_data["image_url"]:
            image_url = og_data["image_url"]
        if og_data["price"]:
            price = og_data["price"]

        # 2단계: JSON-LD
        ld_data = extract_json_ld(soup)
        if not title and ld_data["title"]:
            title = ld_data["title"]
        if not image_url and ld_data["image_url"]:
            image_url = ld_data["image_url"]
        if not price and ld_data["price"]:
            price = ld_data["price"]
        if not brand and ld_data["brand"]:
            brand = ld_data["brand"]

        # 3단계: CSS Selector fallback
        if not title:
            title_elem = soup.select_one('h1.prod-buy-header__title') or soup.select_one('h2.prod-buy-header__title')
            if title_elem:
                title = title_elem.get_text(strip=True)

        if not price:
            # 다양한 가격 selector 시도
            price_selectors = [
                'span.total-price strong',
                '.prod-sale-price .total-price',
                '.prod-price .total-price',
                'span.price-value',
                '.prod-coupon-price .total-price'
            ]
            for selector in price_selectors:
                price_elem = soup.select_one(selector)
                if price_elem:
                    price_text = price_elem.get_text(strip=True)
                    price_numbers = re.sub(r'[^\d]', '', price_text)
                    if price_numbers:
                        price = int(price_numbers)
                        break

        if not image_url:
            img_elem = soup.select_one('.prod-image__detail img') or soup.select_one('.prod-image img')
            if img_elem:
                image_url = img_elem.get('src') or img_elem.get('data-src')
                if image_url and image_url.startswith('//'):
                    image_url = 'https:' + image_url

        if not brand:
            brand_elem = soup.select_one('.prod-brand-name') or soup.select_one('a.prod-brand-name')
            if brand_elem:
                brand = brand_elem.get_text(strip=True)

        return {
            "title": title,
            "brand": brand,
            "price": price,
            "image_url": image_url,
            "platform": "coupang",
            "platform_url": url
        }

    except Exception as e:
        print(f"[Brandpipe] 쿠팡 파싱 오류: {e}")
        return {
            "title": None,
            "brand": None,
            "price": None,
            "image_url": None,
            "platform": "coupang",
            "platform_url": url,
            "error": str(e)
        }


def parse_naver_product(url: str) -> dict:
    """
    네이버 스마트스토어/쇼핑 상품 페이지 파싱 (고도화 버전)

    우선순위:
    1. OpenGraph 메타 태그
    2. JSON-LD 구조화 데이터
    3. CSS Selector fallback
    """
    try:
        response = requests.get(url, headers=COMMON_HEADERS, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')

        # 결과 초기화
        title = None
        brand = None
        price = None
        image_url = None

        # 1단계: OG 메타 태그 (네이버는 OG 태그가 잘 되어 있음)
        og_data = extract_og_meta(soup)
        if og_data["title"]:
            title = og_data["title"]
        if og_data["image_url"]:
            image_url = og_data["image_url"]
        if og_data["price"]:
            price = og_data["price"]

        # 2단계: JSON-LD
        ld_data = extract_json_ld(soup)
        if not title and ld_data["title"]:
            title = ld_data["title"]
        if not image_url and ld_data["image_url"]:
            image_url = ld_data["image_url"]
        if not price and ld_data["price"]:
            price = ld_data["price"]
        if not brand and ld_data["brand"]:
            brand = ld_data["brand"]

        # 3단계: CSS Selector fallback (스마트스토어/쇼핑 다양한 패턴)
        if not title:
            title_selectors = [
                '._3oDjSvLwj1',
                'h3._22kNQuEXmb',
                '.product_title',
                'h2.title',
                '.goods_name'
            ]
            for selector in title_selectors:
                title_elem = soup.select_one(selector)
                if title_elem:
                    title = title_elem.get_text(strip=True)
                    break

        if not price:
            price_selectors = [
                '._1LY7DqCnwR',
                'span._1LY7DqCnwR',
                '.price_num',
                '.sale_price',
                '.price span',
                '._2pgHN-ntx6'
            ]
            for selector in price_selectors:
                price_elem = soup.select_one(selector)
                if price_elem:
                    price_text = price_elem.get_text(strip=True)
                    price_numbers = re.sub(r'[^\d]', '', price_text)
                    if price_numbers:
                        price = int(price_numbers)
                        break

        if not brand:
            brand_selectors = [
                '._1Ko5X6D3YR',
                'a._1Ko5X6D3YR',
                '.brand_name',
                '.seller_name'
            ]
            for selector in brand_selectors:
                brand_elem = soup.select_one(selector)
                if brand_elem:
                    brand = brand_elem.get_text(strip=True)
                    break

        return {
            "title": title,
            "brand": brand,
            "price": price,
            "image_url": image_url,
            "platform": "naver",
            "platform_url": url
        }

    except Exception as e:
        print(f"[Brandpipe] 네이버 파싱 오류: {e}")
        return {
            "title": None,
            "brand": None,
            "price": None,
            "image_url": None,
            "platform": "naver",
            "platform_url": url,
            "error": str(e)
        }


# ===== 마진 필터 설정 =====
DEFAULT_MIN_MARGIN_RATE = 0.15    # 15% 이상
DEFAULT_MIN_MARGIN_AMOUNT = 3000  # 3,000원 이상


def extract_volume_info(text: str) -> tuple:
    """
    텍스트에서 용량/수량 정보 추출

    Args:
        text: 상품명 등 텍스트

    Returns:
        (숫자, 단위) 튜플. 없으면 (None, None)
    """
    if not text:
        return (None, None)

    # 용량 패턴: 100ml, 500g, 1L, 50매, 30개, 1kg 등
    patterns = [
        r'(\d+(?:\.\d+)?)\s*(ml|ML|mL|g|G|kg|KG|Kg|l|L|매|개|정|캡슐|포|입|ea|EA|pack|PACK)',
    ]

    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            num = float(match.group(1))
            unit = match.group(2).lower()
            return (num, unit)

    return (None, None)


def extract_keywords(text: str) -> set:
    """
    텍스트에서 핵심 키워드(명사) 추출

    Args:
        text: 상품명 등 텍스트

    Returns:
        키워드 set
    """
    if not text:
        return set()

    # 불용어 제거
    stopwords = {'의', '를', '을', '이', '가', '에', '도', '로', '와', '과', '한', '및',
                 '더', '등', '용', '형', '무료배송', '특가', '할인', '세일', '정품'}

    # 특수문자 제거 후 단어 분리
    cleaned = re.sub(r'[^\w\s가-힣]', ' ', text)
    words = cleaned.split()

    # 2글자 이상, 불용어 아닌 것만
    keywords = {w.lower() for w in words if len(w) >= 2 and w not in stopwords}

    return keywords


def compute_similarity_score(product: dict, candidate: dict) -> float:
    """
    상품과 공급처 후보 간 유사도 점수 계산

    Args:
        product: 원본 상품 정보 (title, brand 등)
        candidate: 공급처 후보 (name 등)

    Returns:
        0.0 ~ 1.0 사이 점수
    """
    score = 0.0

    product_title = (product.get('title') or '').lower()
    product_brand = (product.get('brand') or '').lower()
    candidate_name = (candidate.get('name') or '').lower()

    if not product_title or not candidate_name:
        return 0.0

    # 1. 브랜드명 포함 여부 (+0.3)
    if product_brand and product_brand in candidate_name:
        score += 0.3
    elif product_brand:
        # 브랜드명 일부만 포함되어도 부분 점수
        brand_words = product_brand.split()
        matching_brand_words = sum(1 for w in brand_words if w in candidate_name)
        if brand_words:
            score += 0.15 * (matching_brand_words / len(brand_words))

    # 2. 용량/수량 일치 여부 (+0.3)
    prod_vol, prod_unit = extract_volume_info(product_title)
    cand_vol, cand_unit = extract_volume_info(candidate_name)

    if prod_vol and cand_vol and prod_unit and cand_unit:
        # 단위 정규화
        unit_map = {'ml': 'ml', 'l': 'l', 'g': 'g', 'kg': 'kg',
                    '매': '매', '개': '개', '정': '정', '캡슐': '캡슐',
                    '포': '포', '입': '입', 'ea': '개', 'pack': '팩'}
        p_unit = unit_map.get(prod_unit, prod_unit)
        c_unit = unit_map.get(cand_unit, cand_unit)

        if p_unit == c_unit:
            # 같은 단위면 수량 비교
            ratio = min(prod_vol, cand_vol) / max(prod_vol, cand_vol)
            if ratio >= 0.95:  # 거의 동일
                score += 0.3
            elif ratio >= 0.8:  # 비슷
                score += 0.2
            elif ratio >= 0.5:
                score += 0.1

    # 3. 핵심 키워드 겹치는 비율 (+0.4)
    prod_keywords = extract_keywords(product_title)
    cand_keywords = extract_keywords(candidate_name)

    if prod_keywords and cand_keywords:
        # 교집합 / 원본 키워드 수
        overlap = prod_keywords & cand_keywords
        overlap_ratio = len(overlap) / len(prod_keywords) if prod_keywords else 0

        score += 0.4 * overlap_ratio

    return round(min(score, 1.0), 2)


def parse_product_info(product_url: str = None, keyword: str = None) -> dict:
    """
    상품 정보 파싱
    - URL이 있으면 해당 플랫폼에서 파싱
    - keyword만 있으면 키워드 기반 기본 정보 반환
    """
    if product_url:
        platform = detect_platform(product_url)

        if platform == "coupang":
            result = parse_coupang_product(product_url)
        elif platform == "naver":
            result = parse_naver_product(product_url)
        else:
            # 알 수 없는 플랫폼
            result = {
                "title": keyword,
                "brand": None,
                "price": None,
                "image_url": None,
                "platform": platform,
                "platform_url": product_url
            }

        # 파싱 실패 시 키워드로 폴백
        if not result.get("title") and keyword:
            result["title"] = keyword

        return result

    elif keyword:
        # 키워드만 있는 경우
        return {
            "title": keyword,
            "brand": None,
            "category": None,
            "platform": "keyword_search",
            "platform_url": None,
            "price": None,
            "image_url": None
        }

    else:
        raise ValueError("product_url 또는 keyword 중 하나는 필수입니다.")


def build_search_keywords(product: dict) -> list:
    """도매 검색용 키워드 리스트 생성"""
    keywords = []
    title = product.get("title", "")
    brand = product.get("brand", "")

    if not title:
        return keywords

    # 기본 키워드 조합
    if brand and brand.lower() not in title.lower():
        keywords.append(f"{brand} {title} 도매")
        keywords.append(f"{title} 도매")
        keywords.append(f"{brand} {title}")
    else:
        keywords.append(f"{title} 도매")
        keywords.append(title)

    # 짧은 버전 (상품명에서 용량/사이즈 등 제거)
    short_title = re.sub(r'\d+[gGmMlL]+|\d+개|\d+매|\d+pack', '', title).strip()
    if short_title and short_title != title:
        keywords.append(f"{short_title} 도매")

    return keywords[:5]  # 최대 5개


def search_from_domemall_mock(keywords: list) -> list:
    """
    도매몰 Mock 데이터 반환 (실제 크롤링 구현 전 테스트용)
    추후 실제 도매 사이트 크롤링으로 교체
    """
    # Mock 데이터 - 키워드와 무관하게 샘플 반환
    return [
        {
            "source": "domemall_mock",
            "name": "도매꾹 테스트 상품",
            "url": "https://domeggook.com/item/123456",
            "unit_price": 2500,
            "shipping_fee": 3000,
            "moq": 10,
            "currency": "KRW"
        },
        {
            "source": "domemall_mock",
            "name": "도매매 샘플 상품",
            "url": "https://domeme.com/product/789",
            "unit_price": 2200,
            "shipping_fee": 2500,
            "moq": 20,
            "currency": "KRW"
        }
    ]


def search_from_naver_mock(keywords: list) -> list:
    """
    네이버 쇼핑 Mock 데이터 반환 (실제 크롤링 구현 전 테스트용)
    추후 네이버 쇼핑 검색 결과 파싱으로 교체
    """
    return [
        {
            "source": "naver_shopping_mock",
            "name": "네이버 쇼핑 도매상품",
            "url": "https://shopping.naver.com/product/12345",
            "unit_price": 3000,
            "shipping_fee": 0,
            "moq": 5,
            "currency": "KRW"
        }
    ]


def search_from_naver_shopping(keywords: list) -> list:
    """
    네이버 쇼핑 검색 페이지를 파싱해서 상품 정보 추출

    주의:
    - robots.txt, 약관을 검토하고 요청 횟수는 적절히 제한할 것
    - 요청 실패/구조 변경 시 전체가 죽지 않게 try/except 처리
    - 네이버 쇼핑은 "우리가 사오는 공급가격"이 아니라 "소비자 판매가"라서
      시장 가격 참고용으로만 활용

    Args:
        keywords: 검색 키워드 리스트

    Returns:
        공급처 후보 형식의 리스트
    """
    results = []
    base_url = "https://search.shopping.naver.com/search/all?query="

    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7',
        'Accept-Encoding': 'gzip, deflate, br',
        'Connection': 'keep-alive',
    }

    # 가장 대표 키워드 1~2개만 사용 (과도한 요청 방지)
    for kw in keywords[:2]:
        try:
            url = base_url + quote(kw)
            resp = requests.get(url, headers=headers, timeout=10)

            if resp.status_code != 200:
                print(f"[Brandpipe] 네이버 쇼핑 검색 실패: HTTP {resp.status_code}")
                continue

            soup = BeautifulSoup(resp.text, 'html.parser')

            # 네이버 쇼핑 검색 결과 파싱 (2024년 기준 구조)
            # 상품 리스트는 script 태그 내 JSON으로 전달되는 경우가 많음
            items_found = []

            # 방법 1: 상품 카드 직접 파싱 시도
            product_items = soup.select('div.product_item, li.product_item, div.basicList_item__0T9JD')

            for item in product_items[:10]:
                try:
                    # 상품명
                    title_elem = item.select_one('a.product_link, a.basicList_link__JLQJf, div.product_title a')
                    if not title_elem:
                        continue

                    title = title_elem.get_text(strip=True)
                    link = title_elem.get('href', '')

                    # 가격
                    price_elem = item.select_one('span.price_num, span.price, em.price_num')
                    if not price_elem:
                        continue

                    price_text = price_elem.get_text(strip=True)
                    price_numbers = re.sub(r'[^\d]', '', price_text)
                    if not price_numbers:
                        continue

                    price = int(price_numbers)

                    items_found.append({
                        "source": "naver_shopping",
                        "name": title[:100],
                        "url": link if link.startswith('http') else f"https://search.shopping.naver.com{link}",
                        "unit_price": price,
                        "shipping_fee": 0,  # 배송비 정보는 상세 페이지에서만 확인 가능
                        "moq": 1,
                        "currency": "KRW"
                    })
                except Exception as e:
                    print(f"[Brandpipe] 네이버 상품 파싱 오류: {e}")
                    continue

            # 방법 2: JSON 데이터에서 추출 시도 (SSR 데이터)
            if not items_found:
                script_tags = soup.find_all('script')
                for script in script_tags:
                    if script.string and 'products' in script.string:
                        try:
                            # __NEXT_DATA__ 또는 window.__PRELOADED_STATE__ 패턴 찾기
                            json_match = re.search(r'(\{.*"products".*\})', script.string)
                            if json_match:
                                data = json.loads(json_match.group(1))
                                products = data.get('products', [])

                                for p in products[:10]:
                                    if isinstance(p, dict):
                                        items_found.append({
                                            "source": "naver_shopping",
                                            "name": p.get('name', p.get('productName', ''))[:100],
                                            "url": p.get('link', p.get('productUrl', '')),
                                            "unit_price": int(p.get('price', p.get('lowPrice', 0))),
                                            "shipping_fee": 0,
                                            "moq": 1,
                                            "currency": "KRW"
                                        })
                        except Exception:
                            pass

            results.extend(items_found)

            # 요청 간 딜레이 (rate limiting)
            time.sleep(0.5)

        except requests.RequestException as e:
            print(f"[Brandpipe] 네이버 쇼핑 요청 오류: {e}")
            continue
        except Exception as e:
            print(f"[Brandpipe] 네이버 쇼핑 파싱 오류: {e}")
            continue

    # 중복 제거 (URL 기준)
    seen_urls = set()
    unique_results = []
    for item in results:
        if item['url'] not in seen_urls:
            seen_urls.add(item['url'])
            unique_results.append(item)

    return unique_results[:15]  # 최대 15개 반환


def search_from_alibaba_mock(keywords: list) -> list:
    """
    알리바바 Mock 데이터 반환 (해외 도매용)
    """
    return [
        {
            "source": "alibaba_mock",
            "name": "Alibaba Wholesale Product",
            "url": "https://www.alibaba.com/product/999",
            "unit_price": 1.5,  # USD
            "shipping_fee": 5.0,
            "moq": 100,
            "currency": "USD"
        }
    ]


def search_suppliers(keywords: list, include_overseas: bool = False, use_real_search: bool = True) -> list:
    """
    모든 공급처에서 검색 후 결과 합치기

    Args:
        keywords: 검색 키워드 리스트
        include_overseas: 해외 도매(알리바바 등) 포함 여부
        use_real_search: 실제 크롤링 사용 여부 (False면 mock만 사용)

    Returns:
        공급처 리스트
    """
    suppliers = []

    if use_real_search:
        # 1. 네이버 쇼핑 검색 (소비자 가격 참고용)
        try:
            naver_results = search_from_naver_shopping(keywords)
            if naver_results:
                suppliers.extend(naver_results)
        except Exception as e:
            print(f"[Brandpipe] 네이버 쇼핑 검색 오류: {e}")

        # 2. 도매꾹 검색 (실제 도매 단가)
        try:
            domeggook_results = search_from_domeggook(keywords)
            if domeggook_results:
                suppliers.extend(domeggook_results)
        except Exception as e:
            print(f"[Brandpipe] 도매꾹 검색 오류: {e}")

        # 3. 도매매 검색 (실제 도매 단가)
        try:
            domeme_results = search_from_domeme(keywords)
            if domeme_results:
                suppliers.extend(domeme_results)
        except Exception as e:
            print(f"[Brandpipe] 도매매 검색 오류: {e}")

        # 실제 결과가 없으면 mock으로 폴백
        if not suppliers:
            try:
                suppliers.extend(search_from_domemall_mock(keywords))
                suppliers.extend(search_from_naver_mock(keywords))
            except Exception as e:
                print(f"[Brandpipe] Mock 폴백 오류: {e}")
    else:
        # Mock 데이터만 사용
        try:
            suppliers.extend(search_from_domemall_mock(keywords))
            suppliers.extend(search_from_naver_mock(keywords))
        except Exception as e:
            print(f"[Brandpipe] Mock 검색 오류: {e}")

    # 4. 해외 도매 (옵션)
    if include_overseas:
        try:
            suppliers.extend(search_from_alibaba_mock(keywords))
        except Exception as e:
            print(f"[Brandpipe] 알리바바 검색 오류: {e}")

    return suppliers


def estimate_margin(platform_price: int, supplier_price: int, shipping_fee: int = 0,
                   fee_rate: float = 0.13) -> dict:
    """
    마진 계산

    Args:
        platform_price: 플랫폼 판매가 (쿠팡/네이버에서의 판매가)
        supplier_price: 공급가 (도매가)
        shipping_fee: 배송비
        fee_rate: 플랫폼 수수료율 (기본 13%)

    Returns:
        margin_amount: 예상 마진 금액
        margin_rate: 예상 마진율
    """
    if not platform_price or platform_price <= 0:
        return {"margin_amount": 0, "margin_rate": 0}

    if not supplier_price:
        supplier_price = 0

    # 총 비용 = 공급가 + 배송비 + 플랫폼 수수료
    platform_fee = platform_price * fee_rate
    total_cost = supplier_price + shipping_fee + platform_fee

    # 마진 계산
    margin_amount = platform_price - total_cost
    margin_rate = margin_amount / platform_price if platform_price > 0 else 0

    return {
        "margin_amount": round(margin_amount),
        "margin_rate": round(margin_rate, 4)
    }


def convert_currency(amount: float, from_currency: str, to_currency: str = "KRW") -> float:
    """통화 변환 (간단한 고정 환율 사용)"""
    # 간단한 환율표 (실제로는 API 사용 권장)
    rates_to_krw = {
        "USD": 1300,
        "CNY": 180,
        "JPY": 9,
        "KRW": 1
    }

    if from_currency == to_currency:
        return amount

    # 원화로 변환
    krw_amount = amount * rates_to_krw.get(from_currency, 1)

    if to_currency == "KRW":
        return krw_amount

    # 다른 통화로 변환
    return krw_amount / rates_to_krw.get(to_currency, 1)


# ===== API 라우트 =====

@brandpipe_bp.route('/brandpipe')
def brandpipe_page():
    """브랜드파이프 메인 페이지"""
    return render_template('brandpipe.html')


@brandpipe_bp.route('/api/brandpipe/analyze', methods=['POST'])
def analyze_product():
    """
    상품 분석 API

    Request JSON:
        product_url: 상품 URL (선택)
        keyword: 검색 키워드 (선택)
        include_overseas: 해외 도매 포함 여부 (선택, 기본 False)

    Response JSON:
        product: 상품 정보
        suppliers: 공급처 리스트 (마진 정보 포함)
        meta: 메타 정보
    """
    start_time = time.time()

    try:
        data = request.get_json() or {}
        product_url = data.get('product_url', '').strip()
        keyword = data.get('keyword', '').strip()
        include_overseas = data.get('include_overseas', False)

        # 입력 검증
        if not product_url and not keyword:
            return jsonify({
                "ok": False,
                "error": "product_url 또는 keyword 중 하나는 필수입니다."
            }), 400

        # 1. 상품 정보 파싱
        product = parse_product_info(product_url or None, keyword or None)

        # 2. 검색 키워드 생성
        search_keywords = build_search_keywords(product)

        # 3. 공급처 검색
        suppliers = search_suppliers(search_keywords, include_overseas)

        # 4. 마진 계산 + 유사도 점수 추가
        platform_price = product.get('price') or 0
        for supplier in suppliers:
            # 통화 변환 (해외 도매의 경우)
            unit_price = supplier.get('unit_price', 0)
            currency = supplier.get('currency', 'KRW')

            if currency != 'KRW':
                unit_price_krw = convert_currency(unit_price, currency, 'KRW')
                shipping_krw = convert_currency(supplier.get('shipping_fee', 0), currency, 'KRW')
            else:
                unit_price_krw = unit_price
                shipping_krw = supplier.get('shipping_fee', 0)

            margin = estimate_margin(platform_price, unit_price_krw, shipping_krw)
            supplier['estimated_margin_rate'] = margin['margin_rate']
            supplier['estimated_margin_amount'] = margin['margin_amount']
            supplier['unit_price_krw'] = round(unit_price_krw)

            # 유사도 점수 계산
            supplier['similarity_score'] = compute_similarity_score(product, supplier)

        # 5. 필터링: 마진 기준 충족하는 것만 (전체 + 필터링된 목록 둘 다 반환)
        filtered_suppliers = []
        for s in suppliers:
            margin_rate = s.get('estimated_margin_rate') or 0
            margin_amount = s.get('estimated_margin_amount') or 0
            if margin_rate >= DEFAULT_MIN_MARGIN_RATE and margin_amount >= DEFAULT_MIN_MARGIN_AMOUNT:
                filtered_suppliers.append(s)

        # 정렬: 유사도 → 마진액 순
        suppliers.sort(
            key=lambda x: (x.get('similarity_score', 0), x.get('estimated_margin_amount', 0)),
            reverse=True
        )
        filtered_suppliers.sort(
            key=lambda x: (x.get('similarity_score', 0), x.get('estimated_margin_amount', 0)),
            reverse=True
        )

        # 응답 구성
        analysis_time_ms = int((time.time() - start_time) * 1000)

        result = {
            "ok": True,
            "product": {
                "title": product.get('title'),
                "brand": product.get('brand'),
                "category": product.get('category'),
                "platform": product.get('platform'),
                "platform_url": product.get('platform_url'),
                "price": product.get('price'),
                "image_url": product.get('image_url'),
                "raw": product
            },
            "suppliers": suppliers,  # 전체 목록
            "filtered_suppliers": filtered_suppliers,  # 마진 기준 충족하는 것만
            "filters": {
                "min_margin_rate": DEFAULT_MIN_MARGIN_RATE,
                "min_margin_amount": DEFAULT_MIN_MARGIN_AMOUNT,
                "filtered_count": len(filtered_suppliers),
                "total_count": len(suppliers)
            },
            "meta": {
                "keyword_used": keyword or product.get('title'),
                "search_keywords": search_keywords,
                "search_providers": ["domemall_mock", "naver_shopping"] + (["alibaba_mock"] if include_overseas else []),
                "analysis_time_ms": analysis_time_ms,
                "parsing_method": "og+jsonld+fallback"
            }
        }

        # DB에 검색 기록 저장
        search_id = None
        try:
            search_id = save_search_history(
                input_url=product_url,
                input_keyword=keyword,
                product_title=product.get('title'),
                product_brand=product.get('brand'),
                product_price=product.get('price'),
                result_json=json.dumps(result, ensure_ascii=False)
            )
            # 응답에 search_id 추가
            result["search_id"] = search_id
        except Exception as e:
            print(f"[Brandpipe] 검색 기록 저장 오류: {e}")

        return jsonify(result)

    except ValueError as e:
        return jsonify({
            "ok": False,
            "error": str(e)
        }), 400
    except Exception as e:
        print(f"[Brandpipe] 분석 오류: {e}")
        return jsonify({
            "ok": False,
            "error": f"분석 중 오류가 발생했습니다: {str(e)}"
        }), 500


@brandpipe_bp.route('/api/brandpipe/history', methods=['GET'])
def get_search_history():
    """
    검색 기록 조회 API

    Query Params:
        limit: 조회할 개수 (기본 20)
        favorites_only: 즐겨찾기만 조회 (선택)

    Response JSON:
        ok: True
        history: 검색 기록 리스트 (is_favorite, note 포함)
    """
    try:
        limit = request.args.get('limit', 20, type=int)
        limit = min(limit, 100)  # 최대 100개
        favorites_only = request.args.get('favorites_only', 'false').lower() == 'true'

        conn = get_brandpipe_db()
        cursor = conn.cursor()

        if USE_POSTGRES:
            if favorites_only:
                cursor.execute('''
                    SELECT id, created_at, input_url, input_keyword,
                           product_title, product_brand, product_price, result_json,
                           is_favorite, note
                    FROM brandpipe_searches
                    WHERE is_favorite = TRUE
                    ORDER BY created_at DESC
                    LIMIT %s
                ''', (limit,))
            else:
                cursor.execute('''
                    SELECT id, created_at, input_url, input_keyword,
                           product_title, product_brand, product_price, result_json,
                           is_favorite, note
                    FROM brandpipe_searches
                    ORDER BY is_favorite DESC, created_at DESC
                    LIMIT %s
                ''', (limit,))
        else:
            if favorites_only:
                cursor.execute('''
                    SELECT id, created_at, input_url, input_keyword,
                           product_title, product_brand, product_price, result_json,
                           is_favorite, note
                    FROM brandpipe_searches
                    WHERE is_favorite = 1
                    ORDER BY created_at DESC
                    LIMIT ?
                ''', (limit,))
            else:
                cursor.execute('''
                    SELECT id, created_at, input_url, input_keyword,
                           product_title, product_brand, product_price, result_json,
                           is_favorite, note
                    FROM brandpipe_searches
                    ORDER BY is_favorite DESC, created_at DESC
                    LIMIT ?
                ''', (limit,))

        rows = cursor.fetchall()
        conn.close()

        history = []
        for row in rows:
            # sqlite3.Row 또는 dict 처리
            if hasattr(row, 'keys'):
                row_dict = dict(row)
            else:
                row_dict = {
                    'id': row[0],
                    'created_at': row[1],
                    'input_url': row[2],
                    'input_keyword': row[3],
                    'product_title': row[4],
                    'product_brand': row[5],
                    'product_price': row[6],
                    'result_json': row[7],
                    'is_favorite': row[8],
                    'note': row[9]
                }

            # 마진 요약 추출
            margin_summary = None
            if row_dict.get('result_json'):
                try:
                    result = json.loads(row_dict['result_json'])
                    suppliers = result.get('suppliers', [])
                    if suppliers:
                        best = suppliers[0]
                        margin_summary = {
                            "best_margin_rate": best.get('estimated_margin_rate'),
                            "best_margin_amount": best.get('estimated_margin_amount'),
                            "supplier_count": len(suppliers)
                        }
                except:
                    pass

            # is_favorite 변환 (SQLite는 0/1, Postgres는 bool)
            is_fav = row_dict.get('is_favorite')
            if isinstance(is_fav, int):
                is_fav = bool(is_fav)

            history.append({
                "id": row_dict['id'],
                "created_at": str(row_dict['created_at']),
                "input_url": row_dict['input_url'],
                "input_keyword": row_dict['input_keyword'],
                "product_title": row_dict['product_title'],
                "product_brand": row_dict['product_brand'],
                "product_price": row_dict['product_price'],
                "margin_summary": margin_summary,
                "is_favorite": is_fav,
                "note": row_dict.get('note')
            })

        return jsonify({
            "ok": True,
            "history": history
        })

    except Exception as e:
        print(f"[Brandpipe] 히스토리 조회 오류: {e}")
        return jsonify({
            "ok": False,
            "error": str(e)
        }), 500


def save_search_history(input_url: str, input_keyword: str, product_title: str,
                       product_brand: str, product_price: int, result_json: str) -> int:
    """검색 기록 저장 및 ID 반환"""
    conn = get_brandpipe_db()
    cursor = conn.cursor()

    if USE_POSTGRES:
        cursor.execute('''
            INSERT INTO brandpipe_searches
            (input_url, input_keyword, product_title, product_brand, product_price, result_json)
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING id
        ''', (input_url, input_keyword, product_title, product_brand, product_price, result_json))
        search_id = cursor.fetchone()[0]
    else:
        cursor.execute('''
            INSERT INTO brandpipe_searches
            (input_url, input_keyword, product_title, product_brand, product_price, result_json)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (input_url, input_keyword, product_title, product_brand, product_price, result_json))
        search_id = cursor.lastrowid

    conn.commit()
    conn.close()
    return search_id


@brandpipe_bp.route('/api/brandpipe/test', methods=['GET'])
def test_endpoint():
    """테스트 엔드포인트"""
    return jsonify({
        "ok": True,
        "message": "Brandpipe API is working!",
        "version": "3.0.0",
        "features": [
            "og_meta_parsing",
            "json_ld_parsing",
            "naver_shopping_search",
            "margin_calculation",
            "favorites",
            "watchlist"
        ]
    })


# ===== 즐겨찾기 / 메모 API =====

@brandpipe_bp.route('/api/brandpipe/search/favorite', methods=['POST'])
def toggle_favorite():
    """
    검색 기록 즐겨찾기 토글

    Request JSON:
        search_id: 검색 기록 ID
        is_favorite: True/False

    Response JSON:
        ok: True
    """
    try:
        data = request.get_json() or {}
        search_id = data.get('search_id')
        is_favorite = data.get('is_favorite', False)

        if not search_id:
            return jsonify({"ok": False, "error": "search_id가 필요합니다."}), 400

        conn = get_brandpipe_db()
        cursor = conn.cursor()

        if USE_POSTGRES:
            cursor.execute('''
                UPDATE brandpipe_searches
                SET is_favorite = %s
                WHERE id = %s
            ''', (is_favorite, search_id))
        else:
            cursor.execute('''
                UPDATE brandpipe_searches
                SET is_favorite = ?
                WHERE id = ?
            ''', (1 if is_favorite else 0, search_id))

        conn.commit()
        conn.close()

        return jsonify({"ok": True})

    except Exception as e:
        print(f"[Brandpipe] 즐겨찾기 토글 오류: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500


@brandpipe_bp.route('/api/brandpipe/search/note', methods=['POST'])
def update_note():
    """
    검색 기록 메모 업데이트

    Request JSON:
        search_id: 검색 기록 ID
        note: 메모 내용

    Response JSON:
        ok: True
    """
    try:
        data = request.get_json() or {}
        search_id = data.get('search_id')
        note = data.get('note', '')

        if not search_id:
            return jsonify({"ok": False, "error": "search_id가 필요합니다."}), 400

        conn = get_brandpipe_db()
        cursor = conn.cursor()

        if USE_POSTGRES:
            cursor.execute('''
                UPDATE brandpipe_searches
                SET note = %s
                WHERE id = %s
            ''', (note[:500] if note else None, search_id))
        else:
            cursor.execute('''
                UPDATE brandpipe_searches
                SET note = ?
                WHERE id = ?
            ''', (note[:500] if note else None, search_id))

        conn.commit()
        conn.close()

        return jsonify({"ok": True})

    except Exception as e:
        print(f"[Brandpipe] 메모 업데이트 오류: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500


# ===== 워치리스트 API =====

@brandpipe_bp.route('/api/brandpipe/watchlist/add', methods=['POST'])
def add_to_watchlist():
    """
    워치리스트에 상품 추가

    Request JSON:
        search_id: 연결할 검색 기록 ID (선택)
        product_title: 상품명 (필수)
        product_url: 상품 URL (선택)
        platform: 플랫폼 (선택)
        target_margin_rate: 목표 마진율 (선택, 기본 0.2)
        target_margin_amount: 목표 마진액 (선택, 기본 5000)

    Response JSON:
        ok: True
        id: 생성된 워치리스트 ID
    """
    try:
        data = request.get_json() or {}
        product_title = data.get('product_title', '').strip()

        if not product_title:
            return jsonify({"ok": False, "error": "product_title이 필요합니다."}), 400

        search_id = data.get('search_id')
        product_url = data.get('product_url', '').strip() or None
        platform = data.get('platform', '').strip() or None
        target_margin_rate = data.get('target_margin_rate', 0.2)
        target_margin_amount = data.get('target_margin_amount', 5000)

        conn = get_brandpipe_db()
        cursor = conn.cursor()

        if USE_POSTGRES:
            cursor.execute('''
                INSERT INTO brandpipe_watchlist
                (search_id, product_title, product_url, platform, target_margin_rate, target_margin_amount)
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING id
            ''', (search_id, product_title, product_url, platform, target_margin_rate, target_margin_amount))
            new_id = cursor.fetchone()[0]
        else:
            cursor.execute('''
                INSERT INTO brandpipe_watchlist
                (search_id, product_title, product_url, platform, target_margin_rate, target_margin_amount)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (search_id, product_title, product_url, platform, target_margin_rate, target_margin_amount))
            new_id = cursor.lastrowid

        conn.commit()
        conn.close()

        return jsonify({"ok": True, "id": new_id})

    except Exception as e:
        print(f"[Brandpipe] 워치리스트 추가 오류: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500


@brandpipe_bp.route('/api/brandpipe/watchlist/remove', methods=['POST'])
def remove_from_watchlist():
    """
    워치리스트에서 상품 삭제

    Request JSON:
        id: 워치리스트 ID

    Response JSON:
        ok: True
    """
    try:
        data = request.get_json() or {}
        watchlist_id = data.get('id')

        if not watchlist_id:
            return jsonify({"ok": False, "error": "id가 필요합니다."}), 400

        conn = get_brandpipe_db()
        cursor = conn.cursor()

        if USE_POSTGRES:
            cursor.execute('DELETE FROM brandpipe_watchlist WHERE id = %s', (watchlist_id,))
        else:
            cursor.execute('DELETE FROM brandpipe_watchlist WHERE id = ?', (watchlist_id,))

        conn.commit()
        conn.close()

        return jsonify({"ok": True})

    except Exception as e:
        print(f"[Brandpipe] 워치리스트 삭제 오류: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500


@brandpipe_bp.route('/api/brandpipe/watchlist', methods=['GET'])
def get_watchlist():
    """
    워치리스트 조회

    Query Params:
        limit: 조회할 개수 (기본 50)

    Response JSON:
        ok: True
        items: 워치리스트 항목 리스트
    """
    try:
        limit = request.args.get('limit', 50, type=int)
        limit = min(limit, 100)

        conn = get_brandpipe_db()
        cursor = conn.cursor()

        if USE_POSTGRES:
            cursor.execute('''
                SELECT id, created_at, search_id, product_title, product_url, platform,
                       target_margin_rate, target_margin_amount,
                       last_checked_at, last_best_margin_rate, last_best_margin_amount
                FROM brandpipe_watchlist
                ORDER BY created_at DESC
                LIMIT %s
            ''', (limit,))
        else:
            cursor.execute('''
                SELECT id, created_at, search_id, product_title, product_url, platform,
                       target_margin_rate, target_margin_amount,
                       last_checked_at, last_best_margin_rate, last_best_margin_amount
                FROM brandpipe_watchlist
                ORDER BY created_at DESC
                LIMIT ?
            ''', (limit,))

        rows = cursor.fetchall()
        conn.close()

        items = []
        for row in rows:
            if hasattr(row, 'keys'):
                row_dict = dict(row)
            else:
                row_dict = {
                    'id': row[0],
                    'created_at': row[1],
                    'search_id': row[2],
                    'product_title': row[3],
                    'product_url': row[4],
                    'platform': row[5],
                    'target_margin_rate': row[6],
                    'target_margin_amount': row[7],
                    'last_checked_at': row[8],
                    'last_best_margin_rate': row[9],
                    'last_best_margin_amount': row[10]
                }

            items.append({
                "id": row_dict['id'],
                "created_at": str(row_dict['created_at']) if row_dict['created_at'] else None,
                "search_id": row_dict['search_id'],
                "product_title": row_dict['product_title'],
                "product_url": row_dict['product_url'],
                "platform": row_dict['platform'],
                "target_margin_rate": row_dict['target_margin_rate'],
                "target_margin_amount": row_dict['target_margin_amount'],
                "last_checked_at": str(row_dict['last_checked_at']) if row_dict['last_checked_at'] else None,
                "last_best_margin_rate": row_dict['last_best_margin_rate'],
                "last_best_margin_amount": row_dict['last_best_margin_amount']
            })

        return jsonify({"ok": True, "items": items})

    except Exception as e:
        print(f"[Brandpipe] 워치리스트 조회 오류: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500


@brandpipe_bp.route('/api/brandpipe/watchlist/analyze', methods=['POST'])
def analyze_watchlist_item():
    """
    워치리스트 항목 재분석

    Request JSON:
        id: 워치리스트 ID

    Response JSON:
        analyze API와 동일한 형식
    """
    try:
        data = request.get_json() or {}
        watchlist_id = data.get('id')

        if not watchlist_id:
            return jsonify({"ok": False, "error": "id가 필요합니다."}), 400

        # 워치리스트 항목 조회
        conn = get_brandpipe_db()
        cursor = conn.cursor()

        if USE_POSTGRES:
            cursor.execute('''
                SELECT id, product_title, product_url, platform
                FROM brandpipe_watchlist
                WHERE id = %s
            ''', (watchlist_id,))
        else:
            cursor.execute('''
                SELECT id, product_title, product_url, platform
                FROM brandpipe_watchlist
                WHERE id = ?
            ''', (watchlist_id,))

        row = cursor.fetchone()
        if not row:
            conn.close()
            return jsonify({"ok": False, "error": "워치리스트 항목을 찾을 수 없습니다."}), 404

        if hasattr(row, 'keys'):
            row_dict = dict(row)
        else:
            row_dict = {
                'id': row[0],
                'product_title': row[1],
                'product_url': row[2],
                'platform': row[3]
            }

        product_url = row_dict['product_url']
        product_title = row_dict['product_title']

        # 분석 수행 (기존 로직 재사용)
        start_time = time.time()

        if product_url:
            product = parse_product_info(product_url, None)
        else:
            product = parse_product_info(None, product_title)

        search_keywords = build_search_keywords(product)
        suppliers = search_suppliers(search_keywords, include_overseas=False)

        # 마진 계산
        platform_price = product.get('price') or 0
        for supplier in suppliers:
            unit_price = supplier.get('unit_price', 0)
            currency = supplier.get('currency', 'KRW')

            if currency != 'KRW':
                unit_price_krw = convert_currency(unit_price, currency, 'KRW')
                shipping_krw = convert_currency(supplier.get('shipping_fee', 0), currency, 'KRW')
            else:
                unit_price_krw = unit_price
                shipping_krw = supplier.get('shipping_fee', 0)

            margin = estimate_margin(platform_price, unit_price_krw, shipping_krw)
            supplier['estimated_margin_rate'] = margin['margin_rate']
            supplier['estimated_margin_amount'] = margin['margin_amount']
            supplier['unit_price_krw'] = round(unit_price_krw)
            supplier['similarity_score'] = compute_similarity_score(product, supplier)

        # 정렬
        suppliers.sort(
            key=lambda x: (x.get('similarity_score', 0), x.get('estimated_margin_amount', 0)),
            reverse=True
        )

        # 최고 마진 정보 업데이트
        best_margin_rate = None
        best_margin_amount = None
        if suppliers:
            best_margin_rate = suppliers[0].get('estimated_margin_rate')
            best_margin_amount = suppliers[0].get('estimated_margin_amount')

        if USE_POSTGRES:
            cursor.execute('''
                UPDATE brandpipe_watchlist
                SET last_checked_at = CURRENT_TIMESTAMP,
                    last_best_margin_rate = %s,
                    last_best_margin_amount = %s
                WHERE id = %s
            ''', (best_margin_rate, best_margin_amount, watchlist_id))
        else:
            cursor.execute('''
                UPDATE brandpipe_watchlist
                SET last_checked_at = CURRENT_TIMESTAMP,
                    last_best_margin_rate = ?,
                    last_best_margin_amount = ?
                WHERE id = ?
            ''', (best_margin_rate, best_margin_amount, watchlist_id))

        conn.commit()
        conn.close()

        analysis_time_ms = int((time.time() - start_time) * 1000)

        return jsonify({
            "ok": True,
            "watchlist_id": watchlist_id,
            "product": {
                "title": product.get('title'),
                "brand": product.get('brand'),
                "platform": product.get('platform'),
                "platform_url": product.get('platform_url'),
                "price": product.get('price'),
                "image_url": product.get('image_url')
            },
            "suppliers": suppliers,
            "meta": {
                "search_keywords": search_keywords,
                "analysis_time_ms": analysis_time_ms
            }
        })

    except Exception as e:
        print(f"[Brandpipe] 워치리스트 재분석 오류: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500
