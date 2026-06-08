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


# ── None-render hardening (рендерерите/модулите да преживеят None леща/percentile) ──
# Регресия за CI crash: thin-window percentile=None и None composite чупеха
# weekly_briefing (_score_color / _pct_bar_html / форматиране) и get_regime.

def test_score_color_none_safe():
    from export.weekly_briefing import _score_color
    assert _score_color(None) == "#8b949e"
    assert _score_color(float("nan")) == "#8b949e"
    assert _score_color(70) == "#3fb950"


def test_pct_bar_html_none_safe():
    from export.weekly_briefing import _pct_bar_html
    assert isinstance(_pct_bar_html(None, "#fff"), str)        # не хвърля (min(100,None))
    assert isinstance(_pct_bar_html(float("nan"), "#fff"), str)


def test_get_regime_none_safe():
    from core.scorer import get_regime
    from config import MACRO_REGIMES
    label, color = get_regime(None, MACRO_REGIMES)
    assert label == "Недостатъчно данни"


def test_render_lens_card_none_composite_and_percentile():
    from export.weekly_briefing import _render_lens_card
    result = {
        "module": "growth",
        "composite": None,                 # леща без данни (#9)
        "regime": "Недостатъчно данни",
        "key_readings": [
            {"label": "X", "value": 1.0, "percentile": None, "date": "2026-01-01"},  # thin (#12)
        ],
        "narrative": [],
    }
    html = _render_lens_card(result)        # не трябва да хвърля
    assert "—" in html


def test_briefing_context_fmt_helpers_none_safe():
    from export.briefing_context import _fmt_score, _fmt_pct
    assert _fmt_score(None) == "—"
    assert _fmt_pct(None) == "—"
    assert _fmt_score(35.0) == "35.0"
    assert _fmt_pct(85.0) == "85%"


def test_briefings_survive_missing_lens(tmp_path):
    """Интеграция: цяла леща без серии (property) → composite None → нито един
    генератор не бива да хвърля (възпроизвежда CI cache-miss ∩ outage)."""
    from datetime import date
    from catalog.series import SERIES_CATALOG
    from modules.property import COMPOSITE_SERIES as PROP
    from export.weekly_briefing import generate_weekly_briefing
    from export.briefing_context import generate_briefing_context
    from export.deep_briefing import generate_deep_briefing
    from export_api import build_macro_state

    idx = pd.date_range(end="2026-05-01", periods=60, freq="MS")
    snap = {k: pd.Series(range(1, 61), index=idx, dtype=float) for k in SERIES_CATALOG}
    for k in PROP:                          # махаме property композитните серии → None composite
        snap.pop(k, None)

    # целият pipeline, който weekly_update.yml пуска — нито един да не хвърля
    generate_weekly_briefing(snap, str(tmp_path / "w.html"), today=date(2026, 5, 30))
    generate_briefing_context(snap, str(tmp_path / "c.md"), today=date(2026, 5, 30))
    generate_deep_briefing(snap, str(tmp_path / "d.html"), today=date(2026, 5, 30), persist_state=False)
    state = build_macro_state(snap, date(2026, 5, 30))
    assert (tmp_path / "w.html").exists()
    assert (tmp_path / "c.md").exists()
    assert (tmp_path / "d.html").exists()
    assert state["executive_summary"]["composite_score"] is not None  # overall винаги float
