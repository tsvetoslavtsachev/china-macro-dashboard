"""
tests/test_polarity_pin.py
===========================
Полярностен GOLDEN PIN (REVIEW-03 т.0.4, P3-fix-B, генериран 2026-07-02).

Полярността на всяка серия е изрично обсъдено решение — една тихо обърната
полярност обръща леща, без нито един тест да падне (инцидентът с housing
сериите, поправен 2026-06-05, мина незабелязан точно затова; REVIEW-03 R.6).
Този тест пинва ПЪЛНИЯ полярностен вектор.

При ЛЕГИТИМНА промяна на полярност: редактирай двата файла ЗАЕДНО (дефиницията
и този golden) в един commit, с обяснение защо посоката се сменя.
"""
from __future__ import annotations

import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

import importlib  # noqa: E402


def _diff(actual: dict, expected: dict) -> dict:
    """Кои ключове се различават — за четим failure."""
    keys = set(actual) | set(expected)
    return {
        k: {"expected": expected.get(k, "<ЛИПСВА>"), "actual": actual.get(k, "<ЛИПСВА>")}
        for k in sorted(keys, key=str)
        if actual.get(k, "<ЛИПСВА>") != expected.get(k, "<ЛИПСВА>")
    }


MODULES = ['growth', 'credit', 'property', 'inflation', 'labor']

EXPECTED = {'credit.CN_BIS_CREDIT_GDP': {'invert': True, 'transform': 'level'},
 'credit.CN_CNY_USD': {'invert': False, 'transform': 'level'},
 'credit.CN_CREDIT_PRIVATE': {'invert': True, 'transform': 'level'},
 'credit.CN_DEPOSIT_RATE': {'invert': True, 'transform': 'level'},
 'credit.CN_LENDING_RATE': {'invert': True, 'transform': 'level'},
 'credit.CN_LPR_1Y': {'invert': True, 'transform': 'level'},
 'credit.CN_LPR_5Y': {'invert': True, 'transform': 'level'},
 'credit.CN_M2_GDP': {'invert': False, 'transform': 'level'},
 'credit.CN_M2_YOY': {'invert': False, 'transform': 'level'},
 'credit.CN_POLICY_RATE': {'invert': True, 'transform': 'level'},
 'credit.CN_TSF_FLOW': {'invert': False, 'transform': 'level'},
 'growth.CN_CAPEX_GDP': {'invert': False, 'transform': 'level'},
 'growth.CN_GDP_GROWTH': {'invert': False, 'transform': 'level'},
 'growth.CN_GDP_GROWTH_Q': {'invert': False, 'transform': 'level'},
 'growth.CN_INDUSTRY_GROWTH': {'invert': False, 'transform': 'level'},
 'growth.CN_IP_YOY_NBS': {'invert': False, 'transform': 'level'},
 'growth.CN_MANUFACTURING_GDP': {'invert': False, 'transform': 'level'},
 'growth.CN_PMI_COMPOSITE_CAIXIN': {'invert': False, 'transform': 'level'},
 'growth.CN_PMI_MFG_NBS': {'invert': False, 'transform': 'level'},
 'growth.CN_PMI_NON_MFG_NBS': {'invert': False, 'transform': 'level'},
 'growth.CN_RETAIL_YOY': {'invert': False, 'transform': 'level'},
 'growth.CN_SERVICES_GROWTH': {'invert': False, 'transform': 'level'},
 'inflation.CN_CPI_INDEX': {'invert': False, 'transform': 'yoy_pct'},
 'inflation.CN_CPI_YOY': {'invert': False, 'transform': 'level'},
 'inflation.CN_CPI_YOY_AK': {'invert': False, 'transform': 'level'},
 'inflation.CN_GDP_DEFLATOR': {'invert': False, 'transform': 'level'},
 'inflation.CN_GDP_DEFLATOR_Q': {'invert': False, 'transform': 'level'},
 'inflation.CN_PPI_INDEX': {'invert': False, 'transform': 'yoy_pct'},
 'inflation.CN_PPI_YOY': {'invert': False, 'transform': 'level'},
 'labor.CN_LABOR_PARTICIPATION': {'invert': False, 'transform': 'level'},
 'labor.CN_UNEMPLOYMENT': {'invert': True, 'transform': 'level'},
 'labor.CN_YOUTH_UNEMPLOYMENT': {'invert': True, 'transform': 'level'},
 'property.CN_BIS_PROPERTY_YOY': {'invert': False, 'transform': 'level'},
 'property.CN_CURRENT_ACCOUNT': {'invert': False, 'transform': 'level'},
 'property.CN_EXPORTS_GDP': {'invert': False, 'transform': 'level'},
 'property.CN_FAI_MOM_YOY': {'invert': False, 'transform': 'level'},
 'property.CN_FDI_ACTUAL': {'invert': False, 'transform': 'level'},
 'property.CN_FDI_GDP': {'invert': False, 'transform': 'level'},
 'property.CN_FIXED_CAPITAL': {'invert': False, 'transform': 'level'},
 'property.CN_NEW_HOUSE_PRICE': {'invert': False, 'transform': 'level'},
 'property.CN_PRIVATE_CAPEX': {'invert': False, 'transform': 'level'}}


def _actual() -> dict:
    agg = {}
    for mod_name in MODULES:
        mod = importlib.import_module(f"modules.{mod_name}")
        for sid, meta in mod.SERIES.items():
            agg[f"{mod_name}.{sid}"] = {
                "invert": bool(meta.get("invert", False)),
                "transform": meta.get("transform", "level"),
            }
    return agg


class TestPolarityPin:
    def test_module_polarity_and_transform_pinned(self):
        d = _diff(_actual(), EXPECTED)
        assert not d, f"ПОЛЯРНОСТЕН/TRANSFORM ДРИФТ (изрична редакция на golden-а нужна): {d}"
