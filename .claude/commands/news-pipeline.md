# 뉴스 자동화 파이프라인 실행

Google News RSS에서 기사를 수집하고 대본 입력용 데이터를 생성합니다.

## 사용법

채널명을 인자로 전달하세요: `/news-pipeline ECON`

## 실행 명령

```bash
curl -X POST "https://drama-s2ns.onrender.com/api/news/run-pipeline?channel=$ARGUMENTS"
```

## 채널 종류

| 채널 | 설명 | 상태 |
|------|------|------|
| ECON | 경제 뉴스 | 활성 |
| POLICY | 정책 뉴스 | 비활성 |
| SOCIETY | 사회 뉴스 | 비활성 |
| WORLD | 국제 뉴스 | 비활성 |

## 파이프라인 흐름

1. RSS 수집 → RAW_FEED
2. 채널 필터링 → CANDIDATES_{CHANNEL}
3. TOP 3 선정 → OPUS_INPUT_{CHANNEL}

## 강제 실행

같은 날 재실행: `/news-pipeline ECON&force=1`
