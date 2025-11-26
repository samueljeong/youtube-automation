"""
디자인 자동화 시스템 - Figma API 연동 & 상세페이지 생성
"""
from flask import Blueprint, request, jsonify, send_file
import os
import requests
import json
import base64
from datetime import datetime
import hashlib
from openai import OpenAI

# OpenAI 클라이언트
def get_openai_client():
    key = (os.getenv("OPENAI_API_KEY") or "").strip()
    if not key:
        return None
    return OpenAI(api_key=key)

design_bp = Blueprint('design', __name__)

# ===== 환경 변수 =====
FIGMA_ACCESS_TOKEN = os.getenv('FIGMA_ACCESS_TOKEN', '')
FIGMA_API_BASE = 'https://api.figma.com/v1'

# ===== 폰트 저장 경로 =====
FONTS_DIR = os.path.join(os.path.dirname(__file__), 'static', 'fonts')
TEMPLATES_DIR = os.path.join(os.path.dirname(__file__), 'static', 'templates')

# 디렉토리 생성
os.makedirs(FONTS_DIR, exist_ok=True)
os.makedirs(TEMPLATES_DIR, exist_ok=True)

# ===== 기본 폰트 목록 (무료 한글 폰트) =====
DEFAULT_FONTS = [
    {
        "id": "pretendard",
        "name": "Pretendard",
        "family": "Pretendard",
        "weights": ["Light", "Regular", "Medium", "SemiBold", "Bold"],
        "source": "https://cdn.jsdelivr.net/gh/orioncactus/pretendard/dist/web/static/pretendard.css",
        "type": "web"
    },
    {
        "id": "noto-sans-kr",
        "name": "Noto Sans KR",
        "family": "Noto Sans KR",
        "weights": ["Light", "Regular", "Medium", "Bold"],
        "source": "https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@300;400;500;700&display=swap",
        "type": "google"
    },
    {
        "id": "spoqa-han-sans",
        "name": "Spoqa Han Sans Neo",
        "family": "Spoqa Han Sans Neo",
        "weights": ["Light", "Regular", "Medium", "Bold"],
        "source": "https://spoqa.github.io/spoqa-han-sans/css/SpoqaHanSansNeo.css",
        "type": "web"
    },
    {
        "id": "nanum-gothic",
        "name": "Nanum Gothic",
        "family": "Nanum Gothic",
        "weights": ["Regular", "Bold", "ExtraBold"],
        "source": "https://fonts.googleapis.com/css2?family=Nanum+Gothic:wght@400;700;800&display=swap",
        "type": "google"
    },
    {
        "id": "nanum-myeongjo",
        "name": "Nanum Myeongjo",
        "family": "Nanum Myeongjo",
        "weights": ["Regular", "Bold", "ExtraBold"],
        "source": "https://fonts.googleapis.com/css2?family=Nanum+Myeongjo:wght@400;700;800&display=swap",
        "type": "google"
    }
]

# ===== 템플릿 저장소 (메모리/DB) =====
TEMPLATES_STORE = []
CUSTOM_FONTS = []

# ===== Figma API 헬퍼 =====
def call_figma_api(endpoint, method='GET', data=None):
    """Figma API 호출"""
    if not FIGMA_ACCESS_TOKEN:
        print("[Figma API] 액세스 토큰이 설정되지 않음")
        return None

    headers = {
        'X-Figma-Token': FIGMA_ACCESS_TOKEN,
        'Content-Type': 'application/json'
    }

    try:
        url = f"{FIGMA_API_BASE}{endpoint}"
        print(f"[Figma API] 요청: {method} {url}")

        if method == 'GET':
            response = requests.get(url, headers=headers)
        elif method == 'POST':
            response = requests.post(url, headers=headers, json=data)

        print(f"[Figma API] 응답 상태: {response.status_code}")

        if response.status_code == 200:
            return response.json()
        else:
            print(f"[Figma API] 오류: {response.text[:500]}")
            return None
    except Exception as e:
        print(f"[Figma API] Error: {e}")
        return None

# ===== API 엔드포인트 =====

@design_bp.route('/api/design/status', methods=['GET'])
def get_design_status():
    """디자인 시스템 상태 확인"""
    figma_connected = bool(FIGMA_ACCESS_TOKEN)

    # Figma 연결 테스트
    figma_user = None
    if figma_connected:
        result = call_figma_api('/me')
        if result:
            figma_user = result.get('handle', result.get('email', 'Connected'))
        else:
            figma_connected = False

    return jsonify({
        "ok": True,
        "status": {
            "figma": {
                "connected": figma_connected,
                "user": figma_user
            },
            "fonts": {
                "default": len(DEFAULT_FONTS),
                "custom": len(CUSTOM_FONTS)
            },
            "templates": len(TEMPLATES_STORE)
        }
    })

