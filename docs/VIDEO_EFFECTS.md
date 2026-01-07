# video_effects 구조

GPT-5.1이 대본 분석 시 자동 생성하는 영상 효과 설정입니다.

## 전체 구조

```json
{
  "bgm_mood": "기본 BGM 분위기",
  "scene_bgm_changes": [
    {"scene": 3, "mood": "tense", "reason": "긴장감 고조"},
    {"scene": 5, "mood": "hopeful", "reason": "희망적인 반전"}
  ],
  "subtitle_highlights": [{"keyword": "충격", "color": "#FF0000"}],
  "screen_overlays": [{"scene": 3, "text": "대박!", "duration": 3, "style": "impact"}],
  "sound_effects": [
    {"scene": 1, "type": "whoosh", "moment": "씬 전환"},
    {"scene": 2, "type": "notification", "moment": "중요 정보"},
    {"scene": 3, "type": "impact", "moment": "충격적 사실"}
  ],
  "lower_thirds": [{"scene": 2, "text": "출처", "position": "bottom-left"}],
  "news_ticker": {"enabled": true, "headlines": ["속보: ..."]},
  "shorts": {
    "highlight_scenes": [2, 3],
    "hook_text": "이 한마디가 모든 걸 바꿨다",
    "title": "충격적인 고백 #Shorts"
  },
  "transitions": {
    "style": "crossfade",
    "duration": 0.5
  }
}
```

## BGM 분위기 종류 (13가지)

| 분위기 | 설명 | 사용 예시 |
|--------|------|----------|
| hopeful | 희망적, 밝은 | 긍정적인 결말, 성공 스토리 |
| sad | 슬픈, 감성적 | 비극, 이별, 슬픈 사연 |
| tense | 긴장감 | 위기, 갈등, 서스펜스 |
| dramatic | 극적인 | 반전, 클라이맥스, 충격적 사실 |
| calm | 차분한 | 정보 전달, 설명, 일상 |
| inspiring | 영감 | 동기부여, 도전, 성취 |
| mysterious | 신비로운 | 미스터리, 의문, 궁금증 |
| nostalgic | 향수 | 과거 회상, 추억 |
| epic | 웅장한 | 대규모 사건, 역사적 순간 |
| romantic | 로맨틱 | 사랑, 감동적인 관계 |
| comedic | 코믹 | 유머, 웃긴 상황 |
| horror | 공포 | 무서운 사건, 소름 |
| upbeat | 신나는 | 활기찬, 에너지 넘치는 |

## SFX 효과음 종류 (13가지)

| 타입 | 설명 | 사용 예시 |
|------|------|----------|
| impact | 충격음 | 충격적인 사실, 반전, 강조 |
| whoosh | 휘익 소리 | 씬 전환, 빠른 움직임 |
| ding | 딩동 알림 | 포인트 강조, 정답 |
| tension | 긴장감 | 위기, 불안, 서스펜스 |
| emotional | 감성 | 감동, 슬픔, 여운 |
| success | 성공 | 달성, 해결, 좋은 결과 |
| notification | 알림 | 중요 정보, 팁, 강조 |
| heartbeat | 심장박동 | 긴장, 불안, 두려움 |
| clock_tick | 시계 소리 | 시간 압박, 긴박감 |
| gasp | 놀람 | 충격, 반전, 서프라이즈 |
| typing | 타이핑 | 텍스트 표시, 메시지 |
| door | 문 소리 | 등장, 퇴장, 전환점 |

## 씬별 BGM 변경 기능

- GPT-5.1이 대본의 감정 흐름을 분석하여 `scene_bgm_changes` 배열 생성
- 각 변경점에서 자동으로 크로스페이드 적용
- 최소 2~3회 BGM 전환 권장 (5씬 이상 영상)
