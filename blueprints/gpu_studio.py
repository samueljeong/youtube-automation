"""
GPU Studio Blueprint
로컬 GPU 기반 이미지/TTS/영상 생성 통합 대시보드
"""

import os
import json
import uuid
import subprocess
import threading
from datetime import datetime
from flask import Blueprint, render_template, request, jsonify, Response, send_from_directory
from typing import Optional, Dict, Any

gpu_studio_bp = Blueprint('gpu_studio', __name__)

# 작업 상태 저장
job_status: Dict[str, Any] = {
    "current_job": None,
    "progress": 0,
    "message": "",
    "results": []
}


@gpu_studio_bp.route('/gpu-studio')
def gpu_studio_page():
    """GPU Studio 메인 페이지"""
    return render_template('gpu_studio.html')


@gpu_studio_bp.route('/api/gpu/status')
def gpu_status():
    """GPU/모델 상태 확인"""
    status = {
        "comfyui": _check_comfyui(),
        "xtts": _check_xtts(),
        "svd": _check_svd(),
    }
    return jsonify(status)


@gpu_studio_bp.route('/api/gpu/image', methods=['POST'])
def generate_image():
    """Flux 이미지 생성"""
    data = request.json or {}
    prompt = data.get('prompt', '')
    size = data.get('size', '1280x720')
    steps = data.get('steps', 4)

    if not prompt:
        return jsonify({"ok": False, "error": "프롬프트가 필요합니다"})

    try:
        # ComfyUI 이미지 생성
        os.environ['COMFYUI_ENABLED'] = 'true'
        os.environ['COMFYUI_MODEL'] = 'flux'

        from image.comfyui import generate_image_comfyui

        result = generate_image_comfyui(
            prompt=prompt,
            size=size,
            steps=steps
        )

        return jsonify(result)

    except Exception as e:
        return jsonify({"ok": False, "error": str(e)})


@gpu_studio_bp.route('/api/gpu/tts', methods=['POST'])
def generate_tts():
    """XTTS 음성 생성"""
    data = request.json or {}
    text = data.get('text', '')
    language = data.get('language', 'ko')
    speaker = data.get('speaker', 'Craig Gutsy')

    if not text:
        return jsonify({"ok": False, "error": "텍스트가 필요합니다"})

    try:
        result = _generate_xtts(text, language, speaker)
        return jsonify(result)
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)})


@gpu_studio_bp.route('/api/gpu/video', methods=['POST'])
def generate_video():
    """SVD 이미지→영상 생성"""
    data = request.json or {}
    image_path = data.get('image_path', '')

    if not image_path:
        return jsonify({"ok": False, "error": "이미지 경로가 필요합니다"})

    if not os.path.exists(image_path):
        return jsonify({"ok": False, "error": "이미지 파일이 존재하지 않습니다"})

    try:
        result = _generate_svd_video(image_path)
        return jsonify(result)
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)})


@gpu_studio_bp.route('/outputs/gpu_studio/<path:filename>')
def serve_gpu_output(filename):
    """GPU Studio 출력 파일 서빙"""
    return send_from_directory('outputs/gpu_studio', filename)


@gpu_studio_bp.route('/api/gpu/history')
def get_history():
    """생성 히스토리 조회"""
    history_dir = "outputs/gpu_studio"
    os.makedirs(history_dir, exist_ok=True)

    history = []
    for f in sorted(os.listdir(history_dir), reverse=True)[:20]:
        path = os.path.join(history_dir, f)
        if os.path.isfile(path):
            history.append({
                "filename": f,
                "path": path,
                "created": datetime.fromtimestamp(os.path.getctime(path)).isoformat(),
                "type": _get_file_type(f)
            })

    return jsonify({"ok": True, "history": history})


# ========== Helper Functions ==========

