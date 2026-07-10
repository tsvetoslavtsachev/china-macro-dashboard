"""
tests/test_polarity_catalog.py
==============================
O3 Вълна 1 (КОКПИТ, 2026-07-10): централният catalog/polarity.py е ЕДИНИЯТ
източник на полярност за scoring-а (модулите вече викат
score_series(polarity=polarity_for(sid)), не invert=meta["invert"]).

Този тест заключва трите инварианта на централизацията:
  1. CONSISTENCY — централната полярност ≡ per-серия invert анотацията в модулите
     (invert=True ⟺ -1). Заедно с test_polarity_pin.py (independent golden на invert)
     това хваща тих флип в който и да е от двата източника.
  2. COMPLETENESS — всяка серия от петте модула присъства изрично в централния
     каталог (никоя не пада към default fallback → S7 CN-1 дупката е затворена).
  3. SPOT — критичните знаци (LPR клас = -1; безработица = -1; растеж = +1) заковани.
"""
from __future__ import annotations

import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

import importlib  # noqa: E402

from catalog.polarity import POLARITY, polarity_for  # noqa: E402

MODULES = ["growth", "credit", "property", "inflation", "labor"]


def _module_series() -> dict[str, dict]:
    agg = {}
    for mod_name in MODULES:
        mod = importlib.import_module(f"modules.{mod_name}")
        for sid, meta in mod.SERIES.items():
            agg[sid] = meta
    return agg


class TestPolarityCatalog:
    def test_catalog_matches_module_invert(self):
        """CONSISTENCY: polarity_for(sid) == (-1 ако invert else +1) за всяка модулна серия."""
        drift = {}
        for sid, meta in _module_series().items():
            expected = -1 if bool(meta.get("invert", False)) else +1
            actual = polarity_for(sid)
            if actual != expected:
                drift[sid] = {"catalog": actual, "module_invert": meta.get("invert")}
        assert not drift, f"ПОЛЯРНОСТЕН ДРИФТ каталог↔модул (изрична редакция на двата нужна): {drift}"

    def test_all_module_series_in_catalog(self):
        """COMPLETENESS: никоя модулна серия не пада към default fallback."""
        missing = [sid for sid in _module_series() if sid not in POLARITY]
        assert not missing, f"Серии извън централния каталог (риск от тих fallback): {missing}"

    def test_critical_signs_pinned(self):
        """SPOT: заковани критични знаци (регресия за S7 CN-1 LPR инцидента)."""
        assert polarity_for("CN_LPR_1Y") == -1
        assert polarity_for("CN_LPR_5Y") == -1        # ипотечен бенчмарк — easing = по-добре
        assert polarity_for("CN_POLICY_RATE") == -1
        assert polarity_for("CN_UNEMPLOYMENT") == -1
        assert polarity_for("CN_YOUTH_UNEMPLOYMENT") == -1
        assert polarity_for("CN_GDP_GROWTH") == +1
        assert polarity_for("CN_RETAIL_YOY") == +1
        assert polarity_for("CN_LABOR_PARTICIPATION") == +1
