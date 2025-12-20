# CTR 기반 제목 자동 변경

업로드 후 7일 경과한 영상의 CTR을 확인하고, 낮은 경우 대안 제목으로 변경합니다.

## 실행 명령

```bash
curl -X POST "https://drama-s2ns.onrender.com/api/sheets/check-ctr-and-update-titles"
```

## 자동 변경 조건

- 업로드 후 7일 경과
- CTR 3% 미만
- 노출 100회 이상

## 변경 순서

1. 제목 → 제목2 (solution 스타일)
2. 제목2 → 제목3 (authority 스타일)

## 주의사항

- 매일 1회 cron 실행 권장
- 변경 시 "제목변경일"에 기록됨
