# -*- coding: utf-8 -*-
"""ПРОЛЕТР4 (25.11.2026): живи източници за Китай.

Офлайн: без мрежа, без akshare. Покрива адаптера за chinadata.live (разбор на низови
стойности и YYYY-MM, JSON и CSV, retry), замените на мъртвите akshare функции (с фалшиви
DataFrame-и), кръстосаните проверки (ok и флаг), правилото за сплитане на опашката на TSF
и членството на новите серии в лещите (само SERIES, не COMPOSITE)."""
from __future__ import annotations

import logging

import pandas as pd
import pytest
import requests

import analysis.crosscheck as cc
from analysis.crosscheck import annotate_snapshot, compare_series, level_yoy, splice_series
from catalog.polarity import polarity_for
from catalog.series import SERIES_CATALOG, validate_catalog
from sources import akshare_cn
from sources.akshare_cn import AkShareAdapter
from sources.chinadata_live import (
    ChinaDataLiveAdapter, ChinaDataError, USER_AGENT, cumulative_yoy, parse_records,
    parse_source_id, _records_from_csv, _records_from_json,
)


def ms(vals, start="2025-01-01"):
    return pd.Series(vals, index=pd.date_range(start, periods=len(vals), freq="MS"), dtype=float)


# ───────────────────────── chinadata.live: разбор ─────────────────────────

ENVELOPE = {"success": True, "data": {"id": "x", "data": [
    {"date": "2026-08", "value": "5.2"}, {"date": "2026-09", "value": ""},
    {"date": "2026-10", "value": "5.1"}, {"date": "bad", "value": "1"}, {"date": "2026-07", "value": "n/a"}]}}


def test_parse_records_string_values_and_month_dates():
    s = parse_records(_records_from_json(ENVELOPE))
    assert list(s.index) == [pd.Timestamp("2026-08-01"), pd.Timestamp("2026-10-01")]   # празно/нечислово/лоша дата отпадат
    assert list(s.values) == [5.2, 5.1] and s.dtype == float


def test_parse_records_trade_field_and_csv():
    csv_text = "date,export,import\n2026-09,447000,314000\n2026-10,412000,307000\n"
    s = parse_records(_records_from_csv(csv_text), "export")
    assert list(s.values) == [447000.0, 412000.0]
    assert parse_source_id("china-trade-monthly#export") == ("china-trade-monthly", "export", None)
    assert parse_source_id("a@cum_yoy") == ("a", "value", "cum_yoy")


def test_json_envelope_errors_are_loud():
    with pytest.raises(ChinaDataError):
        _records_from_json({"success": False})
    with pytest.raises(ChinaDataError):
        _records_from_json({"success": True, "data": {"id": "x"}})
    with pytest.raises(ChinaDataError):
        _records_from_json([1, 2])


def test_cumulative_yoy_needs_same_month_a_year_earlier():
    cum = pd.Series([100.0, 200.0, 50.0, 90.0], index=pd.to_datetime(["2025-02-01", "2025-03-01", "2026-02-01", "2026-04-01"]))
    y = cumulative_yoy(cum)
    assert list(y.index) == [pd.Timestamp("2026-02-01")]      # 2026-04 няма 2025-04 -> отпада, не се интерполира
    assert y.iloc[0] == pytest.approx(-50.0)


# ───────────────────────── chinadata.live: адаптер и retry ─────────────────────────

class FakeResp:
    def __init__(self, payload, status=200):
        self._p, self.status_code = payload, status
        self.text = ""

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"{self.status_code} Server Error")

    def json(self):
        return self._p


class FakeSession:
    def __init__(self, script):
        self.script, self.calls, self.headers = list(script), [], {}

    def get(self, url, timeout=None):
        self.calls.append(url)
        item = self.script.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


def _adapter(tmp_path, script):
    sess = FakeSession(script)
    ad = ChinaDataLiveAdapter(cache_path="data/cache_cd.json", base_dir=tmp_path, retry_backoff=[0, 0],
                              session=sess, request_delay=0)
    return ad, sess


def test_adapter_fetch_and_cache(tmp_path):
    ad, sess = _adapter(tmp_path, [FakeResp(ENVELOPE)])
    s = ad.fetch("CN_YOUTH_UNEMP_M", "china-youth-unemployment", "monthly", force=True)
    assert s.iloc[-1] == 5.1 and sess.calls[0].endswith("/data/china-youth-unemployment")
    s2 = ad.fetch("CN_YOUTH_UNEMP_M", "china-youth-unemployment", "monthly")    # от кеша, без нова заявка
    assert len(sess.calls) == 1 and s2.iloc[-1] == 5.1


