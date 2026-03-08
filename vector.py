from src.memory.vector_store import count_place_embeddings, init_vector_db


def main() -> None:
    init_vector_db()
    print(f"pgvector rows: {count_place_embeddings()}")


if __name__ == "__main__":
    main()
