"""Core route handlers.

HTML pages (Jinja2):  /   /generate-workout   /submit-feedback   /view-all-users
JSON API:             /generate-workout/gemini   /nutrition-tip   /generate-plan
                      /update-plan/{user_id}   /api/users   /health

Handlers are plain ``def`` (not ``async def``) on purpose: Gemini calls are blocking, and
FastAPI runs plain functions in a worker thread so the server stays responsive.
"""
import secrets
from typing import Optional

from fastapi import APIRouter, Depends, Form, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.templating import Jinja2Templates
from pydantic import ValidationError

from .config import BASE_DIR, settings
from .database import (delete_user, get_all_users_with_plans, get_current_plan, get_original_plan,
                       get_user, save_plan, save_user, update_plan)
from .gemini_client import GeminiError
from .gemini_generator import generate_workout_gemini
from .nutrition import get_nutrition_tip
from .schemas import FeedbackForm, FeedbackRequest, UserInput, WorkoutRequest
from .updated_plan import update_workout_plan

router = APIRouter()
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))
security = HTTPBasic(auto_error=False)

FEEDBACK_SUCCESS = "Your plan has been updated based on your feedback!"


# ------------------------------------------------------------------ helpers
def require_admin(credentials: Optional[HTTPBasicCredentials] = Depends(security)) -> None:
    """Protects admin routes only when ADMIN_PASSWORD is set in .env."""
    if not settings.admin_password:
        return
    ok = bool(
        credentials
        and secrets.compare_digest(credentials.username.encode(), settings.admin_username.encode())
        and secrets.compare_digest(credentials.password.encode(), settings.admin_password.encode())
    )
    if not ok:
        raise HTTPException(status_code=401, detail="Admin login required",
                            headers={"WWW-Authenticate": 'Basic realm="FitBuddy Admin"'})


def _format_validation_error(exc: ValidationError) -> str:
    parts = []
    for err in exc.errors():
        field = ".".join(str(p) for p in err["loc"]) or "input"
        parts.append(f"{field}: {err['msg']}")
    return "Please check your details - " + "; ".join(parts)


def _render_index(request: Request, error: Optional[str] = None, form: Optional[dict] = None,
                  status_code: int = 200):
    return templates.TemplateResponse(
        request, "index.html", {"error": error, "form": form or {}}, status_code=status_code)


def _render_result(request: Request, user: dict, plan: str, tip: dict, *, message: Optional[str] = None,
                   error: Optional[str] = None, was_updated: bool = False, status_code: int = 200):
    return templates.TemplateResponse(request, "result.html", {
        "username": user["name"],
        "user_id": user["id"],
        "age": user["age"],
        "weight": user["weight"],
        "goal": user["goal"],
        "intensity": user["intensity"],
        "workout_plan": plan,
        "nutrition_tip": tip["tip"],
        "tip_source": tip["source"],
        "message": message,
        "error": error,
        "was_updated": was_updated,
    }, status_code=status_code)


# ------------------------------------------------------------------ HTML pages
@router.get("/", response_class=HTMLResponse)
def home(request: Request):
    """Home page with the user-details form."""
    return _render_index(request)


@router.post("/generate-workout", response_class=HTMLResponse)
def generate_workout(
    request: Request,
    username: str = Form(...),
    user_id: str = Form(...),
    age: str = Form(...),
    weight: str = Form(...),
    goal: str = Form(...),
    intensity: str = Form(...),
):
    """Form submit: validate -> Gemini plan + tip -> save -> show result.html."""
    raw = {"username": username, "user_id": user_id, "age": age, "weight": weight,
           "goal": goal, "intensity": intensity}
    try:
        data = UserInput(**raw)
    except ValidationError as exc:
        return _render_index(request, _format_validation_error(exc), raw, status_code=422)

    try:
        plan = generate_workout_gemini({"goal": data.goal, "intensity": data.intensity,
                                        "age": data.age, "weight": data.weight})
    except GeminiError as exc:
        return _render_index(request, str(exc), raw, status_code=502)

    tip = get_nutrition_tip(data.goal)
    save_user(data.user_id, data.username, data.age, data.weight, data.goal, data.intensity)
    save_plan(data.user_id, plan)

    user = {"id": data.user_id, "name": data.username, "age": data.age, "weight": data.weight,
            "goal": data.goal, "intensity": data.intensity}
    return _render_result(request, user, plan, tip)


