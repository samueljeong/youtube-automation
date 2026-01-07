# Google Sheets 구조

## 시트 구조 개요

```
Google Sheets 파일
├── 뉴스채널      ← 채널별 탭 (탭 이름 = 채널명)
├── 드라마채널
├── 시니어채널
└── _설정        ← 언더스코어 시작 = 처리 제외 (선택)
```

## 각 시트 구조

**행 1: 채널 설정 (고정)**
| A1 | B1 |
|----|-----|
| 채널ID | UCxxxxxxxxxxxx |

**행 2: 헤더 (열 순서 자유 - 동적 매핑)**

| 헤더명 | 입/출력 | 설명 |
|--------|---------|------|
| 상태 | 입출력 | 대기/처리중/완료/실패 |
| 공개설정 | 입력 | public/private/unlisted |
| 플레이리스트ID | 입력 | YouTube 플레이리스트 ID |
| 작업시간 | 출력 | 파이프라인 실행 시간 |
| 예약시간 | 입력 | YouTube 공개 예약 시간 |
| 영상URL | 출력 | 업로드된 URL |
| CTR | 출력 | 클릭률 (%) - 자동 조회 |
| 노출수 | 출력 | impressions - 자동 조회 |
| 제목 (GPT 생성) | 출력 | GPT가 생성한 제목 |
| 제목(입력) | 입력 | ★ 사용자 입력 제목 (있으면 GPT 생성 제목 대신 사용) |
| 썸네일문구(입력) | 입력 | ★ 사용자 입력 썸네일 문구 (줄바꿈으로 line1/line2 분리) |
| 제목2 | 출력 | 대안 제목 (solution 스타일) |
| 제목3 | 출력 | 대안 제목 (authority 스타일) |
| 제목변경일 | 출력 | CTR 자동화로 변경된 날짜 |
| 대본 | 입력 | 영상 대본 전문 (★ 100% 그대로 TTS 변환됨) |
| 카테고리 | 출력 | GPT 감지 (news/story) |
| 에러메시지 | 출력 | 실패 시 에러 |
| 비용 | 출력 | 생성 비용 ($x.xx) |

**행 3~: 데이터**

## 처리 우선순위

1. **예약시간 있음**: 예약시간 빠른 순으로 처리
2. **예약시간 없음**: 시트 탭 순서대로 처리
3. **처리중 상태**: 어떤 시트에서든 처리중이면 전체 대기

## 제목 A/B 테스트 자동화

- **자동 CTR 확인**: 업로드 후 7일 경과한 영상의 CTR 자동 조회
- **자동 제목 변경**: CTR 3% 미만 + 노출 100회 이상 시 제목2 → 제목3 순서로 변경
- **변경 기록**: 제목변경일에 변경 일시 자동 기록
- **API**: `POST /api/sheets/check-ctr-and-update-titles` (매일 1회 cron 권장)

## 열 순서 자유 변경

헤더 기반 동적 매핑으로 열 순서를 자유롭게 변경할 수 있습니다.
예시:
```
A: 상태 | B: 대본 | C: 제목 | D: 영상URL | ...  (순서 1)
A: 대본 | B: 상태 | C: 영상URL | D: 제목 | ...  (순서 2) - 둘 다 OK
```

**주의**: 헤더 이름은 정확히 일치해야 합니다.

---

## 통합 시트 구조 (2025-12-19)

기존 수집 전용 시트를 **수집 + 영상 자동화** 통합 시트로 변경:

```
┌─────────────────────────────────────────────────────────────────┐
│ NEWS / HISTORY / MYSTERY 통합 시트                              │
├─────────────────────────────────────────────────────────────────┤
│ 행 1: 채널ID | UCxxxxxxxxxxxx                                   │
├─────────────────────────────────────────────────────────────────┤
│ 행 2: 헤더                                                       │
│                                                                  │
│ [수집 영역]                    [영상 자동화 영역]                │
│ ├── category                  ├── 상태 (대기/처리중/완료)       │
│ ├── core_points               ├── 대본 ★                       │
│ ├── opus_prompt_pack          ├── 제목(GPT생성)                 │
│ └── thumbnail_copy            ├── 제목(입력) ★                 │
│                               ├── 썸네일문구(입력) ★            │
│                               ├── 공개설정                      │
│                               ├── 예약시간                      │
│                               └── 영상URL                       │
├─────────────────────────────────────────────────────────────────┤
│ 행 3~: 데이터                                                    │
│                                                                  │
│ 흐름: 수집 → opus_prompt_pack 생성 →                            │
│       (사용자/자동) 대본 작성 → 상태='대기' →                    │
│       영상 생성 파이프라인 자동 시작                             │
└─────────────────────────────────────────────────────────────────┘
```

### 시트별 헤더 구조

| 시트 | 수집 헤더 | 영상 자동화 헤더 |
|------|----------|-----------------|
| NEWS | run_id, selected_rank, category, issue_one_line, core_points, brief, thumbnail_copy, opus_prompt_pack | 상태, 대본, 제목(GPT생성), 제목(입력), 썸네일문구(입력), 공개설정, 예약시간, 플레이리스트ID, 음성, 영상URL, 쇼츠URL, 제목2, 제목3, 비용, 에러메시지, 작업시간 |
| HISTORY | era, episode_slot, structure_role, core_question, facts, human_choices, impact_candidates, source_url, opus_prompt_pack, thumbnail_copy | (동일) |
| MYSTERY | episode, category, title_en, title_ko, wiki_url, summary, full_content, opus_prompt, thumbnail_copy | (동일) |

### API: 통합 시트 생성

```bash
# 3개 시트 모두 생성
curl "https://drama-s2ns.onrender.com/api/sheets/create-unified"

# 특정 시트만 생성
curl "https://drama-s2ns.onrender.com/api/sheets/create-unified?sheets=NEWS,MYSTERY"

# 채널 ID 포함
curl "https://drama-s2ns.onrender.com/api/sheets/create-unified?channel_id_NEWS=UCxxx&channel_id_MYSTERY=UCyyy"
```
