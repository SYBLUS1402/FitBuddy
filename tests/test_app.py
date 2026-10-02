"""Run with:  pytest -v   (no API key or internet needed - Gemini is mocked)."""
from app.database import get_all_users, get_original_plan, get_current_plan, get_user
from app.gemini_client import to_plain_text
from app.nutrition import get_fallback_tip

from .conftest import FAKE_PLAN, FAKE_UPDATED, FORM


# ------------------------------------------------------------ pages
def test_home_page_shows_form(client):
    r = client.get("/")
    assert r.status_code == 200
    assert "Generate Plan" in r.text and 'name="intensity"' in r.text


def test_generate_workout_page_saves_user_and_plan(client, mock_gemini):
    r = client.post("/generate-workout", data=FORM)
    assert r.status_code == 200
    assert "Your Personalized Workout Plan" in r.text
    assert "Push-ups 3x10" in r.text and "Eat protein." in r.text
    assert "Asha" in r.text and "High" in r.text
    assert get_user(7)["goal"] == "muscle gain"
    assert get_original_plan(7) == FAKE_PLAN


def test_invalid_form_is_rejected_and_not_saved(client, mock_gemini):
    r = client.post("/generate-workout", data={**FORM, "age": "3"})
    assert r.status_code == 422
    assert "Please check your details" in r.text
    assert get_all_users() == []


def test_gemini_failure_shows_message_and_saves_nothing(client, gemini_down):
    r = client.post("/generate-workout", data=FORM)
    assert r.status_code == 502
    assert "Gemini is unavailable" in r.text
    assert get_all_users() == []


def test_tip_falls_back_when_flash_fails(client, monkeypatch, mock_gemini):
    from app import nutrition
    from app.gemini_client import GeminiError

    def boom(goal):
        raise GeminiError("tip down")
    monkeypatch.setattr(nutrition, "generate_nutrition_tip_with_flash", boom)
    r = client.post("/generate-workout", data=FORM)
    assert r.status_code == 200
    assert get_fallback_tip("muscle gain") in r.text
    assert "built-in tip" in r.text


# ------------------------------------------------------------ feedback
def test_feedback_updates_plan_and_keeps_original(client, mock_gemini):
    client.post("/generate-workout", data=FORM)
    r = client.post("/submit-feedback", data={"user_id": "7", "feedback": "more cardio"})
    assert r.status_code == 200
    assert "Your plan has been updated based on your feedback!" in r.text
    assert get_original_plan(7) == FAKE_PLAN
    assert get_current_plan(7) == FAKE_UPDATED


def test_feedback_for_unknown_user(client, mock_gemini):
    r = client.post("/submit-feedback", data={"user_id": "999", "feedback": "more cardio"})
    assert r.status_code == 404
    assert "No plan found" in r.text


def test_feedback_gemini_failure_keeps_old_plan(client, mock_gemini, monkeypatch):
    from app import routes
    from app.gemini_client import GeminiError
    client.post("/generate-workout", data=FORM)

    def boom(*args):
        raise GeminiError("update failed")
    monkeypatch.setattr(routes, "update_workout_plan", boom)
    r = client.post("/submit-feedback", data={"user_id": "7", "feedback": "add yoga"})
    assert r.status_code == 502 and "update failed" in r.text
    assert get_current_plan(7) == FAKE_PLAN


# ------------------------------------------------------------ admin
def test_admin_lists_and_deletes_users(client, mock_gemini):
    client.post("/generate-workout", data=FORM)
    client.post("/submit-feedback", data={"user_id": "7", "feedback": "more cardio"})
    page = client.get("/view-all-users")
    assert page.status_code == 200 and "Asha" in page.text and "added per feedback" in page.text

    r = client.post("/delete-user/7", follow_redirects=False)
    assert r.status_code == 303
    assert get_all_users() == []
    assert "No users yet" in client.get("/view-all-users").text


def test_admin_login_required_when_password_set(client, monkeypatch):
    from dataclasses import replace
    from app import routes
    monkeypatch.setattr(routes, "settings", replace(routes.settings, admin_password="secret"))
    assert client.get("/view-all-users").status_code == 401
    assert client.get("/view-all-users", auth=("admin", "secret")).status_code == 200
    assert client.get("/view-all-users", auth=("admin", "wrong")).status_code == 401


# ------------------------------------------------------------ JSON API
def test_api_generate_plan_and_update(client, mock_gemini):
    body = {"user_id": 3, "username": "Ravi", "age": 30, "weight": 80,
            "goal": "weight loss", "intensity": "medium"}
    r = client.post("/generate-plan", json=body)
    assert r.status_code == 200 and r.json()["workout_plan"] == FAKE_PLAN

    r = client.post("/update-plan/3", json={"feedback": "include more rest days"})
    assert r.status_code == 200 and r.json()["updated_plan"] == FAKE_UPDATED
    assert client.post("/update-plan/404", json={"feedback": "xx"}).status_code == 404


def test_api_workout_and_tip(client, mock_gemini):
    r = client.post("/generate-workout/gemini", json={"goal": "muscle gain", "intensity": "HIGH"})
    assert r.status_code == 200 and r.json()["workout_plan"] == FAKE_PLAN
    r = client.get("/nutrition-tip", params={"goal": "muscle gain"})
    assert r.json() == {"goal": "muscle gain", "nutrition_tip": "Eat protein.", "source": "gemini"}
    assert client.post("/generate-workout/gemini",
                       json={"goal": "x y", "intensity": "extreme"}).status_code == 422


def test_api_returns_502_when_gemini_down(client, gemini_down):
    r = client.post("/generate-workout/gemini", json={"goal": "muscle gain", "intensity": "low"})
    assert r.status_code == 502
    tip = client.get("/nutrition-tip", params={"goal": "muscle gain"}).json()
    assert tip["source"] == "fallback"


def test_health(client):
    assert client.get("/health").json()["status"] == "ok"


# ------------------------------------------------------------ helpers
def test_to_plain_text_removes_markdown():
    raw = "## Plan\n**Day 1:** Legs\n* Squats\n* Lunges"
    assert to_plain_text(raw) == "Plan\nDay 1: Legs\n- Squats\n- Lunges"
