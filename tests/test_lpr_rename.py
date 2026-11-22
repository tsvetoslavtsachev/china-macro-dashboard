# -*- coding: utf-8 -*-
"""ИЛЮ3 (22.11.2026): akshare 1.20.48 преименува macro_china_lpr на interest_rate_lpr_em.
Пазачът за LPR го хвана в сухата проба на часовника (AttributeError). Новото име първо."""
import sys
import types

from sources import akshare_cn


def _fake_ak(monkeypatch, **fns):
    mod = types.ModuleType("akshare")
    for k, v in fns.items():
        setattr(mod, k, v)
    monkeypatch.setitem(sys.modules, "akshare", mod)


def test_new_name_is_used_when_present(monkeypatch):
    _fake_ak(monkeypatch, interest_rate_lpr_em=lambda: "new", macro_china_lpr=lambda: "old")
    assert akshare_cn.lpr_frame() == "new"


def test_old_name_still_works_on_old_akshare(monkeypatch):
    _fake_ak(monkeypatch, macro_china_lpr=lambda: "old")
    assert akshare_cn.lpr_frame() == "old"


def test_mutation_neither_name_is_an_error_not_silence(monkeypatch):
    _fake_ak(monkeypatch)
    import pytest
    with pytest.raises(AttributeError):
        akshare_cn.lpr_frame()
