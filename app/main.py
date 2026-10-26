from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from .config import STATIC_DIR, ensure_dirs
from .db import init_db
from .routes import api, pages


@asynccontextmanager
async def lifespan(_: FastAPI):
    ensure_dirs()
    init_db()
    yield


app = FastAPI(title="VolleyTrak", version="0.3.19", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
app.include_router(api.router, prefix="/api")
app.include_router(pages.router)
