from contextlib import asynccontextmanager
from collections.abc import AsyncIterator
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware

from app.api import api_router
from app.db.session import SessionLocal
from app.playground.presets import GLOBAL_PRESET_DEFINITIONS
from app.playground.service import enqueue_global_preset_run
from app.settings import get_settings

logger = logging.getLogger(__name__)

settings = get_settings()


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    settings.validate()
    db = SessionLocal()
    try:
        for preset_id in GLOBAL_PRESET_DEFINITIONS.keys():
            try:
                enqueue_global_preset_run(db, preset_id)
            except Exception:
                logger.exception("Global preset warm-up failed for preset_id=%s", preset_id)
    finally:
        db.close()
    yield


app = FastAPI(title="SimuTrader API", lifespan=lifespan)
app.include_router(api_router)


@app.middleware("http")
async def _security_headers(request, call_next):
    response = await call_next(request)
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; object-src 'none'; base-uri 'self'; frame-ancestors 'none'"
    )
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    if not settings.is_dev_env:
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response


if settings.cors_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=settings.cors_allow_credentials,
        allow_methods=settings.cors_allow_methods,
        allow_headers=settings.cors_allow_headers,
    )

if settings.trusted_hosts:
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.trusted_hosts)


@app.get("/health")
def health_check() -> dict:
    return {"status": "ok"}
