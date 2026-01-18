# -*- coding: utf-8 -*-
from fastapi import APIRouter, HTTPException, Depends, status
from sqlalchemy.orm import Session
from src.schemas.auth import UserSignup, UserLogin, Token, UserResponse
from src.database.mysql import get_db
from src.database.models import User
from src.utils.auth import (
    get_password_hash,
    verify_password,
    create_access_token,
    get_current_user
)

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
    try:
        # 이메일 중복 확인
        existing_user = db.query(User).filter(User.email == user_data.email).first()
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="이미 존재하는 이메일입니다"
            )

        # 비밀번호 해싱
        hashed_password = get_password_hash(user_data.password)

        # 새 사용자 생성
        new_user = User(
            email=user_data.email,
            password=hashed_password,
            name=user_data.name
        )
        db.add(new_user)
        db.commit()
        db.refresh(new_user)

        return new_user

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"회원가입 실패: {str(e)}"
        )

@router.post("/login", response_model=Token)
async def login(user_data: UserLogin, db: Session = Depends(get_db)):
    """
    로그인

    - **email**: 사용자 이메일
    - **password**: 비밀번호

    반환: JWT 액세스 토큰
    """
    try:
        # 사용자 조회
        user = db.query(User).filter(User.email == user_data.email).first()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="이메일 또는 비밀번호가 올바르지 않습니다",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # 비밀번호 검증
        if not verify_password(user_data.password, user.password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="이메일 또는 비밀번호가 올바르지 않습니다",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # 사용자 이름 업데이트 (제공된 경우)
        if user_data.name:
            user.name = user_data.name
            db.commit()
            db.refresh(user)
            
        # JWT 토큰 생성
        access_token = create_access_token(data={"sub": user.id})

        return Token(
            access_token=access_token,
            token_type="bearer",
            user_id=user.id,
            email=user.email
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"로그인 실패: {str(e)}"
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
