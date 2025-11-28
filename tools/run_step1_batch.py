"""
Step1 배치 테스트
Step1 대본 생성 기능을 여러 에피소드로 테스트

Usage:
    python3 tools/run_step1_batch.py
    python3 tools/run_step1_batch.py --episodes 5
    python3 tools/run_step1_batch.py --category category2
"""

import os
import sys
import json
import argparse
import time
from datetime import datetime
from typing import Dict, Any, List, Optional

# 프로젝트 루트 경로 추가
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 테스트용 카테고리별 주제
TEST_THEMES = {
    "category1": [
        "옛날 동네 구멍가게 이야기",
        "고향 마을의 정자나무",
        "시골 외할머니 댁의 여름방학",
    ],
    "category2": [
        "1980년대 서울의 다방 문화",
        "새마을 운동과 우리 마을의 변화",
        "첫 컬러TV가 들어온 날",
    ],
    "category3": [
        "어머니의 재봉틀",
        "아버지의 손때 묻은 도시락",
        "동생에게 물려준 교복",
    ]
}


def create_step1_input(
    theme: str,
    category: str = "category1",
    length_minutes: int = 5
) -> Dict[str, Any]:
    """Step1 입력 생성"""
    return {
        "step": "step1_script_generation",
        "mode": "test",
        "category": category,
        "theme": theme,
        "length_minutes": length_minutes,
        "target_audience": "시니어 (60세 이상)",
        "emotional_tone": "nostalgic, warm, comforting"
    }


def validate_step1_output(output: Dict[str, Any]) -> Dict[str, Any]:
    """Step1 출력 검증"""
    validation = {
        "valid": True,
        "errors": [],
        "warnings": []
    }

    # 필수 필드 확인
    required_fields = ["scenes", "titles"]
    for field in required_fields:
        if field not in output:
            validation["valid"] = False
            validation["errors"].append(f"필수 필드 누락: {field}")

    # scenes 검증
    scenes = output.get("scenes", [])
    if not scenes:
        validation["valid"] = False
        validation["errors"].append("scenes가 비어있음")
    else:
        for i, scene in enumerate(scenes):
            scene_id = scene.get("id", f"scene{i+1}")

            # 필수 필드
            if not scene.get("narration"):
                validation["errors"].append(f"{scene_id}: narration 누락")
                validation["valid"] = False

            # 나레이션 길이 체크
            narration = scene.get("narration", "")
            if len(narration) < 50:
                validation["warnings"].append(f"{scene_id}: 나레이션이 너무 짧음 ({len(narration)}자)")

            # speaker_gender 체크
            gender = scene.get("speaker_gender")
            if gender not in ["male", "female"]:
                validation["warnings"].append(f"{scene_id}: speaker_gender 미지정")

    # titles 검증
    titles = output.get("titles", {})
    if not titles.get("main_title"):
        validation["warnings"].append("main_title이 없음")

    return validation


def run_single_test(
    theme: str,
    category: str,
    length_minutes: int,
    output_dir: str
) -> Dict[str, Any]:
    """단일 에피소드 테스트 실행"""
    from step1_script_generation.run_step1 import run as run_step1

    print(f"\n{'=' * 50}")
    print(f"테마: {theme}")
    print(f"카테고리: {category}, 길이: {length_minutes}분")
    print("=" * 50)

    result = {
        "theme": theme,
        "category": category,
        "success": False,
        "duration_seconds": 0,
        "validation": {},
        "error": None
    }

    step1_input = create_step1_input(theme, category, length_minutes)

    start_time = time.time()

    try:
        output = run_step1(step1_input)
        result["duration_seconds"] = round(time.time() - start_time, 2)

        # 검증
        validation = validate_step1_output(output)
        result["validation"] = validation
        result["success"] = validation["valid"]

        if validation["valid"]:
            print(f"✅ 성공! ({result['duration_seconds']}초)")
            print(f"   - 씬 수: {len(output.get('scenes', []))}")
            print(f"   - 제목: {output.get('titles', {}).get('main_title', 'N/A')}")
        else:
            print(f"❌ 검증 실패")
            for err in validation["errors"]:
                print(f"   - {err}")

        for warn in validation.get("warnings", []):
            print(f"   ⚠️ {warn}")

        # 결과 저장
        if output_dir:
            safe_theme = theme.replace(" ", "_")[:30]
            output_path = os.path.join(
                output_dir,
                f"step1_{category}_{safe_theme}_{int(time.time())}.json"
            )
            os.makedirs(output_dir, exist_ok=True)
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(output, f, ensure_ascii=False, indent=2)
            print(f"   📁 저장: {output_path}")

    except Exception as e:
        result["error"] = str(e)
        result["duration_seconds"] = round(time.time() - start_time, 2)
        print(f"❌ 오류 발생: {e}")

    return result


