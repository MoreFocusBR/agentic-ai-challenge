from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # LLM
    openai_api_key: str
    llm_model: str = "gpt-4o"
    embedding_model: str = "text-embedding-3-small"

    # PostgreSQL
    postgres_host: str = "postgres"
    postgres_port: int = 5432
    postgres_db: str = "corporativo"
    postgres_user: str = "postgres"
    postgres_password: str

    # Segurança
    auth_api_key: str

    # PDF
    documents_dir: str = "documents"

    # Timeout do agente (segundos)
    agent_timeout: int = 30

    @property
    def pg_dsn(self) -> str:
        return (
            f"postgresql://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def pg_dsn_async(self) -> str:
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )


settings = Settings()
