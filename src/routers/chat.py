# -*- coding: utf-8 -*-
from fastapi import APIRouter, Path, Depends
from sqlalchemy.orm import Session
from src.schemas.chat import (
    MessageCreate,
    MessageResponse,
    ChatResponse,
    ChatMessageResponse
)
from src.database.connection import get_db
from src.database.models import User
from src.utils.auth import get_current_user
from src.services.chat_service import ChatService
from typing import List

router = APIRouter(
    prefix="/api/chats",
    tags=["chat"]
)

@router.get("", response_model=List[ChatResponse])
def get_user_chats(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    현재 로그인한 사용자의 모든 채팅 목록 조회

    최신 업데이트 순으로 정렬하여 반환합니다.
    """
    chat_service = ChatService(db)
    return chat_service.get_user_chats(current_user.id)


@router.post("", response_model=ChatResponse)
def create_chat(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    새로운 채팅 생성

    body 없이 호출하면 됩니다.
    제목은 첫 메시지를 보낼 때 AI가 자동 생성합니다.
    """
    chat_service = ChatService(db)
    return chat_service.create_chat(user_id=current_user.id)


@router.get("/{chat_id}", response_model=ChatResponse)
def get_chat(
    chat_id: int = Path(..., description="채팅 ID"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    채팅 정보 조회

    - **chat_id**: 조회할 채팅 ID

    자신이 소유한 채팅만 조회할 수 있습니다.
    """
    chat_service = ChatService(db)
    return chat_service.get_chat(chat_id, current_user.id)


@router.get("/{chat_id}/messages", response_model=List[MessageResponse])
def get_messages(
    chat_id: int = Path(..., description="채팅 ID"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    채팅의 모든 메시지 조회

    - **chat_id**: 채팅 ID

    자신이 소유한 채팅의 메시지만 조회할 수 있습니다.
    """
    chat_service = ChatService(db)
    return chat_service.get_messages(chat_id, current_user.id)


@router.post("/{chat_id}/messages", response_model=ChatMessageResponse)
def send_message(
    chat_id: int = Path(..., description="채팅 ID"),
    message: MessageCreate = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    메시지 전송

    - **chat_id**: 채팅 ID
    - **message**: 메시지 내용

    자신이 소유한 채팅에만 메시지를 전송할 수 있습니다.

    Supervisor agent가 restaurant/room agent를 라우팅하고,
    chat_id 단위 memory로 이전 대화 맥락을 이어갑니다.
    """
    chat_service = ChatService(db)
    result = chat_service.send_message(
        chat_id=chat_id,
        user_id=current_user.id,
        content=message.content
    )

    return ChatMessageResponse(
        user_message=result["user_message"],
        ai_message=result["ai_message"]
    )



@router.delete("/{chat_id}")
def delete_chat(
    chat_id: int = Path(..., description="채팅 ID"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    채팅 삭제

    - **chat_id**: 삭제할 채팅 ID

    자신이 소유한 채팅만 삭제할 수 있습니다.
    """
    chat_service = ChatService(db)
    return chat_service.delete_chat(chat_id, current_user.id)
