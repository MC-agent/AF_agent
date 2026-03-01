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

    # Database Configuration - MySQL components
    mysql_host: Optional[str] = None
    mysql_port: Optional[str] = "3306"
    mysql_user: Optional[str] = None
    mysql_password: Optional[str] = None
    mysql_database: Optional[str] = None

    # Database URL (can be constructed from MySQL components or provided directly)
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

        if all([self.mysql_host, self.mysql_user, self.mysql_password, self.mysql_database]):
            return f"mysql+pymysql://{self.mysql_user}:{self.mysql_password}@{self.mysql_host}:{self.mysql_port}/{self.mysql_database}"

        raise ValueError(
            "Either database_url or all MySQL components (host, user, password, database) must be provided"
        )


# Singleton instance - import this across the application
settings = Settings()
