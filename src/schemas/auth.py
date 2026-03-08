# -*- coding: utf-8 -*-
import re
from pydantic import BaseModel, Field, EmailStr, field_validator
from typing import Optional
from datetime import datetime

class UserSignup(BaseModel):
    """회원가입 요청"""
    email: EmailStr = Field(..., description="사용자 이메일")
    password: str = Field(..., min_length=8, description="비밀번호 (최소 8자, 대소문자/숫자/특수기호 필수)")
    name: str = Field(..., min_length=1, description="사용자 이름")

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        """비밀번호 유효성 검사: 대문자, 소문자, 숫자, 특수기호 각 1개 이상 필수"""
        if not re.search(r"[A-Z]", v):
            raise ValueError("대문자를 1개 이상 포함해야 합니다")
        if not re.search(r"[a-z]", v):
            raise ValueError("소문자를 1개 이상 포함해야 합니다")
        if not re.search(r"[0-9]", v):
            raise ValueError("숫자를 1개 이상 포함해야 합니다")
        if not re.search(r"[!@#$%^&*()_+\-=\[\]{};':\"\\|,.<>/?`~]", v):
            raise ValueError("특수기호를 1개 이상 포함해야 합니다")
        return v

    class Config:
        json_schema_extra = {
            "example": {
                "email": "user@example.com",
                "password": "Password1!",
                "name": "홍길동"
            }
        }

class UserLogin(BaseModel):
    """로그인 요청"""
    email: EmailStr = Field(..., description="사용자 이메일")
    password: str = Field(..., description="비밀번호")

    class Config:
        json_schema_extra = {
            "example": {
                "email": "user@example.com",
                "password": "password123"
            }
        }

class Token(BaseModel):
    """토큰 응답"""
    access_token: str
    token_type: str = "bearer"
    user_id: int
    email: str

class UserResponse(BaseModel):
    """사용자 정보 응답"""
    id: int
    email: str
    name: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True
        json_schema_extra = {
            "example": {
                "id": 1,
                "email": "user@example.com",
                "name": None,
                "created_at": "2024-01-04T12:00:00"
            }
        }
