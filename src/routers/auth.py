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

@router.post(
    "/signup",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        400: {
            "description": "이미 존재하는 이메일",
            "content": {
                "application/json": {
                    "example": {"detail": "이미 존재하는 이메일입니다."}
                }
            },
        },
        422: {
            "description": "유효성 검사 실패 (비밀번호 조건 미충족 등)",
            "content": {
                "application/json": {
                    "example": {
                        "detail": [
                            {
                                "loc": ["body", "password"],
                                "msg": "Value error, 대문자를 1개 이상 포함해야 합니다",
                                "type": "value_error"
                            }
                        ]
                    }
                }
            },
        },
        500: {
            "description": "서버 내부 오류",
            "content": {
                "application/json": {
                    "example": {"detail": "서버 오류가 발생했습니다."}
                }
            },
        },
    },
)
async def signup(user_data: UserSignup, db: Session = Depends(get_db)):
    """
    회원가입

    ## 필수값 (Request Body)

    | 필드 | 타입 | 설명 |
    |------|------|------|
    | email | string | 이메일 형식 (예: user@example.com) |
    | password | string | 최소 8자, 대문자·소문자·숫자·특수기호 각 1개 이상 |
    | name | string | 사용자 이름 (1자 이상) |

    ## 에러 처리 가이드

    **400 - 이메일 중복**
    ```json
    { "detail": "이미 존재하는 이메일입니다" }
    ```
    → `response.data.detail` 로 메시지 추출

    **422 - 유효성 검사 실패 (비밀번호 조건 미충족 등)**
    ```json
    { "detail": [{ "loc": ["body", "password"], "msg": "Value error, 대문자를 1개 이상 포함해야 합니다", "type": "value_error" }] }
    ```
    → `response.data.detail[0].msg` 로 메시지 추출 (배열이므로 여러 개일 수 있음)

    **500 - 서버 오류**
    ```json
    { "detail": "서버 오류가 발생했습니다." }
    ```
    → `response.data.detail` 로 메시지 추출
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
        password=user_data.password
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
