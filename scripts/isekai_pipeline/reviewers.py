"""
혈영 이세계편 - 리뷰 에이전트 모듈

대본 작성 후 자동으로 검증 실행:
1. FORM_CHECKER: 규칙 기반 형식 검증 (문장 길이, 줄바꿈, 대사 비율)
2. VOICE_CHECKER: 체크리스트 제공 (Claude가 대화에서 직접 검토)
3. FEEL_CHECKER: 체크리스트 제공 (Claude가 대화에서 직접 검토)

형식 검증만 코드로 자동화, 내용 검증은 Claude가 수행
"""

import os
import json
import re
from typing import Dict, Any, Optional, List, Tuple
from pathlib import Path

# 프로젝트 경로
_module_dir = os.path.dirname(os.path.abspath(__file__))
_project_root = os.path.dirname(os.path.dirname(_module_dir))
_docs_dir = os.path.join(_module_dir, "docs")


def _load_series_bible() -> str:
    """Series Bible 로드"""
    bible_path = os.path.join(_docs_dir, "series_bible.md")
    if os.path.exists(bible_path):
        with open(bible_path, "r", encoding="utf-8") as f:
            return f.read()
    return ""


# =====================================================
# FORM_CHECKER - 규칙 기반 형식 검증 (자동화)
# =====================================================

def run_form_checker(script: str, episode: str = "EP001") -> Dict[str, Any]:
    """
    FORM_CHECKER 실행 - 규칙 기반 형식 검증

    검증 항목:
    - 총 글자수
    - 평균 문장 길이
    - 35자 초과 문장
    - 대사 비율
    - 빈 줄 비율 (여백)
    """
    lines = script.split('\n')
    total_chars = len(script)
    total_lines = len(lines)

    # 문장 추출 (마침표, 물음표, 느낌표로 분리)
    # 생략 부호(..., ..)를 임시 토큰으로 치환하여 과도 분리 방지
    script_cleaned = re.sub(r'\.{2,}', '<ELLIPSIS>', script)
    sentences = re.split(r'[.?!。？！]\s*', script_cleaned)
    # 원복 및 정리
    sentences = [s.replace('<ELLIPSIS>', '...').strip() for s in sentences if s.strip()]

    # 문장 길이 분석
    sentence_lengths = [len(s) for s in sentences]
    avg_sentence_length = sum(sentence_lengths) / len(sentence_lengths) if sentence_lengths else 0

    # 35자 초과 문장
    over_35_chars = []
    for i, s in enumerate(sentences):
        if len(s) > 35:
            over_35_chars.append({
                "index": i + 1,
                "length": len(s),
                "text": s[:50] + "..." if len(s) > 50 else s
            })

    # 대사 비율 (따옴표로 둘러싸인 텍스트)
    dialogue_pattern = r'["\']([^"\']+)["\']|「([^」]+)」|"([^"]+)"'
    dialogues = re.findall(dialogue_pattern, script)
    dialogue_chars = sum(len(''.join(d)) for d in dialogues)
    dialogue_ratio = dialogue_chars / total_chars if total_chars > 0 else 0

    # 빈 줄 비율 (여백)
    empty_lines = sum(1 for line in lines if not line.strip())
    empty_ratio = empty_lines / total_lines if total_lines > 0 else 0

    # 점수 계산
    # 1. 문장 길이 점수 (30점 만점)
    if avg_sentence_length <= 15:
        sentence_score = 30
    elif avg_sentence_length <= 20:
        sentence_score = 25
    elif avg_sentence_length <= 25:
        sentence_score = 20
    elif avg_sentence_length <= 30:
        sentence_score = 15
    else:
        sentence_score = 10

    # 2. 35자 초과 문장 점수 (20점 만점)
    over_count = len(over_35_chars)
    if over_count == 0:
        over_35_score = 20
    elif over_count <= 10:
        over_35_score = 15
    elif over_count <= 30:
        over_35_score = 10
    else:
        over_35_score = 5

    # 3. 대사 비율 점수 (25점 만점)
    if 0.45 <= dialogue_ratio <= 0.55:
        dialogue_score = 25
    elif 0.40 <= dialogue_ratio <= 0.60:
        dialogue_score = 20
    elif 0.35 <= dialogue_ratio <= 0.65:
        dialogue_score = 15
    else:
        dialogue_score = 10

    # 4. 여백 점수 (25점 만점) - 빈 줄이 15~25%가 이상적
    if 0.15 <= empty_ratio <= 0.25:
        whitespace_score = 25
    elif 0.10 <= empty_ratio <= 0.30:
        whitespace_score = 20
    elif 0.05 <= empty_ratio <= 0.35:
        whitespace_score = 15
    else:
        whitespace_score = 10

    total_score = sentence_score + over_35_score + dialogue_score + whitespace_score

    # 판정
    if total_score >= 80:
        verdict = "PASS"
    elif total_score >= 60:
        verdict = "REVISE"
    else:
        verdict = "REWRITE"

    # 수정 우선순위
    fix_priority = []
    if sentence_score < 25:
        fix_priority.append(f"평균 문장 길이 줄이기 (현재: {avg_sentence_length:.1f}자 → 목표: 15~20자)")
    if over_35_score < 15:
        fix_priority.append(f"35자 초과 문장 분리 ({len(over_35_chars)}개)")
    if dialogue_score < 20:
        fix_priority.append(f"대사 비율 조정 (현재: {dialogue_ratio*100:.1f}% → 목표: 45~55%)")
    if whitespace_score < 20:
        fix_priority.append(f"여백 추가 (현재: {empty_ratio*100:.1f}% → 목표: 15~25%)")

    return {
        "checker": "FORM_CHECKER",
        "episode": episode,
        "score": total_score,
        "statistics": {
            "total_chars": total_chars,
            "total_lines": total_lines,
            "total_sentences": len(sentences),
            "avg_sentence_length": round(avg_sentence_length, 1),
            "dialogue_ratio": round(dialogue_ratio, 3),
            "empty_ratio": round(empty_ratio, 3),
        },
        "violations": {
            "over_35_chars": over_35_chars[:10],  # 상위 10개만
            "over_35_count": len(over_35_chars),
        },
        "scores": {
            "sentence_length": sentence_score,
            "over_35": over_35_score,
            "dialogue_ratio": dialogue_score,
            "whitespace": whitespace_score,
        },
        "verdict": verdict,
        "fix_priority": fix_priority,
    }


