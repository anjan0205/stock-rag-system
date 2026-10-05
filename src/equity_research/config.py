"""Central configuration, loaded from environment / .env.

Phase 1 needs no secrets. ANTHROPIC_API_KEY is declared here so it is ready
for Phase 2, but it is optional and nothing in the data layer reads it.
"""
from __future__ import annotations

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# Project root = three levels up from this file:
# src/equity_research/config.py -> src/equity_research -> src -> <root>
PROJECT_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """Typed application settings."""

    model_config = SettingsConfigDict(
        env_file=str(PROJECT_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- LLM (Phase 2+) ---
    gemini_api_key: str | None = Field(default=None, alias="GEMINI_API_KEY")
    gemini_model: str = Field(default="gemini-3.6-flash", alias="GEMINI_MODEL")

    gemini_model_pro: str = Field(default="gemini-2.5-pro", alias="GEMINI_MODEL_PRO")
    anthropic_api_key: str | None = Field(default=None, alias="ANTHROPIC_API_KEY")
    anthropic_model: str = Field(default="claude-sonnet-5", alias="ANTHROPIC_MODEL")


    # --- Data layer knobs ---
    news_lookback_days: int = Field(default=30, alias="NEWS_LOOKBACK_DAYS")
    price_history_period: str = Field(default="2y", alias="PRICE_HISTORY_PERIOD")

    # --- Storage paths (relative to project root unless absolute) ---
    chroma_dir: str = Field(default="data/chroma", alias="CHROMA_DIR")
    raw_data_dir: str = Field(default="data/raw", alias="RAW_DATA_DIR")
    log_dir: str = Field(default="logs", alias="LOG_DIR")

    def _resolve(self, value: str) -> Path:
        p = Path(value)
        return p if p.is_absolute() else PROJECT_ROOT / p

    @property
    def chroma_path(self) -> Path:
        return self._resolve(self.chroma_dir)

    @property
    def raw_data_path(self) -> Path:
        return self._resolve(self.raw_data_dir)

    @property
    def log_path(self) -> Path:
        return self._resolve(self.log_dir)

    def ensure_dirs(self) -> None:
        for p in (self.chroma_path, self.raw_data_path, self.log_path):
            p.mkdir(parents=True, exist_ok=True)


_settings: Settings | None = None


def get_settings() -> Settings:
    """Return a cached Settings instance."""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
