# Google Sheets 데이터 읽기

Google Sheets에서 영상 생성 대기 목록을 확인합니다.

## 실행 명령

```bash
curl "https://drama-s2ns.onrender.com/api/sheets/read"
```

## 시트 구조

| 헤더 | 설명 |
|------|------|
| 상태 | 대기/처리중/완료/실패 |
| 대본 | 영상 대본 전문 |
| 제목(GPT생성) | GPT가 생성한 제목 |
| 제목(입력) | 사용자 입력 제목 (우선) |
| 영상URL | 업로드된 YouTube URL |
| 에러메시지 | 실패 시 에러 내용 |

## 필터링

"대기" 상태인 항목만 파이프라인에서 처리됩니다.
