from fastapi import FastAPI

app = FastAPI(title="SimuTrader API")


@app.get("/health")
def health_check() -> dict:
    return {"status": "ok"}
