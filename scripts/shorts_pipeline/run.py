"""
쇼츠 파이프라인 - 메인 실행 모듈

전체 흐름:
1. 연예 뉴스 수집 → SHORTS 시트에 저장
2. 대기 상태 행 조회
3. GPT로 대본 + 이미지 프롬프트 생성
4. (추후) Gemini로 이미지 생성
5. (추후) TTS + FFmpeg로 영상 생성
6. (추후) YouTube 업로드
"""

import os
import sys
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional

# 프로젝트 루트 추가
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from .config import SHEET_NAME, estimate_cost
from .sheets import (
    get_sheets_service,
    get_spreadsheet_id,
    create_shorts_sheet,
    read_pending_rows,
    update_status,
    append_row,
    check_duplicate,
)
from .news_collector import (
    collect_entertainment_news,
    search_celebrity_news,
)
from .script_generator import (
    generate_complete_shorts_package,
    format_script_for_sheet,
)


def run_news_collection(
    max_items: int = 10,
    save_to_sheet: bool = True
) -> Dict[str, Any]:
    """
    연예 뉴스 수집 및 시트 저장

    Args:
        max_items: 수집할 최대 뉴스 수
        save_to_sheet: True면 시트에 저장

    Returns:
        {
            "ok": True,
            "collected": 10,
            "saved": 8,
            "duplicates": 2
        }
    """
    print(f"\n{'='*50}")
    print("[SHORTS] 연예 뉴스 수집 시작")
    print(f"{'='*50}\n")

    # 1) 뉴스 수집
    news_items = collect_entertainment_news(
        max_per_feed=5,
        total_limit=max_items
    )

    if not news_items:
        return {"ok": False, "error": "수집된 뉴스 없음"}

    if not save_to_sheet:
        return {
            "ok": True,
            "collected": len(news_items),
            "saved": 0,
            "items": news_items
        }

    # 2) 시트에 저장
    try:
        service = get_sheets_service()
        spreadsheet_id = get_spreadsheet_id()

        # 시트 존재 확인 (없으면 생성)
        create_shorts_sheet(service, spreadsheet_id)

        saved = 0
        duplicates = 0

        for item in news_items:
            # 중복 체크
            if check_duplicate(service, spreadsheet_id, item["celebrity"], item["news_url"]):
                duplicates += 1
                print(f"[SHORTS] 중복 스킵: {item['celebrity']} - {item['news_title'][:30]}...")
                continue

            # 시트에 추가
            append_row(service, spreadsheet_id, item)
            saved += 1
            print(f"[SHORTS] 저장: {item['celebrity']} - {item['issue_type']}")

        print(f"\n[SHORTS] 수집 완료: {len(news_items)}개 중 {saved}개 저장, {duplicates}개 중복")

        return {
            "ok": True,
            "collected": len(news_items),
            "saved": saved,
            "duplicates": duplicates
        }

    except Exception as e:
        print(f"[SHORTS] 뉴스 수집 실패: {e}")
        return {"ok": False, "error": str(e)}


def run_script_generation(
    limit: int = 1
) -> Dict[str, Any]:
    """
    대기 상태 행에 대해 대본 생성

    Args:
        limit: 처리할 최대 행 수

    Returns:
        {
            "ok": True,
            "processed": 1,
            "results": [...]
        }
    """
    print(f"\n{'='*50}")
    print("[SHORTS] 대본 생성 시작")
    print(f"{'='*50}\n")

    try:
        service = get_sheets_service()
        spreadsheet_id = get_spreadsheet_id()

        # 대기 상태 행 조회
        pending_rows = read_pending_rows(service, spreadsheet_id, limit=limit)

        if not pending_rows:
            print("[SHORTS] 대기 상태 행 없음")
            return {"ok": True, "processed": 0, "message": "처리할 행 없음"}

        results = []

        for row_data in pending_rows:
            row_num = row_data["row_number"]
            celebrity = row_data.get("celebrity", "")

            print(f"\n[SHORTS] 처리 중: 행 {row_num} - {celebrity}")

            # 상태 업데이트: 처리중
            update_status(service, spreadsheet_id, row_num, "처리중")

            try:
                # 대본 생성
                result = generate_complete_shorts_package(row_data)

                if not result.get("ok"):
                    raise Exception(result.get("error", "알 수 없는 오류"))

                # 대본을 시트 형식으로 변환
                script_text = format_script_for_sheet(result.get("scenes", []))

                # 시트 업데이트
                update_status(
                    service, spreadsheet_id, row_num, "대본완료",
                    대본=script_text,
                    **{"제목(GPT생성)": result.get("title", "")},
                    비용=f"${result.get('cost', 0):.3f}"
                )

                results.append({
                    "row": row_num,
                    "celebrity": celebrity,
                    "ok": True,
                    "title": result.get("title"),
                    "scenes": len(result.get("scenes", [])),
                    "chars": result.get("total_chars", 0),
                })

                print(f"[SHORTS] 대본 생성 완료: {result.get('title')}")

            except Exception as e:
                update_status(
                    service, spreadsheet_id, row_num, "실패",
                    에러메시지=str(e)[:200]
                )
                results.append({
                    "row": row_num,
                    "celebrity": celebrity,
                    "ok": False,
                    "error": str(e)
                })
                print(f"[SHORTS] 대본 생성 실패: {e}")

        return {
            "ok": True,
            "processed": len(results),
            "results": results
        }

    except Exception as e:
        print(f"[SHORTS] 대본 생성 파이프라인 실패: {e}")
        return {"ok": False, "error": str(e)}