def run_batch_test(
    num_episodes: int = 3,
    category: str = "category1",
    length_minutes: int = 5,
    output_dir: str = "outputs/step1_batch"
) -> Dict[str, Any]:
    """배치 테스트 실행"""
    print("=" * 60)
    print("🔎 Step1 배치 테스트")
    print("=" * 60)
    print(f"테스트 에피소드 수: {num_episodes}")
    print(f"카테고리: {category}")
    print(f"목표 길이: {length_minutes}분")

    themes = TEST_THEMES.get(category, TEST_THEMES["category1"])

    # 테마 순환 사용
    test_themes = []
    for i in range(num_episodes):
        test_themes.append(themes[i % len(themes)])

    results = []
    success_count = 0
    total_duration = 0

    for i, theme in enumerate(test_themes):
        print(f"\n[{i+1}/{num_episodes}] 테스트 중...")
        result = run_single_test(theme, category, length_minutes, output_dir)
        results.append(result)

        if result["success"]:
            success_count += 1
        total_duration += result["duration_seconds"]

        # Rate limiting (API 호출 간격)
        if i < num_episodes - 1:
            print("   ⏳ 다음 테스트까지 2초 대기...")
            time.sleep(2)

    # 최종 보고서
    print("\n" + "=" * 60)
    print("📊 배치 테스트 결과")
    print("=" * 60)
    print(f"총 테스트: {num_episodes}")
    print(f"성공: {success_count}/{num_episodes} ({success_count/num_episodes*100:.0f}%)")
    print(f"총 소요 시간: {total_duration:.1f}초")
    print(f"평균 소요 시간: {total_duration/num_episodes:.1f}초/에피소드")

    if success_count == num_episodes:
        print("\n🎉 모든 테스트 통과!")
    else:
        print(f"\n⚠️ {num_episodes - success_count}개 테스트 실패")
        for i, r in enumerate(results):
            if not r["success"]:
                print(f"   - [{i+1}] {r['theme']}: {r.get('error') or r['validation'].get('errors', [])}")

    return {
        "timestamp": datetime.now().isoformat(),
        "total_tests": num_episodes,
        "success_count": success_count,
        "total_duration_seconds": total_duration,
        "results": results
    }


def check_dependencies() -> bool:
    """필요 모듈 확인"""
    try:
        from step1_script_generation.run_step1 import run as run_step1
        return True
    except ImportError as e:
        print(f"❌ Step1 모듈 임포트 실패: {e}")
        print("   step1_script_generation 디렉토리를 확인하세요.")
        return False


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Step1 배치 테스트"
    )
    parser.add_argument(
        "--episodes", "-n",
        type=int,
        default=3,
        help="테스트할 에피소드 수 (기본: 3)"
    )
    parser.add_argument(
        "--category", "-c",
        default="category1",
        choices=["category1", "category2", "category3"],
        help="카테고리 선택 (기본: category1)"
    )
    parser.add_argument(
        "--length", "-l",
        type=int,
        default=5,
        help="에피소드 길이(분) (기본: 5)"
    )
    parser.add_argument(
        "--output", "-o",
        default="outputs/step1_batch",
        help="출력 디렉토리 (기본: outputs/step1_batch)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="실제 API 호출 없이 테스트 구조만 확인"
    )

    args = parser.parse_args()

    if args.dry_run:
        print("🔍 Dry Run 모드 - 설정 확인만 수행")
        print(f"   에피소드 수: {args.episodes}")
        print(f"   카테고리: {args.category}")
        print(f"   길이: {args.length}분")
        print(f"   출력 디렉토리: {args.output}")

        themes = TEST_THEMES.get(args.category, TEST_THEMES["category1"])
        print(f"\n테스트 테마:")
        for i in range(args.episodes):
            print(f"   [{i+1}] {themes[i % len(themes)]}")

        sys.exit(0)

    # 의존성 확인
    if not check_dependencies():
        sys.exit(1)

    # 배치 테스트 실행
    report = run_batch_test(
        num_episodes=args.episodes,
        category=args.category,
        length_minutes=args.length,
        output_dir=args.output
    )

    # 보고서 저장
    report_path = os.path.join(args.output, "batch_report.json")
    os.makedirs(args.output, exist_ok=True)
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(f"\n📁 보고서 저장: {report_path}")

    sys.exit(0 if report["success_count"] == report["total_tests"] else 1)
