# -*- coding: utf-8 -*-
"""ПРОЛЕТР4: тестовете не чакат реални паузи между опитите към akshare."""
import pytest


@pytest.fixture(autouse=True)
def _no_akshare_backoff(monkeypatch):
    import sources.akshare_cn as ak_cn
    monkeypatch.setattr(ak_cn, "_AK_CALL_BACKOFF", ())
