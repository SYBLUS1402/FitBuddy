"""FitBuddy - AI Fitness Plan Generator.  Run with:  uvicorn app.main:app --reload"""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from .config import BASE_DIR, settings
from .database import init_db
from .gemini_client import PLACEHOLDER_KEYS
from .routes import router

logger = logging.getLogger("uvicorn.error")


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()                                    # creates fitbuddy.db + tables on first run
    if settings.api_key in PLACEHOLDER_KEYS:
        logger.warning("GOOGLE_API_KEY is not set - add it to the .env file, then restart.")
    else:
        logger.info("Gemini models -> plans: %s | tips: %s | fallback: %s",
                    settings.plan_model, settings.tip_model, settings.fallback_model)
    yield


app = FastAPI(
    title="FitBuddy - AI Fitness Plan Generator",
    description="Personalized 7-day workout plans and nutrition tips powered by Google Gemini.",
    version="1.0.0",
    lifespan=lifespan,
)

app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")
app.include_router(router)