# =====================================================
# VOICE_CHECKER - 체크리스트 제공 (Claude가 검토)
# =====================================================

VOICE_CHECKLIST = """
## VOICE_CHECKER 체크리스트

캐릭터별 말투 검증 항목:

### 무영 (주인공)
- [ ] 과묵, 짧은 문장 사용
- [ ] 대사: "...", "시끄럽다.", "상관없어." 스타일
- [ ] 내면 독백: "'...뭐야 이건.'", "'하...' 한숨이 나왔다." 스타일
- [ ] 금지: 장문 대사, 감정 설명, 친절한 말투

### 혈마 (빌런)
- [ ] 오만, 위압적, 광기
- [ ] 대사: "끈질기군.", "하찮은 것." 스타일
- [ ] 금지: 친근한 말투

### 카이든 (조력자)
- [ ] 밝음, 우직, 약간 덜렁
- [ ] 대사: "야, 무!", "걱정 마!" 스타일

### 공통
- [ ] 각 캐릭터가 설정에 맞는 말투 사용
- [ ] 대사가 캐릭터 성격과 일치
- [ ] 내면 독백이 캐릭터 시점에서 자연스러움
"""


def run_voice_checker(script: str, episode: str = "EP001") -> Dict[str, Any]:
    """
    VOICE_CHECKER 실행 - 체크리스트 제공

    Claude가 대화에서 직접 검토할 체크리스트 반환
    """
    # 캐릭터 이름 등장 횟수 확인
    characters = {
        "무영": len(re.findall(r'무영', script)),
        "혈마": len(re.findall(r'혈마', script)),
        "카이든": len(re.findall(r'카이든', script)),
        "에이라": len(re.findall(r'에이라', script)),
        "볼드릭": len(re.findall(r'볼드릭', script)),
    }

    # 대사 추출 (따옴표 내)
    dialogue_pattern = r'["\']([^"\']+)["\']|「([^」]+)」|"([^"]+)"'
    dialogues = re.findall(dialogue_pattern, script)
    dialogue_count = len(dialogues)

    return {
        "checker": "VOICE_CHECKER",
        "episode": episode,
        "type": "checklist",
        "message": "Claude가 대화에서 직접 검토 필요",
        "character_mentions": characters,
        "dialogue_count": dialogue_count,
        "checklist": VOICE_CHECKLIST,
        "verdict": "REVIEW_NEEDED",
    }


# =====================================================
# FEEL_CHECKER - 체크리스트 제공 (Claude가 검토)
# =====================================================

