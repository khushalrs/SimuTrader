from fastapi import APIRouter

from app.api.routes import assets, backtests, market, playground, runs, strategies

api_router = APIRouter()
api_router.include_router(assets.router)
api_router.include_router(backtests.router)
api_router.include_router(market.router)
api_router.include_router(runs.router)
api_router.include_router(playground.router)
api_router.include_router(strategies.router)
