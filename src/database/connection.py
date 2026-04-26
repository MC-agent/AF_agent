# -*- coding: utf-8 -*-
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, declarative_base, sessionmaker

from src.config import settings

DATABASE_URL = settings.get_database_url()

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    pool_recycle=3600,
    pool_timeout=settings.database_pool_timeout_seconds,
    connect_args={"connect_timeout": settings.database_connect_timeout_seconds},
    echo=False,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    from src.database.models import Chat, Message, User

    Base.metadata.create_all(bind=engine)
    print("database tables initialized")


def get_engine():
    return engine
