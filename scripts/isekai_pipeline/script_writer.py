"""
혈영 이세계편 - 대본 분할 작성 도구

12,000~15,000자 대본을 5개 씬으로 분할하여 작성합니다.
Claude 출력 한계를 우회하고 씬별 품질 검수가 가능합니다.

사용법:
1. 기획 에이전트가 씬별로 대본 작성
2. 이 모듈로 씬들을 합쳐서 최종 대본 생성
"""

import os
import json
from typing import Dict, List, Optional
from datetime import datetime

from .config import (
    SCRIPT_CONFIG,
    SERIES_INFO,
    PART_STRUCTURE,
    OUTPUT_BASE,
)

# 출력 디렉토리
SCRIPT_DIR = os.path.join(OUTPUT_BASE, "scripts")
SCENE_DIR = os.path.join(OUTPUT_BASE, "scenes")


def get_episode_brief(episode: int) -> Dict:
    """
    에피소드 기획서 조회 (fallback)

    실제 기획서는 outputs/isekai/briefs/에서 로드하거나,
    없으면 기본값 반환
    """
    # 파트 번호 계산
    part_num = (episode - 1) // 10 + 1
    part_info = PART_STRUCTURE.get(part_num, {})

    # 기획서 파일 확인
    brief_path = os.path.join(OUTPUT_BASE, "briefs", f"ep{episode:03d}_brief.json")
    if os.path.exists(brief_path):
        try:
            with open(brief_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass

    # 기본값 반환
    return {
        "episode": episode,
        "title": f"제{episode}화",
        "part": part_num,
        "part_title": part_info.get("title", ""),
        "summary": part_info.get("summary", ""),
        "key_events": part_info.get("key_events", []),
    }


def ensure_directories():
    """출력 디렉토리 생성"""
    os.makedirs(SCRIPT_DIR, exist_ok=True)
    os.makedirs(SCENE_DIR, exist_ok=True)


# =====================================================
# 씬 분할 설정
# =====================================================

SCENE_CONFIG = {
    "scenes_per_episode": 5,
    "chars_per_scene": 2800,  # 14,000 / 5 = 2,800
    "min_chars_per_scene": 2400,
    "max_chars_per_scene": 3200,
}

SCENE_STRUCTURE = {
    1: {
        "name": "오프닝",
        "purpose": "이전 화 연결 + 상황 설정",
        "ratio": 0.15,  # 약 2,100자
    },
    2: {
        "name": "전개",
        "purpose": "사건 발생 + 갈등 시작/심화",
        "ratio": 0.22,  # 약 3,100자
    },
    3: {
        "name": "클라이맥스",
        "purpose": "절정 + 전투/대결/결정적 순간",
        "ratio": 0.28,  # 약 3,900자
    },
    4: {
        "name": "해결",
        "purpose": "문제 해결 + 결과",
        "ratio": 0.20,  # 약 2,800자
    },
    5: {
        "name": "엔딩",
        "purpose": "마무리 + 다음 화 떡밥",
        "ratio": 0.15,  # 약 2,100자
    },
}


def get_scene_target_chars(scene_num: int, total_target: int = 14000) -> int:
    """씬별 목표 글자수 계산"""
    ratio = SCENE_STRUCTURE.get(scene_num, {}).get("ratio", 1/6)
    return int(total_target * ratio)


def get_scene_prompt(episode: int, scene_num: int) -> str:
    """씬별 작성 프롬프트 생성"""
    brief = get_episode_brief(episode)
    scene_info = SCENE_STRUCTURE.get(scene_num, {})
    target_chars = get_scene_target_chars(scene_num)

    return f"""## 씬 {scene_num} 작성 요청

**에피소드**: {episode}화 - {brief.get('title', '')}
**씬 이름**: {scene_info.get('name', f'씬 {scene_num}')}
**씬 목적**: {scene_info.get('purpose', '')}
**목표 글자수**: {target_chars}자 (±300자)

### 에피소드 기획서
{json.dumps(brief, ensure_ascii=False, indent=2)}

### 이전 씬 요약
(이전 씬 내용을 여기에 제공)

### 작성 지침
1. 소설체로 작성 (대사 35%, 서술 65%)
2. 태그 없이 순수 텍스트로 작성
3. 문단 구분은 빈 줄 하나로
4. 씬 끝에 자연스러운 연결부 작성
"""


# =====================================================
# 씬 저장/로드
# =====================================================

def save_scene(episode: int, scene_num: int, content: str) -> str:
    """개별 씬 저장"""
    ensure_directories()

    scene_path = os.path.join(SCENE_DIR, f"EP{episode:03d}", f"scene_{scene_num:02d}.txt")
    os.makedirs(os.path.dirname(scene_path), exist_ok=True)

    try:
        with open(scene_path, "w", encoding="utf-8") as f:
            f.write(content)

        # 메타데이터 저장
        meta_path = scene_path.replace(".txt", "_meta.json")
        meta = {
            "episode": episode,
            "scene_num": scene_num,
            "char_count": len(content),
            "target_chars": get_scene_target_chars(scene_num),
            "created_at": datetime.now().isoformat(),
        }
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(meta, f, ensure_ascii=False, indent=2)

        return scene_path

    except Exception as e:
        raise IOError(f"씬 저장 실패 (EP{episode:03d}, 씬 {scene_num}): {e}")


def load_scene(episode: int, scene_num: int) -> Optional[str]:
    """개별 씬 로드"""
    scene_path = os.path.join(SCENE_DIR, f"EP{episode:03d}", f"scene_{scene_num:02d}.txt")

    if not os.path.exists(scene_path):
        return None

    try:
        with open(scene_path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        print(f"[WARNING] 씬 로드 실패 (EP{episode:03d}, 씬 {scene_num}): {e}")
        return None


def get_scene_status(episode: int) -> Dict[int, Dict]:
    """에피소드의 씬 작성 상태 조회"""
    status = {}
    num_scenes = SCENE_CONFIG.get("scenes_per_episode", 6)

    for scene_num in range(1, num_scenes + 1):
        scene_path = os.path.join(SCENE_DIR, f"EP{episode:03d}", f"scene_{scene_num:02d}.txt")
        meta_path = scene_path.replace(".txt", "_meta.json")

        if os.path.exists(scene_path):
            content = load_scene(episode, scene_num)
            char_count = len(content) if content else 0

            meta = {}
            if os.path.exists(meta_path):
                try:
                    with open(meta_path, "r", encoding="utf-8") as f:
                        meta = json.load(f)
                except Exception as e:
                    print(f"[WARNING] 메타데이터 로드 실패: {e}")
                    meta = {}

            status[scene_num] = {
                "exists": True,
                "char_count": char_count,
                "target_chars": get_scene_target_chars(scene_num),
                "progress": f"{char_count}/{get_scene_target_chars(scene_num)}",
                "created_at": meta.get("created_at"),
            }
        else:
            status[scene_num] = {
                "exists": False,
                "char_count": 0,
                "target_chars": get_scene_target_chars(scene_num),
                "progress": f"0/{get_scene_target_chars(scene_num)}",
            }

    return status


# =====================================================
# 씬 합치기 → 최종 대본
# =====================================================

def merge_scenes(episode: int) -> Dict:
    """모든 씬을 합쳐서 최종 대본 생성"""
    ensure_directories()

    scenes = []
    total_chars = 0
    missing_scenes = []
    num_scenes = SCENE_CONFIG.get("scenes_per_episode", 6)

    for scene_num in range(1, num_scenes + 1):
        content = load_scene(episode, scene_num)
        if content:
            scenes.append(content)
            total_chars += len(content)
        else:
            missing_scenes.append(scene_num)

    if missing_scenes:
        return {
            "ok": False,
            "error": f"누락된 씬: {missing_scenes}",
            "missing_scenes": missing_scenes,
        }

    # 씬 합치기 (빈 줄 2개로 구분)
    full_script = "\n\n\n".join(scenes)

    # 최종 대본 저장
    brief = get_episode_brief(episode)
    title = brief.get("title", f"제{episode}화")
    # 파일명에서 특수문자 제거
    safe_title = "".join(c for c in title if c.isalnum() or c in (' ', '_', '-')).strip()
    script_path = os.path.join(SCRIPT_DIR, f"EP{episode:03d}_{safe_title}.txt")

    try:
        with open(script_path, "w", encoding="utf-8") as f:
            f.write(full_script)
    except Exception as e:
        return {
            "ok": False,
            "error": f"대본 저장 실패: {e}",
        }

    return {
        "ok": True,
        "script_path": script_path,
        "total_chars": total_chars,
        "target_chars": SCRIPT_CONFIG["target_chars"],
        "scene_count": len(scenes),
    }


# =====================================================
# 진행 상황 출력
# =====================================================

def print_episode_progress(episode: int) -> str:
    """에피소드 작성 진행 상황 출력"""
    status = get_scene_status(episode)
    brief = get_episode_brief(episode)

    lines = [
        f"## EP{episode:03d} - {brief.get('title', '')} 작성 현황",
        "",
        "| 씬 | 이름 | 목표 | 현재 | 상태 |",
        "|:--:|------|-----:|-----:|:----:|",
    ]

    total_current = 0
    total_target = 0
    completed = 0
    num_scenes = SCENE_CONFIG.get("scenes_per_episode", 6)

    for scene_num in range(1, num_scenes + 1):
        info = status.get(scene_num, {})
        scene_info = SCENE_STRUCTURE.get(scene_num, {})

        current = info.get("char_count", 0)
        target = info.get("target_chars", 0)

        total_current += current
        total_target += target

        if info.get("exists"):
            completed += 1
            status_emoji = "✅" if current >= target * 0.9 else "⚠️"
        else:
            status_emoji = "❌"

        lines.append(
            f"| {scene_num} | {scene_info.get('name', '')} | "
            f"{target:,}자 | {current:,}자 | {status_emoji} |"
        )

    lines.extend([
        "",
        f"**전체 진행률**: {completed}/{num_scenes} 씬 완료",
        f"**글자수**: {total_current:,} / {total_target:,}자 ({total_current/total_target*100:.1f}%)" if total_target > 0 else "**글자수**: 0자",
    ])

    if completed == num_scenes:
        lines.append("\n✅ **모든 씬 작성 완료! `merge_scenes()`로 합치세요.**")
    else:
        next_scene = min([s for s in range(1, num_scenes + 1) if not status.get(s, {}).get("exists")], default=None)
        if next_scene:
            lines.append(f"\n➡️ **다음 작성할 씬**: 씬 {next_scene} ({SCENE_STRUCTURE[next_scene]['name']})")

    return "\n".join(lines)


# =====================================================
# 워크플로우 헬퍼
# =====================================================

def start_episode(episode: int) -> str:
    """에피소드 작성 시작 - 첫 번째 씬 프롬프트 반환"""
    ensure_directories()

    # 씬 디렉토리 생성
    os.makedirs(os.path.join(SCENE_DIR, f"EP{episode:03d}"), exist_ok=True)

    progress = print_episode_progress(episode)
    prompt = get_scene_prompt(episode, 1)

    return f"{progress}\n\n---\n\n{prompt}"


def continue_episode(episode: int) -> str:
    """에피소드 계속 작성 - 다음 씬 프롬프트 반환"""
    status = get_scene_status(episode)
    num_scenes = SCENE_CONFIG.get("scenes_per_episode", 6)

    # 다음 미완성 씬 찾기
    next_scene = None
    for scene_num in range(1, num_scenes + 1):
        if not status.get(scene_num, {}).get("exists"):
            next_scene = scene_num
            break

    if next_scene is None:
        return f"✅ EP{episode:03d} 모든 씬 작성 완료!\n\n`merge_scenes({episode})`를 실행하세요."

    # 이전 씬 요약 수집
    prev_scenes_summary = []
    for s in range(1, next_scene):
        content = load_scene(episode, s)
        if content:
            # 마지막 500자만 요약으로 제공
            prev_scenes_summary.append(f"[씬 {s} 끝부분]\n{content[-500:]}")

    progress = print_episode_progress(episode)
    prompt = get_scene_prompt(episode, next_scene)

    prev_context = "\n\n---\n\n".join(prev_scenes_summary) if prev_scenes_summary else "(첫 번째 씬)"

    return f"{progress}\n\n---\n\n{prompt}\n\n### 이전 씬 맥락\n{prev_context}"
