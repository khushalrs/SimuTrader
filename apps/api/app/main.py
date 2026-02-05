from fastapi import FastAPI

from app.api import api_router

app = FastAPI(title="SimuTrader API")
app.include_router(api_router)


@app.get("/health")
def health_check() -> dict:
    return {"status": "ok"}
