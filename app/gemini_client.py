"""Thin wrapper around the Google Gen AI SDK (``google-genai``).

All Gemini calls in FitBuddy go through ``generate_text``. It
  * builds one shared client,
  * retries once on temporary errors (rate limit / server busy),
  * falls back to GEMINI_FALLBACK_MODEL if the chosen model is retired or has no quota,
  * raises ``GeminiError`` with a human-readable message instead of returning
    "Error: ..." text, so a failure is never saved as a workout plan.
"""
import logging
import re
import time

from google import genai
from google.genai import errors as genai_errors

from .config import settings

logger = logging.getLogger("fitbuddy.gemini")

PLACEHOLDER_KEYS = {"", "your_gemini_api_key_here"}
RETRY_CODES = {429, 500, 502, 503, 504}
SWITCH_MODEL_CODES = {403, 404} | RETRY_CODES
REQUEST_TIMEOUT_MS = 90_000

_client = None


class GeminiError(Exception):
    """Raised when Gemini cannot produce a usable answer."""


def _get_client():
    global _client
    if settings.api_key in PLACEHOLDER_KEYS:
        raise GeminiError(
            "No Gemini API key found. Open the .env file, set GOOGLE_API_KEY=<your key>, "
            "then restart the server."
        )
    if _client is None:
        _client = genai.Client(
            api_key=settings.api_key,
            http_options={"timeout": REQUEST_TIMEOUT_MS},
        )
    return _client


def generate_text(prompt: str, model: str) -> str:
    """Send ``prompt`` to ``model`` and return the answer text."""
    client = _get_client()

    candidates = [model]
    if settings.fallback_model and settings.fallback_model != model:
        candidates.append(settings.fallback_model)

    last_problem = "unknown error"
    for name in candidates:
        for attempt in (1, 2):
            try:
                response = client.models.generate_content(model=name, contents=prompt)
            except genai_errors.APIError as exc:
                code = getattr(exc, "code", None)
                message = (getattr(exc, "message", None) or str(exc)).strip()
                last_problem = f"{name}: HTTP {code} - {message[:200]}"
                logger.warning("Gemini call failed (%s)", last_problem)

                if code in (400, 401) and "api key" in message.lower():
                    raise GeminiError(
                        "Gemini rejected the API key. Check GOOGLE_API_KEY in the .env file."
                    ) from exc
                if code in RETRY_CODES and attempt == 1:
                    time.sleep(1.5)
                    continue                      # retry the same model once
                if code in SWITCH_MODEL_CODES:
                    break                         # try the fallback model
                raise GeminiError(f"Gemini request failed ({last_problem})") from exc
            except Exception as exc:              # network down, timeout, ...
                raise GeminiError(f"Could not reach Gemini: {exc}") from exc

            text = (getattr(response, "text", None) or "").strip()
            if not text:
                raise GeminiError(
                    f"Model '{name}' returned an empty answer (it may have been blocked by a "
                    "safety filter). Try rewording your goal or feedback."
                )
            return text

    raise GeminiError(
        f"Gemini could not answer ({last_problem}). If a model name is retired, update "
        "GEMINI_PLAN_MODEL / GEMINI_TIP_MODEL / GEMINI_FALLBACK_MODEL in the .env file."
    )


def to_plain_text(text: str) -> str:
    """Remove markdown symbols so the answer reads cleanly inside <pre> blocks."""
    text = text.replace("**", "")
    text = re.sub(r"^\s{0,3}#{1,6}\s*", "", text, flags=re.MULTILINE)
    text = re.sub(r"^(\s*)[*•]\s+", r"\1- ", text, flags=re.MULTILINE)
    return text.strip()
