"""
tests/test_analytical_layer.py
==============================
Offline тестове за China аналитичния слой (B2):
  - cross_lens_pairs валидация
  - compute_cross_lens_divergence + compute_anomalies върху синтетичен snapshot
  - weekly_briefing рендира новите секции (Cross-Lens Divergence + Top Anomalies)

Без мрежа — синтетичен snapshot покрива целия каталог.
"""
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import numpy as np
import pandas as pd

from catalog.series import SERIES_CATALOG
from catalog.cross_lens_pairs import CROSS_LENS_PAIRS, validate_pairs
from analysis.divergence import compute_cross_lens_divergence
from analysis.anomaly import compute_anomalies
from export.weekly_briefing import generate_weekly_briefing


VALID_STATES = {
    "both_up", "both_down", "a_up_b_down", "a_down_b_up",
    "transition", "insufficient_data",
}


def _monthly(values, end="2026-05-01"):
    idx = pd.date_range(end=end, periods=len(values), freq="MS")
    return pd.Series(values, index=idx)


def _synthetic_snapshot():
    """Покрива целия каталог; смесва тренд + няколко spike-а за аномалии."""
    snap = {}
    for i, k in enumerate(SERIES_CATALOG.keys()):
        if i % 9 == 0:
            vals = [2.0 + 0.03 * np.sin(j * 0.3) for j in range(57)] + [9.0, 9.4, 9.9]
        else:
            vals = list(np.linspace(2.0 + (i % 4) * 0.2, 4.5 + (i % 3) * 0.3, 60))
        snap[k] = _monthly(vals)
    return snap


def test_validate_pairs_clean():
    assert validate_pairs() == []
    assert len(CROSS_LENS_PAIRS) == 3


def test_cross_lens_divergence_runs():
    snap = _synthetic_snapshot()
    rep = compute_cross_lens_divergence(snap)
    assert len(rep.pairs) == 3
    ids = {p.pair_id for p in rep.pairs}
    assert ids == {"credit_real_economy", "monetary_inflation_trap", "external_domestic_balance"}
    for p in rep.pairs:
        assert p.state in VALID_STATES
        # interpretation непразен за всеки state
        assert isinstance(p.interpretation, str) and p.interpretation


def test_anomalies_run():
    snap = _synthetic_snapshot()
    rep = compute_anomalies(snap, z_threshold=2.0, top_n=10)
    assert rep.threshold == 2.0
    assert rep.total_flagged >= 1            # spike-овете гарантират поне 1
    assert len(rep.top) <= 10
    for a in rep.top:
        assert abs(a.z_score) > 2.0
        assert a.direction in ("up", "down")


def test_briefing_renders_new_sections(tmp_path):
    snap = _synthetic_snapshot()
    out = tmp_path / "briefing.html"
    generate_weekly_briefing(snap, str(out), today=date(2026, 5, 30))
    html = out.read_text(encoding="utf-8")
    assert "Cross-Lens Divergence" in html
    assert "Top Anomalies" in html
    assert html.count('class="pair-card"') == 3
    assert 'class="anom-table"' in html
    # China dark тема запазена
    assert "#0d1117" in html
    # self-contained
    assert "<script" not in html.lower()


def test_briefing_handles_empty_snapshot(tmp_path):
    out = tmp_path / "empty.html"
    generate_weekly_briefing({}, str(out), today=date(2026, 5, 30))
    assert out.exists()
    html = out.read_text(encoding="utf-8")
    # При празен snapshot — divergence pairs дават insufficient_data, не crash
    assert "Cross-Lens Divergence" in html
