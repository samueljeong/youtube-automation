# Render 배포

Git push 후 Render에 자동 배포합니다.

## 실행 명령

```bash
git add -A && git status
```

## 배포 흐름

1. 변경사항 확인 (`git status`)
2. 커밋 생성 (사용자 확인 후)
3. Push to origin
4. Render 자동 배포 트리거

## 배포 확인

- 대시보드: https://dashboard.render.com
- 서비스 URL: https://drama-s2ns.onrender.com
- 헬스체크: https://drama-s2ns.onrender.com/health

## 주의사항

- 커밋 전 코드 리뷰 에이전트 실행 권장
- main 브랜치 push 시 자동 배포됨
- 배포 완료까지 약 2-3분 소요
