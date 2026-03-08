# -*- coding: utf-8 -*-
import os
from typing import Generator
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from dotenv import load_dotenv
# .env 파일 로드
load_dotenv()

# =========================
# PostgreSQL 연결 설정 (.env에서 로드)
# =========================
PG_HOST = os.getenv("PG_HOST")
PG_PORT = os.getenv("PG_PORT", "5432")
PG_USER = os.getenv("PG_USER")
PG_PASSWORD = os.getenv("PG_PASSWORD")
PG_DATABASE = os.getenv("PG_DATABASE")

# SQLAlchemy Database URL
# postgresql+psycopg2://user:password@host:port/database
DATABASE_URL = f"postgresql+psycopg2://{PG_USER}:{PG_PASSWORD}@{PG_HOST}:{PG_PORT}/{PG_DATABASE}"

# SQLAlchemy Engine 생성
engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,  # 연결 유효성 확인
    pool_recycle=3600,   # 1시간마다 연결 재생성
    echo=False           # SQL 쿼리 로깅 (개발 시 True로 설정 가능)
)

# Session Local
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base class for ORM models
Base = declarative_base()

# Dependency for FastAPI
def get_db() -> Generator[Session, None, None]:
    """
    FastAPI 의존성 주입을 위한 데이터베이스 세션 생성

    사용 예:
    @app.get("/items")
    def get_items(db: Session = Depends(get_db)):
        return db.query(Item).all()
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def init_db():
    """데이터베이스 테이블 초기화"""
    # models.py에서 정의한 모델들을 import
    from src.database.models import User, Chat, Message

    # 모든 테이블 생성
    Base.metadata.create_all(bind=engine)
    print("✅ 테이블 초기화 완료")

def get_engine():
    """엔진 반환 (테스트용)"""
    return engine