def test_adapter_retries_transient_failures_then_succeeds(tmp_path):
    ad, sess = _adapter(tmp_path, [requests.ConnectionError("reset"), FakeResp({}, 503), FakeResp(ENVELOPE)])
    s = ad.fetch("K", "china-unemployment", "monthly", force=True)
    assert len(sess.calls) == 3 and s.iloc[-1] == 5.1 and ad.last_fetch_failures() == []


def test_adapter_gives_up_loudly_after_retries(tmp_path):
    ad, sess = _adapter(tmp_path, [requests.ConnectionError("down")] * 3)
    s = ad.fetch("K", "china-unemployment", "monthly", force=True)
    assert s.empty and ad._fetch_failures == ["K"]
    assert "chinadata_live K" in (tmp_path / "output" / ".fetch_failed").read_text(encoding="utf-8")


def test_adapter_reference_is_cached_under_a_separate_key_and_user_agent_is_generic(tmp_path):
    ad, sess = _adapter(tmp_path, [FakeResp(ENVELOPE)])
    ref = ad.fetch_reference("china-unemployment")
    assert ref.iloc[-1] == 5.1 and "ref:china-unemployment" in ad._cache
    assert "@" not in USER_AGENT and "http" not in USER_AGENT.lower() and "tsach" not in USER_AGENT.lower()


# ───────────────────────── akshare: замените на мъртвите функции ─────────────────────────

def _fake_ak(monkeypatch, table):
    monkeypatch.setattr(akshare_cn, "_ak_call", lambda name, **kw: table[name if isinstance(name, str) else name[0]].copy())


def _ad(tmp_path):
    return AkShareAdapter(cache_path="data/cache_ak.json", base_dir=tmp_path)


def test_ip_yoy_uses_industrial_value_added(monkeypatch, tmp_path):
    df = pd.DataFrame({"月份": ["2026年09月份", "2026年10月份"], "同比增长": [5.5, 4.8]})
    _fake_ak(monkeypatch, {"macro_china_industrial_value_added": df})
    s = _ad(tmp_path)._fetch_remote("CN_IP_YOY", "ip_yoy")
    assert s.index[-1] == pd.Timestamp("2026-10-01") and s.iloc[-1] == 4.8


def test_customs_trade_newest_first_gives_exports_and_imports(monkeypatch, tmp_path):
    df = pd.DataFrame({"月份": ["2026年10月份", "2026年09月份"], "当月出口额-同比增长": [35.2, 36.3],
                       "当月进口额-同比增长": [41.6, 31.1]})
    _fake_ak(monkeypatch, {"macro_china_customs_trade": df})
    ad = _ad(tmp_path)
    ex, im = ad._fetch_remote("e", "exports_usd_yoy"), ad._fetch_remote("i", "imports_usd_yoy")
    assert ex.index.is_monotonic_increasing and ex.iloc[-1] == 35.2 and im.iloc[-1] == 41.6


def test_caixin_pmi_month_end_dates_snap_to_the_reporting_month(monkeypatch, tmp_path):
    mfg = pd.DataFrame({"日期": ["2026-09-30", "2026-10-31"], "制造业PMI": [52.1, 52.0], "变化值": [0.6, -0.1]})
    svc = pd.DataFrame({"日期": ["2026-09-30", "2026-10-31"], "服务业PMI": [51.6, 50.8], "变化值": [0.2, -0.8]})
    _fake_ak(monkeypatch, {"macro_china_pmi_manufacturing_cx": mfg, "macro_china_pmi_services_cx": svc})
    ad = _ad(tmp_path)
    a, b = ad._fetch_remote("m", "pmi_mfg_caixin"), ad._fetch_remote("s", "pmi_svcs_caixin")
    assert a.index[-1] == pd.Timestamp("2026-10-01") and a.iloc[-1] == 52.0 and b.iloc[-1] == 50.8


def test_unemployment_picks_the_national_surveyed_row_only(monkeypatch, tmp_path):
    df = pd.DataFrame({"date": ["202609", "202609", "202610", "202610"],
                       "item": ["全国城镇调查失业率 ", "全国城镇25—59岁劳动力失业率 ", "全国城镇调查失业率 ", "全国城镇本地户籍劳动力失业率 "],   # 1.20.70: с краен интервал
                       "value": ["5.2", "4.9", "5.1", "5.2"]})
    _fake_ak(monkeypatch, {"macro_china_urban_unemployment": df})
    s = _ad(tmp_path)._fetch_remote("u", "unemp_surveyed")
    assert list(s.values) == [5.2, 5.1] and s.index[-1] == pd.Timestamp("2026-10-01")


