"""
modules/credit.py
=================
Credit & Monetary Policy lens за China macro dashboard.

Специфики за Китай:
  - PBoC управлява чрез лихвени проценти (LPR/repo), RRR и кредитни квоти
  - China Credit Impulse (промяна в новия кредит като % от GDP) е
    доказан глобален leading indicator (leads global PMI с 6-12 месеца)
  - Кредитът към частния сектор е 194% от GDP — debt overhang
  - M2 е 227% от GDP — най-висок в света сред G20
  - CNY/USD е управляван флоат — PBoC контролира дневния band

Composite weights:
  Policy rate      0.25 — PBoC stance (намаляване = easing)
  Lending rate     0.20 — реален cost of credit
  Credit/GDP       0.25 — кредитна дълбочина и debt overhang
  M2/GDP           0.20 — монетарна маса
  CNY/USD          0.10 — валутен курс (слабо CNY = конкурентност)

Convention:
  - Ниски лихви = easing = по-добре за растеж → invert=True за rate серии
  - Висок кредит/GDP = debt overhang = по-лошо → invert=True
  - Слабо CNY (висок CNY/USD) = по-добре за exports → invert=False
"""
from __future__ import annotations
from typing import Any

import pandas as pd

from core.scorer import (
    score_series, build_sparkline, build_historical_context, get_regime,
)
from config import HISTORY_START


SERIES = {
    "CN_POLICY_RATE": {
        "label": "Политическа лихва — PBoC 7-day repo (%)",
        "invert": True,   # по-ниска = easing = по-добре
        "transform": "level",
        "is_rate": False,
    },
    "CN_LENDING_RATE": {
        "label": "Кредитна лихва (%)",
        "invert": True,   # по-ниска = по-евтин кредит = по-добре
        "transform": "level",
        "is_rate": False,
    },
    "CN_DEPOSIT_RATE": {
        "label": "Депозитна лихва (%)",
        "invert": True,
        "transform": "level",
        "is_rate": False,
    },
    "CN_CREDIT_PRIVATE": {
        "label": "Кредит към частния сектор (% от БВП)",
        "invert": True,   # висок кредит/GDP = debt overhang = по-лошо
        "transform": "level",
        "is_rate": False,
    },
    "CN_M2_GDP": {
        "label": "М2 — дял от БВП (%)",
        "invert": False,  # по-висок M2 = повече ликвидност = неутрален
        "transform": "level",
        "is_rate": False,
    },
    "CN_CNY_USD": {
        "label": "Валутен курс CNY/USD",
        "invert": False,
        "transform": "level",
        "is_rate": False,
    },
}

COMPOSITE_SERIES  = ["CN_POLICY_RATE", "CN_LENDING_RATE", "CN_CREDIT_PRIVATE", "CN_M2_GDP", "CN_CNY_USD"]
COMPOSITE_WEIGHTS = [0.25,              0.25,              0.25,                0.15,         0.10]

REGIMES = [
    (75, "СИЛНО МОНЕТАРНО СТИМУЛИРАНЕ", "#00c853"),
    (60, "УМЕРЕНО СТИМУЛИРАНЕ",         "#69f0ae"),
    (45, "НЕУТРАЛНА ПОЛИТИКА",          "#ffd600"),
    (30, "УМЕРЕНО ЗАТЯГАНЕ",            "#ff6d00"),
    (0,  "РЕСТРИКТИВНА ПОЛИТИКА",       "#d50000"),
]


def _apply_transform(series: pd.Series, transform: str) -> pd.Series:
    if transform == "yoy_pct":
        return series.pct_change(periods=12).dropna() * 100
    if transform == "first_diff":
        return series.diff().dropna()
    return series


def run(snapshot: dict[str, pd.Series]) -> dict[str, Any]:
    """Изчислява Credit & Monetary Policy lens за Китай."""
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
        "module": "credit",
        "label": "Монетарна политика и кредит",
        "icon": "🏦",
        "scores": {
            "monetary": {"score": composite, "label": "Монетарни условия"},
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

    policy = indicators.get("CN_POLICY_RATE")
    if policy:
        val = policy.get("current_value", 0)
        hints.append(
            f"PBoC policy rate {val:.2f}% — "
            + ("активен easing цикъл." if val < 2.0 else "умерено ниво.")
        )

    credit = indicators.get("CN_CREDIT_PRIVATE")
    if credit:
        val = credit.get("current_value", 0)
        if val > 190:
            hints.append(f"Кредит към частния сектор {val:.0f}% от БВП — debt overhang. Ограничава monetary policy transmission.")

    m2 = indicators.get("CN_M2_GDP")
    if m2:
        val = m2.get("current_value", 0)
        if val > 200:
            hints.append(f"M2 {val:.0f}% от БВП — най-висок в G20. Монетарна маса значително над реалната икономика.")

    cny = indicators.get("CN_CNY_USD")
    if cny:
        val = cny.get("current_value", 0)
        hints.append(f"CNY/USD {val:.4f} — управляван флоат. PBoC контролира дневния band ±2%.")

    return hints
