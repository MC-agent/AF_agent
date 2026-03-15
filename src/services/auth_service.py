# -*- coding: utf-8 -*-
"""
Auth Service - 인증 관련 비즈니스 로직
"""
from typing import Optional, Tuple
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from src.repositories.user_repository import UserRepository
from src.database.models import User
from src.utils.auth import (
    get_password_hash,
    verify_password,
    create_access_token,
    create_refresh_token,
    decode_access_token
)


class AuthService:
    """인증 관련 비즈니스 로직을 처리하는 Service"""

    def __init__(self, db: Session):
        """
        Args:
            db: SQLAlchemy 데이터베이스 세션
        """
        self.db = db
        self.user_repo = UserRepository(db)

    def signup(self, email: str, password: str, name: str) -> User:
        """
        회원가입 비즈니스 로직

        Args:
            email: 사용자 이메일
            password: 비밀번호 (평문)
            name: 사용자 이름

        Returns:
            생성된 User 객체

        Raises:
            HTTPException: 이메일 중복 또는 회원가입 실패 시
        """
        try:
            # 1. 이메일 중복 확인
            existing_user = self.user_repo.get_by_email(email)
            if existing_user:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="이미 존재하는 이메일입니다"
                )

            # 2. 비밀번호 해싱
            hashed_password = get_password_hash(password)

            # 3. 사용자 생성
            new_user = self.user_repo.create(
                email=email,
                hashed_password=hashed_password,
                name=name
            )

            # 4. 트랜잭션 커밋
            self.db.commit()
            self.db.refresh(new_user)

            return new_user

        except HTTPException:
            raise
        except Exception as e:
            self.db.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"회원가입 실패: {str(e)}"
            )

    def login(self, email: str, password: str) -> Tuple[User, str]:
        """
        로그인 비즈니스 로직

        Args:
            email: 사용자 이메일
            password: 비밀번호 (평문)

        Returns:
            Tuple[User, str]: (사용자 객체, JWT 액세스 토큰)

        Raises:
            HTTPException: 인증 실패 또는 로그인 실패 시
        """
        try:
            # 1. 사용자 조회
            user = self.user_repo.get_by_email(email)
            if not user:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="이메일 또는 비밀번호가 올바르지 않습니다",
                    headers={"WWW-Authenticate": "Bearer"},
                )

            # 2. 비밀번호 검증
            if not verify_password(password, user.password):
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="이메일 또는 비밀번호가 올바르지 않습니다",
                    headers={"WWW-Authenticate": "Bearer"},
                )

            # 3. JWT 토큰 생성
            access_token = create_access_token(data={"sub": str(user.id)})
            refresh_token = create_refresh_token(data={"sub": str(user.id)})

            return user, access_token, refresh_token

        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"로그인 실패: {str(e)}"
            )

    def refresh(self, refresh_token: str) -> Tuple[str, str]:
        """
        리프레시 토큰으로 새 액세스 토큰 + 리프레시 토큰 발급

        Args:
            refresh_token: 리프레시 토큰

        Returns:
            Tuple[str, str]: (새 액세스 토큰, 새 리프레시 토큰)

        Raises:
            HTTPException: 토큰이 유효하지 않거나 만료된 경우
        """
        # 1. 리프레시 토큰 검증
        payload = decode_access_token(refresh_token)
        if payload is None or payload.get("type") != "refresh":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="리프레시 토큰이 유효하지 않습니다",
            )

        # 2. 사용자 존재 확인
        user_id = payload.get("sub")
        user = self.user_repo.get_by_id(int(user_id))
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="사용자를 찾을 수 없습니다",
            )

        # 3. 새 토큰 발급
        new_access_token = create_access_token(data={"sub": str(user.id)})
        new_refresh_token = create_refresh_token(data={"sub": str(user.id)})

        return new_access_token, new_refresh_token
