# -*- coding: utf-8 -*-
"""
Message Repository - Message 테이블 데이터 접근 레이어
"""
from typing import List
from sqlalchemy.orm import Session
from src.database.models import Message, MessageRole


class MessageRepository:
    """Message 테이블에 대한 CRUD 작업을 담당하는 Repository"""

    def __init__(self, db: Session):
        """
        Args:
            db: SQLAlchemy 데이터베이스 세션
        """
        self.db = db

    def get_all_by_chat(self, chat_id: int) -> List[Message]:
        """
        채팅의 모든 메시지 조회 (시간순 정렬)

        Args:
            chat_id: 조회할 채팅 ID

        Returns:
            Message 객체 리스트
        """
        return self.db.query(Message).filter(
            Message.chat_id == chat_id
        ).order_by(Message.created_at.asc()).all()

    def create(self, chat_id: int, role: MessageRole, content: str) -> Message:
        """
        새로운 메시지 생성

        Args:
            chat_id: 채팅 ID
            role: 메시지 역할 (user/assistant)
            content: 메시지 내용

        Returns:
            생성된 Message 객체
        """
        new_message = Message(
            chat_id=chat_id,
            role=role,
            content=content
        )
        self.db.add(new_message)
        self.db.flush()  # ID를 즉시 생성하되 커밋은 Service에서 처리
        self.db.refresh(new_message)
        return new_message
