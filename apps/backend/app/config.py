"""Runtime settings, loaded from environment / .env (spec §7, §8)."""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # CORS — the Vite dev origin by default.
    cors_origins: list[str] = ["http://localhost:5173"]

    # Supabase (not wired in the scaffold; fill in to enable persistence/auth).
    supabase_url: str = ""
    supabase_anon_key: str = ""
    supabase_service_key: str = ""


settings = Settings()
