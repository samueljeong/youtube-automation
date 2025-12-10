#!/usr/bin/env python3
"""
Freesound API를 사용해 BGM/SFX 다운로드
"""

import os
import requests
import time

API_KEY = "xuttzpvpcpbcXZTxGj75GXd6lnzn16SlADMhlP9f"
BASE_URL = "https://freesound.org/apiv2"

# 다운로드할 오디오 정의
# 검색어, 최소 길이(초), 최대 길이(초)
BGM_QUERIES = {
    "epic": ("epic cinematic orchestral", 30, 180),
    "romantic": ("romantic piano love", 30, 180),
    "comedic": ("funny comedy playful", 30, 180),
    "horror": ("horror scary dark ambient", 30, 180),
    "upbeat": ("upbeat happy energetic", 30, 180),
}

SFX_QUERIES = {
    "notification": ("notification alert ding", 0.5, 5),
    "heartbeat": ("heartbeat heart beat", 1, 10),
    "clock_tick": ("clock tick ticking", 1, 10),
    "applause": ("applause clapping crowd", 1, 10),
    "gasp": ("gasp surprise shock", 0.5, 5),
    "typing": ("typing keyboard", 1, 10),
    "door": ("door open close creak", 0.5, 5),
}


def search_sounds(query, min_duration=0, max_duration=300, num_results=4):
    """Freesound에서 소리 검색"""
    params = {
        "query": query,
        "token": API_KEY,
        "fields": "id,name,duration,previews,license",
        "filter": f"duration:[{min_duration} TO {max_duration}]",
        "sort": "score",
        "page_size": num_results * 2,  # 여유있게 검색
    }

    try:
        response = requests.get(f"{BASE_URL}/search/text/", params=params, timeout=30)
        response.raise_for_status()
        data = response.json()
        return data.get("results", [])[:num_results]
    except Exception as e:
        print(f"  ⚠️ 검색 실패: {e}")
        return []


def download_preview(sound, output_path):
    """사운드 프리뷰(MP3) 다운로드"""
    try:
        # HQ MP3 프리뷰 URL 가져오기
        preview_url = sound.get("previews", {}).get("preview-hq-mp3")
        if not preview_url:
            preview_url = sound.get("previews", {}).get("preview-lq-mp3")

        if not preview_url:
            print(f"  ⚠️ 프리뷰 URL 없음: {sound.get('name')}")
            return False

        response = requests.get(preview_url, timeout=60)
        response.raise_for_status()

        with open(output_path, "wb") as f:
            f.write(response.content)

        return True
    except Exception as e:
        print(f"  ⚠️ 다운로드 실패: {e}")
        return False


def download_category(queries, output_dir, category_name):
    """카테고리별 다운로드 (BGM 또는 SFX)"""
    print(f"\n{'='*50}")
    print(f"📥 {category_name} 다운로드 시작")
    print(f"{'='*50}")

    os.makedirs(output_dir, exist_ok=True)

    for sound_type, (query, min_dur, max_dur) in queries.items():
        print(f"\n🔍 [{sound_type}] 검색 중: '{query}'")

        sounds = search_sounds(query, min_dur, max_dur, num_results=4)

        if not sounds:
            print(f"  ❌ 검색 결과 없음")
            continue

        print(f"  ✅ {len(sounds)}개 발견")

        for i, sound in enumerate(sounds, 1):
            filename = f"{sound_type}_{i:02d}.mp3"
            output_path = os.path.join(output_dir, filename)

            # 기존 파일 백업 (필요시)
            if os.path.exists(output_path):
                backup_path = output_path + ".backup"
                os.rename(output_path, backup_path)

            print(f"  📦 다운로드 중: {filename} ({sound.get('name')[:30]}...)")

            if download_preview(sound, output_path):
                print(f"     ✓ 완료 ({sound.get('duration', 0):.1f}초)")
            else:
                # 실패 시 백업 복원
                backup_path = output_path + ".backup"
                if os.path.exists(backup_path):
                    os.rename(backup_path, output_path)

            # Rate limit 방지
            time.sleep(0.5)

        # 쿼리 간 딜레이
        time.sleep(1)


def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    base_dir = os.path.dirname(script_dir)

    bgm_dir = os.path.join(base_dir, "static", "audio", "bgm")
    sfx_dir = os.path.join(base_dir, "static", "audio", "sfx")

    print("🎵 Freesound BGM/SFX 다운로더")
    print(f"   BGM 저장 경로: {bgm_dir}")
    print(f"   SFX 저장 경로: {sfx_dir}")

    # API 키 테스트
    print("\n🔑 API 키 테스트 중...")
    test_result = search_sounds("test", 0, 10, 1)
    if test_result:
        print("   ✅ API 키 유효함")
    else:
        print("   ❌ API 키 확인 필요")
        return

    # BGM 다운로드
    download_category(BGM_QUERIES, bgm_dir, "BGM (배경음악)")

    # SFX 다운로드
    download_category(SFX_QUERIES, sfx_dir, "SFX (효과음)")

    print("\n" + "="*50)
    print("✅ 다운로드 완료!")
    print("="*50)


if __name__ == "__main__":
    main()
