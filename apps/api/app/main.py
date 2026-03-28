from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging

from app.api import api_router
from app.db.session import SessionLocal
from app.playground.presets import GLOBAL_PRESET_DEFINITIONS
from app.playground.service import enqueue_global_preset_run
from app.settings import get_settings

app = FastAPI(title="SimuTrader API")
app.include_router(api_router)
logger = logging.getLogger(__name__)

settings = get_settings()


@app.on_event("startup")
def _validate_runtime_settings() -> None:
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


if settings.cors_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )


@app.get("/health")
def health_check() -> dict:
    return {"status": "ok"}
