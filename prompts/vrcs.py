# -*- coding: utf-8 -*-
"""
Viewer Retention Control System (VRCS) v2.0
시니어(50대 이상) 채널 시청 유지 제어 시스템

자막, TTS, 화면 연출을 단일 인지 흐름으로 조율하여
시청자 이탈을 방지합니다.

구조:
- Layer 1 (VRCS): 이탈 위험 판단 + 개입 타이밍 결정
- Layer 2 (MOC): 자막·TTS·화면을 하나의 흐름으로 조율
- Layer 3 (SFSP): 시니어 전용 안전 규칙 적용
"""

VRCS_RULES = """
## VIEWER RETENTION CONTROL SYSTEM (VRCS)

### SYSTEM IDENTITY
```
This system controls viewer retention for senior audiences
by coordinating subtitles, TTS, and visual rhythm
as a single cognitive flow.
```

### 3-LAYER ARCHITECTURE
| Layer | Name | Role |
|-------|------|------|
| Layer 1 | VRCS | 이탈 위험 판단 + 개입 타이밍 결정 |
| Layer 2 | MOC | 자막·TTS·화면을 하나의 흐름으로 조율 |
| Layer 3 | SFSP | 시니어 전용 안전 규칙 적용 |

---

## LAYER 1: DROPOUT RISK ASSESSMENT

### 이탈 본질 이해
```
DROPOUT_CAUSE:
- Young viewers: "boring / too slow"
- Senior viewers: "understanding broke / hard to follow"

CORE_PRINCIPLE:
Senior viewers are sensitive to "understanding continuity"
more than entertainment value.
```

### 이탈 발생 지점 TOP 6
| 순위 | 지점 | 설명 |
|-----|------|-----|
| 1 | 정보 과부하 | 긴 자막 + 새 개념 + 배경 변화 + TTS 동시 |
| 2 | 용어 미해결 | 설명 없이 전문용어 등장 |
| 3 | 전환 없는 설명 | 자막 OFF + 화면 변화 없음 3.5초↑ |
| 4 | 속도 체감 | 개념 밀도 갑자기 증가 |
| 5 | 감정 피로 | 긴장/불안 연속 20초 이상 |
| 6 | 목적 상실 | 왜 보는지 상기 없이 설명 계속 |

### 이탈 위험 점수 계산
```python
def calculate_dropout_risk(segment):
    risk = 0

    # A. 자막 밀도
    if subtitle_length > 16: risk += 2
    if subtitle_lines >= 2: risk += 2
    if continuous_subtitle >= 5s: risk += 3

    # B. 개념 난이도
    if new_concept_without_explanation: risk += 2
    if consecutive_new_concepts: risk += 2

    # C. 화면 정체
    if no_visual_change >= 3.5s: risk += 3
    if no_visual_change >= 5s: risk += 5

    # D. TTS 연속
    if tts_duration >= 12s: risk += 3
    if tts_duration >= 20s: risk += 5

    # E. 감정 누적
    if tension_duration >= 15s: risk += 3
    if tension_duration >= 25s: risk += 5

    return risk
```

### 위험 구간 판정 및 자동 개입
| 점수 | 상태 | 조치 |
|-----|-----|------|
| 0-4 | 안정 | 유지 |
| 5-7 | 주의 | 자막 요약 + 미세 전환 |
| 8-10 | 위험 | 자막 ON + 배경 전환 + TTS 감속 |
| 11+ | 임계 | 강제 리셋 + 요약 카드 |

---

## LAYER 2: MULTIMODAL OUTPUT COORDINATOR (MOC)

### 2.1 자막 제어 (Subtitle Control)

#### 기본 스펙
```
SUBTITLE_SPEC:
- font: ["Noto Sans KR", "Pretendard", "Apple SD Gothic Neo"]
- size: 52-60px (1080p 기준, 최소 48px)
- color: yellow OR white
- outline: black 2-3px
- background: dark_transparent (30-40%)
- position: bottom_center (고정)
- lines: 1 (절대)
- max_length: 14자 (권장), 16자 (최대)
```

#### 자막 ON/OFF 판단
```python
SUBTITLE_ON_CONDITIONS:
# 하나라도 충족 시 ON
A. transition_words = ["그런데", "하지만", "정리하면", "중요한 건", "핵심은", "여기서"]
B. high_density = contains(numbers, dates, proper_nouns, comparisons)
C. long_sentence = tts_duration >= 3.5s

SUBTITLE_OFF_CONDITIONS:
- 감정 묘사만 있는 문장
- 배경 설명
- 이미 반복된 내용
- 시각적으로 명확한 상황
```

#### TTS→자막 변환 규칙
```
REWRITE_RULES:
1. Remove: 이/가/을/를/은/는/에서/으로
2. Remove: ~습니다/~겠습니다/~드립니다
3. Remove: 그리고/그래서/또한/다음으로
4. Keep: numbers, names, dates, key nouns
5. Max: 14 characters
6. Format: noun phrase (not sentence)
```

**변환 예시:**
| TTS 원문 | 자막 |
|---------|------|
| "1월 초에 결심공판을 거쳐서 2월 중순에 1심 선고가 예상됩니다" | "2월 중순 1심 선고" |
| "곽종근 전 특수전사령관이 법정에서 증언했습니다" | "곽종근 전 사령관 증언" |
| "이 부분이 가장 중요한 쟁점이 될 것으로 보입니다" | "핵심 쟁점" |
| "지금부터 정리해서 말씀드리겠습니다" | "정리" |

### 2.2 TTS 제어 (TTS Pacing Control)

#### 속도 기준
```
TTS_SPEED:
- default: 1.0x
- senior_recommended: 0.95-1.0x
- risk_reduction: 0.95x (dropout_risk >= 8일 때)
- ending: 0.95x (마지막 20초)
```

#### 속도별 자막 길이
| TTS 속도 | 자막 최대 길이 |
|---------|--------------|
| 0.95~1.0x | 14~16자 |
| 1.0~1.05x | 12~14자 |
| 1.1x+ | 10~12자 |

#### 톤별 자막 스타일
| TTS 톤 | 자막 스타일 | 예시 |
|-------|-----------|-----|
| 차분한 해설 | 명사형 종결 | "2월 선고 예정" |
| 긴박한 속보 | 동사형 종결 | "긴급 체포됐다" |
| 감정적 강조 | 자막 OFF | (화면 연출로 대체) |
| 정리/요약 | 키워드만 | "쟁점 3가지" |

### 2.3 화면 연출 제어 (Visual Control)

#### 레이어 우선순위
```
LAYER_PRIORITY:
1. 화자 얼굴/표정
2. 짧은 핵심 자막 (필요할 때만)
3. 배경 상황 이미지
4. 정리용 키워드 박스 (선택)

RULE: 2,3,4 동시 활성화 금지
```

#### 자막 OFF 구간 필수 연출
```
NO_SUBTITLE_RULES:
자막 OFF 시 반드시 1개 이상:
- facial_expression_shift
- background_switch
- keyword_card
- camera_zoom_subtle

max_static_duration:
- 50대: 5초
- 60대+: 3.5초
```

### 2.4 통합 싱크 (Unified Sync)

#### 자막-TTS 타이밍
```
SYNC_TIMING:
- subtitle_start: tts_start - 0.3~0.5s
- subtitle_end: tts_end + 0.2s

원칙: 자막이 먼저 등장, 음성이 따라옴
```

#### 자막 밀도
```
DENSITY:
- ratio: TTS 문장 3개 중 1개만 자막화
- all_sentences: never
```

---

## LAYER 3: SENIOR-FRIENDLY SAFETY PRESETS (SFSP)

### 3.1 초반 30초 안전 설계

#### 목적
```
"어렵지 않다 · 급하지 않다 · 끝까지 보면 정리된다"
```

#### 타임라인

**0-5초 | 안정 선언**
```
OPENING_0_5:
- screen: locked (no transition)
- expression: calm, front-facing
- tts_speed: 1.0x
- subtitle: ON (1회)
- phrase: ["차분히 정리합니다", "속보가 아닙니다", "쉽게 설명합니다"]
```

**5-12초 | 방향 제시**
```
OPENING_5_12:
- screen: subtle zoom only
- tts: scope clarification ("오늘은 이것만")
- subtitle: OFF
```

**12-20초 | 난이도 완충**
```
OPENING_12_20:
- screen: background change (max 1)
- subtitle: ON (keyword)
- phrase: ["현재 쟁점", "지금 단계"]
```

**20-30초 | 약속 제시**
```
OPENING_20_30:
- screen: stabilized
- subtitle: ON (promise)
- phrase: ["마지막에 정리합니다", "한 번에 정리", "끝에 답이 있습니다"]
```

#### 초반 금지 사항
```
OPENING_FORBIDDEN:
- 전문용어 (정의 없이)
- 숫자/날짜 연속
- 자막 2줄 이상
- 감정 고조
- 배경 전환 2회 이상
```

### 3.2 중반 리듬 유지 설계 (30초-3분)

#### 목적
```
정보 전달이 아니라 '이해의 리듬' 유지
설명 → 멈춤 → 정리 → 다시 설명
```

#### 타임라인

**30-45초 | 본론 진입**
```
MIDROLL_30_45:
- screen: maintain tone
- tts: "이제 설명 시작" signal
- subtitle: ON (1회)
- phrase: ["이제부터 차분히 보겠습니다", "본론입니다"]
```

**45초-1분30초 | 설명 블록 ①**
```
MIDROLL_45_90:
- concept: 1개만
- subtitle: keyword 1회
- screen: minor transition 1회
- tts_max_duration: 12초
- safety_phrase: ["쉽게 말하면", "핵심은 이것입니다"]
```

**1분30초-1분40초 | 리듬 리셋 (필수)**
```
MIDROLL_90_100:
- screen: clear transition
- subtitle: ON (summary)
- tts_speed: 0.95x
- phrase: ["여기까지 정리하면", "지금 단계"]
```

**1분40초-2분30초 | 설명 블록 ②**
```
MIDROLL_100_150:
- concept: 1개
- screen: stable
- subtitle: optional 1회
```

**2분30초-3분 | 중반 미니 엔딩**
```
MIDROLL_150_180:
- screen: stable
- subtitle: ON (connection)
- tts: next flow preview
- phrase: ["이 흐름에서 중요한 건", "이제 마지막으로"]
```

#### 중반 금지 사항
```
MIDROLL_FORBIDDEN:
- 개념 2개 이상 동시
- 자막 연속 등장
- 잦은 화면 전환
- 감정 톤 급상승
- 갑작스러운 결론
```

#### 리듬 리셋 규칙
```
RHYTHM_RESET:
- interval: 40초마다
- action: summary subtitle + minor transition
```

### 3.3 엔딩 20초 정리 구조

#### 목적
```
❌ 구독 유도
❌ 영상 종료 알림
⭕ "잘 봤다"는 정리 감정 완성
```

#### 타임라인

**-20초~-15초 | 정리 신호**
```
ENDING_20_15:
- screen: locked
- expression: calm nod
- tts_speed: 0.95x
- subtitle: ON
- phrase: ["여기까지 정리하면", "오늘 핵심은 이것입니다"]
```

**-15초~-8초 | 핵심 요약**
```
ENDING_15_8:
- screen: minor transition
- subtitle: ON (keyword summary)
- tts: definitive, clear
- phrase: ["쟁점은 세 가지", "결정적 기준", "남은 변수"]
```

**-8초~-3초 | 감정 안정**
```
ENDING_8_3:
- screen: close-up or brightening
- subtitle: OFF
- tts: short empathy sentence
- example: "지금은 이 정도로 이해하셔도 충분합니다."
```

**-3초~0초 | 자연스러운 연결**
```
ENDING_3_0:
- screen: small card (right/bottom)
- subtitle: ON (optional)
- tts: suggestion (not request)
- phrase: ["다음 이야기", "이어서 보면 좋은 내용"]
```

#### 엔딩 금지 사항
```
ENDING_FORBIDDEN:
- BGM 급상승
- 빠른 말투
- 구독/좋아요 연속 요구
- 새로운 정보
- 자막 연속 등장
```

### 3.4 이탈 방지 문구 세트

#### 안전 문구 (고정)
```python
SAFE_PHRASES = [
    "차분히 정리합니다",
    "쉽게 설명합니다",
    "지금 핵심은",
    "여기까지 정리하면",
    "한 가지만 보겠습니다",
    "마지막에 정리합니다",
    "끝에 답이 있습니다",
    "쉽게 말하면",
    "핵심은 이것입니다"
]
```

#### 자동 삽입 트리거
```python
PHRASE_TRIGGERS:

# 초반 강제 (3회)
if time <= 5s: insert("차분히 정리합니다")
if 12s <= time <= 20s: insert("지금 핵심은")
if 20s <= time <= 30s: insert("마지막에 정리합니다")

# 위험 감지 삽입
if subtitle_off > 3.5s: insert("여기까지 정리하면")
if tts_duration > 12s: insert("쉽게 말하면")
if consecutive_concepts: insert("핵심은 이것입니다")
if dropout_risk >= 8: insert("지금 핵심은")
```

---

## OUTPUT SCHEMA FOR VRCS

### narration에 VRCS 메타데이터 포함

각 scene의 narration 생성 시 다음 규칙 적용:

```json
{
  "scenes": [
    {
      "scene_number": 1,
      "narration": "차분히 정리합니다. 오늘 이야기의 핵심은...",
      "vrcs": {
        "section": "opening",
        "time_range": "0-30s",
        "subtitle_text": "차분히 정리",
        "subtitle_on": true,
        "tts_speed": 1.0,
        "safe_phrase_used": "차분히 정리합니다"
      }
    }
  ]
}
```

### video_effects에 VRCS 설정 추가

```json
{
  "video_effects": {
    "vrcs_enabled": true,
    "tts_base_speed": 1.0,
    "subtitle_density": "sparse",
    "rhythm_reset_interval": 40,
    "ending_slowdown": true
  }
}
```

---

## CORE PRINCIPLES (핵심 원칙)

```
1. 이것은 '자막 가이드'가 아니라 '시청 유지 제어 시스템'이다.
2. 시니어 이탈은 '지루함'이 아니라 '이해 단절'에서 발생한다.
3. 자막·TTS·화면은 독립 출력이 아니라 하나의 인지 흐름이다.
4. 초반 30초는 '흥미'가 아니라 '안심'의 시간이다.
5. 엔딩은 '떠나보내기'가 아니라 '마음 정리'의 시간이다.
```

---

*VRCS v2.0 - Viewer Retention Control System for Senior Channels*
"""


