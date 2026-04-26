from typing import Optional

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    deploy_env: str = "local"
    enable_pipeline_routes: bool = True

    pg_host: Optional[str] = None
    pg_port: Optional[str] = "5432"
    pg_user: Optional[str] = None
    pg_password: Optional[str] = None
    pg_database: Optional[str] = None
 
    database_url: Optional[str] = None
    pgvector_database_url: Optional[str] = None

    openai_api_key: Optional[str] = None
    openrouter: Optional[str] = None
    openrouter_api_base: str = "https://openrouter.ai/api/v1"
    kakao_api_key: Optional[str] = None

    rag_fallback_enabled: bool = True
    rag_top_k: int = 5
    rag_max_distance: float = 0.45
    rag_model: str = "anthropic/claude-sonnet-4.5"
    embedding_model: str = "text-embedding-3-small"
    external_api_timeout_seconds: float = 25.0
    external_api_max_retries: int = 1
    database_connect_timeout_seconds: int = 5
    database_pool_timeout_seconds: int = 10
    startup_db_init_timeout_seconds: float = 10.0

    langchain_tracing_v2: Optional[str] = None
    langchain_endpoint: Optional[str] = None
    langchain_api_key: Optional[str] = None
    langchain_project: Optional[str] = None

    class Config:
        env_file = ".env"
        case_sensitive = False
        extra = "ignore"

    def _build_postgres_url(self) -> str:
 
        if all([self.pg_host, self.pg_user, self.pg_password, self.pg_database]):
            return (
                f"postgresql+psycopg2://{self.pg_user}:{self.pg_password}"
                f"@{self.pg_host}:{self.pg_port}/{self.pg_database}"
            )

        raise ValueError(
            "Either database_url or all PostgreSQL components "
            "(host, user, password, database) must be provided"
        )

    def get_database_url(self) -> str:
        if self.database_url:
            return self.database_url

        return self._build_postgres_url()

    def get_pgvector_database_url(self) -> str:
        if self.pgvector_database_url:
            return self.pgvector_database_url

        return self.get_database_url()


settings = Settings()
