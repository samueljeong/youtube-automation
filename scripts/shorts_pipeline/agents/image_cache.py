"""
ImageCache - 이미지 프롬프트 캐시 시스템

역할:
- 성공한 프롬프트 저장 및 재사용
- 이슈 타입별 템플릿 관리
- 유사 프롬프트 매칭
- 실패 프롬프트 블랙리스트
"""

import os
import json
import hashlib
from typing import Any, Dict, List, Optional
from datetime import datetime


# 캐시 파일 경로
CACHE_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "image_cache")
PROMPT_CACHE_FILE = os.path.join(CACHE_DIR, "prompt_cache.json")
BLACKLIST_FILE = os.path.join(CACHE_DIR, "blacklist.json")


# 이슈 타입별 기본 배경 템플릿
BACKGROUND_TEMPLATES = {
    "논란": {
        "scene_2": "Korean news studio background, serious atmosphere, red and blue lighting, breaking news style, 4K, no people",
        "scene_3": "Press conference room, multiple microphones, camera flashes, dramatic lighting, 4K, no people",
        "scene_4": "Social media comments visualization, smartphone screen, negative reactions, dark mood, 4K",
        "scene_5": "Question mark silhouette, uncertain future, fog, dramatic lighting, 4K",
    },
    "열애": {
        "scene_2": "Romantic sunset cityscape, Seoul skyline, warm colors, dreamy atmosphere, 4K, no people",
        "scene_3": "Paparazzi camera flash effect, night street, dramatic lighting, 4K, no people",
        "scene_4": "Social media hearts and comments, pink theme, celebration mood, 4K",
        "scene_5": "Two silhouettes walking together, sunset, romantic, 4K",
    },
    "컴백": {
        "scene_2": "Concert stage with dramatic lighting, empty stage, anticipation, 4K, no people",
        "scene_3": "Album cover style background, neon lights, K-pop aesthetic, 4K",
        "scene_4": "Fans celebration, lightsticks, concert atmosphere, 4K, no faces",
        "scene_5": "Stage spotlight, triumphant return, epic atmosphere, 4K",
    },
    "성과": {
        "scene_2": "Award ceremony stage, golden lighting, trophy display, 4K, no people",
        "scene_3": "Red carpet background, camera flashes, glamorous, 4K, no people",
        "scene_4": "Celebration confetti, golden theme, victory atmosphere, 4K",
        "scene_5": "Champion podium, spotlight, glory moment, 4K",
    },
    "사건": {
        "scene_2": "Dark news studio, urgent atmosphere, red alert theme, 4K, no people",
        "scene_3": "Investigation room style, documents scattered, mysterious, 4K, no people",
        "scene_4": "Breaking news graphics, urgent updates, tense mood, 4K",
        "scene_5": "Gavel and scales of justice, legal theme, serious, 4K",
    },
    "근황": {
        "scene_2": "Casual cafe interior, warm lighting, relaxed atmosphere, 4K, no people",
        "scene_3": "Instagram style photo frame, lifestyle aesthetic, 4K",
        "scene_4": "Daily life montage style, warm colors, comfortable mood, 4K",
        "scene_5": "Sunset silhouette, peaceful ending, hopeful, 4K",
    },
    "default": {
        "scene_2": "Korean entertainment news background, professional, clean, 4K, no people",
        "scene_3": "Dynamic abstract background, colorful, modern, 4K",
        "scene_4": "Social media reaction visualization, trendy, 4K",
        "scene_5": "Dramatic sky, question or conclusion mood, 4K",
    },
}


