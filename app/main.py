from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.database import create_db_and_tables
from app.routers import posts, profile, wizard

MEDIA_DIR = Path("media")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
    MEDIA_DIR.mkdir(exist_ok=True)  # noqa: ASYNC240 — runs once at startup, not in a hot path
    create_db_and_tables()
    yield


app = FastAPI(title="Social Planner", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173", "http://0.0.0.0:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/media", StaticFiles(directory=MEDIA_DIR), name="media")
app.include_router(posts.router)
app.include_router(profile.router)
app.include_router(wizard.router)


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
