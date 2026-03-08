# -*- coding: utf-8 -*-
import io
import sys

from openai import OpenAI

from src.config import settings
from src.memory.vector_store import search_place_embeddings

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

client = OpenAI(api_key=settings.openai_api_key)


def search_places(query: str, top_k: int = 3) -> None:
    print(f"\nQuery: {query}")
    print("=" * 80)

    response = client.embeddings.create(
        input=query,
        model=settings.embedding_model,
    )
    results = search_place_embeddings(response.data[0].embedding, top_k)

    if not results:
        print("No results found.")
        return

    for index, hit in enumerate(results, start=1):
        entity = hit["entity"]
        print(f"{index}. {entity.get('name', 'N/A')}")
        print(f"   category: {entity.get('category', 'N/A')}")
        print(f"   type: {entity.get('place_type', 'N/A')}")
        print(f"   rating: {entity.get('rating', 'N/A')}")
        print(f"   address: {entity.get('address', 'N/A')}")
        print(f"   distance: {hit['distance']:.4f}")
        print()


def main() -> None:
    queries = [
        "recommend a hotel in gangnam",
        "restaurant with parking",
        "quiet cafe for a meeting",
    ]

    for query in queries:
        search_places(query, top_k=3)
        print("-" * 80)


if __name__ == "__main__":
    main()
