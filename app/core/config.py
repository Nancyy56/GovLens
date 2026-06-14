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
    
    # Application Configuration
    env: str = "development"
    debug: BoolStr = False
    
    model_config = ConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
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


# Global settings instance loaded from environment
settings = Settings()
