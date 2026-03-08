# -*- coding: utf-8 -*-
"""
Compatibility script for uploading crawled place data into pgvector.

The filename is preserved to avoid breaking old entry points.
"""

import argparse
import json
from pathlib import Path
from typing import List

from src.services.pipeline_service import PipelineService


BASE_DIR = Path(__file__).resolve().parent.parent.parent
CRAWLED_DIR = BASE_DIR / "volumes" / "crawled"


def load_places(file_path: Path) -> List[dict]:
    with open(file_path, "r", encoding="utf-8") as file:
        return json.load(file)


def main() -> None:
    parser = argparse.ArgumentParser(description="Upload crawled place JSON files into pgvector.")
    parser.add_argument(
        "--recreate",
        action="store_true",
        help="Reset the pgvector table before upload.",
    )
    args = parser.parse_args()

    service = PipelineService()
    total_inserted = 0

    targets = [
        ("accommodation", CRAWLED_DIR / "accommodation_detailed.json"),
        ("restaurant", CRAWLED_DIR / "restaurant_detailed.json"),
    ]

    for index, (place_type, file_path) in enumerate(targets):
        if not file_path.exists():
            print(f"Skip missing file: {file_path}")
            continue

        places = load_places(file_path)
        result = service.upload_crawled_data(
            place_type=place_type,
            places=places,
            recreate_collection=args.recreate and index == 0,
        )
        total_inserted += result["inserted_count"]
        print(result["message"])

    print(f"Inserted {total_inserted} records into pgvector.")


if __name__ == "__main__":
    main()
