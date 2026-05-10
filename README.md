# AF Agent

## 주요 구성
- `.env`: LangSmith 추적 및 OpenRouter 호출에 필요한 비밀 키 설정
- `requirements.txt`: LangChain, LangGraph, OpenAI/Anthropic 연계를 위한 의존성 목록
- `Dockerfile`: 슬림한 Python 3.12 이미지 기반 컨테이너 빌드

## 로컬에서 실행하기 

인프라(pgvector 등)는 도커로, 앱 서버는 로컬 Python으로 실행하는 방법이에요.

### 1. 파이썬 가상환경 만들기 & 띄우기

```bash
# 가상환경 생성 (최초 1번만)
python -m venv .venv

# 가상환경 활성화 (터미널 열 때마다)
source .venv/bin/activate
```

#### 왜 가상환경을 써야 하나요?

Node.js(프론트엔드)에 익숙한 분들을 위해 비교하면:

**Node.js는 프로젝트마다 자동으로 패키지가 격리돼요:**
```
프로젝트A/node_modules/   ← A만의 패키지
프로젝트B/node_modules/   ← B만의 패키지
→ 알아서 분리됨, 신경 안 써도 됨
```

**Python은 기본적으로 전역 하나에 다 설치돼요:**
```
/usr/local/lib/python3.x/site-packages/   ← 전부 여기에 쌓임
→ 프로젝트A에서 pip install 한 것도 여기
→ 프로젝트B에서 pip install 한 것도 여기
→ 전부 섞임!
```

그래서 Python은 **가상환경(venv)** 을 만들어서 프로젝트마다 패키지를 분리해요.
`node_modules`의 Python 버전이라고 생각하면 됩니다!

- `python -m venv .venv` → `.venv` 폴더가 생김 (= `node_modules` 같은 역할)
- `source .venv/bin/activate` → 이 프로젝트 전용 Python 환경을 사용하겠다는 뜻
- 터미널에 `(.venv)` 표시가 뜨면 가상환경이 켜진 상태예요!

### 2. 인프라 컨테이너 띄우기 (pgvector 등)

```bash
docker-compose -f docker-compose.infra.yml up -d
```

### 3. 패키지 설치

```bash
pip install -r requirements.txt
```

### 4. 환경 변수 설정

```bash
# .env 파일이 없으면 예시 파일에서 복사
cp .env.example .env

# .env 파일을 열어서 API 키 등을 입력
```

### 5. 앱 실행

```bash
python main.py
```

### 6. 확인

브라우저에서 아래 주소로 접속하면 API 문서를 확인할 수 있어요:

| 주소 | 설명 |
|------|------|
| http://localhost:8000 | 서버 상태 확인 |
| http://localhost:8000/docs | **Swagger UI** - API 목록 보기 & 테스트 |
| http://localhost:8000/redoc | ReDoc - API 문서 (읽기 전용) |
| http://localhost:8000/health | 헬스 체크 |

---

## 폴더 구조 (예정)
> AI가 추천해준 AI Agent Project 폴더 구조 👇
```
AF_agent/
├── src/                          # 소스 코드
│   ├── __init__.py
│   ├── agents/                   # Agent 관련 코드
│   │   ├── __init__.py
│   │   ├── base_agent.py        # 기본 Agent 클래스
│   │   ├── llm_agent.py         # LLM 기반 Agent
│   │   └── specialized/         # 특화된 Agent들
│   │       ├── __init__.py
│   │       └── research_agent.py
│   ├── tools/                    # Agent가 사용하는 도구들
│   │   ├── __init__.py
│   │   ├── web_search.py
│   │   ├── calculator.py
│   │   └── file_handler.py
│   ├── memory/                   # 메모리/컨텍스트 관리
│   │   ├── __init__.py
│   │   ├── vector_store.py
│   │   └── conversation_history.py
│   ├── prompts/                  # 프롬프트 템플릿
│   │   ├── __init__.py
│   │   └── templates.py
│   ├── models/                   # 데이터 모델
│   │   ├── __init__.py
│   │   └── schemas.py
│   └── utils/                    # 유틸리티 함수
│       ├── __init__.py
│       ├── config.py
│       └── logger.py
├── tests/                        # 테스트 코드
│   ├── __init__.py
│   ├── test_agents/
│   ├── test_tools/
│   └── test_integration/
├── config/                       # 설정 파일
│   ├── config.yaml
│   └── prompts.yaml
├── data/                         # 데이터 파일
│   ├── raw/
│   └── processed/
├── logs/                         # 로그 파일
├── scripts/                      # 유틸리티 스크립트
│   └── setup.sh
├── docs/                         # 문서
│   └── architecture.md
├── .env                  # 환경변수
├── .gitignore
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── setup.py
├── README.md
└── main.py                       # 진입점
```