FEEL_CHECKLIST = """
## FEEL_CHECKER 체크리스트

웹소설체 느낌 검증 항목:

### 1. 여백이 생명
- [ ] 임팩트 있는 문장은 단독 줄 사용
- [ ] 빈 줄로 호흡 조절
- [ ] 문단이 너무 밀집되지 않음

### 2. 보여주기 vs 말하기
- [ ] "~했다"보다 행동/감각 묘사 사용
- [ ] ❌ "무영은 분노했다" → ✅ "이를 악물었다. 손에 핏줄이 섰다."
- [ ] 감정 설명 최소화

### 3. 짧고 강한 문장
- [ ] 평균 문장 15~20자
- [ ] 긴 문장은 분리
- [ ] 리듬감 있는 문장 배치

### 4. 클리프행어
- [ ] 에피소드 끝에 긴장감/궁금증 유발
- [ ] 다음 화 클릭 욕구 자극

### 5. 몰입 방해 요소
- [ ] 작가 개입 없음
- [ ] 설명조 지양
- [ ] 시점 일관성 유지
"""


def run_feel_checker(script: str, episode: str = "EP001") -> Dict[str, Any]:
    """
    FEEL_CHECKER 실행 - 체크리스트 제공

    Claude가 대화에서 직접 검토할 체크리스트 반환
    """
    lines = script.split('\n')

    # 기본 통계
    empty_lines = sum(1 for line in lines if not line.strip())
    empty_ratio = empty_lines / len(lines) if lines else 0

    # 마지막 50줄 (클리프행어 확인용)
    last_lines = '\n'.join(lines[-50:]) if len(lines) >= 50 else script

    return {
        "checker": "FEEL_CHECKER",
        "episode": episode,
        "type": "checklist",
        "message": "Claude가 대화에서 직접 검토 필요",
        "statistics": {
            "total_lines": len(lines),
            "empty_lines": empty_lines,
            "empty_ratio": round(empty_ratio, 3),
        },
        "last_50_lines": last_lines,
        "checklist": FEEL_CHECKLIST,
        "verdict": "REVIEW_NEEDED",
    }


# =====================================================
# 통합 리뷰 함수
# =====================================================

