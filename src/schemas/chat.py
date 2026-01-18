# -*- coding: utf-8 -*-
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from enum import Enum

class MessageRole(str, Enum):
    """메시지 역할"""
    USER = "user"
    ASSISTANT = "assistant"

class MessageCreate(BaseModel):
    """메시지 생성 요청"""
    content: str = Field(..., description="메시지 내용", min_length=1)

    class Config:
        json_schema_extra = {
            "example": {
                "content": "강남 맛집 추천해줘"
            }
        }

class MessageResponse(BaseModel):
    """메시지 응답"""
    id: int
    chat_id: int
    role: MessageRole
    content: str
    created_at: datetime

    class Config:
        from_attributes = True  # Pydantic v2: ORM 모드 활성화
        json_schema_extra = {
            "example": {
                "id": 1,
                "chat_id": 1,
                "role": "user",
                "content": "강남 맛집 추천해줘",
                "created_at": "2024-01-04T12:00:00"
            }
        }

class ChatCreate(BaseModel):
    """채팅 생성 요청"""
    user_id: int = Field(..., description="사용자 ID")
    title: Optional[str] = Field(None, description="채팅 제목")

    class Config:
        json_schema_extra = {
            "example": {
                "user_id": 1,
                "title": "강남 맛집 추천"
            }
        }

class ChatResponse(BaseModel):
    """채팅 응답"""
    id: int
    user_id: int
    title: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True  # Pydantic v2: ORM 모드 활성화
        json_schema_extra = {
            "example": {
                "id": 1,
                "user_id": 1,
                "title": "강남 맛집 추천",
                "created_at": "2024-01-04T12:00:00",
                "updated_at": "2024-01-04T12:00:00"
            }
        }

class ChatMessageResponse(BaseModel):
    """채팅 메시지 전송 응답"""
    user_message: MessageResponse
    ai_message: MessageResponse

    class Config:
        json_schema_extra = {
            "example": {
                "user_message": {
                    "id": 1,
                    "chat_id": 1,
                    "role": "user",
                    "content": "강남 맛집 추천해줘",
                    "created_at": "2024-01-04T12:00:00"
                },
                "ai_message": {
                    "id": 2,
                    "chat_id": 1,
                    "role": "assistant",
                    "content": "강남역 근처 맛집 3곳을 추천드립니다...",
                    "created_at": "2024-01-04T12:00:05"
                }
            }
        }

class ChatTitleUpdate(BaseModel):
    """채팅 제목 업데이트 요청"""
    title: str = Field(..., description="새로운 채팅 제목", min_length=1, max_length=255)

    class Config:
        json_schema_extra = {
            "example": {
                "title": "강남 맛집 추천"
            }
        }
