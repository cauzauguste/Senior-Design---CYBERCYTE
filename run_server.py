"""Run the FastAPI app with Uvicorn when executed.

This file provides a simple CLI entrypoint so `python run_server.py`
starts the application in development mode (127.0.0.1:8000).
"""
import uvicorn

if __name__ == "__main__":
    uvicorn.run("backend.app.main:app", host="127.0.0.1", port=8000, log_level="info", reload=False)
