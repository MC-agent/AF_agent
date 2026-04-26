# -*- coding: utf-8 -*-
"""카카오맵 가게 상세 정보를 카카오 내부 JSON API로 가져오는 크롤러."""

import json
import logging
import time
from typing import Any, Dict, List, Optional

import requests


logger = logging.getLogger(__name__)

# 카카오 내부 장소 API 엔드포인트 베이스 (브라우저가 실제로 호출하는 주소)
_API_BASE = "https://place-api.map.kakao.com"

# 카카오 API가 200을 돌려주기 위해 반드시 필요한 헤더 묶음.
# Origin 이 빠지면 406 Not Acceptable 이 떨어진다.
_DEFAULT_HEADERS: Dict[str, str] = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "pf": "PC",
    "Origin": "https://place.map.kakao.com",
    "Referer": "https://place.map.kakao.com/",
    "Accept": "application/json, text/plain, */*",
    "appversion": "6.6.0",
}

# 다운스트림 파이프라인이 기대하는 상한값 (review_*: 10, blog_*: 5).
# panel3 가 이 만큼을 인라인으로 못 주면 별도 탭 엔드포인트를 한 번 호출해서 채운다.
_REVIEW_CAP = 10
_BLOG_CAP = 5
_PHOTO_CAP = 20

# 호출 간 짧은 대기 (한 IP 에서 너무 빠르게 때리는 인상을 피하기 위함)
_INTER_PLACE_DELAY_SECONDS = 0.3


