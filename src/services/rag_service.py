# -*- coding: utf-8 -*-
"""
RAG Service - Retrieval-Augmented Generation Pipeline

pgvector 기반 벡터 검색을 활용한 RAG 파이프라인을 구현합니다.
1. 사용자 쿼리 임베딩 (OpenAI text-embedding-3-small)
2. pgvector place table 검색
3. 검색 결과를 컨텍스트로 변환
4. 시스템 지시사항 + 컨텍스트 + 대화 내역 + 사용자 질문으로 프롬프트 구성
5. Claude (OpenRouter) 로 응답 생성
6. 벡터 스토어 장애 시 LLM-only 폴백 지원
"""

from typing import List, Optional
import logging

from openai import OpenAI
from langchain_openai import ChatOpenAI

from src.config import settings
from src.database.models import Message
from src.memory.vector_store import search_place_embeddings

logger = logging.getLogger(__name__)

# Maximum number of chat history messages to include in prompt
_MAX_HISTORY_MESSAGES = 10

_SYSTEM_INSTRUCTION = (
    "당신은 카카오맵 데이터를 기반으로 숙소와 식당을 추천하는 AI 어시스턴트입니다."
)


class RagService:
    """
    RAG (Retrieval-Augmented Generation) 서비스.

    OpenAI 임베딩, pgvector 검색, Claude LLM 을 조합하여
    사용자 질의에 대한 장소 추천 응답을 생성합니다.
    모든 외부 클라이언트는 최초 사용 시점에 지연 초기화됩니다.
    """

    def __init__(self) -> None:
        self._openai_client: Optional[OpenAI] = None
        self._llm: Optional[ChatOpenAI] = None

    # ------------------------------------------------------------------
    # Lazy-initialized clients
    # ------------------------------------------------------------------

    @property
    def openai_client(self) -> OpenAI:
        """OpenAI 클라이언트 (임베딩용). 최초 호출 시 생성."""
        if self._openai_client is None:
            self._openai_client = OpenAI(api_key=settings.openai_api_key)
        return self._openai_client

    @property
    def llm(self) -> ChatOpenAI:
        """ChatOpenAI (OpenRouter 경유 Claude). 최초 호출 시 생성."""
        if self._llm is None:
            self._llm = ChatOpenAI(
                model=settings.rag_model,
                api_key=settings.openrouter,
                base_url=settings.openrouter_api_base,
            )
        return self._llm

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def generate_response(
        self,
        user_query: str,
        chat_history: List[Message],
    ) -> str:
        """
        RAG 파이프라인을 실행하여 응답을 생성합니다.

        Args:
            user_query: 사용자 질의 텍스트.
            chat_history: 이전 대화 메시지 목록 (DB Message 객체).

        Returns:
            LLM 이 생성한 응답 문자열.

        Raises:
            Exception: 벡터 스토어 장애 시 ``rag_fallback_enabled`` 가 False 이면
                       원본 예외를 다시 발생시킵니다.
        """
        # 1. Embed query
        try:
            query_embedding = self._embed_query(user_query)
        except Exception as exc:
            logger.error(f"Failed to generate embedding: {exc}")
            if not settings.rag_fallback_enabled:
                raise
            # Fallback: use empty context with LLM-only response
            query_embedding = None

        # 2. Search vector store (with graceful fallback)
        context = ""
        if query_embedding is not None:
            try:
                results = self._search_vector_store(query_embedding)
                context = self._format_context(results)
            except Exception as exc:
                logger.warning(f"Vector search failed: {exc}")
                if not settings.rag_fallback_enabled:
                    raise

        # 3. Build prompt
        prompt = self._build_prompt(context, chat_history, user_query)

        # 4. Generate with LLM
        response = self._generate(prompt)
        return response

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _embed_query(self, query: str) -> List[float]:
        """
        OpenAI 임베딩 API 를 사용하여 쿼리를 벡터로 변환합니다.

        Args:
            query: 임베딩할 텍스트.

        Returns:
            1536 차원 float 벡터.
        """
        response = self.openai_client.embeddings.create(
            input=query,
            model=settings.embedding_model,
        )
        return response.data[0].embedding

    def _search_vector_store(self, query_embedding: List[float]) -> List[dict]:
        """
        pgvector-backed place table에서 유사도 검색을 수행합니다.

        Args:
            query_embedding: 쿼리 임베딩 벡터.

        Returns:
            검색 결과 리스트 (각 항목은 distance + entity 포함).
        """
        return search_place_embeddings(query_embedding, settings.rag_top_k)

    def _format_context(self, results: List[dict]) -> str:
        """
        검색 결과를 프롬프트에 삽입할 컨텍스트 문자열로 변환합니다.

        Args:
            results: 벡터 검색 결과 리스트.

        Returns:
            번호가 매겨진 장소 정보 문자열. 결과가 없으면 빈 문자열.
        """
        if not results:
            return ""

        context_parts: List[str] = []
        for i, hit in enumerate(results, 1):
            entity = hit.get("entity", {})
            context_parts.append(
                f"{i}. {entity.get('name', 'Unknown')}\n"
                f"   주소: {entity.get('address', 'N/A')}\n"
                f"   평점: {entity.get('rating', 'N/A')}\n"
                f"   타입: {entity.get('place_type', 'N/A')}"
            )

        return "\n\n".join(context_parts)

    def _build_prompt(
        self,
        context: str,
        chat_history: List[Message],
        user_query: str,
    ) -> str:
        """
        시스템 지시사항, 컨텍스트, 대화 내역, 사용자 질문을 합쳐
        최종 프롬프트를 구성합니다.

        Args:
            context: 검색 결과 컨텍스트 (빈 문자열일 수 있음).
            chat_history: 이전 대화 메시지 목록.
            user_query: 현재 사용자 질문.

        Returns:
            LLM 에 전달할 프롬프트 문자열.
        """
        # System instruction
        system = _SYSTEM_INSTRUCTION

        # Append retrieved context
        if context:
            system += f"\n\n다음은 검색된 관련 장소들입니다:\n{context}"

        # Build chat history (last N messages)
        history_text = ""
        recent_messages = chat_history[-_MAX_HISTORY_MESSAGES:]
        for msg in recent_messages:
            role_value = msg.role.value if hasattr(msg.role, "value") else str(msg.role)
            if role_value == "user":
                history_text += f"사용자: {msg.content}\n"
            elif role_value == "assistant":
                history_text += f"어시스턴트: {msg.content}\n"

        # Combine into final prompt
        prompt = f"{system}\n\n"
        if history_text:
            prompt += f"대화 내역:\n{history_text}\n"
        prompt += f"사용자 질문: {user_query}\n\n답변:"

        return prompt

    def _generate(self, prompt: str) -> str:
        """
        LLM 을 호출하여 응답을 생성합니다.

        Args:
            prompt: 완성된 프롬프트 문자열.

        Returns:
            LLM 응답 텍스트.
        """
        response = self.llm.invoke(prompt)
        return response.content


# Singleton instance - import this across the application
rag_service = RagService()
