# FitBuddy - AI Fitness Plan Generator

FastAPI + Jinja2 + SQLite + Google Gemini. Generates a personalized 7-day workout plan,
a nutrition/recovery tip, updates the plan from your feedback, and gives coaches an admin dashboard.

## Quick start

```bash
python -m venv venv
venv\Scripts\activate            # Windows        (macOS/Linux: source venv/bin/activate)
pip install -r requirements.txt
copy .env.example .env           # Windows        (macOS/Linux: cp .env.example .env)
# open .env and paste your key:  GOOGLE_API_KEY=...   (https://aistudio.google.com/apikey)
python scripts/check_gemini.py   # optional: confirms key + models work
uvicorn app.main:app --reload
```

Open http://127.0.0.1:8000 (app) and http://127.0.0.1:8000/docs (API tester).
Run the tests (no API key needed): `pytest -v`

## Project structure

```
fitbuddy/
├── requirements.txt  .env.example  .gitignore  pytest.ini
├── app/
│   ├── main.py                    FastAPI entry point (static files, DB init)
│   ├── routes.py                  all routes (HTML pages + JSON API + admin)
│   ├── config.py                  settings from .env
│   ├── database.py                SQLAlchemy models (users, plans) + DB functions
│   ├── schemas.py                 Pydantic validation (UserInput, FeedbackRequest, ...)
│   ├── gemini_client.py           shared Gemini caller: retry, model fallback, friendly errors
│   ├── gemini_generator.py        7-day workout plan        (plan model)
│   ├── gemini_flash_generator.py  nutrition tip             (fast model)
│   ├── updated_plan.py            feedback-based plan update (plan model)
│   ├── nutrition.py               tip with built-in fallback if Gemini is down
│   ├── templates/                 base.html, index.html, result.html, all_users.html
│   └── static/images/gym-bg.jpg   background (replace with any gym photo, same name)
├── tests/                         15 tests, Gemini mocked
├── scripts/check_gemini.py        API key / model check
└── .vscode/                       F5 run config + pytest settings
```

`fitbuddy.db` (SQLite) is created automatically on first run.

## Routes

| Method | Path | Purpose |
|---|---|---|
| GET | `/` | Input form |
| POST | `/generate-workout` | Form: plan + tip, saves user, shows result |
| POST | `/submit-feedback` | Form: updates the plan from feedback |
| GET | `/view-all-users` | Admin dashboard (original vs updated plans) |
| POST | `/delete-user/{id}` | Admin: delete a user |
| POST | `/generate-workout/gemini` | JSON: plan from goal + intensity |
| GET | `/nutrition-tip?goal=...` | JSON: nutrition / recovery tip |
| POST | `/generate-plan` | JSON: save user + generate plan |
| POST | `/update-plan/{user_id}` | JSON: update plan from feedback |
| GET | `/api/users`, `/health` | JSON: all users (admin), health check |

## Models

The original design used Gemini 1.5 Pro/Flash, which Google has retired. Model names are
now set in `.env`, so future changes need no code edits:

| Setting | Default | Role |
|---|---|---|
| `GEMINI_PLAN_MODEL` | `gemini-3.8-flash` | workout plans + updates (use `gemini-3.1-pro-preview` for the Pro tier; needs billing) |
| `GEMINI_TIP_MODEL` | `gemini-3.5-flash-lite` | short nutrition tips |
| `GEMINI_FALLBACK_MODEL` | `gemini-3.8-flash` | used automatically if the above is retired / out of quota |

## Notes

- Feedback applies to the **latest** plan (updated if it exists), so several rounds of feedback build on each other. The original plan is always kept for comparison.
- Setting `ADMIN_PASSWORD` in `.env` protects `/view-all-users` with a login. Leave it empty for local use.
- Anyone who knows a User ID can change that user's plan. This is a local demo app with no user accounts; add authentication before putting it online.
- Plans are AI-generated general guidance, not medical advice.

## Troubleshooting

| Message | Fix |
|---|---|
| "No Gemini API key found" | Create `.env` from `.env.example` and set `GOOGLE_API_KEY`; restart the server |
| "Gemini rejected the API key" | Key is wrong/expired; make a new one in Google AI Studio |
| "could not answer ... model name is retired" | Update the model names in `.env` (see https://ai.google.dev/gemini-api/docs/models) |
| `uvicorn` not recognized | Activate the venv first, or run `python -m uvicorn app.main:app --reload` |
| `ModuleNotFoundError: app` | Run commands from the `fitbuddy` folder (the one containing `app/`) |
| Port 8000 busy | `uvicorn app.main:app --reload --port 8001` |
