"""FastAPI app skeleton. Only a health check and static mounts; no detection logic."""
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

WEB = Path(__file__).resolve().parents[3] / "web"

app = FastAPI(title="Satyapan", version="0.1.0")


@app.get("/api/v1/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


app.mount("/static", StaticFiles(directory=WEB / "static"), name="static")
app.mount("/sim", StaticFiles(directory=WEB / "sim", html=True), name="sim")
