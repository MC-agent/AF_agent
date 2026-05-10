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
    entity_rating,
    find_best_accommodation,
    first_text,
    load_full_data,
    reviews_summary,
    services_summary,
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
    
    hit, error = find_best_accommodation(accommodation_name)
    if error:
        return error

    entity = hit.get("entity", {})
    full_data = load_full_data(entity)
    result = f"🏨 {entity_name(entity, full_data)} 상세 정보\n"
    result += f"📍 위치: {entity_address(entity, full_data)}\n"
    result += f"⭐ 평점: {entity_rating(entity, full_data)}\n\n"
    
    # 주차 정보
    if info_type in ["parking", "all", None]:
        parking = full_data.get("parking") or {}
        result += "🚗 주차 정보:\n"
        if isinstance(parking, dict) and parking.get("available"):
            result += f"   ✅ 주차 가능: {parking.get('type', '정보 없음')}\n"
            result += f"   📊 수용 대수: {parking.get('capacity', '정보 없음')}\n"
            result += f"   💰 주차 요금: {parking.get('fee', '정보 없음')}\n"
            result += f"   📝 상세: {parking.get('detail', '정보 없음')}\n\n"
        elif parking:
            result += f"   {parking}\n\n"
        else:
            result += "   pgvector 원본 데이터에 주차 정보가 없습니다.\n\n"
    
    # 체크인/체크아웃 정보
    if info_type in ["checkin", "checkout", "all", None]:
        checkin_info = full_data.get("checkin_checkout") or {}
        result += "🕐 체크인/체크아웃 정보:\n"
        if isinstance(checkin_info, dict) and checkin_info:
            result += f"   ➡️  체크인: {checkin_info.get('checkin', '정보 없음')}\n"
            result += f"   ⬅️  체크아웃: {checkin_info.get('checkout', '정보 없음')}\n"
            result += f"   🌅 얼리 체크인: {checkin_info.get('early_checkin', '정보 없음')}\n"
            result += f"   🌙 레이트 체크아웃: {checkin_info.get('late_checkout', '정보 없음')}\n\n"
        else:
            result += "   pgvector 원본 데이터에 체크인/체크아웃 정보가 없습니다.\n\n"
    
    # 서비스 정보
    if info_type in ["services", "all", None]:
        services = services_summary(full_data)
        result += "✨ 제공 서비스:\n"
        if services:
            for service in services.split(", "):
                result += f"   • {service}\n"
        else:
            result += "   pgvector 원본 데이터에 제공 서비스 정보가 없습니다.\n"
        result += "\n"
    
    # 리뷰 정보
    if info_type in ["reviews", "all", None]:
        reviews = reviews_summary(full_data)
        result += "💬 고객 리뷰:\n"
        if reviews:
            for idx, review in enumerate(reviews.split(", "), 1):
                result += f"   {idx}. {review}\n"
        else:
            text_content = first_text(entity.get("text_content"))
            if text_content:
                result += f"   {text_content[:300]}\n"
            else:
                result += "   pgvector 원본 데이터에 리뷰 정보가 없습니다.\n"
        result += "\n"
    
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
# if __name__ == "__main__":
#     result = agent.invoke({"messages": [{"role": "user", "content": "서울 시티 호텔 주차 시설은 어때?"}]})
#     print(result['messages'][-1].content)