def run_shorts_pipeline(
    celebrity: Optional[str] = None,
    collect_news: bool = True,
    generate_script: bool = True,
    limit: int = 1
) -> Dict[str, Any]:
    """
    쇼츠 파이프라인 전체 실행

    Args:
        celebrity: 특정 연예인만 처리 (없으면 전체)
        collect_news: True면 뉴스 수집
        generate_script: True면 대본 생성
        limit: 처리할 최대 행 수

    Returns:
        {
            "ok": True,
            "news_collection": {...},
            "script_generation": {...}
        }
    """
    start_time = datetime.now(timezone.utc)

    print(f"\n{'#'*60}")
    print(f"# SHORTS 파이프라인 시작: {start_time.isoformat()}")
    print(f"{'#'*60}")

    result = {"ok": True}

    # 1) 뉴스 수집
    if collect_news:
        if celebrity:
            # 특정 연예인 뉴스 검색
            news_items = search_celebrity_news(celebrity, max_items=5)
            # 시트에 저장
            service = get_sheets_service()
            spreadsheet_id = get_spreadsheet_id()
            create_shorts_sheet(service, spreadsheet_id)
            for item in news_items:
                if not check_duplicate(service, spreadsheet_id, item["celebrity"], item["news_url"]):
                    append_row(service, spreadsheet_id, item)
            result["news_collection"] = {
                "ok": True,
                "celebrity": celebrity,
                "collected": len(news_items)
            }
        else:
            result["news_collection"] = run_news_collection(max_items=10)

    # 2) 대본 생성
    if generate_script:
        result["script_generation"] = run_script_generation(limit=limit)

    # 완료
    end_time = datetime.now(timezone.utc)
    duration = (end_time - start_time).total_seconds()

    result["duration_seconds"] = round(duration, 1)
    result["estimated_cost"] = f"${estimate_cost():.2f}/영상"

    print(f"\n{'#'*60}")
    print(f"# SHORTS 파이프라인 완료: {duration:.1f}초")
    print(f"{'#'*60}\n")

    return result


# CLI 실행
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="쇼츠 파이프라인")
    parser.add_argument("--collect", action="store_true", help="뉴스 수집만")
    parser.add_argument("--generate", action="store_true", help="대본 생성만")
    parser.add_argument("--celebrity", type=str, help="특정 연예인")
    parser.add_argument("--limit", type=int, default=1, help="처리할 행 수")
    parser.add_argument("--create-sheet", action="store_true", help="시트 생성만")

    args = parser.parse_args()

    if args.create_sheet:
        service = get_sheets_service()
        spreadsheet_id = get_spreadsheet_id()
        create_shorts_sheet(service, spreadsheet_id, force=True)
        print("시트 생성 완료")
    elif args.collect:
        result = run_news_collection(max_items=10)
        print(f"결과: {result}")
    elif args.generate:
        result = run_script_generation(limit=args.limit)
        print(f"결과: {result}")
    else:
        result = run_shorts_pipeline(
            celebrity=args.celebrity,
            collect_news=not args.generate,
            generate_script=not args.collect,
            limit=args.limit
        )
        print(f"결과: {result}")
