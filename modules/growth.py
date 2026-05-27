"""
modules/growth.py
=================
Growth lens за China macro dashboard.

Специфики за Китай:
  - GDP таргет е explicit (~5%) — политически приоритет #1
  - Индустриалното производство е по-надеждна мярка от headline GDP
  - GDP deflator отрицателен → реалният растеж е надценен спрямо номиналния
  - Капиталообразуването (~40% GDP) е investment-driven growth модел

Composite weights:
  GDP growth        0.35 — headline, политически benchmark
  Industry growth   0.30 — реална активност, по-малко манипулируема
  Services growth   0.20 — структурен преход
  Capital formation 0.15 — investment cycle proxy

Convention: висок YoY % растеж = висок score = здрав растеж.
"""
from __future__ import annotations
from typing import Any

import pandas as pd

from core.scorer import (
    score_series, build_sparkline, build_historical_context, get_regime,
)
from config import HISTORY_START


# ─── Серии в lens-а ──────────────────────────────────────────────
SERIES = {
    "CN_GDP_GROWTH": {
        "label": "БВП — реален растеж (YoY %)",
        "invert": False,
        "transform": "level",
        "is_rate": True,
    },
    "CN_INDUSTRY_GROWTH": {
        "label": "Индустрия — реален растеж (YoY %)",
        "invert": False,
        "transform": "level",
        "is_rate": True,
    },
    "CN_SERVICES_GROWTH": {
        "label": "Услуги — реален растеж (YoY %)",
        "invert": False,
        "transform": "level",
        "is_rate": True,
    },
    "CN_CAPEX_GDP": {
        "label": "Брутно капиталообразуване (% от БВП)",
        "invert": False,
        "transform": "level",
        "is_rate": False,
    },
    "CN_MANUFACTURING_GDP": {
        "label": "Производство — дял от БВП (%)",
        "invert": False,
        "transform": "level",
        "is_rate": False,
    },
}

COMPOSITE_SERIES  = ["CN_GDP_GROWTH", "CN_INDUSTRY_GROWTH", "CN_SERVICES_GROWTH", "CN_CAPEX_GDP"]
COMPOSITE_WEIGHTS = [0.35,             0.30,                 0.20,                 0.15]

REGIMES = [
    (80, "СИЛНА ЕКСПАНЗИЯ",  "#00c853"),
    (65, "РАСТЕЖ НАД ТАРГЕТ","#69f0ae"),
    (50, "РАСТЕЖ НА ТАРГЕТ", "#ffd600"),
    (35, "ПОД ТАРГЕТ",       "#ff6d00"),
    (0,  "РЕЦЕСИЯ",          "#d50000"),
]


def _apply_transform(series: pd.Series, transform: str) -> pd.Series:
    if transform == "yoy_pct":
        return series.pct_change(periods=12).dropna() * 100
    if transform == "qoq_pct":
        return series.pct_change(periods=4).dropna() * 100
    if transform == "mom_pct":
        return series.pct_change().dropna() * 100
    return series


def run(snapshot: dict[str, pd.Series]) -> dict[str, Any]:
    """Изчислява Growth lens за Китай."""
    indicators: dict[str, dict] = {}
    transformed: dict[str, pd.Series] = {}

    for sid, meta in SERIES.items():
        if sid in snapshot and not snapshot[sid].empty:
            transform = meta.get("transform", "level")
            ts = _apply_transform(snapshot[sid], transform)
            transformed[sid] = ts
            if not ts.empty:
                indicators[sid] = score_series(
                    ts,
                    history_start=HISTORY_START,
                    invert=meta["invert"],
                    name=meta["label"],
                    is_rate=meta.get("is_rate", False),
                )

    composite = _composite(indicators, COMPOSITE_SERIES, COMPOSITE_WEIGHTS)
    regime_label, regime_color = get_regime(composite, REGIMES)

    sparklines: dict[str, dict] = {}
    hist_context: dict[str, dict] = {}
    for sid in SERIES:
        if sid in transformed and not transformed[sid].empty:
            sparklines[sid] = build_sparkline(transformed[sid], months=36)
            hist_context[sid] = build_historical_context(
                transformed[sid],
                float(transformed[sid].iloc[-1]),
                history_start=HISTORY_START,
            )

    # China-специфична narrative
    narrative = _build_narrative(indicators)

    return {
        "module": "growth",
        "label": "Растеж и активност",
        "icon": "📈",
        "scores": {
            "activity": {"score": composite, "label": "Активност"},
        },
        "composite": composite,
        "regime": regime_label,
        "regime_color": regime_color,
        "indicators": indicators,
        "sparklines": sparklines,
        "historical_context": hist_context,
        "key_readings": _key_readings(indicators),
        "narrative": narrative,
    }


def _composite(scores: dict, series_list: list, weights: list) -> float:
    vals = [scores[s]["score"] for s in series_list if s in scores]
    wts = [weights[i] for i, s in enumerate(series_list) if s in scores]
    if not vals:
        return 50.0
    return round(sum(v * w for v, w in zip(vals, wts)) / sum(wts), 1)


def _key_readings(indicators: dict) -> list[dict]:
    out = []
    for sid in SERIES:
        if sid in indicators:
            s = indicators[sid]
            out.append({
                "id": sid,
                "label": s["name"],
                "value": s["current_value"],
                "date": s["last_date"],
                "yoy": s["yoy_change"],
                "yoy_unit": s.get("yoy_unit", "%"),
                "percentile": s["percentile"],
                "score": s["score"],
            })
    return out


def _build_narrative(indicators: dict) -> list[str]:
    """China-специфични narrative hints базирани на текущите стойности."""
    hints = []

    gdp = indicators.get("CN_GDP_GROWTH")
    if gdp:
        val = gdp.get("current_value", 0)
        if val >= 5.0:
            hints.append(f"БВП растеж {val:.1f}% — на или над официалния таргет от ~5%.")
        elif val >= 4.0:
            hints.append(f"БВП растеж {val:.1f}% — под официалния таргет. Очаквайте допълнителни стимули.")
        else:
            hints.append(f"БВП растеж {val:.1f}% — значително под таргет. Риск от мащабни стимули.")

    capex = indicators.get("CN_CAPEX_GDP")
    if capex:
        val = capex.get("current_value", 0)
        if val > 42:
            hints.append(f"Капиталообразуване {val:.1f}% от БВП — изключително висок investment-driven модел.")
        elif val < 38:
            hints.append(f"Капиталообразуване {val:.1f}% от БВП — намалява. Rebalancing към потребление в ход.")

    return hints
