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

    # Development — Ollama
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "gemma4"

    # Production — OpenAI (primary)
    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-4o"

    # Production fallback — Anthropic
    ANTHROPIC_API_KEY: str = ""
    ANTHROPIC_MODEL: str = "claude-sonnet-4-20250514"

    # DeepAgent settings
    SKILLS_DIR: str = "server/properties/skills"
    MAX_AGENT_ITERATIONS: int = 3

    # Storage
    ANALYSES_FILE: str = "server/data/analyses.json"

    model_config = ConfigDict(env_file=".env", env_file_encoding="utf-8")


settings = Settings()