class KakaoMapCrawler:
    """카카오맵 장소 상세를 내부 JSON API 로 수집하는 크롤러."""

    def __init__(self, headless: bool = True):
        # headless 인자는 과거 Playwright 시그니처 호환을 위해 남겨둠 (실제로는 사용 안 함)
        self.headless = headless
        self.base_url = _API_BASE
        # 세션 한 개를 재사용해서 TCP/TLS 연결을 아낀다
        self.session = requests.Session()
        self.session.headers.update(_DEFAULT_HEADERS)

    # ──────────────────────────────────────────────────────────────────
    # 공개 메서드
    # ──────────────────────────────────────────────────────────────────

    def crawl_place_detail(self, place_id: str) -> Dict[str, Any]:
        """장소 ID 하나의 상세 정보를 수집해 파이프라인이 기대하는 형태로 반환한다."""
        place_id_str = str(place_id)
        panel = self._fetch_panel3(place_id_str)

        if panel is None:
            # 응답을 못 받았을 때는 다운스트림이 깨지지 않도록 빈 골격을 돌려준다
            return self._empty_payload(place_id_str)

        # panel3 가 인라인으로 주는 첫 페이지 분량
        kmap_inline = (panel.get("kakaomap_review") or {}).get("reviews") or []
        blog_inline = (panel.get("blog_review") or {}).get("reviews") or []

        # 부족할 때만 탭 엔드포인트를 한 번 더 호출해서 부족분을 보충한다
        kakaomap_reviews = kmap_inline
        if len(kakaomap_reviews) < _REVIEW_CAP:
            extra = self._fetch_kakaomap_reviews(place_id_str)
            if extra:
                kakaomap_reviews = extra

        blog_reviews = blog_inline
        if len(blog_reviews) < _BLOG_CAP:
            extra_blog = self._fetch_blog_reviews(place_id_str)
            if extra_blog:
                blog_reviews = extra_blog

        # 다운스트림이 읽는 스키마(basic_info / home / menu / review / blog_review / photo / location) 구성
        result: Dict[str, Any] = {
            "place_id": place_id_str,
            "basic_info": self._build_basic_info(panel),
            "home": self._build_home(panel),
            "menu": self._build_menu(panel),
            "review": self._build_review(kakaomap_reviews, panel),
            "blog_review": self._build_blog_review(blog_reviews),
            "photo": self._build_photo(panel),
            "location": self._build_location(panel),
        }
        return result

    def crawl_multiple_places(self, place_ids: List[str]) -> List[Dict[str, Any]]:
        """여러 place_id 를 순회하며 상세를 모은다 (호출 간 짧은 대기 포함)."""
        results: List[Dict[str, Any]] = []
        total = len(place_ids)
        for index, place_id in enumerate(place_ids, start=1):
            print(f"크롤링 중 ({index}/{total}): {place_id}")
            try:
                results.append(self.crawl_place_detail(place_id))
                print(f"완료: {place_id}")
            except Exception as exc:  # pragma: no cover - 안전망
                logger.warning("place_id=%s 크롤링 실패: %s", place_id, exc)
                results.append(self._empty_payload(str(place_id)))
            # 마지막 항목 뒤에는 굳이 자지 않는다
            if index < total:
                time.sleep(_INTER_PLACE_DELAY_SECONDS)
        return results

    def save_to_json(self, data: Any, filename: str) -> None:
        """수집한 결과를 JSON 으로 떨궈주는 헬퍼."""
        with open(filename, "w", encoding="utf-8") as file:
            json.dump(data, file, ensure_ascii=False, indent=2)
        print(f"데이터 저장 완료: {filename}")

    # ──────────────────────────────────────────────────────────────────
    # 내부 HTTP 호출
    # ──────────────────────────────────────────────────────────────────

    def _fetch_panel3(self, place_id: str) -> Optional[Dict[str, Any]]:
        """panel3 마스터 페이로드를 가져온다 (실패 시 None)."""
        # 카카오가 panel3 → panel4 식으로 버전을 올려도 같은 함수에서 안전하게 실패하도록 try 로 감쌈
        url = f"{self.base_url}/places/panel3/{place_id}"
        return self._get_json(url, place_id, label="panel3")

    def _fetch_kakaomap_reviews(self, place_id: str) -> List[Dict[str, Any]]:
        """카카오맵 리뷰 탭 첫 페이지를 가져와서 reviews 배열만 꺼낸다."""
        url = (
            f"{self.base_url}/places/tab/reviews/kakaomap/{place_id}"
            "?order=RECOMMENDED&only_photo_review=false"
        )
        data = self._get_json(url, place_id, label="kakaomap reviews")
        if not data:
            return []
        return data.get("reviews") or []

    def _fetch_blog_reviews(self, place_id: str) -> List[Dict[str, Any]]:
        """블로그 리뷰 탭 1페이지를 가져와서 reviews 배열만 꺼낸다."""
        url = f"{self.base_url}/places/tab/reviews/blog/{place_id}?page=1"
        data = self._get_json(url, place_id, label="blog reviews")
        if not data:
            return []
        return data.get("reviews") or []

    def _get_json(self, url: str, place_id: str, label: str) -> Optional[Dict[str, Any]]:
        """공통 GET → JSON 변환. 실패하면 경고 로깅 후 None 반환."""
        try:
            response = self.session.get(url, timeout=10)
        except requests.RequestException as exc:
            logger.warning("place_id=%s %s 호출 네트워크 오류: %s", place_id, label, exc)
            return None

        if response.status_code != 200:
            logger.warning(
                "place_id=%s %s 비정상 상태코드: %s",
                place_id,
                label,
                response.status_code,
            )
            return None

        try:
            return response.json()
        except ValueError as exc:
            logger.warning("place_id=%s %s JSON 파싱 실패: %s", place_id, label, exc)
            return None

    # ──────────────────────────────────────────────────────────────────
    # 빈 골격 (기존 크롤러도 실패 시 빈 dict 를 반환했음)
    # ──────────────────────────────────────────────────────────────────

    @staticmethod
    def _empty_payload(place_id: str) -> Dict[str, Any]:
        """API 호출이 모두 실패했을 때 다운스트림이 안전하게 스킵하도록 비워서 반환."""
        return {
            "place_id": place_id,
            "basic_info": {},
            "home": {},
            "menu": {"menus": []},
            "review": {"reviews": []},
            "blog_review": {"blog_reviews": []},
            "photo": {"photos": []},
            "location": {},
        }

    # ──────────────────────────────────────────────────────────────────
    # 섹션별 빌더 (panel3 응답 → 다운스트림 스키마 변환)
    # ──────────────────────────────────────────────────────────────────

    @staticmethod
    def _build_basic_info(panel: Dict[str, Any]) -> Dict[str, Any]:
        """basic_info: 가게명 / 카테고리 / 평점 / 후기수 / 블로그수."""
        summary = panel.get("summary") or {}
        category = summary.get("category") or {}
        score_set = (panel.get("kakaomap_review") or {}).get("score_set") or {}
        blog_block = panel.get("blog_review") or {}

        # 카테고리는 가장 세부 분류명을 우선 (기존 크롤러가 표시하던 .info_cate 와 동일 지점)
        category_name = (
            category.get("name")
            or category.get("name3")
            or category.get("name2")
            or category.get("name1")
            or ""
        )

        # 평점/후기수가 없으면 빈 문자열로 두고, 있으면 문자열로 통일 (기존 크롤러 출력과 같은 모양)
        average_score = score_set.get("average_score")
        rating = "" if average_score in (None, "") else str(average_score)

        review_count_value = score_set.get("review_count")
        review_count = "" if review_count_value in (None, "") else f"{review_count_value}개"

        blog_count_value = blog_block.get("review_count")
        blog_count = "" if blog_count_value in (None, "") else f"{blog_count_value}개"

        basic_info: Dict[str, Any] = {
            "name": summary.get("name") or "",
            "category": category_name,
            "rating": rating,
            "review_count": review_count,
            "blog_count": blog_count,
        }
        return basic_info

    @staticmethod
    def _build_home(panel: Dict[str, Any]) -> Dict[str, Any]:
        """home: 홈페이지 / 도로명 주소(detail) / 서비스 태그."""
        summary = panel.get("summary") or {}
        address = summary.get("address") or {}
        homepages = summary.get("homepages") or []
        place_add_info = panel.get("place_add_info") or {}

        home: Dict[str, Any] = {}

        if homepages:
            home["homepage"] = homepages[0]

        # 다운스트림(resolve_place_address)이 가장 먼저 보는 필드 - 깨끗한 도로명 주소를 직접 채워준다
        address_disp = address.get("disp") or address.get("road") or ""
        if address_disp:
            home["address_detail"] = address_disp

        # 서비스 태그: place_add_info.tags 또는 store_facility_icons 의 텍스트
        services: List[str] = []
        ai_mate = place_add_info.get("ai_mate") or {}
        for icon in (ai_mate.get("store_facility_icons") or []):
            text = icon.get("text") if isinstance(icon, dict) else None
            if text:
                services.append(text)
        if not services:
            for icon in (place_add_info.get("store_facility_icons") or []):
                text = icon.get("text") if isinstance(icon, dict) else None
                if text:
                    services.append(text)
        if services:
            home["services"] = services

        return home

    @staticmethod
    def _build_menu(panel: Dict[str, Any]) -> Dict[str, Any]:
        """menu: panel3 의 menu.menus.items 를 [{name, price, description}] 으로 평탄화."""
        menu_block = panel.get("menu") or {}
        inner = menu_block.get("menus") or {}
        # API 가 menu 자체를 안 주는 케이스(호텔 등)는 빈 리스트
        items = inner.get("items") if isinstance(inner, dict) else None
        if not items:
            return {"menus": []}

        normalized: List[Dict[str, Any]] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            name = item.get("name") or ""
            price_raw = item.get("price")
            price = "" if price_raw in (None, "") else str(price_raw)
            description = item.get("ai_mate_desc") or item.get("description") or ""
            if name or price:
                normalized.append({
                    "name": name,
                    "price": price,
                    "description": description,
                })
        return {"menus": normalized}

    @staticmethod
    def _build_review(reviews: List[Dict[str, Any]], panel: Dict[str, Any]) -> Dict[str, Any]:
        """review: 카카오맵 리뷰를 author/rating/date/content 로 정리하고 10개로 자른다."""
        score_set = (panel.get("kakaomap_review") or {}).get("score_set") or {}
        average_score = score_set.get("average_score")

        normalized: List[Dict[str, Any]] = []
        for raw in (reviews or [])[:_REVIEW_CAP]:
            if not isinstance(raw, dict):
                continue
            owner = ((raw.get("meta") or {}).get("owner")) or {}
            author = owner.get("nickname") or ""

            star_rating = raw.get("star_rating")
            rating = "" if star_rating in (None, "") else str(star_rating)

            date_full = raw.get("registered_at") or raw.get("updated_at") or ""
            # registered_at 이 'YYYY-MM-DD HH:MM:SS' 형태이면 날짜 부분만 사용
            date_only = date_full.split(" ", 1)[0] if isinstance(date_full, str) else ""

            content = raw.get("contents") or ""

            normalized.append({
                "author": author,
                "rating": rating,
                "date": date_only,
                "content": content,
            })

        # 평균 평점은 panel3 의 score_set 값을 그대로 살려두는 게 다운스트림에 도움이 됨
        return {
            "reviews": normalized,
            "average_score": "" if average_score in (None, "") else str(average_score),
        }

    @staticmethod
    def _build_blog_review(blog_reviews: List[Dict[str, Any]]) -> Dict[str, Any]:
        """blog_review: 블로그 리뷰를 title/content/url 로 정리하고 5개로 자른다."""
        normalized: List[Dict[str, Any]] = []
        for raw in (blog_reviews or [])[:_BLOG_CAP]:
            if not isinstance(raw, dict):
                continue
            title = raw.get("title") or ""
            content = raw.get("contents") or ""
            url = raw.get("origin_url") or ""
            entry: Dict[str, Any] = {
                "title": title,
                "content": content,
            }
            if url:
                entry["url"] = url
            normalized.append(entry)
        return {"blog_reviews": normalized}

    @staticmethod
    def _build_photo(panel: Dict[str, Any]) -> Dict[str, Any]:
        """photo: 사진 URL 만 뽑아서 문자열 리스트로 (기존 크롤러 출력과 동일한 형태)."""
        photo_block = panel.get("photos") or {}
        items = photo_block.get("photos") or []
        urls: List[str] = []
        for item in items:
            if isinstance(item, dict):
                url = item.get("url")
            elif isinstance(item, str):
                url = item
            else:
                url = None
            if not url:
                continue
            # 프로토콜이 빠진 경우(드물지만) 안전하게 보정
            if url.startswith("//"):
                url = "https:" + url
            urls.append(url)
            if len(urls) >= _PHOTO_CAP:
                break
        return {"photos": urls}

    @staticmethod
    def _build_location(panel: Dict[str, Any]) -> Dict[str, Any]:
        """location: 도로명 / 지번 주소 (가능한 가장 깨끗한 값으로)."""
        summary = panel.get("summary") or {}
        address = summary.get("address") or {}

        location: Dict[str, Any] = {}

        # 다운스트림(place_data.iter_address_source_texts) 이 가장 먼저 읽는 필드
        road_address = address.get("disp") or address.get("road") or ""
        if road_address:
            location["road_address"] = road_address

        lot_address = address.get("jibun") or ""
        if lot_address:
            location["lot_address"] = lot_address

        return location
