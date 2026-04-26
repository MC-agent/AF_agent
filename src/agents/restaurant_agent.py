from langchain_openai import ChatOpenAI
from langchain.tools import tool
from langchain.agents import create_agent
from typing import Any
from src.memory.vector_store import count_place_embeddings, search_place_embeddings
from dotenv import load_dotenv
from openai import OpenAI
import json
import os

from src.config import settings

load_dotenv()
# os.environ["LANGCHAIN_TRACING_V2"] = 'true'
# os.environ["LANGCHAIN_ENDPOINT"] = os.getenv("LANGCHAIN_ENDPOINT")
# os.environ["LANGCHAIN_PROJECT"] = os.getenv("LANGCHAIN_PROJECT")
# os.environ["LANGCHAIN_API_KEY"] = os.getenv("LANGCHAIN_API_KEY")
CHATROUTER = os.getenv("OPENROUTER")
BASE_URL = os.getenv("OPENROUTER_API_BASE")



# LLM 설정
llm = ChatOpenAI(
    api_key=CHATROUTER,
    base_url="https://openrouter.ai/api/v1",
    model="anthropic/claude-sonnet-4.5",
    temperature=0.5
)


def _first_text(*values: Any) -> str:
    for value in values:
        if value is None:
            continue
        if isinstance(value, str):
            text = value.strip()
            if text:
                return text
        elif isinstance(value, (int, float)):
            return str(value)
    return ""


def _load_full_data(entity: dict[str, Any]) -> dict[str, Any]:
    raw = entity.get("full_data")
    if not raw:
        return {}
    if isinstance(raw, dict):
        return raw
    try:
        loaded = json.loads(raw)
    except (TypeError, json.JSONDecodeError):
        return {}
    return loaded if isinstance(loaded, dict) else {}


def _compact_items(items: list[str], limit: int = 3) -> str:
    compacted = [item.strip() for item in items if item and item.strip()]
    return ", ".join(compacted[:limit])


def _menu_summary(place_data: dict[str, Any]) -> str:
    menus = (place_data.get("menu") or {}).get("menus") or []
    menu_names: list[str] = []
    for menu in menus:
        if isinstance(menu, dict):
            name = _first_text(menu.get("name"), menu.get("menu_name"), menu.get("title"))
            price = _first_text(menu.get("price"), menu.get("amount"))
            if name and price:
                menu_names.append(f"{name} {price}")
            elif name:
                menu_names.append(name)
        elif isinstance(menu, str):
            menu_names.append(menu)
    return _compact_items(menu_names, limit=5)


def _review_summary(place_data: dict[str, Any]) -> str:
    reviews = (place_data.get("review") or {}).get("reviews") or []
    snippets: list[str] = []
    for review in reviews:
        if not isinstance(review, dict):
            continue
        content = _first_text(review.get("content"))
        if content:
            snippets.append(content.replace("\n", " ")[:120])
    return _compact_items(snippets, limit=2)


