"""
tests/test_nbs_manual.py
========================
Offline тестове за NbsManualAdapter (ръчни НБС тримесечни CSV — GDP/deflator).
Чете committed файловете в data/manual/ — без мрежа.

Anchor-ите са на СТАБИЛНА история (2Q2022 COVID dip, 2Q2023 base effect),
устойчиви на минорни ревизии и на бъдещ CSV update.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd

from sources.nbs_manual import NbsManualAdapter
from catalog.series import SERIES_CATALOG, ALLOWED_SOURCES, validate_catalog


def _adapter():
    return NbsManualAdapter()


def test_catalog_registers_quarterly_series():
    assert "nbs_manual" in ALLOWED_SOURCES
    for k in ("CN_GDP_GROWTH_Q", "CN_GDP_DEFLATOR_Q"):
        assert k in SERIES_CATALOG, f"{k} липсва в каталога"
        assert SERIES_CATALOG[k]["source"] == "nbs_manual"
        assert SERIES_CATALOG[k]["release_schedule"] == "quarterly"
    assert validate_catalog() == []


def test_parses_real_gdp_growth():
    snap = _adapter().get_snapshot(["CN_GDP_GROWTH_Q"])
    s = snap["CN_GDP_GROWTH_Q"].dropna()
    assert len(s) >= 10
    # стабилни исторически котви (НБС)
    covid = s.get(pd.Timestamp("2022-06-30"))       # Шанхай lockdown
    base = s.get(pd.Timestamp("2023-06-30"))        # base effect от 2022
    assert covid is not None and covid < 2.0, f"2Q2022 трябва нисък, е {covid}"
    assert base is not None and base > 5.5, f"2Q2023 трябва висок, е {base}"
    # реалният растеж е policy-pinned ~5% → последно в разумен band
    assert 2.0 < float(s.iloc[-1]) < 9.0


def test_parses_deflator_negative_streak():
    snap = _adapter().get_snapshot(["CN_GDP_DEFLATOR_Q"])
    s = snap["CN_GDP_DEFLATOR_Q"].dropna()
    assert len(s) >= 8
    # debt-deflation: дълъг отрицателен стрик в последните тримесечия
    last8 = list(s.tail(8))
    assert sum(1 for v in last8 if v < 0) >= 6, f"очаквам предимно отрицателен дефлатор, {last8}"
    # дефлаторът е малък по модул (не -10%), sanity
    assert all(abs(v) < 5 for v in s.values)


def test_get_snapshot_returns_both():
    snap = _adapter().get_snapshot(["CN_GDP_GROWTH_Q", "CN_GDP_DEFLATOR_Q"])
    assert set(snap.keys()) == {"CN_GDP_GROWTH_Q", "CN_GDP_DEFLATOR_Q"}
    for s in snap.values():
        assert isinstance(s, pd.Series) and not s.dropna().empty
        assert isinstance(s.index, pd.DatetimeIndex)


def test_find_stale_specs_empty():
    # file-based източник → никога auto-stale
    specs = [{"key": "CN_GDP_GROWTH_Q", "source_id": "x", "release_schedule": "quarterly"}]
    assert _adapter().find_stale_specs(specs) == []
