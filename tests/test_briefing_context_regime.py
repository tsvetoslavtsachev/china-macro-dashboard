"""Regression: briefing_context ползва config теглата/режимите (audit 2026-06-07 #8).

По-рано export/briefing_context.py държеше СОБСТВЕНИ MODULE_WEIGHTS/MACRO_REGIMES,
различни от config.py → context.md и macro_state.json/deep.html казваха РАЗЛИЧЕН
режим за същите данни (напр. 35.9 → "РЕЦЕСИОНЕН" vs "ВЛОШАВАЩ СЕ").
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import config
from export import briefing_context
from export.briefing_context import _get_regime


def test_briefing_context_uses_config_constants():
    # Един източник — същите обекти като config.
    assert briefing_context.MODULE_WEIGHTS is config.MODULE_WEIGHTS
    assert briefing_context.MACRO_REGIMES is config.MACRO_REGIMES


def test_get_regime_matches_config_bands():
    assert _get_regime(35.9) == "ВЛОШАВАЩ СЕ"   # ключовият случай от audit #8
    assert _get_regime(35.0) == "ВЛОШАВАЩ СЕ"   # граница (>=)
    assert _get_regime(34.9) == "РЕЦЕСИОНЕН"
    assert _get_regime(82.0) == "ЕКСПАНЗИОНЕН"
    assert _get_regime(50.0) == "СМЕСЕН"


def test_regime_agrees_with_export_api():
    """Същият score → същият режим word в двата артефакта (context.md vs macro_state)."""
    from export_api import _overall_regime
    for score in (15.0, 35.6, 35.9, 50.0, 67.0, 82.0):
        label_ctx = _get_regime(score)
        label_api, _key = _overall_regime(score)
        assert label_ctx == label_api, f"score {score}: ctx={label_ctx} api={label_api}"
