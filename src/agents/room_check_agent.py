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
from datetime import datetime
import random

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
    
    # room_types 정보가 없는 경우
    if "room_types" not in accommodation:
        return f"'{accommodation['name']}'의 객실 정보가 아직 등록되지 않았습니다."
    
    # 날짜 검증
    try:
        check_in_date = datetime.strptime(check_in, "%Y-%m-%d")
        check_out_date = datetime.strptime(check_out, "%Y-%m-%d")
        nights = (check_out_date - check_in_date).days
        
        if nights <= 0:
            return "체크아웃 날짜는 체크인 날짜보다 이후여야 합니다."
    except ValueError:
        return "날짜 형식이 올바르지 않습니다. YYYY-MM-DD 형식으로 입력해주세요."
    
    room_types = accommodation.get("room_types", [])
    
    # 결과 포맷팅
    result = f"🏨 {accommodation['name']} 예약 가능 여부\n"
    result += f"📍 위치: {accommodation['address']}\n"
    result += f"📅 체크인: {check_in} | 체크아웃: {check_out} ({nights}박)\n"
    if guests:
        result += f"👥 인원: {guests}명\n"
    result += "\n"
    
    available_rooms = []
    
    # 각 룸 타입별로 예약 가능 여부 확인
    for room in room_types:
        # 특정 룸 타입만 조회하는 경우
        if room_type and room_type.lower() not in room["type"].lower():
            continue
        
        # 인원 수 필터링
        if guests and room["max_guests"] < guests:
            continue
        
        # 실시간 예약 가능 객실 수 시뮬레이션 (랜덤)
        # 실제로는 DB에서 조회해야 하지만, mock 데이터이므로 랜덤 생성
        total_rooms = room["total_rooms"]
        
        # 예약률: 50~90% 사이로 랜덤 설정
        random.seed(hash(accommodation['name'] + room['type'] + check_in))
        booking_rate = random.uniform(0.5, 0.9)
        booked_rooms = int(total_rooms * booking_rate)
        available = total_rooms - booked_rooms
        
        room_info = {
            "type": room["type"],
            "price": room["price"],
            "available": available,
            "total": total_rooms,
            "max_guests": room["max_guests"],
            "bed_type": room["bed_type"],
            "size_sqm": room["size_sqm"],
            "amenities": room["amenities"],
            "view": room["view"]
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
        if room_info["available"] > 0:
            status = "✅ 예약 가능"
        elif room_info["available"] == 0:
            status = "❌ 매진"
        else:
            status = "⚠️  마감 임박"
        
        result += f"{idx}. {room_info['type']} - {status}\n"
        result += f"   💰 가격: ₩{room_info['price']:,} / 1박 (총 {nights}박: ₩{room_info['price'] * nights:,})\n"
        result += f"   🛏️  침대: {room_info['bed_type']}\n"
        result += f"   👥 최대 인원: {room_info['max_guests']}명\n"
        result += f"   📐 면적: {room_info['size_sqm']}㎡\n"
        result += f"   🪟 뷰: {room_info['view']}\n"
        result += f"   🔢 남은 객실: {room_info['available']}개 / 전체 {room_info['total']}개\n"
        result += f"   ✨ 편의시설: {', '.join(room_info['amenities'][:4])}\n"
        
        if room_info["available"] <= 3 and room_info["available"] > 0:
            result += f"   ⚠️  인기 객실! 얼마 남지 않았습니다.\n"
        
        result += "\n"
    
    # 총 예약 가능 객실 수 요약
    total_available = sum(r["available"] for r in available_rooms)
    result += f"📊 총 예약 가능 객실: {total_available}개\n"
    
    if total_available == 0:
        result += "\n⚠️  해당 날짜에 예약 가능한 객실이 없습니다. 다른 날짜를 검색해보세요.\n"
    elif total_available <= 5:
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
if __name__ == "__main__":
    result = agent.invoke({"messages": [{"role": "user", "content": "서울 시티 호텔 12월 25일부터 27일까지 예약 가능해?"}]})
    print(result['messages'][-1].content)

