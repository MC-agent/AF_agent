import re
from typing import Any, Dict, Iterable


_ADDRESS_PREFIX = (
    r"(?:서울(?:특별시)?|부산(?:광역시)?|대구(?:광역시)?|인천(?:광역시)?|광주(?:광역시)?|"
    r"대전(?:광역시)?|울산(?:광역시)?|세종(?:특별자치시)?|경기(?:도)?|강원(?:특별자치도|도)?|"
    r"충북|충남|전북|전남|경북|경남|제주(?:특별자치도)?)"
)
_ADDRESS_PATTERN = re.compile(
    rf"({_ADDRESS_PREFIX}\s+[가-힣a-zA-Z0-9\-\s]+?(?:로|길|동|읍|면|리|대로)\s+\d+(?:-\d+)?(?:[,\s\w()]+)?)"
)
_HOURS_PATTERN = re.compile(r"\b\d{1,2}:\d{2}\b")
_HOURS_KEYWORDS = (
    "영업",
    "운영",
    "브레이크타임",
    "라스트오더",
    "휴무",
    "까지",
    "오픈",
    "마감",
)


def first_text(*values: Any) -> str:
    for value in values:
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return ""


def is_probable_hours(text: str) -> bool:
    candidate = text.strip()
    if not candidate:
        return False
    if any(keyword in candidate for keyword in _HOURS_KEYWORDS):
        return True
    return bool(_HOURS_PATTERN.search(candidate))


def extract_address_from_text(text: str) -> str:
    if not text:
        return ""
    match = _ADDRESS_PATTERN.search(text)
    if not match:
        return ""
    return match.group(1).strip()


def is_probable_address(text: str) -> bool:
    candidate = text.strip()
    if not candidate or is_probable_hours(candidate):
        return False
    if extract_address_from_text(candidate):
        return True
    if "주소" in candidate and extract_address_from_text(candidate.replace("주소", " ")):
        return True
    return False


def iter_address_source_texts(place_data: Dict[str, Any]) -> Iterable[str]:
    # 크롤링 데이터에서만 주소를 가져옴 (카카오 API 필드는 사용하지 않음)
    home = place_data.get("home") or {}
    yield first_text(home.get("address_detail"))

    location = place_data.get("location") or {}
    yield first_text(location.get("road_address"))
    yield first_text(location.get("lot_address"))

    blog_reviews = (place_data.get("blog_review") or {}).get("blog_reviews", [])
    for blog in blog_reviews:
        yield first_text(blog.get("content"))
        yield first_text(blog.get("title"))

    reviews = (place_data.get("review") or {}).get("reviews", [])
    for review in reviews:
        yield first_text(review.get("content"))

    yield first_text(place_data.get("text_content"))


def resolve_place_address(place_data: Dict[str, Any]) -> str:
    for candidate in iter_address_source_texts(place_data):
        if is_probable_address(candidate):
            extracted = extract_address_from_text(candidate)
            return extracted or candidate.strip()
    return ""
