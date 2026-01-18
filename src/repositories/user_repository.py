# -*- coding: utf-8 -*-
"""
User Repository - User 테이블 데이터 접근 레이어
"""
from typing import Optional
from sqlalchemy.orm import Session
from src.database.models import User


class UserRepository:
    """User 테이블에 대한 CRUD 작업을 담당하는 Repository"""

    def __init__(self, db: Session):
        """
        Args:
            db: SQLAlchemy 데이터베이스 세션
        """
        self.db = db

    def get_by_email(self, email: str) -> Optional[User]:
        """
        이메일로 사용자 조회

        Args:
            email: 조회할 사용자 이메일

        Returns:
            User 객체 또는 None (존재하지 않는 경우)
        """
        return self.db.query(User).filter(User.email == email).first()

    def get_by_id(self, user_id: int) -> Optional[User]:
        """
        ID로 사용자 조회

        Args:
            user_id: 조회할 사용자 ID

        Returns:
            User 객체 또는 None (존재하지 않는 경우)
        """
        return self.db.query(User).filter(User.id == user_id).first()

    def create(self, email: str, hashed_password: str, name: str) -> User:
        """
        새로운 사용자 생성

        Args:
            email: 사용자 이메일
            hashed_password: 해시된 비밀번호
            name: 사용자 이름

        Returns:
            생성된 User 객체
        """
        new_user = User(
            email=email,
            password=hashed_password,
            name=name
        )
        self.db.add(new_user)
        self.db.flush()  # ID를 즉시 생성하되 커밋은 Service에서 처리
        self.db.refresh(new_user)
        return new_user

    def update_name(self, user: User, name: str) -> User:
        """
        사용자 이름 업데이트

        Args:
            user: 업데이트할 User 객체
            name: 새로운 이름

        Returns:
            업데이트된 User 객체
        """
        user.name = name
        self.db.flush()  # 변경사항을 반영하되 커밋은 Service에서 처리
        self.db.refresh(user)
        return user
