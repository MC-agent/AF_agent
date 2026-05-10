from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Optional

from openai import OpenAI

from src.config import settings
from src.memory.vector_store import count_place_embeddings, search_place_embeddings


NO_ACCOMMODATION_DATA = (
    "pgvector의 kakao_places 테이블에 저장된 숙소 데이터가 없습니다. "
    "먼저 숙소 크롤링/업로드 파이프라인을 실행해 주세요."
)


def first_text(*values: Any) -> str:
    for value in values:
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return ""


def load_full_data(entity: dict[str, Any]) -> dict[str, Any]:
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


def search_accommodations(query: str, limit: int = 5) -> tuple[list[dict[str, Any]], Optional[str]]:
    if count_place_embeddings(place_type="accommodation") == 0:
        return [], NO_ACCOMMODATION_DATA
    if not settings.openai_api_key:
        return [], "OPENAI_API_KEY가 없어 pgvector 검색용 임베딩을 만들 수 없습니다."

    try:
        embedding_client = OpenAI(api_key=settings.openai_api_key)
        response = embedding_client.embeddings.create(
            input=query,
            model=settings.embedding_model,
        )
    except Exception as exc:
        return [], f"pgvector 검색용 임베딩 생성에 실패했습니다: {exc}"

    results = search_place_embeddings(
        response.data[0].embedding,
        limit=limit,
        place_type="accommodation",
    )
    return results, None


def entity_name(entity: dict[str, Any], full_data: Optional[dict[str, Any]] = None) -> str:
    full_data = full_data or load_full_data(entity)
    basic_info = full_data.get("basic_info") or {}
    return first_text(entity.get("name"), basic_info.get("name"), "이름 없음")


def entity_address(entity: dict[str, Any], full_data: Optional[dict[str, Any]] = None) -> str:
    full_data = full_data or load_full_data(entity)
    home = full_data.get("home") or {}
    location = full_data.get("location") or {}
    return first_text(
        entity.get("address"),
        location.get("road_address"),
        location.get("lot_address"),
        home.get("address_detail"),
        "주소 정보 없음",
    )


def entity_category(entity: dict[str, Any], full_data: Optional[dict[str, Any]] = None) -> str:
    full_data = full_data or load_full_data(entity)
    basic_info = full_data.get("basic_info") or {}
    return first_text(entity.get("category"), basic_info.get("category"), "카테고리 정보 없음")


def entity_rating(entity: dict[str, Any], full_data: Optional[dict[str, Any]] = None) -> str:
    full_data = full_data or load_full_data(entity)
    basic_info = full_data.get("basic_info") or {}
    return first_text(entity.get("rating"), basic_info.get("rating"), "평점 정보 없음")


def entity_phone(full_data: dict[str, Any]) -> str:
    basic_info = full_data.get("basic_info") or {}
    home = full_data.get("home") or {}
    return first_text(
        full_data.get("phone"),
        full_data.get("phone_number"),
        basic_info.get("phone"),
        home.get("phone"),
        "전화번호 정보 없음",
    )


def entity_hours(full_data: dict[str, Any]) -> str:
    home = full_data.get("home") or {}
    address_detail = first_text(home.get("address_detail"))
    address_detail_hours = address_detail if "까지" in address_detail or "오픈" in address_detail else ""
    return first_text(
        full_data.get("business_hours"),
        full_data.get("opening_hours"),
        home.get("business_hours"),
        home.get("opening_hours"),
        address_detail_hours,
        "운영시간 정보 없음",
    )


def compact_items(items: list[str], limit: int = 5) -> str:
    compacted = [item.strip() for item in items if item and item.strip()]
    return ", ".join(compacted[:limit])


def services_summary(full_data: dict[str, Any]) -> str:
    home = full_data.get("home") or {}
    services = home.get("services") or full_data.get("services") or []
    if not isinstance(services, list):
        return first_text(services)
    return compact_items([str(item) for item in services], limit=8)


def reviews_summary(full_data: dict[str, Any]) -> str:
    reviews = (full_data.get("review") or {}).get("reviews") or full_data.get("reviews") or []
    snippets: list[str] = []
    for review in reviews:
        if isinstance(review, dict):
            content = first_text(review.get("content"), review.get("comment"))
        else:
            content = first_text(review)
        if content:
            snippets.append(content.replace("\n", " ")[:120])
    return compact_items(snippets, limit=3)


def format_accommodation_hit(index: int, hit: dict[str, Any]) -> str:
    entity = hit.get("entity", {})
    full_data = load_full_data(entity)
    distance = hit.get("distance")
    distance_line = f"- 유사도 거리: {float(distance):.4f}" if isinstance(distance, (int, float)) else ""
    lines = [
        f"{index}. {entity_name(entity, full_data)}",
        f"- 카테고리: {entity_category(entity, full_data)}",
        f"- 주소: {entity_address(entity, full_data)}",
        f"- 전화번호: {entity_phone(full_data)}",
        f"- 운영시간: {entity_hours(full_data)}",
        f"- 평점: {entity_rating(entity, full_data)}",
    ]
    services = services_summary(full_data)
    reviews = reviews_summary(full_data)
    if services:
        lines.append(f"- 편의정보: {services}")
    if reviews:
        lines.append(f"- 리뷰 요약: {reviews}")
    if distance_line:
        lines.append(distance_line)
    return "\n".join(lines)


def find_best_accommodation(query: str) -> tuple[Optional[dict[str, Any]], Optional[str]]:
    results, error = search_accommodations(query, limit=1)
    if error:
        return None, error
    if not results:
        return None, f"'{query}'와 관련된 숙소 정보를 pgvector에서 찾지 못했습니다."
    return results[0], None


def parse_nights(check_in: str, check_out: str) -> tuple[Optional[int], Optional[str]]:
    try:
        check_in_date = datetime.strptime(check_in, "%Y-%m-%d")
        check_out_date = datetime.strptime(check_out, "%Y-%m-%d")
    except ValueError:
        return None, "날짜 형식이 올바르지 않습니다. YYYY-MM-DD 형식으로 입력해주세요."

    nights = (check_out_date - check_in_date).days
    if nights <= 0:
        return None, "체크아웃 날짜는 체크인 날짜보다 이후여야 합니다."
    return nights, None