def test_renamed_akshare_functions_resolve_new_name_first(monkeypatch):
    import types
    fake = types.SimpleNamespace(__version__="9", macro_china_social_financing=lambda: pd.DataFrame({"a": [1]}))
    monkeypatch.setitem(__import__("sys").modules, "akshare", fake)
    assert len(akshare_cn._ak_call(("macro_china_social_financing", "macro_china_shrzgm"))) == 1
    with pytest.raises(AttributeError):
        akshare_cn._ak_call(("nope_a", "nope_b"))


# ───────────────────────── кръстосани проверки ─────────────────────────

IDX = pd.date_range("2026-01-01", periods=10, freq="MS")


def test_crosscheck_ok_when_within_tolerance():
    a = pd.Series([5.0] * 10, index=IDX)
    b = a + 0.10                                    # 0.10 <= 0.15
    r = compare_series(a, b, 0.15)
    assert r["ok"] is True and r["n"] == 6 and r["max_diff"] == pytest.approx(0.10)


def test_crosscheck_flags_disagreement_in_any_of_the_last_six_months():
    a = pd.Series([5.0] * 10, index=IDX)
    b = a.copy()
    b.iloc[-3] += 0.30                              # 0.30 > 0.15 в един от последните 6
    r = compare_series(a, b, 0.15)
    assert r["ok"] is False and r["max_diff"] == pytest.approx(0.30) and r["worst_month"] == "2026-08"
    b2 = a.copy()
    b2.iloc[0] += 5.0                               # стар месец извън прозореца -> не броим
    assert compare_series(a, b2, 0.15)["ok"] is True


def test_crosscheck_unknown_when_too_few_common_months():
    r = compare_series(ms([1.0, 2.0]), ms([1.0, 2.0]), 0.1)
    assert r["ok"] is None and "малко" in r["note"]


def _snap(ip_delta=0.0):
    ip = pd.Series([5.0] * 8, index=IDX[:8])
    un = pd.Series([5.1] * 8, index=IDX[:8])
    ex_lv = ms([100.0] * 12 + [110.0] * 8, "2025-01-01")        # yoy 10% през 2026-01..08
    ex = pd.Series([10.0] * 8, index=IDX[:8])
    return {"CN_IP_YOY": ip, "CN_UNEMP_SURVEYED": un, "CN_EXPORTS_USD_YOY": ex,
            "CN_IMPORTS_USD_YOY": pd.Series([1.0] * 8, index=IDX[:8])}, \
        {"china-industrial-output": ip + ip_delta, "china-unemployment": un, "china-trade-monthly#export": ex_lv}


def test_annotate_marks_ok_and_flags_and_skips_imports(caplog):
    snap, refs = _snap(ip_delta=0.0)
    annotate_snapshot(snap, lambda sid: refs[sid])
    for k in ("CN_IP_YOY", "CN_UNEMP_SURVEYED", "CN_EXPORTS_USD_YOY"):
        assert snap[k].attrs["crosscheck"]["ok"] is True, k
    assert snap["CN_IMPORTS_USD_YOY"].attrs["crosscheck"]["ok"] is None
    assert snap["CN_IMPORTS_USD_YOY"].attrs["crosscheck"]["checked"] is False
    snap, refs = _snap(ip_delta=0.5)
    with caplog.at_level(logging.WARNING):
        annotate_snapshot(snap, lambda sid: refs[sid])
    assert snap["CN_IP_YOY"].attrs["crosscheck"]["ok"] is False
    assert "CROSSCHECK CN_IP_YOY" in caplog.text           # и логва предупреждение
    assert snap["CN_IP_YOY"].dropna().iloc[-1] == 5.0      # серията се запазва


def test_annotate_ref_failure_is_unknown_not_a_crash():
    snap, _ = _snap()

    def boom(sid):
        raise requests.ConnectionError("down")

    annotate_snapshot(snap, boom)
    assert snap["CN_IP_YOY"].attrs["crosscheck"]["ok"] is None
    annotate_snapshot(_snap()[0], None)                    # без адаптер


def test_exports_yoy_derivation_and_tolerance_is_one_point():
    lv = ms([100.0] * 12 + [111.0], "2025-01-01")
    assert level_yoy(lv).iloc[-1] == pytest.approx(11.0)
    assert cc.CROSSCHECKS["CN_EXPORTS_USD_YOY"]["tol"] == 1.0
    assert cc.CROSSCHECKS["CN_IP_YOY"]["tol"] == 0.15 and cc.CROSSCHECKS["CN_UNEMP_SURVEYED"]["tol"] == 0.1


# ───────────────────────── сплит на TSF ─────────────────────────

