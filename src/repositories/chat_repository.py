# -*- coding: utf-8 -*-
"""
Chat Repository - Chat 테이블 데이터 접근 레이어
"""
from typing import Optional, List
from sqlalchemy.orm import Session
from src.database.models import Chat


class ChatRepository:
    """Chat 테이블에 대한 CRUD 작업을 담당하는 Repository"""

    def __init__(self, db: Session):
        """
        Args:
            db: SQLAlchemy 데이터베이스 세션
        """
        self.db = db

    def get_by_id(self, chat_id: int) -> Optional[Chat]:
        """
        채팅 ID로 조회

        Args:
            chat_id: 조회할 채팅 ID

        Returns:
            Chat 객체 또는 None (존재하지 않는 경우)
        """
        return self.db.query(Chat).filter(Chat.id == chat_id).first()

    def get_all_by_user(self, user_id: int) -> List[Chat]:
        """
        사용자의 모든 채팅 조회 (최신 업데이트 순으로 정렬)

        Args:
            user_id: 조회할 사용자 ID

        Returns:
            Chat 객체 리스트
        """
        return self.db.query(Chat).filter(
            Chat.user_id == user_id
        ).order_by(Chat.updated_at.desc()).all()

    def create(self, user_id: int, title: str) -> Chat:
        """
        새로운 채팅 생성

        Args:
            user_id: 사용자 ID
            title: 채팅 제목

        Returns:
            생성된 Chat 객체
        """
        new_chat = Chat(
            user_id=user_id,
            title=title
        )
        self.db.add(new_chat)
        self.db.flush()  # ID를 즉시 생성하되 커밋은 Service에서 처리
        self.db.refresh(new_chat)
        return new_chat

    def update_title(self, chat: Chat, title: str) -> Chat:
        """
        채팅 제목 업데이트

        Args:
            chat: 업데이트할 Chat 객체
            title: 새로운 제목

        Returns:
            업데이트된 Chat 객체
        """
        chat.title = title
        self.db.flush()  # 변경사항을 반영하되 커밋은 Service에서 처리
        self.db.refresh(chat)
        return chat

    def delete(self, chat: Chat) -> None:
        """
        채팅 삭제

        Args:
            chat: 삭제할 Chat 객체
        """
        self.db.delete(chat)
        self.db.flush()  # 삭제를 반영하되 커밋은 Service에서 처리
