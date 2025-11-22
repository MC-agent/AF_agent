from langchain_openai import ChatOpenAI
from dotenv import load_dotenv
import os
from langgraph.prebuilt import create_react_agent
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain.tools import tool
from typing import Optional, List
import json
from pathlib import Path
from datetime import datetime, timedelta

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

def calculate_price_with_weekday_weekend(base_price: int, check_in: str, check_out: str) -> dict:
    """체크인/체크아웃 날짜에 따라 주중/주말 가격을 계산합니다.
    
    주말(금요일, 토요일)은 기본 가격의 30% 할증
    주중(일~목)은 기본 가격 적용
    """
    check_in_date = datetime.strptime(check_in, "%Y-%m-%d")
    check_out_date = datetime.strptime(check_out, "%Y-%m-%d")
    
    total_price = 0
    weekday_nights = 0
    weekend_nights = 0
    night_details = []
    
    current_date = check_in_date
    while current_date < check_out_date:
        # 금요일(4), 토요일(5)은 주말 요금
        if current_date.weekday() in [4, 5]:  # Friday, Saturday
            night_price = int(base_price * 1.3)
            weekend_nights += 1
            night_details.append({
                "date": current_date.strftime("%Y-%m-%d"),
                "day": current_date.strftime("%A"),
                "type": "주말",
                "price": night_price
            })
        else:
            night_price = base_price
            weekday_nights += 1
            night_details.append({
                "date": current_date.strftime("%Y-%m-%d"),
                "day": current_date.strftime("%A"),
                "type": "주중",
                "price": night_price
            })
        
        total_price += night_price
        current_date += timedelta(days=1)
    
    return {
        "total_price": total_price,
        "weekday_nights": weekday_nights,
        "weekend_nights": weekend_nights,
        "night_details": night_details,
        "base_price": base_price
    }

