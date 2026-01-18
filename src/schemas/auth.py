# -*- coding: utf-8 -*-
from pydantic import BaseModel, Field, EmailStr
from typing import Optional
from datetime import datetime

class UserSignup(BaseModel):
    """회원가입 요청"""
    email: EmailStr = Field(..., description="사용자 이메일")
    password: str = Field(..., min_length=8, description="비밀번호 (최소 8자)")

    class Config:
        json_schema_extra = {
            "example": {
                "email": "user@example.com",
                "password": "password123"
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
