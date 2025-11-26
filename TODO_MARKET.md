# 마켓 페이지 추가 개발 계획

## 현재 완료된 기능
- [x] 스마트스토어/쿠팡 상품 조회 (Mock 데이터)
- [x] 상품 등록/수정/삭제
- [x] 가격 비교 및 동기화
- [x] 주문 현황 조회
- [x] 판매 분석 대시보드

---

## 추가 개발 계획: 홍보 콘텐츠 자동 생성 & 배포

### 1단계: 콘텐츠 자동 생성
상품 상세페이지를 분석하여 각 플랫폼별 홍보 콘텐츠 자동 생성

| 플랫폼 | 생성 콘텐츠 | 구현 방법 |
|--------|------------|----------|
| 블로그 | 상세 리뷰 글 (1000자+) | GPT로 상세페이지 → 블로그 글 변환 |
| 인스타그램 | 캡션 + 해시태그 | GPT로 짧은 홍보 문구 생성 |
| 틱톡/쇼츠 | 영상 스크립트 (15~60초) | GPT로 대본 생성 |

### 2단계: 복사/다운로드 기능
- 생성된 콘텐츠 원클릭 복사
- 이미지 + 텍스트 조합 다운로드
- 썸네일 자동 생성

### 3단계: 영상 자동 생성
| 방식 | 설명 |
|------|------|
| 간단한 방법 | 상품 이미지 + 텍스트 → 슬라이드쇼 영상 (FFmpeg/MoviePy) |
| 고급 방법 | AI 영상 생성 API (Pictory, Synthesia 등 - 유료) |

### 4단계: 자동 배포 연동
| 플랫폼 | API | 필요한 것 |
|--------|-----|----------|
| 티스토리 | 티스토리 Open API | API 키 발급 |
| 인스타그램 | Instagram Graph API | Facebook 비즈니스 계정 |
| 틱톡 | TikTok for Developers | 개발자 승인 |
| 유튜브 쇼츠 | YouTube Data API v3 | Google Cloud 프로젝트 |
| 네이버 블로그 | ❌ 공식 API 없음 | 수동 복사 |

---

## 환경 변수 (나중에 필요)
```
# 콘텐츠 생성
OPENAI_API_KEY=sk-...  (이미 있음)

# 자동 배포 (추후 추가)
TISTORY_ACCESS_TOKEN=...
INSTAGRAM_ACCESS_TOKEN=...
YOUTUBE_API_KEY=...
TIKTOK_CLIENT_KEY=...
```

---

## 참고 링크
- 티스토리 API: https://tistory.github.io/document-tistory-apis/
- Instagram Graph API: https://developers.facebook.com/docs/instagram-api/
- YouTube Data API: https://developers.google.com/youtube/v3
- TikTok API: https://developers.tiktok.com/