# ===== 폰트 관리 =====

@design_bp.route('/api/design/fonts', methods=['GET'])
def get_fonts():
    """사용 가능한 폰트 목록"""
    all_fonts = DEFAULT_FONTS + CUSTOM_FONTS
    return jsonify({
        "ok": True,
        "fonts": all_fonts,
        "default": DEFAULT_FONTS,
        "custom": CUSTOM_FONTS
    })

@design_bp.route('/api/design/fonts', methods=['POST'])
def add_custom_font():
    """커스텀 폰트 추가"""
    data = request.get_json()

    name = data.get('name')
    family = data.get('family')
    source = data.get('source')  # URL 또는 base64

    if not name or not family:
        return jsonify({"ok": False, "error": "폰트 이름과 family가 필요합니다."}), 400

    font_id = hashlib.md5(name.encode()).hexdigest()[:8]

    new_font = {
        "id": font_id,
        "name": name,
        "family": family,
        "weights": data.get('weights', ['Regular']),
        "source": source,
        "type": "custom",
        "addedAt": datetime.now().isoformat()
    }

    CUSTOM_FONTS.append(new_font)

    return jsonify({
        "ok": True,
        "message": f"폰트 '{name}'가 추가되었습니다.",
        "font": new_font
    })

@design_bp.route('/api/design/fonts/<font_id>', methods=['DELETE'])
def delete_custom_font(font_id):
    """커스텀 폰트 삭제"""
    global CUSTOM_FONTS
    CUSTOM_FONTS = [f for f in CUSTOM_FONTS if f['id'] != font_id]
    return jsonify({"ok": True, "message": "폰트가 삭제되었습니다."})

# ===== Figma 연동 =====

@design_bp.route('/api/design/figma/files', methods=['GET'])
def get_figma_files():
    """Figma 프로젝트/파일 목록"""
    if not FIGMA_ACCESS_TOKEN:
        return jsonify({"ok": False, "error": "Figma 토큰이 설정되지 않았습니다."}), 400

    # 최근 파일 가져오기 (Figma는 팀/프로젝트 기반이므로 team_id 필요)
    # 여기서는 사용자가 파일 키를 직접 입력하는 방식으로
    return jsonify({
        "ok": True,
        "message": "Figma 파일 키를 직접 입력해주세요.",
        "help": "Figma 파일 URL에서 /file/ 뒤의 값이 파일 키입니다."
    })

@design_bp.route('/api/design/figma/file/<file_key>', methods=['GET'])
def get_figma_file(file_key):
    """Figma 파일 정보 가져오기"""
    result = call_figma_api(f'/files/{file_key}')

    if not result:
        return jsonify({"ok": False, "error": "파일을 가져올 수 없습니다."}), 404

    # 파일 구조 파싱
    document = result.get('document', {})
    pages = []

    for child in document.get('children', []):
        if child.get('type') == 'CANVAS':
            frames = []
            for frame in child.get('children', []):
                if frame.get('type') in ['FRAME', 'COMPONENT', 'COMPONENT_SET']:
                    frames.append({
                        "id": frame.get('id'),
                        "name": frame.get('name'),
                        "type": frame.get('type'),
                        "width": frame.get('absoluteBoundingBox', {}).get('width'),
                        "height": frame.get('absoluteBoundingBox', {}).get('height')
                    })
            pages.append({
                "id": child.get('id'),
                "name": child.get('name'),
                "frames": frames
            })

    return jsonify({
        "ok": True,
        "file": {
            "key": file_key,
            "name": result.get('name'),
            "lastModified": result.get('lastModified'),
            "pages": pages
        }
    })

@design_bp.route('/api/design/figma/file/<file_key>/nodes', methods=['GET'])
def get_figma_nodes(file_key):
    """특정 노드들의 상세 정보"""
    node_ids = request.args.get('ids', '')  # 쉼표로 구분된 노드 ID

    if not node_ids:
        return jsonify({"ok": False, "error": "노드 ID가 필요합니다."}), 400

    result = call_figma_api(f'/files/{file_key}/nodes?ids={node_ids}')

    if not result:
        return jsonify({"ok": False, "error": "노드 정보를 가져올 수 없습니다."}), 404

    return jsonify({
        "ok": True,
        "nodes": result.get('nodes', {})
    })

