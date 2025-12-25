#!/usr/bin/env python3
"""
Supervisor Agent 테스트 스크립트
"""

import asyncio
import sys
import os

# agents 디렉토리를 path에 추가
agents_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, agents_dir)

# 직접 임포트 (상대 임포트 우회)
from base import TaskContext, AgentResult
from script_agent import ScriptAgent
from review_agent import ReviewAgent
from image_agent import ImageAgent
from supervisor import SupervisorAgent


async def test_script_agent():
    """ScriptAgent 단독 테스트"""
    print("=== ScriptAgent 테스트 ===")

    agent = ScriptAgent()
    context = TaskContext(
        topic="BTS 새 앨범 발매",
        person="BTS",
        category="연예인",
        issue_type="컴백",
    )

    result = await agent.execute(context)

    print(f"성공: {result.success}")
    print(f"비용: ${result.cost:.4f}")

    if result.success:
        print(f"제목: {result.data.get('title')}")
        print(f"길이: {result.data.get('total_chars')}자")
        print()
        print("대본:")
        print(result.data.get('full_script'))
    else:
        print(f"에러: {result.error}")

    return result


async def test_supervisor():
    """SupervisorAgent 전체 테스트"""
    print("=== Supervisor Agent 테스트 ===")
    print()

    supervisor = SupervisorAgent()

    result = await supervisor.run(
        topic="BTS 새 앨범 발매 소식",
        person="BTS",
        category="연예인",
        issue_type="컴백",
        skip_images=True,  # 이미지 스킵
    )

    print()
    print("=== 결과 ===")
    print(f"성공: {result.success}")
    print(f"비용: ${result.cost:.4f}")
    print(f"소요시간: {result.duration:.1f}초")

    if result.success:
        data = result.data
        print(f"대본 시도: {data.get('script_attempts', 0)}회")

        script = data.get('script', {})
        if script:
            print()
            print("=== 생성된 대본 ===")
            print(f"제목: {script.get('title', 'N/A')}")
            print(f"길이: {script.get('total_chars', 0)}자")
            print()
            print("내용:")
            print(script.get('full_script', 'N/A'))
    else:
        print(f"에러: {result.error}")

    print()
    print("=== 로그 ===")
    for log in result.data.get('logs', []):
        print(f"  [{log['agent']}] {log['action']} -> {log['result']}")

    return result


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--agent", choices=["script", "supervisor"], default="supervisor")
    args = parser.parse_args()

    if args.agent == "script":
        asyncio.run(test_script_agent())
    else:
        asyncio.run(test_supervisor())