@router.post("/submit-feedback", response_class=HTMLResponse)
def submit_feedback(request: Request, user_id: str = Form(...), feedback: str = Form(...)):
    """Feedback form: update the saved plan with Gemini and show the new version."""
    try:
        data = FeedbackForm(user_id=user_id, feedback=feedback)
    except ValidationError as exc:
        return _render_index(request, _format_validation_error(exc), status_code=422)

    user = get_user(data.user_id)
    current = get_current_plan(data.user_id)
    if not user or not current:
        return _render_index(
            request, f"No plan found for User ID {data.user_id}. Generate a plan first.",
            status_code=404)

    tip = get_nutrition_tip(user["goal"])
    try:
        updated = update_workout_plan(current, data.feedback)
    except GeminiError as exc:
        return _render_result(request, user, current, tip, error=str(exc), status_code=502,
                              was_updated=current != get_original_plan(data.user_id))

    update_plan(data.user_id, updated)
    return _render_result(request, user, updated, tip, message=FEEDBACK_SUCCESS, was_updated=True)


@router.get("/view-all-users", response_class=HTMLResponse, dependencies=[Depends(require_admin)])
def view_all_users(request: Request):
    """Admin dashboard: every user with original and updated plans."""
    return templates.TemplateResponse(request, "all_users.html",
                                      {"users": get_all_users_with_plans()})


@router.post("/delete-user/{user_id}", dependencies=[Depends(require_admin)])
def delete_user_route(user_id: int):
    delete_user(user_id)
    return RedirectResponse(url="/view-all-users", status_code=303)


# ------------------------------------------------------------------ JSON API
@router.post("/generate-workout/gemini")
def generate_gemini_workout(request: WorkoutRequest):
    """API: generate a 7-day plan from goal + intensity (nothing is saved)."""
    try:
        plan = generate_workout_gemini(request.model_dump(exclude_none=True))
    except GeminiError as exc:
        raise HTTPException(status_code=502, detail=str(exc))
    return {"model": "gemini", "workout_plan": plan}


@router.get("/nutrition-tip")
def nutrition_tip(goal: str = Query(..., min_length=2, max_length=200)):
    """API: one nutrition / recovery tip for a goal."""
    result = get_nutrition_tip(goal)
    return {"goal": goal, "nutrition_tip": result["tip"], "source": result["source"]}


@router.post("/generate-plan")
def generate_plan(user_data: UserInput):
    """API: save the user, generate a plan with Gemini and store it."""
    try:
        plan = generate_workout_gemini({"goal": user_data.goal, "intensity": user_data.intensity,
                                        "age": user_data.age, "weight": user_data.weight})
    except GeminiError as exc:
        raise HTTPException(status_code=502, detail=str(exc))

    save_user(user_data.user_id, user_data.username, user_data.age, user_data.weight,
              user_data.goal, user_data.intensity)
    save_plan(user_data.user_id, plan)
    tip = get_nutrition_tip(user_data.goal)
    return {"message": "Workout plan generated and saved successfully!",
            "workout_plan": plan, "nutrition_tip": tip["tip"]}


@router.post("/update-plan/{user_id}")
def update_user_plan(user_id: int, data: FeedbackRequest):
    """API: update a user's plan based on feedback."""
    current = get_current_plan(user_id)
    if not current:
        raise HTTPException(status_code=404, detail="Plan not found for this user.")
    try:
        updated = update_workout_plan(current, data.feedback)
    except GeminiError as exc:
        raise HTTPException(status_code=502, detail=str(exc))
    update_plan(user_id, updated)
    return {"updated_plan": updated}


@router.get("/api/users", dependencies=[Depends(require_admin)])
def api_users():
    """API: all users with their plans (admin)."""
    return get_all_users_with_plans()


@router.get("/health")
def health():
    return {"status": "ok", "gemini_key_configured": settings.api_key not in ("", "your_gemini_api_key_here")}
