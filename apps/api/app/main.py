from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import api_router
from app.settings import get_settings

app = FastAPI(title="SimuTrader API")
app.include_router(api_router)

settings = get_settings()


@app.on_event("startup")
def _validate_runtime_settings() -> None:
    settings.validate()


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
