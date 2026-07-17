from __future__ import annotations

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
