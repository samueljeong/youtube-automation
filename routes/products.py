"""
상품관리 API (/api/products/*)

재고 관리 및 판매 로그 기능
"""

from flask import Blueprint, jsonify, request

products_bp = Blueprint('products', __name__)

# DB 연결 함수와 설정은 drama_server에서 import
# 순환 참조 방지를 위해 함수 내에서 import
def _get_db():
    from drama_server import get_db_connection, USE_POSTGRES
    return get_db_connection(), USE_POSTGRES


@products_bp.route("/api/products", methods=["GET"])
def get_products():
    """모든 상품 조회"""
    try:
        conn, USE_POSTGRES = _get_db()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT id, name, category, cny_price, sell_price, quantity, stock,
                   platform, sale_type, hs_code, duty_rate, link, image_url, created_at
            FROM products ORDER BY created_at DESC
        ''')
        rows = cursor.fetchall()
        cursor.close()
        conn.close()

        products = []
        for row in rows:
            if USE_POSTGRES:
                products.append({
                    'id': row['id'],
                    'name': row['name'],
                    'category': row['category'],
                    'cnyPrice': row['cny_price'],
                    'sellPrice': row['sell_price'],
                    'quantity': row['quantity'],
                    'stock': row['stock'],
                    'platform': row['platform'],
                    'saleType': row['sale_type'],
                    'hsCode': row['hs_code'],
                    'dutyRate': row['duty_rate'],
                    'link': row['link'],
                    'imageUrl': row['image_url'],
                    'createdAt': str(row['created_at']) if row['created_at'] else None
                })
            else:
                products.append({
                    'id': row[0],
                    'name': row[1],
                    'category': row[2],
                    'cnyPrice': row[3],
                    'sellPrice': row[4],
                    'quantity': row[5],
                    'stock': row[6],
                    'platform': row[7],
                    'saleType': row[8],
                    'hsCode': row[9],
                    'dutyRate': row[10],
                    'link': row[11],
                    'imageUrl': row[12],
                    'createdAt': row[13]
                })
        return jsonify({'ok': True, 'products': products})
    except Exception as e:
        print(f"[PRODUCTS] Error: {e}")
        return jsonify({'ok': False, 'error': str(e)}), 500


@products_bp.route("/api/products", methods=["POST"])
def add_product():
    """상품 추가"""
    try:
        data = request.json
        conn, USE_POSTGRES = _get_db()
        cursor = conn.cursor()

        if USE_POSTGRES:
            cursor.execute('''
                INSERT INTO products (id, name, category, cny_price, sell_price, quantity, stock,
                                      platform, sale_type, hs_code, duty_rate, link, image_url)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ''', (
                data.get('id'),
                data.get('name'),
                data.get('category', '미분류'),
                data.get('cnyPrice'),
                data.get('sellPrice'),
                data.get('quantity', 1),
                data.get('stock', 0),
                data.get('platform'),
                data.get('saleType'),
                data.get('hsCode'),
                data.get('dutyRate'),
                data.get('link', ''),
                data.get('imageUrl', '')
            ))
        else:
            cursor.execute('''
                INSERT INTO products (id, name, category, cny_price, sell_price, quantity, stock,
                                      platform, sale_type, hs_code, duty_rate, link, image_url)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                data.get('id'),
                data.get('name'),
                data.get('category', '미분류'),
                data.get('cnyPrice'),
                data.get('sellPrice'),
                data.get('quantity', 1),
                data.get('stock', 0),
                data.get('platform'),
                data.get('saleType'),
                data.get('hsCode'),
                data.get('dutyRate'),
                data.get('link', ''),
                data.get('imageUrl', '')
            ))

        conn.commit()
        cursor.close()
        conn.close()
        return jsonify({'ok': True, 'message': '상품이 등록되었습니다.'})
    except Exception as e:
        print(f"[PRODUCTS] Add error: {e}")
        return jsonify({'ok': False, 'error': str(e)}), 500


