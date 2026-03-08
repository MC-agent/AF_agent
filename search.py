from openai import OpenAI

from src.config import settings
from src.memory.vector_store import search_place_embeddings

client = OpenAI(api_key=settings.openai_api_key)


def rag_search(query: str, limit: int = 5):
    response = client.embeddings.create(
        input=query,
        model=settings.embedding_model,
    )
    return search_place_embeddings(response.data[0].embedding, limit)


def print_results(query: str, results: list, limit: int = 5) -> None:
    print(f"Query: {query}")
    for result in results[:limit]:
        entity = result.get("entity", {})
        print(entity.get("name", "N/A"))
        print(entity.get("address", "N/A"))
        print(entity.get("text_content", "")[:200])
        print()


if __name__ == "__main__":
    query = "recommend a jeonse-friendly neighborhood"
    results = rag_search(query, limit=5)
    print_results(query, results, limit=5)
