from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

from .routers import (alerts, auth_router, bus, chatbot, dashboard, progress, risk,
                      students)

app = FastAPI(title="EduAssist AI", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

for r in (auth_router, students, risk, progress, alerts, dashboard, bus, chatbot):
    app.include_router(r.router)


@app.get("/", include_in_schema=False)
def root():
    return RedirectResponse("/app/")


@app.get("/health")
def health():
    return {"status": "ok"}


# Serve the frontend from the same origin: http://127.0.0.1:8000/app/
FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"
app.mount("/app", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
