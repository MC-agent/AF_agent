from langchain_openai import ChatOpenAI
from dotenv import load_dotenv
import os
from langgraph.prebuilt import create_react_agent
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain.tools import tool
from typing import Optional
import json
from pathlib import Path

load_dotenv()
os.environ["LANGCHAIN_TRACING_V2"] = 'true'
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
    
    # mock 데이터를 JSON 파일에서 로드
    mock_file_path = Path(__file__).parent.parent / "mock" / "room.json"
    with open(mock_file_path, 'r', encoding='utf-8') as f:
        mock_accommodations = json.load(f)
    
    # 모든 지역에서 해당 숙소 찾기
    accommodation = None
    for location, accommodations in mock_accommodations.items():
        for acc in accommodations:
            if accommodation_name.lower() in acc["name"].lower() or acc["name"].lower() in accommodation_name.lower():
                accommodation = acc
                break
        if accommodation:
            break
    
    if not accommodation:
        return f"'{accommodation_name}' 숙소를 찾을 수 없습니다. 정확한 숙소 이름을 입력해주세요."
    
    # 위치 정보가 없는 경우
    if "nearby_places" not in accommodation or "transportation" not in accommodation:
        return f"'{accommodation['name']}'의 위치 정보가 아직 등록되지 않았습니다."
    
    nearby = accommodation.get("nearby_places", {})
    transport = accommodation.get("transportation", {})
    
    result = f"📍 {accommodation['name']} 위치 정보\n"
    result += f"🏠 주소: {accommodation['address']}\n\n"
    
    # 주변 맛집 정보
    if query_type in ["restaurants", "all", None]:
        restaurants = nearby.get("restaurants", [])
        if restaurants:
            result += "🍽️  주변 맛집/음식점:\n"
            for rest in restaurants:
                result += f"   • {rest['name']}\n"
                result += f"     - 거리: {rest['distance_km']}km\n"
                if rest.get('walk_time'):
                    result += f"     - 도보: 약 {rest['walk_time']}분\n"
                result += f"     - 차량: 약 {rest['drive_time']}분\n\n"
    
    # 주변 관광지 정보
    if query_type in ["attractions", "all", None]:
        attractions = nearby.get("attractions", [])
        if attractions:
            result += "🗺️  주변 관광지/명소:\n"
            for attr in attractions:
                result += f"   • {attr['name']}\n"
                result += f"     - 거리: {attr['distance_km']}km\n"
                if attr.get('walk_time'):
                    result += f"     - 도보: 약 {attr['walk_time']}분\n"
                else:
                    result += f"     - 도보: 거리가 멀어 차량 이용 권장\n"
                result += f"     - 차량: 약 {attr['drive_time']}분\n\n"
    
    # 쇼핑 정보
    if query_type in ["shopping", "all", None]:
        shopping = nearby.get("shopping", [])
        if shopping:
            result += "🛍️  쇼핑 시설:\n"
            for shop in shopping:
                result += f"   • {shop['name']}\n"
                result += f"     - 거리: {shop['distance_km']}km\n"
                if shop.get('walk_time'):
                    result += f"     - 도보: 약 {shop['walk_time']}분\n"
                else:
                    result += f"     - 도보: 거리가 멀어 차량 이용 권장\n"
                result += f"     - 차량: 약 {shop['drive_time']}분\n\n"
    
    # 대중교통 정보
    if query_type in ["transportation", "subway", "bus", "all", None]:
        result += "🚇 대중교통 정보:\n"
        
        # 지하철
        subways = transport.get("subway", [])
        if subways:
            result += "   [지하철]\n"
            for subway in subways:
                result += f"   • {subway['line']} {subway['station']}\n"
                result += f"     - 거리: {subway['distance_km']}km\n"
                result += f"     - 도보: 약 {subway['walk_time']}분\n\n"
        else:
            result += "   • 근처 지하철역 없음\n\n"
        
        # 버스
        bus_stops = transport.get("bus_stops", [])
        if bus_stops:
            result += "   [버스]\n"
            for bus in bus_stops:
                result += f"   • {bus['name']}\n"
                result += f"     - 거리: {bus['distance_km']}km\n"
                result += f"     - 도보: 약 {bus['walk_time']}분\n\n"
    
    # 공항 정보
    if query_type in ["airport", "all", None]:
        airports = transport.get("airport", {})
        if airports:
            result += "✈️  공항 접근성:\n"
            for airport_name, info in airports.items():
                result += f"   • {airport_name}\n"
                result += f"     - 거리: {info['distance_km']}km\n"
                result += f"     - 차량/택시: 약 {info['drive_time']}분\n"
                result += f"     - 대중교통: 약 {info['public_transport_time']}분\n\n"
    
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
if __name__ == "__main__":
    result = agent.invoke({"messages": [{"role": "user", "content": "명동 게스트하우스 주변 쇼핑은 어떄?"}]})
    print(result['messages'][-1].content)