def test_splice_applies_only_when_overlap_agrees_within_one_percent():
    prim = ms([100.0, 200.0, 300.0, 400.0], "2026-01-01")                     # до 2026-04
    sec = pd.Series([201.0, 299.0, 401.0, 500.0, 600.0], index=pd.date_range("2026-02-01", periods=5, freq="MS"))
    out, info = splice_series(prim, sec)                                      # отклонения 0.5%, 0.33%, 0.25%
    assert info["applied"] is True and info["spliced_months"] == 2
    assert out.iloc[-1] == 600.0 and out.loc["2026-03-01"] == 300.0           # припокриването остава на основния
    bad = sec.copy()
    bad.iloc[1] = 330.0                                                       # +10%
    out2, info2 = splice_series(prim, bad)
    assert info2["applied"] is False and out2.equals(prim) and "разминаване" in info2["reason"]


def test_splice_refuses_with_too_little_overlap():
    prim = ms([100.0, 200.0, 300.0], "2026-01-01")
    sec = pd.Series([300.0, 400.0], index=pd.to_datetime(["2026-03-01", "2026-04-01"]))
    out, info = splice_series(prim, sec)
    assert info["applied"] is False and out.equals(prim)


def test_annotate_splices_tsf_into_the_snapshot_and_records_it():
    prim = ms([100.0, 200.0, 300.0, 400.0], "2026-01-01")
    sec = ms([200.0, 300.0, 400.0, 500.0], "2026-02-01")
    snap = {"CN_TSF_FLOW": prim}
    annotate_snapshot(snap, lambda sid: sec)
    assert snap["CN_TSF_FLOW"].index.max() == pd.Timestamp("2026-05-01")
    assert snap["CN_TSF_FLOW"].attrs["splice"]["applied"] is True
    snap2 = {"CN_TSF_FLOW": prim}
    annotate_snapshot(snap2, lambda sid: sec * 3)
    assert snap2["CN_TSF_FLOW"].index.max() == prim.index.max()
    assert snap2["CN_TSF_FLOW"].attrs["splice"]["applied"] is False


# ───────────────────────── каталог, полярност, членство ─────────────────────────

NEW_IDS = {"CN_UNEMP_SURVEYED": "labor", "CN_YOUTH_UNEMP_M": "labor", "CN_TSF_STOCK_YOY": "credit",
           "CN_RE_INVEST_YOY": "property", "CN_PROPERTY_SALES_YOY": "property"}


def test_catalog_is_valid_and_new_series_are_declared():
    assert validate_catalog() == []
    for k, lens in NEW_IDS.items():
        e = SERIES_CATALOG[k]
        assert lens in e["lens"] and e["release_schedule"] == "monthly" and e["name_bg"]
    assert SERIES_CATALOG["CN_UNEMP_SURVEYED"]["source"] == "akshare"
    assert SERIES_CATALOG["CN_YOUTH_UNEMP_M"]["source"] == "chinadata_live"


def test_polarity_of_new_series():
    assert polarity_for("CN_UNEMP_SURVEYED") == -1 and polarity_for("CN_YOUTH_UNEMP_M") == -1
    for k in ("CN_TSF_STOCK_YOY", "CN_RE_INVEST_YOY", "CN_PROPERTY_SALES_YOY", "CN_IP_YOY",
              "CN_EXPORTS_USD_YOY", "CN_IMPORTS_USD_YOY", "CN_PMI_MFG_CAIXIN", "CN_PMI_SVCS_CAIXIN"):
        assert polarity_for(k) == +1, k


def test_lens_membership_and_composites_after_the_composition_restructuring():
    # Състав 26.11.2026 (одобрен от собственика): композитите са СЪЗНАТЕЛНО сменени;
    # пълният състав е пиннат в test_sastav_cn.py, тук само ПРОЛЕТР4 членството.
    import modules.growth as g, modules.labor as lb, modules.credit as cr, modules.property as pr, modules.external as ex
    assert {"CN_IP_YOY", "CN_PMI_MFG_CAIXIN", "CN_PMI_SVCS_CAIXIN"} <= set(g.SERIES)
    assert {"CN_UNEMP_SURVEYED", "CN_YOUTH_UNEMP_M"} <= set(lb.SERIES)
    assert "CN_TSF_STOCK_YOY" in cr.SERIES
    assert {"CN_RE_INVEST_YOY", "CN_PROPERTY_SALES_YOY"} <= set(pr.SERIES)
    assert {"CN_EXPORTS_USD_YOY", "CN_IMPORTS_USD_YOY"} <= set(ex.SERIES)


def test_workflows_install_from_requirements_so_the_pin_applies():
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    for wf in ("export-api.yml", "weekly_update.yml"):
        assert "pip install -r requirements.txt" in (root / ".github" / "workflows" / wf).read_text(encoding="utf-8"), wf
