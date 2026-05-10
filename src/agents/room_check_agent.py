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
    parse_nights,
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


def _to_int(value) -> Optional[int]:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


@tool
def check_availability(
    accommodation_name: str,
    check_in: str,
    check_out: str,
    guests: Optional[int] = None,
    room_type: Optional[str] = None
) -> str:
    """숙소의 실시간 예약 가능 여부를 확인합니다.
    특정 날짜에 예약 가능한 객실이 있는지, 룸 타입별로 몇 개의 객실이 남아있는지 확인합니다.

    Args:
        accommodation_name: 숙소 이름 (예: "서울 시티 호텔", "해운대 비치 리조트")
        check_in: 체크인 날짜 (YYYY-MM-DD 형식)
        check_out: 체크아웃 날짜 (YYYY-MM-DD 형식)
        guests: 투숙 인원 (선택사항, 지정하면 해당 인원 수용 가능한 룸만 표시)
        room_type: 특정 룸 타입 조회 (선택사항, 예: "스탠다드", "디럭스", "스위트")

    Returns:
        예약 가능 여부, 룸 타입별 남은 객실 수, 가격 정보
    """
    
    nights, date_error = parse_nights(check_in, check_out)
    if date_error:
        return date_error

    hit, error = find_best_accommodation(accommodation_name)
    if error:
        return error

    entity = hit.get("entity", {})
    full_data = load_full_data(entity)
    room_types = full_data.get("room_types") or full_data.get("rooms") or []
    if not room_types:
        return (
            f"'{entity_name(entity, full_data)}' 숙소는 pgvector에서 찾았지만, "
            "현재 pgvector 원본 데이터에 객실 재고/룸 타입 정보가 없어 예약 가능 여부를 확인할 수 없습니다."
        )

    # 결과 포맷팅
    result = f"🏨 {entity_name(entity, full_data)} 예약 가능 여부\n"
    result += f"📍 위치: {entity_address(entity, full_data)}\n"
    result += f"📅 체크인: {check_in} | 체크아웃: {check_out} ({nights}박)\n"
    if guests:
        result += f"👥 인원: {guests}명\n"
    result += "\n"
    
    available_rooms = []
    
    # 각 룸 타입별로 예약 가능 여부 확인
    for room in room_types:
        # 특정 룸 타입만 조회하는 경우
        room_name = str(room.get("type") or room.get("name") or room.get("room_type") or "")
        if room_type and room_type.lower() not in room_name.lower():
            continue
        
        # 인원 수 필터링
        max_guests = _to_int(room.get("max_guests") or room.get("capacity") or room.get("guests"))
        if guests and max_guests and max_guests < guests:
            continue
        
        total_rooms = _to_int(room.get("total_rooms") or room.get("total") or room.get("stock")) or 0
        available_raw = room.get("available")
        if available_raw is None:
            available_raw = room.get("available_rooms")
        if available_raw is None:
            available_raw = room.get("remaining")
        available = _to_int(available_raw)
        price = _to_int(room.get("price") or room.get("amount")) or 0
        room_info = {
            "type": room_name or "객실 타입 정보 없음",
            "price": price,
            "available": available,
            "total": total_rooms,
            "max_guests": max_guests or "정보 없음",
            "bed_type": room.get("bed_type") or "정보 없음",
            "size_sqm": room.get("size_sqm") or "정보 없음",
            "amenities": room.get("amenities") or [],
            "view": room.get("view") or "정보 없음"
        }
        available_rooms.append(room_info)
    
    if not available_rooms:
        if room_type:
            result += f"❌ '{room_type}' 타입의 객실을 찾을 수 없거나 조건에 맞는 객실이 없습니다.\n"
        elif guests:
            result += f"❌ {guests}명이 투숙 가능한 객실이 없습니다.\n"
        else:
            result += "❌ 조건에 맞는 객실이 없습니다.\n"
        return result
    
    # 예약 가능한 객실 정보 출력
    result += "💎 예약 가능한 객실:\n\n"
    
    for idx, room_info in enumerate(available_rooms, 1):
        if room_info["available"] is None:
            status = "재고 정보 없음"
        elif room_info["available"] > 0:
            status = "✅ 예약 가능"
        elif room_info["available"] == 0:
            status = "❌ 매진"
        else:
            status = "⚠️  마감 임박"
        
        result += f"{idx}. {room_info['type']} - {status}\n"
        if room_info["price"]:
            result += f"   💰 가격: ₩{room_info['price']:,} / 1박 (총 {nights}박: ₩{room_info['price'] * nights:,})\n"
        else:
            result += "   💰 가격: 정보 없음\n"
        result += f"   🛏️  침대: {room_info['bed_type']}\n"
        result += f"   👥 최대 인원: {room_info['max_guests']}명\n"
        result += f"   📐 면적: {room_info['size_sqm']}㎡\n"
        result += f"   🪟 뷰: {room_info['view']}\n"
        if room_info["available"] is None:
            result += f"   🔢 남은 객실: 정보 없음 / 전체 {room_info['total']}개\n"
        else:
            result += f"   🔢 남은 객실: {room_info['available']}개 / 전체 {room_info['total']}개\n"
        amenities = room_info["amenities"] if isinstance(room_info["amenities"], list) else []
        if amenities:
            result += f"   ✨ 편의시설: {', '.join(str(item) for item in amenities[:4])}\n"
        
        if room_info["available"] is not None and room_info["available"] <= 3 and room_info["available"] > 0:
            result += f"   ⚠️  인기 객실! 얼마 남지 않았습니다.\n"
        
        result += "\n"
    
    # 총 예약 가능 객실 수 요약
    known_available = [r["available"] for r in available_rooms if r["available"] is not None]
    total_available = sum(known_available)
    if known_available:
        result += f"📊 총 예약 가능 객실: {total_available}개\n"
    else:
        result += "📊 총 예약 가능 객실: pgvector 원본 데이터에 재고 수량 정보가 없습니다.\n"

    if known_available and total_available == 0:
        result += "\n⚠️  해당 날짜에 예약 가능한 객실이 없습니다. 다른 날짜를 검색해보세요.\n"
    elif known_available and total_available <= 5:
        result += "\n⚠️  남은 객실이 얼마 없습니다. 빠른 예약을 권장합니다!\n"
    
    return result

# Agent 생성
agent = create_react_agent(
    model=llm,
    tools=[check_availability],
    prompt="""당신은 숙소 예약 가능 여부 확인 전문 어시스턴트입니다.
    사용자가 특정 날짜에 숙소를 예약할 수 있는지, 어떤 객실이 남아있는지 확인하고 싶어하면 check_availability 도구를 사용하세요.
    
    중요:
    - 사용자가 "예약 가능해?", "빈 방 있어?", "객실 남아있어?" 등의 숙박 예약을 위한 질문을 하면 이 도구를 사용하세요.
    - 체크인/체크아웃 날짜가 필요합니다. 없으면 사용자에게 물어보세요.
    - 룸 타입이나 인원 수는 선택사항이지만, 제공되면 더 정확한 정보를 줄 수 있습니다.
    - 남은 객실이 적으면 빠른 예약을 권장하세요.
    - 매진된 객실이 있으면 다른 객실 타입을 제안하세요.
    - 가격 정보와 총 숙박 비용을 명확히 안내하세요.""",
)

# 테스트
# if __name__ == "__main__":
#     result = agent.invoke({"messages": [{"role": "user", "content": "서울 시티 호텔 12월 25일부터 27일까지 예약 가능해?"}]})
#     print(result['messages'][-1].content)