def _format_restaurant_hit(index: int, hit: dict[str, Any]) -> str:
    entity = hit.get("entity", {})
    full_data = _load_full_data(entity)
    basic_info = full_data.get("basic_info") or {}
    home = full_data.get("home") or {}
    location = full_data.get("location") or {}

    name = _first_text(entity.get("name"), basic_info.get("name"), "이름 없음")
    category = _first_text(entity.get("category"), basic_info.get("category"), "카테고리 없음")
    address = _first_text(
        entity.get("address"),
        location.get("road_address"),
        location.get("lot_address"),
        home.get("address_detail"),
        "주소 정보 없음",
    )
    phone = _first_text(
        full_data.get("phone"),
        full_data.get("phone_number"),
        basic_info.get("phone"),
        home.get("phone"),
        "전화번호 정보 없음",
    )
    hours = _first_text(
        full_data.get("business_hours"),
        full_data.get("opening_hours"),
        home.get("business_hours"),
        home.get("opening_hours"),
        home.get("address_detail") if "까지" in _first_text(home.get("address_detail")) or "오픈" in _first_text(home.get("address_detail")) else "",
        "영업시간 정보 없음",
    )
    rating = _first_text(entity.get("rating"), basic_info.get("rating"), "평점 정보 없음")
    services = _compact_items([str(item) for item in home.get("services", [])], limit=6)
    menus = _menu_summary(full_data)
    reviews = _review_summary(full_data)
    distance = hit.get("distance")
    score_line = f"유사도 거리: {float(distance):.4f}" if isinstance(distance, (int, float)) else ""

    lines = [
        f"{index}. {name}",
        f"- 카테고리: {category}",
        f"- 주소: {address}",
        f"- 전화번호: {phone}",
        f"- 영업시간: {hours}",
        f"- 평점: {rating}",
    ]
    if services:
        lines.append(f"- 편의정보: {services}")
    if menus:
        lines.append(f"- 대표 메뉴: {menus}")
    if reviews:
        lines.append(f"- 리뷰 요약: {reviews}")
    if score_line:
        lines.append(f"- {score_line}")

    return "\n".join(lines)

@tool
def restaurant_info(restaurant_name: str) -> str:
    """pgvector에 저장된 식당 정보를 검색합니다. 식당 이름, 음식 종류, 지역을 입력받아 위치, 전화번호, 영업시간, 평점 등의 정보를 반환합니다."""
    query = restaurant_name.strip()
    if not query:
        return "검색어가 비어 있습니다. 식당 이름, 음식 종류 또는 지역을 입력해 주세요."
    if count_place_embeddings(place_type="restaurant") == 0:
        return "pgvector의 kakao_places 테이블에 저장된 식당 데이터가 없습니다. 먼저 식당 크롤링/업로드 파이프라인을 실행해 주세요."
    if not settings.openai_api_key:
        return "OPENAI_API_KEY가 없어 pgvector 검색용 임베딩을 만들 수 없습니다."

    embedding_client = OpenAI(api_key=settings.openai_api_key)
    response = embedding_client.embeddings.create(
        input=query,
        model=settings.embedding_model,
    )
    query_embedding = response.data[0].embedding
    search_results = search_place_embeddings(query_embedding, limit=5, place_type="restaurant")

    if not search_results:
        return f"'{query}'와 관련된 식당 정보를 pgvector에서 찾지 못했습니다."

    formatted_results = [_format_restaurant_hit(index, hit) for index, hit in enumerate(search_results, start=1)]
    return "pgvector 검색 결과입니다.\n\n" + "\n\n".join(formatted_results)


def load_restaurant_agent():
    prompt_text = """
    당신은 사용자의 식당 탐색을 돕는 도우미입니다.
    당신이 사용할 수 있는 도구는 restaurant_info(검색어)입니다. 이 도구는 pgvector에 저장된 카카오맵 식당 데이터를 검색해 식당의 위치, 전화번호, 영업시간, 평점 등의 정보를 반환합니다.
    규칙:
    - 사용자의 입력에서 지역, 음식 종류, 식당 이름을 파악하세요.
    - 식당 이름이 명확하면 해당 식당 정보를 찾으세요.
    - 식당 이름이 없고 지역/종류만 있으면 그 조건에 맞는 식당 후보를 찾으세요.
    - 데이터베이스 검색 결과가 없으면 지어내지 말고 없다고 답하세요.
    - 답변은 짧고 명확하게 정리하세요.
    """
    agent = create_agent(
    model=llm,
    tools=[restaurant_info],
    system_prompt = prompt_text,
    name='restaurant_agent'
    )    

    return agent


# if __name__ == '__main__':
#     user_input = "홍대에 있는 중국집 알려줘"
#     agent = load_restaurant_agent()
#     response = agent.invoke({"messages": [{"role": "user", "content": user_input}]})
#     #response = restaurant_info(user_input)

#     print(response['messages'][-1].content)
