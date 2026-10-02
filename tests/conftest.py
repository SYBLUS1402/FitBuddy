"""Test setup: use a throw-away database and never touch the real Gemini API."""
import os
import tempfile

_tmp_dir = tempfile.mkdtemp(prefix="fitbuddy_tests_")
os.environ["DATABASE_URL"] = "sqlite:///" + os.path.join(_tmp_dir, "test.db").replace("\\", "/")
os.environ["GOOGLE_API_KEY"] = "test-key"
os.environ["ADMIN_PASSWORD"] = ""          # admin page open during tests

import pytest                                   # noqa: E402
from fastapi.testclient import TestClient       # noqa: E402

from app import nutrition, routes               # noqa: E402
from app.database import Base, engine           # noqa: E402
from app.gemini_client import GeminiError       # noqa: E402
from app.main import app                        # noqa: E402

FAKE_PLAN = "Day 1: Upper Body\nWarm-up: Arm circles\nMain Workout:\n- Push-ups 3x10\nCooldown: Stretch"
FAKE_UPDATED = FAKE_PLAN + "\nDay 2: Cardio (added per feedback)"


@pytest.fixture(autouse=True)
def clean_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield


@pytest.fixture
def mock_gemini(monkeypatch):
    """Replace every Gemini call with a fast fake."""
    monkeypatch.setattr(routes, "generate_workout_gemini", lambda user_input: FAKE_PLAN)
    monkeypatch.setattr(routes, "update_workout_plan", lambda original, feedback: FAKE_UPDATED)
    monkeypatch.setattr(nutrition, "generate_nutrition_tip_with_flash", lambda goal: "Eat protein.")


@pytest.fixture
def gemini_down(monkeypatch):
    def boom(*args, **kwargs):
        raise GeminiError("Gemini is unavailable (test)")
    monkeypatch.setattr(routes, "generate_workout_gemini", boom)
    monkeypatch.setattr(routes, "update_workout_plan", boom)
    monkeypatch.setattr(nutrition, "generate_nutrition_tip_with_flash", boom)


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


FORM = {"username": "Asha", "user_id": "7", "age": "24", "weight": "58.5",
        "goal": "muscle gain", "intensity": "High"}
