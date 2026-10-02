"""Nutrition-specific logic: AI tip with a safe built-in fallback."""
import logging

from .gemini_client import GeminiError
from .gemini_flash_generator import generate_nutrition_tip_with_flash

logger = logging.getLogger("fitbuddy.nutrition")

FALLBACK_TIPS = {
    "weight_loss": (
        "Build each meal around lean protein and vegetables, and drink a glass of water before "
        "eating. It keeps you full and makes a calorie deficit easier to stick to."
    ),
    "muscle_gain": (
        "Include a good protein source (eggs, chicken, fish, paneer, lentils or Greek yogurt) in "
        "your post-workout meal to support muscle repair and growth."
    ),
    "general": (
        "Drink water through the day, eat a mix of protein, whole grains and vegetables, and aim "
        "for 7-9 hours of sleep so your body can recover between workouts."
    ),
}


def get_fallback_tip(goal: str) -> str:
    text = (goal or "").lower()
    if any(word in text for word in ("lose", "loss", "fat", "slim", "cut", "weight")):
        return FALLBACK_TIPS["weight_loss"]
    if any(word in text for word in ("muscle", "gain", "bulk", "strength", "mass")):
        return FALLBACK_TIPS["muscle_gain"]
    return FALLBACK_TIPS["general"]


def get_nutrition_tip(goal: str) -> dict:
    """Return ``{"tip": str, "source": "gemini" | "fallback"}``. Never raises."""
    try:
        return {"tip": generate_nutrition_tip_with_flash(goal), "source": "gemini"}
    except GeminiError as exc:
        logger.warning("Using fallback nutrition tip: %s", exc)
        return {"tip": get_fallback_tip(goal), "source": "fallback"}
