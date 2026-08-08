"""Runtime settings, loaded from environment / .env (spec §7, §8)."""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Deployment environment (CTO A10/S1). "production" makes startup
    # fail-fast: the app refuses to boot on the dev fallbacks (in-memory
    # stores, sentinel auth, open access) that a missing or typo'd env var
    # would otherwise silently select — the fail-open path the review called
    # a deploy blocker. Anything else is development semantics.
    app_env: str = "development"

    # CORS — the Vite dev origin by default.
    cors_origins: list[str] = ["http://localhost:5173"]

    # Supabase (not wired in the scaffold; fill in to enable persistence/auth).
    supabase_url: str = ""
    supabase_anon_key: str = ""
    supabase_service_key: str = ""


settings = Settings()
