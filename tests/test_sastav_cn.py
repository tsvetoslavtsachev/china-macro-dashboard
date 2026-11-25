# -*- coding: utf-8 -*-
"""ПРОЛЕТР4, подобрение на състава (26.11.2026, одобрен от собственика).

Пинва: 6 лещи, точния състав на SERIES и COMPOSITE, махнатите 13 серии, WB фона,
съответствието леща <-> catalog lens, FRED адаптера (офлайн) и резервата за CGB 10Y.
"""
from __future__ import annotations

import importlib
import sys
from datetime import date
from pathlib import Path

import pandas as pd
import pytest

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from catalog.series import SERIES_CATALOG  # noqa: E402
from catalog.polarity import POLARITY, polarity_for  # noqa: E402

LENSES = ["growth", "inflation", "labor", "credit", "property", "external"]

REMOVED = [
    "CN_CPI_INDEX", "CN_PPI_INDEX", "CN_POLICY_RATE", "CN_LENDING_RATE", "CN_DEPOSIT_RATE",
    "CN_CREDIT_PRIVATE", "CN_M2_GDP", "CN_CAPEX_GDP", "CN_PRIVATE_CAPEX", "CN_FIXED_CAPITAL",
    "CN_FDI_ACTUAL", "CN_IP_YOY_NBS", "CN_CNH",
]

SERIES_EXPECTED = {
    "growth": ["CN_GDP_GROWTH_Q", "CN_IP_YOY", "CN_RETAIL_YOY", "CN_PMI_MFG_NBS", "CN_PMI_NON_MFG_NBS",
               "CN_PMI_COMPOSITE_CAIXIN", "CN_PMI_MFG_CAIXIN", "CN_PMI_SVCS_CAIXIN"],
    "inflation": ["CN_CPI_YOY_AK", "CN_PPI_YOY", "CN_GDP_DEFLATOR_Q"],
    "labor": ["CN_UNEMP_SURVEYED", "CN_YOUTH_UNEMP_M"],
    "credit": ["CN_LPR_1Y", "CN_LPR_5Y", "CN_BIS_CREDIT_GDP", "CN_M2_YOY", "CN_TSF_FLOW", "CN_TSF_STOCK_YOY",
               "CN_NEW_LOANS_MOM", "CN_INTERBANK_3M", "CN_CGB_10Y"],
    "property": ["CN_NEW_HOUSE_PRICE", "CN_BIS_PROPERTY_YOY", "CN_FAI_MOM_YOY", "CN_RE_INVEST_YOY",
                 "CN_PROPERTY_SALES_YOY"],
    "external": ["CN_EXPORTS_USD_YOY", "CN_REER", "CN_CNY_USD", "CN_IMPORTS_USD_YOY", "CN_FX_RESERVES",
                 "CN_CURRENT_ACCOUNT"],
}
COMPOSITE_EXPECTED = {
    "growth": ["CN_GDP_GROWTH_Q", "CN_IP_YOY", "CN_RETAIL_YOY", "CN_PMI_MFG_NBS", "CN_PMI_NON_MFG_NBS"],
    "inflation": ["CN_CPI_YOY_AK", "CN_PPI_YOY", "CN_GDP_DEFLATOR_Q"],
    "labor": ["CN_UNEMP_SURVEYED", "CN_YOUTH_UNEMP_M"],
    "credit": ["CN_LPR_1Y", "CN_BIS_CREDIT_GDP", "CN_M2_YOY", "CN_TSF_FLOW"],
    "property": ["CN_NEW_HOUSE_PRICE", "CN_RE_INVEST_YOY", "CN_FAI_MOM_YOY", "CN_BIS_PROPERTY_YOY"],
    "external": ["CN_EXPORTS_USD_YOY", "CN_REER", "CN_CNY_USD"],
}
WB_BACKGROUND = [
    "CN_GDP_GROWTH", "CN_INDUSTRY_GROWTH", "CN_SERVICES_GROWTH", "CN_MANUFACTURING_GDP", "CN_CPI_YOY",
    "CN_GDP_DEFLATOR", "CN_UNEMPLOYMENT", "CN_YOUTH_UNEMPLOYMENT", "CN_LABOR_PARTICIPATION",
    "CN_EXPORTS_GDP", "CN_FDI_GDP",
]


def _mod(name):
    return importlib.import_module(f"modules.{name}")


def _full_snapshot():
    idx = pd.date_range(end="2026-10-01", periods=60, freq="MS")
    return {k: pd.Series(range(1, 61), index=idx, dtype=float) for k in SERIES_CATALOG}


# ── състав ──────────────────────────────────────────────────────────────────

def test_six_lenses_in_export_order():
    import export_api
    from config import MODULE_WEIGHTS
    assert [n for n, _ in export_api.MODULES_ORDER] == LENSES
    assert set(export_api._MODULE_SERIES) == set(LENSES)
    assert set(LENSES) <= set(MODULE_WEIGHTS)


