from langchain_openai import ChatOpenAI
from dotenv import load_dotenv
import os
from langgraph.prebuilt import create_react_agent
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain.tools import tool
from src.agents.accommodation_vector import format_accommodation_hit, search_accommodations
from typing import Optional

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

@tool
def get_accommodation_search(
    location: str,
    check_in: Optional[str] = None,
    check_out: Optional[str] = None,
    guests: Optional[int] = None,
    min_price: Optional[int] = None,
    max_price: Optional[int] = None,
    accommodation_type: Optional[str] = None
) -> str:
    """한국 안에 있는 숙소를 검색합니다.
    하나의 숙소만 추천해주지 않고, 여러 숙소를 추천해줍니다.
    최대 5개의 숙소를 추천해줍니다.
    
    Args:
        location: 검색할 지역 (예: "서울", "부산", "경주", "제주도")
        check_in: 체크인 날짜 (선택사항, 현재 pgvector 검색 필터에는 사용하지 않음)
        check_out: 체크아웃 날짜 (선택사항, 현재 pgvector 검색 필터에는 사용하지 않음)
        guests: 투숙 인원 (선택사항, 현재 pgvector 검색 필터에는 사용하지 않음)
        min_price: 최소 가격 (선택사항, 현재 pgvector 검색 필터에는 사용하지 않음)
        max_price: 최대 가격 (선택사항, 현재 pgvector 검색 필터에는 사용하지 않음)
        accommodation_type: 숙소 타입 (선택사항: "호텔", "게스트하우스", "리조트", "펜션")
    
    Returns:
        검색된 숙소 정보 목록
    """
    
    query_parts = [location]
    if accommodation_type:
        query_parts.append(accommodation_type)
    query_parts.append("숙소")
    results, error = search_accommodations(" ".join(query_parts), limit=5)
    if error:
        return error
    if not results:
        return f"'{location}' 지역에서 검색된 숙소가 없습니다. 다른 지역을 검색해보세요."

    result = f"🏨 {location} 지역 숙소 검색 결과\n"
    if check_in or check_out or guests or min_price or max_price:
        result += "※ 현재 pgvector 숙소 데이터는 체크인/체크아웃, 인원수, 가격 조건으로 필터링하지 않습니다.\n\n"
    else:
        result += "\n"

    for idx, hit in enumerate(results, 1):
        result += format_accommodation_hit(idx, hit)
        result += "\n\n"

    return result

# Agent 생성
agent = create_react_agent(
    model=llm,
    tools=[get_accommodation_search],
    prompt="""당신은 숙박 추천 전문 어시스턴트입니다.
    사용자가 숙소를 검색, 추천하거나 위치/주소/상세 정보를 물으면 get_accommodation_search 도구를 사용하세요.
    
    중요:
    - 현재 pgvector 숙소 데이터는 체크인/체크아웃, 인원수, 가격, 실시간 객실 재고를 의미 있게 필터링하지 않습니다.
    - 날짜와 인원수를 물어봐도 가능 여부를 단정하지 말고, 숙소 검색 결과 중심으로 답변하세요.
    - 불필요한 추가 정보를 요청하지 말고, 바로 추천해주세요.
    - 추천해주는 숙소는 최소 2개 이상 최대 5개까지만 추천해주세요.""",
)

# result = agent.invoke({"messages": [{"role": "user", "content": "홍대 근처 호텔 추천해줘"}]})
# print(result['messages'][-1].content)
