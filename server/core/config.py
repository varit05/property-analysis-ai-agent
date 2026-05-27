from pydantic import ConfigDict
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    APP_NAME: str = "Property Analysis API"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = True

    # Environment
    ENVIRONMENT: str = "development"  # "development" or "production"

    # Server
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    # Logging
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "json"  # "json" or "text"

    model_config = ConfigDict(env_file=".env", env_file_encoding="utf-8")


settings = Settings()
