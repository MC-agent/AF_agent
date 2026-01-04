# -*- coding: utf-8 -*-
from fastapi import APIRouter, HTTPException, Path
from src.schemas.chat import (
    MessageCreate,
    MessageResponse,
    ChatCreate,
    ChatResponse,
    ChatMessageResponse,
    MessageRole
)
from src.database.mysql import db
from datetime import datetime
from typing import List

router = APIRouter(
    prefix="/api/chats",
    tags=["chat"]
)

@router.post("", response_model=ChatResponse)
async def create_chat(chat: ChatCreate):
    """
    새로운 채팅 생성

    - **user_id**: 사용자 ID
    - **title**: 채팅 제목 (선택사항)
    """
    try:
        query = """
            INSERT INTO chats (user_id, title)
            VALUES (%s, %s)
        """
        params = (chat.user_id, chat.title or "새 채팅")

        with db.get_cursor() as cursor:
            cursor.execute(query, params)
            chat_id = cursor.lastrowid

            # 생성된 채팅 정보 조회
            cursor.execute("SELECT * FROM chats WHERE id = %s", (chat_id,))
            result = cursor.fetchone()

        return ChatResponse(**result)

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"채팅 생성 실패: {str(e)}")


@router.get("/{chat_id}", response_model=ChatResponse)
async def get_chat(chat_id: int = Path(..., description="채팅 ID")):
    """
    채팅 정보 조회

    - **chat_id**: 조회할 채팅 ID
    """
    try:
        query = "SELECT * FROM chats WHERE id = %s"
        with db.get_cursor() as cursor:
            cursor.execute(query, (chat_id,))
            result = cursor.fetchone()

        if not result:
            raise HTTPException(status_code=404, detail="채팅을 찾을 수 없습니다")

        return ChatResponse(**result)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"채팅 조회 실패: {str(e)}")


@router.get("/{chat_id}/messages", response_model=List[MessageResponse])
async def get_messages(chat_id: int = Path(..., description="채팅 ID")):
    """
    채팅의 모든 메시지 조회

    - **chat_id**: 채팅 ID
    """
    try:
        query = """
            SELECT * FROM messages
            WHERE chat_id = %s
            ORDER BY created_at ASC
        """
        with db.get_cursor() as cursor:
            cursor.execute(query, (chat_id,))
            results = cursor.fetchall()

        return [MessageResponse(**row) for row in results]

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"메시지 조회 실패: {str(e)}")


@router.post("/{chat_id}/messages", response_model=ChatMessageResponse)
async def send_message(
    chat_id: int = Path(..., description="채팅 ID"),
    message: MessageCreate = None
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
        user_message_query = """
            INSERT INTO messages (chat_id, role, content)
            VALUES (%s, %s, %s)
        """

        with db.get_cursor() as cursor:
            # 사용자 메시지 저장
            cursor.execute(user_message_query, (chat_id, MessageRole.USER.value, message.content))
            user_message_id = cursor.lastrowid

            # 저장된 사용자 메시지 조회
            cursor.execute("SELECT * FROM messages WHERE id = %s", (user_message_id,))
            user_msg_result = cursor.fetchone()

            # 2. AI 응답 생성 (현재는 간단한 응답)
            # TODO: 여기에 RAG 파이프라인 추가
            ai_response = f"'{message.content}'에 대한 응답입니다. (향후 RAG 파이프라인 추가 예정)"

            # AI 메시지 저장
            cursor.execute(user_message_query, (chat_id, MessageRole.ASSISTANT.value, ai_response))
            ai_message_id = cursor.lastrowid

            # 저장된 AI 메시지 조회
            cursor.execute("SELECT * FROM messages WHERE id = %s", (ai_message_id,))
            ai_msg_result = cursor.fetchone()

        return ChatMessageResponse(
            user_message=MessageResponse(**user_msg_result),
            ai_message=MessageResponse(**ai_msg_result)
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"메시지 전송 실패: {str(e)}")


@router.delete("/{chat_id}")
async def delete_chat(chat_id: int = Path(..., description="채팅 ID")):
    """
    채팅 삭제

    - **chat_id**: 삭제할 채팅 ID
    """
    try:
        query = "DELETE FROM chats WHERE id = %s"
        with db.get_cursor() as cursor:
            cursor.execute(query, (chat_id,))
            affected_rows = cursor.rowcount

        if affected_rows == 0:
            raise HTTPException(status_code=404, detail="채팅을 찾을 수 없습니다")

        return {"message": "채팅이 삭제되었습니다", "chat_id": chat_id}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"채팅 삭제 실패: {str(e)}")