@products_bp.route("/api/products/<product_id>", methods=["PUT"])
def update_product(product_id):
    """상품 수정"""
    try:
        data = request.json
        conn, USE_POSTGRES = _get_db()
        cursor = conn.cursor()

        if USE_POSTGRES:
            cursor.execute('''
                UPDATE products SET name=%s, category=%s, cny_price=%s, sell_price=%s,
                                   stock=%s, image_url=%s, updated_at=CURRENT_TIMESTAMP
                WHERE id=%s
            ''', (
                data.get('name'),
                data.get('category'),
                data.get('cnyPrice'),
                data.get('sellPrice'),
                data.get('stock', 0),
                data.get('imageUrl', ''),
                product_id
            ))
        else:
            cursor.execute('''
                UPDATE products SET name=?, category=?, cny_price=?, sell_price=?,
                                   stock=?, image_url=?, updated_at=CURRENT_TIMESTAMP
                WHERE id=?
            ''', (
                data.get('name'),
                data.get('category'),
                data.get('cnyPrice'),
                data.get('sellPrice'),
                data.get('stock', 0),
                data.get('imageUrl', ''),
                product_id
            ))

        conn.commit()
        cursor.close()
        conn.close()
        return jsonify({'ok': True, 'message': '상품이 수정되었습니다.'})
    except Exception as e:
        print(f"[PRODUCTS] Update error: {e}")
        return jsonify({'ok': False, 'error': str(e)}), 500


@products_bp.route("/api/products/<product_id>", methods=["DELETE"])
def delete_product(product_id):
    """상품 삭제"""
    try:
        conn, USE_POSTGRES = _get_db()
        cursor = conn.cursor()
        if USE_POSTGRES:
            cursor.execute('DELETE FROM products WHERE id=%s', (product_id,))
        else:
            cursor.execute('DELETE FROM products WHERE id=?', (product_id,))
        conn.commit()
        cursor.close()
        conn.close()
        return jsonify({'ok': True, 'message': '상품이 삭제되었습니다.'})
    except Exception as e:
        print(f"[PRODUCTS] Delete error: {e}")
        return jsonify({'ok': False, 'error': str(e)}), 500


@products_bp.route("/api/products/<product_id>/stock", methods=["PATCH"])
def update_stock(product_id):
    """재고 업데이트 + 로그 기록"""
    try:
        data = request.json
        new_stock = data.get('stock', 0)

        conn, USE_POSTGRES = _get_db()
        cursor = conn.cursor()

        # 기존 재고 조회
        if USE_POSTGRES:
            cursor.execute('SELECT stock, name FROM products WHERE id=%s', (product_id,))
        else:
            cursor.execute('SELECT stock, name FROM products WHERE id=?', (product_id,))
        row = cursor.fetchone()
        if not row:
            return jsonify({'ok': False, 'error': '상품을 찾을 수 없습니다.'}), 404

        if USE_POSTGRES:
            old_stock = row['stock']
            product_name = row['name']
        else:
            old_stock = row[0]
            product_name = row[1]
        change = new_stock - old_stock

        # 재고 업데이트
        if USE_POSTGRES:
            cursor.execute('UPDATE products SET stock=%s, updated_at=CURRENT_TIMESTAMP WHERE id=%s',
                          (new_stock, product_id))
        else:
            cursor.execute('UPDATE products SET stock=?, updated_at=CURRENT_TIMESTAMP WHERE id=?',
                          (new_stock, product_id))

        # 변동이 있으면 로그 기록
        if change != 0:
            if USE_POSTGRES:
                cursor.execute('''
                    INSERT INTO sales_logs (product_id, product_name, change_amount)
                    VALUES (%s, %s, %s)
                ''', (product_id, product_name, change))
            else:
                cursor.execute('''
                    INSERT INTO sales_logs (product_id, product_name, change_amount)
                    VALUES (?, ?, ?)
                ''', (product_id, product_name, change))

        conn.commit()
        cursor.close()
        conn.close()
        return jsonify({'ok': True, 'change': change})
    except Exception as e:
        print(f"[PRODUCTS] Stock update error: {e}")
        return jsonify({'ok': False, 'error': str(e)}), 500


@products_bp.route("/api/products/sales-logs", methods=["GET"])
def get_sales_logs():
    """판매/재고 변동 로그 조회"""
    try:
        conn, USE_POSTGRES = _get_db()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT product_name, change_amount, log_date
            FROM sales_logs ORDER BY log_date DESC LIMIT 50
        ''')
        rows = cursor.fetchall()
        cursor.close()
        conn.close()

        logs = []
        for row in rows:
            if USE_POSTGRES:
                logs.append({
                    'productName': row['product_name'],
                    'change': row['change_amount'],
                    'date': str(row['log_date']) if row['log_date'] else None
                })
            else:
                logs.append({
                    'productName': row[0],
                    'change': row[1],
                    'date': row[2]
                })
        return jsonify({'ok': True, 'logs': logs})
    except Exception as e:
        print(f"[PRODUCTS] Logs error: {e}")
        return jsonify({'ok': False, 'error': str(e)}), 500
