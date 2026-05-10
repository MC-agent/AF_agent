import re
from typing import Any, Dict, Iterable


_REGION_PREFIXES = (
    "서울",
    "부산",
    "대구",
    "인천",
    "광주",
    "대전",
    "울산",
    "세종",
    "경기",
    "강원",
    "충북",
    "충남",
    "전북",
    "전남",
    "경북",
    "경남",
    "제주",
)
_HOURS_PATTERN = re.compile(r"\b\d{1,2}:\d{2}\b")
_HOURS_KEYWORDS = (
    "영업",
    "운영",
    "브레이크타임",
    "라스트오더",
    "휴무",
    "오픈",
    "마감",
)
_POSTCODE_PATTERN = re.compile(r"\s*\(우\)\s*\d{5}\s*$")
_WHITESPACE_PATTERN = re.compile(r"\s+")
_ADDRESS_PATTERN = re.compile(
    r"((?:서울|부산|대구|인천|광주|대전|울산|세종|경기|강원|충북|충남|전북|전남|경북|경남|제주)"
    r"(?:특별시|광역시|특별자치시|특별자치도|도)?\s+"
    r"[^\n|,]{1,80}?"
    r"(?:대로|번길|로|길|동|읍|면|리)\s*\d*(?:-\d+)?"
    r"(?:\s+[^\n|,()]{1,30}){0,4})"
)


def first_text(*values: Any) -> str:
    for value in values:
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return ""


def normalize_address_text(text: Any) -> str:
    candidate = first_text(text)
    if not candidate:
        return ""

    candidate = candidate.replace("\r", " ").replace("\n", " ")
    candidate = _WHITESPACE_PATTERN.sub(" ", candidate).strip(" |,")

    for part in candidate.split("|"):
        section = part.strip()
        lower_section = section.lower()
        if lower_section.startswith("address:"):
            candidate = section.split(":", 1)[1].strip()
            break
        if section.startswith("주소"):
            candidate = section.split(":", 1)[-1].strip()
            break

    candidate = _POSTCODE_PATTERN.sub("", candidate).strip()
    return candidate


def is_probable_hours(text: str) -> bool:
    candidate = normalize_address_text(text)
    if not candidate:
        return False
    if any(keyword in candidate for keyword in _HOURS_KEYWORDS):
        return True
    return bool(_HOURS_PATTERN.search(candidate))


def extract_address_from_text(text: str) -> str:
    candidate = normalize_address_text(text)
    if not candidate:
        return ""

    match = _ADDRESS_PATTERN.search(candidate)
    if match:
        return match.group(1).strip()

    return ""


def looks_like_address(text: str) -> bool:
    candidate = normalize_address_text(text)
    if not candidate or is_probable_hours(candidate):
        return False

    if len(candidate) > 120:
        return False

    if not any(candidate.startswith(prefix) for prefix in _REGION_PREFIXES):
        return False

    return any(token in candidate for token in ("대로", "번길", "로", "길", "동", "읍", "면", "리"))


def is_probable_address(text: str) -> bool:
    candidate = normalize_address_text(text)
    if not candidate or is_probable_hours(candidate):
        return False

    if extract_address_from_text(candidate):
        return True

    return looks_like_address(candidate)


def iter_address_source_texts(place_data: Dict[str, Any]) -> Iterable[str]:
    home = place_data.get("home") or {}
    yield first_text(home.get("address_detail"))

    location = place_data.get("location") or {}
    yield first_text(location.get("road_address"))
    yield first_text(location.get("lot_address"))

    yield first_text(
        place_data.get("address"),
        place_data.get("road_address_name"),
        place_data.get("address_name"),
    )

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
        normalized = normalize_address_text(candidate)
        if not normalized or is_probable_hours(normalized):
            continue

        extracted = extract_address_from_text(normalized)
        if extracted:
            return extracted

        if looks_like_address(normalized):
            return normalized

    return ""