@pytest.mark.parametrize("lens", LENSES)
def test_module_series_and_composite_exact(lens):
    m = _mod(lens)
    assert sorted(m.SERIES) == sorted(SERIES_EXPECTED[lens])
    assert list(m.COMPOSITE_SERIES) == COMPOSITE_EXPECTED[lens]
    assert len(m.COMPOSITE_SERIES) == len(m.COMPOSITE_WEIGHTS)
    assert set(m.COMPOSITE_SERIES) <= set(m.SERIES)
    assert abs(sum(m.COMPOSITE_WEIGHTS) - 1.0) < 1e-9


def test_removed_ids_are_absent_everywhere():
    for sid in REMOVED:
        assert sid not in SERIES_CATALOG, sid
        assert sid not in POLARITY, sid
        for lens in LENSES:
            assert sid not in _mod(lens).SERIES, (lens, sid)
            assert sid not in _mod(lens).COMPOSITE_SERIES, (lens, sid)


def test_removed_ids_absent_from_series_data():
    from export_api import build_series_data
    out = build_series_data(_full_snapshot(), date(2026, 11, 26), years=10)["series"]
    assert not set(REMOVED) & set(out)
    assert set(WB_BACKGROUND) <= set(out)            # фонът още се изнася
    assert {"CN_REER", "CN_INTERBANK_3M"} <= set(out)


def test_world_bank_background_is_in_no_module_and_no_composite():
    in_modules = {s for lens in LENSES for s in _mod(lens).SERIES}
    for sid in WB_BACKGROUND:
        assert sid in SERIES_CATALOG and SERIES_CATALOG[sid]["source"] == "worldbank"
        assert sid not in in_modules, sid
    assert "CN_CURRENT_ACCOUNT" in _mod("external").SERIES
    assert "CN_CURRENT_ACCOUNT" not in _mod("external").COMPOSITE_SERIES   # годишна: само в SERIES


@pytest.mark.parametrize("lens", LENSES)
def test_catalog_lens_matches_the_module_it_is_in(lens):
    """Консуматорът (лампите) датира лещата по meta.lens/lens_all на серията."""
    for sid in _mod(lens).SERIES:
        assert lens in SERIES_CATALOG[sid]["lens"], (lens, sid, SERIES_CATALOG[sid]["lens"])


def test_series_data_meta_carries_the_module_lens():
    from export_api import build_series_data
    out = build_series_data(_full_snapshot(), date(2026, 11, 26), years=10)["series"]
    for lens in LENSES:
        for sid in _mod(lens).SERIES:
            assert lens in out[sid]["meta"]["lens_all"], (lens, sid)


def test_every_module_series_has_polarity_and_new_signs():
    for lens in LENSES:
        for sid in _mod(lens).SERIES:
            assert sid in POLARITY, sid
    assert polarity_for("CN_REER") == -1 and polarity_for("CN_INTERBANK_3M") == -1
    assert polarity_for("CN_CGB_10Y") == -1 and polarity_for("CN_CNY_USD") == +1


def test_new_external_module_runs_and_has_bulgarian_labels():
    idx = pd.date_range(end="2026-10-01", periods=130, freq="MS")
    snap = {k: pd.Series(range(1, 131), index=idx, dtype=float) for k in _mod("external").SERIES}
    r = _mod("external").run(snap)
    assert r["module"] == "external" and r["composite"] is not None
    assert r["label"] and r["regime"] and r["narrative"]


def test_resourced_catalog_entries():
    c = SERIES_CATALOG
    cny = c["CN_CNY_USD"]
    assert (cny["source"], cny["id"], cny["release_schedule"]) == ("fred_csv", "DEXCHUS", "daily")
    assert c["CN_BIS_CREDIT_GDP"]["id"] == "QCNPAM770A@qend"
    assert c["CN_BIS_PROPERTY_YOY"]["id"] == "QCNN628BIS@qend@yoy"
    assert c["CN_REER"]["id"] == "RBCNBIS" and c["CN_INTERBANK_3M"]["id"] == "IR3TIB01CNM156N"
    assert (c["CN_CGB_10Y"]["source"], c["CN_CGB_10Y"]["id"]) == ("akshare", "cgb_10y")
    assert c["CN_CGB_10Y"]["bridge_fallback_parquet"]


# ── FRED адаптер (офлайн) ───────────────────────────────────────────────────

FRED_TXT = "observation_date,DEXCHUS\n2026-11-17,6.60\n2026-11-18,.\n2026-11-19,\n2026-11-20,6.677\n"
FRED_Q = (
    "observation_date,QCNN628BIS\n2024-01-01,100.0\n2024-04-01,.\n2024-07-01,102.0\n"
    "2024-10-01,104.0\n2025-01-01,110.0\n2025-04-01,111.0\n2025-07-01,102.0\n"
)


def test_fred_parse_skips_dot_and_blank():
    from sources.fred_csv import parse_fred_csv
    s = parse_fred_csv(FRED_TXT)
    assert list(s.index.strftime("%Y-%m-%d")) == ["2026-11-17", "2026-11-20"]
    assert s.iloc[-1] == pytest.approx(6.677)
    assert parse_fred_csv("observation_date,X\n").empty


