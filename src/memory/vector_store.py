from __future__ import annotations

import json
from contextlib import contextmanager
from typing import Any, Dict, Iterable, List, Optional

from pgvector.sqlalchemy import Vector
from sqlalchemy import String, Text, create_engine, delete, select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker

from src.config import settings
from src.utils.place_data import first_text, resolve_place_address

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
    place_id = str(place.get("place_id") or place.get("id") or "")
    resolved_address = resolve_place_address(place)

    return {
        "id": f"{place_type}_{place_id}",
        "place_id": place_id,
        "name": first_text(
            basic_info.get("name"),
            place.get("place_name"),
            place.get("display_name"),
            place.get("name"),
        ),
        "category": first_text(
            basic_info.get("category"),
            place.get("category_name"),
            place.get("category"),
        ),
        "place_type": place_type,
        "rating": first_text(
            basic_info.get("rating"),
            place.get("rating"),
            place.get("score"),
            place.get("review_score"),
        ),
        "address": resolved_address,
        "text_content": first_text(place.get("text_content")),
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


def search_place_embeddings(
    query_embedding: List[float],
    limit: int = 5,
    place_type: Optional[str] = None,
) -> List[Dict[str, Any]]:
    init_vector_db()

    with get_vector_session() as session:
        distance_expr = PlaceEmbedding.embedding.cosine_distance(query_embedding)
        distance = distance_expr.label("distance")
        stmt = select(PlaceEmbedding, distance)
        if place_type:
            stmt = stmt.where(PlaceEmbedding.place_type == place_type)
        if settings.rag_max_distance is not None:
            stmt = stmt.where(distance_expr <= settings.rag_max_distance)
        stmt = stmt.order_by(distance_expr).limit(limit)
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


def count_place_embeddings(place_type: Optional[str] = None) -> int:
    init_vector_db()
    with get_vector_session() as session:
        query = session.query(PlaceEmbedding)
        if place_type:
            query = query.filter(PlaceEmbedding.place_type == place_type)
        return query.count()
