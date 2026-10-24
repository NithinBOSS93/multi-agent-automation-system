"""Groq-hosted LLaMA models, shared by all agents."""
from functools import lru_cache

from langchain_groq import ChatGroq

from app.core.config import settings


class MissingAPIKey(RuntimeError):
    pass


def _check_key() -> None:
    if not settings.groq_api_key:
        raise MissingAPIKey(
            "GROQ_API_KEY is not set. Copy .env.example to .env and add your key "
            "from https://console.groq.com/keys"
        )


@lru_cache
def get_llm(fast: bool = False, streaming: bool = True) -> ChatGroq:
    _check_key()
    return ChatGroq(
        api_key=settings.groq_api_key,
        model=settings.groq_fast_model if fast else settings.groq_model,
        temperature=settings.temperature,
        max_tokens=settings.max_tokens,
        streaming=streaming,
    )
