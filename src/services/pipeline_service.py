# -*- coding: utf-8 -*-
import json
from pathlib import Path
from typing import Dict, List

from openai import OpenAI

from src.config import settings
from src.crawlers.kakao_map_crawler import KakaoMapCrawler
from src.crawlers.kakao_search import CATEGORY_ACCOMMODATION, CATEGORY_RESTAURANT, KakaoSearch
from src.memory.vector_store import (
    build_place_record,
    init_vector_db,
    reset_place_embeddings,
    upsert_place_embeddings,
)
from src.utils.place_data import first_text, resolve_place_address


class PipelineService:
    BASE_DIR = Path(__file__).resolve().parent.parent.parent
    RAW_DIR = BASE_DIR / "volumes" / "raw"
    CRAWLED_DIR = BASE_DIR / "volumes" / "crawled"
    EMBEDDING_MODEL = settings.embedding_model

    def __init__(self) -> None:
        self.openai_client = OpenAI(api_key=settings.openai_api_key)
        self.pipeline_status = {
            "is_running": False,
            "current_phase": None,
            "category": None,
            "crawl_progress": 0,
            "crawl_total": 0,
            "insert_progress": 0,
            "insert_total": 0,
            "crawled_count": 0,
            "inserted_count": 0,
            "errors": [],
        }

    def get_status(self) -> Dict:
        return self.pipeline_status.copy()

    def search_places_with_kakao(
        self,
        search_queries: List[str],
        category_code: str,
        limit_per_query: int = 10,
    ) -> List[Dict]:
        kakao_search = KakaoSearch()
        all_places: List[Dict] = []
        seen_ids = set()

        for query in search_queries:
            print(f"Searching for: {query}")
            try:
                places = kakao_search.search_and_extract_ids(
                    query=query,
                    category_group_code=category_code,
                    max_results=limit_per_query,
                )
            except Exception as exc:
                print(f"Search failed for '{query}': {exc}")
                continue

            for place in places:
                place_id = place.get("id")
                if place_id and place_id not in seen_ids:
                    all_places.append(place)
                    seen_ids.add(place_id)

            print(f"Found {len(places)} places for '{query}'")

        return all_places

    def create_vector_store(self, recreate: bool = False) -> None:
        init_vector_db()
        if recreate:
            reset_place_embeddings()

    def normalize_place_data(self, place_data: Dict) -> Dict:
        normalized_place = dict(place_data)
        basic_info = dict(place_data.get("basic_info") or {})
        home = dict(place_data.get("home") or {})
        location = dict(place_data.get("location") or {})

        if not basic_info.get("name"):
            basic_info["name"] = first_text(
                place_data.get("place_name"),
                place_data.get("display_name"),
                place_data.get("name"),
            )
        if not basic_info.get("category"):
            basic_info["category"] = first_text(
                place_data.get("category_name"),
                place_data.get("category"),
            )
        if not basic_info.get("rating"):
            basic_info["rating"] = first_text(
                place_data.get("rating"),
                place_data.get("score"),
                place_data.get("review_score"),
            )
        resolved_address = resolve_place_address(normalized_place)
        if resolved_address:
            home["address_detail"] = resolved_address
            if not location.get("road_address"):
                location["road_address"] = resolved_address

        normalized_place["basic_info"] = basic_info
        normalized_place["home"] = home
        normalized_place["location"] = location
        return normalized_place

    def create_text_content(self, place_data: Dict) -> str:
        place_data = self.normalize_place_data(place_data)
        parts: List[str] = []

        basic_info = place_data.get("basic_info", {})
        home = place_data.get("home", {})
        menus = place_data.get("menu", {}).get("menus", [])
        reviews = place_data.get("review", {}).get("reviews", [])
        blog_reviews = place_data.get("blog_review", {}).get("blog_reviews", [])

        if basic_info.get("name"):
            parts.append(f"name: {basic_info['name']}")
        if basic_info.get("category"):
            parts.append(f"category: {basic_info['category']}")
        if home.get("address_detail"):
            parts.append(f"address: {home['address_detail']}")
        if home.get("services"):
            parts.append(f"services: {', '.join(home['services'])}")

        menu_names = [menu.get("name", "") for menu in menus if menu.get("name")]
        if menu_names:
            parts.append(f"menus: {', '.join(menu_names[:10])}")

        for index, review in enumerate(reviews[:10], start=1):
            content = review.get("content", "").strip()
            if content:
                parts.append(f"review_{index}: {content[:200]}")

        for index, blog in enumerate(blog_reviews[:5], start=1):
            title = blog.get("title", "").strip()
            content = blog.get("content", "").strip()
            if title:
                parts.append(f"blog_title_{index}: {title}")
            if content:
                parts.append(f"blog_content_{index}: {content[:200]}")

        return " | ".join(parts)

    def _prepare_records(self, place_type: str, places: List[Dict]) -> List[Dict]:
        records: List[Dict] = []
        self.pipeline_status["insert_total"] = len(places)
        self.pipeline_status["insert_progress"] = 0

        for index, place in enumerate(places, start=1):
            try:
                normalized_place = self.normalize_place_data(place)
                place_id = normalized_place.get("place_id") or normalized_place.get("id") or place.get("id") or "unknown"

                text_content = self.create_text_content(normalized_place).strip()
                if not text_content:
                    self.pipeline_status["errors"].append(
                        f"Skipped {place_id}: text_content is empty after normalization"
                    )
                    self.pipeline_status["insert_progress"] = index
                    continue

                response = self.openai_client.embeddings.create(
                    input=text_content,
                    model=self.EMBEDDING_MODEL,
                )
                embedding = response.data[0].embedding

                enriched_place = dict(place)
                enriched_place["basic_info"] = normalized_place.get("basic_info", {})
                enriched_place["home"] = normalized_place.get("home", {})
                enriched_place["text_content"] = text_content
                records.append(build_place_record(place_type, enriched_place, embedding))
                self.pipeline_status["insert_progress"] = index
            except Exception as exc:
                self.pipeline_status["errors"].append(
                    f"Failed to embed {place_id}: {exc}"
                )

        return records

    def run_pipeline(
        self,
        category: str,
        search_queries: List[str],
        limit_per_query: int,
        crawl_limit: int,
        recreate_collection: bool,
    ) -> Dict:
        self.pipeline_status.update(
            {
                "is_running": True,
                "current_phase": "initializing",
                "category": category,
                "crawl_progress": 0,
                "crawl_total": 0,
                "insert_progress": 0,
                "insert_total": 0,
                "crawled_count": 0,
                "inserted_count": 0,
                "errors": [],
            }
        )

        try:
            self.create_vector_store(recreate=recreate_collection)
            categories = ["accommodation", "restaurant"] if category == "all" else [category]

            total_crawled = 0
            total_inserted = 0

            for place_type in categories:
                self.pipeline_status["current_phase"] = "searching"
                category_code = (
                    CATEGORY_ACCOMMODATION
                    if place_type == "accommodation"
                    else CATEGORY_RESTAURANT
                )

                search_results = self.search_places_with_kakao(
                    search_queries=search_queries,
                    category_code=category_code,
                    limit_per_query=limit_per_query,
                )

                self.RAW_DIR.mkdir(parents=True, exist_ok=True)
                raw_file = self.RAW_DIR / f"{place_type}.json"
                with open(raw_file, "w", encoding="utf-8") as file:
                    json.dump(search_results, file, ensure_ascii=False, indent=2)

                place_ids = [item["id"] for item in search_results if item.get("id")][:crawl_limit]
                self.pipeline_status["crawl_total"] = len(place_ids)
                self.pipeline_status["crawl_progress"] = 0

                self.pipeline_status["current_phase"] = "crawling"
                crawler = KakaoMapCrawler(headless=True)
                crawled_places: List[Dict] = []

                for index, place_id in enumerate(place_ids, start=1):
                    try:
                        crawled_places.append(crawler.crawl_place_detail(place_id))
                        self.pipeline_status["crawl_progress"] = index
                    except Exception as exc:
                        self.pipeline_status["errors"].append(
                            f"Failed to crawl {place_id}: {exc}"
                        )

                if crawled_places:
                    self.CRAWLED_DIR.mkdir(parents=True, exist_ok=True)
                    output_file = self.CRAWLED_DIR / f"{place_type}_detailed.json"
                    with open(output_file, "w", encoding="utf-8") as file:
                        json.dump(crawled_places, file, ensure_ascii=False, indent=2)

                total_crawled += len(crawled_places)
                self.pipeline_status["crawled_count"] = total_crawled

                self.pipeline_status["current_phase"] = "inserting"
                records = self._prepare_records(place_type, crawled_places)
                inserted_count = upsert_place_embeddings(records)

                total_inserted += inserted_count
                self.pipeline_status["inserted_count"] = total_inserted

            self.pipeline_status["current_phase"] = "completed"
        except Exception as exc:
            self.pipeline_status["current_phase"] = "failed"
            self.pipeline_status["errors"].append(f"Pipeline failed: {exc}")
        finally:
            self.pipeline_status["is_running"] = False

        status = self.pipeline_status["current_phase"] or "failed"
        if (
            status == "completed"
            and self.pipeline_status["crawl_total"] > 0
            and self.pipeline_status["crawled_count"] == 0
        ):
            status = "failed"
        if (
            status == "completed"
            and self.pipeline_status["crawled_count"] > 0
            and self.pipeline_status["inserted_count"] == 0
        ):
            status = "failed"

        message = (
            "Pipeline completed successfully"
            if status == "completed"
            else "Pipeline failed"
        )
        if status == "completed" and self.pipeline_status["errors"]:
            message = "Pipeline completed with errors"

        return {
            "message": message,
            "category": category,
            "total_places": self.pipeline_status["crawled_count"],
            "crawled_count": self.pipeline_status["crawled_count"],
            "inserted_count": self.pipeline_status["inserted_count"],
            "status": status,
            "errors": list(self.pipeline_status["errors"]),
        }

    def upload_crawled_data(
        self,
        place_type: str,
        places: List[Dict],
        recreate_collection: bool,
    ) -> Dict:
        try:
            self.pipeline_status["errors"] = []
            self.create_vector_store(recreate=recreate_collection)
            records = self._prepare_records(place_type, places)
            inserted_count = upsert_place_embeddings(records)

            return {
                "message": f"Successfully uploaded {inserted_count} places to pgvector",
                "place_type": place_type,
                "total_uploaded": len(places),
                "inserted_count": inserted_count,
                "errors": list(self.pipeline_status["errors"]),
            }
        except Exception as exc:
            raise Exception(f"Upload failed: {exc}") from exc