def _check_comfyui() -> Dict[str, Any]:
    """ComfyUI 상태 확인"""
    try:
        import requests
        url = os.getenv("COMFYUI_URL", "http://localhost:8188")
        response = requests.get(f"{url}/system_stats", timeout=3)
        if response.status_code == 200:
            data = response.json()
            return {
                "available": True,
                "url": url,
                "vram_free": data.get("devices", [{}])[0].get("vram_free", 0),
                "model": "flux"
            }
    except:
        pass
    return {"available": False, "error": "ComfyUI 서버에 연결할 수 없습니다"}


def _check_xtts() -> Dict[str, Any]:
    """XTTS 상태 확인"""
    try:
        # Python 3.10 경로로 확인
        result = subprocess.run(
            ["/opt/homebrew/bin/python3.10", "-c", "from TTS.api import TTS; print('ok')"],
            capture_output=True,
            text=True,
            timeout=10
        )
        if "ok" in result.stdout:
            return {"available": True, "model": "xtts_v2"}
    except:
        pass
    return {"available": False, "error": "XTTS가 설치되지 않았습니다"}


def _check_svd() -> Dict[str, Any]:
    """SVD 모델 상태 확인"""
    svd_path = "/Users/samuel/ComfyUI/models/svd/svd_xt.safetensors"
    if os.path.exists(svd_path):
        size = os.path.getsize(svd_path)
        if size > 9_000_000_000:  # 9GB 이상이면 완료
            return {"available": True, "model": "svd_xt", "size": size}
        else:
            return {"available": False, "error": f"다운로드 중 ({size / 1e9:.1f}GB / 9.5GB)"}
    return {"available": False, "error": "SVD 모델이 설치되지 않았습니다"}


def _generate_xtts(text: str, language: str = "ko", speaker: str = "Craig Gutsy") -> Dict[str, Any]:
    """XTTS로 음성 생성"""
    output_dir = "outputs/gpu_studio"
    os.makedirs(output_dir, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = os.path.join(output_dir, f"tts_{timestamp}.wav")

    # 텍스트 이스케이프 처리
    escaped_text = text.replace('\\', '\\\\').replace('"', '\\"').replace('\n', ' ')

    # Python 3.10으로 XTTS 실행
    script = f'''
import os
os.environ["COQUI_TOS_AGREED"] = "1"
import warnings
warnings.filterwarnings("ignore")
from TTS.api import TTS

# XTTS 모델 로드
tts = TTS("tts_models/multilingual/multi-dataset/xtts_v2")
print("Model loaded")

# 음성 생성
tts.tts_to_file(
    text="{escaped_text}",
    language="{language}",
    speaker="{speaker}",
    file_path="{output_path}"
)
print("Done")
'''

    try:
        # COQUI_TOS_AGREED=1 환경변수로 라이선스 자동 동의
        env = os.environ.copy()
        env["COQUI_TOS_AGREED"] = "1"

        result = subprocess.run(
            ["/opt/homebrew/bin/python3.10", "-c", script],
            capture_output=True,
            text=True,
            timeout=300,
            env=env
        )

        if os.path.exists(output_path):
            return {
                "ok": True,
                "audio_path": output_path,
                "device": "mps" if "mps" in result.stdout else "cpu"
            }
        else:
            return {"ok": False, "error": result.stderr[:500]}

    except subprocess.TimeoutExpired:
        return {"ok": False, "error": "TTS 생성 타임아웃"}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def _generate_svd_video(image_path: str) -> Dict[str, Any]:
    """SVD로 이미지→영상 생성 (ComfyUI 사용)"""
    # TODO: SVD 워크플로우 구현
    return {"ok": False, "error": "SVD 영상 생성은 아직 구현 중입니다"}


def _get_file_type(filename: str) -> str:
    """파일 타입 반환"""
    ext = filename.lower().split('.')[-1]
    if ext in ['jpg', 'jpeg', 'png', 'webp']:
        return 'image'
    elif ext in ['wav', 'mp3', 'ogg']:
        return 'audio'
    elif ext in ['mp4', 'webm', 'mov']:
        return 'video'
    return 'unknown'
