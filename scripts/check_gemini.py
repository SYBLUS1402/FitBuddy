"""Quick check that your API key and model names work.

Run from the project folder:   python scripts/check_gemini.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import settings                                  # noqa: E402
from app.gemini_client import GeminiError, generate_text         # noqa: E402


def main() -> int:
    print("FitBuddy - Gemini connection check")
    key = settings.api_key
    print(f"API key : {'set (' + key[:4] + '...)' if key and not key.startswith('your_') else 'MISSING'}")
    print(f"Models  : plan={settings.plan_model} | tip={settings.tip_model} | fallback={settings.fallback_model}\n")

    failed = False
    for label, model in (("plan model", settings.plan_model), ("tip model", settings.tip_model)):
        try:
            answer = generate_text("Reply with the single word: ready", model)
            print(f"[OK]   {label} ({model}) -> {answer[:40]!r}")
        except GeminiError as exc:
            failed = True
            print(f"[FAIL] {label} ({model})\n       {exc}")
    print("\nAll good - start the app with: uvicorn app.main:app --reload" if not failed
          else "\nFix the problem above (see README > Troubleshooting), then run this again.")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
