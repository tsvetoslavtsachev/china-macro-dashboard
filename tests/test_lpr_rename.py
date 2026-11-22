# -*- coding: utf-8 -*-
"""ИЛЮ3: LPR от akshare през смените на версиите.
22.11.2026: 1.20.48 преименува macro_china_lpr на interest_rate_lpr_em (същите колони).
23.11.2026 (Е1): 1.20.65 връща колоните на китайски. Двата вида се свеждат до латинските;
непознат вид е грешка, която назовава видените колони."""
import sys
import types

import pandas as pd
import pytest

from sources import akshare_cn

LATIN = pd.DataFrame({"TRADE_DATE": ["2026-10-20", "2026-11-20"], "LPR1Y": [3.0, 3.0],
                      "LPR5Y": [3.5, 3.5], "RATE_1": [4.35, 4.35], "RATE_2": [4.9, 4.9]})
CHINESE = pd.DataFrame({"日期": ["2026-10-20", "2026-11-20"], "1年期LPR": [3.0, 3.0],
                        "5年期以上LPR": [3.5, 3.5], "短期贷款利率": [4.35, 4.35], "中长期贷款利率": [4.9, 4.9]})


def _fake_ak(monkeypatch, **fns):
    mod = types.ModuleType("akshare")
    for k, v in fns.items():
        setattr(mod, k, v)
    monkeypatch.setitem(sys.modules, "akshare", mod)


def test_new_name_is_used_when_present(monkeypatch):
    _fake_ak(monkeypatch, interest_rate_lpr_em=lambda: LATIN.copy(),
             macro_china_lpr=lambda: pytest.fail("старото име не бива да се вика"))
    assert list(akshare_cn.lpr_frame()["LPR1Y"]) == [3.0, 3.0]


def test_old_name_still_works_on_old_akshare(monkeypatch):
    _fake_ak(monkeypatch, macro_china_lpr=lambda: LATIN.copy())
    assert "TRADE_DATE" in akshare_cn.lpr_frame().columns


def test_e1_chinese_columns_of_1_20_65_are_read(monkeypatch):
    _fake_ak(monkeypatch, interest_rate_lpr_em=lambda: CHINESE.copy())
    df = akshare_cn.lpr_frame()
    assert list(df["TRADE_DATE"]) == ["2026-10-20", "2026-11-20"]
    assert list(df["LPR1Y"]) == [3.0, 3.0] and list(df["LPR5Y"]) == [3.5, 3.5]


def test_e1_both_kinds_give_the_same_published_lpr(monkeypatch):
    from datetime import date
    import export_api as E
    out = []
    for frame in (LATIN, CHINESE):
        _fake_ak(monkeypatch, interest_rate_lpr_em=lambda f=frame: f.copy())
        out.append(E.build_lpr(akshare_cn.lpr_frame(), date(2026, 11, 22))["series"])
    assert out[0] == out[1] and out[0]["lpr_1y"][-1] == ["2026-11-20", 3.0]


def test_mutation_e1_unknown_columns_name_what_was_seen(monkeypatch):
    _fake_ak(monkeypatch, interest_rate_lpr_em=lambda: pd.DataFrame({"date": ["x"], "lpr": [1.0]}))
    with pytest.raises(ValueError) as e:
        akshare_cn.lpr_frame()
    assert "видях ['date', 'lpr']" in str(e.value) and "TRADE_DATE" in str(e.value)


def test_mutation_neither_name_is_an_error_not_silence(monkeypatch):
    _fake_ak(monkeypatch)
    with pytest.raises(AttributeError):
        akshare_cn.lpr_frame()


def test_source_label_names_the_real_function_and_version(monkeypatch):
    from datetime import date
    import export_api as E

    def macro_china_lpr():
        return LATIN.copy()
    _fake_ak(monkeypatch, macro_china_lpr=macro_china_lpr, __version__="1.20.36")
    doc = E.build_lpr(akshare_cn.lpr_frame(), date(2026, 11, 22))
    assert doc["source"] == "akshare macro_china_lpr 1.20.36"