@tool
def compare_prices(
    location: str,
    check_in: str,
    check_out: str,
    guests: Optional[int] = 2,
    accommodation_type: Optional[str] = None,
    max_results: Optional[int] = 5
) -> str:
    """여러 숙소의 가격을 비교하고, 주중/주말 가격 차이를 분석합니다.
    지역 내 여러 숙소의 가격을 한눈에 비교하고 최저가 숙소를 찾아줍니다.
    
    Args:
        location: 검색할 지역 (예: "서울", "부산", "제주도")
        check_in: 체크인 날짜 (YYYY-MM-DD 형식)
        check_out: 체크아웃 날짜 (YYYY-MM-DD 형식)
        guests: 투숙 인원 (기본값: 2명)
        accommodation_type: 숙소 타입 필터 (선택사항: "호텔", "게스트하우스", "리조트", "펜션")
        max_results: 비교할 최대 숙소 수 (기본값: 5개)
    
    Returns:
        각 숙소의 총 가격, 주중/주말 가격 차이, 최저가 정보
    """
    
    # mock 데이터를 JSON 파일에서 로드
    mock_file_path = Path(__file__).parent.parent / "mock" / "room.json"
    with open(mock_file_path, 'r', encoding='utf-8') as f:
        mock_accommodations = json.load(f)
    
    # 위치에 해당하는 숙소 찾기
    accommodations = mock_accommodations.get(location, [])
    
    if not accommodations:
        return f"'{location}' 지역에서 검색된 숙소가 없습니다. 다른 지역을 검색해보세요. (예: 서울, 부산, 제주도)"
    
    # 날짜 검증
    try:
        check_in_date = datetime.strptime(check_in, "%Y-%m-%d")
        check_out_date = datetime.strptime(check_out, "%Y-%m-%d")
        nights = (check_out_date - check_in_date).days
        
        if nights <= 0:
            return "체크아웃 날짜는 체크인 날짜보다 이후여야 합니다."
    except ValueError:
        return "날짜 형식이 올바르지 않습니다. YYYY-MM-DD 형식으로 입력해주세요."
    
    # 숙소 타입 필터링
    if accommodation_type:
        accommodations = [acc for acc in accommodations if acc["type"] == accommodation_type]
        
        if not accommodations:
            return f"'{location}' 지역에 '{accommodation_type}' 타입의 숙소가 없습니다."
    
    # 각 숙소의 가격 계산
    price_comparisons = []
    
    for acc in accommodations[:max_results]:
        base_price = acc["price"]
        
        # 주중/주말 가격 계산
        price_info = calculate_price_with_weekday_weekend(base_price, check_in, check_out)
        
        price_comparisons.append({
            "name": acc["name"],
            "type": acc["type"],
            "rating": acc["rating"],
            "address": acc["address"],
            "base_price": base_price,
            "total_price": price_info["total_price"],
            "weekday_nights": price_info["weekday_nights"],
            "weekend_nights": price_info["weekend_nights"],
            "night_details": price_info["night_details"],
            "amenities": acc.get("amenities", [])
        })
    
    # 가격순으로 정렬
    price_comparisons.sort(key=lambda x: x["total_price"])
    
    # 결과 포맷팅
    result = f"💰 {location} 지역 숙소 가격 비교\n"
    result += f"📅 체크인: {check_in} | 체크아웃: {check_out} ({nights}박)\n"
    result += f"👥 인원: {guests}명\n"
    if accommodation_type:
        result += f"🏨 타입: {accommodation_type}\n"
    result += "\n"
    
    # 주중/주말 구성 요약
    first_acc = price_comparisons[0]
    if first_acc["weekday_nights"] > 0 and first_acc["weekend_nights"] > 0:
        result += f"📊 숙박 구성: 주중 {first_acc['weekday_nights']}박 + 주말 {first_acc['weekend_nights']}박\n"
        result += f"💡 주말 요금은 기본 요금의 130% 적용됩니다.\n\n"
    elif first_acc["weekend_nights"] > 0:
        result += f"📊 숙박 구성: 주말 {first_acc['weekend_nights']}박\n"
        result += f"💡 주말 요금은 기본 요금의 130% 적용됩니다.\n\n"
    else:
        result += f"📊 숙박 구성: 주중 {first_acc['weekday_nights']}박\n\n"
    
    result += "=" * 50 + "\n\n"
    
    # 각 숙소별 가격 정보
    for idx, acc in enumerate(price_comparisons, 1):
        if idx == 1:
            result += f"🏆 {idx}. {acc['name']} ({acc['type']}) - ⭐ 최저가!\n"
        else:
            result += f"{idx}. {acc['name']} ({acc['type']})\n"
        
        result += f"   📍 위치: {acc['address']}\n"
        result += f"   ⭐ 평점: {acc['rating']}/5.0\n"
        result += f"   💰 기본 1박 요금: ₩{acc['base_price']:,}\n"
        
        # 주중/주말 가격 상세
        if acc["weekday_nights"] > 0 and acc["weekend_nights"] > 0:
            weekday_total = acc["base_price"] * acc["weekday_nights"]
            weekend_total = int(acc["base_price"] * 1.3) * acc["weekend_nights"]
            result += f"      • 주중 {acc['weekday_nights']}박: ₩{weekday_total:,} (₩{acc['base_price']:,}/박)\n"
            result += f"      • 주말 {acc['weekend_nights']}박: ₩{weekend_total:,} (₩{int(acc['base_price'] * 1.3):,}/박)\n"
        elif acc["weekend_nights"] > 0:
            result += f"      • 주말 {acc['weekend_nights']}박: ₩{int(acc['base_price'] * 1.3):,}/박\n"
        else:
            result += f"      • 주중 {acc['weekday_nights']}박: ₩{acc['base_price']:,}/박\n"
        
        result += f"   💵 총 숙박 비용: ₩{acc['total_price']:,}\n"
        result += f"   ✨ 편의시설: {', '.join(acc['amenities'][:4])}\n"
        
        # 최저가 대비 가격 차이
        if idx > 1:
            price_diff = acc['total_price'] - price_comparisons[0]['total_price']
            result += f"   📈 최저가 대비: +₩{price_diff:,}\n"
        
        result += "\n"
    
    # 가격 요약 및 추천
    result += "=" * 50 + "\n\n"
    result += "📌 가격 요약:\n"
    result += f"   🏆 최저가: {price_comparisons[0]['name']} - ₩{price_comparisons[0]['total_price']:,}\n"
    result += f"   💸 최고가: {price_comparisons[-1]['name']} - ₩{price_comparisons[-1]['total_price']:,}\n"
    
    price_range = price_comparisons[-1]['total_price'] - price_comparisons[0]['total_price']
    result += f"   📊 가격 차이: ₩{price_range:,}\n\n"
    
    # 가성비 추천
    result += "💡 추천:\n"
    
    # 최저가 추천
    best_price = price_comparisons[0]
    result += f"   💰 가장 저렴한 숙소: {best_price['name']} (₩{best_price['total_price']:,})\n"
    
    # 가성비 추천 (가격 대비 평점)
    value_scores = [(acc, acc['rating'] / (acc['total_price'] / 100000)) for acc in price_comparisons]
    value_scores.sort(key=lambda x: x[1], reverse=True)
    best_value = value_scores[0][0]
    
    if best_value['name'] != best_price['name']:
        result += f"   ⭐ 가성비 최고: {best_value['name']} (평점 {best_value['rating']}, ₩{best_value['total_price']:,})\n"
    
    # 날짜별 상세 가격 (첫 번째 숙소 기준 - 선택사항)
    result += f"\n📅 날짜별 가격 상세 ({price_comparisons[0]['name']} 기준):\n"
    for night in price_comparisons[0]['night_details']:
        day_kr = {
            "Monday": "월", "Tuesday": "화", "Wednesday": "수", 
            "Thursday": "목", "Friday": "금", "Saturday": "토", "Sunday": "일"
        }.get(night['day'], night['day'])
        
        result += f"   • {night['date']} ({day_kr}) - {night['type']}: ₩{night['price']:,}\n"
    
    return result

# Agent 생성
agent = create_react_agent(
    model=llm,
    tools=[compare_prices],
    prompt="""당신은 숙소 가격 비교 전문 어시스턴트입니다.
    사용자가 여러 숙소의 가격을 비교하고 싶어하거나, 최저가를 찾고 싶어하면 compare_prices 도구를 사용하세요.
    
    중요:
    - 사용자가 "가격 비교해줘", "얼마나 차이나?", "최저가 어디야?", "가장 싼 곳은?" 등의 질문을 하면 이 도구를 사용하세요.
    - 지역과 체크인/체크아웃 날짜가 필요합니다. 없으면 사용자에게 물어보세요.
    - 주중과 주말 가격 차이를 명확하게 설명해주세요.
    - 최저가뿐만 아니라 가성비(가격 대비 평점)도 함께 추천해주세요.
    - 가격 차이가 크면 왜 그런지 설명해주세요 (시설, 위치, 평점 등).
    - 날짜를 조정하면 가격을 절약할 수 있는 팁도 제공하세요.""",
)

# 테스트
if __name__ == "__main__":
    # 주중+주말 혼합 테스트 (금요일~일요일)
    result = agent.invoke({"messages": [{"role": "user", "content": "서울 지역 숙소 12월 20일부터 22일까지 가격 비교해줘"}]})
    print(result['messages'][-1].content)
