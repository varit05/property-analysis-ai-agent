"""
LLM Factory — creates LLM instances based on the environment setting.

  - Development: Ollama (local)
  - Production: OpenAI (primary) with Anthropic (fallback)
"""

import logging

from langchain_core.language_models import BaseLanguageModel

from server.core.config import settings

logger = logging.getLogger(__name__)


def _get_primary_llm():
    """Return the primary LLM based on the environment setting."""
    env = settings.ENVIRONMENT.lower()

    if env == "production":
        from langchain_openai import ChatOpenAI

        logger.info("Using OpenAI as primary LLM (model=%s)", settings.OPENAI_MODEL)
        return ChatOpenAI(
            model=settings.OPENAI_MODEL,
            api_key=settings.OPENAI_API_KEY,
            temperature=0.1,
        )
    else:
        from langchain_ollama import ChatOllama

        logger.info("Using Ollama as primary LLM (model=%s)", settings.OLLAMA_MODEL)
        return ChatOllama(
            model=settings.OLLAMA_MODEL,
            base_url=settings.OLLAMA_BASE_URL,
            temperature=0.1,
        )


def _get_fallback_llm():
    """Return the fallback LLM. Only used in production when the primary fails."""
    env = settings.ENVIRONMENT.lower()

    if env == "production":
        from langchain_anthropic import ChatAnthropic

        logger.info(
            "Using Anthropic as fallback LLM (model=%s)", settings.ANTHROPIC_MODEL
        )
        return ChatAnthropic(
            model=settings.ANTHROPIC_MODEL,
            api_key=settings.ANTHROPIC_API_KEY,
            temperature=0.1,
        )
    return None


def get_llm() -> BaseLanguageModel:
    """Get the primary LLM wrapped with fallback support (production only)."""
    primary = _get_primary_llm()
    fallback = _get_fallback_llm()

    if fallback is not None:
        from langchain_core.runnables import RunnableWithFallbacks

        logger.info("Wrapping primary LLM with fallback chain")
        return RunnableWithFallbacks(
            runnable=primary,
            fallbacks=[fallback],
        )

    return primary


def get_llm_info() -> dict:
    """Return metadata about which LLMs are configured.

    Useful for the DeepAgent to decide whether to use Anthropic-specific
    features such as prompt caching with cache_control breakpoints.
    """
    env = settings.ENVIRONMENT.lower()
    info = {
        "primary": {
            "provider": "openai" if env == "production" else "ollama",
            "model": (
                settings.OPENAI_MODEL if env == "production" else settings.OLLAMA_MODEL
            ),
        },
        "has_fallback": env == "production",
    }
    if env == "production":
        info["fallback"] = {
            "provider": "anthropic",
            "model": settings.ANTHROPIC_MODEL,
        }
    return info


def is_anthropic_available() -> bool:
    """Return ``True`` if the Anthropic fallback model is configured."""
    env = settings.ENVIRONMENT.lower()
    return (
        env == "production"
        and bool(settings.ANTHROPIC_API_KEY)
        and bool(settings.ANTHROPIC_MODEL)
    )
