"""Pydantic models used to validate form data and JSON bodies."""
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

Intensity = Literal["low", "medium", "high"]


class _Base(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)


class _IntensityMixin(_Base):
    intensity: Intensity

    @field_validator("intensity", mode="before")
    @classmethod
    def _normalize_intensity(cls, value):
        return value.strip().lower() if isinstance(value, str) else value


class UserInput(_IntensityMixin):
    """Everything the home-page form collects."""
    user_id: int = Field(..., gt=0, description="Unique number chosen by the user")
    username: str = Field(..., min_length=1, max_length=60)
    age: int = Field(..., ge=10, le=100)
    weight: float = Field(..., gt=20, le=350, description="Weight in kg")
    goal: str = Field(..., min_length=2, max_length=200)


class WorkoutRequest(_IntensityMixin):
    """Body for POST /generate-workout/gemini."""
    goal: str = Field(..., min_length=2, max_length=200)
    age: Optional[int] = Field(None, ge=10, le=100)
    weight: Optional[float] = Field(None, gt=20, le=350)


class FeedbackRequest(_Base):
    """Body for POST /update-plan/{user_id}."""
    feedback: str = Field(..., min_length=2, max_length=500)


class FeedbackForm(FeedbackRequest):
    """Feedback form on the result page (adds the user id)."""
    user_id: int = Field(..., gt=0)
