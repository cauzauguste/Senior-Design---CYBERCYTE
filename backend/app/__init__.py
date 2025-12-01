"""
Cybercyte backend package.

Keep this file minimal so importing `backend.app` has no side effects.
"""

# Optional: expose the FastAPI app as `backend.app.app`
try:
    from .main import app  # noqa: F401
except Exception:
    # During migrations / partial setups, `main` might not import cleanly.
    app = None
# Empty init so backend.app works as a module
