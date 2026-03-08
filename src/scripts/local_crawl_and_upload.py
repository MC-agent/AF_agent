# -*- coding: utf-8 -*-
import argparse
import json
import sys
from pathlib import Path
from typing import Dict, List

import requests

BASE_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(BASE_DIR))

from src.crawlers.kakao_map_crawler import KakaoMapCrawler
from src.crawlers.kakao_search import CATEGORY_ACCOMMODATION, CATEGORY_RESTAURANT, KakaoSearch


def search_places(search_queries: List[str], category_code: str, limit_per_query: int = 10) -> List[Dict]:
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

    return all_places


def crawl_places(place_ids: List[str], headless: bool = True) -> List[Dict]:
    crawler = KakaoMapCrawler(headless=headless)
    crawled_data: List[Dict] = []

    for index, place_id in enumerate(place_ids, start=1):
        try:
            print(f"Crawling {index}/{len(place_ids)}: {place_id}")
            crawled_data.append(crawler.crawl_place_detail(place_id))
        except Exception as exc:
            print(f"Failed to crawl {place_id}: {exc}")

    return crawled_data


def save_to_json(data: List[Dict], output_file: Path) -> None:
    output_file.parent.mkdir(parents=True, exist_ok=True)
    with open(output_file, "w", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False, indent=2)
    print(f"Saved to {output_file}")


def upload_to_server(
    server_url: str,
    place_type: str,
    crawled_data: List[Dict],
    recreate_collection: bool = False,
) -> Dict:
    endpoint = f"{server_url}/pipeline/upload"
    payload = {
        "place_type": place_type,
        "places": crawled_data,
        "recreate_collection": recreate_collection,
    }

    response = requests.post(endpoint, json=payload, timeout=300)
    response.raise_for_status()
    result = response.json()
    print(f"Uploaded {result['inserted_count']} places to pgvector.")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Search Kakao places, crawl details, and upload to the server.")
    parser.add_argument("--queries", nargs="+", required=True, help="Kakao search queries")
    parser.add_argument(
        "--place_type",
        choices=["restaurant", "accommodation"],
        required=True,
        help="Place type to search",
    )
    parser.add_argument("--limit", type=int, default=10, help="Search limit per query")
    parser.add_argument("--crawl_limit", type=int, default=None, help="Maximum places to crawl")
    parser.add_argument("--server_url", default="http://localhost:8000", help="API server URL")
    parser.add_argument("--output", type=Path, default=None, help="Optional JSON output path")
    parser.add_argument("--no-upload", action="store_true", help="Only save local crawl output")
    parser.add_argument("--headless", action="store_true", default=True, help="Run browser in headless mode")
    parser.add_argument(
        "--recreate-collection",
        action="store_true",
        help="Reset the pgvector table before upload",
    )
    args = parser.parse_args()

    category_code = (
        CATEGORY_ACCOMMODATION if args.place_type == "accommodation" else CATEGORY_RESTAURANT
    )

    search_results = search_places(args.queries, category_code, args.limit)
    place_ids = [place["id"] for place in search_results if place.get("id")]
    if args.crawl_limit:
        place_ids = place_ids[: args.crawl_limit]

    crawled_data = crawl_places(place_ids, headless=args.headless)
    if not crawled_data:
        print("No crawled data collected.")
        return

    if args.output:
        save_to_json(crawled_data, args.output)

    if not args.no_upload:
        upload_to_server(
            server_url=args.server_url,
            place_type=args.place_type,
            crawled_data=crawled_data,
            recreate_collection=args.recreate_collection,
        )


if __name__ == "__main__":
    main()
