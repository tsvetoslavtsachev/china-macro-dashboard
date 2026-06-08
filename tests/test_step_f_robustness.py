"""Regression за Стъпка F (audit 2026-06-07): #9 неутрална леща, #12 thin-window.

#9: леща без композитни серии връща composite=None и се изключва от headline-а
    (reweight), вместо да влачи фалшиво 50 (cache-miss ∩ akshare outage).
#12: percentile/z върху ~14-17-точкова (policy-pinned тримесечна) серия е ненадеждна
    → percentile/z_score=None + thin_window=True.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent))

from config import overall_composite
from core.scorer import score_series


# ── #9 — None-safe reweight ──────────────────────────────────────────────────

def test_overall_composite_excludes_none_lens():
    """Леща с composite=None не дърпа headline-а към 50; reweight върху backed."""
    results = [
        {"module": "growth", "composite": None},      # без данни (outage)
        {"module": "credit", "composite": 30.0},
        {"module": "property", "composite": 30.0},
    ]
    # backed: credit(0.25)+property(0.20), и двете 30 → 30.0 (не ~43 от фалшиво 50)
    assert overall_composite(results) == 30.0


def test_overall_composite_reweights_correctly():
    results = [
        {"module": "growth", "composite": 40.0},      # 0.30
        {"module": "credit", "composite": None},       # изключена
        {"module": "property", "composite": 60.0},     # 0.20
    ]
    # (40*0.30 + 60*0.20) / (0.30+0.20) = 24 / 0.50 = 48.0
    assert overall_composite(results) == 48.0


def test_overall_composite_all_none_neutral():
    results = [
        {"module": "growth", "composite": None},
        {"module": "credit", "composite": None},
    ]
    assert overall_composite(results) == 50.0


def test_module_composite_none_when_no_series():
    from modules.growth import _composite
    assert _composite({}, ["X", "Y"], [1, 1]) is None


# ── #12 — thin-window флаг ───────────────────────────────────────────────────

def test_thin_window_nulls_display_stats():
    """Къса тримесечна серия (14 < min_obs 36) → percentile/z None, thin_window True."""
    idx = pd.date_range(end="2026-01-01", periods=14, freq="QS")
    s = pd.Series(
        [1.0, 1.1, 1.0, 0.9, 1.0, 1.2, 0.8, 1.0, 1.1, 0.95, 1.05, 1.0, 0.9, 1.0],
        index=idx,
    )
    out = score_series(s, name="CN_GDP_DEFLATOR_Q")
    assert out["thin_window"] is True
    assert out["percentile"] is None
    assert out["z_score"] is None
    assert out["score"] is not None       # score все пак се смята (best-effort)


def test_full_window_not_thin():
    idx = pd.date_range(end="2026-01-01", periods=120, freq="MS")
    s = pd.Series(range(120), index=idx, dtype=float)
    out = score_series(s, name="LONG")
    assert out["thin_window"] is False
    assert out["percentile"] is not None
    assert out["z_score"] is not None
