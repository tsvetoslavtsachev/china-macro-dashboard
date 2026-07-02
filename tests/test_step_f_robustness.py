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


# ── #9 / REVIEW-03 т.0.8 (P3-fix-A) — MIN_BACKED_LENSES под ──────────────────
# reweight формулата нямаше долна граница: 1-2 backed лещи ставаха ЦЕЛИЯТ
# "Композитен Macro Score" (labor-only → 18.6 → "РЕЦЕСИОНЕН" flip чисто от
# availability, не сигнал). Пренаписано по нова спецификация: <3 backed
# лещи → overall_composite()=None (недостатъчно за headline). Старите пинове
# на 30.0 (2 backed) и 48.0 (2 backed) СА ЗАМЕНЕНИ по спец, не изтрити тихо —
# и двата случая вече падат под MIN_BACKED_LENSES=3.

def test_overall_composite_below_min_backed_is_none():
    """2 backed лещи (< MIN_BACKED_LENSES=3) → None, не reweight върху 2-те.

    Преди фикса (P3-fix-A 0.8) този случай връщаше 30.0 (credit(0.25)+
    property(0.20) reweight) — заменено, защото 2 от 5 лещи не са достатъчна
    основа за headline "Композитен Macro Score" (REVIEW-03 демо: labor-only
    единична леща минаваше за целия композит)."""
    results = [
        {"module": "growth", "composite": None},      # без данни (outage)
        {"module": "credit", "composite": 30.0},
        {"module": "property", "composite": 30.0},
    ]
    assert overall_composite(results) is None


def test_overall_composite_still_below_min_backed_is_none():
    """2 backed лещи (growth+property, < MIN_BACKED_LENSES=3) → None.

    Преди фикса (P3-fix-A 0.8) този случай връщаше 48.0 — (40*0.30+60*0.20)
    /(0.30+0.20)=24/0.50=48.0. Заменено по същата причина като горния тест."""
    results = [
        {"module": "growth", "composite": 40.0},      # 0.30
        {"module": "credit", "composite": None},       # изключена
        {"module": "property", "composite": 60.0},     # 0.20
    ]
    assert overall_composite(results) is None


def test_overall_composite_exactly_min_backed_computes():
    """ТОЧНО 3 backed лещи (= MIN_BACKED_LENSES) → смята се нормално.

    Синтетичен пин (изчислен САМО с Python аритметика от РЕАЛНИТЕ тегла в
    config.MODULE_WEIGHTS — growth=0.30, credit=0.25, labor=0.10 — НЕ
    мандатния илюстративен пример, който аритметично не излиза):
      growth 70.0 * 0.30 = 21.0
      credit 40.0 * 0.25 = 10.0
      labor  55.0 * 0.10 =  5.5
      total_w = 0.65; weighted = 36.5; 36.5 / 0.65 = 56.153... → round(.,1) = 56.2
    """
    results = [
        {"module": "growth", "composite": 70.0},
        {"module": "credit", "composite": 40.0},
        {"module": "property", "composite": None},
        {"module": "inflation", "composite": None},
        {"module": "labor", "composite": 55.0},
    ]
    assert overall_composite(results) == 56.2


def test_overall_composite_all_five_backed_unchanged():
    """5/5 backed (пълен композит) — непроменено поведение от преди фикса."""
    results = [
        {"module": "growth", "composite": 60.0},
        {"module": "credit", "composite": 60.0},
        {"module": "property", "composite": 60.0},
        {"module": "inflation", "composite": 60.0},
        {"module": "labor", "composite": 60.0},
    ]
    assert overall_composite(results) == 60.0


def test_overall_composite_all_none_is_none_not_50():
    """0 backed лещи → None (старият total_w==0 → 50.0 клон е недостижим по
    спец — MIN_BACKED_LENSES=3 гейтът хваща случая по-рано; при 0 backed
    гейтът гарантира None преди total_w изобщо да се провери)."""
    results = [
        {"module": "growth", "composite": None},
        {"module": "credit", "composite": None},
    ]
    assert overall_composite(results) is None


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
    # 4/5 backed (само property липсва) — над MIN_BACKED_LENSES=3, overall си остава float.
    assert state["executive_summary"]["composite_score"] is not None


# ── REVIEW-03 т.0.8 (P3-fix-A) — lenses_backed поле + insufficient режим ────
# executive_summary["lenses_backed"] = "X/5" — ВИНАГИ попълнено (не само при
# проблем), за всичките случаи: <3 backed (insufficient), ==3, ==5 (пълно).

def _macro_state_with_n_backed(n_backed: int) -> dict:
    """Помощна: build_macro_state с точно n_backed от 5-те лещи имащи данни
    (останалите — снапшот без техните композитни серии → composite None)."""
    from datetime import date
    from catalog.series import SERIES_CATALOG
    from export_api import build_macro_state
    import modules.growth, modules.credit, modules.property, modules.inflation, modules.labor

    lens_composite_series = {
        "growth": modules.growth.COMPOSITE_SERIES,
        "credit": modules.credit.COMPOSITE_SERIES,
        "property": modules.property.COMPOSITE_SERIES,
        "inflation": modules.inflation.COMPOSITE_SERIES,
        "labor": modules.labor.COMPOSITE_SERIES,
    }
    lens_order = ["growth", "credit", "property", "inflation", "labor"]
    to_drop_lenses = lens_order[n_backed:]   # изважда лещите СЛЕД първите n_backed

    idx = pd.date_range(end="2026-05-01", periods=60, freq="MS")
    snap = {k: pd.Series(range(1, 61), index=idx, dtype=float) for k in SERIES_CATALOG}
    for lens in to_drop_lenses:
        for k in lens_composite_series[lens]:
            snap.pop(k, None)

    return build_macro_state(snap, date(2026, 5, 30))


def test_lenses_backed_field_two_backed_is_insufficient():
    """2/5 backed (< MIN_BACKED_LENSES=3) → composite None + regime "insufficient"
    + lenses_backed="2/5", попълнено ВИНАГИ (не само при проблем)."""
    state = _macro_state_with_n_backed(2)
    es = state["executive_summary"]
    assert es["composite_score"] is None
    assert es["regime_key"] == "insufficient"
    assert es["lenses_backed"] == "2/5"


def test_lenses_backed_field_three_backed_computes():
    """3/5 backed (== MIN_BACKED_LENSES) → composite смятан нормално,
    lenses_backed="3/5"."""
    state = _macro_state_with_n_backed(3)
    es = state["executive_summary"]
    assert es["composite_score"] is not None
    assert es["regime_key"] != "insufficient"
    assert es["lenses_backed"] == "3/5"


def test_lenses_backed_field_five_backed_unchanged():
    """5/5 backed (пълен композит) — непроменено поведение, lenses_backed="5/5"."""
    state = _macro_state_with_n_backed(5)
    es = state["executive_summary"]
    assert es["composite_score"] is not None
    assert es["regime_key"] != "insufficient"
    assert es["lenses_backed"] == "5/5"