class ImageCache:
    """이미지 프롬프트 캐시 관리자"""

    def __init__(self):
        self._ensure_cache_dir()
        self.prompt_cache = self._load_cache()
        self.blacklist = self._load_blacklist()

    def _ensure_cache_dir(self):
        """캐시 디렉토리 생성"""
        os.makedirs(CACHE_DIR, exist_ok=True)

    def _load_cache(self) -> Dict[str, Any]:
        """캐시 로드"""
        if os.path.exists(PROMPT_CACHE_FILE):
            try:
                with open(PROMPT_CACHE_FILE, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                pass
        return {"prompts": {}, "stats": {"hits": 0, "misses": 0}}

    def _save_cache(self):
        """캐시 저장"""
        with open(PROMPT_CACHE_FILE, 'w', encoding='utf-8') as f:
            json.dump(self.prompt_cache, f, ensure_ascii=False, indent=2)

    def _load_blacklist(self) -> List[str]:
        """블랙리스트 로드"""
        if os.path.exists(BLACKLIST_FILE):
            try:
                with open(BLACKLIST_FILE, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                pass
        return []

    def _save_blacklist(self):
        """블랙리스트 저장"""
        with open(BLACKLIST_FILE, 'w', encoding='utf-8') as f:
            json.dump(self.blacklist, f, ensure_ascii=False, indent=2)

    def _hash_prompt(self, prompt: str) -> str:
        """프롬프트 해시 생성"""
        # 핵심 키워드만 추출해서 해시
        normalized = prompt.lower().strip()
        return hashlib.md5(normalized.encode()).hexdigest()[:12]

    def get_template(self, issue_type: str, scene_number: int) -> Optional[str]:
        """이슈 타입별 템플릿 반환"""
        templates = BACKGROUND_TEMPLATES.get(issue_type, BACKGROUND_TEMPLATES["default"])
        scene_key = f"scene_{scene_number}"
        return templates.get(scene_key)

    def get_cached_prompt(self, issue_type: str, scene_number: int, keywords: List[str] = None) -> Optional[Dict]:
        """캐시된 프롬프트 찾기"""
        cache_key = f"{issue_type}_scene{scene_number}"

        if cache_key in self.prompt_cache["prompts"]:
            cached = self.prompt_cache["prompts"][cache_key]
            self.prompt_cache["stats"]["hits"] += 1
            self._save_cache()
            return {
                "prompt": cached["prompt"],
                "image_path": cached.get("image_path"),
                "from_cache": True,
            }

        self.prompt_cache["stats"]["misses"] += 1
        return None

    def save_successful_prompt(
        self,
        issue_type: str,
        scene_number: int,
        prompt: str,
        image_path: str = None
    ):
        """성공한 프롬프트 저장"""
        cache_key = f"{issue_type}_scene{scene_number}"

        self.prompt_cache["prompts"][cache_key] = {
            "prompt": prompt,
            "image_path": image_path,
            "success_count": self.prompt_cache["prompts"].get(cache_key, {}).get("success_count", 0) + 1,
            "last_used": datetime.now().isoformat(),
        }
        self._save_cache()

    def add_to_blacklist(self, prompt: str, reason: str = ""):
        """실패 프롬프트 블랙리스트 추가"""
        prompt_hash = self._hash_prompt(prompt)
        if prompt_hash not in self.blacklist:
            self.blacklist.append({
                "hash": prompt_hash,
                "prompt_preview": prompt[:100],
                "reason": reason,
                "added_at": datetime.now().isoformat(),
            })
            self._save_blacklist()

    def is_blacklisted(self, prompt: str) -> bool:
        """블랙리스트 확인"""
        prompt_hash = self._hash_prompt(prompt)
        return any(item.get("hash") == prompt_hash for item in self.blacklist if isinstance(item, dict))

    def get_optimized_prompts(self, scenes: List[Dict], issue_type: str) -> List[Dict]:
        """
        씬 목록에 대해 최적화된 프롬프트 반환

        - 씬1 (훅): 항상 새로 생성 (인물별 실루엣)
        - 씬2-4: 템플릿 또는 캐시 사용
        - 씬5: 템플릿 또는 캐시 사용

        Returns:
            [
                {"scene": 1, "prompt": "...", "use_cache": False, "generate": True},
                {"scene": 2, "prompt": "...", "use_cache": True, "generate": False},
                ...
            ]
        """
        optimized = []

        for scene in scenes:
            scene_num = scene.get("scene_number", 1)
            original_prompt = scene.get("image_prompt_enhanced", scene.get("image_prompt", ""))

            if scene_num == 1:
                # 씬1은 항상 새로 생성 (인물 실루엣)
                optimized.append({
                    "scene": scene_num,
                    "prompt": original_prompt,
                    "use_cache": False,
                    "generate": True,
                    "reason": "훅 씬은 인물별로 생성 필요",
                })
            else:
                # 캐시 확인
                cached = self.get_cached_prompt(issue_type, scene_num)
                if cached and cached.get("image_path") and os.path.exists(cached["image_path"]):
                    # 캐시 히트 + 이미지 존재
                    optimized.append({
                        "scene": scene_num,
                        "prompt": cached["prompt"],
                        "image_path": cached["image_path"],
                        "use_cache": True,
                        "generate": False,
                        "reason": "캐시 히트",
                    })
                else:
                    # 템플릿 사용
                    template = self.get_template(issue_type, scene_num)
                    if template:
                        optimized.append({
                            "scene": scene_num,
                            "prompt": template,
                            "use_cache": False,
                            "generate": True,
                            "reason": f"템플릿 사용 ({issue_type})",
                        })
                    else:
                        # 원본 프롬프트 사용
                        optimized.append({
                            "scene": scene_num,
                            "prompt": original_prompt,
                            "use_cache": False,
                            "generate": True,
                            "reason": "원본 프롬프트",
                        })

        return optimized

    def get_stats(self) -> Dict[str, Any]:
        """캐시 통계"""
        stats = self.prompt_cache.get("stats", {"hits": 0, "misses": 0})
        total = stats["hits"] + stats["misses"]
        hit_rate = (stats["hits"] / total * 100) if total > 0 else 0

        return {
            "hits": stats["hits"],
            "misses": stats["misses"],
            "hit_rate": f"{hit_rate:.1f}%",
            "cached_prompts": len(self.prompt_cache.get("prompts", {})),
            "blacklisted": len(self.blacklist),
        }


# 싱글톤 인스턴스
_cache_instance = None


def get_image_cache() -> ImageCache:
    """ImageCache 싱글톤 반환"""
    global _cache_instance
    if _cache_instance is None:
        _cache_instance = ImageCache()
    return _cache_instance
