# AF Agent

## 주요 구성
- `.env`: LangSmith 추적 및 OpenRouter 호출에 필요한 비밀 키 설정
- `requirements.txt`: LangChain, LangGraph, OpenAI/Anthropic 연계를 위한 의존성 목록
- `Dockerfile`: 슬림한 Python 3.12 이미지 기반 컨테이너 빌드

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
