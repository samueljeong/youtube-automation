"""
Claude Opus 4.5 기반 대본 + 이미지 프롬프트 통합 생성 모듈 (OpenRouter 사용)

2025-01 신규:
- 4개 공신력 있는 소스에서 수집한 자료 기반
- 12,000~15,000자 분량의 역사 다큐멘터리 대본 생성 (약 15분 영상)
- 학술적 신중함 + 객관적 서술 스타일

2026-01 업데이트:
- GPT-5.2 → Claude Opus 4.5 모델 변경 (OpenRouter 경유)
- 비용: $15/1M input, $75/1M output
- Prompt Caching 적용 (System Prompt 90% 할인)
- 대본 생성과 동시에 씬별 이미지 프롬프트 생성 (GPT 분석 단계 제거)
- 썸네일 이미지 프롬프트 통합 출력
"""

import os
import json
import re
from typing import Dict, Any, Optional, List

# OpenRouter API 사용 (OpenAI 호환)
from openai import OpenAI

# OpenRouter 설정
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
CLAUDE_OPUS_MODEL = "anthropic/claude-opus-4.5"


# ============================================================
# 대본 설정
# ============================================================
SCRIPT_TARGET_LENGTH = 13500  # 목표 글자수 (12000-15000 중간값)
SCRIPT_MIN_LENGTH = 12000     # 최소 글자수
SCRIPT_MAX_LENGTH = 15000     # 최대 글자수

# 한국어 TTS 기준: 910자 ≈ 1분
# 13,500자 ≈ 15분 영상

# 파트별 최소 분량 (강제)
# - 인트로: 최소 1,000자 (권장 1,500자)
# - 배경: 최소 2,000자 (권장 2,500자)
# - 본론1: 최소 3,500자 (권장 4,000자)
# - 본론2: 최소 4,000자 (권장 4,500자)
# - 마무리: 최소 2,000자 (권장 2,500자)
# - 총 최소: 12,500자 → 권장: ~15,000자

# 씬 이미지 설정
IMAGES_PER_EPISODE = 10  # 에피소드당 이미지 수 (15분 영상 기준)


