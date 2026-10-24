"""Application settings, loaded from environment variables / .env file."""
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parents[2]  # backend/


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(BASE_DIR / ".env", BASE_DIR.parent / ".env"),
        extra="ignore",
    )

    # LLM (Groq)
    groq_api_key: str = ""
    groq_model: str = "llama-3.3-70b-versatile"
    groq_fast_model: str = "llama-3.1-8b-instant"
    temperature: float = 0.3
    max_tokens: int = 2048

    # Web search (optional) — https://tavily.com
    tavily_api_key: str = ""

    # Storage
    data_dir: Path = BASE_DIR / "data"
    database_file: str = "app.db"
    chroma_dir: str = "chroma"
    collection_name: str = "knowledge_base"

    # RAG
    chunk_size: int = 800
    chunk_overlap: int = 120
    top_k: int = 4
    embedding_dim: int = 384

    # MCP tools
    workspace_dir: Path = BASE_DIR / "data" / "workspace"

    # Auth
    jwt_secret: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60 * 24

    # CORS
    cors_origins: list[str] = ["http://localhost:3000", "http://127.0.0.1:3000"]

    @property
    def database_path(self) -> Path:
        return self.data_dir / self.database_file

    @property
    def chroma_path(self) -> Path:
        return self.data_dir / self.chroma_dir


settings = Settings()
settings.data_dir.mkdir(parents=True, exist_ok=True)
settings.workspace_dir.mkdir(parents=True, exist_ok=True)
