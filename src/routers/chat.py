# -*- coding: utf-8 -*-
from fastapi import APIRouter, HTTPException, Path, Depends
from sqlalchemy.orm import Session
from src.schemas.chat import (
    MessageCreate,
    MessageResponse,
    ChatCreate,
    ChatResponse,
    ChatMessageResponse,
    ChatTitleUpdate,
    MessageRole
)
from src.database.mysql import get_db
from src.database.models import Chat, Message, User
from datetime import datetime
from typing import List

router = APIRouter(
    prefix="/api/chats",
    tags=["chat"]
)

@router.post("", response_model=ChatResponse)
async def create_chat(chat: ChatCreate, db: Session = Depends(get_db)):
    """
    새로운 채팅 생성

    - **user_id**: 사용자 ID
    - **title**: 채팅 제목 (선택사항)
    """
    try:
        # 새 채팅 생성
        new_chat = Chat(
            user_id=chat.user_id,
            title=chat.title or "새 채팅"
        )
        db.add(new_chat)
        db.commit()
        db.refresh(new_chat)

        return new_chat

    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"채팅 생성 실패: {str(e)}")


@router.get("/{chat_id}", response_model=ChatResponse)
async def get_chat(chat_id: int = Path(..., description="채팅 ID"), db: Session = Depends(get_db)):
    """
    채팅 정보 조회

    - **chat_id**: 조회할 채팅 ID
    """
    try:
        chat = db.query(Chat).filter(Chat.id == chat_id).first()

        if not chat:
            raise HTTPException(status_code=404, detail="채팅을 찾을 수 없습니다")

        return chat

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"채팅 조회 실패: {str(e)}")


@router.get("/{chat_id}/messages", response_model=List[MessageResponse])
async def get_messages(chat_id: int = Path(..., description="채팅 ID"), db: Session = Depends(get_db)):
    """
    채팅의 모든 메시지 조회

    - **chat_id**: 채팅 ID
    """
    try:
        messages = db.query(Message).filter(
            Message.chat_id == chat_id
        ).order_by(Message.created_at.asc()).all()

        return messages

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"메시지 조회 실패: {str(e)}")


@router.post("/{chat_id}/messages", response_model=ChatMessageResponse)
async def send_message(
    chat_id: int = Path(..., description="채팅 ID"),
    message: MessageCreate = None,
    db: Session = Depends(get_db)
):
    """
    메시지 전송 (간단 버전)

    - **chat_id**: 채팅 ID
    - **message**: 메시지 내용

    현재는 간단한 응답만 반환합니다.
    향후 RAG 파이프라인과 연동 예정:
    1. Embedding 변환
    2. Milvus 벡터 검색
    3. Kakao Map API 호출
    4. LLM(Claude/GPT)에 전달
    5. 자연스러운 답변 생성
    """
    try:
        # 1. 사용자 메시지 저장
        user_message = Message(
            chat_id=chat_id,
            role=MessageRole.USER,
            content=message.content
        )
        db.add(user_message)
        db.commit()
        db.refresh(user_message)

        # 2. AI 응답 생성 (현재는 간단한 응답)
        # TODO: 여기에 RAG 파이프라인 추가
        ai_response = f"'{message.content}'에 대한 응답입니다. (향후 RAG 파이프라인 추가 예정)"

        # AI 메시지 저장
        ai_message = Message(
            chat_id=chat_id,
            role=MessageRole.ASSISTANT,
            content=ai_response
        )
        db.add(ai_message)
        db.commit()
        db.refresh(ai_message)

        return ChatMessageResponse(
            user_message=user_message,
            ai_message=ai_message
        )

    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"메시지 전송 실패: {str(e)}")


@router.patch("/{chat_id}/title", response_model=ChatResponse)
async def update_chat_title(
    chat_id: int = Path(..., description="채팅 ID"),
    title_update: ChatTitleUpdate = None,
    db: Session = Depends(get_db)
):
    """
    채팅 제목 업데이트

    - **chat_id**: 채팅 ID
    - **title**: 새로운 채팅 제목
    """
    try:
        chat = db.query(Chat).filter(Chat.id == chat_id).first()

        if not chat:
            raise HTTPException(status_code=404, detail="채팅을 찾을 수 없습니다")

        # 제목 업데이트
        chat.title = title_update.title
        db.commit()
        db.refresh(chat)

        return chat

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"채팅 제목 업데이트 실패: {str(e)}")


@router.delete("/{chat_id}")
async def delete_chat(chat_id: int = Path(..., description="채팅 ID"), db: Session = Depends(get_db)):
    """
    채팅 삭제

    - **chat_id**: 삭제할 채팅 ID
    """
    try:
        chat = db.query(Chat).filter(Chat.id == chat_id).first()

        if not chat:
            raise HTTPException(status_code=404, detail="채팅을 찾을 수 없습니다")

        db.delete(chat)
        db.commit()

        return {"message": "채팅이 삭제되었습니다", "chat_id": chat_id}

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"채팅 삭제 실패: {str(e)}")