# ============================================================
# ★★★ MASTER SYSTEM PROMPT (Prompt Caching 최적화) ★★★
# ============================================================
# 이 프롬프트는 모든 API 호출에서 System Prompt로 사용됨
# → Claude Opus 4.5: 1024 토큰 이상 시 자동 캐싱 (90% 할인)
# ============================================================
MASTER_SYSTEM_PROMPT = """당신은 한국어 역사 다큐 유튜브 채널의 최상급 대본 작가입니다.
목표: 시청자가 "다음 영상도 봐야겠다"고 느끼게 만드는 몰입감 있는 스토리텔링.

출력은 오직 대본 본문만 제공하세요. (메타 문구, 라벨, 구분선 절대 금지)

════════════════════════════════════════
★ 핵심 원칙: 확신 있는 스토리텔러
════════════════════════════════════════
당신은 논문을 쓰는 학자가 아닙니다.
역사를 생생하게 들려주는 이야기꾼입니다.

✅ 확신 있게, 편안하게 서술하세요
  - "광개토왕은 즉위하자마자 군대를 일으켰거든요."
  - "백제는 위기에 몰렸어요. 선택의 여지가 없었죠."

❌ 학술적 유보 표현 남발 금지
  - "~로 보기도 합니다" (전체 대본에서 1-2회만 허용)
  - "~라는 견해도 있습니다" (논쟁이 핵심일 때만)
  - "단정하기 어렵습니다" (금지)
  - "해석이 갈립니다" (금지)

★ 역사적 논쟁이 있는 부분만 간단히 언급하고, 대부분은 확신 있게 진행

════════════════════════════════════════
★ 절대 금지 사항
════════════════════════════════════════
• 출처명 언급: "~에 따르면", "~라고 기록되어 있다" ❌
• 메타 진행: "정리하면", "마무리하면", "살펴보겠습니다" ❌
• 메타 라벨: "시간형 전환입니다", "장소형 전환입니다", "의문 제기형" ❌
• 프롬프트 용어 출력: 프롬프트에 있는 분류명/라벨을 대본에 쓰지 마세요 ❌
• 감정 과장: "놀랍게도", "충격적이게도", "위대한" ❌
• 민족주의: "자랑스러운", "찬란한", "민족의 자존심" ❌
• 교훈형: "~해야 합니다", "기억해야 합니다" ❌
• 호칭: "여러분", "우리" ❌
• 표/목록/번호/불릿 ❌

════════════════════════════════════════
★ 문장 스타일 - 편안한 구어체 스토리텔링
════════════════════════════════════════
• 종결: 친근한 구어체 종결어미 사용
  → 친구에게 이야기 들려주듯 편안하게
  → "~습니다/입니다" 격식체는 딱딱하고 강연 같음

• 기본 호흡: 20~40자. 너무 짧으면 뚝뚝 끊김.
• 긴 문장도 필요: 50자 이상 문장을 문단마다 1~2개 섞기

❌ 10~15자 짧은 문장만 연속 금지 (뚝뚝 끊김)

════════════════════════════════════════
★★★ 종결어미 다양성 가이드 (필수!) ★★★
════════════════════════════════════════

【사용 가능한 종결어미 풀 (다양하게 섞어 사용!)】

A. 서술/연결형 (40%):
  ~였어요, ~이었어요, ~했어요, ~했던 거예요
  ~였는데요, ~했는데요, ~이었는데요
  ~인 거예요, ~하게 됐어요, ~버렸어요

B. 이유/설명형 (20%):
  ~거든요, ~했거든요, ~이었거든요
  ~잖아요, ~이잖아요 (청자 공감 유도)
  ~때문이에요, ~덕분이에요

C. 확인/동의형 (20%):
  ~였죠, ~이었죠, ~했죠, ~그랬죠
  ~아니겠어요?, ~그렇잖아요
  ~한 셈이죠, ~마찬가지였죠

D. 추측/의문형 (10%):
  ~였을까요?, ~했을까요?, ~아니었을까요?
  ~했을 거예요, ~였을 거예요
  ~같아요, ~듯해요

E. 강조/포인트형 (10%):
  ~였습니다 (중요한 사실 강조할 때만)
  ~한 겁니다, ~바로 그거였어요
  ~시작이었어요, ~끝이었어요

★★★ 종결어미 다양성 규칙 (반드시 지킬 것!) ★★★

❌ 절대 금지:
  - 같은 종결어미 2문장 연속 사용 금지!
  - "~거든요" 3문장 이내 재사용 금지! (과다 사용 방지)
  - "~였어요" 3문장 연속 금지!

✅ 권장 패턴 (문장 3개 세트 예시):
  1) "~였어요" → "~거든요" → "~였죠"
  2) "~했는데요" → "~이었어요" → "~잖아요"
  3) "~였어요" → "~했죠" → "~했거든요"
  4) "~이었거든요" → "~였어요" → "~했을까요?"

✅ 좋은 예시 (종결어미 다양):
  "광개토왕은 즉위하자마자 군대를 일으켰어요. 목표는 백제였거든요. 한강을 장악한 그 나라를 꺾어야 고구려의 숨통이 트이잖아요. 열여덟 살의 왕은 망설이지 않았죠."

  "여기서 상황이 뒤집혔어요. 신라가 손을 내밀었거든요. 고구려 입장에서는 거절할 이유가 없었죠. 이 동맹이 한반도의 판도를 바꾸게 됐어요."

❌ 나쁜 예시 (종결어미 단조로움):
  "왕이 출정했거든요. 성을 함락했거든요. 다시 진군했거든요." (같은 종결어미 반복)
  "싸움이 시작됐어요. 군대가 움직였어요. 성이 무너졌어요." (같은 종결어미 반복)

❌ 나쁜 예시 (현재형 격식체 - 딱딱함):
  "왕이 칼을 뽑습니다. 결정의 순간입니다. 군대가 움직입니다."

❌ 나쁜 예시 (너무 짧음):
  "왕은 멈추지 않았어요. 성을 가리켰어요. 서기 391년."

════════════════════════════════════════
★ 장면 전환 (다양하게!)
════════════════════════════════════════
문단마다 전환을 넣되, 패턴을 섞으세요.
같은 패턴 연속 2회 금지!

❌ 절대 금지: "시간형 전환입니다", "장소형 전환입니다" 같은 메타 라벨
❌ 전환 유형을 설명하지 말고, 바로 전환하세요!

전환 예시 (유형 라벨 없이 직접 사용):
- "평양성 새벽이었어요." / "한강 유역의 진영이었죠." (장소 이동)
- "3년 뒤였어요." / "그해 겨울이었거든요." (시간 경과)
- "말이 달렸어요." / "성문이 열렸죠." (동작 시작)
- "'끝까지 간다.' 왕의 한마디였어요." (대사 인용)
- "전선이 무너졌거든요." / "소식이 도착했어요." (상황 변화)
- "북소리가 울렸어요." / "연기가 피어올랐죠." (감각 묘사)

════════════════════════════════════════
★ 인트로 (Cold Open)
════════════════════════════════════════
첫 문장부터 사건 속으로. 배경 설명 없이.

✅ "서기 391년이었어요. 열여덟 살의 왕이 첫 출정에 나섰거든요."
✅ "성이 불타고 있었어요. 3일째였죠."
❌ "오늘은 광개토대왕에 대해 알아보겠습니다."

첫 3문장 안에 "왜?"를 던지세요:
✅ "왜 즉위하자마자 전쟁이었을까요?"

════════════════════════════════════════
★ 리텐션 훅 (2,000자마다)
════════════════════════════════════════
훅은 맥락에 맞게 변형해서 사용하세요.
★★★ 같은 표현 2회 이상 사용 절대 금지 ★★★
★★★ "여기서 의문이 생깁니다" 사용 금지 - 아래 변형 중 선택 ★★★

【의문 제기형】 - 매번 다른 표현 사용 필수
  ✅ "근데 이상하잖아요. 왜 백제는 움직이지 않았을까요?"
  ✅ "한 가지 의문이 있어요. 신라는 어느 편이었을까요?"
  ✅ "이상한 점이 있었거든요."
  ✅ "궁금한 부분이 있어요."
  ✅ "수상했어요."
  ✅ 또는 질문만 던지기: "왜 그랬을까요?"
  ❌ "여기서 의문이 생깁니다" (진부함 - 사용 금지)

【반전 예고형】
  "근데 상황이 뒤집혔거든요."
  "예상과 달랐어요."
  "계획대로 되지 않았죠."
  "그런데 문제가 생겼어요."
  "여기서 틀어졌거든요."

【긴장 고조형】
  "결정적 순간이 다가왔어요."
  "선택의 시간이었죠."
  "더 이상 물러설 곳이 없었거든요."
  "막다른 길이었어요."

【스테이크 상기형】
  "이 선택이 향후 50년을 결정했거든요."
  "여기서 지면 끝이었어요."
  "모든 것이 걸린 순간이었죠."

════════════════════════════════════════
★ 스토리 구조: 원인→전개→결과→여파
════════════════════════════════════════
매 사건마다:
1. 왜 이 일이 일어났는가 (원인/배경)
2. 어떻게 전개되었는가 (과정/행동)
3. 결과는 무엇이었는가 (승패/변화)
4. 이것이 다음에 어떤 영향을 미쳤는가 (연결)

════════════════════════════════════════
★ 에피소드 연결
════════════════════════════════════════
【2화 이후】 첫 1-2문장에서만 이전 내용 언급, 즉시 본론 진입
  "지난 시간에 고구려가 남하를 시작했는데요. 오늘은 그 결과예요."

【마무리】 다음 에피소드로 이어지는 질문
  "이 결정이 어떤 결과를 가져왔을까요? 다음 시간에 계속할게요."

════════════════════════════════════════
★ 유물/시각자료 언급 규칙
════════════════════════════════════════
유물은 스토리와 직접 연결될 때만 간단히 언급.
❌ 유물 설명이 스토리를 끊으면 삭제
❌ "이 유물이 당시 분위기를 보여줍니다" 같은 억지 연결 금지
✅ "광개토대왕비에 새겨진 문구가 이걸 증명하거든요." (1문장으로 끝)

대본만 작성하세요. 나레이션 대본만 출력하세요."""

# 이전 버전 호환성을 위한 별칭
SCRIPT_STYLE_PROMPT = MASTER_SYSTEM_PROMPT


