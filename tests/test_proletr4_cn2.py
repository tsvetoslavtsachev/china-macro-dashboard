"""ПРОЛЕТР4, втората вълна за Китай (26.11.2026, реш. Ц. КТ-1 до КТ-4 „Да, приемам ги.“).

Пазят: парсерите на новите серии (форматите са от живите отговори), спреда от същите рамки на
ChinaBond, лещата само за показване (бюджетът) и тавана ±6 на ориентирания z (КТ-3).
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from catalog.series import (  # noqa: E402
    SERIES_CATALOG, SCORED_LENSES, DISPLAY_ONLY_LENSES, ALLOWED_LENSES, validate_catalog,
)
from sources.akshare_cn import AkShareAdapter  # noqa: E402

NEW_SCORED = {
    "CN_CORE_CPI_YOY": "inflation", "CN_CONS_CONF": "growth", "CN_PMI_EMPLOYMENT": "labor",
    "CN_DISP_INCOME_YOY": "labor", "CN_CORP_SPREAD_3Y": "credit",
}
NEW_DISPLAY = ("CN_FISCAL_REV_YOY", "CN_FISCAL_EXP_YOY")


def test_catalog_valid_and_lenses_split():
    assert validate_catalog() == []
    assert ALLOWED_LENSES == SCORED_LENSES | DISPLAY_ONLY_LENSES
    assert DISPLAY_ONLY_LENSES == {"fiscal"} and not (SCORED_LENSES & DISPLAY_ONLY_LENSES)
    for k, lens in NEW_SCORED.items():
        assert SERIES_CATALOG[k]["lens"] == [lens]
    for k in NEW_DISPLAY:
        assert SERIES_CATALOG[k]["lens"] == ["fiscal"]


def test_new_scored_series_are_lens_members_not_composite():
    import importlib
    for k, lens in NEW_SCORED.items():
        m = importlib.import_module(f"modules.{lens}")
        assert k in m.SERIES and k not in m.COMPOSITE_SERIES


def test_display_only_lens_has_no_module():
    import export_api
    assert "fiscal" not in [name for name, _ in export_api.MODULES_ORDER]


def test_display_only_series_are_not_anomalies():
    from analysis.anomaly import compute_anomalies
    idx = pd.date_range("2010-01-01", periods=200, freq="MS")
    base = pd.Series(np.sin(np.arange(200) / 5.0), index=idx)
    spike = base.copy()
    spike.iloc[-1] = 50.0
    rep = compute_anomalies({"CN_FISCAL_REV_YOY": spike, "CN_CONS_CONF": spike.copy()})
    keys = {r.series_key for r in rep.top}
    assert "CN_FISCAL_REV_YOY" not in keys and "CN_CONS_CONF" in keys


# ── парсерите ────────────────────────────────────────────────────────────────

def test_core_cpi_row_parse_minus_100():
    df = pd.DataFrame(
        {"2026年10月": [100.7, 100.8], "2026年9月": [99.7, 101.0]},
        index=["居民消费价格指数(上年同月=100)", "不包括食品和能源居民消费价格指数(上年同月=100)"],
    )
    s = AkShareAdapter._parse_nbs_core_row(df)
    assert list(s.index) == [pd.Timestamp("2026-09-01"), pd.Timestamp("2026-10-01")]
    assert [round(v, 2) for v in s.values] == [1.0, 0.8]


def test_core_cpi_fetch_joins_baskets_newest_wins(tmp_path, monkeypatch):
    import sources.akshare_cn as m
    new = pd.DataFrame({"2026年1月": [100.8], "2025年12月": [101.5]}, index=["不包括食品和能源X"])
    old = pd.DataFrame({"2025年12月": [101.2], "2025年11月": [101.2]}, index=["不包括食品和能源X"])
    calls = []

    def fake(name, **kw):
        calls.append(kw["period"])
        return new if kw["period"] == "2026-" else old

    monkeypatch.setattr(m, "_ak_call", fake)
    s = m.AkShareAdapter(cache_path="c.json", base_dir=tmp_path)._fetch_core_cpi_yoy()
    assert calls == ["2026-", "2021-2025"]
    assert s.index.is_unique and s.index.is_monotonic_increasing
    assert round(float(s.loc["2025-12-01"]), 2) == 1.5   # застъпването: новата кошница печели


def _curve_frame():
    return pd.DataFrame({
        "曲线名称": ["中债国债收益率曲线", "中债中短期票据收益率曲线(AAA)", "中债商业银行普通债收益率曲线(AAA)",
                 "中债国债收益率曲线", "中债中短期票据收益率曲线(AAA)"],
        "日期": ["2026-11-25", "2026-11-25", "2026-11-25", "2026-11-26", "2026-11-26"],
        "3年": [1.40, 1.826, 9.99, 1.40, 1.876],
        "10年": [1.80, 2.10, 9.99, 1.81, 2.12],
    })


def test_spread_parse_mtn_minus_cgb_in_bp():
    s = AkShareAdapter._parse_spread_frame(_curve_frame())
    assert list(s.round(1).values) == [42.6, 47.6]


def test_chinabond_frames_fetched_once_for_both_series(tmp_path, monkeypatch):
    import sources.akshare_cn as m
    calls = []

    def fake(name, **kw):
        calls.append(kw["start_date"])
        if len(calls) > 1:
            raise ValueError("празен отговор")
        return _curve_frame()

    monkeypatch.setattr(m, "_ak_call", fake)
    a = m.AkShareAdapter(cache_path="c.json", base_dir=tmp_path)
    cgb = a._fetch_cgb_10y()
    n = len(calls)
    spr = a._fetch_aaa_spread_3y()
    assert len(calls) == n   # спредът не тегли наново
    assert list(cgb.values) == [1.80, 1.81] and len(spr) == 2


def test_consumer_confidence_and_fiscal_parse(tmp_path, monkeypatch):
    import sources.akshare_cn as m
    cc = pd.DataFrame({"月份": ["2026年09月份", "2026年08月份"], "消费者信心指数-指数值": [89.0, 89.5]})
    fr = pd.DataFrame({"月份": ["2026年10月份", "2026年09月份"], "累计-同比增长": [4.9, 5.1]})
    monkeypatch.setattr(m, "_ak_call", lambda name, **kw: {"macro_china_consumer_confidence": cc,
                                                         "macro_china_fiscal_revenue": fr}[name])
    a = m.AkShareAdapter(cache_path="c.json", base_dir=tmp_path)
    s = a._fetch_consumer_confidence()
    assert s.index[-1] == pd.Timestamp("2026-09-01") and s.iloc[-1] == 89.0
    f = a._fetch_fiscal_revenue_cum_yoy()
    assert f.index[-1] == pd.Timestamp("2026-10-01") and f.iloc[-1] == 4.9


# ── КТ-3: таванът на ориентирания z ─────────────────────────────────────────

def test_oriented_z_capped_at_6_with_tiny_nonzero_mad():
    from core.scorer import score_series
    idx = pd.date_range("2016-01-01", periods=130, freq="MS")
    vals = 3.45 + 0.005 * (np.arange(130) % 3)   # MAD почти нула, но не нула
    vals[-1] = 3.0
    s = pd.Series(vals, index=idx)
    r = score_series(s, polarity=-1, name="LPR", is_rate=True)
    assert r["z_score"] == 6.0 and r["health_z"] == 6.0
    assert r["z_raw"] is not None and abs(r["z_raw"]) > 6   # суровото остава
