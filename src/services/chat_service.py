# -*- coding: utf-8 -*-
"""
Chat Service - 채팅 관련 비즈니스 로직
"""
from typing import List, Optional, Dict
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from src.repositories.chat_repository import ChatRepository
from src.repositories.message_repository import MessageRepository
from src.database.models import Chat, Message, MessageRole


class ChatService:
    """채팅 관련 비즈니스 로직을 처리하는 Service"""

    def __init__(self, db: Session):
        """
        Args:
            db: SQLAlchemy 데이터베이스 세션
        """
        self.db = db
        self.chat_repo = ChatRepository(db)
        self.message_repo = MessageRepository(db)

    def _verify_ownership(self, chat: Chat, user_id: int) -> None:
        """
        채팅 소유권 검증 (내부 메서드)

        Args:
            chat: 검증할 Chat 객체
            user_id: 현재 사용자 ID

        Raises:
            HTTPException: 소유권이 없는 경우
        """
        if chat.user_id != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="이 채팅에 접근할 권한이 없습니다"
            )

    def get_user_chats(self, user_id: int) -> List[Chat]:
        """
        사용자의 모든 채팅 목록 조회

        Args:
            user_id: 사용자 ID

        Returns:
            Chat 객체 리스트 (최신 업데이트 순)

        Raises:
            HTTPException: 조회 실패 시
        """
        try:
            return self.chat_repo.get_all_by_user(user_id)
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"채팅 목록 조회 실패: {str(e)}"
            )

    def create_chat(self, user_id: int, title: Optional[str] = None) -> Chat:
        """
        새로운 채팅 생성

        Args:
            user_id: 사용자 ID
            title: 채팅 제목 (선택사항, 기본값: "새 채팅")

        Returns:
            생성된 Chat 객체

        Raises:
            HTTPException: 생성 실패 시
        """
        try:
            new_chat = self.chat_repo.create(
                user_id=user_id,
                title=title or "새 채팅"
            )
            self.db.commit()
            self.db.refresh(new_chat)
            return new_chat
        except Exception as e:
            self.db.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"채팅 생성 실패: {str(e)}"
            )

    def get_chat(self, chat_id: int, user_id: int) -> Chat:
        """
        채팅 정보 조회 (소유권 검증 포함)

        Args:
            chat_id: 채팅 ID
            user_id: 사용자 ID

        Returns:
            Chat 객체

        Raises:
            HTTPException: 채팅이 없거나 권한이 없는 경우
        """
        try:
            chat = self.chat_repo.get_by_id(chat_id)
            if not chat:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="채팅을 찾을 수 없습니다"
                )

            # 소유권 확인
            self._verify_ownership(chat, user_id)

            return chat
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"채팅 조회 실패: {str(e)}"
            )

    def get_messages(self, chat_id: int, user_id: int) -> List[Message]:
        """
        채팅의 모든 메시지 조회 (소유권 검증 포함)

        Args:
            chat_id: 채팅 ID
            user_id: 사용자 ID

        Returns:
            Message 객체 리스트

        Raises:
            HTTPException: 채팅이 없거나 권한이 없는 경우
        """
        try:
            # 채팅 소유권 확인
            chat = self.chat_repo.get_by_id(chat_id)
            if not chat:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="채팅을 찾을 수 없습니다"
                )

            self._verify_ownership(chat, user_id)

            # 메시지 조회
            return self.message_repo.get_all_by_chat(chat_id)
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"메시지 조회 실패: {str(e)}"
            )

    def send_message(self, chat_id: int, user_id: int, content: str) -> Dict:
        """
        메시지 전송 (사용자 메시지 + AI 응답 생성 및 저장)

        Args:
            chat_id: 채팅 ID
            user_id: 사용자 ID
            content: 메시지 내용

        Returns:
            Dict: {"user_message": Message, "ai_message": Message}

        Raises:
            HTTPException: 채팅이 없거나 권한이 없는 경우
        """
        try:
            # 채팅 소유권 확인
            chat = self.chat_repo.get_by_id(chat_id)
            if not chat:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="채팅을 찾을 수 없습니다"
                )

            self._verify_ownership(chat, user_id)

            # 1. 사용자 메시지 저장
            user_message = self.message_repo.create(
                chat_id=chat_id,
                role=MessageRole.USER,
                content=content
            )

            # 2. AI 응답 생성 (현재는 간단한 응답)
            # TODO: 여기에 RAG 파이프라인 추가
            ai_response = f"'{content}'에 대한 응답입니다. (향후 RAG 파이프라인 추가 예정)"

            # 3. AI 메시지 저장
            ai_message = self.message_repo.create(
                chat_id=chat_id,
                role=MessageRole.ASSISTANT,
                content=ai_response
            )

            # 4. 트랜잭션 커밋
            self.db.commit()
            self.db.refresh(user_message)
            self.db.refresh(ai_message)

            return {
                "user_message": user_message,
                "ai_message": ai_message
            }
        except HTTPException:
            raise
        except Exception as e:
            self.db.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"메시지 전송 실패: {str(e)}"
            )

    def update_title(self, chat_id: int, user_id: int, title: str) -> Chat:
        """
        채팅 제목 업데이트 (소유권 검증 포함)

        Args:
            chat_id: 채팅 ID
            user_id: 사용자 ID
            title: 새로운 제목

        Returns:
            업데이트된 Chat 객체

        Raises:
            HTTPException: 채팅이 없거나 권한이 없는 경우
        """
        try:
            chat = self.chat_repo.get_by_id(chat_id)
            if not chat:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="채팅을 찾을 수 없습니다"
                )

            # 소유권 확인
            self._verify_ownership(chat, user_id)

            # 제목 업데이트
            updated_chat = self.chat_repo.update_title(chat, title)
            self.db.commit()
            self.db.refresh(updated_chat)

            return updated_chat
        except HTTPException:
            raise
        except Exception as e:
            self.db.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"채팅 제목 업데이트 실패: {str(e)}"
            )

    def delete_chat(self, chat_id: int, user_id: int) -> Dict:
        """
        채팅 삭제 (소유권 검증 포함)

        Args:
            chat_id: 채팅 ID
            user_id: 사용자 ID

        Returns:
            Dict: {"message": str, "chat_id": int}

        Raises:
            HTTPException: 채팅이 없거나 권한이 없는 경우
        """
        try:
            chat = self.chat_repo.get_by_id(chat_id)
            if not chat:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="채팅을 찾을 수 없습니다"
                )

            # 소유권 확인
            self._verify_ownership(chat, user_id)

            # 채팅 삭제
            self.chat_repo.delete(chat)
            self.db.commit()

            return {
                "message": "채팅이 삭제되었습니다",
                "chat_id": chat_id
            }
        except HTTPException:
            raise
        except Exception as e:
            self.db.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"채팅 삭제 실패: {str(e)}"
            )
