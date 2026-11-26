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


MODULES = ['growth', 'credit', 'property', 'inflation', 'labor', 'external']

# ПОДОБРЕНИЕ НА СЪСТАВА (26.11.2026): премахнати 13 серии, нова леща external; golden-ът е
# преразгледан серия по серия (нови: REER invert, 3М междубанков invert, 10г ДЦК invert).
EXPECTED = {
 'credit.CN_BIS_CREDIT_GDP': {'invert': True, 'transform': 'level'},
 'credit.CN_CGB_10Y': {'invert': True, 'transform': 'level'},
 'credit.CN_CORP_SPREAD_3Y': {'invert': True, 'transform': 'level'},
 'growth.CN_CONS_CONF': {'invert': False, 'transform': 'level'},
 'inflation.CN_CORE_CPI_YOY': {'invert': False, 'transform': 'level'},
 'labor.CN_DISP_INCOME_YOY': {'invert': False, 'transform': 'level'},
 'labor.CN_PMI_EMPLOYMENT': {'invert': False, 'transform': 'level'},
 'credit.CN_INTERBANK_3M': {'invert': True, 'transform': 'level'},
 'credit.CN_LPR_1Y': {'invert': True, 'transform': 'level'},
 'credit.CN_LPR_5Y': {'invert': True, 'transform': 'level'},
 'credit.CN_M2_YOY': {'invert': False, 'transform': 'level'},
 'credit.CN_NEW_LOANS_MOM': {'invert': False, 'transform': 'level'},
 'credit.CN_TSF_FLOW': {'invert': False, 'transform': 'level'},
 'credit.CN_TSF_STOCK_YOY': {'invert': False, 'transform': 'level'},
 'external.CN_CNY_USD': {'invert': False, 'transform': 'level'},
 'external.CN_CURRENT_ACCOUNT': {'invert': False, 'transform': 'level'},
 'external.CN_EXPORTS_USD_YOY': {'invert': False, 'transform': 'level'},
 'external.CN_FX_RESERVES': {'invert': False, 'transform': 'level'},
 'external.CN_IMPORTS_USD_YOY': {'invert': False, 'transform': 'level'},
 'external.CN_REER': {'invert': True, 'transform': 'level'},
 'growth.CN_GDP_GROWTH_Q': {'invert': False, 'transform': 'level'},
 'growth.CN_IP_YOY': {'invert': False, 'transform': 'level'},
 'growth.CN_PMI_COMPOSITE_CAIXIN': {'invert': False, 'transform': 'level'},
 'growth.CN_PMI_MFG_CAIXIN': {'invert': False, 'transform': 'level'},
 'growth.CN_PMI_MFG_NBS': {'invert': False, 'transform': 'level'},
 'growth.CN_PMI_NON_MFG_NBS': {'invert': False, 'transform': 'level'},
 'growth.CN_PMI_SVCS_CAIXIN': {'invert': False, 'transform': 'level'},
 'growth.CN_RETAIL_YOY': {'invert': False, 'transform': 'level'},
 'inflation.CN_CPI_YOY_AK': {'invert': False, 'transform': 'level'},
 'inflation.CN_GDP_DEFLATOR_Q': {'invert': False, 'transform': 'level'},
 'inflation.CN_PPI_YOY': {'invert': False, 'transform': 'level'},
 'labor.CN_UNEMP_SURVEYED': {'invert': True, 'transform': 'level'},
 'labor.CN_YOUTH_UNEMP_M': {'invert': True, 'transform': 'level'},
 'property.CN_BIS_PROPERTY_YOY': {'invert': False, 'transform': 'level'},
 'property.CN_FAI_MOM_YOY': {'invert': False, 'transform': 'level'},
 'property.CN_NEW_HOUSE_PRICE': {'invert': False, 'transform': 'level'},
 'property.CN_PROPERTY_SALES_YOY': {'invert': False, 'transform': 'level'},
 'property.CN_RE_INVEST_YOY': {'invert': False, 'transform': 'level'}}


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