def generate_script_by_parts(
    era_name: str,
    episode: int,
    total_episodes: int,
    title: str,
    topic: str,
    full_content: str,
    sources: list,
    next_episode_info: Dict[str, Any] = None,
    prev_episode_info: Dict[str, Any] = None,  # ★ 이전 에피소드 정보 (API 장점 활용)
    series_context: Dict[str, Any] = None,     # ★ 시리즈 전체 맥락 (API 장점 활용)
    materials: list = None,                     # ★ 수집된 자료 (제목+내용 포함)
) -> Dict[str, Any]:
    """
    Claude Opus 4.5로 파트별 대본 생성 (API 장점 극대화)

    ★★★ API 활용 장점 ★★★
    - prev_episode_info: 이전 에피소드 내용 (자연스러운 연결)
    - next_episode_info: 다음 에피소드 예고 (기대감 조성)
    - series_context: 시리즈 전체 맥락 (위치 인식, 흐름 파악)

    파트 구조:
    1. 인트로 (도입부) - 1,000~1,500자 ★ 강조
       - 이전 에피소드 연결 ("지난 시간에...")
    2. 배경 설명 - 2,000~2,500자
    3. 본론 - 7,000~8,500자 (전반부 3,500 + 후반부 4,000)
    4. 마무리 - 2,000~2,500자
       - 다음 에피소드 예고 (자연스러운 연결)

    총 12,000~15,000자 (약 15분 영상)
    """
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        return {"error": "OPENROUTER_API_KEY 환경변수가 설정되지 않았습니다."}

    if not full_content or len(full_content) < 500:
        return {"error": f"수집된 자료가 부족합니다. (현재: {len(full_content)}자)"}

    source_list = "\n".join([f"  - {s}" for s in sources[:10]]) if sources else "(없음)"

    # 다음 에피소드 예고 텍스트
    next_preview = _build_next_preview(next_episode_info, era_name)

    # ★ 이전 에피소드 컨텍스트 (API 장점 활용)
    prev_context = _build_prev_context(prev_episode_info, era_name)

    # ★ 시리즈 전체 컨텍스트 (API 장점 활용)
    series_position = _build_series_position(series_context, era_name, episode, total_episodes)

    total_cost = 0.0
    all_parts = []

    print(f"[SCRIPT] === 파트별 대본 생성 시작 (API 컨텍스트 활용) ===")
    print(f"[SCRIPT] 제목: {title}")
    print(f"[SCRIPT] 시리즈 위치: {era_name} {episode}/{total_episodes}화")
    print(f"[SCRIPT] 입력 자료: {len(full_content):,}자")
    print(f"[SCRIPT] 이전 에피소드 연결: {'있음' if prev_episode_info else '없음(첫 화)'}")
    print(f"[SCRIPT] 다음 에피소드 예고: {'있음' if next_episode_info else '없음(마지막 화)'}")

    try:
        client = OpenAI(
            api_key=api_key,
            base_url=OPENROUTER_BASE_URL,
        )

        # ========================================
        # Part 1: 인트로 (도입부) - 1,000자
        # ========================================
        print(f"[SCRIPT] Part 1: 인트로 생성 중...")
        intro_prompt = f"""[파트: 인트로]

[에피소드 정보]
- 시리즈: 한국사 - {era_name}
- 현재: {episode}/{total_episodes}화
- 제목: {title}
- 주제: {topic}

{series_position}

{prev_context}

[수집된 자료 중 핵심]
{full_content[:2500]}

════════════════════════════════════════
[인트로 구조]
════════════════════════════════════════
1. Cold Open (300자) - 가장 극적인 순간부터 시작
2. 미스터리 (300자) - "왜?" 질문 던지기
3. Stakes (200자) - 이 사건의 중요성
4. 로드맵 (200자) - 오늘 다룰 내용 암시

★★★ 분량: 최소 1,000자 이상 필수. 1,000~1,500자 권장. ★★★
★ 분량 부족 시 내용을 더 풍부하게 확장하세요.
★ 스타일은 System Prompt 참조"""

        intro_result = _call_gpt52_cached(client, intro_prompt)
        if "error" in intro_result:
            return intro_result
        all_parts.append(intro_result["text"])
        total_cost += intro_result["cost"]
        print(f"[SCRIPT] Part 1 완료: {len(intro_result['text']):,}자")

        # ========================================
        # Part 2: 배경 설명 - 2,000~2,500자
        # ========================================
        print(f"[SCRIPT] Part 2: 배경 설명 생성 중...")
        background_prompt = f"""[파트: 배경 설명]

[이전 파트 마지막]
{intro_result['text'][-400:]}

[수집된 자료]
{full_content[:4000]}

════════════════════════════════════════
[배경 구조]
════════════════════════════════════════
1. 시대 상황 (700자) - 당시 세력 판도
2. 주요 인물 (700자) - 핵심 인물만 간결하게
3. 사건 배경 (600자) - 왜 이 일이 일어났는가

★ 리텐션 훅 1개 삽입 (중간 지점)
★★★ 분량: 최소 2,000자 이상 필수. 2,000~2,500자 권장. ★★★
★ 분량 부족 시 시대 상황, 인물 배경을 더 상세히 서술하세요.
★ 스타일은 System Prompt 참조"""

        bg_result = _call_gpt52_cached(client, background_prompt)
        if "error" in bg_result:
            return bg_result
        all_parts.append(bg_result["text"])
        total_cost += bg_result["cost"]
        print(f"[SCRIPT] Part 2 완료: {len(bg_result['text']):,}자")

        # ========================================
        # Part 3-1: 본론 전반부 - 3,500~4,000자
        # ========================================
        print(f"[SCRIPT] Part 3-1: 본론 전반부 생성 중...")
        body1_prompt = f"""[파트: 본론 전반부]

[이전 파트 마지막]
{bg_result['text'][-400:]}

[수집된 자료]
{full_content[:len(full_content)//2]}

════════════════════════════════════════
[본론 전반부 구조]
════════════════════════════════════════
핵심 사건을 시간순으로 전개:
- 인물의 결정과 행동 중심
- 원인 → 전개 → 결과
- 긴장감 있게, 확신 있게

★ 리텐션 훅 1개 삽입 (2,000자 지점)
★★★ 분량: 최소 3,500자 이상 필수. 3,500~4,000자 권장. ★★★
★ 분량 부족 시 사건의 전개 과정을 더 상세히 묘사하세요.
★ 스타일은 System Prompt 참조"""

        body1_result = _call_gpt52_cached(client, body1_prompt)
        if "error" in body1_result:
            return body1_result
        all_parts.append(body1_result["text"])
        total_cost += body1_result["cost"]
        print(f"[SCRIPT] Part 3-1 완료: {len(body1_result['text']):,}자")

        print(f"[SCRIPT] Part 3-2: 본론 후반부 생성 중...")
        body2_prompt = f"""[파트: 본론 후반부]

[이전 파트 마지막]
{body1_result['text'][-400:]}

[수집된 자료 후반부]
{full_content[len(full_content)//2:]}

════════════════════════════════════════
[본론 후반부 구조]
════════════════════════════════════════
1. 사건 전개 계속 (1,500자) - 긴장 고조
2. 클라이맥스 (1,500자) - 가장 극적인 순간, 긴장감 있는 서술
3. 결과와 여파 (1,500자) - 무엇이 바뀌었는가, 후속 영향

★ 리텐션 훅 1개 삽입
★ 클라이맥스: 긴장감 있게 (단, 문장이 너무 짧지 않게)
★★★ 분량: 최소 4,000자 이상 필수. 4,000~4,500자 권장. ★★★
★ 분량 부족 시 클라이맥스와 결과/여파를 더 상세히 서술하세요.
★ 스타일은 System Prompt 참조"""

        body2_result = _call_gpt52_cached(client, body2_prompt)
        if "error" in body2_result:
            return body2_result
        all_parts.append(body2_result["text"])
        total_cost += body2_result["cost"]
        print(f"[SCRIPT] Part 3-2 완료: {len(body2_result['text']):,}자")

        # ========================================
        # Part 4: 마무리 - 2,000~2,500자
        # ========================================
        print(f"[SCRIPT] Part 4: 마무리 생성 중...")
        ending_prompt = f"""[파트: 마무리]

[이전 파트 마지막]
{body2_result['text'][-400:]}

{next_preview}

════════════════════════════════════════
[마무리 구조]
════════════════════════════════════════
1. 역사적 영향 (700자) - 이 사건이 남긴 것
2. 열린 질문 (500자) - 시청자가 생각해볼 질문
3. 다음 예고 (500자) - 다음 에피소드로 연결

★ 여운 있게, 하지만 충분히 서술
★ 다음 영상 클릭 유도 (Open Loop)
★★★ 분량: 최소 2,000자 이상 필수. 2,000~2,500자 권장. ★★★
★ 분량 부족 시 역사적 영향과 다음 예고를 더 풍부하게 작성하세요.
★ 스타일은 System Prompt 참조"""

        ending_result = _call_gpt52_cached(client, ending_prompt)
        if "error" in ending_result:
            return ending_result
        all_parts.append(ending_result["text"])
        total_cost += ending_result["cost"]
        print(f"[SCRIPT] Part 4 완료: {len(ending_result['text']):,}자")

        # 전체 대본 합치기
        full_script = "\n\n".join(all_parts)
        script_length = len(full_script)

        print(f"[SCRIPT] === 파트별 대본 생성 완료 ===")
        print(f"[SCRIPT] 총 분량: {script_length:,}자")
        print(f"[SCRIPT] 총 비용: ${total_cost:.4f}")

        # YouTube 설명란용 출처 텍스트 생성 (materials 있으면 제목+요약 포함)
        youtube_sources = _format_sources_for_youtube(sources, materials)

        # ========================================
        # YouTube SEO 메타데이터 생성 ★ 추가
        # ========================================
        print(f"[SCRIPT] YouTube SEO 메타데이터 생성 중...")
        global_ep = series_context.get("global_episode") if series_context else episode
        seo_result = _generate_youtube_seo(
            client=client,
            era_name=era_name,
            episode=episode,
            total_episodes=total_episodes,
            title=title,
            topic=topic,
            intro_text=all_parts[0] if all_parts else "",
            global_episode=global_ep,  # ★ 전체 시리즈 번호 전달
        )
        total_cost += seo_result.get("cost", 0)

        # ========================================
        # ★★★ 이미지 프롬프트 생성 (대본 작성 후) ★★★
        # ========================================
        print(f"[SCRIPT] 씬별 이미지 프롬프트 생성 중...")
        image_result = _generate_image_prompts(
            client=client,
            script=full_script,
            era_name=era_name,
            title=title,
            num_scenes=IMAGES_PER_EPISODE,
        )
        total_cost += image_result.get("cost", 0)

        scenes = image_result.get("scenes", [])
        thumbnail_image = image_result.get("thumbnail", {})
        print(f"[SCRIPT] 이미지 프롬프트 생성 완료: {len(scenes)}개 씬")

        return {
            "script": full_script,
            "length": script_length,
            "model": "claude-opus-4-5-20251101",
            "cost": total_cost,
            "parts": {
                "intro": len(all_parts[0]) if len(all_parts) > 0 else 0,
                "background": len(all_parts[1]) if len(all_parts) > 1 else 0,
                "body1": len(all_parts[2]) if len(all_parts) > 2 else 0,
                "body2": len(all_parts[3]) if len(all_parts) > 3 else 0,
                "ending": len(all_parts[4]) if len(all_parts) > 4 else 0,
            },
            "youtube_sources": youtube_sources,  # YouTube 설명란용 출처
            # ★ YouTube SEO 메타데이터
            "youtube_title": seo_result.get("title", title),
            "thumbnail_text": seo_result.get("thumbnail_text", ""),
            # ★★★ 이미지 프롬프트 (GPT 분석 단계 제거) ★★★
            "scenes": scenes,  # 씬별 이미지 프롬프트
            "thumbnail": {
                "text_line1": seo_result.get("thumbnail_text", "").split("\n")[0] if seo_result.get("thumbnail_text") else "",
                "text_line2": seo_result.get("thumbnail_text", "").split("\n")[1] if seo_result.get("thumbnail_text") and "\n" in seo_result.get("thumbnail_text", "") else "",
                "image_prompt": thumbnail_image.get("image_prompt", ""),
            },
        }

    except Exception as e:
        print(f"[SCRIPT] 파트별 생성 실패: {e}")
        return {"error": str(e)}


