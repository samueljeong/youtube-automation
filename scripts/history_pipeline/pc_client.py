"""
PC 서버 클라이언트

PC가 온라인이면 PC 서버 사용, 오프라인이면 Render API + 로컬 TTS/렌더링
"""

import os
import requests
from typing import Dict, Any, List, Optional


# 서버 URL 설정
PC_SERVER_URL = os.environ.get("PC_SERVER_URL", "http://localhost:5059")
RENDER_URL = "https://drama-s2ns.onrender.com"


def check_pc_online(timeout: float = 3.0) -> bool:
    """PC 서버가 온라인인지 확인"""
    try:
        response = requests.get(f"{PC_SERVER_URL}/health", timeout=timeout)
        return response.status_code == 200
    except:
        return False


def get_active_server() -> tuple[str, str]:
    """
    활성 서버 확인

    Returns:
        (server_url, server_name)
    """
    if check_pc_online():
        return PC_SERVER_URL, "PC"
    return RENDER_URL, "Render"


def generate_video_on_pc(
    script: str,
    title: str,
    image_prompts: List[Dict[str, Any]],
    metadata: Dict[str, Any],
    episode_id: str = "ep001",
    voice: str = "ko-KR-Neural2-C",
    upload: bool = False,
    privacy_status: str = "private",
) -> Dict[str, Any]:
    """
    PC 서버에서 영상 생성 (전체 파이프라인)

    PC가 온라인이면 PC에서 모든 작업 수행
    PC가 오프라인이면 하이브리드 모드 (Render 이미지 + 로컬 TTS/렌더링)
    """
    server_url, server_name = get_active_server()

    print(f"[PC-CLIENT] 활성 서버: {server_name} ({server_url})")

    if server_name == "PC":
        # PC 서버에서 전체 처리
        return _generate_on_pc_server(
            server_url=server_url,
            script=script,
            title=title,
            image_prompts=image_prompts,
            metadata=metadata,
            episode_id=episode_id,
            voice=voice,
            upload=upload,
            privacy_status=privacy_status,
        )
    else:
        # 하이브리드 모드: Render 이미지 + 로컬 TTS/렌더링
        return _generate_hybrid(
            script=script,
            title=title,
            image_prompts=image_prompts,
            metadata=metadata,
            episode_id=episode_id,
            voice=voice,
            upload=upload,
            privacy_status=privacy_status,
        )


def _generate_on_pc_server(
    server_url: str,
    script: str,
    title: str,
    image_prompts: List[Dict[str, Any]],
    metadata: Dict[str, Any],
    episode_id: str,
    voice: str,
    upload: bool,
    privacy_status: str,
) -> Dict[str, Any]:
    """PC 서버에서 전체 파이프라인 실행"""
    try:
        # PC 서버의 영상 생성 API 호출
        response = requests.post(
            f"{server_url}/api/history/generate-video",
            json={
                "episode_id": episode_id,
                "title": title,
                "script": script,
                "image_prompts": image_prompts,
                "metadata": metadata,
                "voice": voice,
                "upload": upload,
                "privacy_status": privacy_status,
            },
            timeout=1800,  # 30분
        )

        if response.status_code == 200:
            return response.json()
        else:
            return {"ok": False, "error": f"PC 서버 오류: {response.status_code}"}

    except Exception as e:
        return {"ok": False, "error": f"PC 서버 연결 실패: {str(e)}"}


def _generate_hybrid(
    script: str,
    title: str,
    image_prompts: List[Dict[str, Any]],
    metadata: Dict[str, Any],
    episode_id: str,
    voice: str,
    upload: bool,
    privacy_status: str,
) -> Dict[str, Any]:
    """
    하이브리드 모드: Render 이미지 + 로컬 TTS/렌더링

    PC 오프라인 시 사용
    """
    from .tts import generate_tts
    from .image_gen import generate_scene_images
    from .renderer import render_video, render_multi_image_video

    result = {
        "ok": False,
        "episode_id": episode_id,
        "title": title,
        "mode": "hybrid",
    }

    print(f"\n[HYBRID] 하이브리드 모드로 영상 생성")
    print(f"[HYBRID] 이미지: Render API, TTS/렌더링: 로컬")

    # 1. TTS 생성 (로컬)
    print(f"\n[HYBRID] 1/3. TTS 생성 중...")
    output_dir = f"outputs/history/audio"
    tts_result = generate_tts(
        episode_id=episode_id,
        script=script,
        output_dir=output_dir,
    )

    if not tts_result.get("ok"):
        result["error"] = f"TTS 실패: {tts_result.get('error')}"
        return result

    result["audio_path"] = tts_result.get("audio_path")
    result["srt_path"] = tts_result.get("srt_path")
    result["duration"] = tts_result.get("duration")
    print(f"[HYBRID] TTS 완료: {result['duration']:.1f}초")

    # 2. 이미지 생성 (Render API)
    print(f"\n[HYBRID] 2/3. 이미지 생성 중 (Render API)...")
    image_dir = f"outputs/history/images"
    img_result = generate_scene_images(
        episode_id=episode_id,
        prompts=image_prompts,
        output_dir=image_dir,
        style="historical",
    )

    if not img_result.get("ok") and not img_result.get("images"):
        result["error"] = f"이미지 생성 실패: {img_result.get('error')}"
        return result

    image_paths = [img["path"] for img in img_result.get("images", [])]
    result["image_paths"] = image_paths
    print(f"[HYBRID] 이미지 완료: {len(image_paths)}개")

    # 3. 영상 렌더링 (로컬 FFmpeg)
    print(f"\n[HYBRID] 3/3. 영상 렌더링 중...")
    video_path = f"outputs/history/videos/{episode_id}.mp4"

    if len(image_paths) == 1:
        render_result = render_video(
            audio_path=result["audio_path"],
            image_path=image_paths[0],
            output_path=video_path,
            srt_path=result.get("srt_path"),
        )
    else:
        render_result = render_multi_image_video(
            audio_path=result["audio_path"],
            image_paths=image_paths,
            output_path=video_path,
            srt_path=result.get("srt_path"),
        )

    if not render_result.get("ok"):
        result["error"] = f"렌더링 실패: {render_result.get('error')}"
        return result

    result["video_path"] = render_result.get("video_path")
    print(f"[HYBRID] 렌더링 완료: {result['video_path']}")

    result["ok"] = True
    return result


def generate_image_on_pc(
    prompt: str,
    output_path: str = None,
    style: str = "historical",
) -> Dict[str, Any]:
    """PC 서버에서 이미지 생성"""
    server_url, server_name = get_active_server()

    if server_name == "PC":
        try:
            response = requests.post(
                f"{server_url}/api/drama/generate-image",
                json={"prompt": prompt, "style": style},
                timeout=180,
            )
            if response.status_code == 200:
                result = response.json()
                if result.get("success") and output_path:
                    # 이미지 다운로드
                    img_url = result.get("image_url")
                    if img_url:
                        img_data = requests.get(img_url, timeout=60).content
                        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
                        with open(output_path, "wb") as f:
                            f.write(img_data)
                        return {"ok": True, "image_path": output_path}
                return result
        except Exception as e:
            print(f"[PC-CLIENT] PC 서버 실패, Render로 전환: {e}")

    # Render API로 fallback
    from .image_gen import generate_image
    return generate_image(prompt=prompt, output_path=output_path, style=style)


if __name__ == "__main__":
    # 테스트
    print(f"PC 서버 URL: {PC_SERVER_URL}")
    print(f"PC 온라인: {check_pc_online()}")

    server_url, server_name = get_active_server()
    print(f"활성 서버: {server_name} ({server_url})")
