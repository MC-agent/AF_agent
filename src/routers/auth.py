# -*- coding: utf-8 -*-
from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
from src.schemas.auth import UserSignup, UserLogin, Token, UserResponse
from src.database.mysql import get_db
from src.database.models import User
from src.utils.auth import get_current_user
from src.services.auth_service import AuthService

router = APIRouter(
    prefix="/api/auth",
    tags=["auth"]
)

@router.post("/signup", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def signup(user_data: UserSignup, db: Session = Depends(get_db)):
    """
    회원가입

    - **email**: 사용자 이메일 (고유값)
    - **password**: 비밀번호 (최소 8자)
    """
    auth_service = AuthService(db)
    return auth_service.signup(
        email=user_data.email,
        password=user_data.password,
        name=user_data.name
    )

@router.post("/login", response_model=Token)
async def login(user_data: UserLogin, db: Session = Depends(get_db)):
    """
    로그인

    - **email**: 사용자 이메일
    - **password**: 비밀번호

    반환: JWT 액세스 토큰
    """
    auth_service = AuthService(db)
    user, access_token = auth_service.login(
        email=user_data.email,
        password=user_data.password,
        name=user_data.name
    )

    return Token(
        access_token=access_token,
        token_type="bearer",
        user_id=user.id,
        email=user.email
    )

@router.post("/logout")
async def logout(current_user: User = Depends(get_current_user)):
    """
    로그아웃

    JWT 토큰 기반 인증이므로 실제로는 프론트엔드에서 토큰을 삭제합니다.
    이 엔드포인트는 로그아웃 로그를 남기거나 추가 작업이 필요할 때 사용합니다.
    """
    return {
        "message": "로그아웃 되었습니다",
        "user_id": current_user.id
    }

@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)):
    """
    현재 로그인한 사용자 정보 조회

    Authorization 헤더에 Bearer 토큰 필요
    """
    return current_user
