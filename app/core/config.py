"""
Configuration management using Pydantic Settings.

Handles all environment variables and application settings with
validation and type safety.
"""

from typing import Annotated, Any

from pydantic import BeforeValidator, ConfigDict

from pydantic_settings import BaseSettings


def _coerce_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() not in {"0", "false", "off", "no", "release"}
    return bool(value)


BoolStr = Annotated[bool, BeforeValidator(_coerce_bool)]


def _split_csv(value: str | None) -> list[str]:
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables.

    All settings are validated through Pydantic and support
    type coercion for environment variables.

    All fields have sensible defaults to allow the application to start
    even if .env is not fully configured.
    """

    # PostgreSQL Configuration
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_db: str = "govlens"
    postgres_user: str = "govlens_user"
    postgres_password: str = "changeme"

    # Qdrant Configuration
    qdrant_host: str = "localhost"
    qdrant_port: int = 6333
    qdrant_api_key: str | None = None
    qdrant_collection: str = "government_documents"

    # Ollama / generation configuration
    ollama_base_url: str = "http://ollama:11434"
    # The 4B instruct build fits an 8-16 GB laptop and answers directly. (Plain
    # "qwen3:4b" is now a thinking build that narrates its reasoning.) qwen3:8b
    # answers somewhat better but needs ~8 GB of RAM for itself.
    ollama_model: str = "qwen3:4b-instruct"
    ollama_timeout_seconds: int = 900
    ollama_num_predict: int = 512
    # How long Ollama keeps the model loaded after a request. "0" unloads it
    # immediately: each answer pays ~5 s to reload, but Ollama's prompt cache
    # (up to 8 GB of RAM) is freed every time, which prevents out-of-memory
    # crashes on 8-16 GB laptops. Use e.g. "5m" on machines with more memory.
    ollama_keep_alive: str = "0"

    # Embedding and retrieval configuration
    embedding_model: str = "BAAI/bge-small-en-v1.5"
    hybrid_search_enabled: BoolStr = True
    retrieval_candidate_multiplier: int = 3
    reranker_enabled: BoolStr = True
    reranker_model: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"
    # Reranked chunks scoring below this are treated as irrelevant (0 disables).
    reranker_min_score: float = 0.01

    # Ask the LLM for metadata fields the rule-based patterns missed (values are verified against the text).
    metadata_llm_fallback: BoolStr = True

    # Ingestion configuration
    upload_dir: str = "data/uploads"
    max_upload_mb: int = 50
    # Comma-separated directories that path-based ingestion may read from.
    ingest_allowed_dirs: str = "/app,data/uploads"
    ingest_workers: int = 1

    # Security configuration
    # When False, every request is treated as an admin (local experiments only).
    auth_enabled: BoolStr = True
    # First admin account, created at startup when no users exist. If no
    # password is set, one is generated and written to data/initial_admin_password.txt.
    admin_username: str = "admin"
    admin_password: str | None = None
    token_ttl_hours: int = 12
    # Optional service keys for scripts: "key" (admin) or "key:VIEWER", comma-separated.
    api_keys: str = ""
    rate_limit_per_minute: int = 60
    # Failed and successful sign-in attempts per client IP.
    login_rate_limit_per_minute: int = 10
    # "database" shares counts across API workers; "memory" is per process.
    rate_limit_backend: str = "database"
    # Comma-separated origins allowed for CORS. Empty disables cross-origin access.
    cors_origins: str = ""

    # Application Configuration
    env: str = "development"
    debug: BoolStr = False
    # Log every SQL statement (very verbose).
    db_echo: BoolStr = False
    log_level: str = "INFO"
    # "text" or "json"
    log_format: str = "text"

    model_config = ConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    @property
    def database_url(self) -> str:
        """
        Construct the PostgreSQL database URL.

        Returns:
            str: PostgreSQL connection URL in format
                 postgresql+psycopg2://user:password@host:port/dbname
        """
        return (
            f"postgresql+psycopg2://{self.postgres_user}:"
            f"{self.postgres_password}@{self.postgres_host}:"
            f"{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def qdrant_url(self) -> str:
        """
        Construct the Qdrant connection URL.

        Returns:
            str: Qdrant connection URL in format http://host:port
        """
        return f"http://{self.qdrant_host}:{self.qdrant_port}"

    @property
    def api_key_roles(self) -> dict[str, str]:
        """Map each service key to its role name (default ADMIN)."""

        roles: dict[str, str] = {}
        for entry in _split_csv(self.api_keys):
            key, _, role = entry.partition(":")
            roles[key.strip()] = (role.strip() or "ADMIN").upper()
        return roles

    @property
    def cors_origin_list(self) -> list[str]:
        return _split_csv(self.cors_origins)

    @property
    def ingest_allowed_dir_list(self) -> list[str]:
        return _split_csv(self.ingest_allowed_dirs)


# Global settings instance loaded from environment
settings = Settings()
