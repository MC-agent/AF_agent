from __future__ import annotations

import json
from contextlib import contextmanager
from typing import Any, Dict, Iterable, List

from pgvector.sqlalchemy import Vector
from sqlalchemy import String, Text, create_engine, delete, select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker

from src.config import settings

EMBEDDING_DIM = 1536


class VectorBase(DeclarativeBase):
    pass


class PlaceEmbedding(VectorBase):
    __tablename__ = "kakao_places"

    id: Mapped[str] = mapped_column(String(100), primary_key=True)
    place_id: Mapped[str] = mapped_column(String(100), index=True)
    name: Mapped[str] = mapped_column(String(500), default="")
    category: Mapped[str] = mapped_column(String(100), default="")
    place_type: Mapped[str] = mapped_column(String(50), index=True)
    rating: Mapped[str] = mapped_column(String(50), default="")
    address: Mapped[str] = mapped_column(String(500), default="")
    text_content: Mapped[str] = mapped_column(Text, default="")
    full_data: Mapped[str] = mapped_column(Text, default="")
    embedding: Mapped[List[float]] = mapped_column(Vector(EMBEDDING_DIM))


vector_engine = create_engine(
    settings.get_pgvector_database_url(),
    pool_pre_ping=True,
    pool_recycle=3600,
    echo=False,
)

VectorSessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=vector_engine,
)


@contextmanager
def get_vector_session() -> Iterable[Session]:
    session = VectorSessionLocal()
    try:
        yield session
    finally:
        session.close()


def init_vector_db() -> None:
    with vector_engine.begin() as connection:
        connection.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
    VectorBase.metadata.create_all(bind=vector_engine)


def reset_place_embeddings() -> None:
    init_vector_db()
    with vector_engine.begin() as connection:
        connection.execute(delete(PlaceEmbedding))


def build_place_record(place_type: str, place: Dict[str, Any], embedding: List[float]) -> Dict[str, Any]:
    basic_info = place.get("basic_info", {})
    home = place.get("home", {})
    place_id = str(place.get("place_id") or place.get("id") or "")

    return {
        "id": f"{place_type}_{place_id}",
        "place_id": place_id,
        "name": str(basic_info.get("name", "")),
        "category": str(basic_info.get("category", "")),
        "place_type": place_type,
        "rating": str(basic_info.get("rating", "")),
        "address": str(home.get("address_detail", "")),
        "text_content": str(place.get("text_content", "")),
        "full_data": json.dumps(place, ensure_ascii=False),
        "embedding": embedding,
    }


def upsert_place_embeddings(records: List[Dict[str, Any]]) -> int:
    if not records:
        return 0

    init_vector_db()

    with vector_engine.begin() as connection:
        stmt = insert(PlaceEmbedding).values(records)
        update_columns = {
            "place_id": stmt.excluded.place_id,
            "name": stmt.excluded.name,
            "category": stmt.excluded.category,
            "place_type": stmt.excluded.place_type,
            "rating": stmt.excluded.rating,
            "address": stmt.excluded.address,
            "text_content": stmt.excluded.text_content,
            "full_data": stmt.excluded.full_data,
            "embedding": stmt.excluded.embedding,
        }
        connection.execute(
            stmt.on_conflict_do_update(
                index_elements=[PlaceEmbedding.id],
                set_=update_columns,
            )
        )

    return len(records)


def search_place_embeddings(query_embedding: List[float], limit: int = 5) -> List[Dict[str, Any]]:
    init_vector_db()

    with get_vector_session() as session:
        distance = PlaceEmbedding.embedding.cosine_distance(query_embedding).label("distance")
        stmt = (
            select(PlaceEmbedding, distance)
            .order_by(distance)
            .limit(limit)
        )
        rows = session.execute(stmt).all()

    results: List[Dict[str, Any]] = []
    for place, row_distance in rows:
        results.append(
            {
                "distance": float(row_distance),
                "entity": {
                    "id": place.id,
                    "place_id": place.place_id,
                    "name": place.name,
                    "category": place.category,
                    "place_type": place.place_type,
                    "rating": place.rating,
                    "address": place.address,
                    "text_content": place.text_content,
                    "full_data": place.full_data,
                },
            }
        )

    return results


def count_place_embeddings() -> int:
    init_vector_db()
    with get_vector_session() as session:
        return session.query(PlaceEmbedding).count()
