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
# MySQL 연결 설정 (.env에서 로드)
# =========================
MYSQL_HOST = os.getenv("MYSQL_HOST")
MYSQL_PORT = os.getenv("MYSQL_PORT")
MYSQL_USER = os.getenv("MYSQL_USER")
MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD")
MYSQL_DATABASE = os.getenv("MYSQL_DATABASE")

# SQLAlchemy Database URL
# mysql+pymysql://user:password@host:port/database
DATABASE_URL = f"mysql+pymysql://{MYSQL_USER}:{MYSQL_PASSWORD}@{MYSQL_HOST}:{MYSQL_PORT}/{MYSQL_DATABASE}"

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