def auto_review_script(
    script: str,
    episode: str = "EP001",
    save_results: bool = True,
    output_dir: Optional[str] = None,
) -> Dict[str, Any]:
    """
    대본에 대해 자동 검증 + 체크리스트 생성

    - FORM_CHECKER: 규칙 기반 자동 검증 (점수 산출)
    - VOICE_CHECKER: 체크리스트 제공 (Claude가 검토)
    - FEEL_CHECKER: 체크리스트 제공 (Claude가 검토)

    Returns:
        {
            "episode": "EP001",
            "form_check": {...},  # 자동 검증 결과
            "voice_checklist": {...},  # 체크리스트
            "feel_checklist": {...},  # 체크리스트
            "form_score": 75,
            "form_verdict": "PASS" | "REVISE" | "REWRITE",
            "needs_manual_review": True  # Claude 검토 필요 여부
        }
    """
    print(f"\n{'='*60}")
    print(f"[REVIEW] {episode} 대본 검증 시작")
    print(f"{'='*60}\n")

    results = {
        "episode": episode,
    }

    # 1. FORM_CHECKER (자동 검증)
    print("[1/3] FORM_CHECKER 실행 중 (자동 검증)...")
    form_result = run_form_checker(script, episode)
    results["form_check"] = form_result
    results["form_score"] = form_result["score"]
    results["form_verdict"] = form_result["verdict"]

    print(f"      → 점수: {form_result['score']}점 ({form_result['verdict']})")
    print(f"      → 평균 문장 길이: {form_result['statistics']['avg_sentence_length']}자")
    print(f"      → 35자 초과: {form_result['violations']['over_35_count']}개")
    print(f"      → 대사 비율: {form_result['statistics']['dialogue_ratio']*100:.1f}%")
    print(f"      → 여백 비율: {form_result['statistics']['empty_ratio']*100:.1f}%")

    # 2. VOICE_CHECKER (체크리스트)
    print("\n[2/3] VOICE_CHECKER 체크리스트 생성...")
    voice_result = run_voice_checker(script, episode)
    results["voice_checklist"] = voice_result
    print(f"      → 캐릭터 등장: {voice_result['character_mentions']}")
    print(f"      → 대사 수: {voice_result['dialogue_count']}개")
    print("      ⚠️  Claude가 대화에서 직접 검토 필요")

    # 3. FEEL_CHECKER (체크리스트)
    print("\n[3/3] FEEL_CHECKER 체크리스트 생성...")
    feel_result = run_feel_checker(script, episode)
    results["feel_checklist"] = feel_result
    print(f"      → 여백 비율: {feel_result['statistics']['empty_ratio']*100:.1f}%")
    print("      ⚠️  Claude가 대화에서 직접 검토 필요")

    # Claude 검토 필요 여부
    results["needs_manual_review"] = True  # VOICE, FEEL은 항상 수동 검토

    # 결과 출력
    print(f"\n{'='*60}")
    print(f"[REVIEW] {episode} 검증 완료")
    print(f"{'='*60}")
    print(f"  FORM (자동):  {form_result['score']}점 - {form_result['verdict']}")
    print(f"  VOICE (수동): Claude 검토 필요")
    print(f"  FEEL (수동):  Claude 검토 필요")

    if form_result["verdict"] != "PASS":
        print(f"\n[FORM 수정 필요 사항]")
        for i, p in enumerate(form_result.get("fix_priority", [])[:5], 1):
            print(f"  {i}. {p}")

    print(f"\n[다음 단계]")
    print("  Claude가 VOICE_CHECKLIST와 FEEL_CHECKLIST를 검토하고")
    print("  체크리스트 항목을 확인해야 합니다.")
    print(f"{'='*60}\n")

    # 결과 저장
    if save_results:
        try:
            if output_dir is None:
                output_dir = os.path.join(_project_root, "outputs", "isekai", episode)

            os.makedirs(output_dir, exist_ok=True)

            # 종합 결과 저장
            review_path = os.path.join(output_dir, f"{episode}_review.json")
            with open(review_path, "w", encoding="utf-8") as f:
                # 체크리스트 텍스트는 별도 저장
                save_data = {
                    "episode": episode,
                    "form_check": form_result,
                    "voice_character_mentions": voice_result["character_mentions"],
                    "voice_dialogue_count": voice_result["dialogue_count"],
                    "feel_statistics": feel_result["statistics"],
                    "needs_manual_review": True,
                }
                json.dump(save_data, f, ensure_ascii=False, indent=2)
            print(f"[SAVE] {review_path}")
        except Exception as e:
            print(f"[WARNING] 리뷰 결과 저장 실패: {e}")

    return results


def review_script_file(script_path: str, episode: Optional[str] = None) -> Dict[str, Any]:
    """
    대본 파일을 읽어서 리뷰 실행

    Args:
        script_path: 대본 파일 경로
        episode: 에피소드 번호 (None이면 파일명에서 추출)

    Returns:
        auto_review_script 결과
    """
    with open(script_path, "r", encoding="utf-8") as f:
        script = f.read()

    if episode is None:
        # 파일명에서 에피소드 추출 (예: EP001_script.txt)
        filename = os.path.basename(script_path)
        if filename.startswith("EP"):
            episode = filename[:5]  # EP001
        else:
            episode = "EP000"

    output_dir = os.path.dirname(script_path)

    return auto_review_script(script, episode, save_results=True, output_dir=output_dir)


def get_review_checklists() -> Dict[str, str]:
    """
    리뷰 체크리스트 반환 (Claude가 사용)
    """
    return {
        "voice": VOICE_CHECKLIST,
        "feel": FEEL_CHECKLIST,
    }


def print_checklists():
    """체크리스트 출력 (Claude 검토용)"""
    print(VOICE_CHECKLIST)
    print("\n" + "="*60 + "\n")
    print(FEEL_CHECKLIST)


# =====================================================
# CLI 진입점
# =====================================================

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="혈영 이세계편 대본 리뷰")
    parser.add_argument("script_path", nargs="?", help="대본 파일 경로")
    parser.add_argument("--episode", "-e", help="에피소드 번호 (예: EP001)")
    parser.add_argument("--checklists", "-c", action="store_true", help="체크리스트만 출력")

    args = parser.parse_args()

    if args.checklists:
        print_checklists()
    elif args.script_path:
        result = review_script_file(args.script_path, args.episode)
        print("\n=== 최종 결과 ===")
        print(f"FORM 점수: {result['form_score']}점 - {result['form_verdict']}")
        print(f"수동 검토 필요: {result['needs_manual_review']}")
    else:
        print("사용법:")
        print("  python -m scripts.isekai_pipeline.reviewers EP001_script.txt")
        print("  python -m scripts.isekai_pipeline.reviewers --checklists")
