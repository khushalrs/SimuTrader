from fastapi import APIRouter

from app.api.routes import assets, backtests

api_router = APIRouter()
api_router.include_router(assets.router)
api_router.include_router(backtests.router)