@design_bp.route('/api/design/figma/file/<file_key>/images', methods=['GET'])
def get_figma_images(file_key):
    """Figma 프레임을 이미지로 내보내기"""
    node_ids = request.args.get('ids', '')
    format = request.args.get('format', 'png')  # png, jpg, svg, pdf
    scale = request.args.get('scale', '2')  # 1, 2, 3, 4

    if not node_ids:
        return jsonify({"ok": False, "error": "노드 ID가 필요합니다."}), 400

    result = call_figma_api(f'/images/{file_key}?ids={node_ids}&format={format}&scale={scale}')

    if not result:
        return jsonify({"ok": False, "error": "이미지를 생성할 수 없습니다."}), 500

    return jsonify({
        "ok": True,
        "images": result.get('images', {}),
        "err": result.get('err')
    })

# ===== 템플릿 관리 =====

@design_bp.route('/api/design/templates', methods=['GET'])
def get_templates():
    """저장된 템플릿 목록"""
    return jsonify({
        "ok": True,
        "templates": TEMPLATES_STORE
    })

@design_bp.route('/api/design/templates', methods=['POST'])
def create_template():
    """새 템플릿 생성 (Figma 파일에서)"""
    data = request.get_json()

    figma_file_key = data.get('figmaFileKey')
    figma_node_id = data.get('figmaNodeId')
    name = data.get('name')
    category = data.get('category', 'general')
    variables = data.get('variables', [])  # [{"name": "product_name", "type": "text", "layerId": "xxx"}]

    if not name:
        return jsonify({"ok": False, "error": "템플릿 이름이 필요합니다."}), 400

    template_id = hashlib.md5(f"{name}{datetime.now().isoformat()}".encode()).hexdigest()[:12]

    new_template = {
        "id": template_id,
        "name": name,
        "category": category,
        "figma": {
            "fileKey": figma_file_key,
            "nodeId": figma_node_id
        } if figma_file_key else None,
        "variables": variables,
        "createdAt": datetime.now().isoformat(),
        "updatedAt": datetime.now().isoformat()
    }

    TEMPLATES_STORE.append(new_template)

    return jsonify({
        "ok": True,
        "message": f"템플릿 '{name}'가 생성되었습니다.",
        "template": new_template
    })

@design_bp.route('/api/design/templates/<template_id>', methods=['GET'])
def get_template(template_id):
    """템플릿 상세 정보"""
    template = next((t for t in TEMPLATES_STORE if t['id'] == template_id), None)

    if not template:
        return jsonify({"ok": False, "error": "템플릿을 찾을 수 없습니다."}), 404

    return jsonify({
        "ok": True,
        "template": template
    })

@design_bp.route('/api/design/templates/<template_id>', methods=['PUT'])
def update_template(template_id):
    """템플릿 수정"""
    data = request.get_json()

    template = next((t for t in TEMPLATES_STORE if t['id'] == template_id), None)

    if not template:
        return jsonify({"ok": False, "error": "템플릿을 찾을 수 없습니다."}), 404

    # 업데이트
    if 'name' in data:
        template['name'] = data['name']
    if 'category' in data:
        template['category'] = data['category']
    if 'variables' in data:
        template['variables'] = data['variables']

    template['updatedAt'] = datetime.now().isoformat()

    return jsonify({
        "ok": True,
        "message": "템플릿이 수정되었습니다.",
        "template": template
    })

@design_bp.route('/api/design/templates/<template_id>', methods=['DELETE'])
def delete_template(template_id):
    """템플릿 삭제"""
    global TEMPLATES_STORE
    TEMPLATES_STORE = [t for t in TEMPLATES_STORE if t['id'] != template_id]
    return jsonify({"ok": True, "message": "템플릿이 삭제되었습니다."})

# ===== 이미지 생성 =====

@design_bp.route('/api/design/generate', methods=['POST'])
def generate_image():
    """템플릿에 데이터를 바인딩하여 이미지 생성"""
    data = request.get_json()

    template_id = data.get('templateId')
    variables = data.get('variables', {})  # {"product_name": "상품명", "price": "29,000원"}

    template = next((t for t in TEMPLATES_STORE if t['id'] == template_id), None)

    if not template:
        return jsonify({"ok": False, "error": "템플릿을 찾을 수 없습니다."}), 404

    if not template.get('figma'):
        return jsonify({"ok": False, "error": "Figma 연동이 필요한 템플릿입니다."}), 400

    # Figma에서 이미지 생성
    # 실제로는 Figma Plugin API를 사용하여 변수를 교체해야 함
    # 여기서는 기본 이미지만 내보내기

    file_key = template['figma']['fileKey']
    node_id = template['figma']['nodeId']

    result = call_figma_api(f'/images/{file_key}?ids={node_id}&format=png&scale=2')

    if not result or not result.get('images'):
        return jsonify({"ok": False, "error": "이미지 생성 실패"}), 500

    image_url = result['images'].get(node_id)

    return jsonify({
        "ok": True,
        "message": "이미지가 생성되었습니다.",
        "image": {
            "url": image_url,
            "variables": variables,
            "template": template['name']
        }
    })