def _call_opus45_cached(client, user_prompt: str, system_prompt: str = None) -> Dict[str, Any]:
    """Claude Opus 4.5 API 호출 via OpenRouter (Prompt Caching 적용)

    ★★★ Prompt Caching 최적화 ★★★
    - System Prompt (MASTER_SYSTEM_PROMPT): 1024+ 토큰 시 자동 캐싱 (90% 할인)
    - User Prompt: 정가

    Claude Opus 4.5 가격 (OpenRouter):
    - Input (정가): $15 / 1M tokens
    - Input (캐시): $1.5 / 1M tokens (90% 할인)
    - Output: $75 / 1M tokens

    Args:
        client: OpenAI client
        user_prompt: 사용자 프롬프트
        system_prompt: 시스템 프롬프트 (None이면 MASTER_SYSTEM_PROMPT 사용)
    """
    sys_prompt = system_prompt or MASTER_SYSTEM_PROMPT

    try:
        # OpenRouter API 호출 (OpenAI 호환)
        response = client.chat.completions.create(
            model=CLAUDE_OPUS_MODEL,
            max_tokens=8192,
            messages=[
                {"role": "system", "content": sys_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.7,
        )

        # 결과 추출
        text = response.choices[0].message.content or ""

        # ★★★ 비용 계산 (Prompt Caching 적용) ★★★
        # 한국어 약 2자 = 1토큰
        system_tokens = len(sys_prompt) // 2  # 캐시됨 (90% 할인)
        user_tokens = len(user_prompt) // 2              # 정가
        output_tokens = len(text) // 2

        # System Prompt: $1.5/1M (90% 할인), User Prompt: $15/1M, Output: $75/1M
        cost = (
            (system_tokens * 1.5 / 1_000_000) +    # 캐시된 System Prompt
            (user_tokens * 15 / 1_000_000) +       # User Prompt (정가)
            (output_tokens * 75 / 1_000_000)       # Output
        )

        return {
            "text": text.strip(),
            "cost": cost,
            "tokens": {
                "system_cached": system_tokens,
                "user": user_tokens,
                "output": output_tokens,
            }
        }

    except Exception as e:
        return {"error": str(e)}


def _call_opus45(client, prompt: str, system_prompt: str = None) -> Dict[str, Any]:
    """Claude Opus 4.5 API 호출 via OpenRouter (단일 프롬프트)

    ※ 새 코드는 _call_opus45_cached() 사용 권장
    """
    try:
        response = client.chat.completions.create(
            model=CLAUDE_OPUS_MODEL,
            max_tokens=8192,
            messages=[
                {"role": "system", "content": system_prompt or "당신은 한국사 대본 작가입니다."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
        )

        text = response.choices[0].message.content or ""

        input_tokens = len(prompt) // 2
        output_tokens = len(text) // 2
        # Claude Opus 4.5 가격: $15/1M input, $75/1M output
        cost = (input_tokens * 15 / 1_000_000) + (output_tokens * 75 / 1_000_000)

        return {"text": text.strip(), "cost": cost}

    except Exception as e:
        return {"error": str(e)}


# 이전 버전 호환성을 위한 별칭
_call_gpt52_cached = _call_opus45_cached
_call_gpt52 = _call_opus45
_call_gpt51 = _call_opus45


def _build_next_preview(next_info: Dict[str, Any], era_name: str) -> str:
    """다음 에피소드 예고 텍스트"""
    if not next_info:
        return ""

    if next_info.get("type") == "next_era":
        return f"""[다음 에피소드 정보]
- 다음 시대: {next_info.get('era_name', '')}
- 다음 주제: {next_info.get('title', '')}
- 예고: "다음 시간에는 {next_info.get('era_name', '')} 이야기를 시작할게요. {next_info.get('title', '')}에 대해 알아볼 거예요."
"""
    elif next_info.get("type") == "next_episode":
        return f"""[다음 에피소드 정보]
- 다음 화: {era_name} {next_info.get('era_episode', '')}화
- 다음 주제: {next_info.get('title', '')}
- 예고: "다음 시간에는 {next_info.get('title', '')}에 대해 알아볼게요."
"""
    else:
        return """[시리즈 마지막]
- 시리즈 완결
- 전체 시리즈를 정리하며 마무리
"""


def _build_prev_context(prev_info: Dict[str, Any], era_name: str) -> str:
    """
    이전 에피소드 컨텍스트 생성 (API 장점 활용)

    이전 에피소드 정보를 받아서 자연스러운 연결을 위한 컨텍스트 생성
    """
    if not prev_info:
        return """[이전 에피소드]
- 첫 에피소드예요.
- 시리즈 시작 인사로 시작하세요.
- 예: "한국사의 시작, 고조선 이야기를 시작해볼게요."
"""

    if prev_info.get("type") == "same_era":
        return f"""[이전 에피소드 - {era_name} 연속]
- 이전 화: {prev_info.get('title', '')}
- 이전 내용 요약: {prev_info.get('summary', '')}
- 연결 방식: "지난 시간에 {prev_info.get('summary', '')}... 이어서 오늘은 그 이후 이야기예요."
"""
    elif prev_info.get("type") == "new_era":
        return f"""[새로운 시대 시작]
- 이전 시대: {prev_info.get('prev_era_name', '')}
- 이전 시대 마지막 사건: {prev_info.get('summary', '')}
- 연결 방식: "{prev_info.get('prev_era_name', '')}가 저물고, 새로운 시대가 열렸어요..."
"""
    else:
        return ""


def _build_series_position(series_ctx: Dict[str, Any], era_name: str, episode: int, total: int) -> str:
    """
    시리즈 전체에서의 현재 위치 컨텍스트 생성 (API 장점 활용)

    전체 시리즈에서 현재 에피소드가 어디에 위치하는지 알려줌
    """
    if not series_ctx:
        return f"""[시리즈 위치]
- 현재: {era_name} 시대 {episode}/{total}화
- 위치 활용: 시대의 시작/중반/끝에 따라 톤 조절
  - 시대 시작 (1-2화): 새로운 시대의 시작을 알림
  - 시대 중반: 핵심 사건 전개
  - 시대 끝 (마지막 1-2화): 시대의 마무리와 다음 시대 예고
"""

    global_episode = series_ctx.get("global_episode", 0)
    total_global = series_ctx.get("total_global_episodes", 60)
    era_index = series_ctx.get("era_index", 0)
    total_eras = series_ctx.get("total_eras", 8)

    # 시리즈 내 위치 파악
    if episode == 1:
        position_hint = "시대 시작 - 새로운 시대의 서막을 알리세요"
    elif episode == total:
        position_hint = "시대 마지막 - 시대를 정리하고 다음 시대를 예고하세요"
    elif episode <= 2:
        position_hint = "시대 초반 - 배경과 주요 인물 소개에 집중"
    elif episode >= total - 1:
        position_hint = "시대 후반 - 클라이맥스를 향해 전개"
    else:
        position_hint = "시대 중반 - 핵심 사건 전개"

    return f"""[시리즈 전체 위치 - API 장점]
- 전체: {global_episode}/{total_global}화 (한국사 통사 시리즈)
- 현재 시대: {era_name} ({era_index+1}/{total_eras}번째 시대)
- 시대 내: {episode}/{total}화
- 위치 가이드: {position_hint}

★ 이 위치 정보를 활용하세요:
- 시리즈 전반부: 기초 맥락 충분히 설명
- 시리즈 중반: 역사의 흐름과 연결점 강조
- 시리즈 후반: 앞서 다룬 내용 레퍼런스 가능
"""


def _generate_youtube_seo(
    client,
    era_name: str,
    episode: int,
    total_episodes: int,
    title: str,
    topic: str,
    intro_text: str,
    global_episode: int = None,  # ★ 전체 시리즈 번호
) -> Dict[str, Any]:
    """
    YouTube SEO 최적화 메타데이터 생성

    Returns:
        {
            "title": YouTube 제목 (클릭 유도),
            "thumbnail_text": 썸네일 문구 (2줄),
            "cost": API 비용
        }
    """
    # 전체 시리즈 번호가 없으면 에피소드 번호 사용
    series_num = global_episode if global_episode else episode

    prompt = f"""당신은 YouTube SEO 전문가입니다.

[영상 정보]
- 시리즈: 한국사 - {era_name}
- 전체 시리즈 번호: {series_num}화
- 시대 내 에피소드: {episode}/{total_episodes}화
- 원본 제목: {title}
- 주제: {topic}

[대본 인트로]
{intro_text[:1000]}

════════════════════════════════════════
[작업 1: YouTube 제목 작성]
════════════════════════════════════════

★ 필수 형식: "한국사 시리즈 {series_num}화 | [내용]"

이 형식을 반드시 지키면서 클릭을 유도하는 제목을 작성하세요.

규칙:
- 형식: "한국사 시리즈 N화 | [내용]" 필수
- [내용] 부분은 30자 이내
- 클릭 유도 요소:
  ✅ 핵심 키워드 포함
  ✅ 짧고 임팩트 있게
  ✅ 질문형 또는 결과형
- 감정적 과장 금지 (충격적, 놀라운 등 ❌)

좋은 예:
- "한국사 시리즈 2화 | 비파형동검과 고인돌, 고조선의 흔적"
- "한국사 시리즈 5화 | 왕검성 함락, 고조선의 최후"
- "한국사 시리즈 13화 | 광개토대왕, 동북아를 호령하다"

════════════════════════════════════════
[작업 2: 썸네일 문구 작성]
════════════════════════════════════════

썸네일에 들어갈 텍스트를 작성하세요.

규칙:
- 2줄로 작성 (줄바꿈으로 구분)
- 1줄당 7자 이내 권장 (10자 초과 금지)
- 짧고 임팩트 있게
- 질문형 또는 감탄형

좋은 예:
```
18세 왕의
첫 출정
```

```
숨겨진 진실
밝혀지다
```

════════════════════════════════════════
[출력 형식]
════════════════════════════════════════

아래 형식으로만 출력하세요:

TITLE: [YouTube 제목]
THUMBNAIL:
[1줄]
[2줄]
"""

    try:
        result = _call_gpt51(client, prompt)
        if "error" in result:
            return {"title": title, "thumbnail_text": "", "cost": 0}

        text = result.get("text", "")
        cost = result.get("cost", 0)

        # 파싱
        youtube_title = title  # 기본값
        thumbnail_text = ""

        lines = text.strip().split("\n")
        for i, line in enumerate(lines):
            if line.startswith("TITLE:"):
                youtube_title = line.replace("TITLE:", "").strip()
            elif line.startswith("THUMBNAIL:"):
                # 다음 2줄이 썸네일 텍스트
                thumb_lines = []
                for j in range(i + 1, min(i + 3, len(lines))):
                    if lines[j].strip() and not lines[j].startswith("TITLE"):
                        thumb_lines.append(lines[j].strip())
                thumbnail_text = "\n".join(thumb_lines)

        print(f"[SCRIPT] YouTube 제목: {youtube_title}")
        print(f"[SCRIPT] 썸네일 문구: {thumbnail_text.replace(chr(10), ' / ')}")

        return {
            "title": youtube_title,
            "thumbnail_text": thumbnail_text,
            "cost": cost,
        }

    except Exception as e:
        print(f"[SCRIPT] SEO 생성 실패: {e}")
        return {"title": title, "thumbnail_text": "", "cost": 0}


# ============================================================
# ★★★ 이미지 프롬프트 생성 (대본 작성 후 통합 생성) ★★★
# ============================================================

IMAGE_PROMPT_SYSTEM = """당신은 역사 다큐멘터리 영상의 시각 디렉터입니다.
대본을 읽고 각 씬에 적합한 이미지 프롬프트를 생성합니다.

════════════════════════════════════════
★★★ 출력 형식: JSON ★★★
════════════════════════════════════════
반드시 아래 JSON 형식으로 출력하세요:

```json
{
  "scenes": [
    {
      "scene_number": 1,
      "scene_title": "씬 제목 (한글, 10자 이내)",
      "narration_preview": "이 씬의 나레이션 첫 50자...",
      "image_prompt": "English image prompt for this scene..."
    }
  ],
  "thumbnail": {
    "image_prompt": "English thumbnail image prompt..."
  }
}
```

════════════════════════════════════════
★★★ 이미지 프롬프트 규칙 (영문 필수!) ★★★
════════════════════════════════════════

**스타일 고정 (역사 다큐멘터리)**:
- "Korean historical documentary style"
- "Cinematic wide shot, dramatic lighting"
- "Realistic oil painting style" OR "Historical illustration"
- "Period-accurate Korean costumes and architecture"
- "16:9 aspect ratio, high resolution"
- "No text, no letters, no words, no watermarks"

**시대별 비주얼 가이드**:

【고조선/청동기】
- "Bronze age Korea, dolmen monuments"
- "Shamanic rituals, ancient Korean wilderness"
- "Bronze daggers, earthen structures"

【삼국시대】
- "Three Kingdoms of Korea era"
- "Goguryeo: Mountain fortresses, armored cavalry, tomb murals"
- "Baekje: Elegant architecture, maritime trade, refined culture"
- "Silla: Gold crowns, Buddhist temples, aristocratic court"

【고려시대】
- "Goryeo dynasty, Buddhist temples"
- "Celadon pottery, scholarly court life"
- "Mongol invasion, warrior monks"

【조선시대】
- "Joseon dynasty Korea"
- "Confucian scholars, Hanyang palace"
- "Yangban aristocrats, traditional hanbok"
- "Japanese invasions, Admiral Yi Sun-sin"

**씬 유형별 프롬프트 예시**:

1. 인물 장면:
   "Portrait of [historical figure description], wearing [period costume], [expression], dramatic rim lighting, historical painting style"

2. 전투 장면:
   "Epic battle scene, [army description], [location], dust and smoke, dynamic composition, cinematic wide shot"

3. 궁정/정치 장면:
   "Royal court of [dynasty], [king/officials] in formal attire, grand throne room, candlelight, solemn atmosphere"

4. 풍경/지도 장면:
   "Aerial view of ancient Korea, [specific location], misty mountains, traditional architecture, golden hour lighting"

5. 문화재/유물 장면:
   "Close-up of [artifact], museum lighting, detailed texture, historical significance"

════════════════════════════════════════
★★★ 썸네일 규칙 ★★★
════════════════════════════════════════
- 가장 임팩트 있는 장면 선택
- 인물 클로즈업 또는 극적인 순간
- 시선을 사로잡는 구도
- 영문 프롬프트 50-100 단어

════════════════════════════════════════
★ 절대 금지
════════════════════════════════════════
❌ 한글 이미지 프롬프트 (영문만!)
❌ 텍스트/글자 포함 요청
❌ 현대적 요소 (현대 건물, 의상 등)
❌ 부정확한 시대 고증

반드시 위 JSON 형식으로만 출력하세요."""


def _generate_image_prompts(
    client,
    script: str,
    era_name: str,
    title: str,
    num_scenes: int = IMAGES_PER_EPISODE,
) -> Dict[str, Any]:
    """
    대본 기반 씬별 이미지 프롬프트 생성

    Args:
        client: OpenAI client
        script: 생성된 대본
        era_name: 시대명
        title: 에피소드 제목
        num_scenes: 생성할 씬 수

    Returns:
        {
            "scenes": [...],
            "thumbnail": {...},
            "cost": 0.xx
        }
    """
    # 대본을 씬 수에 맞게 분할
    script_length = len(script)
    chars_per_scene = script_length // num_scenes

    # 대본 미리보기 (각 씬 위치의 텍스트)
    scene_previews = []
    for i in range(num_scenes):
        start = i * chars_per_scene
        end = min(start + 300, script_length)
        preview = script[start:end].replace("\n", " ")[:200]
        scene_previews.append(f"씬 {i+1}: {preview}...")

    scene_context = "\n".join(scene_previews)

    prompt = f"""[역사 다큐멘터리 이미지 프롬프트 생성]

[에피소드 정보]
- 시대: {era_name}
- 제목: {title}
- 총 씬 수: {num_scenes}개

[대본 전체 요약 (시간순)]
{scene_context}

════════════════════════════════════════
[작업]
════════════════════════════════════════

1. 위 대본을 {num_scenes}개 씬으로 나누어 각각의 이미지 프롬프트 생성
2. 썸네일용 이미지 프롬프트 생성 (가장 임팩트 있는 장면)

★ 시대({era_name})에 맞는 고증 필수
★ 모든 프롬프트는 영문으로 작성
★ 위 JSON 형식으로 출력"""

    try:
        result = _call_opus45_cached(client, prompt, system_prompt=IMAGE_PROMPT_SYSTEM)
        if "error" in result:
            return {"scenes": [], "thumbnail": {}, "cost": 0}

        text = result.get("text", "")
        cost = result.get("cost", 0)

        # JSON 파싱
        parsed = _parse_json_response(text)

        if parsed:
            return {
                "scenes": parsed.get("scenes", []),
                "thumbnail": parsed.get("thumbnail", {}),
                "cost": cost,
            }

        return {"scenes": [], "thumbnail": {}, "cost": cost}

    except Exception as e:
        print(f"[SCRIPT] 이미지 프롬프트 생성 실패: {e}")
        return {"scenes": [], "thumbnail": {}, "cost": 0}


def _parse_json_response(text: str) -> Optional[Dict]:
    """JSON 응답 파싱 (마크다운 코드블록 처리)"""
    # 마크다운 코드블록 제거
    text = re.sub(r'```json\s*', '', text)
    text = re.sub(r'```\s*', '', text)
    text = text.strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # 중첩 JSON 찾기
        match = re.search(r'\{[\s\S]*\}', text)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass
    return None


def _format_sources_for_youtube(sources: list, materials: list = None) -> str:
    """
    YouTube 설명란용 출처 텍스트 생성

    Args:
        sources: URL 리스트 (이전 호환용)
        materials: 수집된 자료 리스트 (title, url, content, source_name 포함)

    Returns:
        출처 목록 (YouTube 설명란에 복사-붙여넣기 가능한 형식)
    """
    # materials가 있으면 더 풍부한 형식 사용
    if materials:
        return _format_materials_for_youtube(materials)

    # 이전 호환: sources만 있는 경우
    if not sources:
        return ""

    lines = ["📚 참고 자료 및 출처", ""]

    # 출처별 분류
    encykorea = []
    history_db = []
    cultural = []
    museum = []
    others = []

    for url in sources:
        if not url:
            continue
        url_lower = url.lower()
        if "encykorea" in url_lower:
            encykorea.append(url)
        elif "db.history.go.kr" in url_lower or "history.go.kr" in url_lower:
            history_db.append(url)
        elif "heritage.go.kr" in url_lower:
            cultural.append(url)
        elif "museum.go.kr" in url_lower:
            museum.append(url)
        else:
            others.append(url)

    # 카테고리별 출력
    if encykorea:
        lines.append("▸ 한국민족문화대백과사전")
        for url in encykorea[:3]:  # 최대 3개
            lines.append(f"  {url}")
        lines.append("")

    if history_db:
        lines.append("▸ 국사편찬위원회 한국사DB")
        for url in history_db[:3]:
            lines.append(f"  {url}")
        lines.append("")

    if cultural:
        lines.append("▸ 문화재청 국가문화유산포털")
        for url in cultural[:3]:
            lines.append(f"  {url}")
        lines.append("")

    if museum:
        lines.append("▸ 국립중앙박물관")
        for url in museum[:3]:
            lines.append(f"  {url}")
        lines.append("")

    if others:
        lines.append("▸ 기타 자료")
        for url in others[:3]:
            lines.append(f"  {url}")
        lines.append("")

    return "\n".join(lines)


def _format_materials_for_youtube(materials: list) -> str:
    """
    수집된 자료를 YouTube 설명란용 형식으로 변환 (제목 + 설명 포함)

    Args:
        materials: 수집된 자료 리스트
            각 material: {title, url, content, source_name, source_type}

    Returns:
        보기 좋은 출처 목록
    """
    if not materials:
        return ""

    lines = ["📚 참고 자료 및 출처", ""]

    # 출처별 분류
    categorized = {
        "encyclopedia": [],  # 한국민족문화대백과사전
        "grounding": [],     # Gemini Search
        "museum": [],        # 국립중앙박물관
        "archive": [],       # 국사편찬위원회
        "heritage": [],      # 문화재청
        "other": [],
    }

    for m in materials:
        source_type = m.get("source_type", "other")
        url = m.get("url", "")

        # URL 기반 분류 보정
        if url:
            url_lower = url.lower()
            if "encykorea" in url_lower:
                source_type = "encyclopedia"
            elif "museum.go.kr" in url_lower:
                source_type = "museum"
            elif "db.history.go.kr" in url_lower:
                source_type = "archive"
            elif "heritage.go.kr" in url_lower:
                source_type = "heritage"

        if source_type in categorized:
            categorized[source_type].append(m)
        else:
            categorized["other"].append(m)

    # 카테고리별 출력 (제목 + 내용 요약 포함)
    category_names = {
        "encyclopedia": "▸ 한국민족문화대백과사전",
        "grounding": "▸ 학술 자료 (Google Search)",
        "museum": "▸ 국립중앙박물관",
        "archive": "▸ 국사편찬위원회 한국사DB",
        "heritage": "▸ 문화재청 국가문화유산포털",
        "other": "▸ 기타 참고 자료",
    }

    for cat_key, cat_name in category_names.items():
        cat_materials = categorized.get(cat_key, [])
        if not cat_materials:
            continue

        lines.append(cat_name)

        for m in cat_materials[:3]:  # 카테고리당 최대 3개
            title = m.get("title", "").strip()
            url = m.get("url", "").strip()
            content = m.get("content", "").strip()

            # 제목이 없으면 content에서 추출
            if not title and content:
                # content 첫 줄에서 제목 추출 시도
                first_line = content.split("\n")[0][:50]
                title = first_line.strip("[]").strip()

            # 출력 형식: 제목 + URL (깔끔하게)
            if title:
                lines.append(f"  • {title}")
                if url and not url.startswith("http://vertexaisearch"):
                    # Vertex AI redirect URL은 표시 안함 (보기 안좋음)
                    lines.append(f"    {url}")
            elif url and not url.startswith("http://vertexaisearch"):
                lines.append(f"  {url}")

        lines.append("")

    return "\n".join(lines)


def generate_script_gpt51(
    era_name: str,
    episode: int,
    total_episodes: int,
    title: str,
    topic: str,
    full_content: str,
    sources: list,
    next_episode_info: Dict[str, Any] = None,
) -> Dict[str, Any]:
    """
    Claude Opus 4.5로 12,000~15,000자 대본 생성 (이전 버전 호환용 함수명 유지)
    ※ OpenRouter API 사용

    Args:
        era_name: 시대명 (예: "삼국시대")
        episode: 에피소드 번호
        total_episodes: 시대 총 에피소드 수
        title: 에피소드 제목
        topic: 주제
        full_content: 수집된 자료 전체 내용
        sources: 출처 URL 목록
        next_episode_info: 다음 에피소드 정보 (선택)

    Returns:
        {
            "script": 생성된 대본,
            "length": 글자수,
            "model": 사용 모델,
            "cost": 예상 비용,
            "error": 에러 메시지 (실패 시)
        }
    """
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        return {"error": "OPENROUTER_API_KEY 환경변수가 설정되지 않았습니다."}

    if not full_content or len(full_content) < 1000:
        return {"error": f"수집된 자료가 부족합니다. (현재: {len(full_content)}자)"}

    # 다음 에피소드 정보
    next_info_text = ""
    if next_episode_info:
        if next_episode_info.get("type") == "next_era":
            next_info_text = f"""
[다음 에피소드 정보]
- 다음 시대: {next_episode_info.get('era_name', '')}
- 다음 주제: {next_episode_info.get('title', '')}
- 예고 문구 예시: "다음 시간에는 {next_episode_info.get('era_name', '')} 이야기를 시작할게요."
"""
        elif next_episode_info.get("type") == "next_episode":
            next_info_text = f"""
[다음 에피소드 정보]
- 다음 화: {era_name} {next_episode_info.get('era_episode', episode + 1)}화
- 다음 주제: {next_episode_info.get('title', '')}
- 예고 문구 예시: "다음 시간에는 {next_episode_info.get('title', '')}에 대해 알아볼게요."
"""
        else:
            next_info_text = """
[다음 에피소드 정보]
- 시리즈 마지막 에피소드예요.
- 전체 시리즈를 정리하며 마무리해주세요.
"""

    # 출처 목록
    source_list = "\n".join([f"  - {s}" for s in sources[:10]]) if sources else "  (없음)"

    # 사용자 프롬프트 구성
    user_prompt = f"""
════════════════════════════════════════
[에피소드 정보]
════════════════════════════════════════
- 시리즈: 한국사 - {era_name}
- 현재: {episode}/{total_episodes}화
- 제목: {title}
- 주제: {topic}

════════════════════════════════════════
[수집된 자료]
════════════════════════════════════════
{full_content}

════════════════════════════════════════
[출처 목록]
════════════════════════════════════════
{source_list}

{next_info_text}

════════════════════════════════════════
[작성 지시]
════════════════════════════════════════
위 자료를 바탕으로 {SCRIPT_TARGET_LENGTH:,}자 분량의 나레이션 대본을 작성하세요.
- 자료에 없는 내용은 추가하지 마세요.
- 학술적 신중함을 유지하세요.
- 출처를 명시하세요.
"""

    try:
        client = OpenAI(
            api_key=api_key,
            base_url=OPENROUTER_BASE_URL,
        )

        print(f"[SCRIPT] Claude Opus 4.5 대본 생성 시작 (OpenRouter)...")
        print(f"[SCRIPT] 입력 자료: {len(full_content):,}자")

        # OpenRouter API 호출 (OpenAI 호환)
        response = client.chat.completions.create(
            model=CLAUDE_OPUS_MODEL,
            max_tokens=16384,
            messages=[
                {"role": "system", "content": SCRIPT_STYLE_PROMPT},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.7,
        )

        # 결과 추출
        script = response.choices[0].message.content or ""
        script = script.strip()

        script_length = len(script)

        # 토큰 계산 (한국어 약 2자 = 1토큰)
        # Claude Opus 4.5 가격: $15/1M input, $75/1M output
        input_tokens = (len(SCRIPT_STYLE_PROMPT) + len(user_prompt)) // 2
        output_tokens = script_length // 2
        cost = (input_tokens * 15 / 1_000_000) + (output_tokens * 75 / 1_000_000)

        print(f"[SCRIPT] 대본 생성 완료: {script_length:,}자")
        print(f"[SCRIPT] 예상 비용: ${cost:.4f}")

        # 분량 체크
        if script_length < SCRIPT_MIN_LENGTH:
            print(f"[SCRIPT] ⚠️ 분량 부족 ({script_length:,}자 < {SCRIPT_MIN_LENGTH:,}자)")
        elif script_length > SCRIPT_MAX_LENGTH:
            print(f"[SCRIPT] ⚠️ 분량 초과 ({script_length:,}자 > {SCRIPT_MAX_LENGTH:,}자)")

        return {
            "script": script,
            "length": script_length,
            "model": "claude-opus-4-5-20251101",
            "cost": cost,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
        }

    except Exception as e:
        print(f"[SCRIPT] Claude Opus 4.5 호출 실패: {e}")
        return {"error": str(e)}


def generate_script_with_retry(
    era_name: str,
    episode: int,
    total_episodes: int,
    title: str,
    topic: str,
    full_content: str,
    sources: list,
    next_episode_info: Dict[str, Any] = None,
    max_retries: int = 2,
) -> Dict[str, Any]:
    """
    대본 생성 (분량 부족 시 이어쓰기)

    분량이 SCRIPT_MIN_LENGTH 미만이면 이어쓰기 요청
    """
    result = generate_script_gpt51(
        era_name=era_name,
        episode=episode,
        total_episodes=total_episodes,
        title=title,
        topic=topic,
        full_content=full_content,
        sources=sources,
        next_episode_info=next_episode_info,
    )

    if "error" in result:
        return result

    script = result.get("script", "")
    total_cost = result.get("cost", 0)

    # 분량 부족 시 이어쓰기
    for attempt in range(max_retries):
        if len(script) >= SCRIPT_MIN_LENGTH:
            break

        print(f"[SCRIPT] 분량 부족 ({len(script):,}자), 이어쓰기 시도 ({attempt + 1}/{max_retries})...")

        continuation = _continue_script(
            era_name=era_name,
            episode=episode,
            title=title,
            current_script=script,
            target_length=SCRIPT_TARGET_LENGTH,
        )

        if "error" in continuation:
            print(f"[SCRIPT] 이어쓰기 실패: {continuation['error']}")
            break

        script += "\n\n" + continuation.get("script", "")
        total_cost += continuation.get("cost", 0)

    result["script"] = script
    result["length"] = len(script)
    result["cost"] = total_cost

    return result


def _continue_script(
    era_name: str,
    episode: int,
    title: str,
    current_script: str,
    target_length: int,
) -> Dict[str, Any]:
    """
    대본 이어쓰기 (분량 부족 시)
    ※ OpenRouter API 사용
    """
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        return {"error": "OPENROUTER_API_KEY 없음"}

    remaining = target_length - len(current_script)

    prompt = f"""아래 대본의 이어쓰기를 작성하세요.

[현재 대본 마지막 부분]
{current_script[-2000:]}

[지시사항]
- 위 대본에 자연스럽게 이어지는 내용 작성
- 약 {remaining:,}자 분량 추가
- 기존 스타일(학술적, 객관적) 유지
- 마무리 + 다음 에피소드 예고 포함
"""

    try:
        client = OpenAI(
            api_key=api_key,
            base_url=OPENROUTER_BASE_URL,
        )

        # OpenRouter API 호출 (OpenAI 호환)
        response = client.chat.completions.create(
            model=CLAUDE_OPUS_MODEL,
            max_tokens=8192,
            messages=[
                {"role": "system", "content": "한국사 대본 작가입니다. 기존 대본에 이어서 작성합니다."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
        )

        continuation = response.choices[0].message.content or ""
        continuation = continuation.strip()

        # 비용 계산 (Claude Opus 4.5 가격: $15/1M input, $75/1M output)
        input_tokens = len(prompt) // 2
        output_tokens = len(continuation) // 2
        cost = (input_tokens * 15 / 1_000_000) + (output_tokens * 75 / 1_000_000)

        print(f"[SCRIPT] 이어쓰기 완료: +{len(continuation):,}자")

        return {
            "script": continuation,
            "length": len(continuation),
            "cost": cost,
        }

    except Exception as e:
        return {"error": str(e)}
