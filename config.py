"""Runtime configuration, read from environment variables."""

from __future__ import annotations

import os
from dataclasses import dataclass, field


def _normalize_db_url(url: str) -> str:
    # Accept the common Heroku/Docker style URLs and use the psycopg 3 driver.
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://") :]
    if url.startswith("postgresql://"):
        url = "postgresql+psycopg://" + url[len("postgresql://") :]
    return url


def _split(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


@dataclass(frozen=True)
class Settings:
    database_url: str = "sqlite:///./estimates.db"
    cors_origins: list[str] = field(default_factory=lambda: ["http://localhost:3000"])
    log_level: str = "INFO"
    max_input_chars: int = 2000

    def __post_init__(self) -> None:
        object.__setattr__(self, "database_url", _normalize_db_url(self.database_url))

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            database_url=os.getenv("DATABASE_URL", cls.database_url),
            cors_origins=_split(os.getenv("CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000")),
            log_level=os.getenv("LOG_LEVEL", "INFO").upper(),
            max_input_chars=int(os.getenv("MAX_INPUT_CHARS", "2000")),
        )