def test_fred_split_id():
    from sources.fred_csv import split_id
    assert split_id("QCNN628BIS@qend@yoy") == ("QCNN628BIS", {"qend", "yoy"})
    assert split_id("RBCNBIS") == ("RBCNBIS", set())


def test_fred_quarter_end_and_yoy_conversion():
    from sources.fred_csv import parse_fred_csv, quarter_start_to_end, yoy_pct
    s = quarter_start_to_end(parse_fred_csv(FRED_Q))
    assert str(s.index[0].date()) == "2024-03-31" and str(s.index[-1].date()) == "2025-09-30"
    y = yoy_pct(s)
    # 2025-03-31 = 110/100-1 ; 2025-09-30 = 102/102-1 ; 2025-06-30 и 2024-12-31 нямат базова точка
    assert list(y.index.strftime("%Y-%m-%d")) == ["2025-03-31", "2025-09-30"]
    assert y.iloc[0] == pytest.approx(10.0) and y.iloc[1] == pytest.approx(0.0)


def test_fred_adapter_fetch_with_cache(tmp_path, monkeypatch):
    from sources.fred_csv import FredCsvAdapter
    a = FredCsvAdapter(cache_path="c.json", base_dir=tmp_path, retry_backoff=[])
    calls = []
    monkeypatch.setattr(a, "_download", lambda fid: calls.append(fid) or FRED_Q)
    s = a.fetch("CN_BIS_PROPERTY_YOY", "QCNN628BIS@qend@yoy", "quarterly")
    assert calls == ["QCNN628BIS"] and s.iloc[0] == pytest.approx(10.0)
    s2 = a.fetch("CN_BIS_PROPERTY_YOY", "QCNN628BIS@qend@yoy", "quarterly")   # от кеша
    assert calls == ["QCNN628BIS"] and len(s2) == len(s)


def test_fred_adapter_failure_is_recorded_not_raised(tmp_path, monkeypatch):
    from sources.fred_csv import FredCsvAdapter
    a = FredCsvAdapter(cache_path="c.json", base_dir=tmp_path, retry_backoff=[])

    def boom(fid):
        raise RuntimeError("HTTP 404: nope")

    monkeypatch.setattr(a, "_download", boom)
    assert a.fetch("CN_REER", "RBCNBIS", "monthly").empty
    assert "CN_REER" in a._fetch_failures


# ── CGB 10Y: akshare + резерва от моста ─────────────────────────────────────

def _cgb_frame():
    return pd.DataFrame({
        "曲线名称": ["中债国债收益率曲线", "中债国债收益率曲线", "中债商业银行普通债收益率曲线(AAA)"],
        "日期": ["2026-11-24", "2026-11-25", "2026-11-25"],
        "10年": [1.60, 1.5914, 9.99],
    })


def test_cgb_parse_takes_only_the_treasury_curve():
    from sources.akshare_cn import AkShareAdapter
    s = AkShareAdapter._parse_cgb_frame(_cgb_frame())
    assert list(s.values) == [1.60, 1.5914]


def test_cgb_fetch_chunks_and_dedups(tmp_path, monkeypatch):
    import sources.akshare_cn as m
    calls = []

    def fake(name, **kw):
        calls.append((kw["start_date"], kw["end_date"]))
        if len(calls) > 2:
            raise ValueError("празен отговор")
        return _cgb_frame()

    monkeypatch.setattr(m, "_ak_call", fake)
    a = m.AkShareAdapter(cache_path="c.json", base_dir=tmp_path)
    s = a._fetch_cgb_10y()
    assert s.index.is_unique and len(s) == 2
    assert calls[0][1] == date.today().strftime("%Y%m%d")
    for st, en in calls:
        assert (pd.Timestamp(en) - pd.Timestamp(st)).days <= 365   # над 1 г. сървърът връща празно


def test_cgb_akshare_failure_falls_back_to_bridge():
    from run import apply_bridge_fallbacks

    class FakeBridge:
        def fetch(self, key, path):
            return pd.Series([1.5], index=pd.to_datetime(["2026-05-29"]))

    snap = {}   # akshare не е дал нищо
    used = apply_bridge_fallbacks(snap, SERIES_CATALOG, bridge=FakeBridge())
    assert used == ["CN_CGB_10Y"] and snap["CN_CGB_10Y"].iloc[-1] == 1.5


def test_cgb_bridge_is_not_used_when_akshare_has_data():
    from run import apply_bridge_fallbacks

    class FakeBridge:
        def fetch(self, key, path):
            raise AssertionError("мостът не трябва да се вика")

    snap = {"CN_CGB_10Y": pd.Series([1.59], index=pd.to_datetime(["2026-11-25"]))}
    assert apply_bridge_fallbacks(snap, SERIES_CATALOG, bridge=FakeBridge()) == []
    assert snap["CN_CGB_10Y"].iloc[-1] == 1.59
