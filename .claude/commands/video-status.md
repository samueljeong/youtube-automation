# 영상 생성 상태 확인

진행 중인 영상 생성 작업의 상태를 확인합니다.

## 사용법

job_id를 인자로 전달하세요: `/video-status abc123`

## 실행 명령

```bash
curl "https://drama-s2ns.onrender.com/api/image/video-status/$ARGUMENTS"
```

## 응답 예시

```json
{
  "status": "processing",
  "progress": 75,
  "current_step": "영상 합성 중",
  "estimated_remaining": "5분"
}
```

## 상태 종류

| 상태 | 설명 |
|------|------|
| pending | 대기 중 |
| processing | 처리 중 |
| completed | 완료 |
| failed | 실패 |
