from langchain_openai import ChatOpenAI
from dotenv import load_dotenv
import os
from langgraph.prebuilt import create_react_agent
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain.tools import tool
from src.agents.accommodation_vector import (
    entity_address,
    entity_name,
    find_best_accommodation,
    load_full_data,
)
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
def get_location_info(
    accommodation_name: str,
    query_type: Optional[str] = None
) -> str:
    """숙소의 위치 기반 정보를 조회합니다.
    주변 맛집, 관광지, 교통 정보, 공항까지의 거리/시간 등을 제공합니다.
    
    Args:
        accommodation_name: 숙소 이름 (예: "서울 시티 호텔", "해운대 비치 리조트")
        query_type: 조회할 정보 타입 (선택사항)
                   - "restaurants": 주변 맛집/음식점 정보
                   - "attractions": 주변 관광지/명소 정보
                   - "transportation": 대중교통 정보 (지하철, 버스)
                   - "airport": 공항까지의 거리와 시간
                   - "all": 모든 위치 정보 (기본값)
    
    Returns:
        요청한 숙소의 위치 관련 정보 (거리, 도보 시간, 차량 시간 등)
    """
    
    hit, error = find_best_accommodation(accommodation_name)
    if error:
        return error

    entity = hit.get("entity", {})
    full_data = load_full_data(entity)
    nearby = full_data.get("nearby_places") or {}
    transport = full_data.get("transportation") or {}

    result = f"📍 {entity_name(entity, full_data)} 위치 정보\n"
    result += f"🏠 주소: {entity_address(entity, full_data)}\n\n"

    if not nearby and not transport:
        result += "pgvector 원본 데이터에 주변 시설/교통 상세 정보가 없습니다."
        return result
    
    # 주변 맛집 정보
    if query_type in ["restaurants", "all", None]:
        restaurants = nearby.get("restaurants", [])
        if restaurants:
            result += "🍽️  주변 맛집/음식점:\n"
            for rest in restaurants:
                result += f"   • {rest.get('name', '이름 정보 없음')}\n"
                result += f"     - 거리: {rest.get('distance_km', '정보 없음')}km\n"
                if rest.get('walk_time'):
                    result += f"     - 도보: 약 {rest['walk_time']}분\n"
                result += f"     - 차량: 약 {rest.get('drive_time', '정보 없음')}분\n\n"
    
    # 주변 관광지 정보
    if query_type in ["attractions", "all", None]:
        attractions = nearby.get("attractions", [])
        if attractions:
            result += "🗺️  주변 관광지/명소:\n"
            for attr in attractions:
                result += f"   • {attr.get('name', '이름 정보 없음')}\n"
                result += f"     - 거리: {attr.get('distance_km', '정보 없음')}km\n"
                if attr.get('walk_time'):
                    result += f"     - 도보: 약 {attr['walk_time']}분\n"
                else:
                    result += f"     - 도보: 거리가 멀어 차량 이용 권장\n"
                result += f"     - 차량: 약 {attr.get('drive_time', '정보 없음')}분\n\n"
    
    # 쇼핑 정보
    if query_type in ["shopping", "all", None]:
        shopping = nearby.get("shopping", [])
        if shopping:
            result += "🛍️  쇼핑 시설:\n"
            for shop in shopping:
                result += f"   • {shop.get('name', '이름 정보 없음')}\n"
                result += f"     - 거리: {shop.get('distance_km', '정보 없음')}km\n"
                if shop.get('walk_time'):
                    result += f"     - 도보: 약 {shop['walk_time']}분\n"
                else:
                    result += f"     - 도보: 거리가 멀어 차량 이용 권장\n"
                result += f"     - 차량: 약 {shop.get('drive_time', '정보 없음')}분\n\n"
    
    # 대중교통 정보
    if query_type in ["transportation", "subway", "bus", "all", None]:
        result += "🚇 대중교통 정보:\n"
        
        # 지하철
        subways = transport.get("subway", [])
        if subways:
            result += "   [지하철]\n"
            for subway in subways:
                result += f"   • {subway.get('line', '')} {subway.get('station', '역 정보 없음')}\n"
                result += f"     - 거리: {subway.get('distance_km', '정보 없음')}km\n"
                result += f"     - 도보: 약 {subway.get('walk_time', '정보 없음')}분\n\n"
        else:
            result += "   • 근처 지하철역 없음\n\n"
        
        # 버스
        bus_stops = transport.get("bus_stops", [])
        if bus_stops:
            result += "   [버스]\n"
            for bus in bus_stops:
                result += f"   • {bus.get('name', '정류장 정보 없음')}\n"
                result += f"     - 거리: {bus.get('distance_km', '정보 없음')}km\n"
                result += f"     - 도보: 약 {bus.get('walk_time', '정보 없음')}분\n\n"
    
    # 공항 정보
    if query_type in ["airport", "all", None]:
        airports = transport.get("airport", {})
        if airports:
            result += "✈️  공항 접근성:\n"
            for airport_name, info in airports.items():
                result += f"   • {airport_name}\n"
                result += f"     - 거리: {info.get('distance_km', '정보 없음')}km\n"
                result += f"     - 차량/택시: 약 {info.get('drive_time', '정보 없음')}분\n"
                result += f"     - 대중교통: 약 {info.get('public_transport_time', '정보 없음')}분\n\n"
    
    return result

# Agent 생성
agent = create_react_agent(
    model=llm,
    tools=[get_location_info],
    prompt="""당신은 숙소 위치 정보 전문 어시스턴트입니다.
    사용자가 숙소의 위치, 주변 시설, 교통편, 거리, 소요 시간 등에 대해 질문하면 get_location_info 도구를 사용하세요.
    
    중요:
    - "여기서 공항까지 얼마나 걸려?" → query_type="airport"
    - "주변에 맛집이 많아?" → query_type="restaurants"
    - "지하철 역에서 걸어서 몇 분 거리야?" → query_type="transportation"
    - "주변에 뭐가 있어?" → query_type="all" 또는 None
    - 거리는 km와 도보/차량 소요 시간으로 친절하게 설명하세요.
    - 사용자가 구체적인 정보를 물어보면 해당 정보만 제공하세요.
    - 일반적인 위치 질문이면 모든 정보를 제공하세요.
    """,
)

# 테스트
# 질문 예시 : 해운대 비치 리조트 주변에 맛집 많아 ? / 명동 게스트하우스 지하철역에서 걸어서 몇분거리야? / 제주 오션 리조트 주변에 뭐가 있어?
# if __name__ == "__main__":
#     result = agent.invoke({"messages": [{"role": "user", "content": "명동 게스트하우스 주변 쇼핑은 어떄?"}]})
#     print(result['messages'][-1].content)
