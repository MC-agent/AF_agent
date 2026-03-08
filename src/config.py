"""
Centralized configuration module for AF_agent.

This module provides a single source of truth for all environment variables
and configuration settings used across the application.
"""

from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables.

    All settings can be overridden via environment variables.
    The .env file is automatically loaded if present.
    """

    # Deployment Configuration
    deploy_env: str = "local"
    enable_pipeline_routes: bool = True

    # Database Configuration - PostgreSQL components
    pg_host: Optional[str] = None
    pg_port: Optional[str] = "5432"
    pg_user: Optional[str] = None
    pg_password: Optional[str] = None
    pg_database: Optional[str] = None

    # Database URL (can be constructed from PostgreSQL components or provided directly)
    database_url: Optional[str] = None

    # External API Keys
    openai_api_key: Optional[str] = None
    openrouter: Optional[str] = None  # Note: existing code uses "OPENROUTER" not "OPENROUTER_API_KEY"
    openrouter_api_base: str = "https://openrouter.ai/api/v1"
    kakao_api_key: Optional[str] = None

    # Vector Database Configuration
    milvus_uri: str = "http://localhost:19530"

    # RAG Configuration
    rag_fallback_enabled: bool = True
    rag_top_k: int = 5
    rag_model: str = "anthropic/claude-sonnet-4.5"
    embedding_model: str = "text-embedding-3-small"

    # LangChain Tracing Configuration (Optional)
    langchain_tracing_v2: Optional[str] = None
    langchain_endpoint: Optional[str] = None
    langchain_api_key: Optional[str] = None
    langchain_project: Optional[str] = None

    class Config:
        env_file = ".env"
        case_sensitive = False
        extra = "ignore"

    def get_database_url(self) -> str:
        """
        Get database URL, constructing from MySQL components if needed.

        Returns:
            Database URL string

        Raises:
            ValueError: If neither database_url nor MySQL components are provided
        """
        if self.database_url:
            return self.database_url

        if all([self.pg_host, self.pg_user, self.pg_password, self.pg_database]):
            return f"postgresql+psycopg2://{self.pg_user}:{self.pg_password}@{self.pg_host}:{self.pg_port}/{self.pg_database}"

        raise ValueError(
            "Either database_url or all PostgreSQL components (host, user, password, database) must be provided"
        )


# Singleton instance - import this across the application
settings = Settings()