# ===== 벤치마킹 (웹페이지 캡처 & 분석) =====

@design_bp.route('/api/design/benchmark', methods=['POST'])
def benchmark_page():
    """웹페이지 벤치마킹 (스크린샷 + AI 분석)"""
    data = request.get_json()
    url = data.get('url')
    image_url = data.get('imageUrl')  # 직접 이미지 URL 입력도 지원

    if not url and not image_url:
        return jsonify({"ok": False, "error": "URL 또는 이미지 URL이 필요합니다."}), 400

    client = get_openai_client()
    if not client:
        return jsonify({"ok": False, "error": "OpenAI API 키가 설정되지 않았습니다."}), 400

    try:
        # 이미지 URL 결정 (직접 입력 또는 스크린샷 서비스 사용)
        if image_url:
            analysis_image_url = image_url
        else:
            # thum.io 무료 스크린샷 서비스 사용
            analysis_image_url = f"https://image.thum.io/get/width/1200/crop/2000/{url}"

        print(f"[Benchmark] 분석 이미지 URL: {analysis_image_url}")

        # OpenAI Vision API로 분석
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "system",
                    "content": """당신은 전문 UI/UX 디자이너입니다. 상세페이지 이미지를 분석하여 다음 정보를 JSON 형식으로 추출해주세요:

1. colors: 주요 색상 팔레트 (HEX 코드 5개)
2. fonts: 감지된 폰트 스타일 (제목, 본문, 강조 등)
3. layout: 레이아웃 구조 설명
4. style: 전체적인 디자인 스타일 (모던, 미니멀, 화려함 등)
5. highlights: 눈에 띄는 디자인 요소
6. suggestions: 이 스타일을 참고할 때 추천 사항

반드시 JSON 형식으로만 응답하세요."""
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": "이 상세페이지의 디자인을 분석해주세요."
                        },
                        {
                            "type": "image_url",
                            "image_url": {"url": analysis_image_url}
                        }
                    ]
                }
            ],
            max_tokens=1500
        )

        result_text = response.choices[0].message.content
        print(f"[Benchmark] AI 응답: {result_text[:200]}...")

        # JSON 파싱 시도
        import re
        json_match = re.search(r'\{[\s\S]*\}', result_text)
        if json_match:
            analysis = json.loads(json_match.group())
        else:
            analysis = {"raw": result_text}

        return jsonify({
            "ok": True,
            "url": url,
            "imageUrl": analysis_image_url,
            "analysis": analysis
        })

    except Exception as e:
        print(f"[Benchmark] 오류: {e}")
        return jsonify({
            "ok": False,
            "error": f"분석 중 오류가 발생했습니다: {str(e)}"
        }), 500

# ===== 변수 추출 (Figma 레이어에서) =====

@design_bp.route('/api/design/figma/file/<file_key>/extract-variables', methods=['GET'])
def extract_variables(file_key):
    """Figma 파일에서 {{변수}} 패턴을 가진 레이어 추출"""
    node_id = request.args.get('nodeId')

    result = call_figma_api(f'/files/{file_key}')

    if not result:
        return jsonify({"ok": False, "error": "파일을 가져올 수 없습니다."}), 404

    variables = []

    def find_variables(node, path=""):
        """재귀적으로 {{변수}} 패턴 찾기"""
        name = node.get('name', '')
        node_path = f"{path}/{name}" if path else name

        # {{variable}} 패턴 찾기
        import re
        matches = re.findall(r'\{\{(\w+)\}\}', name)

        for match in matches:
            variables.append({
                "name": match,
                "layerId": node.get('id'),
                "layerName": name,
                "layerType": node.get('type'),
                "path": node_path
            })

        # 텍스트 노드의 경우 characters에서도 찾기
        if node.get('type') == 'TEXT':
            text = node.get('characters', '')
            text_matches = re.findall(r'\{\{(\w+)\}\}', text)
            for match in text_matches:
                if match not in [v['name'] for v in variables]:
                    variables.append({
                        "name": match,
                        "layerId": node.get('id'),
                        "layerName": name,
                        "layerType": 'TEXT',
                        "path": node_path,
                        "inText": True
                    })

        # 자식 노드 탐색
        for child in node.get('children', []):
            find_variables(child, node_path)

    # 문서 전체 탐색
    document = result.get('document', {})
    find_variables(document)

    return jsonify({
        "ok": True,
        "variables": variables,
        "count": len(variables)
    })

print("[Design Server] 디자인 자동화 모듈 로드됨")