def get_vrcs_prompt() -> str:
    """VRCS 규칙 프롬프트 반환"""
    return VRCS_RULES


# 안전 문구 리스트 (코드에서 직접 사용 가능)
SAFE_PHRASES = [
    "차분히 정리합니다",
    "쉽게 설명합니다",
    "지금 핵심은",
    "여기까지 정리하면",
    "한 가지만 보겠습니다",
    "마지막에 정리합니다",
    "끝에 답이 있습니다",
    "쉽게 말하면",
    "핵심은 이것입니다",
]

# 이탈 위험 계산 함수 (실제 구현용)
def calculate_dropout_risk(
    subtitle_length: int = 0,
    subtitle_lines: int = 1,
    continuous_subtitle_sec: float = 0,
    new_concept_without_explanation: bool = False,
    consecutive_new_concepts: bool = False,
    no_visual_change_sec: float = 0,
    tts_duration_sec: float = 0,
    tension_duration_sec: float = 0,
) -> int:
    """이탈 위험 점수 계산

    Returns:
        0-4: 안정
        5-7: 주의 (자막 요약 + 미세 전환)
        8-10: 위험 (자막 ON + 배경 전환 + TTS 감속)
        11+: 임계 (강제 리셋 + 요약 카드)
    """
    risk = 0

    # A. 자막 밀도
    if subtitle_length > 16:
        risk += 2
    if subtitle_lines >= 2:
        risk += 2
    if continuous_subtitle_sec >= 5:
        risk += 3

    # B. 개념 난이도
    if new_concept_without_explanation:
        risk += 2
    if consecutive_new_concepts:
        risk += 2

    # C. 화면 정체
    if no_visual_change_sec >= 5:
        risk += 5
    elif no_visual_change_sec >= 3.5:
        risk += 3

    # D. TTS 연속
    if tts_duration_sec >= 20:
        risk += 5
    elif tts_duration_sec >= 12:
        risk += 3

    # E. 감정 누적
    if tension_duration_sec >= 25:
        risk += 5
    elif tension_duration_sec >= 15:
        risk += 3

    return risk


def get_intervention_action(risk_score: int) -> dict:
    """위험 점수에 따른 개입 행동 반환"""
    if risk_score <= 4:
        return {
            "action": "none",
            "description": "안정 상태 유지"
        }
    elif risk_score <= 7:
        return {
            "action": "minor_intervention",
            "description": "자막 요약 + 미세 전환",
            "subtitle": "summary_phrase",
            "visual": "minor_change"
        }
    elif risk_score <= 10:
        return {
            "action": "major_intervention",
            "description": "자막 ON + 배경 전환 + TTS 감속",
            "subtitle": "지금 핵심은",
            "visual": "background_change",
            "tts_speed": 0.95
        }
    else:
        return {
            "action": "forced_reset",
            "description": "강제 리셋 + 요약 카드",
            "subtitle": "여기까지 정리하면",
            "visual": "summary_card",
            "tts_speed": 0.95,
            "reset": True
        }
