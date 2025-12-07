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
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS brandpipe_searches (
                id SERIAL PRIMARY KEY,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                input_url VARCHAR(500),
                input_keyword VARCHAR(200),
                product_title VARCHAR(300),
                product_brand VARCHAR(200),
                product_price INTEGER,
                result_json TEXT
            )
        ''')
    else:
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS brandpipe_searches (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                input_url TEXT,
                input_keyword TEXT,
                product_title TEXT,
                product_brand TEXT,
                product_price INTEGER,
                result_json TEXT
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

    # 1. 국내 도매몰 검색 (현재 Mock)
    try:
        suppliers.extend(search_from_domemall_mock(keywords))
    except Exception as e:
        print(f"[Brandpipe] 도매몰 검색 오류: {e}")

    # 2. 네이버 쇼핑 검색 (실제 크롤링)
    if use_real_search:
        try:
            naver_results = search_from_naver_shopping(keywords)
            if naver_results:
                suppliers.extend(naver_results)
            else:
                # 실제 검색 결과가 없으면 mock으로 폴백
                suppliers.extend(search_from_naver_mock(keywords))
        except Exception as e:
            print(f"[Brandpipe] 네이버 실제 검색 오류, mock으로 폴백: {e}")
            suppliers.extend(search_from_naver_mock(keywords))
    else:
        try:
            suppliers.extend(search_from_naver_mock(keywords))
        except Exception as e:
            print(f"[Brandpipe] 네이버 mock 검색 오류: {e}")

    # 3. 해외 도매 (옵션)
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

        # 4. 마진 계산 추가
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

        # 마진율 높은 순으로 정렬
        suppliers.sort(key=lambda x: x.get('estimated_margin_rate', 0), reverse=True)

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
            "suppliers": suppliers,
            "meta": {
                "keyword_used": keyword or product.get('title'),
                "search_keywords": search_keywords,
                "search_providers": ["domemall_mock", "naver_shopping"] + (["alibaba_mock"] if include_overseas else []),
                "analysis_time_ms": analysis_time_ms,
                "parsing_method": "og+jsonld+fallback"
            }
        }

        # DB에 검색 기록 저장
        try:
            save_search_history(
                input_url=product_url,
                input_keyword=keyword,
                product_title=product.get('title'),
                product_brand=product.get('brand'),
                product_price=product.get('price'),
                result_json=json.dumps(result, ensure_ascii=False)
            )
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

    Response JSON:
        ok: True
        history: 검색 기록 리스트
    """
    try:
        limit = request.args.get('limit', 20, type=int)
        limit = min(limit, 100)  # 최대 100개

        conn = get_brandpipe_db()
        cursor = conn.cursor()

        if USE_POSTGRES:
            cursor.execute('''
                SELECT id, created_at, input_url, input_keyword,
                       product_title, product_brand, product_price, result_json
                FROM brandpipe_searches
                ORDER BY created_at DESC
                LIMIT %s
            ''', (limit,))
        else:
            cursor.execute('''
                SELECT id, created_at, input_url, input_keyword,
                       product_title, product_brand, product_price, result_json
                FROM brandpipe_searches
                ORDER BY created_at DESC
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
                    'result_json': row[7]
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

            history.append({
                "id": row_dict['id'],
                "created_at": str(row_dict['created_at']),
                "input_url": row_dict['input_url'],
                "input_keyword": row_dict['input_keyword'],
                "product_title": row_dict['product_title'],
                "product_brand": row_dict['product_brand'],
                "product_price": row_dict['product_price'],
                "margin_summary": margin_summary
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
                       product_brand: str, product_price: int, result_json: str):
    """검색 기록 저장"""
    conn = get_brandpipe_db()
    cursor = conn.cursor()

    if USE_POSTGRES:
        cursor.execute('''
            INSERT INTO brandpipe_searches
            (input_url, input_keyword, product_title, product_brand, product_price, result_json)
            VALUES (%s, %s, %s, %s, %s, %s)
        ''', (input_url, input_keyword, product_title, product_brand, product_price, result_json))
    else:
        cursor.execute('''
            INSERT INTO brandpipe_searches
            (input_url, input_keyword, product_title, product_brand, product_price, result_json)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (input_url, input_keyword, product_title, product_brand, product_price, result_json))

    conn.commit()
    conn.close()


@brandpipe_bp.route('/api/brandpipe/test', methods=['GET'])
def test_endpoint():
    """테스트 엔드포인트"""
    return jsonify({
        "ok": True,
        "message": "Brandpipe API is working!",
        "version": "2.0.0",
        "features": [
            "og_meta_parsing",
            "json_ld_parsing",
            "naver_shopping_search",
            "margin_calculation"
        ]
    })
