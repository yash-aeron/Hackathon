"""Application settings, loaded from environment variables and `.env`.

Everything the rest of the backend needs to know about its runtime environment
lives here so that tests and modules can share one cached ``Settings`` object.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict

APP_VERSION = "1.0.0"


class Settings(BaseSettings):
    """Runtime configuration for the Scoutly backend.

    Values are read from process environment variables first, then from a
    ``.env`` file in the current working directory (``backend/``).
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- LLM ---------------------------------------------------------------
    llm_provider: str = "openai"
    llm_api_key: str = ""
    llm_model: str = "gpt-4o-mini"
    llm_base_url: str = ""
    mock_llm: bool = False
    llm_timeout_seconds: float = 10.0

    # --- Storage -----------------------------------------------------------
    database_url: str = "sqlite:///./scoutly.db"

    # --- Web ---------------------------------------------------------------
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"

    # --- Embeddings --------------------------------------------------------
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    #: ``auto`` uses sentence-transformers (falling back to hashed embeddings if
    #: it cannot load); ``hashing`` skips torch entirely for a faster cold start.
    embedding_backend: str = "auto"

    @property
    def mock_mode(self) -> bool:
        """True when every LLM call should return canned JSON.

        Mock mode is active when explicitly requested via ``MOCK_LLM=true`` or
        when no API key is configured at all, so a fresh clone of the repo runs
        without any credentials.
        """
        return bool(self.mock_llm) or not self.llm_api_key.strip()

    @property
    def provider(self) -> str:
        """Normalised provider name (``mock`` when mock mode is on)."""
        if self.mock_mode:
            return "mock"
        normalised = (self.llm_provider or "openai").strip().lower()
        if normalised in {"openai", "openrouter", "azure", "groq", "together", "local"}:
            return "openai"
        if normalised == "anthropic":
            return "anthropic"
        return normalised

    @property
    def cors_origin_list(self) -> list[str]:
        """Allowed CORS origins as a list."""
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the process-wide cached :class:`Settings` instance."""
    return Settings()
