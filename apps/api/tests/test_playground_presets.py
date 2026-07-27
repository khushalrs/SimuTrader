from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes.playground import router as playground_router
from app.playground.presets import GLOBAL_PRESET_DEFINITIONS
from app.services.config_validation import validate_and_resolve_config


def test_global_demo_presets_are_valid():
    expected = {
        "us-mega-cap-buy-hold",
        "india-equity-buy-hold",
        "us-india-mixed-portfolio",
        "momentum-top-k",
        "tax-regime-comparison",
        "long-short-margin-stress",
    }
    assert set(GLOBAL_PRESET_DEFINITIONS) == expected

    for preset in GLOBAL_PRESET_DEFINITIONS.values():
        validate_and_resolve_config(preset["config_snapshot"])


def test_playground_preset_catalog_matches_runnable_presets():
    app = FastAPI()
    app.include_router(playground_router)
    response = TestClient(app).get("/playground/presets")

    assert response.status_code == 200
    catalog = response.json()
    assert {item["id"] for item in catalog} == set(GLOBAL_PRESET_DEFINITIONS)
    assert all(item["strategy_type"] for item in catalog)
    assert all(item["symbols"] for item in catalog)
    assert all(item["config_snapshot"] for item in catalog)
