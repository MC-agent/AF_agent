from langchain_openai import ChatOpenAI
from dotenv import load_dotenv
import os
from langgraph.prebuilt import create_react_agent
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain.tools import tool
from typing import Optional
from datetime import datetime
import json
from pathlib import Path

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
    check_in: str,
    check_out: str,
    guests: int = 2,
    min_price: Optional[int] = None,
    max_price: Optional[int] = None,
    accommodation_type: Optional[str] = None
) -> str:
    """한국 안에 있는 숙소를 검색합니다.
    하나의 숙소만 추천해주지 않고, 여러 숙소를 추천해줍니다.
    최대 5개의 숙소를 추천해줍니다.
    
    Args:
        location: 검색할 지역 (예: "서울", "부산", "경주", "제주도")
        check_in: 체크인 날짜 (YYYY-MM-DD 형식)
        check_out: 체크아웃 날짜 (YYYY-MM-DD 형식)
        guests: 투숙 인원 (기본값: 2명)
        min_price: 최소 가격 (선택사항)
        max_price: 최대 가격 (선택사항)
        accommodation_type: 숙소 타입 (선택사항: "호텔", "게스트하우스", "리조트", "펜션")
    
    Returns:
        검색된 숙소 정보 목록
    """
    
    # mock 데이터를 JSON 파일에서 로드 (이후 API 연동 시 삭제)
    mock_file_path = Path(__file__).parent.parent / "mock" / "room.json"
    with open(mock_file_path, 'r', encoding='utf-8') as f:
        mock_accommodations = json.load(f)
    
    # 위치에 해당하는 숙소 찾기
    accommodations = mock_accommodations.get(location, [])
    
    if not accommodations:
        return f"'{location}' 지역에서 검색된 숙소가 없습니다. 다른 지역을 검색해보세요."
    
    # 필터링 (최소 가격, 최대 가격, 숙소 타입)
    filtered = accommodations
    if min_price:
        filtered = [acc for acc in filtered if acc["price"] >= min_price]
    if max_price:
        filtered = [acc for acc in filtered if acc["price"] <= max_price]
    if accommodation_type:
        filtered = [acc for acc in filtered if acc["type"] == accommodation_type]
    
    # 결과 포맷팅
    result = f"🏨 {location} 지역 숙소 검색 결과\n"
    result += f"📅 체크인: {check_in} | 체크아웃: {check_out}\n"
    result += f"👥 인원: {guests}명\n\n"
    
    if not filtered:
        result += "검색 조건에 맞는 숙소가 없습니다."
        return result
    
    for idx, acc in enumerate(filtered, 1):
        result += f"{idx}. {acc['name']} ({acc['type']})\n"
        result += f"   💰 가격: ₩{acc['price']:,} / 1박\n"
        result += f"   ⭐ 평점: {acc['rating']}/5.0\n"
        result += f"   📍 위치: {acc['address']}\n"
        result += f"   ✨ 편의시설: {', '.join(acc['amenities'])}\n\n"
    
    return result

# Agent 생성
agent = create_react_agent(
    model=llm,
    tools=[get_accommodation_search],
    prompt="""당신은 숙박 추천 전문 어시스턴트입니다.
    사용자가 숙소를 검색하고 추천해주길 원하면 get_accommodation_search 도구를 사용하세요.
    
    중요:
    - 사용자가 체크인/체크아웃 날짜를 명시하지 않으면, 날짜 없이 바로 get_accommodation_search을 호출하세요.
    - 사용자가 인원수를 명시하지 않으면, 기본값(2명)으로 get_accommodation_search을 호출하세요.
    - 불필요한 추가 정보를 요청하지 말고, 바로 추천해주세요.
    - 추천해주는 숙소는 최소 2개 이상 최대 5개까지만 추천해주세요.""",
)

# result = agent.invoke({"messages": [{"role": "user", "content": "홍대 근처 호텔 추천해줘"}]})
# print(result['messages'][-1].content)