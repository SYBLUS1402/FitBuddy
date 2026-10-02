"""Central configuration for FitBuddy.

Every value comes from environment variables, which python-dotenv fills from the
``.env`` file in the project root (see ``.env.example``).
"""
import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent      # .../fitbuddy/app
PROJECT_DIR = BASE_DIR.parent                   # .../fitbuddy

load_dotenv(PROJECT_DIR / ".env")


def _get(name: str, default: str = "") -> str:
    value = os.getenv(name)
    return value.strip() if value and value.strip() else default


@dataclass(frozen=True)
class Settings:
    api_key: str
    plan_model: str          # workout generation + feedback updates
    tip_model: str           # nutrition / recovery tips
    fallback_model: str      # used if the primary model is retired or out of quota
    database_url: str
    admin_username: str
    admin_password: str      # empty string = admin page is open (local use)


def load_settings() -> Settings:
    default_db = "sqlite:///" + (PROJECT_DIR / "fitbuddy.db").as_posix()
    return Settings(
        api_key=_get("GOOGLE_API_KEY") or _get("GEMINI_API_KEY"),
        plan_model=_get("GEMINI_PLAN_MODEL", "gemini-3.8-flash"),
        tip_model=_get("GEMINI_TIP_MODEL", "gemini-3.5-flash-lite"),
        fallback_model=_get("GEMINI_FALLBACK_MODEL", "gemini-3.8-flash"),
        database_url=_get("DATABASE_URL", default_db),
        admin_username=_get("ADMIN_USERNAME", "admin"),
        admin_password=_get("ADMIN_PASSWORD", ""),
    )


settings = load_settings()
