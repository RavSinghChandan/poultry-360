"""Settings, from the environment with safe defaults."""
from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    app_name: str = "Poultry 360"
    version: str = "0.2.0"
    # READ_ONLY by default: a public demo must not be able to change anything.
    policy_mode: str = os.environ.get("POULTRY_POLICY_MODE", "read_only")
    cors_origins: str = os.environ.get("POULTRY_CORS", "*")

    @property
    def llm_enabled(self) -> bool:
        return bool(os.environ.get("DEEPSEEK_API_KEY", "").strip())


settings = Settings()
