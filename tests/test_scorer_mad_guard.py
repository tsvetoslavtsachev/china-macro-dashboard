"""
tests/test_scorer_mad_guard.py
===============================
Verify gate за REVIEW-03 т.0.9 (P3-fix-B): MAD=0 guard за административно
пиннати серии (LPR клас).

Дефектът: медиана, доминираща 10-г. прозорец (>50% еднакви котировки) → MAD=0
→ scale=0 → z форсиран 0 → score 50 "неутрално" при реален всеисторически
екстремум. Гейтът: такава серия НЕ дава 50; константа навсякъде → 50, но с
изричен degenerate флаг.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from core.scorer import score_series  # noqa: E402


def monthly(values: list[float], end: str = "2026-03-01") -> pd.Series:
    idx = pd.date_range(end=end, periods=len(values), freq="MS")
    return pd.Series(values, index=idx)


def pinned_rate_series() -> pd.Series:
    """LPR-подобна: дълга варирана предистория + 10-г. прозорец, доминиран от
    плато 4.3, завършващ на всеисторически минимум 3.0.

    Прозорецът (последните 120 месеца): 115×4.3 + 5 стъпки надолу → MAD=0.
    Пълната история: +130 по-ранни варирани месеца → MAD>0 → fallback работи.
    """
    early = list(np.linspace(5.0, 6.0, 130))            # варирана предистория
    plateau = [4.3] * 115                                # административно плато
    steps = [4.1, 3.9, 3.6, 3.3, 3.0]                    # cuts до all-time low
    return monthly(early + plateau + steps)


class TestMadGuard:
    def test_pinned_series_at_low_is_not_neutral(self):
        """ГЕЙТ: пинната серия на всеисторически минимум НЕ дава score 50."""
        s = pinned_rate_series()
        res = score_series(s, invert=True, name="LPR-like", min_obs=36)

        assert res["scale_fallback"] is True, "очаквахме fallback към пълна история"
        assert res["degenerate"] is False
        assert res["score"] != pytest.approx(50.0), (
            f"пинната серия на дъно дава {res['score']} — фалшивото неутрално се върна"
        )
        # invert=True + стойност под нормата → облекчаване → score > 50
        assert res["score"] > 50.0
        assert res["health_z"] > 0

    def test_constant_series_is_neutral_but_flagged(self):
        """Константа навсякъде → неутрално 50, но с изричен degenerate флаг."""
        s = monthly([4.3] * 200)
        res = score_series(s, invert=True, name="const", min_obs=36)

        assert res["degenerate"] is True
        assert res["score"] == pytest.approx(50.0)
        assert res["health_z"] == pytest.approx(0.0)

    def test_constant_u_polarity_is_neutral_not_73(self):
        """U-полярност + константа: преди даваше z_h=band → score ~73.
        Сега: неутрално 50 + degenerate флаг."""
        s = monthly([2.0] * 200)
        res = score_series(s, polarity=("U", "target", 2.0), name="const-U", min_obs=36)

        assert res["degenerate"] is True
        assert res["score"] == pytest.approx(50.0)

    def test_normal_series_unaffected(self):
        """Регресия: нормална варирана серия не тригерира guard-а."""
        rng = np.random.default_rng(7)
        s = monthly(list(5.0 + np.cumsum(rng.normal(0, 0.1, 180))))
        res = score_series(s, invert=False, name="normal", min_obs=36)

        assert res["scale_fallback"] is False
        assert res["degenerate"] is False
        assert res["z_score"] is not None

    def test_thin_window_unchanged(self):
        """Регресия: thin_window пътят (годишни серии) остава какъвто беше —
        fallback към пълна история, percentile/z нулирани за display."""
        s = monthly(list(np.linspace(60.0, 70.0, 20)))  # 20 точки < min_obs
        res = score_series(s, invert=False, name="thin", min_obs=36)

        assert res["thin_window"] is True
        assert res["percentile"] is None
        assert res["z_score"] is None
