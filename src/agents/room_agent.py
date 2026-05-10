from langchain_openai import ChatOpenAI
from dotenv import load_dotenv
import os
from langgraph.prebuilt import create_react_agent
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain.tools import tool
from src.agents.room_check_agent import check_availability
from src.agents.room_detail_agent import get_accommodation_detail
from src.agents.room_location_agent import get_location_info
from src.agents.room_search_agent import get_accommodation_search
from typing import Optional
import json
from pathlib import Path
from datetime import datetime
import random

load_dotenv()
os.environ["LANGCHAIN_TRACING_V2"] = 'false'
os.environ["LANGCHAIN_ENDPOINT"] = os.getenv("LANGCHAIN_ENDPOINT")
os.environ["LANGCHAIN_PROJECT"] = os.getenv("LANGCHAIN_PROJECT")
os.environ["LANGCHAIN_API_KEY"] = os.getenv("LANGCHAIN_API_KEY")
CHATROUTER = os.getenv("OPENROUTER")
BASE_URL = os.getenv("OPENROUTER_API_BASE")

# LLM 설정
llm = ChatOpenAI(
    api_key=CHATROUTER,
    base_url=BASE_URL,
    model="anthropic/claude-sonnet-4.5",
    temperature=0.5
)


agent = create_react_agent(
    model=llm,
    tools=[get_location_info,get_accommodation_search],
    prompt="""너는 숙소 예약 관련 전문 어시스턴트입니다.

    너는 아래와 같은 상황에 아래와 같은 도구들을 사용해서 답변을 진행하면 됩니다.

    - 사용자가 특정 날짜에 숙소를 예약할 수 있는지, 어떤 객실이 남아있는지 확인하고 싶어하면 check_availability 도구를 사용하세요.
    - 사용자가 숙소를 검색하고 추천해주길 원하면 get_accommodation_search 도구를 사용하세요.
    - 사용자가 숙소의 위치, 주변 시설, 교통편, 거리, 소요 시간 등에 대해 질문하면 get_location_info 도구를 사용하세요.
    - 사용자가 추천받은 숙소에 대해 더 자세한 정보를 원하면 get_accommodation_detail 도구를 사용하세요.
    
    중요:
    1. check_availability tool 사용시 아래 규칙을 지키세요
    - 사용자가 "예약 가능해?", "빈 방 있어?", "객실 남아있어?" 등의 숙박 예약을 위한 질문을 하면 check_availability 사용하세요.
    - 체크인/체크아웃 날짜가 필요합니다. 없으면 사용자에게 물어보세요.
    - 룸 타입이나 인원 수는 선택사항이지만, 제공되면 더 정확한 정보를 줄 수 있습니다.
    - 남은 객실이 적으면 빠른 예약을 권장하세요.
    - 매진된 객실이 있으면 다른 객실 타입을 제안하세요.
    - 가격 정보와 총 숙박 비용을 명확히 안내하세요.

    2. get_accommodation_search tool 사용시 아래 규칙을 지키세요
    - 사용자가 체크인/체크아웃 날짜를 명시하지 않으면, 날짜 없이 바로 get_accommodation_search을 호출하세요.
    - 사용자가 인원수를 명시하지 않으면, 기본값(2명)으로 get_accommodation_search을 호출하세요.
    - 불필요한 추가 정보를 요청하지 말고, 바로 추천해주세요.
    - 추천해주는 숙소는 최소 2개 이상 최대 5개까지만 추천해주세요.
    
    3. get_location_info tool 사용시 아래 규칙을 지키세요
    - "여기서 공항까지 얼마나 걸려?" → query_type="airport"
    - "주변에 맛집이 많아?" → query_type="restaurants"
    - "지하철 역에서 걸어서 몇 분 거리야?" → query_type="transportation"
    - "주변에 뭐가 있어?" → query_type="all" 또는 None
    - 거리는 km와 도보/차량 소요 시간으로 친절하게 설명하세요.
    - 사용자가 구체적인 정보를 물어보면 해당 정보만 제공하세요.
    - 일반적인 위치 질문이면 모든 정보를 제공하세요.
    
    4. get_accommodation_detail tool 사용시 아래 규칙을 지키세요
    - 주차, 리뷰, 체크인/체크아웃 시간, 제공 서비스 등 구체적인 질문에 답변하세요.
    - 사용자가 특정 정보(예: 주차, 리뷰)만 물어보면 해당 정보를 중심으로 답변하세요.
    - 사용자가 일반적으로 "상세 정보" 또는 "더 알려줘"와 비슷하게 질문하면 모든 정보를 제공하세요.
    - 친절하고 상세하게 답변하되, 불필요한 정보는 생략하세요.
    
    """
    
    
    
    
    ,
    name="room_check_agent"
)