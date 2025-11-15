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
def get_accommodation_detail(
    accommodation_name: str,
    info_type: Optional[str] = None
) -> str:
    """추천받은 숙소의 상세 정보를 조회합니다.
    주차, 리뷰, 체크인/체크아웃, 서비스 등 상세 정보를 제공합니다.
    
    Args:
        accommodation_name: 숙소 이름 (예: "서울 시티 호텔", "홍대 게스트하우스")
        info_type: 조회할 정보 타입 (선택사항: "parking", "reviews", "checkin", "services", "all")
                  지정하지 않으면 모든 상세 정보를 제공합니다.
    
    Returns:
        요청한 숙소의 상세 정보
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
    
    # 정보 타입에 따라 다른 정보 반환
    result = f"🏨 {accommodation['name']} 상세 정보\n"
    result += f"📍 위치: {accommodation['address']}\n"
    result += f"⭐ 평점: {accommodation['rating']}/5.0\n\n"
    
    # 주차 정보
    if info_type in ["parking", "all", None]:
        parking = accommodation.get("parking", {})
        result += "🚗 주차 정보:\n"
        if parking.get("available"):
            result += f"   ✅ 주차 가능: {parking.get('type', '정보 없음')}\n"
            result += f"   📊 수용 대수: {parking.get('capacity', '정보 없음')}\n"
            result += f"   💰 주차 요금: {parking.get('fee', '정보 없음')}\n"
            result += f"   📝 상세: {parking.get('detail', '정보 없음')}\n\n"
        else:
            result += "   ❌ 주차 불가능\n\n"
    
    # 체크인/체크아웃 정보
    if info_type in ["checkin", "checkout", "all", None]:
        checkin_info = accommodation.get("checkin_checkout", {})
        result += "🕐 체크인/체크아웃 정보:\n"
        result += f"   ➡️  체크인: {checkin_info.get('checkin', '정보 없음')}\n"
        result += f"   ⬅️  체크아웃: {checkin_info.get('checkout', '정보 없음')}\n"
        result += f"   🌅 얼리 체크인: {checkin_info.get('early_checkin', '정보 없음')}\n"
        result += f"   🌙 레이트 체크아웃: {checkin_info.get('late_checkout', '정보 없음')}\n\n"
    
    # 서비스 정보
    if info_type in ["services", "all", None]:
        services = accommodation.get("services", [])
        result += "✨ 제공 서비스:\n"
        for service in services:
            result += f"   • {service}\n"
        result += "\n"
    
    # 리뷰 정보
    if info_type in ["reviews", "all", None]:
        reviews = accommodation.get("reviews", [])
        result += "💬 고객 리뷰:\n"
        if reviews:
            for idx, review in enumerate(reviews[:5], 1):  # 최대 5개 리뷰만 표시
                result += f"   {idx}. {review.get('user', '익명')} (⭐ {review.get('rating', 0)}/5)\n"
                result += f"      📅 {review.get('date', '날짜 없음')}\n"
                result += f"      💭 \"{review.get('comment', '리뷰 없음')}\"\n\n"
        else:
            result += "   아직 리뷰가 없습니다.\n\n"
    
    return result

# Agent 생성
agent = create_react_agent(
    model=llm,
    tools=[get_accommodation_detail],
    prompt="""당신은 숙박 시설 상세 정보 전문 어시스턴트입니다.
    사용자가 추천받은 숙소에 대해 더 자세한 정보를 원하면 get_accommodation_detail 도구를 사용하세요.
    
    중요:
    - 주차, 리뷰, 체크인/체크아웃 시간, 제공 서비스 등 구체적인 질문에 답변하세요.
    - 사용자가 특정 정보(예: 주차, 리뷰)만 물어보면 해당 정보를 중심으로 답변하세요.
    - 사용자가 일반적으로 "상세 정보" 또는 "더 알려줘"와 비슷하게 질문하면 모든 정보를 제공하세요.
    - 친절하고 상세하게 답변하되, 불필요한 정보는 생략하세요.""",
)

# 테스트
if __name__ == "__main__":
    result = agent.invoke({"messages": [{"role": "user", "content": "서울 시티 호텔 주차 시설은 어때?"}]})
    print(result['messages'][-1].content)

