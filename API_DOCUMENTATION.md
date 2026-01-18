# AF Agent API 문서

**Base URL**: `http://your-server:8000`
**Version**: 1.0.0

---

## 목차
1. [인증 API](#인증-api)
2. [채팅 API](#채팅-api)
3. [파이프라인 API](#파이프라인-api)
4. [번역 API](#번역-api)
5. [상태 확인](#상태-확인)

---

## 인증 API

### 1. 회원가입
새로운 사용자를 생성합니다.

- **URL**: `/api/auth/signup`
- **Method**: `POST`
- **인증 필요**: 없음

#### 요청
```json
{
  "email": "user@example.com",
  "password": "password123"  // 최소 8자
}
```

#### 응답 (201 Created)
```json
{
  "id": 1,
  "email": "user@example.com",
  "name": null,
  "created_at": "2024-01-04T12:00:00"
}
```

#### 에러
- `400`: 이메일이 이미 존재
- `422`: 이메일 형식 오류 또는 비밀번호가 8자 미만
- `500`: 서버 오류

---

### 2. 로그인
사용자 인증 후 JWT 토큰을 발급합니다.

- **URL**: `/api/auth/login`
- **Method**: `POST`
- **인증 필요**: 없음

#### 요청
```json
{
  "email": "user@example.com",
  "password": "password123"
}
```

#### 응답 (200 OK)
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "user_id": 1,
  "email": "user@example.com"
}
```

#### 에러
- `401`: 이메일 또는 비밀번호 오류
- `500`: 서버 오류

---

### 3. 로그아웃
로그아웃을 처리합니다. (클라이언트에서 토큰 삭제 필요)

- **URL**: `/api/auth/logout`
- **Method**: `POST`
- **인증 필요**: **예** (Bearer Token)

#### 요청
- **Headers**:
  ```
  Authorization: Bearer {access_token}
  ```

#### 응답 (200 OK)
```json
{
  "message": "로그아웃 되었습니다",
  "user_id": 1
}
```

#### 에러
- `401`: 인증 정보가 유효하지 않음

---

### 4. 내 정보 조회
현재 로그인한 사용자 정보를 조회합니다.

- **URL**: `/api/auth/me`
- **Method**: `GET`
- **인증 필요**: **예** (Bearer Token)

#### 요청
- **Headers**:
  ```
  Authorization: Bearer {access_token}
  ```

#### 응답 (200 OK)
```json
{
  "id": 1,
  "email": "user@example.com",
  "name": null,
  "created_at": "2024-01-04T12:00:00"
}
```

#### 에러
- `401`: 인증 정보가 유효하지 않음

---

## 채팅 API

### 5. 새 채팅 생성
새로운 채팅을 생성합니다.

- **URL**: `/api/chats`
- **Method**: `POST`
- **인증 필요**: 없음 (현재)

#### 요청
```json
{
  "user_id": 1,
  "title": "강남 맛집 추천"  // 선택사항, 기본값: "새 채팅"
}
```

#### 응답 (200 OK)
```json
{
  "id": 1,
  "user_id": 1,
  "title": "강남 맛집 추천",
  "created_at": "2024-01-04T12:00:00",
  "updated_at": "2024-01-04T12:00:00"
}
```

#### 에러
- `500`: 서버 오류

---

### 6. 채팅 정보 조회
특정 채팅의 정보를 조회합니다.

- **URL**: `/api/chats/{chat_id}`
- **Method**: `GET`
- **인증 필요**: 없음 (현재)

#### 응답 (200 OK)
```json
{
  "id": 1,
  "user_id": 1,
  "title": "강남 맛집 추천",
  "created_at": "2024-01-04T12:00:00",
  "updated_at": "2024-01-04T12:00:00"
}
```

#### 에러
- `404`: 채팅을 찾을 수 없음
- `500`: 서버 오류

---

### 7. 채팅 메시지 목록 조회
채팅의 모든 메시지를 시간순으로 조회합니다.

- **URL**: `/api/chats/{chat_id}/messages`
- **Method**: `GET`
- **인증 필요**: 없음 (현재)

#### 응답 (200 OK)
```json
[
  {
    "id": 1,
    "chat_id": 1,
    "role": "user",
    "content": "강남 맛집 추천해줘",
    "created_at": "2024-01-04T12:00:00"
  },
  {
    "id": 2,
    "chat_id": 1,
    "role": "assistant",
    "content": "강남역 근처 맛집 3곳을 추천드립니다...",
    "created_at": "2024-01-04T12:00:05"
  }
]
```

#### 에러
- `500`: 서버 오류

---

### 8. 메시지 전송
채팅에 메시지를 전송하고 AI 응답을 받습니다.

- **URL**: `/api/chats/{chat_id}/messages`
- **Method**: `POST`
- **인증 필요**: 없음 (현재)

#### 요청
```json
{
  "content": "강남 맛집 추천해줘"
}
```

#### 응답 (200 OK)
```json
{
  "user_message": {
    "id": 1,
    "chat_id": 1,
    "role": "user",
    "content": "강남 맛집 추천해줘",
    "created_at": "2024-01-04T12:00:00"
  },
  "ai_message": {
    "id": 2,
    "chat_id": 1,
    "role": "assistant",
    "content": "'강남 맛집 추천해줘'에 대한 응답입니다. (향후 RAG 파이프라인 추가 예정)",
    "created_at": "2024-01-04T12:00:05"
  }
}
```

#### 참고
- 현재는 간단한 응답을 반환합니다.
- 향후 RAG 파이프라인 연동 예정 (Embedding → Milvus 검색 → Kakao Map API → LLM)

#### 에러
- `500`: 서버 오류

---

### 9. 채팅 제목 업데이트
채팅의 제목을 변경합니다.

- **URL**: `/api/chats/{chat_id}/title`
- **Method**: `PATCH`
- **인증 필요**: 없음 (현재)

#### 요청
```json
{
  "title": "강남 맛집 추천"
}
```

#### 응답 (200 OK)
```json
{
  "id": 1,
  "user_id": 1,
  "title": "강남 맛집 추천",
  "created_at": "2024-01-04T12:00:00",
  "updated_at": "2024-01-04T12:05:00"
}
```

#### 사용 시나리오
1. 새 채팅 생성 (title: "새 채팅")
2. 사용자가 첫 메시지 전송
3. 첫 메시지 내용을 요약하여 title 업데이트

#### 에러
- `404`: 채팅을 찾을 수 없음
- `500`: 서버 오류

---

### 10. 채팅 삭제
특정 채팅과 관련된 모든 메시지를 삭제합니다.

- **URL**: `/api/chats/{chat_id}`
- **Method**: `DELETE`
- **인증 필요**: 없음 (현재)

#### 응답 (200 OK)
```json
{
  "message": "채팅이 삭제되었습니다",
  "chat_id": 1
}
```

#### 에러
- `404`: 채팅을 찾을 수 없음
- `500`: 서버 오류

---

## 파이프라인 API

### 11. 파이프라인 실행
카카오맵 검색 → 크롤링 → Milvus 삽입까지 완전 통합 파이프라인을 백그라운드로 실행합니다.

- **URL**: `/pipeline/run`
- **Method**: `POST`
- **인증 필요**: 없음

#### 요청
```json
{
  "category": "restaurant",  // "accommodation", "restaurant", "all"
  "search_queries": ["강남 맛집", "신사동 일식"],
  "limit_per_query": 10,  // 1-30, 쿼리당 검색할 장소 수
  "crawl_limit": 5,  // 1-100, 실제 크롤링할 장소 수
  "recreate_collection": false  // true면 기존 컬렉션 삭제 후 재생성
}
```

#### 응답 (200 OK)
```json
{
  "message": "Pipeline started successfully. Search -> Crawl -> Insert will run automatically.",
  "category": "restaurant",
  "total_places": 5,
  "status": "running"
}
```

#### 파이프라인 단계
1. **searching**: 카카오 API로 장소 검색
2. **crawling**: 카카오맵에서 상세 정보 크롤링
3. **inserting**: OpenAI 임베딩 생성 및 Milvus 삽입
4. **completed**: 완료

#### 에러
- `400`: 파이프라인이 이미 실행 중이거나 잘못된 파라미터
- `500`: 서버 오류

---

### 12. 파이프라인 상태 조회
현재 실행 중인 파이프라인의 진행 상태를 확인합니다.

- **URL**: `/pipeline/status`
- **Method**: `GET`
- **인증 필요**: 없음

#### 응답 (200 OK)
```json
{
  "is_running": true,
  "current_phase": "crawling",  // "searching", "crawling", "inserting", "completed", "failed"
  "category": "restaurant",
  "crawl_progress": 3,
  "crawl_total": 5,
  "insert_progress": 0,
  "insert_total": 0,
  "crawled_count": 3,
  "inserted_count": 0,
  "errors": []
}
```

#### 필드 설명
- `is_running`: 파이프라인 실행 중 여부
- `current_phase`: 현재 단계
- `crawl_progress/crawl_total`: 크롤링 진행률
- `insert_progress/insert_total`: 삽입 진행률
- `crawled_count`: 총 크롤링된 장소 수
- `inserted_count`: 총 Milvus에 삽입된 장소 수
- `errors`: 발생한 에러 목록

---

### 13. 크롤링 데이터 업로드
로컬에서 크롤링한 JSON 데이터를 서버로 업로드하여 Milvus에 저장합니다.

- **URL**: `/pipeline/upload`
- **Method**: `POST`
- **인증 필요**: 없음

#### 요청
```json
{
  "place_type": "restaurant",  // "accommodation" 또는 "restaurant"
  "places": [
    {
      "place_id": "11463001",
      "basic_info": {
        "name": "맛집",
        "category": "음식점"
      },
      "home": {},
      "menu": {},
      "review": {},
      "blog_review": {},
      "photo": {},
      "location": {}
    }
  ],
  "recreate_collection": false
}
```

#### 응답 (200 OK)
```json
{
  "message": "Successfully uploaded and inserted 1 places to Milvus",
  "place_type": "restaurant",
  "total_uploaded": 1,
  "inserted_count": 1,
  "errors": []
}
```

#### 에러
- `400`: 잘못된 파라미터
- `500`: 서버 오류

---

## 번역 API

### 14. 언어 감지 및 번역
입력된 텍스트의 언어를 감지하고 같은 언어로 응답합니다.

- **URL**: `/translate`
- **Method**: `POST`
- **인증 필요**: 없음

#### 요청
```json
{
  "text": "Hello, how are you?"
}
```

#### 응답 (200 OK)
```json
{
  "original_text": "Hello, how are you?",
  "response": "I'm doing well, thank you! How can I help you today?"
}
```

#### 지원 언어
- 한국어 입력 → 한국어 응답
- 영어 입력 → 영어 응답
- 일본어 입력 → 일본어 응답

#### 에러
- `500`: 서버 오류

---

## 상태 확인

### 15. 루트 엔드포인트
API 서버 상태를 확인합니다.

- **URL**: `/`
- **Method**: `GET`

#### 응답 (200 OK)
```json
{
  "message": "AF Agent API is running",
  "status": "healthy"
}
```

---

### 16. 헬스 체크
서버 헬스 체크를 수행합니다.

- **URL**: `/health`
- **Method**: `GET`

#### 응답 (200 OK)
```json
{
  "status": "healthy"
}
```

---

## 인증 헤더 사용법

인증이 필요한 API는 요청 헤더에 Bearer 토큰을 포함해야 합니다.

```
Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

### JavaScript 예시
```javascript
const response = await fetch('http://your-server:8000/api/auth/me', {
  headers: {
    'Authorization': `Bearer ${accessToken}`,
    'Content-Type': 'application/json'
  }
});
```

### Python 예시
```python
import requests

headers = {
    'Authorization': f'Bearer {access_token}',
    'Content-Type': 'application/json'
}

response = requests.get('http://your-server:8000/api/auth/me', headers=headers)
```

---

## 에러 응답 형식

모든 API는 에러 발생 시 다음 형식으로 응답합니다.

```json
{
  "detail": "에러 메시지"
}
```

### 일반적인 HTTP 상태 코드
- `200`: 성공
- `201`: 생성 성공
- `400`: 잘못된 요청
- `401`: 인증 실패
- `404`: 리소스를 찾을 수 없음
- `422`: 유효성 검증 실패
- `500`: 서버 내부 오류

---

## 개발 참고사항

### 채팅 히스토리 관리
- 로그인 기능은 있지만, 브라우저를 닫으면 localStorage의 chat_id가 날아갑니다.
- 프론트엔드에서 localStorage에 chat_id 배열을 저장하여 히스토리를 관리하세요.

### 새 채팅 플로우
1. "새 채팅" 버튼 클릭 → `POST /api/chats` 호출
2. 받은 `chat_id`를 localStorage에 저장
3. 첫 메시지 전송 → `POST /api/chats/{chat_id}/messages`
4. 첫 메시지 내용을 요약하여 → `PATCH /api/chats/{chat_id}/title`
5. 사이드바에 title 표시

### JWT 토큰 관리
- 토큰 유효기간: 7일
- 로그아웃 시 localStorage에서 토큰 삭제 필요
- 401 에러 발생 시 로그인 페이지로 리다이렉트

---

## Swagger UI

API 문서는 다음 URL에서 인터랙티브하게 확인할 수 있습니다.

**Swagger UI**: `http://your-server:8000/docs`
**ReDoc**: `http://your-server:8000/redoc`

---

**문서 버전**: 1.0.0
**최종 업데이트**: 2024-01-04
