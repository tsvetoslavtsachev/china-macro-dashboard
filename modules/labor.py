"""
modules/labor.py
================
Labor lens за China macro dashboard.

Специфики за Китай:
  - Официалната безработица (~5%) е широко считана за подценена
  - Не включва мигрантски работници и неформалния сектор
  - Младежката безработица (16-24 г.) е структурен проблем
    → рекорд 21.3% юни 2023
    → НБС спря публикуването за 6 месеца (юли-декември 2023)
  - Демографски натиск: стареещо население намалява работната сила

Composite weights:
  Unemployment rate   0.40 — headline (подценена, но тренд е информативен)
  Youth unemployment  0.40 — структурен проблем, политически чувствителен
  Labor participation 0.20 — демографски proxy

Convention: ниска безработица = висок score (добре).
  Инверсия за unemployment: True (по-ниска = по-добре).
  Инверсия за participation: False (по-висока = по-добре).
"""
from __future__ import annotations
from typing import Any

import pandas as pd

from core.scorer import (
    score_series, build_sparkline, build_historical_context, get_regime,
)
from config import HISTORY_START


SERIES = {
    "CN_UNEMPLOYMENT": {
        "label": "Безработица — официална (ILO, %)",
        "invert": True,   # по-ниска = по-добре
        "transform": "level",
        "is_rate": False,
    },
    "CN_YOUTH_UNEMPLOYMENT": {
        "label": "Младежка безработица (16-24 г., %)",
        "invert": True,   # по-ниска = по-добре
        "transform": "level",
        "is_rate": False,
    },
    "CN_LABOR_PARTICIPATION": {
        "label": "Коефициент на участие в работната сила (%)",
        "invert": False,  # по-висока = по-добре
        "transform": "level",
        "is_rate": False,
    },
}

COMPOSITE_SERIES  = ["CN_UNEMPLOYMENT", "CN_YOUTH_UNEMPLOYMENT", "CN_LABOR_PARTICIPATION"]
COMPOSITE_WEIGHTS = [0.40,               0.40,                    0.20]

REGIMES = [
    (75, "ЗДРАВ ПАЗАР НА ТРУДА", "#00c853"),
    (60, "УМЕРЕНО НАПРЕЖЕНИЕ",   "#69f0ae"),
    (45, "СТРУКТУРНИ ПРОБЛЕМИ",  "#ffd600"),
    (30, "ВЛОШАВАНЕ",            "#ff6d00"),
    (0,  "КРИЗА НА ТРУДА",       "#d50000"),
]


def _apply_transform(series: pd.Series, transform: str) -> pd.Series:
    if transform == "yoy_pct":
        return series.pct_change(periods=12).dropna() * 100
    return series


def run(snapshot: dict[str, pd.Series]) -> dict[str, Any]:
    """Изчислява Labor lens за Китай."""
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

    narrative = _build_narrative(indicators)

    return {
        "module": "labor",
        "label": "Пазар на труда",
        "icon": "👷",
        "scores": {
            "employment": {"score": composite, "label": "Заетост"},
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
    hints = []

    youth = indicators.get("CN_YOUTH_UNEMPLOYMENT")
    if youth:
        val = youth.get("current_value", 0)
        if val > 20:
            hints.append(f"⚠️ Младежка безработица {val:.1f}% — над 20%. Структурен проблем. НБС спря публикуването 2023.")
        elif val > 15:
            hints.append(f"Младежка безработица {val:.1f}% — повишена. Образователната система произвежда повече дипломирани, отколкото пазарът абсорбира.")
        else:
            hints.append(f"Младежка безработица {val:.1f}% — под историческия пик (21.3% юни 2023).")

    unemp = indicators.get("CN_UNEMPLOYMENT")
    if unemp:
        val = unemp.get("current_value", 0)
        hints.append(f"Официална безработица {val:.1f}% — подценена. Не включва ~300 млн. мигрантски работници.")

    return hints
