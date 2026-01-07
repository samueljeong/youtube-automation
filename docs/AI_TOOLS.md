# Claude 보조 도구 (AI Tools)

**사용자가 YouTube 검색, 이미지 생성, 트렌드 확인을 요청하면 이 API를 호출하세요!**

## 사용 가능한 도구

| 도구 | API | 용도 |
|------|-----|------|
| YouTube 리서처 | `/api/ai-tools/youtube` | 영상 검색, 자막 추출, 댓글 분석 |
| 트렌드 스캐너 | `/api/ai-tools/trend` | 실시간 뉴스, 검색어 트렌드 |
| 이미지 생성 | `/api/ai-tools/image-generate` | Gemini Imagen으로 이미지 생성 |
| 이미지 분석 | `/api/ai-tools/vision` | Gemini Vision으로 이미지/URL 분석 |

## Claude가 직접 호출하는 방법

```bash
# YouTube 검색
curl -X POST http://localhost:5059/api/ai-tools/youtube \
  -H "Content-Type: application/json" \
  -d '{"query": "검색어", "action": "search", "limit": 10}'

# 자막 추출
curl -X POST http://localhost:5059/api/ai-tools/youtube \
  -H "Content-Type: application/json" \
  -d '{"query": "VIDEO_ID", "action": "transcript"}'

# 뉴스 트렌드
curl -X POST http://localhost:5059/api/ai-tools/trend \
  -H "Content-Type: application/json" \
  -d '{"source": "news", "category": "economy"}'

# 이미지 생성
curl -X POST http://localhost:5059/api/ai-tools/image-generate \
  -H "Content-Type: application/json" \
  -d '{"prompt": "이미지 설명", "style": "realistic", "ratio": "16:9"}'

# 이미지 분석
curl -X POST http://localhost:5059/api/ai-tools/vision \
  -H "Content-Type: application/json" \
  -d '{"url": "이미지URL", "prompt": "분석 요청"}'
```

## 웹 UI

- `/ai-tools` 페이지에서 사용자가 직접 사용 가능
